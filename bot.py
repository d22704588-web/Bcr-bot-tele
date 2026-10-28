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
    return "Bot Baccarat Auto Signal (Sniper AI Engine v6) is Running 24/7!"

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
        "MUC_TIEU_LAI": "15", 
        "MUC_TIEU_LO": "-10", 
        "TY_LE_VAO": "5",
        "CA_HOAT_DONG": json.dumps(["12:00", "13:00", "14:00", "15:00"]),
        "CA_NGHI": json.dumps([])
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
    ca_nghi_raw = get_setting("CA_NGHI")
    return {
        "MUC_TIEU_LAI": int(get_setting("MUC_TIEU_LAI") or 15),
        "MUC_TIEU_LO": int(get_setting("MUC_TIEU_LO") or -10),
        "TY_LE_VAO": int(get_setting("TY_LE_VAO") or 5),
        "CA_HOAT_DONG": json.loads(get_setting("CA_HOAT_DONG") or '["12:00"]'),
        "CA_NGHI": json.loads(ca_nghi_raw) if ca_nghi_raw else []
    }

bot_settings = load_all_settings()

def save_bot_settings():
    set_setting("MUC_TIEU_LAI", bot_settings["MUC_TIEU_LAI"])
    set_setting("MUC_TIEU_LO", bot_settings["MUC_TIEU_LO"])
    set_setting("TY_LE_VAO", bot_settings["TY_LE_VAO"])
    set_setting("CA_HOAT_DONG", json.dumps(bot_settings["CA_HOAT_DONG"]))
    set_setting("CA_NGHI", json.dumps(bot_settings.get("CA_NGHI", [])))

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
    # Làm tròn số nguyên nếu không có phần lẻ thập phân (ví dụ +15% thay vì +15.0%)
    if isinstance(total, float) and total.is_integer():
        total = int(total)
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
    ca_nghi = set(bot_settings.get('CA_NGHI', []))
    
    now = datetime.now(timezone.utc) + timedelta(hours=7)
    current_time_str = now.strftime("%H:%M")
    
    # Chỉ đánh số thứ tự CA cho những ca Hoạt Động (đã loại trừ ca nghỉ)
    active_ca_list = [c for c in ca_list if c not in ca_nghi]
    
    for i, ca in enumerate(active_ca_list, 1):
        hour_str = ca.split(":")[0] + "H" if ":00" in ca else ca.replace(":", "H")
        if ca in report["shifts"]: 
            msg += f"💸 {hour_str} CA {i} : {report['shifts'][ca]}\n"
        else: 
            if ca < current_time_str:
                msg += f"💸 {hour_str} CA {i} : OFF\n"
            else:
                msg += f"💸 {hour_str} CA {i} : \n"
                
    total_str = f"+{report['total']}" if report['total'] > 0 else f"{report['total']}"
    msg += f"\n➡️ **TỔNG LÃI : {total_str}%** 💲\n\n📞 **THÔNG TIN LIÊN HỆ:**\n{LIEN_HE}"
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

# ================= 4. THUẬT TOÁN SNIPER AI V6 (CHỐNG BẺ CẦU & BẮT CẦU THật) =================
def fetch_api(table_id=""):
    url = f"https://api-bcrsexy.onrender.com/api/baccarat/{table_id}" if table_id else "https://api-bcrsexy.onrender.com/api/baccarat"
    try:
        res = requests.get(url, timeout=30)
        if res.status_code == 200: return res.json()
    except: pass
    return None

def opp(side):
    return 'P' if side == 'B' else 'B'

def get_columns(clean):
    """Tách chuỗi kết quả thành các cột Big Road (Ví dụ: ['BBB', 'P', 'BB', 'PP'])"""
    if not clean: return []
    cols = []
    cur = clean[0]
    for c in clean[1:]:
        if c == cur[0]:
            cur += c
        else:
            cols.append(cur)
            cur = c
    cols.append(cur)
    return cols

def analyze_road_structure(clean):
    """
    Phân tích cấu trúc Big Road thực tế giống cao thủ soi cầu:
    Trả về: (Dự_đoán_Thuận_Cầu, Độ_Chuẩn_Cầu 0.0 -> 1.0, Tên_Thế_Cầu)
    """
    if len(clean) < 4:
        return (clean[-1] if clean else 'B'), 0.5, "Cầu Mới"
        
    cols = get_columns(clean)
    cur_col = cols[-1]
    cur_side = cur_col[0]
    cur_len = len(cur_col)
    
    # 1. THẾ CẦU BỆT DÀI (Đang bệt từ 4 cây trở lên -> Tuyệt đối ôm bệt, không bẻ!)
    if cur_len >= 4:
        return cur_side, 0.90, "Cầu Bệt Dài"
        
    # 2. THẾ CẦU BỆT 3 (Nếu trong bàn trước đó đã từng có cột >= 3 thì ôm bệt tiếp)
    if cur_len == 3:
        has_dragon_before = any(len(c) >= 3 for c in cols[:-1])
        if has_dragon_before:
            return cur_side, 0.82, "Cầu Bệt"
        else:
            return cur_side, 0.72, "Chớm Bệt 3"
            
    # 3. THẾ CẦU 1-1 PINGPONG (Từ 3 cột liên tiếp trước đó đều dài 1)
    if len(cols) >= 4:
        prev_3_lens = [len(c) for c in cols[-4:-1]]
        if prev_3_lens == [1, 1, 1] and cur_len == 1:
            return opp(cur_side), 0.88, "Cầu 1-1 Thông"
            
    # 4. THẾ CẦU 2-2 (Các cột trước dài 2-2)
    if len(cols) >= 3:
        prev_2_lens = [len(c) for c in cols[-3:-1]]
        if prev_2_lens == [2, 2]:
            if cur_len == 1:
                return cur_side, 0.86, "Cầu 2-2 (Lên 2)"
            elif cur_len == 2:
                return opp(cur_side), 0.86, "Cầu 2-2 (Đảo)"
                
    # 5. THẾ CẦU 2-1-2-1 (Nhịp nhảy 2-1)
    if len(cols) >= 4:
        prev_3_lens = [len(c) for c in cols[-4:-1]]
        if prev_3_lens == [1, 2, 1]:
            if cur_len == 1:
                return cur_side, 0.80, "Cầu 1-2-1 (Lên 2)"
            elif cur_len == 2:
                return opp(cur_side), 0.80, "Cầu 1-2-1 (Đảo)"
        elif prev_3_lens == [2, 1, 2]:
            if cur_len == 1:
                return opp(cur_side), 0.80, "Cầu 2-1-2 (Đảo 1)"
                
    # 6. THẾ CẦU NGHIÊNG (Shoe Bias: 12 ván gần nhất 1 bên chiếm >= 75%)
    recent_12 = clean[-12:]
    b_rate = recent_12.count('B') / len(recent_12)
    if b_rate >= 0.75:
        return 'B', 0.78, "Cầu Nghiêng Cái"
    elif b_rate <= 0.25:
        return 'P', 0.78, "Cầu Nghiêng Con"
        
    # 7. SO KHỚP LỊCH SỬ BÀN (Markov Pattern 3-4 tay trong hộp bài hiện tại)
    n = len(clean)
    for length in (4, 3):
        if n > length + 2:
            pat = clean[-length:]
            cnt = {'B': 0, 'P': 0}
            for i in range(n - length - 1):
                if clean[i:i+length] == pat:
                    nxt = clean[i+length]
                    if nxt in cnt: cnt[nxt] += 1
            total_match = cnt['B'] + cnt['P']
            if total_match >= 2:
                if cnt['B'] / total_match >= 0.75:
                    return 'B', 0.75, "Lặp Khuôn Bàn"
                if cnt['P'] / total_match >= 0.75:
                    return 'P', 0.75, "Lặp Khuôn Bàn"

    # Nếu không thuộc các cầu rõ ràng trên:
    # Kiểm tra 2 cột gần nhất xem bàn đang thích đi ngắn (1-1) hay đi cặp (2-2)
    if len(cols) >= 2:
        prev_len = len(cols[-2])
        if prev_len == 1 and cur_len == 1:
            return opp(cur_side), 0.60, "Nhịp Đảo"
        if prev_len >= 2 and cur_len == 1:
            return cur_side, 0.62, "Nhịp Theo Cặp"
            
    return cur_side, 0.52, "Cầu Phức Tạp"

def evaluate_table_ai(results):
    """
    Cơ chế Tự Đảo Chiều Thông Minh (Meta-Flip):
    Kiểm tra trên 6 ván gần nhất của bàn:
    - Nếu thuật toán Thuận Cầu đang ăn (>= 60%) -> Đánh Thuận Cầu!
    - Nếu bàn đang cố tình BẺ thuật toán Thuận Cầu (Thuận Cầu chỉ đúng <= 33%, tức là đánh Ngược lại ăn >= 67%) -> Lập tức kích hoạt chế độ ĐÁNH NGƯỢC BẺ NHÀ CÁI!
    - Nếu đang 50/50 loạn xạ -> Báo độ tự tin thấp để đổi bàn!
    """
    clean = [r for r in results if r in ('B', 'P')]
    if len(clean) < 5:
        return (clean[-1] if clean else 'B'), 0.5, "Khởi tạo"
        
    # Chấm điểm độ khớp thực tế trên 6 tay sát nhất
    start_idx = max(4, len(clean) - 6)
    hits = []
    for i in range(start_idx, len(clean)):
        sub = clean[:i]
        actual = clean[i]
        pred_i, _, _ = analyze_road_structure(sub)
        hits.append(1 if pred_i == actual else 0)
        
    raw_pred, struct_score, pattern_name = analyze_road_structure(clean)
    
    if not hits:
        return raw_pred, struct_score, pattern_name
        
    win_rate = sum(hits) / len(hits)
    
    # Đếm chuỗi thắng/thua sát nhất
    streak_win = 0
    for x in reversed(hits):
        if x == 1: streak_win += 1
        else: break
        
    streak_lose = 0
    for x in reversed(hits):
        if x == 0: streak_lose += 1
        else: break

    # TRƯỜNG HỢP 1: Bàn đang đi rất thuận theo bộ đọc cầu (Winrate >= 66% hoặc vừa thông >= 2 tay)
    if win_rate >= 0.65 or streak_win >= 2:
        conf = max(struct_score, win_rate)
        if streak_win >= 3: conf = max(conf, 0.88)
        return raw_pred, conf, pattern_name
        
    # TRƯỜNG HỢP 2: Bàn đang BẺ CẦU liên tục (Winrate thuận <= 34% hoặc gãy thông >= 3 tay)
    # -> Tự động LẬT NGƯỢC dự đoán (Anti-Trap) để ăn trọn nhịp bẻ của nhà cái!
    if win_rate <= 0.34 or streak_lose >= 3:
        anti_wr = 1.0 - win_rate
        conf = max(0.75, anti_wr)
        return opp(raw_pred), conf, f"Bắt Bài Bẻ Cầu ({pattern_name})"
        
    # TRƯỜNG HỢP 3: Bàn đang lưng chừng (50/50)
    return raw_pred, (win_rate * 0.6 + struct_score * 0.4), pattern_name

def du_doan_thuat_toan(results):
    pred, _, _ = evaluate_table_ai(results)
    return pred

def kiem_tra_cau_dep_thuc_te(results, ban, win_streak, lose_streak, tong_lai):
    """
    QUẢN LÝ VỐN KỶ LUẬT THÉP (BẢO VỆ TÀI KHOẢN & CHỐT LỜI NHANH):
    1. KHÔNG BAO GIỜ đánh 10% ở tay đầu tiên vừa vào bàn (tránh trường hợp vừa vào bị lừa dẫn tới âm sâu -10% ngay tay đầu).
    2. Khi vừa HÚP tay trước (win_streak >= 1) VÀ cầu bàn vẫn đang đẹp (conf >= 0.72) -> Nhồi 10% 🔥 (Lấy tiền lãi của nhà cái để đánh bứt tốc, thắng là +15% nghỉ luôn, nếu chẳng may thua cũng chỉ về lại 0% chứ không âm vốn!).
    3. Nếu vừa GÃY 1 tay 5% (lose_streak == 1): Chỉ được phép đánh 10% 🔥 khi và chỉ khi bàn đang có thế cầu CỰC KỲ RÕ RÀNG (conf >= 0.82 - như Bệt dài, 1-1 thông, 2-2 chuẩn). Nếu cầu bình thường -> Bắt buộc đi 5% để giữ mạng!
    4. Nếu đã gãy 2 tay (lose_streak >= 2) -> Tuyệt đối chỉ đi 5%, không gấp thếp mù quáng tránh chạm mốc cắt lỗ -15%!
    """
    if lose_streak >= 2:
        return False
        
    clean = [r for r in results if r in ('B', 'P')]
    _, confidence, _ = evaluate_table_ai(clean)
    
    # Ưu tiên số 1: Thừa thắng xông lên (Đang có đà thắng win_streak >= 1 và cầu ổn định >= 70%)
    if win_streak >= 1 and confidence >= 0.70:
        return True
        
    # Ưu tiên số 2: Gỡ nhanh sau 1 tay sẩy chân (lose_streak == 1) NHƯNG cầu phải thực sự nét (>= 82%)
    if lose_streak == 1 and confidence >= 0.82:
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
            
            pred, conf, pat_name = evaluate_table_ai(clean)
            ai_memory[tid] = {
                "last_len": len(results),
                "clean_len": len(clean),
                "predicted": pred,
                "confidence": conf,
                "pattern": pat_name
            }
                    
        active_tids = data.keys()
        keys_to_del = [k for k in list(ai_memory.keys()) if k not in active_tids]
        for k in keys_to_del: del ai_memory[k]

def chon_ban_thong_minh(exclude_tables=None):
    """Quét toàn bộ sảnh, chọn bàn đang có Thế Cầu Đẹp & Độ Tự Tin AI cao nhất"""
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
        # Vòng 1: Tìm các bàn đang ở độ chín vàng (8 đến 45 ván) và có cầu rõ nét
        for tid, info in data.items():
            if str(tid) in exclude_tables:
                continue
            results = info.get("results", "")
            clean = [r for r in results if r in ('B', 'P')]
            if 8 <= len(clean) <= 45:
                _, conf, _ = evaluate_table_ai(clean)
                if conf > best_score:
                    best_score = conf
                    best_table = tid

        # Vòng 2: Nới lỏng số ván (5 đến 52 ván) nếu vòng 1 không có bàn nào
        if not best_table:
            for tid, info in data.items():
                if str(tid) in exclude_tables:
                    continue
                clean = [r for r in info.get("results", "") if r in ('B', 'P')]
                if 5 <= len(clean) <= 52:
                    _, conf, _ = evaluate_table_ai(clean)
                    if conf > best_score:
                        best_score = conf
                        best_table = tid

        # Vòng 3: Dự phòng
        if not best_table:
            for tid in data.keys():
                if str(tid) not in exclude_tables:
                    best_table = tid
                    break

    return best_table

# ================= 5. MENU & QUẢN LÝ CA / CA NGHỈ =================
bot.set_my_commands([
    BotCommand("/menu", "Mở Bảng Điều Khiển VIP"),
    BotCommand("/setgroup", "Cấp quyền Bot cho nhóm hiện tại"),
    BotCommand("/ca", "Chia lịch đánh nhanh (VD: /ca 12:00 22:00 60)"),
    BotCommand("/canghi", "Chọn các giờ nghỉ (VD: /canghi 14 15 17 18)"),
    BotCommand("/dungbot", "🛑 Dừng ca đánh khẩn cấp")
])

def send_menu(chat_id):
    all_ca = bot_settings['CA_HOAT_DONG']
    ca_nghi = set(bot_settings.get('CA_NGHI', []))
    active_ca = [c for c in all_ca if c not in ca_nghi]
    
    gio_ca_active = ", ".join(active_ca) if active_ca else "Trống"
    gio_ca_nghi = ", ".join(sorted(list(ca_nghi))) if ca_nghi else "Không có"
    trang_thai = "🟢 ĐANG CHẠY" if bot_state["is_running"] else "💤 ĐANG NGHỈ"
    
    now = datetime.now(timezone.utc) + timedelta(hours=7)
    server_time = now.strftime("%H:%M:%S")
    
    text = (
        "👑 **TRUNG TÂM ĐIỀU KHIỂN AUTO SIGNAL (SNIPER V6)** 👑\n\n"
        f"⚡️ Trạng thái Bot: **{trang_thai}**\n"
        f"🕒 Giờ Server: `{server_time}`\n"
        f"📊 **MỤC TIÊU GIAO DỊCH:**\n"
        f"┣ 🎯 **Chốt Lãi:** `+{bot_settings['MUC_TIEU_LAI']}%`\n"
        f"┣ 🛑 **Chốt Lỗ:** `{bot_settings['MUC_TIEU_LO']}%`\n"
        f"┗ 💰 **Quản Lý Vốn:** `{bot_settings['TY_LE_VAO']}%` (Nhồi `{bot_settings['TY_LE_VAO']*2}%` khi thông cầu)\n\n"
        f"🗓 **LỊCH LÊN CA TỰ ĐỘNG:**\n"
        f"┣ ⏱ **Số ca chạy thực tế:** {len(active_ca)} ca\n"
        f"┣ ⏰ **Khung giờ chạy:** `{gio_ca_active}`\n"
        f"┗ 💤 **Khung giờ nghỉ:** `{gio_ca_nghi}`\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "👇 **BẢNG CHỨC NĂNG:** 👇"
    )
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("🎯 Sửa Chốt Lãi", callback_data="btn_lai"), InlineKeyboardButton("🛑 Sửa Chốt Lỗ", callback_data="btn_lo"))
    markup.row(InlineKeyboardButton("💰 Sửa Vốn Lệnh", callback_data="btn_von"), InlineKeyboardButton("⏰ Cài Lịch Ca", callback_data="btn_ca"))
    markup.row(InlineKeyboardButton("💤 Chọn Ca Nghỉ (Gõ Số)", callback_data="btn_canghi_text"), InlineKeyboardButton("🎛 Bật/Tắt Ca Nghỉ (Nút)", callback_data="btn_canghi_ui"))
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
        msg = bot.send_message(chat_id, "👉 Gõ số % chốt **LỖ** (VD: 15):", reply_markup=ForceReply())
        bot.register_next_step_handler(msg, step_set_val, 'MUC_TIEU_LO')
    elif call.data == "btn_von":
        msg = bot.send_message(chat_id, "👉 Gõ số % đi **MỖI LỆNH** (VD: 5):", reply_markup=ForceReply())
        bot.register_next_step_handler(msg, step_set_val, 'TY_LE_VAO')
    elif call.data == "btn_ca":
        msg = bot.send_message(
            chat_id, 
            "👉 **CÀI ĐẶT LỊCH CA NHANH**\n"
            "• Cách 1 (Chỉ tạo lịch): `12:00 22:00 60`\n"
            "• Cách 2 (Tạo lịch xong chọn tiếp ca nghỉ): Sau khi nhập dòng này bạn có thể bấm nút **Chọn Ca Nghỉ** để loại các giờ muốn bỏ.",
            parse_mode="Markdown", reply_markup=ForceReply()
        )
        bot.register_next_step_handler(msg, step_ca_all_in_one)
    elif call.data == "btn_canghi_text":
        all_ca_str = ", ".join(bot_settings['CA_HOAT_DONG'])
        msg = bot.send_message(
            chat_id,
            f"📋 **Các ca trong khung hiện tại:**\n`{all_ca_str}`\n\n"
            "👉 **Nhập các giờ bạn muốn NGHỈ (bỏ qua), cách nhau bằng dấu cách:**\n"
            "• Ví dụ gõ: `14 15 17 18` (hoặc `14:00 15:00 17:00 18:00` đều được)\n"
            "• Gõ `0` hoặc `xoa` nếu muốn chạy lại tất cả các ca (không nghỉ ca nào).",
            parse_mode="Markdown", reply_markup=ForceReply()
        )
        bot.register_next_step_handler(msg, step_set_canghi_text)
    elif call.data == "btn_canghi_ui":
        show_canghi_ui(call)
    elif call.data.startswith("toggleca_"):
        ca_val = call.data.split("_", 1)[1]
        ca_nghi_list = set(bot_settings.get('CA_NGHI', []))
        if ca_val in ca_nghi_list:
            ca_nghi_list.remove(ca_val)
            bot.answer_callback_query(call.id, f"✅ Đã BẬT lại ca {ca_val}")
        else:
            ca_nghi_list.add(ca_val)
            bot.answer_callback_query(call.id, f"💤 Đã cho NGHỈ ca {ca_val}")
        bot_settings['CA_NGHI'] = sorted(list(ca_nghi_list))
        save_bot_settings()
        show_canghi_ui(call)
    elif call.data == "clear_canghi":
        bot_settings['CA_NGHI'] = []
        save_bot_settings()
        bot.answer_callback_query(call.id, "✅ Đã bật chạy toàn bộ các ca!")
        show_canghi_ui(call)
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

def show_canghi_ui(call):
    """Bảng bấm nút Bật/Tắt từng ca trực quan"""
    all_ca = bot_settings['CA_HOAT_DONG']
    ca_nghi = set(bot_settings.get('CA_NGHI', []))
    markup = InlineKeyboardMarkup()
    
    row_btns = []
    for ca in all_ca:
        if ca in ca_nghi:
            btn_text = f"❌ {ca} (Nghỉ)"
        else:
            btn_text = f"✅ {ca} (Chạy)"
        row_btns.append(InlineKeyboardButton(btn_text, callback_data=f"toggleca_{ca}"))
        if len(row_btns) == 3:
            markup.row(*row_btns)
            row_btns = []
    if row_btns:
        markup.row(*row_btns)
        
    markup.row(InlineKeyboardButton("🔄 Bật Lại Tất Cả Các Ca", callback_data="clear_canghi"))
    markup.row(InlineKeyboardButton("⬅️ LƯU & QUAY LẠI MENU", callback_data="btn_back_menu"))
    
    text = (
        "🎛 **BẢNG CHỌN CA NGHỈ TRỰC QUAN**\n\n"
        "• Bấm vào giờ nào để chuyển đổi giữa **✅ Chạy** và **❌ Nghỉ**.\n"
        "• Ca nào đánh dấu **❌ Nghỉ** sẽ được loại bỏ khỏi lịch chạy và bảng lãi."
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

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

def match_off_tokens_to_shifts(tokens, shift_list):
    """Nhận diện thông minh: Người dùng gõ '14 15 17 18' hoặc '14:00 15h 17:30' đều khớp chính xác với các ca trong lịch"""
    matched = set()
    for tok in tokens:
        t = tok.strip().lower().replace('h', ':')
        if not t: continue
        if t.endswith(':'): t = t[:-1]
        
        if ':' in t:
            try:
                dt = datetime.strptime(t, "%H:%M")
                norm = dt.strftime("%H:%M")
                if norm in shift_list:
                    matched.add(norm)
            except:
                pass
        else:
            # Nếu chỉ gõ số giờ (VD: "14", "15", "17", "18")
            if t.isdigit():
                h_int = int(t)
                h_prefix = f"{h_int:02d}:"
                for s in shift_list:
                    if s.startswith(h_prefix):
                        matched.add(s)
    return sorted(list(matched))

def parse_and_set_schedule(text, message):
    parts = text.replace('  ', ' ').strip().split()
    if len(parts) < 3:
        bot.reply_to(message, "⚠️ Lỗi cú pháp. VD: `12:00 22:00 60`", parse_mode="Markdown")
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
        # Nếu người dùng gõ kèm luôn các giờ nghỉ ở phía sau hoặc muốn hỏi tiếp
        if len(parts) > 3:
            off_tokens = parts[3:]
            bot_settings['CA_NGHI'] = match_off_tokens_to_shifts(off_tokens, new_ca)
            save_bot_settings()
            active_cnt = len(new_ca) - len(bot_settings['CA_NGHI'])
            bot.reply_to(message, f"✅ Đã tạo lịch và loại bỏ {len(bot_settings['CA_NGHI'])} ca nghỉ! Còn lại **{active_cnt} ca** hoạt động.", parse_mode="Markdown")
            send_menu(message.chat.id)
        else:
            bot_settings['CA_NGHI'] = []
            save_bot_settings()
            all_ca_str = ", ".join(new_ca)
            msg = bot.reply_to(
                message, 
                f"✅ Đã chia xong **{len(new_ca)} ca**: `{all_ca_str}`\n\n"
                "💤 **BƯỚC TIẾP THEO (CHỌN CA NGHỈ):**\n"
                "👉 Hãy gõ các giờ bạn muốn **NGHỈ (loại ra)** cách nhau bằng dấu cách (Ví dụ: `14 15 17 18`).\n"
                "👉 Hoặc gõ `0` nếu muốn chạy toàn bộ không nghỉ ca nào!",
                parse_mode="Markdown",
                reply_markup=ForceReply()
            )
            bot.register_next_step_handler(msg, step_set_canghi_text)
    except Exception as e:
        bot.reply_to(message, f"⚠️ Lỗi định dạng: {str(e)}", parse_mode="Markdown")

def step_set_canghi_text(message):
    txt = message.text.strip().lower()
    if txt in ('0', 'xoa', 'không', 'khong', 'ko', 'none', 'all'):
        bot_settings['CA_NGHI'] = []
        save_bot_settings()
        bot.reply_to(message, "✅ Đã cài đặt: **Chạy tất cả các ca (Không nghỉ ca nào)!**", parse_mode="Markdown")
        send_menu(message.chat.id)
        return
        
    tokens = txt.replace(',', ' ').split()
    matched_off = match_off_tokens_to_shifts(tokens, bot_settings['CA_HOAT_DONG'])
    bot_settings['CA_NGHI'] = matched_off
    save_bot_settings()
    
    active_ca = [c for c in bot_settings['CA_HOAT_DONG'] if c not in set(matched_off)]
    if matched_off:
        bot.reply_to(
            message, 
            f"✅ Đã loại bỏ các ca nghỉ: `{', '.join(matched_off)}`\n"
            f"▶️ Các ca sẽ chạy ({len(active_ca)} ca): `{', '.join(active_ca)}`",
            parse_mode="Markdown"
        )
    else:
        bot.reply_to(message, "⚠️ Không tìm thấy giờ nào trùng với lịch hiện tại. Giữ nguyên toàn bộ ca chạy.")
    send_menu(message.chat.id)

def step_ca_all_in_one(message):
    parse_and_set_schedule(message.text, message)

@bot.message_handler(commands=['ca'])
def cmd_ca_fast(message):
    if message.from_user.id != ADMIN_ID: return
    content = message.text.replace('/ca', '').strip()
    if not content:
        bot.reply_to(message, "👉 VD: `/ca 12:00 22:00 60` (Sau đó bot sẽ hỏi tiếp các giờ bạn muốn nghỉ)", parse_mode="Markdown")
        return
    parse_and_set_schedule(content, message)

@bot.message_handler(commands=['canghi'])
def cmd_canghi_fast(message):
    if message.from_user.id != ADMIN_ID: return
    content = message.text.replace('/canghi', '').strip()
    if not content:
        bot.reply_to(message, "👉 Cú pháp chọn nhanh giờ nghỉ:\nVí dụ: `/canghi 14 15 17 18`\n(Hoặc gõ `/canghi 0` để xóa toàn bộ giờ nghỉ)", parse_mode="Markdown")
        return
    message.text = content
    step_set_canghi_text(message)

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
        # DỰ ĐOÁN BẰNG SNIPER AI V6 (TỰ ĐỘNG BẮT BÀI CẢ KHI BÀN BẺ CẦU)
        predicted_side, confidence, _ = evaluate_table_ai(ket_qua_hien_tai)
        
        # QUẢN LÝ VỐN KỶ LUẬT THÉP: Không đánh 10% mù quáng ở tay đầu, chỉ bứt tốc khi đang thông cầu!
        cau_dep = kiem_tra_cau_dep_thuc_te(ket_qua_hien_tai, ban, win_streak, lose_streak, tong_lai)
                
        ty_le_hien_tai = (ty_le_goc * 2) if cau_dep else ty_le_goc
        
        # Kìm hãm nếu gần chạm mục tiêu lãi (Ví dụ đang +10%, mục tiêu +15% thì chỉ đánh 5%)
        khoang_cach_lai = muc_tieu_lai - tong_lai
        if khoang_cach_lai > 0 and ty_le_hien_tai > khoang_cach_lai:
            ty_le_hien_tai = khoang_cach_lai
            
        # Bảo vệ đáy chốt lỗ: Nếu đang gần mức lỗ tối đa (VD đang -10%, mục tiêu lỗ -15%), chỉ được đánh tối đa 5%
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
                    
            # CƠ CHẾ ĐỔI BÀN KHI BÀN LOẠN CẦU: Gãy 2 tay liên tiếp ở bàn hiện tại -> Đổi sang bàn mới ngay!
            if lose_streak >= 2 and tong_lai > muc_tieu_lo:
                ban_cu = ban
                excluded_tables.add(str(ban_cu))
                ban = chon_ban_thong_minh(excluded_tables)
                bot_state["selected_table"] = ban
                win_streak = 0
                lose_streak = 0
                for group_id in list(allowed_groups):
                    safe_send(group_id, bot.send_message, f"⚠️ **Bàn {ban_cu} đang loạn cầu!** Hệ thống lập tức chuyển sang bàn **{ban}** (Cầu chuẩn hơn)!", parse_mode="Markdown")
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

# ================= 7. LUỒNG ĐẾM GIỜ LÊN CA (CÓ LỌC CA NGHỈ) =================
def get_current_time_str():
    now = datetime.now(timezone.utc) + timedelta(hours=7)
    return now.strftime("%H:%M")

def run_scheduler():
    last_run_time = ""
    while True:
        current_time = get_current_time_str()
        if current_time != last_run_time:
            ca_hoat_dong = bot_settings.get('CA_HOAT_DONG', [])
            ca_nghi = set(bot_settings.get('CA_NGHI', []))
            # Chỉ chạy nếu giờ hiện tại nằm trong lịch VÀ không nằm trong danh sách Ca Nghỉ
            if current_time in ca_hoat_dong and current_time not in ca_nghi:
                last_run_time = current_time 
                if not bot_state["is_running"]:
                    threading.Thread(target=chay_ca_danh, args=(current_time,)).start()
        time.sleep(1) 

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    threading.Thread(target=self_ping, daemon=True).start()
    threading.Thread(target=ai_continuous_learning, daemon=True).start()
    threading.Thread(target=run_scheduler, daemon=True).start()
    print("✅ Hệ thống BOT Đã Sẵn Sàng (Sniper AI v6 + Chức năng Ca Nghỉ)!")
    bot.infinity_permissions_polling() if hasattr(bot, 'infinity_permissions_polling') else bot.infinity_polling()
