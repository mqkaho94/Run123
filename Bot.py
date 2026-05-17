import telebot
import random
import time
import threading
import sqlite3
import os
from datetime import date

TOKEN = os.getenv("7742431712:AAHBx-YjOKHNK6Pq_bDkj7nOOnxEejE_Xo8")

bot = telebot.TeleBot(TOKEN)

HORSES = ["⚡閃電", "🌪黑旋風", "⭐幸運星", "🔥火麒麟", "💨疾風", "🏅黃金戰馬"]

# 資料庫
conn = sqlite3.connect('race.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                chips INTEGER DEFAULT 1000,
                last_daily TEXT)''')
conn.commit()

def get_user(user_id, username):
    c.execute("SELECT chips FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    if not row:
        c.execute("INSERT INTO users (user_id, username, chips) VALUES (?, ?, 1000)", (user_id, username))
        conn.commit()
        return 1000
    return row[0]

def update_chips(user_id, amount):
    c.execute("UPDATE users SET chips = chips + ? WHERE user_id=?", (amount, user_id))
    conn.commit()

def get_leaderboard():
    c.execute("SELECT username, chips FROM users ORDER BY chips DESC LIMIT 10")
    return c.fetchall()

current_race = None
race_bets = {}

@bot.message_handler(commands=['start'])
def start(message):
    chips = get_user(message.from_user.id, message.from_user.first_name)
    bot.reply_to(message, f"🏇 **@Run1234567bot 虛擬賽馬**\n\n你的籌碼：**{chips}** chips\n\n/race 開賽\n/daily 簽到\n/balance 查籌碼\n/leaderboard 排行榜", parse_mode='Markdown')

@bot.message_handler(commands=['daily'])
def daily(message):
    user_id = message.from_user.id
    today = date.today().isoformat()
    c.execute("SELECT last_daily FROM users WHERE user_id=?", (user_id,))
    last = c.fetchone()
    if last and last[0] == today:
        bot.reply_to(message, "❌ 今天已領取過每日獎勵！")
        return
    update_chips(user_id, 500)
    c.execute("UPDATE users SET last_daily=? WHERE user_id=?", (today, user_id))
    conn.commit()
    bot.reply_to(message, "✅ 每日簽到成功！+500 chips")

@bot.message_handler(commands=['balance'])
def balance(message):
    chips = get_user(message.from_user.id, message.from_user.first_name)
    bot.reply_to(message, f"💰 你的籌碼：**{chips}** chips", parse_mode='Markdown')

@bot.message_handler(commands=['leaderboard'])
def leaderboard(message):
    board = get_leaderboard()
    text = "🏆 **排行榜** 🏆\n\n"
    for i, (name, chips) in enumerate(board, 1):
        text += f"{i}. {name} — **{chips}** chips\n"
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['race'])
def start_race(message):
    global current_race
    if current_race:
        bot.reply_to(message, "已有賽事進行中...")
        return
    current_race = time.time()
    race_bets.clear()
    text = "🏇 新賽事開始！30秒後開跑\n\n" + "\n".join([f"• {h}" for h in HORSES]) + "\n\n下注：/bet 馬名 金額"
    bot.reply_to(message, text)
    threading.Timer(30, run_race, [message.chat.id]).start()

def run_race(chat_id):
    global current_race
    bot.send_message(chat_id, "🏁 賽馬開跑！")
    time.sleep(3.5)
    finish = HORSES[:]
    random.shuffle(finish)
    winner = finish[0]
    result = "🏆 賽果：\n" + "\n".join([f"{i+1}. {h}" for i, h in enumerate(finish)])
    bot.send_message(chat_id, result)
    if current_race in race_bets:
        for uid, (horse, amt) in race_bets[current_race].items():
            if horse == winner:
                update_chips(uid, amt * 3)
                bot.send_message(chat_id, f"🎉 有人贏得 {amt*3} chips！")
    current_race = None

@bot.message_handler(commands=['bet'])
def bet(message):
    global current_race
    if not current_race:
        bot.reply_to(message, "請先 /race 開賽")
        return
    try:
        _, horse, amt = message.text.split()
        amt = int(amt)
        if horse not in HORSES:
            bot.reply_to(message, "馬名錯誤")
            return
        chips = get_user(message.from_user.id, message.from_user.first_name)
        if chips < amt:
            bot.reply_to(message, "籌碼不足")
            return
        update_chips(message.from_user.id, -amt)
        if current_race not in race_bets:
            race_bets[current_race] = {}
        race_bets[current_race][message.from_user.id] = (horse, amt)
        bot.reply_to(message, f"✅ 下注成功 {horse} {amt} chips")
    except:
        bot.reply_to(message, "格式錯誤：/bet 馬名 金額")

print("Bot 運行中...")
bot.infinity_polling()
