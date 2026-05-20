from flask import Flask
import threading
import os

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    # Render 會自動給予一個 PORT 環境變數
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

# 在背景啟動網頁伺服器，防止 Render 因為沒有 Port 監聽而部署失敗
threading.Thread(target=run_flask, daemon=True).start()

# 這裡緊接著執行你原本的賽鼠機器人程式碼
if __name__ == "__main__":
    from BOT import bot  # 假設你的主程式檔名叫 BOT.py
    print("🚀 賽鼠機器人已在背景啟動...")
    bot.infinity_polling(timeout=20, long_polling_timeout=10)
