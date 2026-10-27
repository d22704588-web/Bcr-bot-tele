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
    return "Bot Baccarat Auto Signal is Running 24/7!"

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

# MEDIA GIAO DIỆN (UP FILE VÀO CÙNG THƯ MỤC TRÊN GITHUB)
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
    cursor.execute('''CREATE TABLE IF NOT EXISTS allowed_groups (chat_id INTEGER PRIMARY KEY)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS daily_reports (date TEXT, shift TEXT, result TEXT, PRIMARY KEY(date, shift))''')
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

# ================= 4. THUẬT TOÁN =================
def fetch_api(table_id=""):
    url = f"https://api-bcrsexy.onrender.com/api/baccarat/{table_id}" if table_id else "https://api-bcrsexy.onrender.com/api/baccarat"
    try:
        res = requests.get(url, timeout=30)
        if res.status_code == 200: return res.json()
    except: pass
    return None

def du_doan_thuat_toan(results):
    if not results or len(results) < 3: return 'B'
    last_3 = results[-3:]
    if last_3[0] == last_3[1] == last_3[2]: return last_3[-1] 
    else: return 'P' if last_3[-1] == 'B' else 'B' 

def ai_continuous_learning():
    global ai_memory
    while True:
        time.sleep(5) 
        data = fetch_api()
        if not data: continue
        
        for tid, info in data.items():
            results = info.get("results", "")
            if len(results) < 5: continue
            
            if tid not in ai_memory:
                ai_memory[tid] = {"last_len": len(results), "predicted": None, "wins": 0, "losses": 0}
                for i in range(3, len(results) - 1):
                    lich_su_cat_lat = results[:i]
                    kq_thuc_te_tay_sau = results[i]
                    du_doan_nhap = du_doan_thuat_toan(lich_su_cat_lat)
                    if du_doan_nhap == kq_thuc_te_tay_sau:
                        ai_memory[tid]["wins"] += 1
                    elif kq_thuc_te_tay_sau != 'T':
                        ai_memory[tid]["losses"] += 1
                ai_memory[tid]["predicted"] = du_doan_thuat_toan(results)
            else:
                mem = ai_memory[tid]
                if len(results) > mem["last_len"]:
                    actual = results[-1]
                    if mem["predicted"]:
                        if actual == mem["predicted"]: mem["wins"] += 1
                        elif actual != 'T': mem["losses"] += 1
                    mem["last_len"] = len(results)
                    mem["predicted"] = du_doan_thuat_toan(results)
                    
        active_tids = data.keys()
        keys_to_del = [k for k in ai_memory if k not in active_tids]
        for k in keys_to_del: del ai_memory[k]

def chon_ban_thong_minh():
    best_table = None
    max_win_rate = -1
    for tid, mem in ai_memory.items():
        total_played = mem["wins"] + mem["losses"]
        if total_played >= 3: 
            win_rate = (mem["wins"] / total_played) * 100
            if win_rate > max_win_rate:
                max_win_rate = win_rate
                best_table = tid
    if not best_table: 
        data = fetch_api()
        if data:
            for tid, info in data.items():
                if len(info.get("results", "")) > 3:
                    best_table = tid; break
            if not best_table: best_table = list(data.keys())[0]
    return best_table

# ================= 5. MENU & QUẢN LÝ NHÓM TỐI GIẢN =================
# ĐÃ BỔ SUNG LỆNH /dungbot VÀO DANH SÁCH MENU GÕ
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
        "👑 **TRUNG TÂM ĐIỀU KHIỂN AUTO SIGNAL** 👑\n\n"
        f"⚡️ Trạng thái Bot: **{trang_thai}**\n"
        f"🕒 Giờ Server: `{server_time}`\n"
        f"📊 **MỤC TIÊU GIAO DỊCH:**\n"
        f"┣ 🎯 **Chốt Lãi:** `+{bot_settings['MUC_TIEU_LAI']}%`\n"
        f"┣ 🛑 **Chốt Lỗ:** `{bot_settings['MUC_TIEU_LO']}%`\n"
        f"┗ 💰 **Vào Lệnh Bthg:** `{bot_settings['TY_LE_VAO']}%` (Tự động x2 nếu cầu đẹp)\n\n"
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
        
    elif call.data == "btn_ca":
        msg = bot.send_message(chat_id, "👉 **CÀI ĐẶT CA NHANH 1 DÒNG**\nVD: `12:30 22:30 60`\n(Hoặc gõ trực tiếp lệnh `/ca 12:30 22:30 60`)", parse_mode="Markdown", reply_markup=ForceReply())
        bot.register_next_step_handler(msg, step_ca_all_in_one)
        
    elif call.data == "btn_test":
        if not allowed_groups: bot.send_message(chat_id, "⚠️ Chưa có nhóm nào được cấp quyền. Mời bot vào nhóm và gõ `/setgroup` trước.")
        elif bot_state["is_running"]: bot.send_message(chat_id, "⚠️ Bot đang bận chạy ca! Bấm [RESET LỖI KẸT] nếu bot bị đứng.")
        else: 
            bot.send_message(chat_id, "🚀 Đang lên ca Test...")
            threading.Thread(target=chay_ca_danh, args=("TEST",)).start()
            
    elif call.data == "btn_stop":
        bot_state["force_stop"] = True
        bot.send_message(chat_id, "🛑 **ĐÃ PHÁT LỆNH DỪNG!** Đang tiến hành chốt ca...", parse_mode="Markdown")
        
    elif call.data == "btn_reset":
        bot_state["is_running"] = False
        bot_state["force_stop"] = False
        bot.send_message(chat_id, "✅ Đã Reset trạng thái thành công. Ca tiếp theo sẽ chạy tự động bình thường!")
        send_menu(chat_id)
        
    elif call.data == "btn_groups":
        show_groups_manager(call)
        
    elif call.data.startswith("delgrp_"):
        gid = int(call.data.split("_")[1])
        if gid in allowed_groups:
            allowed_groups.remove(gid)
            remove_group_db(gid)
            bot.answer_callback_query(call.id, "✅ Đã thu hồi quyền báo lệnh của Bot khỏi nhóm này!")
            show_groups_manager(call) 
            
    elif call.data == "btn_back_menu":
        bot.delete_message(chat_id, call.message.message_id)
        send_menu(chat_id)

def show_groups_manager(call):
    markup = InlineKeyboardMarkup()
    if not allowed_groups:
        text = "⚠️ Hiện chưa có nhóm nào được cấp quyền.\n👉 Hãy thêm bot vào nhóm chat và gõ lệnh `/setgroup`."
    else:
        text = "📋 **DANH SÁCH NHÓM ĐANG ĐƯỢC BÁO LỆNH:**\n\n👉 *Bấm vào nút ❌ để thu hồi quyền báo lệnh của Bot tại nhóm đó.*"
        for gid in list(allowed_groups):
            try:
                chat = bot.get_chat(gid)
                gname = chat.title if chat.title else str(gid)
            except:
                gname = f"Nhóm ẩn (ID: {gid})"
            
            markup.row(InlineKeyboardButton(f"👥 {gname[:25]}", callback_data="ignore"), InlineKeyboardButton("❌ Xóa", callback_data=f"delgrp_{gid}"))
            
    markup.row(InlineKeyboardButton("⬅️ QUAY LẠI MENU CHÍNH", callback_data="btn_back_menu"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

def step_set_val(message, key):
    try:
        val = int(message.text)
        if key == 'MUC_TIEU_LO' and val > 0: val = -val
        bot_settings[key] = val
        save_bot_settings()
        bot.reply_to(message, "✅ Đã lưu cài đặt!")
        send_menu(message.chat.id)
    except: bot.reply_to(message, "⚠️ Lỗi: Chỉ chấp nhận số.")

def parse_and_set_schedule(text, message):
    parts = text.replace('  ', ' ').strip().split()
    if len(parts) != 3:
        bot.reply_to(message, "⚠️ Lỗi: Nhập sai cú pháp.\nVD chuẩn: `12:30 22:30 60`", parse_mode="Markdown")
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
        bot.reply_to(message, f"✅ Đã tự động chia đều {len(new_ca)} ca.")
        send_menu(message.chat.id)
    except Exception as e:
        bot.reply_to(message, f"⚠️ Sai định dạng thời gian.\nVD chuẩn: `12:30 22:30 60`\nLỗi: {str(e)}", parse_mode="Markdown")

def step_ca_all_in_one(message):
    parse_and_set_schedule(message.text, message)

@bot.message_handler(commands=['ca'])
def cmd_ca_fast(message):
    if message.from_user.id != ADMIN_ID: return
    content = message.text.replace('/ca', '').strip()
    if not content:
        bot.reply_to(message, "👉 Cú pháp chia ca nhanh:\n`/ca [Giờ_bắt_đầu] [Giờ_kết_thúc] [Khoảng_cách_phút]`\nVí dụ: `/ca 12:30 22:30 60`", parse_mode="Markdown")
        return
    parse_and_set_schedule(content, message)

@bot.message_handler(commands=['setgroup'])
def allow_group(message):
    if message.from_user.id != ADMIN_ID: return
    allowed_groups.add(message.chat.id)
    add_group_db(message.chat.id)
    bot.reply_to(message, "✅ Đã xác nhận cấp quyền. Bot sẽ tự động báo lệnh vào nhóm này khi tới ca.")

@bot.message_handler(commands=['dungbot'])
def cmd_dungbot(message):
    if message.from_user.id != ADMIN_ID: return
    bot_state["force_stop"] = True
    bot.send_message(message.chat.id, "🛑 **ĐÃ PHÁT LỆNH DỪNG!** Đang chốt ca...", parse_mode="Markdown")

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
    if not allowed_groups: return 
    if bot_state["is_running"]: return
        
    bot_state["is_running"] = True
    bot_state["force_stop"] = False

    tong_lai = 0
    muc_tieu_lai = bot_settings['MUC_TIEU_LAI']
    muc_tieu_lo = bot_settings['MUC_TIEU_LO']
    ty_le_goc = bot_settings['TY_LE_VAO']

    for group_id in list(allowed_groups):
        gui_anh_hoac_video(group_id, GIF_1_VAO_SANH, "🔥 **MN ƠI CHUẨN BỊ VÀO SẢNH SEXY ĐỢI LỆNH!**")
    if not smart_sleep(4): return goto_chot_ca(tong_lai, ca_time, muc_tieu_lai, muc_tieu_lo)

    ban = chon_ban_thong_minh()
    bot_state["selected_table"] = ban
    
    for group_id in list(allowed_groups):
        safe_send(group_id, bot.send_message, f"🎰 **BÁO BÀN MỚI:** Chọn bàn chuẩn **{ban}**", parse_mode="Markdown")
        gui_anh_hoac_video(group_id, GIF_2_CHO_LENH, f"⏳ **SẴN SÀNG TAY SAU VÀO LỆNH (Bàn {ban})**")

    data_ban_moi = fetch_api(ban)
            so_van_cu = len(data_ban_moi.get('results', [])) if data_ban_moi else 0
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
            str_tong_lai = f"+{tong_lai}" if tong_lai >= 0 else f"{tong_lai}"
            msg_ketqua = f"💰 **H{str_tong_lai}%**"
            for group_id in list(allowed_groups):
                safe_send(group_id, bot.send_message, msg_ketqua, parse_mode="Markdown")
                try:
                    with open(VID_WIN_HAND, 'rb') as vid:
                        safe_send(group_id, bot.send_animation, vid)
                except Exception:
                    pass
                    
        else:
            tong_lai -= ty_le_hien_tai
            str_tong_lai = f"+{tong_lai}" if tong_lai >= 0 else f"{tong_lai}"
            msg_ketqua = f"❌ **G{str_tong_lai}%**"
            for group_id in list(allowed_groups):
                safe_send(group_id, bot.send_message, msg_ketqua, parse_mode="Markdown")
                try:
                    with open(VID_LOSE_HAND, 'rb') as vid:
                        safe_send(group_id, bot.send_animation, vid)
                except Exception:
                    pass
                    
        smart_sleep(2)

    goto_chot_ca(tong_lai, ca_time, muc_tieu_lai, muc_tieu_lo)

def goto_chot_ca(tong_lai, ca_time, muc_tieu_lai, muc_tieu_lo):
    if bot_state["force_stop"]:
        for group_id in list(allowed_groups):
            safe_send(group_id, bot.send_message, "⚠️ **CA ĐÁNH BỊ DỪNG ĐỘT XUẤT!** Đang tiến hành chốt ca...", parse_mode="Markdown")
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
    print("✅ Hệ thống BOT Đã Sẵn Sàng!")
    bot.infinity_polling()
