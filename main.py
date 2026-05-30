import logging
import sqlite3
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from flask import Flask
from threading import Thread
import requests
import time
import random

# ===== ВЕБ-СЕРВЕР =====
flask_app = Flask('')

@flask_app.route('/')
def home():
    return "CryptoBank работает!"

Thread(target=lambda: flask_app.run(host='0.0.0.0', port=8080)).start()

# ===== НАСТРОЙКИ =====
TOKEN = "ВСТАВЬ_СВОЙ_TOKEN"
OWNER_ID = 7845037971

# ===== БАЗА ДАННЫХ =====
def init_db():
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        balance REAL DEFAULT 0,
        account_number TEXT,
        registered INTEGER DEFAULT 0,
        reg_date TEXT,
        daily_limit REAL DEFAULT 100000,
        limit_enabled INTEGER DEFAULT 1
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS admins (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        added_date TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT,
        amount REAL,
        date TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS savings (
        user_id INTEGER PRIMARY KEY,
        balance REAL DEFAULT 0,
        created_date TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS loans (
        user_id INTEGER PRIMARY KEY,
        amount REAL DEFAULT 0,
        taken_date TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS wallets (
        user_id INTEGER,
        coin TEXT,
        amount REAL DEFAULT 0,
        avg_price REAL DEFAULT 0,
        PRIMARY KEY (user_id, coin)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS cards (
        user_id INTEGER PRIMARY KEY,
        card_number TEXT,
        card_type TEXT,
        created_date TEXT,
        frozen INTEGER DEFAULT 0
    )''')
    conn.commit()
    conn.close()

def is_owner(user_id):
    return user_id == OWNER_ID

def is_admin(user_id):
    if is_owner(user_id):
        return True
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('SELECT user_id FROM admins WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    return row is not None

def get_user(user_id, username="", first_name=""):
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = c.fetchone()
    if not user:
        account = f"CR{user_id}"[-10:]
        c.execute('''INSERT INTO users 
            (user_id, username, first_name, balance, account_number, registered) 
            VALUES (?, ?, ?, ?, ?, ?)''',
            (user_id, username, first_name, 0, account, 0))
        conn.commit()
        c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = c.fetchone()
    conn.close()
    return user

def get_balance(user_id):
    if is_owner(user_id):
        return float('inf')
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def add_history(user_id, action, amount):
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('INSERT INTO history (user_id, action, amount, date) VALUES (?, ?, ?, ?)',
              (user_id, action, amount, datetime.now().strftime('%d.%m.%Y %H:%M')))
    conn.commit()
    conn.close()

def get_crypto_rates():
    try:
        r = requests.get(
            'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana,dogecoin&vs_currencies=rub',
            timeout=5
        )
        data = r.json()
        return {
            'BTC': data['bitcoin']['rub'],
            'ETH': data['ethereum']['rub'],
            'SOL': data['solana']['rub'],
            'DOGE': data['dogecoin']['rub']
        }
    except:
        return {'BTC': 8500000, 'ETH': 320000, 'SOL': 12000, 'DOGE': 12}

# ===== ОСНОВНЫЕ КОМАНДЫ =====

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "", user.first_name or "")
    await update.message.reply_text(
        f"🏦 Добро пожаловать в *CryptoBank*, {user.first_name}!\n\n"
        "💳 *Основные:*\n"
        "• /balance — баланс\n"
        "• /details — реквизиты\n"
        "• /history — история\n"
        "• /register — официальный статус\n\n"
        "📤 *Операции:*\n"
        "• /withdraw <сумма>\n"
        "• /send @user <сумма>\n\n"
        "💳 *Карта:*\n"
        "• /card — моя карта\n"
        "• /card freeze — заморозить\n"
        "• /card unfreeze — разморозить\n\n"
        "🏦 *Продукты:*\n"
        "• /savings — вклад 5%/год\n"
        "• /loan — кредит 15%/год\n"
        "• /limits — лимиты\n\n"
        "📊 *Крипто:*\n"
        "• /rates — курсы\n"
        "• /wallet — кошелёк\n"
        "• /buy BTC 10000\n"
        "• /sell ETH 0.5\n\n"
        "🎰 *Развлечения:*\n"
        "• /roulette <сумма> — рулетка\n"
        "• /slots <сумма> — слоты\n"
        "• /dice <сумма> — кости\n\n"
        "🏆 *Рейтинг:*\n"
        "• /top — топ богачей\n"
        "• /stats — статистика банка",
        parse_mode='Markdown'
    )

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "", user.first_name or "")
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('SELECT registered FROM users WHERE user_id = ?', (user.id,))
    row = c.fetchone()
    if row and row[0] == 1:
        await update.message.reply_text("✅ Ты уже зарегистрирован!")
        conn.close()
        return
    c.execute('UPDATE users SET registered = 1, reg_date = ? WHERE user_id = ?',
              (datetime.now().strftime('%d.%m.%Y'), user.id))
    conn.commit()
    conn.close()
    await update.message.reply_text(
        f"✅ *Официальный счёт открыт!*\n\n"
        f"👤 {user.first_name}\n"
        f"📅 {datetime.now().strftime('%d.%m.%Y')}\n\n"
        f"Добро пожаловать в CryptoBank! 🏦",
        parse_mode='Markdown'
    )

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "", user.first_name or "")
    bal = get_balance(user.id)
    bal_str = "∞" if bal == float('inf') else f"{bal:,.2f} ₽"
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('SELECT balance FROM savings WHERE user_id = ?', (user.id,))
    sav = c.fetchone()
    c.execute('SELECT amount FROM loans WHERE user_id = ?', (user.id,))
    loan_row = c.fetchone()
    conn.close()
    sav_bal = sav[0] if sav else 0
    loan_debt = loan_row[0] if loan_row else 0
    await update.message.reply_text(
        f"💳 *Баланс счёта*\n\n"
        f"💰 Основной: {bal_str}\n"
        f"🏦 Вклад: {sav_bal:,.2f} ₽\n"
        f"💸 Долг по кредиту: {loan_debt:,.2f} ₽",
        parse_mode='Markdown'
    )

async def details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    u = get_user(user.id, user.username or "", user.first_name or "")
    bal = get_balance(user.id)
    bal_str = "∞" if bal == float('inf') else f"{bal:,.2f} ₽"
    role = "👑 Владелец" if is_owner(user.id) else ("🛡 Администратор" if is_admin(user.id) else "👤 Клиент")
    reg_status = "✅ Зарегистрирован" if u[5] == 1 else "📋 Не зарегистрирован"
    await update.message.reply_text(
        f"📋 *Реквизиты счёта*\n\n"
        f"👤 Имя: {user.first_name}\n"
        f"🔢 Счёт: `{u[4]}`\n"
        f"💰 Баланс: {bal_str}\n"
        f"🎭 Роль: {role}\n"
        f"📋 Статус: {reg_status}",
        parse_mode='Markdown'
    )

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "", user.first_name or "")
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('SELECT action, amount, date FROM history WHERE user_id = ? ORDER BY id DESC LIMIT 10', (user.id,))
    rows = c.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("📭 История пуста")
        return
    text = "📊 *Последние транзакции:*\n\n"
    for r in rows:
        text += f"• {r[0]} — {r[1]:,.2f} ₽ ({r[2]})\n"
    await update.message.reply_text(text, parse_mode='Markdown')

async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "", user.first_name or "")
    if not context.args:
        await update.message.reply_text("❌ Укажи сумму: /withdraw 1000")
        return
    try:
        amount = float(context.args[0])
        if amount <= 0:
            raise ValueError
    except:
        await update.message.reply_text("❌ Неверная сумма")
        return
    bal = get_balance(user.id)
    if bal != float('inf') and bal < amount:
        await update.message.reply_text("❌ Недостаточно средств")
        return
    if not is_owner(user.id):
        conn = sqlite3.connect('bank.db')
        c = conn.cursor()
        c.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (amount, user.id))
        conn.commit()
        conn.close()
    add_history(user.id, "Снятие", amount)
    await update.message.reply_text(f"✅ Снято *{amount:,.2f} ₽*", parse_mode='Markdown')

async def send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "", user.first_name or "")
    if len(context.args) < 2:
        await update.message.reply_text("❌ Формат: /send @user 1000")
        return
    try:
        amount = float(context.args[1])
        if amount <= 0:
            raise ValueError
    except:
        await update.message.reply_text("❌ Неверная сумма")
        return
    target_username = context.args[0].replace('@', '')
    bal = get_balance(user.id)
    if bal != float('inf') and bal < amount:
        await update.message.reply_text("❌ Недостаточно средств")
        return
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('SELECT user_id FROM users WHERE username = ?', (target_username,))
    target = c.fetchone()
    if not target:
        conn.close()
        await update.message.reply_text("❌ Пользователь не найден. Он должен написать /start боту.")
        return
    if not is_owner(user.id):
        c.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (amount, user.id))
    c.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, target[0]))
    conn.commit()
    conn.close()
    add_history(user.id, f"Перевод → @{target_username}", amount)
    add_history(target[0], f"Получено от @{user.username}", amount)
    await update.message.reply_text(f"✅ Отправлено *{amount:,.2f} ₽* → @{target_username}", parse_mode='Markdown')

# ===== КАРТА =====

async def card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "", user.first_name or "")
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('SELECT * FROM cards WHERE user_id = ?', (user.id,))
    row = c.fetchone()

    if context.args and context.args[0] == 'freeze':
        if not row:
            await update.message.reply_text("❌ У тебя нет карты. Напиши /card чтобы получить.")
            conn.close()
            return
        c.execute('UPDATE cards SET frozen = 1 WHERE user_id = ?', (user.id,))
        conn.commit()
        conn.close()
        await update.message.reply_text("🧊 Карта *заморожена*", parse_mode='Markdown')
        return

    if context.args and context.args[0] == 'unfreeze':
        if not row:
            await update.message.reply_text("❌ У тебя нет карты.")
            conn.close()
            return
        c.execute('UPDATE cards SET frozen = 0 WHERE user_id = ?', (user.id,))
        conn.commit()
        conn.close()
        await update.message.reply_text("✅ Карта *разморожена*", parse_mode='Markdown')
        return

    if not row:
        card_num = ' '.join([''.join([str(random.randint(0,9)) for _ in range(4)]) for _ in range(4)])
        card_type = random.choice(['VISA', 'MasterCard'])
        c.execute('INSERT INTO cards VALUES (?, ?, ?, ?, ?)',
                  (user.id, card_num, card_type, datetime.now().strftime('%d.%m.%Y'), 0))
        conn.commit()
        c.execute('SELECT * FROM cards WHERE user_id = ?', (user.id,))
        row = c.fetchone()

    conn.close()
    status = "🧊 Заморожена" if row[4] == 1 else "✅ Активна"
    await update.message.reply_text(
        f"💳 *Моя карта*\n\n"
        f"🏦 {row[2]}\n"
        f"🔢 `{row[1]}`\n"
        f"📅 Выдана: {row[3]}\n"
        f"🔘 Статус: {status}\n\n"
        f"• /card freeze — заморозить\n"
        f"• /card unfreeze — разморозить",
        parse_mode='Markdown'
    )

# ===== ВКЛАД =====

async def savings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "", user.first_name or "")
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('SELECT balance, created_date FROM savings WHERE user_id = ?', (user.id,))
    row = c.fetchone()
    if context.args and context.args[0] == 'deposit':
        try:
            amount = float(context.args[1])
        except:
            await update.message.reply_text("❌ Формат: /savings deposit 1000")
            conn.close()
            return
        bal = get_balance(user.id)
        if bal != float('inf') and bal < amount:
            await update.message.reply_text("❌ Недостаточно средств")
            conn.close()
            return
        if not is_owner(user.id):
            c.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (amount, user.id))
        if row:
            c.execute('UPDATE savings SET balance = balance + ? WHERE user_id = ?', (amount, user.id))
        else:
            c.execute('INSERT INTO savings VALUES (?, ?, ?)',
                      (user.id, amount, datetime.now().strftime('%d.%m.%Y')))
        conn.commit()
        conn.close()
        add_history(user.id, "Вклад — пополнение", amount)
        await update.message.reply_text(f"✅ На вклад добавлено *{amount:,.2f} ₽*", parse_mode='Markdown')
    elif context.args and context.args[0] == 'withdraw':
        try:
            amount = float(context.args[1])
        except:
            await update.message.reply_text("❌ Формат: /savings withdraw 1000")
            conn.close()
            return
        if not row or row[0] < amount:
            await update.message.reply_text("❌ Недостаточно на вкладе")
            conn.close()
            return
        c.execute('UPDATE savings SET balance = balance - ? WHERE user_id = ?', (amount, user.id))
        c.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user.id))
        conn.commit()
        conn.close()
        add_history(user.id, "Вклад — снятие", amount)
        await update.message.reply_text(f"✅ Со вклада снято *{amount:,.2f} ₽*", parse_mode='Markdown')
    else:
        bal = row[0] if row else 0
        conn.close()
        await update.message.reply_text(
            f"🏦 *Накопительный вклад*\n\n"
            f"💰 Баланс: {bal:,.2f} ₽\n"
            f"📈 Ставка: 5%/год\n\n"
            f"• /savings deposit <сумма>\n"
            f"• /savings withdraw <сумма>",
            parse_mode='Markdown'
        )

# ===== КРЕДИТ =====

async def loan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "", user.first_name or "")
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('SELECT amount, taken_date FROM loans WHERE user_id = ?', (user.id,))
    row = c.fetchone()
    if context.args and context.args[0] == 'take':
        try:
            amount = float(context.args[1])
            if amount > 5000000:
                await update.message.reply_text("❌ Максимум 5 000 000 ₽")
                conn.close()
                return
        except:
            await update.message.reply_text("❌ Формат: /loan take 100000")
            conn.close()
            return
        if row and row[0] > 0:
            await update.message.reply_text("❌ У тебя уже есть кредит. Сначала погаси его.")
            conn.close()
            return
        c.execute('INSERT OR REPLACE INTO loans VALUES (?, ?, ?)',
                  (user.id, amount, datetime.now().strftime('%d.%m.%Y')))
        c.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user.id))
        conn.commit()
        conn.close()
        add_history(user.id, "Кредит получен", amount)
        await update.message.reply_text(
            f"✅ Кредит *{amount:,.2f} ₽* выдан!\nПогасить: /loan repay <сумма>",
            parse_mode='Markdown'
        )
    elif context.args and context.args[0] == 'repay':
        try:
            amount = float(context.args[1])
        except:
            await update.message.reply_text("❌ Формат: /loan repay 10000")
            conn.close()
            return
        if not row or row[0] <= 0:
            await update.message.reply_text("❌ У тебя нет кредита")
            conn.close()
            return
        bal = get_balance(user.id)
        if bal != float('inf') and bal < amount:
            await update.message.reply_text("❌ Недостаточно средств")
            conn.close()
            return
        new_loan = max(0, row[0] - amount)
        if not is_owner(user.id):
            c.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (amount, user.id))
        c.execute('UPDATE loans SET amount = ? WHERE user_id = ?', (new_loan, user.id))
        conn.commit()
        conn.close()
        add_history(user.id, "Погашение кредита", amount)
        await update.message.reply_text(
            f"✅ Погашено *{amount:,.2f} ₽*\nОсталось: {new_loan:,.2f} ₽",
            parse_mode='Markdown'
        )
    else:
        debt = row[0] if row else 0
        conn.close()
        await update.message.reply_text(
            f"💳 *Кредит*\n\n"
            f"💸 Долг: {debt:,.2f} ₽\n"
            f"📈 Ставка: 15%/год\n"
            f"🔢 Лимит: 5 000 000 ₽\n\n"
            f"• /loan take <сумма>\n"
            f"• /loan repay <сумма>",
            parse_mode='Markdown'
        )

# ===== ЛИМИТЫ =====

async def limits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "", user.first_name or "")
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    if context.args and context.args[0] == 'set':
        try:
            amount = float(context.args[1])
        except:
            await update.message.reply_text("❌ Формат: /limits set 50000")
            conn.close()
            return
        c.execute('UPDATE users SET daily_limit = ?, limit_enabled = 1 WHERE user_id = ?', (amount, user.id))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ Лимит: *{amount:,.2f} ₽/день*", parse_mode='Markdown')
    elif context.args and context.args[0] == 'off':
        c.execute('UPDATE users SET limit_enabled = 0 WHERE user_id = ?', (user.id,))
        conn.commit()
        conn.close()
        await update.message.reply_text("✅ Лимит отключён")
    else:
        c.execute('SELECT daily_limit, limit_enabled FROM users WHERE user_id = ?', (user.id,))
        row = c.fetchone()
        conn.close()
        status = "включён" if row and row[1] else "отключён"
        lim = row[0] if row else 100000
        await update.message.reply_text(
            f"⚙️ *Лимиты*\n\n"
            f"📊 Дневной: {lim:,.2f} ₽\n"
            f"🔘 Статус: {status}\n\n"
            f"• /limits set <сумма>\n"
            f"• /limits off",
            parse_mode='Markdown'
        )

# ===== КРИПТО =====

async def rates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Получаю курсы...")
    r = get_crypto_rates()
    await update.message.reply_text(
        f"📊 *Курсы криптовалют (₽)*\n\n"
        f"₿ BTC: {r['BTC']:,.0f} ₽\n"
        f"Ξ ETH: {r['ETH']:,.0f} ₽\n"
        f"◎ SOL: {r['SOL']:,.0f} ₽\n"
        f"Ð DOGE: {r['DOGE']:,.2f} ₽",
        parse_mode='Markdown'
    )

async def wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "", user.first_name or "")
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('SELECT coin, amount, avg_price FROM wallets WHERE user_id = ?', (user.id,))
    rows = c.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("👛 Кошелёк пуст\nКупи крипту: /buy BTC 10000")
        return
    r = get_crypto_rates()
    text = "👛 *Кошелёк*\n\n"
    for coin, amount, avg_price in rows:
        if amount > 0 and coin in r:
            current = r[coin]
            value = amount * current
            pl = (current - avg_price) * amount
            pl_str = f"+{pl:,.0f}" if pl >= 0 else f"{pl:,.0f}"
            text += f"*{coin}*: {amount:.6f} = {value:,.0f} ₽ (P&L: {pl_str} ₽)\n"
    await update.message.reply_text(text, parse_mode='Markdown')

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "", user.first_name or "")
    if len(context.args) < 2:
        await update.message.reply_text("❌ Формат: /buy BTC 10000")
        return
    coin = context.args[0].upper()
    try:
        rub_amount = float(context.args[1])
    except:
        await update.message.reply_text("❌ Неверная сумма")
        return
    r = get_crypto_rates()
    if coin not in r:
        await update.message.reply_text("❌ Доступно: BTC ETH SOL DOGE")
        return
    bal = get_balance(user.id)
    if bal != float('inf') and bal < rub_amount:
        await update.message.reply_text("❌ Недостаточно средств")
        return
    price = r[coin]
    coin_amount = rub_amount / price
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    if not is_owner(user.id):
        c.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (rub_amount, user.id))
    c.execute('SELECT amount, avg_price FROM wallets WHERE user_id = ? AND coin = ?', (user.id, coin))
    existing = c.fetchone()
    if existing:
        new_amount = existing[0] + coin_amount
        new_avg = ((existing[0] * existing[1]) + rub_amount) / new_amount
        c.execute('UPDATE wallets SET amount = ?, avg_price = ? WHERE user_id = ? AND coin = ?',
                  (new_amount, new_avg, user.id, coin))
    else:
        c.execute('INSERT INTO wallets VALUES (?, ?, ?, ?)', (user.id, coin, coin_amount, price))
    conn.commit()
    conn.close()
    add_history(user.id, f"Покупка {coin}", rub_amount)
    await update.message.reply_text(
        f"✅ Куплено *{coin_amount:.6f} {coin}*\n"
        f"💸 Потрачено: {rub_amount:,.0f} ₽\n"
        f"💲 Цена: {price:,.0f} ₽/{coin}",
        parse_mode='Markdown'
    )

async def sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "", user.first_name or "")
    if len(context.args) < 2:
        await update.message.reply_text("❌ Формат: /sell BTC 0.001")
        return
    coin = context.args[0].upper()
    try:
        coin_amount = float(context.args[1])
    except:
        await update.message.reply_text("❌ Неверная сумма")
        return
    r = get_crypto_rates()
    if coin not in r:
        await update.message.reply_text("❌ Доступно: BTC ETH SOL DOGE")
        return
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('SELECT amount, avg_price FROM wallets WHERE user_id = ? AND coin = ?', (user.id, coin))
    existing = c.fetchone()
    if not existing or existing[0] < coin_amount:
        await update.message.reply_text("❌ Недостаточно монет")
        conn.close()
        return
    price = r[coin]
    rub_amount = coin_amount * price
    new_amount = existing[0] - coin_amount
    c.execute('UPDATE wallets SET amount = ? WHERE user_id = ? AND coin = ?', (new_amount, user.id, coin))
    c.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (rub_amount, user.id))
    conn.commit()
    conn.close()
    add_history(user.id, f"Продажа {coin}", rub_amount)
    pl = (price - existing[1]) * coin_amount
    pl_str = f"+{pl:,.0f}" if pl >= 0 else f"{pl:,.0f}"
    await update.message.reply_text(
        f"✅ Продано *{coin_amount:.6f} {coin}*\n"
        f"💰 Получено: {rub_amount:,.0f} ₽\n"
        f"📊 P&L: {pl_str} ₽",
        parse_mode='Markdown'
    )

# ===== ИГРЫ =====

async def roulette(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "", user.first_name or "")
    if not context.args:
        await update.message.reply_text("❌ Формат: /roulette 1000")
        return
    try:
        amount = float(context.args[0])
        if amount <= 0:
            raise ValueError
    except:
        await update.message.reply_text("❌ Неверная сумма")
        return
    bal = get_balance(user.id)
    if bal != float('inf') and bal < amount:
        await update.message.reply_text("❌ Недостаточно средств")
        return
    result = random.randint(0, 36)
    colors = {0: "🟢"}
    for i in range(1, 37):
        colors[i] = "🔴" if i % 2 == 1 else "⚫"
    color = colors[result]
    win = result != 0 and random.random() > 0.48
    if win:
        winnings = amount * 2
        if not is_owner(user.id):
            conn = sqlite3.connect('bank.db')
            c = conn.cursor()
            c.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user.id))
            conn.commit()
            conn.close()
        add_history(user.id, "Рулетка — выигрыш", winnings)
        await update.message.reply_text(
            f"🎰 *Рулетка*\n\n"
            f"Выпало: {color} *{result}*\n\n"
            f"🎉 Выигрыш! +{amount:,.2f} ₽",
            parse_mode='Markdown'
        )
    else:
        if not is_owner(user.id):
            conn = sqlite3.connect('bank.db')
            c = conn.cursor()
            c.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (amount, user.id))
            conn.commit()
            conn.close()
        add_history(user.id, "Рулетка — проигрыш", amount)
        await update.message.reply_text(
            f"🎰 *Рулетка*\n\n"
            f"Выпало: {color} *{result}*\n\n"
            f"😢 Проигрыш! -{amount:,.2f} ₽",
            parse_mode='Markdown'
        )

async def slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "", user.first_name or "")
    if not context.args:
        await update.message.reply_text("❌ Формат: /slots 1000")
        return
    try:
        amount = float(context.args[0])
        if amount <= 0:
            raise ValueError
    except:
        await update.message.reply_text("❌ Неверная сумма")
        return
    bal = get_balance(user.id)
    if bal != float('inf') and bal < amount:
        await update.message.reply_text("❌ Недостаточно средств")
        return
    symbols = ['🍒', '🍋', '🍊', '⭐', '💎', '7️⃣']
    s1, s2, s3 = random.choice(symbols), random.choice(symbols), random.choice(symbols)
    if s1 == s2 == s3 == '💎':
        mult = 10
        result_text = "💎 ДЖЕКПОТ! x10"
    elif s1 == s2 == s3 == '7️⃣':
        mult = 7
        result_text = "7️⃣ СЕМЁРКИ! x7"
    elif s1 == s2 == s3:
        mult = 3
        result_text = "🎉 Три одинаковых! x3"
    elif s1 == s2 or s2 == s3:
        mult = 1.5
        result_text = "✨ Два одинаковых! x1.5"
    else:
        mult = 0
        result_text = "😢 Нет совпадений"
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    if mult > 0:
        winnings = amount * mult - amount
        if not is_owner(user.id):
            c.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (winnings, user.id))
        add_history(user.id, f"Слоты — выигрыш x{mult}", amount * mult)
        result_money = f"+{winnings:,.2f} ₽"
    else:
        if not is_owner(user.id):
            c.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (amount, user.id))
        add_history(user.id, "Слоты — проигрыш", amount)
        result_money = f"-{amount:,.2f} ₽"
    conn.commit()
    conn.close()
    await update.message.reply_text(
        f"🎰 *Слоты*\n\n"
        f"[ {s1} | {s2} | {s3} ]\n\n"
        f"{result_text}\n"
        f"{result_money}",
        parse_mode='Markdown'
    )

async def dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "", user.first_name or "")
    if not context.args:
        await update.message.reply_text("❌ Формат: /dice 1000")
        return
    try:
        amount = float(context.args[0])
        if amount <= 0:
            raise ValueError
    except:
        await update.message.reply_text("❌ Неверная сумма")
        return
    bal = get_balance(user.id)
    if bal != float('inf') and bal < amount:
        await update.message.reply_text("❌ Недостаточно средств")
        return
    player = random.randint(1, 6)
    bank = random.randint(1, 6)
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    if player > bank:
        if not is_owner(user.id):
            c.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user.id))
        add_history(user.id, "Кости — выигрыш", amount)
        result = f"🎉 Ты выиграл! +{amount:,.2f} ₽"
    elif player < bank:
        if not is_owner(user.id):
            c.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (amount, user.id))
        add_history(user.id, "Кости — проигрыш", amount)
        result = f"😢 Банк выиграл! -{amount:,.2f} ₽"
    else:
        result = "🤝 Ничья! Ставка возвращена"
    conn.commit()
    conn.close()
    await update.message.reply_text(
        f"🎲 *Кости против Банка*\n\n"
        f"Твой бросок: *{player}*\n"
        f"Бросок банка: *{bank}*\n\n"
        f"{result}",
        parse_mode='Markdown'
    )

# ===== ТОП И СТАТИСТИКА =====

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('SELECT username, first_name, balance FROM users ORDER BY balance DESC LIMIT 10')
    rows = c.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("📭 Список пуст")
        return
    medals = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']
    text = "🏆 *Топ богачей CryptoBank*\n\n"
    for i, (username, first_name, balance) in enumerate(rows):
        name = f"@{username}" if username else first_name or "Аноним"
        text += f"{medals[i]} {name} — {balance:,.2f} ₽\n"
    await update.message.reply_text(text, parse_mode='Markdown')

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM users')
    total_users = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM users WHERE registered = 1')
    reg_users = c.fetchone()[0]
    c.execute('SELECT SUM(balance) FROM users')
    total_money = c.fetchone()[0] or 0
    c.execute('SELECT COUNT(*) FROM history')
    total_tx = c.fetchone()[0]
    c.execute('SELECT SUM(amount) FROM loans WHERE amount > 0')
    total_loans = c.fetchone()[0] or 0
    conn.close()
    await update.message.reply_text(
        f"📊 *Статистика CryptoBank*\n\n"
        f"👥 Всего клиентов: {total_users}\n"
        f"✅ Зарегистрировано: {reg_users}\n"
        f"💰 Деньги в банке: {total_money:,.2f} ₽\n"
        f"📋 Транзакций: {total_tx}\n"
        f"💸 Выдано кредитов: {total_loans:,.2f} ₽",
        parse_mode='Markdown'
    )

# ===== АДМИН КОМАНДЫ =====

async def addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_owner(user.id):
        await update.message.reply_text("❌ Только владелец может добавлять администраторов")
        return
    if not context.args:
        await update.message.reply_text("❌ Формат: /addadmin @username")
        return
    target_username = context.args[0].replace('@', '')
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('SELECT user_id FROM users WHERE username = ?', (target_username,))
    target = c.fetchone()
    if not target:
        fake_id = abs(hash(target_username)) % 1000000000
        account = f"CR{fake_id}"[-10:]
        c.execute('INSERT OR IGNORE INTO users (user_id, username, first_name, balance, account_number, registered, reg_date) VALUES (?, ?, ?, ?, ?, ?, ?)',
                  (fake_id, target_username, target_username, 0, account, 1, datetime.now().strftime('%d.%m.%Y')))
        target = (fake_id,)
    c.execute('INSERT OR REPLACE INTO admins VALUES (?, ?, ?)',
              (target[0], target_username, datetime.now().strftime('%d.%m.%Y')))
    c.execute('UPDATE users SET registered = 1, reg_date = ? WHERE user_id = ?',
              (datetime.now().strftime('%d.%m.%Y'), target[0]))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ @{target_username} назначен администратором!")

async def removeadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_owner(user.id):
        await update.message.reply_text("❌ Только владелец может снимать администраторов")
        return
    if not context.args:
        await update.message.reply_text("❌ Формат: /removeadmin @username")
        return
    target_username = context.args[0].replace('@', '')
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('DELETE FROM admins WHERE username = ?', (target_username,))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ @{target_username} снят с должности")

async def admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('SELECT username, added_date FROM admins')
    rows = c.fetchall()
    conn.close()
    text = "🛡 *Администрация CryptoBank*\n\n"
    text += f"👑 Владелец: ID `{OWNER_ID}`\n\n"
    if rows:
        text += "🛡 *Администраторы:*\n"
        for username, date in rows:
            text += f"• @{username} (с {date})\n"
    else:
        text += "Администраторов пока нет"
    await update.message.reply_text(text, parse_mode='Markdown')

async def setbalance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("❌ Нет доступа")
        return
    if len(context.args) < 2:
        await update.message.reply_text("❌ Формат: /setbalance @username 10000")
        return
    target_username = context.args[0].replace('@', '')
    try:
        amount = float(context.args[1])
    except:
        await update.message.reply_text("❌ Неверная сумма")
        return
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('UPDATE users SET balance = ? WHERE username = ?', (amount, target_username))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ Баланс @{target_username} = {amount:,.2f} ₽")

# ===== ЗАПУСК =====
init_db()

while True:
    try:
        bot = ApplicationBuilder().token(TOKEN).build()
        bot.add_handler(CommandHandler("start", start))
        bot.add_handler(CommandHandler("register", register))
        bot.add_handler(CommandHandler("balance", balance))
        bot.add_handler(CommandHandler("details", details))
        bot.add_handler(CommandHandler("history", history))
        bot.add_handler(CommandHandler("withdraw", withdraw))
        bot.add_handler(CommandHandler("send", send))
        bot.add_handler(CommandHandler("card", card))
        bot.add_handler(CommandHandler("savings", savings))
        bot.add_handler(CommandHandler("loan", loan))
        bot.add_handler(CommandHandler("limits", limits))
        bot.add_handler(CommandHandler("rates", rates))
        bot.add_handler(CommandHandler("wallet", wallet))
        bot.add_handler(CommandHandler("buy", buy))
        bot.add_handler(CommandHandler("sell", sell))
        bot.add_handler(CommandHandler("roulette", roulette))
        bot.add_handler(CommandHandler("slots", slots))
        bot.add_handler(CommandHandler("dice", dice))
        bot.add_handler(CommandHandler("top", top))
        bot.add_handler(CommandHandler("stats", stats))
        bot.add_handler(CommandHandler("addadmin", addadmin))
        bot.add_handler(CommandHandler("removeadmin", removeadmin))
        bot.add_handler(CommandHandler("admins", admins))
        bot.add_handler(CommandHandler("setbalance", setbalance))
        bot.run_polling()
    except Exception as e:
        print(f"Ошибка: {e}")
        time.sleep(5)
