import telebot
import random
import time
import threading
import sqlite3
import os
import json
from datetime import date

# ================== 設定 ==================
TOKEN = "8999179825:AAGMP7VHxI75FniZG8KKv6XsJsuMfcSwudM"
BOT_USERNAME = "@gapjaibot"

bot = telebot.TeleBot(TOKEN, threaded=True, num_threads=4)

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "race.db")
HORSE_PRICE = 3000

daily_lock = threading.Lock()

# ================== 固定資料 ==================
BASE_NPC_HORSES = [
    ("奧雲狗狗", "⚡"), ("黑旋風", "🌪"), ("戰槌巨人", "⭐"), ("火麒麟", "🔥"), 
    ("疾風", "💨"), ("黃金戰鼠", "🏅"), ("海嘯", "🌊"), ("傲空", "🦅")
]

RANDOM_ANIMAL_EMOJIS = ["🦁", "🐼", "🦊", "🐭", "🐨", "🐯", "🐸", "🐷", "🐻", "🐰", "🐵", "🐔", "🐧", "🐦", "🦆", "🦅", "🦉", "🦇", "🐺", "🐗"]

BETTING_SURFACE_STATUSES = [
    "鼠神加持🤩高光時刻", "外星物種👽高深莫測", "科技外掛🤖液態金屬", "剛吃興奮劑💊眼神清澈", 
    "昨晚拜神🙏獲得神秘力量", "祖先托夢👑這局穩贏", "賽道车神🏎️自帶BGM", "氣勢如虹😤單眼單挑", 
    "氪金玩家💰全身發光", "不可一世😎王者風範",
    "天生扁平足🦶跑動困難", "沉迷股票📉痛失家產心慌慌", "剛剛小兒麻痺症發作🤒", "霉運當頭🌀烏雲蓋頂", 
    "體重超標🐷走路都喘氣", "出局邊緣🥀毫無鬥志", "四肢無力🥵缺乏維他命", "中暑邊緣☀️頭暈身熱", 
    "靈魂出竅👻呆若木雞", "忘記帶大腦🧠全憑本能"
]

# ================== 資料庫 ==================
def init_db():
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, chips INTEGER DEFAULT 1000,
            last_daily TEXT, has_horse INTEGER DEFAULT 0, horse_name TEXT,
            horse_first INTEGER DEFAULT 0, horse_second INTEGER DEFAULT 0,
            horse_third INTEGER DEFAULT 0, horse_losses INTEGER DEFAULT 0, last_luck_date TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS system_config (key TEXT PRIMARY KEY, value TEXT);''')
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

# ================== 保底機制 ==================
def get_system_race_count():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT value FROM system_config WHERE key='total_races'")
        row = c.fetchone()
        return int(row[0]) if row else 0

def increment_system_race_count():
    count = get_system_race_count() + 1
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("UPDATE system_config SET value=? WHERE key='total_races'", (str(count),))
        conn.commit()
    return count

def get_guarantee_plan():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT value FROM system_config WHERE key='guarantee_plan'")
        row = c.fetchone()
        if row and row[0]:
            return json.loads(row[0])
        g_races = random.sample(range(1, 11), 2)
        plan = {str(g_races[0]): random.choice([1, 2]), str(g_races[1]): random.choice([1, 2])}
        c.execute("INSERT OR REPLACE INTO system_config (key, value) VALUES ('guarantee_plan', ?)", (json.dumps(plan),))
        conn.commit()
        return plan

def refresh_guarantee_plan():
    g_races = random.sample(range(1, 11), 2)
    plan = {str(g_races[0]): random.choice([1, 2]), str(g_races[1]): random.choice([1, 2])}
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO system_config (key, value) VALUES ('guarantee_plan', ?)", (json.dumps(plan),))
        conn.commit()

# ================== 賽事狀態 ==================
race_states = {}

# ================== 開賽 ==================
@bot.message_handler(commands=['startrun'])
def startrun(message):
    chat_id = message.chat.id
    if chat_id in race_states and race_states[chat_id].get('status') in ['betting', 'running']:
        bot.reply_to(message, "⚠️ 本群已有賽事進行中！")
        return

    total_races = increment_system_race_count()
    cycle_index = total_races % 10 or 10
    guarantee_plan = get_guarantee_plan()
    is_guarantee = str(cycle_index) in guarantee_plan
    guarantee_count = guarantee_plan.get(str(cycle_index), 0)

    race_data = {'status': 'betting', 'horses': [], 'odds': {}, 'horse_statuses': {}, 'guaranteed_cold': []}
    race_states[chat_id] = race_data

    # 準備賽鼠
    final_8 = [(None, name, icon) for name, icon in BASE_NPC_HORSES]
    random.shuffle(final_8)
    current_horses = [f"{icon}{i+1}.{name}" for i, (_, name, icon) in enumerate(final_8)]
    race_data['horses'] = current_horses

    # 狀態與賠率
    statuses = BETTING_SURFACE_STATUSES.copy()
    random.shuffle(statuses)
    round_statuses = statuses[:8]
    cold_candidates = []

    for idx, h in enumerate(current_horses):
        surface = round_statuses[idx]
        is_cold = any(k in surface for k in ["小兒麻痺", "出局邊緣", "沉迷股票", "體重超標", "霉運當頭"])
        odds = round(random.uniform(13.0, 22.0) if is_cold else random.uniform(3.0, 8.5), 1)
        
        race_data['odds'][h] = odds
        race_data['horse_statuses'][h] = {"betting_text": surface, "is_cold": is_cold}
        if is_cold:
            cold_candidates.append(h)

    # 保底
    guaranteed = []
    if is_guarantee and cold_candidates:
        num = min(guarantee_count, len(cold_candidates))
        guaranteed = random.sample(cold_candidates, num)
        race_data['guaranteed_cold'] = guaranteed

    # 發送投注面板
    text = f"🏁 **賽鼠會 - 第 {total_races} 場** 🏁\n"
    if is_guarantee:
        text += f"✨ **冷門馬保底局**（保護 {guarantee_count} 隻）✨\n\n"
    
    animal_emojis = random.sample(RANDOM_ANIMAL_EMOJIS, 8)
    for i, h in enumerate(current_horses, 1):
        mark = " ✨[保底]" if h in guaranteed else ""
        text += f"{i} {h}{mark} {animal_emojis[i-1]}\n   獨贏: {race_data['odds'][h]}倍\n"

    text += "\n💰 下注：`/win 號碼 金額` | `/pla 號碼 金額` | `/ww 號碼1 號碼2 金額`"
    bot.reply_to(message, text, parse_mode='Markdown')

    threading.Timer(60, lambda: run_race(chat_id)).start()

    if cycle_index == 10:
        refresh_guarantee_plan()

# ================== 動態直播進度條 ==================
def run_race(chat_id):
    if chat_id not in race_states:
        return
    rd = race_states[chat_id]
    rd['status'] = 'running'

    horses = rd['horses'][:]
    distances = {h: 0.0 for h in horses}
    TOTAL = 100.0
    DISPLAY = 15

    # 發送直播訊息
    live_msg = bot.send_message(chat_id, "🏁 **賽鼠直播進行中...**")

    for _ in range(25):  # 模擬25秒比賽
        time.sleep(2)
        
        for h in horses:
            if distances[h] >= TOTAL:
                continue
            # 隨機推進
            step = random.uniform(3.0, 7.0)
            if random.random() < 0.15:      # 爆發
                step *= 1.8
            distances[h] += step
            if distances[h] > TOTAL:
                distances[h] = TOTAL

        # 建立直播文字
        text = "🐿️ **賽鼠直播進行中** 🏁\n" + "—" * 25 + "\n\n"
        
        sorted_horses = sorted(horses, key=lambda h: distances[h], reverse=True)
        
        for rank, h in enumerate(sorted_horses, 1):
            progress = int((distances[h] / TOTAL) * DISPLAY)
            bar = "🏁" + "█" * progress + "░" * (DISPLAY - progress) + "🐿️"
            status = "【衝線】" if distances[h] >= TOTAL else ""
            text += f"{rank}位 {h} {status}\n`{bar}`\n\n"

        try:
            bot.edit_message_text(text, chat_id, live_msg.message_id, parse_mode='Markdown')
        except:
            pass

    # 最終結果
    final_rank = sorted(horses, key=lambda h: distances[h], reverse=True)
    result = "🏆 **最終賽果** 🏆\n\n"
    for i, h in enumerate(final_rank, 1):
        medal = "🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else ""
        result += f"{medal} 第 {i} 名：{h}\n"

    bot.send_message(chat_id, result, parse_mode='Markdown')

    # 清理
    if chat_id in race_states:
        del race_states[chat_id]

# ================== 其他指令 ==================
@bot.message_handler(commands=['money'])
def money(message):
    chips = get_chips(message.from_user.id)
    bot.reply_to(message, f"💰 你的餘額：**{chips:,}** 金幣", parse_mode='Markdown')

@bot.message_handler(commands=['daily'])
def daily(message):
    user_id = message.from_user.id
    today = date.today().isoformat()
    with daily_lock:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute("SELECT last_daily FROM users WHERE user_id=?", (user_id,))
            last = c.fetchone()
            if last and last[0] == today:
                bot.reply_to(message, "❌ 你今天已經領過每日獎勵！")
                return
            c.execute("UPDATE users SET last_daily=? WHERE user_id=?", (today, user_id))
            conn.commit()
        update_chips(user_id, 3000)
        bot.reply_to(message, "✅ **每日簽到成功！** +3000 金幣 💰")

@bot.message_handler(commands=['help'])
def help_cmd(message):
    bot.reply_to(message, """🐿️ **賽鼠 Bot**
/startrun - 開始新賽事（含冷門保底）
/money - 查金幣
/daily - 每日簽到""", parse_mode='Markdown')

# ================== 啟動 ==================
init_db()
print(f"🐿️ {BOT_USERNAME} 【動態直播進度條 + 冷門保底】已成功啟動！")
bot.infinity_polling(timeout=20, long_polling_timeout=10)