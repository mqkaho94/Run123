import telebot
from telebot import util  
import random
import time
import threading
import psycopg2  # 💡 這裡由 sqlite3 改為 psycopg2
from psycopg2.extras import DictCursor # 💡 讓查詢結果能像原本的 sqlite 一樣用欄位名稱讀取
import os
import json
from datetime import date

TOKEN = os.getenv("8999179825:AAGMP7VHxI75FniZG8KKv6XsJsuMfcSwudM")
BOT_USERNAME = "@gapjaibot"

# 💡 從環境變數讀取 Supabase URI（安全性高），本機測試可直接把字串貼在後面當備份
SUPABASE_URI = os.getenv("postgresql://hidden:Kaho@03241003@hidden:5432//postgres:Kaho@03241003@db.shbztgepcqgchtioixpz.supabase.co:5432/postgres")

bot = telebot.TeleBot(TOKEN, threaded=True, num_threads=4)
daily_lock = threading.Lock()

# ================== 💡 SUPABASE 資料庫管理 ==================
def get_db_connection():
    """連線到雲端 Supabase PostgreSQL 資料庫"""
    # 使用 DictCursor 完美相容原本的 sqlite3 Row 功能
    conn = psycopg2.connect(SUPABASE_URI, cursor_factory=DictCursor)
    return conn

def get_chips(user_id):
    with get_db_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT chips FROM users WHERE user_id=%s", (user_id,)) # 💡 Postgres 語法標記改為 %s
            row = c.fetchone()
            if not row:
                c.execute("INSERT INTO users (user_id, chips) VALUES (%s, 1000)", (user_id,))
                conn.commit()
                return 1000
            return row['chips'] # 💡 原本是 row[0]，改為欄位名稱取值更安全

def update_chips(user_id, amount):
    with get_db_connection() as conn:
        with conn.cursor() as c:
            c.execute("UPDATE users SET chips = chips + %s WHERE user_id=%s", (amount, user_id))
            conn.commit()

def get_user_horse(user_id):
    with get_db_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT has_horse, horse_name, horse_first, horse_second, horse_third, horse_losses FROM users WHERE user_id=%s", (user_id,))
            row = c.fetchone()
            if row: 
                return {"has_horse": row['has_horse'], "horse_name": row['horse_name'], "first": row['horse_first'], "second": row['horse_second'], "third": row['horse_third'], "losses": row['horse_losses']}
            return {"has_horse": 0, "horse_name": None, "first": 0, "second": 0, "third": 0, "losses": 0}

def get_owner_by_horse_name(horse_name):
    clean_name = horse_name.split(".", 1)[1] if "." in horse_name else horse_name
    with get_db_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT user_id FROM users WHERE horse_name=%s", (clean_name,))
            row = c.fetchone()
            return row['user_id'] if row else None

def get_all_registered_horses():
    with get_db_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT user_id, horse_name FROM users WHERE has_horse=1 AND horse_name IS NOT NULL")
            return c.fetchall()

def get_all_users_for_luck():
    with get_db_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT user_id, username, has_horse, horse_name, last_luck_date FROM users")
            return c.fetchall()

def update_luck_date(user_id, today_str):
    with get_db_connection() as conn:
        with conn.cursor() as c:
            c.execute("UPDATE users SET last_luck_date=%s WHERE user_id=%s", (today_str, user_id))
            conn.commit()

def sync_username(user_id, username):
    if not username: return
    with get_db_connection() as conn:
        with conn.cursor() as c:
            c.execute("UPDATE users SET username=%s WHERE user_id=%s", (username.lower(), user_id))
            conn.commit()

def record_detailed_result(user_id, rank_type):
    with get_db_connection() as conn:
        with conn.cursor() as c:
            if rank_type == 1: c.execute("UPDATE users SET horse_first = horse_first + 1 WHERE user_id=%s", (user_id,))
            elif rank_type == 2: c.execute("UPDATE users SET horse_second = horse_second + 1 WHERE user_id=%s", (user_id,))
            elif rank_type == 3: c.execute("UPDATE users SET horse_third = horse_third + 1 WHERE user_id=%s", (user_id,))
            else: c.execute("UPDATE users SET horse_losses = horse_losses + 1 WHERE user_id=%s", (user_id,))
            conn.commit()

# ================== 💡 保底機制管理 (Postgres 版) ==================
def get_system_race_count():
    with get_db_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT value FROM system_config WHERE key='total_races'")
            row = c.fetchone()
            if row: return int(row['value'])
            c.execute("INSERT INTO system_config (key, value) VALUES ('total_races', '0')")
            conn.commit()
            return 0

def increment_system_race_count():
    current = get_system_race_count()
    new_count = current + 1
    with get_db_connection() as conn:
        with conn.cursor() as c:
            c.execute("UPDATE system_config SET value=%s WHERE key='total_races'", (str(new_count),))
            conn.commit()
    return new_count

def get_guarantee_plan():
    with get_db_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT value FROM system_config WHERE key='guarantee_plan'")
            row = c.fetchone()
            if row: return json.loads(row['value'])
            
            g_races = random.sample(range(1, 11), 2)
            plan = {str(g_races[0]): random.choice([1, 2]), str(g_races[1]): random.choice([1, 2])}
            c.execute("INSERT INTO system_config (key, value) VALUES ('guarantee_plan', %s)", (json.dumps(plan),))
            conn.commit()
            return plan

def refresh_guarantee_plan():
    g_races = random.sample(range(1, 11), 2)
    plan = {str(g_races[0]): random.choice([1, 2]), str(g_races[1]): random.choice([1, 2])}
    with get_db_connection() as conn:
        with conn.cursor() as c:
            c.execute("UPDATE system_config SET value=%s WHERE key='guarantee_plan'", (json.dumps(plan),))
            conn.commit()
    return plan

def daily(message):
    user_id = message.from_user.id
    today = date.today().isoformat()  
    with get_db_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT last_daily FROM users WHERE user_id=%s", (user_id,))
            row = c.fetchone()
            if row and row['last_daily'] == today:
                bot.reply_to(message, "⚠️ 你今天已經領過每日獎勵！明天再來吧。")
                return
            c.execute("UPDATE users SET last_daily=%s WHERE user_id=%s", (today, user_id))
            conn.commit()
    update_chips(user_id, 3000)
    bot.reply_to(message, "🎁 **每日簽到成功！** +3000 金幣")

# ... 程式碼其餘部分的賽馬直播邏輯保持不變 ...
# 1. 設定你的 Bot 憑證 (強烈建議改用環境變數 os.getenv 讀取)
TOKEN = os.getenv("8999179825:AAGMP7VHxI75FniZG8KKv6XsJsuMfcSwudM")
BOT_USERNAME = "@gapjaibot"

# 啟用多線程 ThreadPool
bot = telebot.TeleBot(TOKEN, threaded=True, num_threads=4)

# 定義每日簽到安全鎖 (防並發連擊)
daily_lock = threading.Lock()

# 2. 基礎 NPC 固定鼠隻名單與其專屬圖標
BASE_NPC_HORSES = [
    ("奧雲狗狗", "🐹"), ("黑旋風", "🐭"), ("戰槌巨人", "🐀"), ("火麒麟", "🐁"), 
    ("疾風", "🐹"), ("黃金戰鼠", "🐭"), ("海嘯", "🐀"), ("傲空", "🐁")
]

# 名次對應的數字 Emoji 對照表
RANK_EMOJIS = {
    1: "🥇", 2: "🥈", 3: "🥉", 4: "4️⃣",
    5: "5️⃣", 6: "6️⃣", 7: "7️⃣", 8: "8️⃣"
}

# 可供隨機抽取的動物 Emoji 清單
RANDOM_ANIMAL_EMOJIS = ["🐹", "🐭", "🐁", "🐀", "🐿️", "🐾", "🦔", "🐇"]

# 清單 A：下注排位表顯示的外觀狀態
BETTING_SURFACE_STATUSES = [
    "鼠神加持✨高光時刻", "外星物種👽高深莫測", "科技外掛🤖液態金屬", "剛吃興奮劑🔥眼神清澈", 
    "昨晚拜神🙏獲得神秘力量", "祖先托夢💤這局穩贏", "賽道之神🏎️自帶BGM", "氣勢如虹☄️單眼單挑", 
    "氪金玩家💰全身發光", "不可一世👑王者風範",
    "天生扁平足🦶跑動困難", "沉迷股票📉痛失家產心慌慌", "剛剛小兒麻痺症發作🏥", "霉運當頭⛈️烏雲蓋頂", 
    "體重超標🍔走路都喘氣", "出局邊緣📉毫無鬥志", "四肢無力🥀缺乏維他命", "中暑邊緣🥵頭暈身熱", 
    "靈魂出竅👻呆若木雞", "忘記帶大腦🧠全憑本能"
]

# 清單 B：開局5秒狀態通報
RACE_START_STATUSES = [
    "朋友最多轉圈哈姆共你🐹", "趕住返屋企瀨屎💩", "昨晚拜過黃大仙🙏獲得神祕力量加持",   
    "尋晚飲咗過期維他奶🤢個肚好滾", "出門口踩到舊大狗屎💩霉運當頭", "尋晚拉咗十二次斯🚽對腳發軟",
    "倒瀉咗杯凍檸茶走甜熱辣辣☕", "以為自己係比卡超⚡自帶十萬伏特", "突然叮噹大長篇上身🦸‍♂️要拯救地球",
    "阿嬤覺得佢餓👵嫌餵到變咗個波", "智商突然下線📉全憑生物本能前進", "食咗誠實豆沙包🍞個人好清醒",
    "氪金玩家💰全身閃爍住人民幣嘅光芒", "眼神充滿殺氣👀覺得自己係黎明", "自帶背景音樂BGM🎵氣勢如虹",
    "跛咗隻腳🦵嫌推輪椅代步跑", "成晚通宵打機🎮條黑眼圈去到下巴", "飲咗兩啖假酒🍷左右不分亂打打",
    "失戀萬念毀滅💔打算跑完去跳海", "高山反應🏔️呼吸困難行得好辛苦"
]

# 資料庫持久化路徑設定
# ==========================================
# 資料庫持久化路徑設定 (防止 Railway 更新後資料遺失)
# ==========================================
# 自動判斷：如果 Railway 上有掛載 /data 硬碟空間，就存進去；否則存在當前目錄（本機測試用）
if os.path.exists('/data'):
    DB_FILE = '/data/race.db'
else:
    DB_FILE = 'race.db'
HORSE_PRICE = 3000  

# ================== 資料庫管理 ==================
def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            chips INTEGER DEFAULT 1000,
            last_daily TEXT,
            has_horse INTEGER DEFAULT 0,
            horse_name TEXT DEFAULT NULL,
            horse_first INTEGER DEFAULT 0,
            horse_second INTEGER DEFAULT 0,
            horse_third INTEGER DEFAULT 0,
            horse_losses INTEGER DEFAULT 0,
            last_luck_date TEXT DEFAULT NULL
        );
        ''')
        
        c.execute('''
        CREATE TABLE IF NOT EXISTS system_config (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        ''')
        conn.commit()

def get_chips(user_id):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT chips FROM users WHERE user_id=?", (user_id,))
        row = c.fetchone()
        if not row:
            c.execute("INSERT INTO users (user_id, chips) VALUES (?, 1000)", (user_id,))
            conn.commit()
            return 1000
        return row[0]

def update_chips(user_id, amount):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET chips = chips + ? WHERE user_id=?", (amount, user_id))
        conn.commit()

def get_user_horse(user_id):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT has_horse, horse_name, horse_first, horse_second, horse_third, horse_losses FROM users WHERE user_id=?", (user_id,))
        row = c.fetchone()
        if row: 
            return {"has_horse": row[0], "horse_name": row[1], "first": row[2], "second": row[3], "third": row[4], "losses": row[5]}
        return {"has_horse": 0, "horse_name": None, "first": 0, "second": 0, "third": 0, "losses": 0}

def get_owner_by_horse_name(horse_name):
    clean_name = horse_name.split(".", 1)[1] if "." in horse_name else horse_name
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT user_id FROM users WHERE horse_name=?", (clean_name,))
        row = c.fetchone()
        return row[0] if row else None

def get_all_registered_horses():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT user_id, horse_name FROM users WHERE has_horse=1 AND horse_name IS NOT NULL")
        return c.fetchall()

def get_all_users_for_luck():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT user_id, username, has_horse, horse_name, last_luck_date FROM users")
        return c.fetchall()

def update_luck_date(user_id, today_str):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET last_luck_date=? WHERE user_id=?", (today_str, user_id))
        conn.commit()

def sync_username(user_id, username):
    if not username: return
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET username=? WHERE user_id=?", (username.lower(), user_id))
        conn.commit()

def record_detailed_result(user_id, rank_type):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        if rank_type == 1: c.execute("UPDATE users SET horse_first = horse_first + 1 WHERE user_id=?", (user_id,))
        elif rank_type == 2: c.execute("UPDATE users SET horse_second = horse_second + 1 WHERE user_id=?", (user_id,))
        elif rank_type == 3: c.execute("UPDATE users SET horse_third = horse_third + 1 WHERE user_id=?", (user_id,))
        else: c.execute("UPDATE users SET horse_losses = horse_losses + 1 WHERE user_id=?", (user_id,))
        conn.commit()

# ================== 保底機制核心管理 ==================
def get_system_race_count():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT value FROM system_config WHERE key='total_races'")
        row = c.fetchone()
        if row: return int(row[0])
        c.execute("INSERT INTO system_config (key, value) VALUES ('total_races', '0')")
        conn.commit()
        return 0

def increment_system_race_count():
    current = get_system_race_count()
    new_count = current + 1
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("UPDATE system_config SET value=? WHERE key='total_races'", (str(new_count),))
        conn.commit()
    return new_count

def get_guarantee_plan():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT value FROM system_config WHERE key='guarantee_plan'")
        row = c.fetchone()
        if row: return json.loads(row[0])
        
        g_races = random.sample(range(1, 11), 2)
        plan = {str(g_races[0]): random.choice([1, 2]), str(g_races[1]): random.choice([1, 2])}
        c.execute("INSERT INTO system_config (key, value) VALUES ('guarantee_plan', ?)", (json.dumps(plan),))
        conn.commit()
        return plan

def refresh_guarantee_plan():
    g_races = random.sample(range(1, 11), 2)
    plan = {str(g_races[0]): random.choice([1, 2]), str(g_races[1]): random.choice([1, 2])}
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("UPDATE system_config SET value=? WHERE key='guarantee_plan'", (json.dumps(plan),))
        conn.commit()
    return plan

init_db()

# ================== 賽事與氣運全域變數 ==================
current_race = None    
race_id = None
race_bets = {}   
race_odds = {}  
current_horses = []   
horse_statuses = {}  
scheduled_disasters = {}  
active_horse_luck = {}
user_bet_count = {}     
user_refund_count = {}  
user_actual_deduct = {} 

# ================== 轉帳系統 ==================
@bot.message_handler(commands=['pay'])
def pay_chips(message):
    try:
        from_user_id = message.from_user.id
        sync_username(from_user_id, message.from_user.username)
        
        to_user_id = None
        to_username = "神祕玩家"
        
        text_clean = message.text.replace(f"{BOT_USERNAME}", "").strip()
        cmd = text_clean.split()
        
        if len(cmd) < 2:
            bot.reply_to(message, "⚠️ **格式錯誤**\n👉 回覆他人訊息轉帳：`/pay 金額`\n👉 直接標記名字轉帳：`/pay @玩家標記 金額`", parse_mode='Markdown')
            return

        if len(cmd) >= 3 and cmd[1].startswith('@'):
            target_username = cmd[1].replace('@', '').strip().lower()
            raw_amount = cmd[2].strip()
            with sqlite3.connect(DB_FILE) as conn:
                c = conn.cursor()
                c.execute("SELECT user_id, username FROM users WHERE username=?", (target_username,))
                row = c.fetchone()
                if row:
                    to_user_id = row[0]
                    to_username = row[1] if row[1] else target_username
                else:
                    bot.reply_to(message, f"❌ **轉帳失敗**：找不到玩家 `@{target_username}`。", parse_mode='Markdown')
                    return
        elif message.reply_to_message and message.reply_to_message.from_user:
            to_user_id = message.reply_to_message.from_user.id
            to_username = message.reply_to_message.from_user.first_name
            sync_username(to_user_id, message.reply_to_message.from_user.username)
            raw_amount = cmd[1].strip()
        else:
            bot.reply_to(message, "❌ **轉帳失敗！請正確回覆或標記用戶。**", parse_mode='Markdown')
            return

        try:
            pay_amount = int(raw_amount)
            if pay_amount <= 0 or from_user_id == to_user_id: return
        except ValueError: return

        from_user_chips = get_chips(from_user_id) 
        if from_user_chips < pay_amount: 
            bot.reply_to(message, "❌ 餘額不足以轉帳！")
            return

        update_chips(from_user_id, -pay_amount) 
        update_chips(to_user_id, pay_amount)   

        from_username = message.from_user.first_name if message.from_user.first_name else "神祕玩家"
        success_text = f"✅ **【金幣轉讓成功】** ✅\n📤 轉出人：{from_username}\n📥 接收人：{to_username}\n💰 轉讓金額：<b>{pay_amount:,}</b> 金幣"
        bot.send_message(message.chat.id, success_text, parse_mode='HTML')
    except Exception as e: print(e)

# ================== 開局排位 + 氣運系統 ==================
@bot.message_handler(commands=['startrun'])
def startrun(message):
    global current_race, race_id, race_odds, user_bet_count, user_refund_count, user_actual_deduct, current_horses, horse_statuses, scheduled_disasters, active_horse_luck
    if current_race:
        bot.reply_to(message, "⚠️ 已有賽事進行中！")
        return

    current_race = "betting"  
    total_races = increment_system_race_count()
    cycle_index = total_races % 10 or 10
    
    if cycle_index == 1: refresh_guarantee_plan()
    
    race_id = f"R{int(time.time())}"
    race_bets[race_id] = {}
    race_odds, horse_statuses, scheduled_disasters, active_horse_luck = {}, {}, {}, {}
    user_bet_count, user_refund_count, user_actual_deduct = {}, {}, {}
    
    plan = get_guarantee_plan()
    is_guarantee_round = str(cycle_index) in plan
    guarantee_count = plan.get(str(cycle_index), 0) if is_guarantee_round else 0

    sync_username(message.from_user.id, message.from_user.username)
    all_registered = get_all_registered_horses()
    final_8_horses = []  
    
    if len(all_registered) == 0:
        final_8_horses = [(None, npc_name, npc_icon) for npc_name, npc_icon in BASE_NPC_HORSES]
    else:
        random.shuffle(all_registered)
        final_8_horses = [(uid, h_name, "⭐") for uid, h_name in all_registered[:8]]
        if len(final_8_horses) < 8:
            available_npcs = random.sample(BASE_NPC_HORSES, 8 - len(final_8_horses))
            final_8_horses.extend([(None, n, i) for n, i in available_npcs])

    random.shuffle(final_8_horses)
    current_horses = [f"{icon}{idx+1}.{h_name}" for idx, (uid, h_name, icon) in enumerate(final_8_horses)]

    luck_announcements = []
    today_str = date.today().isoformat()
    
    for u_id, u_name, has_h, h_name, last_luck_date in get_all_users_for_luck():
        if last_luck_date == today_str: continue
        roll = random.random()
        
        if roll < 0.010:  
            update_luck_date(u_id, today_str) 
            try: nickname = bot.get_chat_member(message.chat.id, u_id).user.first_name
            except: nickname = f"@{u_name}" if u_name else f"玩家({u_id})"
            matching_horse = next((h for h in current_horses if h_name and h_name in h), None)
            
            if roll < 0.005: # 好運
                if matching_horse and random.random() < 0.50:
                    active_horse_luck[matching_horse] = "good"
                    luck_announcements.append(f"🎉 <b>【氣運爆發】</b> 鼠主 <b>{nickname}</b> 的愛鼠 <b>{matching_horse}</b> 獲得【幸運加速】！")
                else:
                    update_chips(u_id, 3000)
                    luck_announcements.append(f"🎉 <b>【氣運爆發】</b> 玩家 <b>{nickname}</b> 突發好運！獲得 <b>+3,000</b> 金幣！")
            else: # 壞運
                if matching_horse and random.random() < 0.50:
                    active_horse_luck[matching_horse] = "bad"
                    luck_announcements.append(f"🌧️ <b>【霉運當頭】</b> 鼠主 <b>{nickname}</b> 的愛鼠 <b>{matching_horse}</b> 遭遇【意外率提升】！")
                else:
                    update_chips(u_id, -3000)
                    luck_announcements.append(f"🌧️ <b>【霉運當頭】</b> 玩家 <b>{nickname}</b> 亂倒鼠糧被罰款，扣除 <b>3,000</b> 金幣！")

    if random.random() < 0.04:
        for uh in random.sample(current_horses, random.choice([1, 2])):
            scheduled_disasters[uh] = {"trigger_at": random.uniform(0.0, 99.0), "reason": random.choice(["☠️【被貓吃掉】", "🪤【踩到鼠夾】"])}

    for h in current_horses:
        if active_horse_luck.get(h) == "bad" and h not in scheduled_disasters and random.random() < 0.05:
            scheduled_disasters[h] = {"trigger_at": random.uniform(5.0, 85.0), "reason": random.choice(["☠️【被野貓吃掉】", "🪤【踩中特大鼠夾】"])}

    available_statuses = BETTING_SURFACE_STATUSES.copy()
    random.shuffle(available_statuses)
    round_statuses = available_statuses[:8]

    detected_cold_horses = [h for idx, h in enumerate(current_horses) if any(kw in round_statuses[idx] for kw in ["小兒麻痺", "出局邊緣", "沉迷股票", "體重超標"])]
    guaranteed_cold_horses = random.sample(detected_cold_horses, min(guarantee_count, len(detected_cold_horses))) if is_guarantee_round and detected_cold_horses else []

    text = f"🏁 **【賽鼠會 - 第 {total_races} 場】** 🏁\n🏆 本場盃賽：【鼠王爭霸戰】\n📊 週期進度：第 {cycle_index}/10 場\n\n"
    round_animal_emojis = random.sample(RANDOM_ANIMAL_EMOJIS, 8)

    for idx, h in enumerate(current_horses):
        surface_txt = round_statuses[idx] 
        is_hot = any(keyword in surface_txt for keyword in ["鼠神", "外星", "科技", "拜神", "賽道", "氪金", "不可一世"])
        is_cold = h in detected_cold_horses
        has_surface_buff = (not is_cold) and any(keyword in surface_txt for keyword in ["鼠神加持", "外星物種"])

        horse_statuses[h] = {
            "betting_text": surface_txt,      
            "start_text": "",                 
            "target_time": 50.0,  
            "dead_reason": None,
            "freeze_steps": 0,       
            "freeze_reason": "",
            "is_buff_carrier": has_surface_buff,  
            "is_debuff_carrier": (random.random() < 0.05) if is_cold and h not in guaranteed_cold_horses else False,            
            "buff_active": False,
            "debuff_active": False,
            "is_guaranteed": (h in guaranteed_cold_horses) 
        }

        if is_cold: win_odds, class_icon = round(random.uniform(13.0, 20.0), 1), "🟢"
        elif is_hot: win_odds, class_icon = round(random.uniform(2.5, 3.6), 1), "🔴"
        else: win_odds, class_icon = round(random.uniform(4.0, 8.5), 1), "🟡"
        
        place_odds = max(1.1, round(win_odds * 0.4, 1))
        race_odds[h] = win_odds  
        
        luck_tag = " ✨[好運加成]" if active_horse_luck.get(h) == "good" else " ⛈️[歹運纏身]" if active_horse_luck.get(h) == "bad" else ""
        text += f"{idx+1} {h.split('.', 1)[1]}{h[0]}{luck_tag} {round_animal_emojis[idx]} {surface_txt}\n    {class_icon} 獨贏: {win_odds}倍 | 位置: {place_odds}倍\n"

    text += "\n" + "—" * 20 + "\n💡 **【下注方式】** /win 號碼 金額 | /pla 號碼 金額 | /ww 號碼1 號碼2 金額\n"
    
    if luck_announcements:
        bot.send_message(message.chat.id, "🌟 <b>【每局氣運星象通報】</b> 🌟\n" + "￣"*25 + "\n" + "\n\n".join(luck_announcements), parse_mode='HTML')
        time.sleep(1)

    bot.reply_to(message, text, parse_mode='Markdown')
    threading.Timer(60, lambda: run_race(message.chat.id)).start()

# ================== 直播與戰績結算 ==================
def run_race(chat_id):
    global current_race
    if current_race != "betting": return
    current_race = "running" 
    
    status_intro = f"📢 **賽前選手狀態通報** 📢\n" + "￣" * 25 + "\n"
    for h in current_horses:
        start_txt = "😱 突然舊患復發！全身發軟手震震" if horse_statuses[h]["is_debuff_carrier"] else random.choice(RACE_START_STATUSES)
        horse_statuses[h]["start_text"] = start_txt  
        
        luck_desc = " ✨(幸運加速)" if active_horse_luck.get(h) == "good" else " ⛈️(意外率提升)" if active_horse_luck.get(h) == "bad" else ""
        status_intro += f"{h} 💬 **{start_txt}**{luck_desc}\n"

        if horse_statuses[h].get("is_guaranteed", False): base_time_range = (22.0, 26.0) 
        elif horse_statuses[h]["is_debuff_carrier"]: base_time_range = (120.0, 180.0) 
        else:
            score = random.randint(1, 10)
            base_time_range = (28.0, 38.0) if score >= 9 else (42.0, 58.0) if score >= 4 else (62.0, 80.0)
                
        horse_statuses[h]["target_time"] = random.uniform(*base_time_range) * (0.95 if active_horse_luck.get(h) == "good" else 1.0)

    status_intro += "\n⏳ _狀態展示中，比賽將於 5 秒後正式鳴槍！_"
    race_msg = bot.send_message(chat_id, status_intro, parse_mode='Markdown')
    time.sleep(5)  
    
    TOTAL_DISTANCE = 100.0  
    DISPLAY_LENGTH = 15     
    speeds = {h: TOTAL_DISTANCE / horse_statuses[h]["target_time"] for h in current_horses}
    current_distance = {h: 0.0 for h in current_horses}
    finished_horses, dead_horses = [], []
    last_refresh_time = time.time()
    
    while (len(finished_horses) < 3) and (len(finished_horses) + len(dead_horses) < len(current_horses)):
        time.sleep(1.0)  
        now = time.time()
        current_second_reports = {}
        
        for h in current_horses:
            if horse_statuses[h]["dead_reason"]:
                current_second_reports[h] = f"💀 {horse_statuses[h]['dead_reason']}"
                continue

            if current_distance[h] >= TOTAL_DISTANCE:
                current_second_reports[h] = f"🏁 已衝線 (第 {finished_horses.index(h) + 1} 名)"
                continue

            if h in scheduled_disasters and current_distance[h] >= scheduled_disasters[h]["trigger_at"] and not horse_statuses[h].get("is_guaranteed"):
                horse_statuses[h]["dead_reason"] = scheduled_disasters[h]["reason"]
                dead_horses.append(h)
                current_second_reports[h] = f"💀 {horse_statuses[h]['dead_reason']}"
                continue
            
            if horse_statuses[h]["freeze_steps"] > 0:
                current_second_reports[h] = f"⏸️ {horse_statuses[h]['freeze_reason']} (剩 {horse_statuses[h]['freeze_steps']} 秒)"
                horse_statuses[h]["freeze_steps"] -= 1 
                continue 
            
            if random.random() < 0.005 and not horse_statuses[h].get("is_guaranteed"):
                horse_statuses[h]["freeze_steps"] = random.randint(3, 5)
                horse_statuses[h]["freeze_reason"] = random.choice(["發呆停止步行", "地上撿到芝士吃兩口"])
                continue

            if (horse_statuses[h]["is_buff_carrier"] or active_horse_luck.get(h) == "good") and not horse_statuses[h]["buff_active"] and random.random() < 0.055:
                horse_statuses[h]["buff_active"] = True

            if horse_statuses[h]["is_debuff_carrier"]: step_modifier, action_text = 0.1, "📉 腳軟慢跑中..."
            elif horse_statuses[h].get("is_guaranteed") or horse_statuses[h]["buff_active"]:
                step_modifier, action_text = 3.5, "🚀 隱藏潛能突發暴走！"
                horse_statuses[h]["buff_active"] = False 
            else:
                move_roll = random.randint(1, 10)
                step_modifier, action_text = (2.0, "💨 快步推進") if move_roll >= 9 else (1.0, "🚶 穩步向前") if move_roll >= 4 else (0.5, "🐢 慢步推進")
                
            current_distance[h] = min(TOTAL_DISTANCE, current_distance[h] + (speeds[h] * step_modifier) + random.uniform(-0.2, 0.2))
            
            if current_distance[h] >= TOTAL_DISTANCE:
                if h not in finished_horses: finished_horses.append(h)
                current_second_reports[h] = f"🏁 剛剛衝線了！"
            else:
                current_second_reports[h] = action_text
                        
        if now - last_refresh_time >= 3.0 or (len(finished_horses) >= 3) or (len(finished_horses) + len(dead_horses) == len(current_horses)):
            last_refresh_time = now
            dynamic_text = f"🎥 **現場直播** 🎥\n" + "￣" * 25 + "\n"
            for h in current_horses:
                if horse_statuses[h]["dead_reason"]: dynamic_text += f"{h} 💀 {horse_statuses[h]['dead_reason']}\n\n"
                else:
                    progress = min(max(int((current_distance[h] / TOTAL_DISTANCE) * DISPLAY_LENGTH), 0), DISPLAY_LENGTH)
                    track_str = "🐾" + "_" * (DISPLAY_LENGTH - progress) + "🏃" + "_" * progress
                    status = f" 🏆【第{finished_horses.index(h)+1}名】" if h in finished_horses else ""
                    dynamic_text += f"{h}{status}\n`{track_str}`\n\n"
            try: bot.edit_message_text(dynamic_text, chat_id, race_msg.message_id, parse_mode='Markdown')
            except: pass

    alive_remaining = sorted([h for h in current_horses if h not in finished_horses and h not in dead_horses], key=lambda x: current_distance[x], reverse=True)
    all_ranks = finished_horses + alive_remaining + dead_horses
    
    bot.edit_message_text("🏁 **比賽結束！正在計算最終名次與分紅...**", chat_id, race_msg.message_id, parse_mode='Markdown')
    
    result = "🏆 **最終賽果名次結果** 🏆\n\n"
    for i, h in enumerate(all_ranks, 1):
        medal = RANK_EMOJIS.get(i, "🏅")
        if horse_statuses[h]["dead_reason"]: result += f"💀 未完賽：{h} -> {horse_statuses[h]['dead_reason']}\n"
        else: result += f"{medal} 第 {i} 名：{h} (獨贏 {race_odds[h]}x)\n"
    bot.send_message(chat_id, result, parse_mode='Markdown')
    
    # 派彩結算
    if race_id in race_bets and len(finished_horses) > 0:
        payout_message = "💰 **派彩結果** 💰\n\n"
        has_winner = False
        winner, second = all_ranks[0] if len(finished_horses) > 0 else None, all_ranks[1] if len(finished_horses) > 1 else None
        
        for uid, bets in race_bets[race_id].items():
            win_amount = 0
            for b_type, horses, amt in bets:
                if b_type == "win" and winner and horses == winner: win_amount += int(amt * race_odds[winner])
                elif b_type == "pla" and horses in finished_horses[:3]: win_amount += int(amt * (race_odds[horses] * 0.4)) 
                elif b_type == "ww" and winner and second and set(horses) == set([winner, second]): win_amount += int(amt * (race_odds[winner] * race_odds[second]))
            
            if win_amount > 0:
                update_chips(uid, win_amount)
                try: p_name = bot.get_chat_member(chat_id, uid).user.first_name
                except: p_name = f"玩家({uid})"
                payout_message += f"🎉 玩家 <b>{p_name}</b> 贏得 <b>{win_amount:,}</b> 金幣\n"
                has_winner = True
        
        bot.send_message(chat_id, payout_message if has_winner else "💸 壓注全空！本局沒有人中獎", parse_mode='HTML')
    
    # 專利分紅
    owner_text, has_owner_bonus = "💼 <b>【本局鼠主專利分紅】</b> 💼\n", False
    for i, h in enumerate(all_ranks):
        owner_id = get_owner_by_horse_name(h)
        if not owner_id: continue
        
        if horse_statuses[h]["dead_reason"] is None and i < 3:
            record_detailed_result(owner_id, rank_type=(i + 1))
            bonus = random.randint(10000, 20000) if i==0 else random.randint(6000, 7500) if i==1 else random.randint(1000, 2000)
            update_chips(owner_id, bonus)
            owner_text += f"恭喜專屬鼠 <b>{h}</b> 榮獲第{i+1}名！鼠主獲得分紅 <b>+{bonus:,}</b> 金幣\n"
            has_owner_bonus = True
        else:
            record_detailed_result(owner_id, rank_type=4)
            comfort_bonus = random.randint(300, 500)
            update_chips(owner_id, comfort_bonus)
            owner_text += f"安慰獎：專屬鼠 <b>{h}</b> 鼠主獲得 <b>+{comfort_bonus:,}</b> 金幣\n"
            has_owner_bonus = True

    if has_owner_bonus: bot.send_message(chat_id, owner_text, parse_mode='HTML')
    current_race = None

# ================== 投注與退款邏輯 ==================
@bot.message_handler(commands=['win', 'pla', 'ww'])
def place_bet(message):
    if current_race != "betting":
        bot.reply_to(message, "⚠️ 目前非投注時間！")
        return
    user_id = message.from_user.id
    if user_bet_count.get(user_id, 0) >= 1:
        bot.reply_to(message, "⚠️ 您本場已投注過！更改請先輸入 /refund 退款。")
        return

    cmd = message.text.replace(f"{BOT_USERNAME}", "").strip().split()
    bet_type = cmd[0][1:].lower()  
    
    try:
        if bet_type in ["win", "pla"] and len(cmd) >= 3:
            horse_num = int(cmd[1])
            selected_horse_full = current_horses[horse_num-1]
            odds_val = race_odds[selected_horse_full] if bet_type == "win" else round(race_odds[selected_horse_full] * 0.4, 1)
        elif bet_type == "ww" and len(cmd) >= 4:
            h1, h2 = int(cmd[1]), int(cmd[2])
            selected_horse_full = [current_horses[h1-1], current_horses[h2-1]]
            odds_val = round(race_odds[selected_horse_full[0]] * race_odds[selected_horse_full[1]], 1)
            cmd[2] = cmd[3] # Shift amount for parsing
        else: raise ValueError

        bet_amount = int(cmd[2])
        if bet_amount <= 0: raise ValueError
        
        chips = get_chips(user_id)
        if bet_amount > chips:
            bot.reply_to(message, f"❌ 金幣餘額不足！你目前只有 `{chips:,}` 金幣。", parse_mode='Markdown')
            return

        update_chips(user_id, -bet_amount)
        user_actual_deduct[user_id] = bet_amount 
        user_bet_count[user_id] = 1

        if user_id not in race_bets.setdefault(race_id, {}): race_bets[race_id][user_id] = []
        race_bets[race_id][user_id].append((bet_type, selected_horse_full, bet_amount))

        type_title = "獨贏" if bet_type == "win" else "位置" if bet_type == "pla" else "連贏"
        bot.reply_to(message, f"✅ （{type_title}）成功！\n💰 投注：{bet_amount:,} 金幣\n📈 賠率：{odds_val} 倍", parse_mode='Markdown')

    except Exception:
        bot.reply_to(message, "⚠️ **投注格式錯誤！**\n👉 獨贏：`/win [編號] [金額]`\n👉 位置：`/pla [編號] [金額]`\n👉 連贏：`/ww [A] [B] [金額]`", parse_mode='Markdown')

@bot.message_handler(commands=['refund'])
def refund_bet(message):
    user_id = message.from_user.id
    if current_race != "betting" or user_bet_count.get(user_id, 0) == 0 or user_refund_count.get(user_id, 0) >= 1: return
    refund_amount = user_actual_deduct.get(user_id, 0)
    update_chips(user_id, refund_amount) 
    if race_id in race_bets and user_id in race_bets[race_id]: del race_bets[race_id][user_id]
    user_bet_count[user_id] = 0; user_refund_count[user_id] = 1
    bot.reply_to(message, f"💸 退款成功！退回金額：`{refund_amount:,}` 金幣", parse_mode='Markdown')

# ================== 其他基礎指令 ==================
@bot.message_handler(commands=['daily'])
def daily(message):
    user_id = message.from_user.id
    today = date.today().isoformat()  
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT last_daily FROM users WHERE user_id=?", (user_id,))
        if (last := c.fetchone()) and last[0] == today:
            bot.reply_to(message, "⚠️ 你今天已經領過每日獎勵！明天再來吧。")
            return
        c.execute("UPDATE users SET last_daily=? WHERE user_id=?", (today, user_id))
        conn.commit()
    update_chips(user_id, 3000)
    bot.reply_to(message, "🎁 **每日簽到成功！** +3000 金幣")

@bot.message_handler(commands=['money'])
def money(message): bot.reply_to(message, f"💰 你的餘額：**{get_chips(message.from_user.id):,}** 金幣", parse_mode='Markdown')

@bot.message_handler(commands=['start', 'help'])
def help_cmd(message):
    text = f"""🤖 **賽鼠機器人指令列表**
/startrun - 開始新賽事
/money   - 查詢目前金幣
/refund    - 開賽前退款當局投注
/daily     - 領取每日福利 (+3000)
/pay - 轉讓金幣 (回覆訊息: `/pay 金額` 或標記: `/pay @用戶 金額`)
【投注方式】
/win 號碼 金額
/pla 號碼 金額
/ww 號碼1 號碼2 金幣
"""
    bot.reply_to(message, text, parse_mode='HTML')

# ================== 啟動服務 ==================
print(f"🚀 {BOT_USERNAME} 【優化清理版】啟動！")
bot.infinity_polling(timeout=20, long_polling_timeout=10)
