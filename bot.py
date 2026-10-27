import telebot
from telebot.types import BotCommand, InlineKeyboardMarkup, InlineKeyboardButton, ForceReply
import requests
import time
import threading
import sqlite3
import json
import os
from datetime import datetime, timedelta, timezone
from flask import Flask

# ================= ĐỒNG BỘ MÚI GIỜ VIỆT NAM =================
os.environ['TZ'] = 'Asia/Ho_Chi_Minh'
try:
    time.tzset()
except AttributeError:
    pass

# ================= 0. MINI WEB SERVER =================
app = Flask('')

@app.route('/')
def home():
    return "Bot Baccarat Auto Signal (Multi-AI Engine v5) is Running 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def self_ping():
    app_url = os.environ.get("RENDER_EXTERNAL_URL")
    if not app_url: return
    while True:
        time.sleep(600)
        try: requests.get(app_url, timeout=10)
        except: pass

# ================= 1. CẤU HÌNH CƠ BẢN =================
BOT_TOKEN = '8821941153:AAGvo-PWg9qmpk95x4rF73cTbudDurU4EM8'
ADMIN_ID = 8183008050 
LIEN_HE = "@AdminCuaBan" 

GIF_1_VAO_SANH = "CgACAgUAAxkBAANtat8dQcSf69J-PhDApL6M2WQytZAAArkeAAJecAhVocMq_43H9nI9BA"  
GIF_2_CHO_LENH = "CgACAgUAAxkBAANvat8dTA2D3ywvFv5WxCpZDXR0_kQAAnwpAAKyGElWlZ98dsadPrM9BA"  
GIF_3_CHOT_LAI = "CgACAgUAAxkBAANxat8dUNqmcTp81-Zh310m6zRYAbMAAmQiAAINmwlX9emEg5t-DCk9BA"  
GIF_4_CHOT_LO  = "CgACAgUAAxkBAANzat8dVEVTP8Bhs4XfBFugoWQUr3QAAgofAAJGrslXZjvL-_oDlx09BA"  

IMG_BANG_VON  = "bang_thong_ke.png"
VID_WIN_HAND  = "win_hand.mp4"   
VID_LOSE_HAND = "lose_hand.mp4"  

bot = telebot.TeleBot(BOT_TOKEN)
DB_FILE = "baccarat_bot.db"

bot_state = {"is_running": False, "force_stop": False, "selected_table": None}
ai_memory = {} 

# ================= 2. QUẢN LÝ DATABASE =================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS allowed_groups (chat_id INTEGER PRIMARY KEY)")
    cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS daily_reports (date TEXT, shift TEXT, result TEXT, PRIMARY KEY(date, shift))")
    conn.commit()
    
    default_settings = {
        "MUC_TIEU_LAI": "15", "MUC_TIEU_LO": "-10", "TY_LE_VAO": "5",
        "CA_HOAT_DONG": json.dumps(["12:00", "13:00", "14:00", "15:00"])
    }
    for k, v in default_settings.items():
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
    conn.commit()
    conn.close()

init_db()

def get_setting(key):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def set_setting(key, value):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

def load_all_settings():
    return {
        "MUC_TIEU_LAI": int(get_setting("MUC_TIEU_LAI")),
        "MUC_TIEU_LO": int(get_setting("MUC_TIEU_LO")),
        "TY_LE_VAO": int(get_setting("TY_LE_VAO")),
        "CA_HOAT_DONG": json.loads(get_setting("CA_HOAT_DONG"))
    }

bot_settings = load_all_settings()

def save_bot_settings():
    set_setting("MUC_TIEU_LAI", bot_settings["MUC_TIEU_LAI"])
    set_setting("MUC_TIEU_LO", bot_settings["MUC_TIEU_LO"])
    set_setting("TY_LE_VAO", bot_settings["TY_LE_VAO"])
    set_setting("CA_HOAT_DONG", json.dumps(bot_settings["CA_HOAT_DONG"]))

def load_groups():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT chat_id FROM allowed_groups")
    rows = cursor.fetchall()
    conn.close()
    return set(row[0] for row in rows)

def add_group_db(chat_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO allowed_groups (chat_id) VALUES (?)", (chat_id,))
    conn.commit()
    conn.close()

def remove_group_db(chat_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM allowed_groups WHERE chat_id = ?", (chat_id,))
    conn.commit()
    conn.close()

allowed_groups = load_groups()

def get_daily_report():
    now = datetime.now(timezone.utc) + timedelta(hours=7)
    today_str = now.strftime("%d-%m-%Y")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT shift, result FROM daily_reports WHERE date = ?", (today_str,))
    rows = cursor.fetchall()
    conn.close()
    shifts = {}
    total = 0
    for shift, res_str in rows:
        shifts[shift] = res_str
        try: total += float(res_str.replace("+", "").replace("%", ""))
        except: pass
    return {"date": today_str, "shifts": shifts, "total": total}

def save_shift_result(shift, result_str):
    now = datetime.now(timezone.utc) + timedelta(hours=7)
    today_str = now.strftime("%d-%m-%Y")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO daily_reports (date, shift, result) VALUES (?, ?, ?)", (today_str, shift, result_str))
    conn.commit()
    conn.close()

def create_board_msg():
    report = get_daily_report()
    date_str = report["date"].replace("-", " ➖ ") 
    msg = "🚨 **BẢNG LÃI CA GIAO DỊCH TRONG NGÀY CHO ANH EM NHA** 🚨\n\n"
    msg += f"🗓 **{date_str}**\n"
    ca_list = bot_settings['CA_HOAT_DONG']
    
    now = datetime.now(timezone.utc) + timedelta(hours=7)
    current_time_str = now.strftime("%H:%M")
    
    for i, ca in enumerate(ca_list, 1):
        hour_str = ca.split(":")[0] + "H" if ":00" in ca else ca.replace(":", "H")
        if ca in report["shifts"]: 
            msg += f"💸 {hour_str} CA {i} : {report['shifts'][ca]}\n"
        else: 
            if ca < current_time_str:
                msg += f"💸 {hour_str} CA {i} : OFF\n"
            else:
                msg += f"💸 {hour_str} CA {i} : \n"
                
    msg += f"\n➡️ **TỔNG LÃI : {report['total']}%** 💲\n\n📞 **THÔNG TIN LIÊN HỆ:**\n{LIEN_HE}"
    return msg

# ================= 3. GỬI LỆNH AN TOÀN =================
def safe_send(group_id, send_func, *args, **kwargs):
    global allowed_groups
    try:
        return send_func(group_id, *args, **kwargs)
    except telebot.apihelper.ApiTelegramException as e:
        if e.error_code in [403, 400]:
            if group_id in allowed_groups:
                allowed_groups.remove(group_id)
                remove_group_db(group_id)
        return None
    except Exception: return None

def gui_anh_hoac_video(group_id, file_id, caption):
    if not file_id: 
        safe_send(group_id, bot.send_message, caption, parse_mode="Markdown")
        return
    res = safe_send(group_id, bot.send_animation, file_id, caption=caption, parse_mode="Markdown")
    if res is not None: return
    res = safe_send(group_id, bot.send_video, file_id, caption=caption, parse_mode="Markdown")
    if res is not None: return
    safe_send(group_id, bot.send_message, caption, parse_mode="Markdown")
    
def gui_media_local_co_caption(group_id, file_path, caption):
    try:
        with open(file_path, 'rb') as f:
            res = safe_send(group_id, bot.send_animation, f, caption=caption, parse_mode="Markdown")
            if res is None:
                f.seek(0)
                res = safe_send(group_id, bot.send_video, f, caption=caption, parse_mode="Markdown")
            return res is not None
    except Exception:
        return False

# ================= 4. HỆ THỐNG ĐA THUẬT TOÁN AI (MULTI-STRATEGY ENGINE V5) =================
def fetch_api(table_id=""):
    url = f"https://api-bcrsexy.onrender.com/api/baccarat/{table_id}" if table_id else "https://api-bcrsexy.onrender.com/api/baccarat"
    try:
        res = requests.get(url, timeout=30)
        if res.status_code == 200: return res.json()
    except: pass
    return None

def opp(side):
    return 'P' if side == 'B' else 'B'

def strat_pattern_matcher(clean):
    """Chiến thuật 1: So khớp chuỗi lịch sử (Markov Pattern Matching) ngay trong bàn hiện tại"""
    n = len(clean)
    if n < 6: return clean[-1] if n > 0 else 'B'
    # Quét mẫu từ độ dài 4 xuống 2 trong lịch sử bàn để xem sau chuỗi này bàn hay ra gì nhất
    for length in (4, 3, 2):
        if n > length + 1:
            pattern = clean[-length:]
            counts = {'B': 0, 'P': 0}
            for i in range(n - length - 1):
                if clean[i:i+length] == pattern:
                    next_val = clean[i+length]
                    if next_val in counts:
                        counts[next_val] += 1
            if counts['B'] > counts['P']: return 'B'
            if counts['P'] > counts['B']: return 'P'
    return clean[-1]

def strat_classic_road(clean):
    """Chiến thuật 2: Bắt nhịp cầu chuẩn (Bệt, 1-1, 2-2, 2-1-2)"""
    n = len(clean)
    if n < 3: return 'B'
    if n >= 4:
        last4 = clean[-4:]
        # Cầu 2-2: BBPP -> B, PPBB -> P
        if last4 == ['B', 'B', 'P', 'P']: return 'B'
        if last4 == ['P', 'P', 'B', 'B']: return 'P'
        # Cầu 1-2-1 hoặc 2-1-2: B P P B -> P
        if last4 == ['B', 'P', 'P', 'B']: return 'P'
        if last4 == ['P', 'B', 'B', 'P']: return 'B'
    last3 = clean[-3:]
    # Bệt 3 -> Đánh tiếp bệt
    if last3[0] == last3[1] == last3[2]: return last3[-1]
    # 1-1 (B P B -> P)
    if last3[0] != last3[1] and last3[1] != last3[2]: return opp(last3[-1])
    # B B P -> P (Theo nhịp lên 2-2)
    if last3[0] == last3[1] and last3[1] != last3[2]: return last3[-1]
    # B P P -> B (Chặn cầu 1-2 về 1-2-1)
    return opp(last3[-1])

def strat_trend_follow(clean):
    """Chiến thuật 3: Thuận xu hướng bàn (Follow Last / Bám Bệt & Cầu Dài)"""
    if not clean: return 'B'
    return clean[-1]

def strat_chop_reversal(clean):
    """Chiến thuật 4: Bẻ cầu / Bắt đảo chiều liên tục (Ping-pong & Chặt Bệt)"""
    if not clean: return 'B'
    if len(clean) >= 3 and clean[-1] == clean[-2] != clean[-3]:
        # Nếu vừa lên nhịp 2 (VD: P B B) thì bẻ về P (cầu 1-2)
        return opp(clean[-1])
    return opp(clean[-1])

def get_all_strategy_predictions(results):
    clean = [r for r in results if r in ('B', 'P')]
    if len(clean) < 3:
        default = clean[-1] if clean else 'B'
        return {'S1': default, 'S2': default, 'S3': default, 'S4': opp(default)}
    return {
        'S1': strat_pattern_matcher(clean),
        'S2': strat_classic_road(clean),
        'S3': strat_trend_follow(clean),
        'S4': strat_chop_reversal(clean)
    }

def evaluate_table_ai(results):
    """Chấm điểm 4 chiến thuật trên lịch sử bàn (Sliding Window 8 tay gần nhất) để chọn Chiến thuật Vua"""
    clean = [r for r in results if r in ('B', 'P')]
    if len(clean) < 4:
        return 'B', 0.5, 'S2'
        
    scores = {'S1': [], 'S2': [], 'S3': [], 'S4': []}
    start_idx = max(3, len(clean) - 10)
    for i in range(start_idx, len(clean)):
        sub = clean[:i]
        actual = clean[i]
        preds = get_all_strategy_predictions(sub)
        for k, p in preds.items():
            scores[k].append(1 if p == actual else 0)
            
    best_strat = 'S1'
    best_wr = -1.0
    for k in ('S1', 'S2', 'S3', 'S4'):
        recent = scores[k][-6:] # Lấy 6 tay sát nhất để nhạy bén với việc đổi cầu
        wr = (sum(recent) / len(recent)) if recent else 0.5
        if wr > best_wr:
            best_wr = wr
            best_strat = k
            
    current_preds = get_all_strategy_predictions(clean)
    best_pred = current_preds[best_strat]
    
    # ĐÁNH GIÁ ĐỘ KẾT (CONFIDENCE) ĐỂ QUYẾT ĐỊNH VÀO 10%:
    # Nếu chiến thuật đang có chuỗi thông >= 3 tay liên tiếp hoặc đồng thuận cao
    recent_best = scores[best_strat][-6:]
    consecutive_wins = 0
    for x in reversed(recent_best):
        if x == 1: consecutive_wins += 1
        else: break
        
    # Đếm số chiến thuật có Winrate >= 60% cùng chỉ về 1 cửa
    agree_count = 0
    for k in ('S1', 'S2', 'S3', 'S4'):
        r_k = scores[k][-6:]
        wr_k = (sum(r_k) / len(r_k)) if r_k else 0
        if wr_k >= 0.6 and current_preds[k] == best_pred:
            agree_count += 1
            
    confidence = best_wr
    if consecutive_wins >= 3 or agree_count >= 2:
        confidence = max(confidence, 0.78)
        
    return best_pred, confidence, best_strat

def du_doan_thuat_toan(results):
    pred, _, _ = evaluate_table_ai(results)
    return pred

def kiem_tra_cau_dep_thuc_te(results, ban, win_streak, lose_streak, tong_lai):
    """Logic Quản Lý Vốn Thông Minh: Kết hợp Độ tự tin AI + Nhịp Cầu + Bù Lỗ Linh Hoạt"""
    clean = [r for r in results if r in ('B', 'P')]
    _, confidence, _ = evaluate_table_ai(clean)
    
    # Kiểm tra thế bài chuẩn mực (Bệt >= 4, 1-1 >= 4, 2-2 chuẩn)
    pattern_strong = False
    if len(clean) >= 4:
        l4 = clean[-4:]
        if l4[0] == l4[1] == l4[2] == l4[3]: pattern_strong = True
        elif l4[0] != l4[1] and l4[1] != l4[2] and l4[2] != l4[3]: pattern_strong = True
        elif l4 in (['B', 'B', 'P', 'P'], ['P', 'P', 'B', 'B']): pattern_strong = True

    # TH1: Tay Siêu Chắc Chắn (AI tự tin >= 75% hoặc vừa hợp bài chuẩn vừa đúng nhịp AI >= 66%) -> Đánh 10% ngay!
    if confidence >= 0.75 or (confidence >= 0.65 and pattern_strong):
        return True
        
    # TH2: Sau khi vừa thua 1 tay (lose_streak == 1, ví dụ đang G-5% hoặc sụt lãi)
    # Nếu cầu đang thuận (confidence >= 60% hoặc pattern_strong) -> Gấp thếp 10% để 1 tay vừa gỡ lỗ vừa lãi +5% luôn!
    if lose_streak == 1 and (confidence >= 0.60 or pattern_strong):
        return True
        
    # TH3: Thừa thắng xông lên (Vừa ăn tay trước win_streak >= 1 và cầu vẫn giữ nhịp >= 60%) -> Bứt tốc 10% chốt ca nhanh!
    if win_streak >= 1 and (confidence >= 0.60 or pattern_strong):
        return True
        
    # TH4: Đang âm vốn (tong_lai < 0) ở tay đầu của bàn mới rất đẹp (confidence >= 65%) -> Đánh 10% kéo về bờ nhanh
    if tong_lai < 0 and lose_streak == 0 and confidence >= 0.65:
        return True
        
    return False

def ai_continuous_learning():
    global ai_memory
    while True:
        time.sleep(5) 
        data = fetch_api()
        if not data: continue
        
        for tid, info in data.items():
            results = info.get("results", "")
            clean = [r for r in results if r in ('B', 'P')]
            if len(clean) < 5: continue
            
            pred, conf, strat = evaluate_table_ai(clean)
            ai_memory[tid] = {
                "last_len": len(results),
                "clean_len": len(clean),
                "predicted": pred,
                "confidence": conf,
                "best_strat": strat
            }
                    
        active_tids = data.keys()
        keys_to_del = [k for k in list(ai_memory.keys()) if k not in active_tids]
        for k in keys_to_del: del ai_memory[k]

def chon_ban_thong_minh(exclude_tables=None):
    """Quét toàn bộ sảnh, chấm điểm trực tiếp từng bàn ở thời điểm hiện tại để bốc bàn có tỷ lệ ăn cao nhất"""
    if exclude_tables is None:
        exclude_tables = set()
    elif not isinstance(exclude_tables, (set, list, tuple)):
        exclude_tables = {str(exclude_tables)}
    else:
        exclude_tables = {str(x) for x in exclude_tables}

    data = fetch_api()
    best_table = None
    best_score = -1.0

    if data:
        for tid, info in data.items():
            if str(tid) in exclude_tables:
                continue
            results = info.get("results", "")
            clean = [r for r in results if r in ('B', 'P')]
            # Chỉ chọn bàn đã có từ 6 đến 48 ván (đủ dữ liệu soi cầu và không sợ hết bài ngay lập tức)
            if 6 <= len(clean) <= 48:
                _, conf, _ = evaluate_table_ai(clean)
                # Ưu tiên bàn có độ tự tin cao nhất
                if conf > best_score:
                    best_score = conf
                    best_table = tid

        # Nếu tất cả bàn đều ít/nhiều ván hơn khoảng trên, nới lỏng điều kiện
        if not best_table:
            for tid, info in data.items():
                if str(tid) in exclude_tables:
                    continue
                clean = [r for r in info.get("results", "") if r in ('B', 'P')]
                if len(clean) >= 3:
                    _, conf, _ = evaluate_table_ai(clean)
                    if conf > best_score:
                        best_score = conf
                        best_table = tid

        if not best_table:
            for tid in data.keys():
                if str(tid) not in exclude_tables:
                    best_table = tid
                    break

    return best_table

# ================= 5. MENU & QUẢN LÝ NHÓM =================
bot.set_my_commands([
    BotCommand("/menu", "Mở Bảng Điều Khiển VIP"),
    BotCommand("/setgroup", "Cấp quyền Bot cho nhóm hiện tại"),
    BotCommand("/ca", "Chia lịch đánh nhanh (VD: /ca 12:00 22:00 60)"),
    BotCommand("/dungbot", "🛑 Dừng ca đánh khẩn cấp")
])

def send_menu(chat_id):
    so_ca = len(bot_settings['CA_HOAT_DONG'])
    gio_ca = ", ".join(bot_settings['CA_HOAT_DONG'])
    trang_thai = "🟢 ĐANG CHẠY" if bot_state["is_running"] else "💤 ĐANG NGHỈ"
    
    now = datetime.now(timezone.utc) + timedelta(hours=7)
    server_time = now.strftime("%H:%M:%S")
    
    text = (
        "👑 **TRUNG TÂM ĐIỀU KHIỂN AUTO SIGNAL (AI V5)** 👑\n\n"
        f"⚡️ Trạng thái Bot: **{trang_thai}**\n"
        f"🕒 Giờ Server: `{server_time}`\n"
        f"📊 **MỤC TIÊU GIAO DỊCH:**\n"
        f"┣ 🎯 **Chốt Lãi:** `+{bot_settings['MUC_TIEU_LAI']}%`\n"
        f"┣ 🛑 **Chốt Lỗ:** `{bot_settings['MUC_TIEU_LO']}%`\n"
        f"┗ 💰 **Quản Lý Vốn:** `{bot_settings['TY_LE_VAO']}%` - `{bot_settings['TY_LE_VAO']*2}%` (Đa Thuật Toán AI)\n\n"
        f"🗓 **LỊCH LÊN CA TỰ ĐỘNG:**\n"
        f"┣ ⏱ **Số ca hiện tại:** {so_ca} ca\n"
        f"┗ ⏰ **Khung giờ:** {gio_ca}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "👇 **BẢNG CHỨC NĂNG:** 👇"
    )
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("🎯 Sửa Chốt Lãi", callback_data="btn_lai"), InlineKeyboardButton("🛑 Sửa Chốt Lỗ", callback_data="btn_lo"))
    markup.row(InlineKeyboardButton("💰 Sửa Vốn Lệnh", callback_data="btn_von"), InlineKeyboardButton("⏰ Cài Lịch Ca", callback_data="btn_ca"))
    markup.row(InlineKeyboardButton("▶️ CHẠY THỬ CA THẬT", callback_data="btn_test"), InlineKeyboardButton("🔄 RESET LỖI KẸT", callback_data="btn_reset"))
    markup.row(InlineKeyboardButton("👥 QUẢN LÝ NHÓM BOT", callback_data="btn_groups"), InlineKeyboardButton("🛑 DỪNG BOT CẤP TỐC", callback_data="btn_stop"))
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(commands=['menu'])
def cmd_menu(message):
    if message.from_user.id != ADMIN_ID: return
    send_menu(message.chat.id)

@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    if call.from_user.id != ADMIN_ID: return
    chat_id = call.message.chat.id
    
    if call.data == "ignore":
        bot.answer_callback_query(call.id)
    elif call.data == "btn_lai":
        msg = bot.send_message(chat_id, "👉 Gõ số % chốt **LÃI** (VD: 15):", reply_markup=ForceReply())
        bot.register_next_step_handler(msg, step_set_val, 'MUC_TIEU_LAI')
    elif call.data == "btn_lo":
        msg = bot.send_message(chat_id, "👉 Gõ số % chốt **LỖ** (VD: 10):", reply_markup=ForceReply())
        bot.register_next_step_handler(msg, step_set_val, 'MUC_TIEU_LO')
    elif call.data == "btn_von":
        msg = bot.send_message(chat_id, "👉 Gõ số % đi **MỖI LỆNH** (VD: 5):", reply_markup=ForceReply())
        bot.register_next_step_handler(msg, step_set_val, 'TY_LE_VAO')
    elif call.data == "btn_von":
        msg = bot.send_message(chat_id, "👉 Gõ số % đi **MỖI LỆNH** (VD: 5):", reply_markup=ForceReply())
        bot.register_next_step_handler(msg, step_set_val, 'TY_LE_VAO')
    elif call.data == "btn_ca":
        msg = bot.send_message(chat_id, "👉 **CÀI ĐẶT CA NHANH 1 DÒNG**\nVD: `12:30 22:30 60`", parse_mode="Markdown", reply_markup=ForceReply())
        bot.register_next_step_handler(msg, step_ca_all_in_one)
    elif call.data == "btn_test":
        if not allowed_groups: bot.send_message(chat_id, "⚠️ Chưa có nhóm. Gõ `/setgroup`.")
        elif bot_state["is_running"]: bot.send_message(chat_id, "⚠️ Bot đang bận chạy ca!")
        else: 
            bot.send_message(chat_id, "🚀 Đang lên ca Test...")
            threading.Thread(target=chay_ca_danh, args=("TEST",)).start()
    elif call.data == "btn_stop":
        bot_state["force_stop"] = True
        bot.send_message(chat_id, "🛑 **ĐÃ PHÁT LỆNH DỪNG!**", parse_mode="Markdown")
    elif call.data == "btn_reset":
        bot_state["is_running"] = False
        bot_state["force_stop"] = False
        bot.send_message(chat_id, "✅ Đã Reset trạng thái thành công!")
        send_menu(chat_id)
    elif call.data == "btn_groups":
        show_groups_manager(call)
    elif call.data.startswith("delgrp_"):
        gid = int(call.data.split("_")[1])
        if gid in allowed_groups:
            allowed_groups.remove(gid)
            remove_group_db(gid)
            bot.answer_callback_query(call.id, "✅ Đã xóa quyền nhóm!")
            show_groups_manager(call) 
    elif call.data == "btn_back_menu":
        bot.delete_message(chat_id, call.message.message_id)
        send_menu(chat_id)

def show_groups_manager(call):
    markup = InlineKeyboardMarkup()
    if not allowed_groups:
        text = "⚠️ Chưa có nhóm nào được cấp quyền."
    else:
        text = "📋 **DANH SÁCH NHÓM ĐƯỢC BÁO LỆNH:**"
        for gid in list(allowed_groups):
            try:
                chat = bot.get_chat(gid)
                gname = chat.title if chat.title else str(gid)
            except:
                gname = f"ID: {gid}"
            markup.row(InlineKeyboardButton(f"👥 {gname[:25]}", callback_data="ignore"), InlineKeyboardButton("❌ Xóa", callback_data=f"delgrp_{gid}"))
    markup.row(InlineKeyboardButton("⬅️ QUAY LẠI MENU", callback_data="btn_back_menu"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

def step_set_val(message, key):
    try:
        val = int(message.text)
        if key == 'MUC_TIEU_LO' and val > 0: val = -val
        bot_settings[key] = val
        save_bot_settings()
        bot.reply_to(message, "✅ Đã lưu!")
        send_menu(message.chat.id)
    except: bot.reply_to(message, "⚠️ Lỗi: Chỉ gõ số.")

def parse_and_set_schedule(text, message):
    parts = text.replace('  ', ' ').strip().split()
    if len(parts) != 3:
        bot.reply_to(message, "⚠️ Lỗi cú pháp. VD: `12:30 22:30 60`", parse_mode="Markdown")
        return
    try:
        t_start = datetime.strptime(parts[0], "%H:%M")
        t_end = datetime.strptime(parts[1], "%H:%M")
        interval = int(parts[2])
        if t_end < t_start: t_end += timedelta(days=1)
        new_ca = []
        while t_start <= t_end:
            new_ca.append(t_start.strftime("%H:%M"))
            t_start += timedelta(minutes=interval)
        bot_settings['CA_HOAT_DONG'] = new_ca
        save_bot_settings()
        bot.reply_to(message, f"✅ Đã chia xong {len(new_ca)} ca.")
        send_menu(message.chat.id)
    except Exception as e:
        bot.reply_to(message, f"⚠️ Lỗi: {str(e)}", parse_mode="Markdown")

def step_ca_all_in_one(message):
    parse_and_set_schedule(message.text, message)

@bot.message_handler(commands=['ca'])
def cmd_ca_fast(message):
    if message.from_user.id != ADMIN_ID: return
    content = message.text.replace('/ca', '').strip()
    if not content:
        bot.reply_to(message, "👉 VD: `/ca 12:30 22:30 60`", parse_mode="Markdown")
        return
    parse_and_set_schedule(content, message)

@bot.message_handler(commands=['setgroup'])
def allow_group(message):
    if message.from_user.id != ADMIN_ID: return
    allowed_groups.add(message.chat.id)
    add_group_db(message.chat.id)
    bot.reply_to(message, "✅ Đã lưu nhóm.")

@bot.message_handler(commands=['dungbot'])
def cmd_dungbot(message):
    if message.from_user.id != ADMIN_ID: return
    bot_state["force_stop"] = True
    bot.send_message(message.chat.id, "🛑 Đang chốt ca...", parse_mode="Markdown")

def smart_sleep(seconds):
    for _ in range(seconds):
        if bot_state["force_stop"]: return False
        time.sleep(1)
    return True

# ================= 6. LUỒNG ĐÁNH THỰC CHIẾN =================
def wait_for_new_result(table_id, current_len, timeout=50):
    start = time.time()
    while time.time() - start < timeout and not bot_state["force_stop"]:
        time.sleep(3)
        d = fetch_api(table_id)
        if d and 'results' in d:
            if len(d['results']) > current_len: return d['results']
    return None

def chay_ca_danh(ca_time):
    if not allowed_groups or bot_state["is_running"]: return 
    bot_state["is_running"] = True
    bot_state["force_stop"] = False

    tong_lai = 0
    muc_tieu_lai = bot_settings['MUC_TIEU_LAI']
    muc_tieu_lo = bot_settings['MUC_TIEU_LO']
    ty_le_goc = bot_settings['TY_LE_VAO']
    
    win_streak = 0
    lose_streak = 0
    excluded_tables = set()

    for group_id in list(allowed_groups):
        gui_anh_hoac_video(group_id, GIF_1_VAO_SANH, "🔥 **MN ƠI CHUẨN BỊ VÀO SẢNH SEXY ĐỢI LỆNH!**")
    if not smart_sleep(4): return goto_chot_ca(tong_lai, ca_time, muc_tieu_lai, muc_tieu_lo)

    ban = chon_ban_thong_minh(excluded_tables)
    bot_state["selected_table"] = ban
    
    for group_id in list(allowed_groups):
        safe_send(group_id, bot.send_message, f"🎰 **BÁO BÀN MỚI:** Chọn bàn chuẩn **{ban}**", parse_mode="Markdown")
        gui_anh_hoac_video(group_id, GIF_2_CHO_LENH, f"⏳ **SẴN SÀNG TAY SAU VÀO LỆNH (Bàn {ban})**")

    data_ban = fetch_api(ban)
    if not data_ban: return goto_chot_ca(tong_lai, ca_time, muc_tieu_lai, muc_tieu_lo)
    so_van_cu = len(data_ban.get('results', ''))

    ket_qua_hien_tai = wait_for_new_result(ban, so_van_cu, 50)
    if ket_qua_hien_tai: so_van_cu = len(ket_qua_hien_tai)
    else: ket_qua_hien_tai = data_ban.get('results', '')

    while muc_tieu_lo < tong_lai < muc_tieu_lai and not bot_state["force_stop"]:
        # DỰ ĐOÁN BẰNG ĐA THUẬT TOÁN AI TỐI ƯU NHẤT CHO BÀN HIỆN TẠI
        predicted_side, confidence, _ = evaluate_table_ai(ket_qua_hien_tai)
        
        # KIỂM TRA ĐỘ KẾT ĐỂ ĐÁNH 10% (CHỐT LỜI NHANH & GỠ LỖ THÔNG MINH)
        cau_dep = kiem_tra_cau_dep_thuc_te(ket_qua_hien_tai, ban, win_streak, lose_streak, tong_lai)
                
        ty_le_hien_tai = (ty_le_goc * 2) if cau_dep else ty_le_goc
        
        # Kìm hãm nếu gần chạm mục tiêu lãi (Ví dụ đang +10%, mục tiêu +15% thì chỉ đánh 5%)
        khoang_cach_lai = muc_tieu_lai - tong_lai
        if khoang_cach_lai > 0 and ty_le_hien_tai > khoang_cach_lai:
            ty_le_hien_tai = khoang_cach_lai
            
        # Bảo vệ đáy chốt lỗ: Nếu đang gần mức lỗ tối đa (VD đang -10%, mục tiêu lỗ -15%), không đánh lố mức lỗ
        khoang_cach_lo = tong_lai - muc_tieu_lo
        if khoang_cach_lo > 0 and ty_le_hien_tai > khoang_cach_lo:
            ty_le_hien_tai = khoang_cach_lo
        
        if predicted_side == 'P':
            msg_lenh = f"👉 🔵 **CON {ty_le_hien_tai}%**"
        else:
            msg_lenh = f"👉 🔴 **CÁI {ty_le_hien_tai}%**"
            
        if ty_le_hien_tai > ty_le_goc:
            msg_lenh += " 🔥" 
            
        for group_id in list(allowed_groups):
            safe_send(group_id, bot.send_message, msg_lenh, parse_mode="Markdown")

        ket_qua_moi = wait_for_new_result(ban, so_van_cu, 50)
        if bot_state["force_stop"]: break

        # NẾU HẾT BÀI / XÁO BÀI -> ĐỔI BÀN
        if not ket_qua_moi or len(ket_qua_moi) < so_van_cu:
            ban_cu = ban
            excluded_tables.add(str(ban_cu))
            ban = chon_ban_thong_minh(excluded_tables)
            bot_state["selected_table"] = ban
            win_streak = 0
            lose_streak = 0
            
            for group_id in list(allowed_groups):
                safe_send(group_id, bot.send_message, f"🔄 **Hết bài đổi bàn...** Bàn {ban_cu} hết bài, hệ thống chuyển sang bàn mới!", parse_mode="Markdown")
                safe_send(group_id, bot.send_message, f"🎰 **BÁO BÀN MỚI:** Chuyển sang bàn chuẩn **{ban}**", parse_mode="Markdown")
                gui_anh_hoac_video(group_id, GIF_2_CHO_LENH, f"⏳ **SẴN SÀNG TAY SAU VÀO LỆNH (Bàn {ban})**")
            
            data_ban_moi = fetch_api(ban)
            so_van_cu = len(data_ban_moi.get('results', '')) if data_ban_moi else 0
            ket_qua_hien_tai = wait_for_new_result(ban, so_van_cu, 50)
            if ket_qua_hien_tai: so_van_cu = len(ket_qua_hien_tai)
            continue 

        actual_result = ket_qua_moi[-1]
        so_van_cu = len(ket_qua_moi)
        ket_qua_hien_tai = ket_qua_moi 

        if actual_result == 'T':
            str_tong_lai = f"+{tong_lai}" if tong_lai >= 0 else f"{tong_lai}"
            msg_ketqua = f"⚖️ **HÒA {str_tong_lai}%**"
            for group_id in list(allowed_groups):
                safe_send(group_id, bot.send_message, msg_ketqua, parse_mode="Markdown")
                
        elif actual_result == predicted_side:
            tong_lai += ty_le_hien_tai
            win_streak += 1
            lose_streak = 0
            str_tong_lai = f"+{tong_lai}" if tong_lai >= 0 else f"{tong_lai}"
            msg_ketqua = f"💰 **H{str_tong_lai}%**"
            for group_id in list(allowed_groups):
                if not gui_media_local_co_caption(group_id, VID_WIN_HAND, msg_ketqua):
                    safe_send(group_id, bot.send_message, msg_ketqua, parse_mode="Markdown")
                    
        else:
            tong_lai -= ty_le_hien_tai
            lose_streak += 1
            win_streak = 0
            str_tong_lai = f"+{tong_lai}" if tong_lai >= 0 else f"{tong_lai}"
            msg_ketqua = f"❌ **G{str_tong_lai}%**"
            for group_id in list(allowed_groups):
                if not gui_media_local_co_caption(group_id, VID_LOSE_HAND, msg_ketqua):
                    safe_send(group_id, bot.send_message, msg_ketqua, parse_mode="Markdown")
                    
            # CƠ CHẾ ĐỔI BÀN KHI BÀN BẺ CẦU: Nếu gãy 2 tay liên tiếp hoặc AI tụt độ tự tin < 45% -> Đổi sang bàn đang thông ngay!
            _, new_conf, _ = evaluate_table_ai(ket_qua_hien_tai)
            if (lose_streak >= 2 or new_conf < 0.45) and tong_lai > muc_tieu_lo:
                ban_cu = ban
                excluded_tables.add(str(ban_cu))
                ban = chon_ban_thong_minh(excluded_tables)
                bot_state["selected_table"] = ban
                win_streak = 0
                for group_id in list(allowed_groups):
                    safe_send(group_id, bot.send_message, f"⚠️ **Bàn {ban_cu} đổi nhịp cầu!** Hệ thống lập tức chuyển sang bàn **{ban}** (Cầu đang thông)!", parse_mode="Markdown")
                    gui_anh_hoac_video(group_id, GIF_2_CHO_LENH, f"⏳ **SẴN SÀNG TAY SAU VÀO LỆNH (Bàn {ban})**")
                data_ban_moi = fetch_api(ban)
                so_van_cu = len(data_ban_moi.get('results', '')) if data_ban_moi else 0
                ket_qua_hien_tai = wait_for_new_result(ban, so_van_cu, 50)
                if ket_qua_hien_tai: so_van_cu = len(ket_qua_hien_tai)
                continue
                    
        smart_sleep(2)

    goto_chot_ca(tong_lai, ca_time, muc_tieu_lai, muc_tieu_lo)

def goto_chot_ca(tong_lai, ca_time, muc_tieu_lai, muc_tieu_lo):
    if bot_state["force_stop"]:
        for group_id in list(allowed_groups):
            safe_send(group_id, bot.send_message, "⚠️ **CA ĐÁNH BỊ DỪNG ĐỘT XUẤT!**", parse_mode="Markdown")
        time.sleep(2)

    str_tong_lai = f"+{tong_lai}%" if tong_lai >= 0 else f"{tong_lai}%"
    if ca_time != "TEST": save_shift_result(ca_time, str_tong_lai)

    for group_id in list(allowed_groups):
        if tong_lai >= muc_tieu_lai or (bot_state["force_stop"] and tong_lai > 0):
            gui_anh_hoac_video(group_id, GIF_3_CHOT_LAI, f"🎉 **CHỐT LÃI {str_tong_lai} NGƯNG CA**\n🔥 Húp rực rỡ!")
        elif tong_lai <= muc_tieu_lo or (bot_state["force_stop"] and tong_lai < 0):
            gui_anh_hoac_video(group_id, GIF_4_CHOT_LO, f"🛑 **CHỐT LỖ {str_tong_lai} NGƯNG CA**\nCa sau làm lại!")
        else:
            safe_send(group_id, bot.send_message, f"⚖️ **HÒA {str_tong_lai}**\nCa sau làm lại!", parse_mode="Markdown")
        
        time.sleep(2)
        
        board_msg = create_board_msg()
        try:
            with open(IMG_BANG_VON, 'rb') as photo:
                safe_send(group_id, bot.send_photo, photo, caption=board_msg, parse_mode="Markdown")
        except Exception:
            safe_send(group_id, bot.send_message, board_msg, parse_mode="Markdown")
    
    bot_state["is_running"] = False
    bot_state["force_stop"] = False

# ================= 7. LUỒNG ĐẾM GIỜ LÊN CA =================
def get_current_time_str():
    now = datetime.now(timezone.utc) + timedelta(hours=7)
    return now.strftime("%H:%M")

def run_scheduler():
    last_run_time = ""
    while True:
        current_time = get_current_time_str()
        if current_time != last_run_time:
            if current_time in bot_settings.get('CA_HOAT_DONG', []):
                last_run_time = current_time 
                if not bot_state["is_running"]:
                    threading.Thread(target=chay_ca_danh, args=(current_time,)).start()
        time.sleep(1) 

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    threading.Thread(target=self_ping, daemon=True).start()
    threading.Thread(target=ai_continuous_learning, daemon=True).start()
    threading.Thread(target=run_scheduler, daemon=True).start()
    print("✅ Hệ thống BOT Đã Sẵn Sàng (Multi-AI Engine v5)!")
    bot.infinity_permissions_polling() if hasattr(bot, 'infinity_permissions_polling') else bot.infinity_polling()
