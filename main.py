import os
import time
import threading
import subprocess
from flask import Flask

# Flask для Render
web = Flask(__name__)

@web.route("/")
def home():
    return "Bot is running!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    web.run(host="0.0.0.0", port=port)

# Запуск bank.py
def run_bank():
    subprocess.run(["python", "bank.py"])

# Запуск market.py
def run_market():
    subprocess.run(["python", "market.py"])

if __name__ == "__main__":
    # Запускаем веб-сервер для Render
    threading.Thread(target=run_web, daemon=True).start()

    # Запускаем ботов
    t1 = threading.Thread(target=run_bank)
    t2 = threading.Thread(target=run_market)

    t1.start()
    time.sleep(3)
    t2.start()

    t1.join()
    t2.join()