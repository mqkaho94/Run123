import telebot
from telebot import util  
import random
import time
import threading
import sqlite3
import os
import json
from datetime import datetime, date

# ⚠️ 請記得去 @BotFather 重置 Token 並更換此處
TOKEN = "8447034432:AAFOW7PmFbBaY3p70dKAchGCUqKlH_ii9XI"
BOT_USERNAME = "@Gapjaibot"

# 🚀 啟用多線程 ThreadPool
bot = telebot.TeleBot(TOKEN, threaded=True, num_threads=4)

# 🔒 安全鎖
daily_lock = threading.Lock()
store_lock = threading.Lock()
db_lock = threading.Lock()  # 資料庫鎖，防多線程死鎖

BASE_NPC_HORSES = [
    ("奧雲狗狗", "⚡"), ("黑旋風", "🌪"), ("戰槌巨人", "⭐"), ("火麒麟", "🔥"), 
    ("疾風", "💨"), ("黃金戰鼠", "🏅"), ("海嘯", "🌊"), ("傲空", "🦅")
]

RANK_EMOJIS = {1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣", 5: "5️⃣", 6: "6️⃣", 7: "7️⃣", 8: "8️⃣"}

BETTING_SURFACE_STATUSES = [
    "鼠神加持🤩高光時刻", "外星物種👽高深莫測", "科技外掛🤖液態金屬", "剛吃興奮劑💊眼神清澈", 
    "昨晚拜神🙏獲得神秘力量", "祖先托夢👑這局穩贏", "賽道车神🏎️自帶BGM", "氣勢如虹😤單眼單挑", 
    "氪金玩家💰全身發光", "不可一世😎王者風範",
    "天生扁平足🦶跑動困難", "沉迷股票📉痛失家產心慌慌", "剛剛小兒麻痺症發作🤒", "霉運當頭🌀烏雲蓋頂", 
    "體重超標🐷走路都喘氣", "出局邊緣🥀毫無鬥志", "四肢無力🥵缺乏維他命", "中暑邊緣☀️頭暈身熱", 
    "靈魂出竅👻呆若木雞", "忘記帶大腦🧠全憑本能"
]

RACE_START_STATUSES = [
    "朋友最多轉圈哈姆共你🐹", "趕住返屋企瀨屎💩", "昨晚拜過黃大仙🙏獲得神祕力量加持",   
    "尋晚飲咗過期維奶🥛個肚好滾", "出門口踩到舊大狗屎💩霉運當頭", "尋晚拉咗十二次斯🚽對腳發軟",
    "倒瀉咗杯凍檸茶走甜熱辣辣🍹", "以為自己係比卡超⚡自帶十萬伏特", "突然叮噹大長篇上身🎒要拯救地球",
    "阿嬤覺得佢餓👵嫌餵到變咗個波", "智商突然下線🧠全憑生物本能前進", "食咗誠實豆沙包💊個人好清醒",
    "氪金玩家💰全身閃爍住人民幣嘅光芒", "眼神充滿殺氣🔪覺得自己係黎明", "自帶背景音樂BGM🎵氣勢如虹",
    "跛咗隻腳🧑嫌推輪椅代步跑", "成晚通宵打機🎮條黑眼圈去到下巴", "飲咗兩啖假酒🥴左右不分亂打打",
    "失戀萬念毀滅💔打算跑完去跳海", "高山反應🏔️呼吸困難行得好辛苦"
]

DB_FILE = '/data/race.db'
PRICE_HAMSTER = 3000
PRICE_FOOD = 300
PRICE_CLEAN = 500

def get_db_connection():
    """獲取資料庫連接，並加入 timeout 避免多線程鎖死"""
    return sqlite3.connect(DB_FILE, timeout=20)

# ================== 💾 資料庫管理 ==================
def init_db():
    try: os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    except: pass
    with db_lock:
        with get_db_connection() as conn:
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
                last_luck_date TEXT DEFAULT NULL,
                last_fed_time TEXT DEFAULT NULL,
                last_cleaned_time TEXT DEFAULT NULL,
                born_time TEXT DEFAULT NULL
            );
            ''')
            
            c.execute('''
            CREATE TABLE IF NOT EXISTS rainbow_bridge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER,
                hamster_name TEXT,
                reason TEXT,
                days_survived INTEGER,
                wins INTEGER,
                total_races INTEGER,
                memorial_date TEXT
            );
            ''')
            
            c.execute('''CREATE TABLE IF NOT EXISTS system_config (key TEXT PRIMARY KEY, value TEXT);''')
            
            c.execute("PRAGMA table_info(users)")
            columns = [col[1] for col in c.fetchall()]
            for col_name, col_type in [
                ("horse_first", "INTEGER DEFAULT 0"), ("horse_second", "INTEGER DEFAULT 0"), 
                ("horse_third", "INTEGER DEFAULT 0"), ("horse_losses", "INTEGER DEFAULT 0"), 
                ("last_luck_date", "TEXT DEFAULT NULL"), ("last_fed_time", "TEXT DEFAULT NULL"),
                ("last_cleaned_time", "TEXT DEFAULT NULL"), ("born_time", "TEXT DEFAULT NULL")
            ]:
                if col_name not in columns:
                    c.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
            conn.commit()

def check_single_hamster_survival(user_id):
    with db_lock:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT has_horse, horse_name, last_fed_time, last_cleaned_time, born_time, horse_first, horse_second, horse_third, horse_losses FROM users WHERE user_id=?", (user_id,))
            row = c.fetchone()
            if not row or row[0] == 0:
                return None
            
            has_horse, name, last_fed, last_clean, born, first, second, third, losses = row
            now = datetime.utcnow()
            
            if last_fed:
                try:
                    fed_dt = datetime.fromisoformat(last_fed)
                    if (now - fed_dt).days >= 3:
                        conn_close = True
                except: conn_close = False
                    
            if last_clean:
                try:
                    clean_dt = datetime.fromisoformat(last_clean)
                    if (now - clean_dt).days >= 7:
                        conn_close = True
                except: conn_close = False

    if last_fed and (now - datetime.fromisoformat(last_fed)).days >= 3:
        kill_hamster(user_id, name, "飢餓離世（連續3天無買鼠糧），去咗彩虹橋。🌾", born, first, second, third, losses)
        return "餓死"
    if last_clean and (now - datetime.fromisoformat(last_clean)).days >= 7:
        kill_hamster(user_id, name, "環境惡劣生病離世（連續7天無買清潔），希望天堂無污垢。🧹", born, first, second, third, losses)
        return "病死"
    return None

def kill_hamster(user_id, name, reason, born_time_str, first, second, third, losses):
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    days = 1
    if born_time_str:
        try: days = max(1, (datetime.utcnow() - datetime.fromisoformat(born_time_str)).days)
        except: pass
    total_races = first + second + third + losses
    
    with db_lock:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("""
                INSERT INTO rainbow_bridge (player_id, hamster_name, reason, days_survived, wins, total_races, memorial_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (user_id, name, reason, days, first, total_races, now_str))
            c.execute("""
                UPDATE users SET has_horse=0, horse_name=NULL, horse_first=0, horse_second=0, horse_third=0, horse_losses=0,
                last_fed_time=NULL, last_cleaned_time=NULL, born_time=NULL WHERE user_id=?
            """, (user_id,))
            conn.commit()

def check_all_survivals_global():
    with db_lock:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT user_id FROM users WHERE has_horse=1")
            uids = [r[0] for r in c.fetchall()]
    for uid in uids:
        check_single_hamster_survival(uid)

def roll_random_disaster(user_id, name, born_str, first, second, third, losses):
    if random.random() < 0.05: 
        reason = random.choice([
            "不幸突發猝死，主人十分傷心。⚡",
            "不小心走失了，從此音訊全無。永久失去。🍃"
        ])
        kill_hamster(user_id, name, reason, born_str, first, second, third, losses)
        return reason
    return None

def get_chips(user_id):
    with db_lock:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT chips FROM users WHERE user_id=?", (user_id,))
            row = c.fetchone()
            if not row:
                c.execute("INSERT INTO users (user_id, chips) VALUES (?, 1000)", (user_id,))
                conn.commit()
                return 1000
            return row[0]

def update_chips(user_id, amount):
    with db_lock:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("UPDATE users SET chips = chips + ? WHERE user_id=?", (amount, user_id))
            conn.commit()

def get_user_horse(user_id):
    with db_lock:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT has_horse, horse_name, horse_first, horse_second, horse_third, horse_losses, last_fed_time, last_cleaned_time, born_time FROM users WHERE user_id=?", (user_id,))
            row = c.fetchone()
            if row: 
                return {"has_horse": row[0], "horse_name": row[1], "first": row[2], "second": row[3], "third": row[4], "losses": row[5], "last_fed": row[6], "last_clean": row[7], "born": row[8]}
            return {"has_horse": 0, "horse_name": None, "first": 0, "second": 0, "third": 0, "losses": 0, "last_fed": None, "last_clean": None, "born": None}

def get_owner_by_horse_name(horse_name):
    clean_name = horse_name
    if "." in clean_name: clean_name = clean_name.split(".", 1)[1]
    with db_lock:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT user_id FROM users WHERE horse_name=?", (clean_name,))
            row = c.fetchone()
            return row[0] if row else None

def get_all_registered_horses():
    with db_lock:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT user_id, horse_name FROM users WHERE has_horse=1 AND horse_name IS NOT NULL")
            return c.fetchall()

def get_all_users_for_luck():
    with db_lock:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT user_id, username, has_horse, horse_name, last_luck_date FROM users")
            return c.fetchall()

def update_luck_date(user_id, today_str):
    with db_lock:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("UPDATE users SET last_luck_date=? WHERE user_id=?", (today_str, user_id))
            conn.commit()

def sync_username(user_id, username):
    if not username: return
    with db_lock:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("UPDATE users SET username=? WHERE user_id=?", (username.lower(), user_id))
            conn.commit()

def record_detailed_result(user_id, rank_type):
    with db_lock:
        with get_db_connection() as conn:
            c = conn.cursor()
            if rank_type == 1: c.execute("UPDATE users SET horse_first = horse_first + 1 WHERE user_id=?", (user_id,))
            elif rank_type == 2: c.execute("UPDATE users SET horse_second = horse_second + 1 WHERE user_id=?", (user_id,))
            elif rank_type == 3: c.execute("UPDATE users SET horse_third = horse_third + 1 WHERE user_id=?", (user_id,))
            else: c.execute("UPDATE users SET horse_losses = horse_losses + 1 WHERE user_id=?", (user_id,))
            conn.commit()

def get_system_race_count():
    with db_lock:
        with get_db_connection() as conn:
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
    with db_lock:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("UPDATE system_config SET value=? WHERE key='total_races'", (str(new_count),))
            conn.commit()
    return new_count

def get_guarantee_plan():
    with db_lock:
        with get_db_connection() as conn:
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
    with db_lock:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("UPDATE system_config SET value=? WHERE key='guarantee_plan'", (json.dumps(plan),))
            conn.commit()
    return plan

init_db()

# ================== 賽事全域變數 ==================
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

def background_survival_loop():
    while True:
        try: check_all_survivals_global()
        except: pass
        time.sleep(3600)
threading.Thread(target=background_survival_loop, daemon=True).start()

# ================== 💸 轉帳系統 ==================
@bot.message_handler(commands=['pay'])
def pay_chips(message):
    try:
        from_user_id = message.from_user.id
        sync_username(from_user_id, message.from_user.username)
        to_user_id = None
        to_username = "神祕玩家"
        pay_amount = 0

        text_clean = message.text
        if f"{BOT_USERNAME}" in text_clean: text_clean = text_clean.replace(f"{BOT_USERNAME}", "")
        elif f"@run1234567bot" in text_clean.lower(): text_clean = text_clean.lower().replace("@run1234567bot", "")

        cmd = text_clean.split()
        if len(cmd) < 2:
            bot.reply_to(message, "❌ **格式錯誤**\n👉 回覆他人訊息轉帳：`/pay 金額`\n👉 直接標記名字轉帳：`/pay @玩家標記 金額`", parse_mode='Markdown')
            return

        if len(cmd) >= 3 and cmd[1].startswith('@'):
            target_username = cmd[1].replace('@', '').strip().lower()
            raw_amount = cmd[2].strip()
            with db_lock:
                with get_db_connection() as conn:
                    c = conn.cursor()
                    c.execute("SELECT user_id, username FROM users WHERE username=?", (target_username,))
                    row = c.fetchone()
                    if row:
                        to_user_id = row[0]
                        to_username = row[1] if row[1] else target_username
                    else:
                        bot.reply_to(message, f"❌ **轉帳失敗**：找不到玩家 `@{target_username}`。", parse_mode='Markdown')
                        return
        elif message.reply_to_message:
            if message.reply_to_message.from_user:
                to_user_id = message.reply_to_message.from_user.id
                to_username = message.reply_to_message.from_user.first_name
                sync_username(to_user_id, message.reply_to_message.from_user.username)
            else:
                bot.reply_to(message, "❌ **轉帳失敗**：無法讀取該訊息發送者隱私。", parse_mode='Markdown')
                return
            raw_amount = cmd[1].strip()
        else:
            bot.reply_to(message, "❌ **轉帳失敗！**", parse_mode='Markdown')
            return

        try:
            pay_amount = int(raw_amount)
            if pay_amount <= 0: return
        except ValueError: return

        if from_user_id == to_user_id: return
        from_user_chips = get_chips(from_user_id) 
        if from_user_chips < pay_amount: return

        get_chips(to_user_id) 
        update_chips(from_user_id, -pay_amount) 
        update_chips(to_user_id, pay_amount)   

        from_username = message.from_user.first_name if message.from_user.first_name else "神祕玩家"
        success_text = f"💸 **【金幣轉讓成功】** 💸\n🤝 轉出人：{from_username}\n🎁 接收人：{to_username}\n💰 轉讓金額：<b>{pay_amount:,}</b> 金幣"
        bot.send_message(message.chat.id, success_text, parse_mode='HTML')
    except: pass

# ================== 🛒 綜合商店系統（支援數字與按鈕快捷鍵） ==================
@bot.message_handler(commands=['buy'])
def store_buy(message):
    if message.chat.type != "private":
        bot.reply_to(message, f"❌ 限私訊使用！請點擊私訊： {BOT_USERNAME}")
        return
        
    user_id = message.from_user.id
    sync_username(user_id, message.from_user.username)
    
    with store_lock:
        chips = get_chips(user_id)
        info = get_user_horse(user_id)
        cmd = message.text.split()
        
        # ─── 情況一：只輸入 /buy (顯示商店目錄 + 快捷按鈕) ───
        if len(cmd) < 2:
            embed_text = "🛍️ <b>【賽鼠綜合商店中心】</b> 🛍️\n" + "—"*25 + f"\n💰 你的錢包餘額：<b>{chips:,}</b> 金幣\n\n"
            
            # 建立按鈕選單
            markup = telebot.types.InlineKeyboardMarkup()
            
            if info["has_horse"] == 0:
                embed_text += "⚠️ 你目前【擁有 0 隻鼠】，已解鎖購買賽鼠新秀！\n"
                embed_text += f"1️⃣ <b>購買新賽鼠</b>\n └ 價格：<code>$3,000</code> 金幣\n └ 指令：<code>/buy 1 你的鼠名</code> 或 <code>/buy hamster 你的鼠名</code>\n\n"
                embed_text += "🔒 <i>[ 鼠糧與清潔選項已關閉，請先購買一隻倉鼠 ]</i>"
                
                # 沒鼠時只給買鼠按鈕（因為需要名字，按鈕會提示指令）
                btn_buy_h = telebot.types.InlineKeyboardButton("1️⃣ 購買新賽鼠 ($3,000)", switch_inline_query_current_chat="/buy 1 ")
                markup.add(btn_buy_h)
            else:
                embed_text += f"🐿️ 當前愛鼠：<b>{info['horse_name']}</b>\n"
                embed_text += f"📊 戰績：🥇<code>{info['first']}</code> 亞<code>{info['second']}</code> 季<code>{info['third']}</code> 輸<code>{info['losses']}</code>\n\n"
                embed_text += "🔒 <i>[ You已擁有一隻愛鼠，無法重複購買 ]</i>\n\n"
                embed_text += f"2️⃣ <b>購買高級鼠糧 (重置3天餓死倒數)</b>\n └ 價格：<code>$300</code> 金幣\n └ 快捷指令：<code>/buy 2</code> 或 <code>/buy food</code>\n\n"
                embed_text += f"3️⃣ <b>購買籠子清潔 (重置7天病死倒數)</b>\n └ 價格：<code>$500</code> 金幣\n └ 快捷指令：<code>/buy 3</code> 或 <code>/buy clean</code>"
                
                # 有鼠時，加入 2號糧食 與 3號清潔 的直接點擊按鈕
                btn_food = telebot.types.InlineKeyboardButton("2️⃣ 買高級鼠糧 ($300)", callback_data="buy_fast_2")
                btn_clean = telebot.types.InlineKeyboardButton("3️⃣ 買籠子清潔 ($500)", callback_data="buy_fast_3")
                markup.add(btn_food, btn_clean)
                
            bot.reply_to(message, embed_text, parse_mode='HTML', reply_markup=markup)
            return
            
        # ─── 情況二：輸入了參數 (例如 /buy 2 或 /buy food) ───
        sub_item = cmd[1].lower()
        
        # 代替轉換：將 1, 2, 3 映射到對應的英文代碼
        if sub_item == "1": sub_item = "hamster"
        elif sub_item == "2": sub_item = "food"
        elif sub_item == "3": sub_item = "clean"
        
        # 1. 購買倉鼠
        if sub_item == "hamster":
            if info["has_horse"] == 1:
                bot.reply_to(message, f"❌ 購買失敗：你已經擁有一隻愛鼠了！")
                return
            if chips < PRICE_HAMSTER:
                bot.reply_to(message, f"❌ 餘額不足：購買新鼠需要 `${PRICE_HAMSTER}`。")
                return
            if len(cmd) < 3:
                bot.reply_to(message, f"❌ 請提供你想為賽鼠改的名字！\n格式：`/buy 1 你的鼠名`")
                return
                
            h_name = " ".join(cmd[2:]).strip()
            if len(h_name) < 1 or len(h_name) > 15:
                bot.reply_to(message, "❌ 賽鼠名字長度限制為 1-15 個字元。")
                return
                
            now_str = datetime.utcnow().isoformat()
            update_chips(user_id, -PRICE_HAMSTER)
            with db_lock:
                with get_db_connection() as conn:
                    c = conn.cursor()
                    c.execute("""
                        UPDATE users SET has_horse=1, horse_name=?, horse_first=0, horse_second=0, horse_third=0, horse_losses=0,
                        last_fed_time=?, last_cleaned_time=?, born_time=? WHERE user_id=?
                    """, (h_name, now_str, now_str, now_str, user_id))
                    conn.commit()
            bot.reply_to(message, f"🎉 **購買新秀成功！**\n專屬比賽愛鼠 **「{h_name}」** 已登記完成！")
            return
            
        # 驗證後續物資必須有鼠才能買
        if info["has_horse"] == 0:
            bot.reply_to(message, "❌ 購買失敗：你目前兩手空空沒有倉鼠！請先輸入 `/buy 1 鼠名` 購買一隻。")
            return
            
        now_str = datetime.utcnow().isoformat()
        
        # 2. 購買食物
        if sub_item == "food":
            if chips < PRICE_FOOD:
                bot.reply_to(message, f"❌ 金幣餘額不足！需要 `${PRICE_FOOD}`。")
                return
            update_chips(user_id, -PRICE_FOOD)
            with db_lock:
                with get_db_connection() as conn:
                    c = conn.cursor()
                    c.execute("UPDATE users SET last_fed_time=? WHERE user_id=?", (now_str, user_id))
                    conn.commit()
            bot.reply_to(message, f"🌾 購買成功！3天飢餓死亡時間已全部重置！(飽腹度100%)")
            
        # 3. 購買清潔
        elif sub_item == "clean":
            if chips < PRICE_CLEAN:
                bot.reply_to(message, f"❌ 金幣餘額不足！需要 `${PRICE_CLEAN}`。")
                return
            update_chips(user_id, -PRICE_CLEAN)
            with db_lock:
                with get_db_connection() as conn:
                    c = conn.cursor()
                    c.execute("UPDATE users SET last_cleaned_time=? WHERE user_id=?", (now_str, user_id))
                    conn.commit()
            bot.reply_to(message, f"🧹 購買成功！7天髒亂生病致死線已全面清零！(健康度100%)")
        else:
            bot.reply_to(message, "❌ 無效商品！請輸入 1, 2 或 3。")
            return
            
        disaster_txt = roll_random_disaster(user_id, info["horse_name"], info["born"], info["first"], info["second"], info["third"], info["losses"])
        if disaster_txt:
            bot.send_message(message.chat.id, f"🚨 **【突發天意大災難！】**\n在購買物資期間，你嘅愛鼠 **{info['horse_name']}** {disaster_txt}")

# ================== 🔘 處理按鈕直接點擊事件 ==================
@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_fast_'))
def callback_buy_fast(call):
    user_id = call.from_user.id
    item_num = call.data.split('_')[-1]
    
    fake_msg = telebot.types.Message(
        message_id=call.message.message_id,
        from_user=call.from_user,
        date=call.message.date,
        chat=call.message.chat,
        content_type='text',
        options=[],
        json_string=""
    )
    fake_msg.text = f"/buy {item_num}"
    store_buy(fake_msg)
    
    try: bot.answer_callback_query(call.id)
    except: pass

# ================== 🌈 彩虹橋公共紀念碑 ==================
@bot.message_handler(commands=['rainbow'])
def show_rainbow_bridge(message):
    try:
        sync_username(message.from_user.id, message.from_user.username)
        with db_lock:
            with get_db_connection() as conn:
                c = conn.cursor()
                c.execute("""
                    SELECT player_id, hamster_name, reason, days_survived, wins, total_races, memorial_date 
                    FROM rainbow_bridge ORDER BY id DESC LIMIT 12
                """)
                rows = c.fetchall()
                c.execute("SELECT COUNT(*) FROM rainbow_bridge")
                total_dead_count = c.fetchone()[0]
            
        if not rows:
            bot.reply_to(message, "🌈 目前一片詳和！還沒有任何玩家的愛鼠登入彩虹橋！")
            return
            
        memorial_text = "🌈 <b>【全服賽鼠彩虹橋 • 永恆榮譽碑】</b> 🌈\n" + "‾" * 32 + "\n"
        
        for row in rows:
            uid, name, reason, days, wins, total, m_date = row
            try: chat_member = bot.get_chat_member(message.chat.id, uid)
            except: chat_member = None
            owner_name = chat_member.user.first_name if chat_member else f"玩家({uid})"
            
            memorial_text += f"🕯️ <b>【{name}】</b> (鼠主: {owner_name})\n"
            memorial_text += f"  ⏱️ 陪伴時長：<code>{days} 天</code> | 🏆 生前戰績：<code>{wins} 勝 / {total} 場</code>\n"
            memorial_text += f"  🪦 離去去向：<i>{reason}</i>\n"
            memorial_text += f"  📅 紀念日期：<code>{m_date}</code>\n\n"
            
        if total_dead_count > 12:
            memorial_text += "—" * 15 + f"\n統計：已有 <b>{total_dead_count}</b> 隻賽鼠榮歸星海。"
            
        bot.send_message(message.chat.id, memorial_text, parse_mode='HTML')
    except Exception as e:
        print(f"彩虹橋讀取錯誤: {e}")

# ================== 🎰 開局排位 + 🔮 氣運系統 ==================
@bot.message_handler(commands=['startrun'])
def startrun(message):
    global current_race, race_id, race_odds, user_bet_count, user_refund_count, user_actual_deduct, current_horses, horse_statuses, scheduled_disasters, active_horse_luck
    if current_race:
        bot.reply_to(message, "⚠️ 已有賽事進行中！")
        return

    current_race = "betting"  
    total_races = increment_system_race_count()
    cycle_index = total_races % 10
    if cycle_index == 0: cycle_index = 10
    
    race_id = f"R{int(time.time())}"
    race_bets[race_id] = {}
    race_odds = {}
    horse_statuses = {}
    scheduled_disasters = {} 
    active_horse_luck = {}
    user_bet_count = {}
    user_refund_count = {}
    user_actual_deduct = {}
    
    plan = get_guarantee_plan()
    is_guarantee_round = str(cycle_index) in plan
    guarantee_count = plan.get(str(cycle_index), 0) if is_guarantee_round else 0

    sync_username(message.from_user.id, message.from_user.username)
    all_registered = get_all_registered_horses()
    final_8_horses = []  
    
    if len(all_registered) == 0:
        for npc_name, npc_icon in BASE_NPC_HORSES:
            final_8_horses.append((None, npc_name, npc_icon))
    else:
        random.shuffle(all_registered)
        selected_players = all_registered[:8]
        for uid, h_name in selected_players:
            final_8_horses.append((uid, h_name, "👑"))
        if len(final_8_horses) < 8:
            shortage = 8 - len(final_8_horses)
            available_npcs = BASE_NPC_HORSES.copy()
            random.shuffle(available_npcs)
            for i in range(shortage):
                npc_name, npc_icon = available_npcs[i]
                final_8_horses.append((None, npc_name, npc_icon))

    random.shuffle(final_8_horses)
    chosen_horses_pool = []
    for idx, (uid, h_name, icon) in enumerate(final_8_horses):
        lane_num = idx + 1
        chosen_horses_pool.append(f"{icon}{lane_num}.{h_name}")
    current_horses = chosen_horses_pool

    luck_announcements = []
    all_users = get_all_users_for_luck()
    today_str = date.today().isoformat()
    
    for u_id, u_name, has_h, h_name, last_luck_date in all_users:
        if last_luck_date == today_str:
            continue

        roll = random.random()
        if roll < 0.005:  
            update_luck_date(u_id, today_str) 
            try: nickname = bot.get_chat_member(message.chat.id, u_id).user.first_name
            except: nickname = f"@{u_name}" if u_name else f"玩家({u_id})"
            
            matching_horse = next((h for h in current_horses if h_name and h_name in h), None)
            if matching_horse and random.random() < 0.50:
                active_horse_luck[matching_horse] = "good"
                luck_announcements.append(f"🍀 <b>【氣運爆發 • 今日好運】</b>\n鼠主 <b>{nickname}</b> 獲得愛鼠之神眷顧！本局參賽愛鼠 <b>{matching_horse}</b> 獲得<b>【幸運值 +5% 跑速與暴走加成】</b>！🚀")
            else:
                update_chips(u_id, 3000)
                luck_announcements.append(f"🍀 <b>【氣運爆發 • 今日好運】</b>\n愛鼠之人 <b>{nickname}</b> 突發好運！獲得 <b>+3,000</b> 金幣已存入餘額！💰")

        elif roll >= 0.005 and roll < 0.010:  
            update_luck_date(u_id, today_str) 
            try: nickname = bot.get_chat_member(message.chat.id, u_id).user.first_name
            except: nickname = f"@{u_name}" if u_name else f"玩家({u_id})"
            
            matching_horse = next((h for h in current_horses if h_name and h_name in h), None)
            if matching_horse and random.random() < 0.50:
                active_horse_luck[matching_horse] = "bad"
                luck_announcements.append(f"💀 <b>【霉運當頭 • 今日歹運】</b>\n鼠主 <b>{nickname}</b> 驚逢黑仔期！本局參賽愛鼠 <b>{matching_horse}</b> 遭遇<b>【Debuff/死亡意外率 +5%】</b>！⚠️")
            else:
                update_chips(u_id, -3000)
                luck_announcements.append(f"💀 <b>【霉運當頭 • 今日歹運】</b>\n玩家 <b>{nickname}</b> 因隨地亂倒鼠糧被<b>罰款 $3,000</b>！💸")

    if random.random() < 0.04:
        disaster_count = random.choice([1, 2])
        unlucky_horses = random.sample(current_horses, disaster_count)
        for uh in unlucky_horses:
            trigger_point = random.uniform(0.0, 99.0)
            reason = random.choice(["🐱【被貓吃掉❌】", "🪤【踩到鼠夾❌】"])
            scheduled_disasters[uh] = {"trigger_at": trigger_point, "reason": reason}

    for h in current_horses:
        if active_horse_luck.get(h) == "bad" and h not in scheduled_disasters:
            if random.random() < 0.05:
                trigger_point = random.uniform(5.0, 85.0)
                reason = random.choice(["🐱【黑仔遇到野貓吃掉❌】", "🪤【歹運踩中特大鼠夾❌】"])
                scheduled_disasters[h] = {"trigger_at": trigger_point, "reason": reason}

    available_statuses = BETTING_SURFACE_STATUSES.copy()
    random.shuffle(available_statuses)
    round_statuses = available_statuses[:7]
    if random.random() < 0.50: round_statuses.append(random.choice(round_statuses))  
    else: round_statuses.append(available_statuses[7]) 
    random.shuffle(round_statuses)  

    guaranteed_cold_horses = []
    detected_cold_horses = []
    for idx, h in enumerate(current_horses):
        surface_txt = round_statuses[idx]
        is_cold = any(keyword in surface_txt for keyword in ["小兒麻痺", "出局邊緣", "沉迷股票", "體重超標"])
        if is_cold: detected_cold_horses.append(h)

    if is_guarantee_round and detected_cold_horses:
        actual_guarantee_count = min(guarantee_count, len(detected_cold_horses))
        guaranteed_cold_horses = random.sample(detected_cold_horses, actual_guarantee_count)

    text = f"賽鼠 **【賽鼠會 - 第 {total_races} 場】** 🐿️\n🏆 本場盃賽：【鼠王爭霸戰】\n"
    if is_guarantee_round: text += f"✨ _本場為本週期第 {cycle_index} 場暗號保底局_\n\n"
    else: text += f"📊 週期進度：第 {cycle_index}/10 場\n\n"
    
    for idx, h in enumerate(current_horses):
        lane_num = idx + 1
        surface_txt = round_statuses[idx] 

        is_hot = any(keyword in surface_txt for keyword in ["鼠神", "外星", "科技", "拜神", "賽道", "氪金", "不可一世"])
        is_cold = h in detected_cold_horses
        has_surface_buff = (not is_cold) and any(keyword in surface_txt for keyword in ["鼠神加持🤩高光時刻", "外星物種👽高深莫測"])

        is_cold_debuffed = False
        if is_cold:
            if h in guaranteed_cold_horses: is_cold_debuffed = False  
            else: is_cold_debuffed = (random.random() < 0.05)  

        horse_statuses[h] = {
            "betting_text": surface_txt, "start_text": "", "target_time": 50.0,  
            "dead_reason": None, "freeze_steps": 0, "freeze_reason": "",
            "is_buff_carrier": has_surface_buff, "is_debuff_carrier": is_cold_debuffed, 
            "buff_active": False, "debuff_active": False, "is_guaranteed": (h in guaranteed_cold_horses)
        }

        if is_cold: 
            win_odds = round(random.uniform(13.0, 20.0), 1)
            class_icon = "💀"
        elif is_hot: 
            win_odds = round(random.uniform(2.5, 3.6), 1)
            class_icon = "🔥"
        else: 
            win_odds = round(random.uniform(4.0, 8.5), 1)
            class_icon = "🎲"

        place_odds = round(win_odds * 0.4, 1)
        if place_odds < 1.1: place_odds = 1.1  
        race_odds[h] = win_odds  
        
        icon = h[0]
        name_part = h.split('.', 1)[1]
        
        luck_tag = " 🍀[好運加成]" if active_horse_luck.get(h) == "good" else " 💀[歹運纏身]" if active_horse_luck.get(h) == "bad" else ""
        if h in guaranteed_cold_horses: luck_tag += " ✨[暗影爆發]"

        text += f"{lane_num} {name_part}{icon}{luck_tag} 🎪 {surface_txt}\n"
        text += f"    {class_icon} 獨贏: {win_odds}倍 | 位置: {place_odds}倍\n"

    text += "\n" + "—" * 20 + "\n"
    text += "💰 **【下注方式】** /win 號碼 金額 | /pla 號碼 金額 | /ww 號碼1 號碼2 金額\n"
    
    if luck_announcements:
        try: bot.send_message(message.chat.id, "🔮 <b>【每局天星氣運星象通報】</b> 🔮\n" + "‾"*25 + "\n" + "\n\n".join(luck_announcements), parse_mode='HTML')
        except: pass
        time.sleep(1)

    bot.reply_to(message, text, parse_mode='Markdown')
    if cycle_index == 10: refresh_guarantee_plan()
    threading.Timer(60, lambda: run_race(message.chat.id)).start()

# ================== 直播與戰績結算 ==================
def run_race(chat_id):
    global current_race, race_id, race_odds, race_bets, current_horses, horse_statuses, scheduled_disasters, active_horse_luck
    
    if current_race != "betting": return
    current_race = "running" 
    
    status_intro = f"📋 **賽前選手狀態通報** 📋\n" + "‾" * 25 + "\n"
    for h in current_horses:
        start_txt = random.choice(RACE_START_STATUSES)
        if horse_statuses[h]["is_debuff_carrier"]:
            start_txt = "❌ 突然舊患復發！全身發軟手震震"
            
        horse_statuses[h]["start_text"] = start_txt  
        luck_desc = ""
        if active_horse_luck.get(h) == "good": luck_desc = " 🍀(今日幸運加速)"
        elif active_horse_luck.get(h) == "bad": luck_desc = " 💀(今日意外率提升)"
        
        status_intro += f"{h} ➡️ **{start_txt}**{luck_desc}\n"

        if horse_statuses[h].get("is_guaranteed", False): base_time_range = (22.0, 26.0) 
        else:
            if start_txt in ["朋友最多轉圈哈姆共你🐹", "趕住返屋企瀨屎💩", "昨晚拜過黃大仙🙏獲得神祕力量加持"]:
                if random.random() < 0.60: base_time_range = (27.0, 35.0) 
                else: base_time_range = (40.0, 55.0) 
            elif horse_statuses[h]["is_debuff_carrier"]: base_time_range = (120.0, 180.0) 
            else:
                status_score = random.randint(1, 10)
                if status_score >= 9: base_time_range = (28.0, 38.0)  
                elif status_score >= 4: base_time_range = (42.0, 58.0)  
                else: base_time_range = (62.0, 80.0)
                
        final_target_time = random.uniform(*base_time_range)
        if active_horse_luck.get(h) == "good": final_target_time *= 0.95 
        horse_statuses[h]["target_time"] = final_target_time

    status_intro += "\n⏱ _狀態展示中，比賽將於 5 秒後正式鳴槍！_"
    race_msg = bot.send_message(chat_id, status_intro, parse_mode='Markdown')
    time.sleep(5)  
    
    TOTAL_DISTANCE = 100.0  
    DISPLAY_LENGTH = 15     
    speeds = {h: TOTAL_DISTANCE / horse_statuses[h]["target_time"] for h in current_horses}
    current_distance = {h: 0.0 for h in current_horses}
    finished_horses = []   
    dead_horses = []       
    
    start_time = time.time()
    last_refresh_time = start_time
    
    while (len(finished_horses) < 3) and (len(finished_horses) + len(dead_horses) < len(current_horses)):
        time.sleep(1.0)  
        now = time.time()
        current_second_reports = {}
        
        for h in current_horses:
            if horse_statuses[h]["dead_reason"] is not None:
                current_second_reports[h] = f"❌ {horse_statuses[h]['dead_reason']}"
                continue

            if current_distance[h] >= TOTAL_DISTANCE:
                r = finished_horses.index(h) + 1
                current_second_reports[h] = f"🏁 已衝線 (第 {r} 名)"
                continue

            if h in scheduled_disasters and current_distance[h] >= scheduled_disasters[h]["trigger_at"]:
                if horse_statuses[h].get("is_guaranteed", False): pass
                else:
                    disaster_reason = scheduled_disasters[h]["reason"]
                    horse_statuses[h]["dead_reason"] = disaster_reason
                    dead_horses.append(h)
                    current_second_reports[h] = f"❌ {disaster_reason}"
                    
                    if "👑" in h:
                        o_id = get_owner_by_horse_name(h)
                        if o_id:
                            h_info = get_user_horse(int(o_id))
                            kill_hamster(int(o_id), h_info["horse_name"], f"在賽事中突發意外【{disaster_reason}】淘汰，不幸離世。🪦", h_info["born"], h_info["first"], h_info["second"], h_info["third"], h_info["losses"])
                    continue
            
            if horse_statuses[h]["freeze_steps"] > 0:
                reason = horse_statuses[h]["freeze_reason"]
                sec_left = horse_statuses[h]["freeze_steps"]
                current_second_reports[h] = f"⚠️ {reason} (剩餘 {sec_left} 秒) 🕒"
                horse_statuses[h]["freeze_steps"] -= 1 
                continue 
            
            if random.random() < 0.005 and not horse_statuses[h].get("is_guaranteed", False):
                freeze_sec = random.randint(3, 5) 
                freeze_type = random.choice(["發呆停止步行 💤", "地上撿到芝士吃兩口 🧀"])
                horse_statuses[h]["freeze_steps"] = freeze_sec
                horse_statuses[h]["freeze_reason"] = freeze_type
                current_second_reports[h] = f"⚠️ {freeze_type} (剩餘 {freeze_sec} 秒) 🕒"
                horse_statuses[h]["freeze_steps"] -= 1 
                continue

            buff_check_chance = 0.055 if active_horse_luck.get(h) == "good" else 0.005
            if (horse_statuses[h]["is_buff_carrier"] or active_horse_luck.get(h) == "good") and not horse_statuses[h]["buff_active"]:
                if random.random() < buff_check_chance: horse_statuses[h]["buff_active"] = True

            if horse_statuses[h]["is_debuff_carrier"]:
                step_modifier = 0.1 
                action_text = "⚠️ 狀態大下滑！腳軟慢跑中... 🐢"
            elif horse_statuses[h].get("is_guaranteed", False):
                step_modifier = 1.3 
                action_text = "✨ 🚀 隱藏潛能突發暴走！全速大躍進！！"
            elif horse_statuses[h]["buff_active"]:
                step_modifier = 3.5  
                action_text = "✨ 🚀 隱藏潛能突發暴走！全速大躍進！！"
                horse_statuses[h]["buff_active"] = False 
            else:
                move_roll = random.randint(1, 10)
                if move_roll >= 9: step_modifier = 2.0; action_text = "⚡ 快步推進"
                elif move_roll >= 4: step_modifier = 1.0; action_text = "✨ 穩步向前"
                else: step_modifier = 0.5; action_text = "💤 慢步推進"
                
            current_distance[h] += (speeds[h] * 1.0) * step_modifier + random.uniform(-0.2, 0.2)
            if current_distance[h] < 0: current_distance[h] = 0
            
            if current_distance[h] >= TOTAL_DISTANCE:
                current_distance[h] = TOTAL_DISTANCE
                if h not in finished_horses: finished_horses.append(h)
                current_second_reports[h] = f"🏁 剛剛衝線了！(第 {finished_horses.index(h) + 1} 名)"
            else: current_second_reports[h] = action_text
                        
        if now - last_refresh_time >= 3.0 or (len(finished_horses) >= 3) or (len(finished_horses) + len(dead_horses) == len(current_horses)):
            last_refresh_time = now
            dynamic_text = f"🐿️ **現場直播** 🏁\n" + "‾" * 25 + "\n"
            
            for h in current_horses:
                if horse_statuses[h]["dead_reason"] is not None:
                    dynamic_text += f"{h} ➡️ {horse_statuses[h]['dead_reason']}\n\n"
                else:
                    progress = int((current_distance[h] / TOTAL_DISTANCE) * DISPLAY_LENGTH)
                    progress = min(max(progress, 0), DISPLAY_LENGTH)
                    track_str = "🏁 " + "_" * (DISPLAY_LENGTH - progress) + "🐿️" + "_" * progress
                    status = ""
                    if h in finished_horses:
                        r = finished_horses.index(h) + 1
                        status = " 🥇【冠軍】" if r==1 else " 🥈【亞軍】" if r==2 else " 🥉【季軍】"
                    dynamic_text += f"{h}{status}\n`{track_str}`\n\n"
            
            action_reports = []
            for h in current_horses:
                msg_status = current_second_reports.get(h, "未知")
                if horse_statuses[h]["dead_reason"] is not None: rank_str = "淘汰"
                elif h in finished_horses: rank_str = f"第 {finished_horses.index(h) + 1} 名"
                else:
                    higher_count = sum(1 for comp in current_horses if comp != h and horse_statuses[comp]["dead_reason"] is None and comp not in finished_horses and current_distance[comp] > current_distance[h])
                    current_rank = len(finished_horses) + 1 + higher_count
                    rank_str = f"第 {current_rank} 名"
                action_reports.append(f"🏃 [{rank_str}] {h} ➡️ `[{msg_status}]`")
            
            dynamic_text += "—" * 15 + "\n"
            dynamic_text += "📊 **【即時動態戰況提示】**\n" + "\n".join(action_reports)
            
            try: bot.edit_message_text(dynamic_text, chat_id, race_msg.message_id, parse_mode='Markdown')
            except: pass

    alive_remaining = [h for h in current_horses if h not in finished_horses and h not in dead_horses]
    alive_remaining.sort(key=lambda h: current_distance[h], reverse=True)
    all_ranks = finished_horses + alive_remaining + dead_horses
    
    final_text = f"🐿️ **直播結束（定格名次）** 🏁\n" + "‾" * 25 + "\n"
    for h in current_horses:
        if horse_statuses[h]["dead_reason"] is not None:
            final_text += f"{h} ➡️ {horse_statuses[h]['dead_reason']} (取消資格)\n\n"
        else:
            final_rank = all_ranks.index(h) + 1
            rank_emoji = RANK_EMOJIS.get(final_rank, "🐿️") 
            progress = int((current_distance[h] / TOTAL_DISTANCE) * DISPLAY_LENGTH)
            progress = min(max(progress, 0), DISPLAY_LENGTH)
            track_str = "🏁 " + "_" * (DISPLAY_LENGTH - progress) + rank_emoji + "_" * progress
            status = " 🥇【冠軍】" if final_rank==1 else " 🥈【亞軍】" if final_rank==2 else " 🥉【季軍】" if final_rank==3 else ""
            final_text += f"{h}{status}\n`{track_str}`\n\n"
    
    final_text += "—" * 15 + "\n🏁 比賽結束！正在計算最終名次與分紅..."
    try: bot.edit_message_text(final_text, chat_id, race_msg.message_id, parse_mode='Markdown')
    except: pass
                
    winner, second = all_ranks[0] if len(finished_horses) > 0 else None, all_ranks[1] if len(finished_horses) > 1 else None
    
    result = "🏆 **最終賽果名次結果** 🏆\n\n"
    for i, h in enumerate(all_ranks, 1):
        medal = "🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else "🏁"
        if horse_statuses[h]["dead_reason"] is not None:
            result += f"❌ 未完賽：{h} -> {horse_statuses[h]['dead_reason']} (全輸)\n"
        else:
            result += f"{medal} 第 {i} 名：{h} (獨贏 {race_odds[h]}x)\n"
    bot.send_message(chat_id, result, parse_mode='Markdown')
    
    if race_id in race_bets and len(finished_horses) > 0:
        payout_message = "🎉 **派彩結果** 🎉\n\n"
        has_winner = False
        for uid, bets in race_bets[race_id].items():
            win_amount = 0
            for b_type, horses, amt in bets:
                if b_type == "win" and winner and horses == winner: win_amount += int(amt * race_odds[winner])
                elif b_type == "pla" and horses in finished_horses[:3]: win_amount += int(amt * (race_odds[horses] * 0.4)) 
                elif b_type == "ww" and winner and second and isinstance(horses, list) and set(horses) == set([winner, second]):
                    win_amount += int(amt * (race_odds[winner] * race_odds[second]))
            if win_amount > 0:
                update_chips(uid, win_amount)
                try: p_name = bot.get_chat_member(chat_id, uid).user.first_name
                except: p_name = f"玩家({uid})"
                payout_message += f"✅ 玩家 <b>{p_name}</b> 贏得 <b>{win_amount:,}</b> 金幣\n"
                has_winner = True
        if has_winner: bot.send_message(chat_id, payout_message, parse_mode='HTML')
        else: bot.send_message(chat_id, "壓注全空！本局沒有人中獎 💸")
    else: bot.send_message(chat_id, "壓注全空！本局沒有人中獎 💸")

    for h in current_horses:
        if "👑" in h: 
            owner_id = get_owner_by_horse_name(h)
            if owner_id:
                owner_id = int(owner_id)
                rank_idx = all_ranks.index(h)
                if horse_statuses[h]["dead_reason"] is None:
                    if rank_idx < 3: record_detailed_result(owner_id, rank_type=(rank_idx + 1))
                    else: record_detailed_result(owner_id, rank_type=4)

    owner_text = "✨ <b>【本局鼠主專利分紅】</b> ✨\n"
    has_owner_bonus = False
    consolation_owners = [] 

    for rank_idx in range(min(3, len(finished_horses))):
        target_horse = finished_horses[rank_idx]
        if "👑" in target_horse:
            owner_id = get_owner_by_horse_name(target_horse)
            if owner_id:
                owner_id = int(owner_id)
                rank_num = rank_idx + 1
                try: owner_name = bot.get_chat_member(chat_id, owner_id).user.first_name
                except: owner_name = f"鼠主({owner_id})"
                
                if rank_num == 1: bonus_chips = random.randint(10000, 20000); t_title = "🥇 冠軍"
                elif rank_num == 2: bonus_chips = random.randint(6000, 7500); t_title = "🥈 亞軍"
                else: bonus_chips = random.randint(1000, 2000); t_title = "🥉 季軍"
                
                update_chips(owner_id, bonus_chips)
                owner_text += f"恭喜專屬鼠 <b>{target_horse}</b> 榮獲{t_title}！\n鼠主 <b>{owner_name}</b> 獲得分紅大獎 <b>+{bonus_chips:,}</b> 金幣 💰\n"
                has_owner_bonus = True

    for rank_idx in range(3, len(all_ranks)):
        target_horse = all_ranks[rank_idx]
        if "👑" in target_horse:
            owner_id = get_owner_by_horse_name(target_horse)
            if owner_id: consolation_owners.append(int(owner_id))

    if consolation_owners:
        consolation_mentions = []
        for c_owner in consolation_owners:
            lucky_comfort_bonus = random.randint(300, 500)
            update_chips(c_owner, lucky_comfort_bonus)
            try: c_name = bot.get_chat_member(chat_id, c_owner).user.first_name
            except: c_name = f"鼠主({c_owner})"
            consolation_mentions.append(f"<b>{c_name}</b> (<b>+{lucky_comfort_bonus:,}</b>)")
        owner_text += f"\n🎁 <b>【鼠主同慶安慰獎】</b>\n本局遺憾落敗（或不幸罹難）的鼠主： " + "、".join(consolation_mentions) + f" 獲得安慰分紅！\n"
        has_owner_bonus = True

    if has_owner_bonus: bot.send_message(chat_id, owner_text, parse_mode='HTML')
    
    current_race, race_odds, horse_statuses, scheduled_disasters, active_horse_luck = None, {}, {}, {}, {}
    if race_id in race_bets: del race_bets[race_id]

# ================== 📊 排行榜功能 ==================
@bot.message_handler(commands=['rk'])
def show_leaderboard(message):
    try:
        sync_username(message.from_user.id, message.from_user.username)
        with db_lock:
            with get_db_connection() as conn:
                c = conn.cursor()
                c.execute("""
                    SELECT username, horse_name, horse_first, horse_second, horse_third, horse_losses, user_id 
                    FROM users WHERE has_horse = 1 AND horse_name IS NOT NULL
                """)
                rows = c.fetchall()
            
        if not rows:
            bot.reply_to(message, "📊 目前還沒有任何專屬賽鼠的比賽記錄！", parse_mode='Markdown')
            return

        def get_sort_key(row): return (row[2], row[3], row[4])
        sorted_rows = sorted(rows, key=get_sort_key, reverse=True)

        leaderboard_text = "📊 <b>【賽鼠殿堂 - 官方戰績榮譽榜】</b> 📊\n" + "‾" * 30 + "\n"

        for idx, row in enumerate(sorted_rows, 1):
            uname, h_name, firsts, seconds, thirds, losses, uid = row
            total_races = firsts + seconds + thirds + losses
            medal = "👑 🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"[{idx}]"
            try: nickname = bot.get_chat_member(message.chat.id, uid).user.first_name
            except: nickname = f"@{uname}" if uname else f"玩家({uid})"

            leaderboard_text += f"{medal} <b>{h_name}</b> (鼠主: {nickname})\n"
            leaderboard_text += f"    🏆 榮譽：🥇<code>{firsts} 冠</code> | 🥈<code>{seconds} 亞</code> | 🥉<code>{thirds} 季</code>\n"
            leaderboard_text += f"    📉 損益：❌<code>{losses} 輸</code> (總出賽次數: {total_races} 場)\n\n"

        bot.send_message(message.chat.id, leaderboard_text, parse_mode='HTML')
    except Exception as e: print(f"排行榜出錯: {e}")

# ================== 投注與退款邏輯 ==================
@bot.message_handler(commands=['win', 'pla', 'ww'])
def place_bet(message):
    global current_race, race_id, race_odds, user_bet_count, user_actual_deduct, current_horses
    error_help_text = "❌ **投注格式錯誤！**\n👉 獨贏：`/win [編號] [金額]`\n👉 位置：`/pla [編號] [金額]`\n👉 連贏：`/ww [A] [B] [金額]`"
    
    if current_race != "betting":
        bot.reply_to(message, "❌ 目前非投注時間！")
        return

    user_id = message.from_user.id
    sync_username(user_id, message.from_user.username)
    if user_bet_count.get(user_id, 0) >= 1:
        bot.reply_to(message, "❌ 您本場已投注過！更改請先輸入 /refund 退款。")
        return

    text_clean = message.text
    if f"{BOT_USERNAME}" in text_clean: text_clean = text_clean.replace(f"{BOT_USERNAME}", "")
    elif f"@run1234567bot" in text_clean.lower(): text_clean = text_clean.lower().replace("@run1234567bot", "")

    cmd = text_clean.split()
    if len(cmd) < 2:
        bot.reply_to(message, error_help_text, parse_mode='Markdown')
        return

    bet_type = cmd[0][1:].lower()  
    chips = get_chips(user_id)

    try:
        if bet_type in ["win", "pla"]:
            if len(cmd) < 3:
                bot.reply_to(message, error_help_text, parse_mode='Markdown')
                return
            horse_num = int(cmd[1])
            amount_str = cmd[2]
            
            if horse_num < 1 or horse_num > len(current_horses):
                bot.reply_to(message, f"❌ 找不到該號碼！", parse_mode='Markdown')
                return
            selected_horse_full = current_horses[horse_num-1]
            horse_name_clean = selected_horse_full.split('.', 1)[1] if '.' in selected_horse_full else selected_horse_full
            horse_display = f"（{horse_num}號）（{horse_name_clean}）"
            odds_val = race_odds[selected_horse_full] if bet_type == "win" else round(race_odds[selected_horse_full] * 0.4, 1)

        elif bet_type == "ww":
            if len(cmd) < 4:
                bot.reply_to(message, error_help_text, parse_mode='Markdown')
                return
            h1, h2 = int(cmd[1]), int(cmd[2])
            amount_str = cmd[3]
            
            if h1 == h2 or min(h1, h2) < 1 or max(h1, h2) > len(current_horses):
                bot.reply_to(message, f"❌ 號碼選擇不合法！", parse_mode='Markdown')
                return
            selected_horse_full = [current_horses[h1-1], current_horses[h2-1]]
            h1_clean = selected_horse_full[0].split('.', 1)[1] if '.' in selected_horse_full[0] else selected_horse_full[0]
            h2_clean = selected_horse_full[1].split('.', 1)[1] if '.' in selected_horse_full[1] else selected_horse_full[1]
            horse_display = f"（{h1},{h2}號）（{h1_clean} & {h2_clean}）"
            odds_val = round(race_odds[selected_horse_full[0]] * race_odds[selected_horse_full[1]], 1)
        else: return 

        if "%" in amount_str:
            pct = int(amount_str.replace("%", ""))
            bet_amount = int(chips * pct / 100)
        else: bet_amount = int(amount_str)

        if bet_amount <= 0:
            bot.reply_to(message, "❌ 投注金額必須大於 0 金幣！", parse_mode='Markdown')
            return

        credit = 100
        actual_deduct = max(0, bet_amount - credit)
        if actual_deduct > chips:
            bot.reply_to(message, f"❌ 金幣餘額不足！你目前只有 `{chips:,}` 金幣。", parse_mode='Markdown')
            return

        update_chips(user_id, -actual_deduct)
        user_actual_deduct[user_id] = actual_deduct 
        user_bet_count[user_id] = 1

        if user_id not in race_bets[race_id]: race_bets[race_id][user_id] = []
        race_bets[race_id][user_id].append((bet_type, selected_horse_full, bet_amount))

        type_title = "獨贏" if bet_type == "win" else "位置" if bet_type == "pla" else "連贏"
        potential_win = int(bet_amount * odds_val)
        bot.reply_to(message, f"（{type_title}）成功 🎊 {horse_display}\n投注幾錢：{bet_amount:,} 金幣\n幾多倍：{odds_val} 倍\n贏出總數可以收幾多：{potential_win:,} 金幣", parse_mode='Markdown')
    except (ValueError, IndexError): bot.reply_to(message, error_help_text, parse_mode='Markdown')
    except Exception as e: print(f"投注未知系統錯誤: {e}")

@bot.message_handler(commands=['refund'])
def refund_bet(message):
    global current_race, race_id, race_bets, user_bet_count, user_refund_count, user_actual_deduct
    if current_race != "betting": return
    user_id = message.from_user.id
    if user_bet_count.get(user_id, 0) == 0 or user_refund_count.get(user_id, 0) >= 1: return
    refund_amount = user_actual_deduct.get(user_id, 0)
    update_chips(user_id, refund_amount) 
    if race_id in race_bets and user_id in race_bets[race_id]: del race_bets[race_id][user_id]
    user_bet_count[user_id] = 0
    user_refund_count[user_id] = 1
    bot.reply_to(message, f"✅ 退款成功！實退錢包金額：`{refund_amount:,}` 金幣", parse_mode='Markdown')

# ================== 每日福利 ==================
@bot.message_handler(commands=['daily'])
def daily(message):
    user_id = message.from_user.id
    sync_username(user_id, message.from_user.username)
    today = date.today().isoformat()  
    with daily_lock:
        with db_lock:
            with get_db_connection() as conn:
                c = conn.cursor()
                c.execute("SELECT last_daily FROM users WHERE user_id=?", (user_id,))
                last = c.fetchone()
                if last and last[0] == today:
                    bot.reply_to(message, "❌ 你今天已經領過每日獎勵！明天再來吧。")
                    return
                c.execute("UPDATE users SET last_daily=? WHERE user_id=?", (today, user_id))
                conn.commit()
        update_chips(user_id, 3000)
        bot.reply_to(message, "✅ **每日簽到成功！** +3000 金幣 💰")

# ================== 🛠️ 個人狀態與健康檢查功能 ==================
@bot.message_handler(commands=['money'])
def money(message):
    """純粹專注顯示玩家金幣餘額"""
    user_id = message.from_user.id
    sync_username(user_id, message.from_user.username)
    
    chips = get_chips(user_id)
    
    balance_text = f"💰 <b>【玩家資產查詢】</b>\n" + "‾" * 20 + f"\n"
    balance_text += f"👤 玩家：{message.from_user.first_name}\n"
    balance_text += f"💵 金幣餘額：<b>{chips:,}</b> 金幣"
    
    bot.reply_to(message, balance_text, parse_mode='HTML')

@bot.message_handler(commands=['myhamster'])
def my_hamster_cmd(message):
    """精確計算距離飢餓、生病離世還剩幾天幾小時"""
    user_id = message.from_user.id
    sync_username(user_id, message.from_user.username)
    
    info = get_user_horse(user_id)
    if info["has_horse"] == 0:
        bot.reply_to(message, "❌ **健康檢查失敗**\n你目前兩手空空沒有愛鼠！請先私訊我輸入 `/buy 1 你的鼠名` 購買一隻吧！")
        return
        
    now = datetime.utcnow()
    
    # 1. 計算飢餓剩餘時間 (3天 = 72小時)
    fed_status = "🟢 飽腹"
    if info["last_fed"]:
        fed_seconds_left = (72 * 3600) - (now - datetime.fromisoformat(info["last_fed"])).total_seconds()
        if fed_seconds_left <= 0:
            fed_text = "🚨 **已進入瀕死挨餓狀態！請立馬買糧！**"
        else:
            fd_days = int(fed_seconds_left // 86400)
            fd_hours = int((fed_seconds_left % 86400) // 3600)
            fed_text = f"`{fd_days} 天 {fd_hours} 小時`"
            if fd_days < 1: fed_status = "🟡 飢餓"
    else:
        fed_text = "❓ 未知 (請盡快餵食一次)"

    # 2. 計算清潔剩餘時間 (7天 = 168小時)
    clean_status = "🟢 健康"
    if info["last_clean"]:
        clean_seconds_left = (168 * 3600) - (now - datetime.fromisoformat(info["last_clean"])).total_seconds()
        if clean_seconds_left <= 0:
            clean_text = "🚨 **環境極度惡劣！隨時生病致死！**"
        else:
            cl_days = int(clean_seconds_left // 86400)
            cl_hours = int((clean_seconds_left % 86400) // 3600)
            clean_text = f"`{cl_days} 天 {cl_hours} 小時`"
            if cl_days < 2: clean_status = "🔴 虛弱"
    else:
        clean_text = "❓ 未知 (請盡快清潔一次)"

    status_text = f"📊 <b>【愛鼠生理健康狀態報告】</b> 📊\n" + "‾" * 25 + f"\n"
    status_text += f"🐹 愛鼠名字：<b>{info['horse_name']}</b>\n"
    status_text += f"📊 當前狀態：【 {fed_status} | {clean_status} 】\n\n"
    status_text += f"🌾 <b>距離飢餓離世還剩</b>：\n └ {fed_text} <i>(滿值 3 天)</i>\n"
    status_text += f"🧹 <b>距離髒亂病逝還剩</b>：\n └ {clean_text} <i>(滿值 7 天)</i>\n\n"
    status_text += f"💡 <i>提示：快到期時請私訊機器人使用 <code>/buy 2</code> 或 <code>/buy 3</code> 補滿狀態！</i>"

    bot.reply_to(message, status_text, parse_mode='HTML')

# ================== 其他輔助功能 ==================
@bot.message_handler(commands=['rename'])
def rename_horse(message):
    if message.chat.type != "private": return
    user_id = message.from_user.id
    horse_info = get_user_horse(user_id)
    if horse_info["has_horse"] == 0: return
    cmd = message.text.split(maxsplit=1)
    if len(cmd) < 2: return
    new_name = cmd[1].strip()
    if len(new_name) < 1 or len(new_name) > 15: return
    with db_lock:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("UPDATE users SET horse_name=? WHERE user_id=?", (new_name, user_id))
            conn.commit()
    bot.reply_to(message, f"✨ 愛鼠已更名為：**「{new_name}」** 🐿️")

@bot.message_handler(commands=['start'])
def start(message):
    sync_username(message.from_user.id, message.from_user.username)
    bot.reply_to(message, f"🐿️ **虛擬賽鼠 Bot 已就緒**\n輸入 /help 查看完整指令列表。")

@bot.message_handler(commands=['help'])
def help_cmd(message):
    """【指令整合】加入數字快捷說明與新手飼養手冊"""
    text = f"""🐿️ <b>【虛擬賽鼠會 - 指令與飼養手冊】</b> 🐿️
‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾
🏁 <b>常用指令：</b>
  • <code>/startrun</code>  - 開始新一場賽事
  • <code>/money</code>    - 查詢目前錢包金幣餘額 💰
  • <code>/myhamster</code> - 查看專屬愛鼠生理健康與剩餘存活天數 🐹
  • <code>/refund</code>    - 開賽前退款當局投注
  • <code>/daily</code>     - 領取每日福利 (+3000 金幣)
  • <code>/rk</code>        - 查看賽鼠官方勝負戰績風雲榜 📊
  • <code>/pay</code>       - <b>【回覆訊息】</b>轉讓金幣給其他玩家

🛒 <b>商店養成功能（必須【私訊】機器人使用）：</b>
  • <code>/buy</code>         - 打開商店中心目錄（內附直接點擊購買按鈕）
  • <code>/buy 1 鼠名</code>  - 購買新賽鼠新秀 ($3,000) <i>(亦可輸入 /buy hamster)</i>
  • <code>/buy 2</code>       - 購買高級鼠糧 ($300) ➡️ 補滿3天餓死線 <i>(亦可輸入 /buy food)</i>
  • <code>/buy 3</code>       - 購買籠子清潔 ($500) ➡️ 補滿7天病死線 <i>(亦可輸入 /buy clean)</i>
  • <code>/rename</code>    - 修改愛鼠的名字
  • <code>/rainbow</code>   - 查看全服愛鼠彩虹橋紀念碑 🌈

🎲 <b>投注方式：</b>
  • 獨贏：<code>/win 號碼 金額</code> | 位置：<code>/pla 號碼 金額</code> | 連贏：<code>/ww 號碼1 號碼2 金額</code>

—" * 15 + """
📕 <b>【新手飼養鼠隻指南】</b> ⚠️
1️⃣ 連續 <b>3 天</b>沒有餵食（購買 <code>/buy 2</code>），愛鼠會<b>餓死</b>並送往彩虹橋。
2️⃣ 連續 <b>7 天</b>沒有清理籠子（購買 <code>/buy 3</code>），愛鼠會<b>病死</b>並送往彩虹橋。
3️⃣ 請定期使用 <code>/myhamster</code> 進行健康檢查，隨時保持滿腹與乾淨！
"""
    bot.reply_to(message, text, parse_mode='HTML')

# ================== 啟動服務 ==================
print(f"🐿️ {BOT_USERNAME} 【數字捷徑與按鈕優化版】啟動！")
bot.infinity_polling(timeout=20, long_polling_timeout=10)
