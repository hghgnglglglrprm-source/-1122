import sqlite3
import random
import requests
import os
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

TOKEN = os.environ.get("TOKEN", "8757614437:AAGHiuzebO3_lFvsPEfD5cLE3BOlFmobzW8")
OWNER_ID = 7845037971
TRANSFER_FEE = 0.05
PHOTO_CHAT_ID = None
SUPPORT_CHAT_ID = None

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
    c.execute('''CREATE TABLE IF NOT EXISTS owners (
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
        taken_date TEXT,
        loan_type TEXT DEFAULT 'standard'
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
    c.execute('''CREATE TABLE IF NOT EXISTS treasury (
        id INTEGER PRIMARY KEY,
        balance REAL DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS photos (
        file_unique_id TEXT PRIMARY KEY,
        user_id INTEGER,
        reward REAL,
        date TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS admin_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id INTEGER,
        action TEXT,
        target_id INTEGER,
        amount REAL,
        created_at TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS support_tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        text TEXT,
        status TEXT DEFAULT 'open',
        date TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS suggestions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        text TEXT,
        status TEXT DEFAULT 'new',
        date TEXT
    )''')
    c.execute('INSERT OR IGNORE INTO treasury VALUES (0, 0)')
    conn.commit()
    conn.close()

def is_owner(user_id):
    if user_id == OWNER_ID:
        return True
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('SELECT user_id FROM owners WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    return row is not None

def is_admin(user_id):
    if is_owner(user_id):
        return True
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('SELECT user_id FROM admins WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    return row is not None

def get_role(user_id):
    if user_id == OWNER_ID:
        return '👑 Главный владелец'
    if is_owner(user_id):
        return '👑 Владелец'
    if is_admin(user_id):
        return '🛡 Администратор'
    return '👤 Пользователь'

def log_action(admin_id, action, target_id=None, amount=None):
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('INSERT INTO admin_logs (admin_id, action, target_id, amount, created_at) VALUES (?, ?, ?, ?, ?)',
              (admin_id, action, target_id, amount, datetime.now().strftime('%d.%m.%Y %H:%M')))
    conn.commit()
    conn.close()

def get_user(user_id, username="", first_name=""):
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = c.fetchone()
    if not user:
        account = f"CR{user_id}"[-10:]
        c.execute('INSERT INTO users (user_id, username, first_name, balance, account_number, registered) VALUES (?, ?, ?, ?, ?, ?)',
                  (user_id, username, first_name, 0, account, 0))
        conn.commit()
        c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = c.fetchone()
    conn.close()
    return user

def get_balance(user_id):
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def add_money(user_id, amount):
    if amount <= 0:
        return False
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    conn.close()
    return True

def remove_money(user_id, amount):
    if amount <= 0:
        return False
    bal = get_balance(user_id)
    if bal < amount:
        return False
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    conn.close()
    return True

def add_history(user_id, action, amount):
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('INSERT INTO history (user_id, action, amount, date) VALUES (?, ?, ?, ?)',
              (user_id, action, amount, datetime.now().strftime('%d.%m.%Y %H:%M')))
    conn.commit()
    conn.close()

def get_treasury():
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('SELECT balance FROM treasury WHERE id = 0')
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def add_to_treasury(amount):
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('UPDATE treasury SET balance = balance + ? WHERE id = 0', (amount,))
    conn.commit()
    conn.close()

def is_card_frozen(user_id):
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('SELECT frozen FROM cards WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    return row and row[0] == 1

def get_crypto_rates():
    try:
        r = requests.get(
            'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana,dogecoin,the-open-network&vs_currencies=rub',
            timeout=5
        )
        data = r.json()
        return {
            'BTC': data['bitcoin']['rub'],
            'ETH': data['ethereum']['rub'],
            'SOL': data['solana']['rub'],
            'DOGE': data['dogecoin']['rub'],
            'TON': data['the-open-network']['rub']
        }
    except:
        return {'BTC': 8500000, 'ETH': 320000, 'SOL': 12000, 'DOGE': 12, 'TON': 450}

def find_user(arg):
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    if arg.isdigit():
        c.execute('SELECT user_id, username FROM users WHERE user_id = ?', (int(arg),))
    else:
        c.execute('SELECT user_id, username FROM users WHERE username = ?', (arg,))
    row = c.fetchone()
    conn.close()
    return row

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "", user.first_name or "")
    role = get_role(user.id)
    await update.message.reply_text(
        f"🏦 *CryptoBank V2*\n{role}\n\n"
        "💳 *Основные:*\n"
        "• /balance — баланс\n"
        "• /details — реквизиты\n"
        "• /history — история\n"
        "• /register — регистрация\n\n"
        "📤 *Операции:*\n"
        "• /send @user <сумма> (5%)\n\n"
        "💳 *Карта:*\n"
        "• /card — моя карта\n"
        "• /card freeze / unfreeze\n\n"
        "🏦 *Продукты:*\n"
        "• /savings — вклад 5%/год\n"
        "• /loan — кредит 15%\n"
        "• /microloan — микрокредит 20%\n"
        "• /limits — лимиты\n\n"
        "📊 *Крипто:*\n"
        "• /rates — курсы\n"
        "• /wallet — кошелёк\n"
        "• /buy BTC/ETH/SOL/DOGE/TON <сумма>\n"
        "• /sell <монета> <кол-во>\n\n"
        "🎰 *Развлечения:*\n"
        "• /roulette /slots /dice <сумма>\n\n"
        "🏆 /top — топ богачей\n"
        "📊 /stats — статистика\n"
        "🏛 /treasury — казна\n\n"
        "🆘 /support <вопрос>\n"
        "💡 /suggest <идея>",
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
    bonus = 0
    if is_admin(user.id):
        bonus = 10000000
        add_money(user.id, bonus)
        add_history(user.id, "Бонус администратора", bonus)
    msg = f"✅ *Счёт открыт!*\n\n👤 {user.first_name}\n📅 {datetime.now().strftime('%d.%m.%Y')}"
    if bonus:
        msg += f"\n\n🎁 Бонус: *{bonus:,.0f} ₽*"
    await update.message.reply_text(msg, parse_mode='Markdown')

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "", user.first_name or "")
    bal = get_balance(user.id)
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('SELECT balance FROM savings WHERE user_id = ?', (user.id,))
    sav = c.fetchone()
    c.execute('SELECT amount, loan_type FROM loans WHERE user_id = ?', (user.id,))
    loan_row = c.fetchone()
    conn.close()
    sav_bal = sav[0] if sav else 0
    loan_debt = loan_row[0] if loan_row else 0
    loan_type = loan_row[1] if loan_row else None
    loan_info = ""
    if loan_debt > 0:
        rate = "20%" if loan_type == 'micro' else "15%"
        loan_info = f"\n💸 Долг ({rate}): {loan_debt:,.2f} ₽"
    frozen = "\n🧊 Карта заморожена" if is_card_frozen(user.id) else ""
    await update.message.reply_text(
        f"💳 *Баланс счёта*\n\n"
        f"💰 Основной: {bal:,.2f} ₽\n"
        f"🏦 Вклад: {sav_bal:,.2f} ₽"
        f"{loan_info}{frozen}",
        parse_mode='Markdown'
    )

async def details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    u = get_user(user.id, user.username or "", user.first_name or "")
    bal = get_balance(user.id)
    role = get_role(user.id)
    reg_status = "✅ Зарегистрирован" if u[5] == 1 else "📋 Не зарегистрирован"
    await update.message.reply_text(
        f"📋 *Реквизиты счёта*\n\n"
        f"👤 Имя: {user.first_name}\n"
        f"🔢 Счёт: `{u[4]}`\n"
        f"💰 Баланс: {bal:,.2f} ₽\n"
        f"🎭 Роль: {role}\n"
        f"📋 Статус: {reg_status}",
        parse_mode='Markdown'
    )

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
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

async def givemoney(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("❌ Нет доступа")
        return
    if len(context.args) < 2:
        await update.message.reply_text("❌ Формат: /give @username 10000")
        return
    arg = context.args[0].replace('@', '')
    try:
        amount = float(context.args[1])
        if amount <= 0:
            raise ValueError
    except:
        await update.message.reply_text("❌ Неверная сумма")
        return
    target = find_user(arg)
    if not target:
        await update.message.reply_text("❌ Пользователь не найден")
        return
    add_money(target[0], amount)
    add_history(target[0], f"Выдача от администратора", amount)
    log_action(user.id, "give", target[0], amount)
    await update.message.reply_text(f"✅ Выдано *{amount:,.2f} ₽* → {context.args[0]}", parse_mode='Markdown')
    try:
        await context.bot.send_message(
            target[0],
            f"💰 *Вам выдали деньги!*\n\n"
            f"Сумма: *{amount:,.2f} ₽*\n"
            f"От: администратора",
            parse_mode='Markdown'
        )
    except:
        pass

async def addmoney(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("❌ Нет доступа")
        return
    if len(context.args) < 2:
        await update.message.reply_text("❌ Формат: /addmoney @username 10000")
        return
    arg = context.args[0].replace('@', '')
    try:
        amount = float(context.args[1])
        if amount <= 0:
            raise ValueError
    except:
        await update.message.reply_text("❌ Неверная сумма")
        return
    target = find_user(arg)
    if not target:
        await update.message.reply_text("❌ Пользователь не найден")
        return
    add_money(target[0], amount)
    add_history(target[0], "Начисление", amount)
    log_action(user.id, "addmoney", target[0], amount)
    await update.message.reply_text(f"✅ Начислено *{amount:,.2f} ₽* → {context.args[0]}", parse_mode='Markdown')

async def removemoney(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("❌ Нет доступа")
        return
    if len(context.args) < 2:
        await update.message.reply_text("❌ Формат: /removemoney @username 10000")
        return
    arg = context.args[0].replace('@', '')
    try:
        amount = float(context.args[1])
        if amount <= 0:
            raise ValueError
    except:
        await update.message.reply_text("❌ Неверная сумма")
        return
    target = find_user(arg)
    if not target:
        await update.message.reply_text("❌ Пользователь не найден")
        return
    if not remove_money(target[0], amount):
        await update.message.reply_text("❌ Недостаточно средств")
        return
    add_history(target[0], "Списание", amount)
    log_action(user.id, "removemoney", target[0], amount)
    await update.message.reply_text(f"✅ Списано *{amount:,.2f} ₽* у {context.args[0]}", parse_mode='Markdown')

async def setbalance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("❌ Нет доступа")
        return
    if len(context.args) < 2:
        await update.message.reply_text("❌ Формат: /setbalance @username 10000")
        return
    arg = context.args[0].replace('@', '')
    try:
        amount = float(context.args[1])
        if amount < 0:
            raise ValueError
    except:
        await update.message.reply_text("❌ Неверная сумма")
        return
    target = find_user(arg)
    if not target:
        await update.message.reply_text("❌ Пользователь не найден")
        return
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('UPDATE users SET balance = ? WHERE user_id = ?', (amount, target[0]))
    conn.commit()
    conn.close()
    log_action(user.id, "setbalance", target[0], amount)
    await update.message.reply_text(f"✅ Баланс {context.args[0]} = *{amount:,.2f} ₽*", parse_mode='Markdown')

async def send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "", user.first_name or "")
    if is_card_frozen(user.id):
        await update.message.reply_text("❌ Карта заморожена")
        return
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
    fee = round(amount * TRANSFER_FEE, 2)
    total = amount + fee
    if not remove_money(user.id, total):
        await update.message.reply_text(
            f"❌ Недостаточно средств\n"
            f"💸 Сумма: {amount:,.2f} ₽\n"
            f"💰 Комиссия: {fee:,.2f} ₽\n"
            f"📊 Итого: {total:,.2f} ₽"
        )
        return
    target = find_user(target_username)
    if not target:
        add_money(user.id, total)
        await update.message.reply_text("❌ Пользователь не найден. Деньги возвращены.")
        return
    add_money(target[0], amount)
    add_to_treasury(fee)
    add_history(user.id, f"Перевод → @{target_username}", total)
    add_history(target[0], f"Получено от @{user.username}", amount)
    await update.message.reply_text(
        f"✅ Отправлено *{amount:,.2f} ₽* → @{target_username}\n💰 Комиссия: {fee:,.2f} ₽",
        parse_mode='Markdown'
    )

async def card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "", user.first_name or "")
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('SELECT * FROM cards WHERE user_id = ?', (user.id,))
    row = c.fetchone()
    if context.args and context.args[0] == 'freeze':
        if not row:
            await update.message.reply_text("❌ Нет карты. Напиши /card")
            conn.close()
            return
        c.execute('UPDATE cards SET frozen = 1 WHERE user_id = ?', (user.id,))
        conn.commit()
        conn.close()
        await update.message.reply_text("🧊 Карта *заморожена*", parse_mode='Markdown')
        return
    if context.args and context.args[0] == 'unfreeze':
        if not row:
            await update.message.reply_text("❌ Нет карты.")
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
        f"💳 *Моя карта*\n\n🏦 {row[2]}\n🔢 `{row[1]}`\n📅 {row[3]}\n🔘 {status}\n\n"
        f"• /card freeze\n• /card unfreeze",
        parse_mode='Markdown'
    )

async def savings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "", user.first_name or "")
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('SELECT balance FROM savings WHERE user_id = ?', (user.id,))
    row = c.fetchone()
    if context.args and context.args[0] == 'deposit':
        try:
            amount = float(context.args[1])
            if amount <= 0:
                raise ValueError
        except:
            await update.message.reply_text("❌ Формат: /savings deposit 1000")
            conn.close()
            return
        if not remove_money(user.id, amount):
            await update.message.reply_text("❌ Недостаточно средств")
            conn.close()
            return
        if row:
            c.execute('UPDATE savings SET balance = balance + ? WHERE user_id = ?', (amount, user.id))
        else:
            c.execute('INSERT INTO savings VALUES (?, ?, ?)', (user.id, amount, datetime.now().strftime('%d.%m.%Y')))
        conn.commit()
        conn.close()
        add_history(user.id, "Вклад — пополнение", amount)
        await update.message.reply_text(f"✅ На вклад: *{amount:,.2f} ₽*", parse_mode='Markdown')
    elif context.args and context.args[0] == 'withdraw':
        try:
            amount = float(context.args[1])
            if amount <= 0:
                raise ValueError
        except:
            await update.message.reply_text("❌ Формат: /savings withdraw 1000")
            conn.close()
            return
        if not row or row[0] < amount:
            await update.message.reply_text("❌ Недостаточно на вкладе")
            conn.close()
            return
        c.execute('UPDATE savings SET balance = balance - ? WHERE user_id = ?', (amount, user.id))
        conn.commit()
        conn.close()
        add_money(user.id, amount)
        add_history(user.id, "Вклад — снятие", amount)
        await update.message.reply_text(f"✅ Со вклада: *{amount:,.2f} ₽*", parse_mode='Markdown')
    else:
        bal = row[0] if row else 0
        conn.close()
        await update.message.reply_text(
            f"🏦 *Вклад*\n\n💰 {bal:,.2f} ₽\n📈 5%/год\n\n"
            f"• /savings deposit <сумма>\n• /savings withdraw <сумма>",
            parse_mode='Markdown'
        )

async def loan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "", user.first_name or "")
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('SELECT amount, loan_type FROM loans WHERE user_id = ?', (user.id,))
    row = c.fetchone()
    if context.args and context.args[0] == 'take':
        try:
            amount = float(context.args[1])
            if amount <= 0 or amount > 5000000:
                raise ValueError
        except:
            await update.message.reply_text("❌ Формат: /loan take 100000")
            conn.close()
            return
        if row and row[0] > 0:
            await update.message.reply_text("❌ Уже есть кредит")
            conn.close()
            return
        interest = round(amount * 0.15, 2)
        total = amount + interest
        c.execute('INSERT OR REPLACE INTO loans VALUES (?, ?, ?, ?)',
                  (user.id, total, datetime.now().strftime('%d.%m.%Y'), 'standard'))
        conn.commit()
        conn.close()
        add_money(user.id, amount)
        add_history(user.id, "Кредит получен", amount)
        await update.message.reply_text(
            f"✅ Кредит *{amount:,.2f} ₽*\n📈 Проценты: {interest:,.2f} ₽\n💸 К возврату: {total:,.2f} ₽",
            parse_mode='Markdown'
        )
    elif context.args and context.args[0] == 'repay':
        try:
            amount = float(context.args[1])
            if amount <= 0:
                raise ValueError
        except:
            await update.message.reply_text("❌ Формат: /loan repay 10000")
            conn.close()
            return
        if not row or row[0] <= 0:
            await update.message.reply_text("❌ Нет кредита")
            conn.close()
            return
        if not remove_money(user.id, amount):
            await update.message.reply_text("❌ Недостаточно средств")
            conn.close()
            return
        new_loan = max(0, row[0] - amount)
        c.execute('UPDATE loans SET amount = ? WHERE user_id = ?', (new_loan, user.id))
        conn.commit()
        conn.close()
        add_to_treasury(amount * 0.1)
        add_history(user.id, "Погашение кредита", amount)
        await update.message.reply_text(f"✅ Погашено *{amount:,.2f} ₽*\nОсталось: {new_loan:,.2f} ₽", parse_mode='Markdown')
    else:
        debt = row[0] if row else 0
        conn.close()
        await update.message.reply_text(
            f"💳 *Кредит*\n\n💸 Долг: {debt:,.2f} ₽\n📈 15%\n🔢 Макс: 5 000 000 ₽\n\n"
            f"• /loan take <сумма>\n• /loan repay <сумма>",
            parse_mode='Markdown'
        )

async def microloan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "", user.first_name or "")
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('SELECT amount, loan_type FROM loans WHERE user_id = ?', (user.id,))
    row = c.fetchone()
    if context.args and context.args[0] == 'take':
        try:
            amount = float(context.args[1])
            if amount <= 0 or amount > 50000:
                raise ValueError
        except:
            await update.message.reply_text("❌ Формат: /microloan take 10000")
            conn.close()
            return
        if row and row[0] > 0:
            await update.message.reply_text("❌ Уже есть кредит")
            conn.close()
            return
        interest = round(amount * 0.20, 2)
        total = amount + interest
        c.execute('INSERT OR REPLACE INTO loans VALUES (?, ?, ?, ?)',
                  (user.id, total, datetime.now().strftime('%d.%m.%Y'), 'micro'))
        conn.commit()
        conn.close()
        add_money(user.id, amount)
        add_history(user.id, "Микрокредит получен", amount)
        await update.message.reply_text(
            f"⚡ Микрокредит *{amount:,.2f} ₽*\n📈 Проценты: {interest:,.2f} ₽\n💸 К возврату: {total:,.2f} ₽",
            parse_mode='Markdown'
        )
    elif context.args and context.args[0] == 'repay':
        try:
            amount = float(context.args[1])
            if amount <= 0:
                raise ValueError
        except:
            await update.message.reply_text("❌ Формат: /microloan repay 5000")
            conn.close()
            return
        if not row or row[0] <= 0 or row[1] != 'micro':
            await update.message.reply_text("❌ Нет микрокредита")
            conn.close()
            return
        if not remove_money(user.id, amount):
            await update.message.reply_text("❌ Недостаточно средств")
            conn.close()
            return
        new_loan = max(0, row[0] - amount)
        c.execute('UPDATE loans SET amount = ? WHERE user_id = ?', (new_loan, user.id))
        conn.commit()
        conn.close()
        add_to_treasury(amount * 0.1)
        add_history(user.id, "Погашение микрокредита", amount)
        await update.message.reply_text(f"✅ Погашено *{amount:,.2f} ₽*\nОсталось: {new_loan:,.2f} ₽", parse_mode='Markdown')
    else:
        debt = row[0] if row and row[1] == 'micro' else 0
        conn.close()
        await update.message.reply_text(
            f"⚡ *Микрокредит*\n\n💸 Долг: {debt:,.2f} ₽\n📈 20%\n🔢 Макс: 50 000 ₽\n\n"
            f"• /microloan take <сумма>\n• /microloan repay <сумма>",
            parse_mode='Markdown'
        )

async def limits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "", user.first_name or "")
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    if context.args and context.args[0] == 'set':
        try:
            amount = float(context.args[1])
            if amount <= 0:
                raise ValueError
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
            f"⚙️ *Лимиты*\n\n📊 {lim:,.2f} ₽/день\n🔘 {status}\n\n"
            f"• /limits set <сумма>\n• /limits off",
            parse_mode='Markdown'
        )

async def rates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Получаю курсы...")
    r = get_crypto_rates()
    await update.message.reply_text(
        f"📊 *Курсы криптовалют (₽)*\n\n"
        f"₿ BTC: {r['BTC']:,.0f} ₽\n"
        f"Ξ ETH: {r['ETH']:,.0f} ₽\n"
        f"◎ SOL: {r['SOL']:,.0f} ₽\n"
        f"Ð DOGE: {r['DOGE']:,.2f} ₽\n"
        f"💎 TON: {r['TON']:,.2f} ₽",
        parse_mode='Markdown'
    )

async def wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('SELECT coin, amount, avg_price FROM wallets WHERE user_id = ?', (user.id,))
    rows = c.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("👛 Кошелёк пуст")
        return
    r = get_crypto_rates()
    text = "👛 *Кошелёк*\n\n"
    for coin, amount, avg_price in rows:
        if amount > 0 and coin in r:
            value = amount * r[coin]
            pl = (r[coin] - avg_price) * amount
            pl_str = f"+{pl:,.0f}" if pl >= 0 else f"{pl:,.0f}"
            text += f"*{coin}*: {amount:.6f} = {value:,.0f} ₽ (P&L: {pl_str} ₽)\n"
    await update.message.reply_text(text, parse_mode='Markdown')

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "", user.first_name or "")
    if len(context.args) < 2:
        await update.message.reply_text("❌ Формат: /buy TON 1000")
        return
    coin = context.args[0].upper()
    try:
        rub_amount = float(context.args[1])
        if rub_amount <= 0:
            raise ValueError
    except:
        await update.message.reply_text("❌ Неверная сумма")
        return
    r = get_crypto_rates()
    if coin not in r:
        await update.message.reply_text("❌ Доступно: BTC ETH SOL DOGE TON")
        return
    if not remove_money(user.id, rub_amount):
        await update.message.reply_text("❌ Недостаточно средств")
        return
    price = r[coin]
    coin_amount = rub_amount / price
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
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
        f"✅ Куплено *{coin_amount:.6f} {coin}*\n💸 {rub_amount:,.0f} ₽",
        parse_mode='Markdown'
    )

async def sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username or "", user.first_name or "")
    if len(context.args) < 2:
        await update.message.reply_text("❌ Формат: /sell TON 10")
        return
    coin = context.args[0].upper()
    try:
        coin_amount = float(context.args[1])
        if coin_amount <= 0:
            raise ValueError
    except:
        await update.message.reply_text("❌ Неверная сумма")
        return
    r = get_crypto_rates()
    if coin not in r:
        await update.message.reply_text("❌ Доступно: BTC ETH SOL DOGE TON")
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
    c.execute('UPDATE wallets SET amount = ? WHERE user_id = ? AND coin = ?',
              (existing[0] - coin_amount, user.id, coin))
    conn.commit()
    conn.close()
    add_money(user.id, rub_amount)
    add_history(user.id, f"Продажа {coin}", rub_amount)
    pl = (price - existing[1]) * coin_amount
    pl_str = f"+{pl:,.0f}" if pl >= 0 else f"{pl:,.0f}"
    await update.message.reply_text(
        f"✅ Продано *{coin_amount:.6f} {coin}*\n💰 {rub_amount:,.0f} ₽\n📊 P&L: {pl_str} ₽",
        parse_mode='Markdown'
    )

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
    if not remove_money(user.id, amount):
        await update.message.reply_text("❌ Недостаточно средств")
        return
    result = random.randint(0, 36)
    colors = {0: "🟢"}
    for i in range(1, 37):
        colors[i] = "🔴" if i % 2 == 1 else "⚫"
    win = result != 0 and random.random() > 0.48
    if win:
        add_money(user.id, amount * 2)
        add_history(user.id, "Рулетка — выигрыш", amount)
        await update.message.reply_text(
            f"🎰 *Рулетка*\n{colors[result]} *{result}*\n\n🎉 +{amount:,.2f} ₽",
            parse_mode='Markdown'
        )
    else:
        add_to_treasury(amount * 0.1)
        add_history(user.id, "Рулетка — проигрыш", amount)
        await update.message.reply_text(
            f"🎰 *Рулетка*\n{colors[result]} *{result}*\n\n😢 -{amount:,.2f} ₽",
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
    if not remove_money(user.id, amount):
        await update.message.reply_text("❌ Недостаточно средств")
        return
    symbols = ['🍒', '🍋', '🍊', '⭐', '💎', '7️⃣']
    s1, s2, s3 = random.choice(symbols), random.choice(symbols), random.choice(symbols)
    if s1 == s2 == s3 == '💎':
        mult, text = 10, "💎 ДЖЕКПОТ! x10"
    elif s1 == s2 == s3 == '7️⃣':
        mult, text = 7, "7️⃣ СЕМЁРКИ! x7"
    elif s1 == s2 == s3:
        mult, text = 3, "🎉 Три одинаковых! x3"
    elif s1 == s2 or s2 == s3:
        mult, text = 1.5, "✨ Два одинаковых! x1.5"
    else:
        mult, text = 0, "😢 Нет совпадений"
    if mult > 0:
        winnings = amount * mult
        add_money(user.id, winnings)
        add_history(user.id, f"Слоты x{mult}", winnings)
        money_str = f"+{winnings - amount:,.2f} ₽"
    else:
        add_to_treasury(amount * 0.1)
        add_history(user.id, "Слоты — проигрыш", amount)
        money_str = f"-{amount:,.2f} ₽"
    await update.message.reply_text(
        f"🎰 *Слоты*\n[ {s1} | {s2} | {s3} ]\n\n{text}\n{money_str}",
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
    if not remove_money(user.id, amount):
        await update.message.reply_text("❌ Недостаточно средств")
        return
    player = random.randint(1, 6)
    bank_roll = random.randint(1, 6)
    if player > bank_roll:
        add_money(user.id, amount * 2)
        add_history(user.id, "Кости — выигрыш", amount)
        result = f"🎉 Ты выиграл! +{amount:,.2f} ₽"
    elif player < bank_roll:
        add_to_treasury(amount * 0.1)
        add_history(user.id, "Кости — проигрыш", amount)
        result = f"😢 Банк выиграл! -{amount:,.2f} ₽"
    else:
        add_money(user.id, amount)
        result = "🤝 Ничья!"
    await update.message.reply_text(
        f"🎲 *Кости*\nТы: *{player}* | Банк: *{bank_roll}*\n\n{result}",
        parse_mode='Markdown'
    )

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('SELECT username, first_name, balance FROM users ORDER BY balance DESC LIMIT 10')
    rows = c.fetchall()
    conn.close()
    medals = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']
    text = "🏆 *Топ богачей CryptoBank V2*\n\n"
    for i, (username, first_name, balance) in enumerate(rows):
        name = f"@{username}" if username else first_name or "Аноним"
        text += f"{medals[i]} {name} — {balance:,.2f} ₽\n"
    await update.message.reply_text(text, parse_mode='Markdown')

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM users')
    total_users = c.fetchone()[0]
    c.execute('SELECT COALESCE(SUM(balance), 0) FROM users')
    total_money = c.fetchone()[0]
    c.execute('SELECT COALESCE(SUM(balance), 0) FROM savings')
    total_savings = c.fetchone()[0]
    c.execute('SELECT COALESCE(SUM(amount), 0) FROM loans WHERE amount > 0')
    total_loans = c.fetchone()[0]
    c.execute('SELECT COUNT(*), COALESCE(SUM(reward), 0) FROM photos')
    photo_row = c.fetchone()
    c.execute('SELECT COUNT(*) FROM history')
    total_tx = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM support_tickets WHERE status = "open"')
    open_tickets = c.fetchone()[0]
    treasury_bal = get_treasury()
    conn.close()
    await update.message.reply_text(
        f"📊 *Статистика CryptoBank V2*\n\n"
        f"👥 Клиентов: {total_users}\n"
        f"💰 Деньги в системе: {total_money:,.2f} ₽\n"
        f"🏦 На вкладах: {total_savings:,.2f} ₽\n"
        f"💸 Долги: {total_loans:,.2f} ₽\n"
        f"🏛 Казна: {treasury_bal:,.2f} ₽\n"
        f"📸 Фото-наград: {photo_row[0]} ({photo_row[1]:,.0f} ₽)\n"
        f"📋 Транзакций: {total_tx}\n"
        f"🆘 Открытых обращений: {open_tickets}",
        parse_mode='Markdown'
    )

async def treasury_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bal = get_treasury()
    await update.message.reply_text(
        f"🏛 *Казна CryptoBank*\n\n💰 {bal:,.2f} ₽\n\n"
        f"_Источники:_\n• Комиссии переводов\n• Проценты кредитов\n• Проигрыши казино",
        parse_mode='Markdown'
    )

async def treasury_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_owner(user.id):
        await update.message.reply_text("❌ Только владелец")
        return
    if not context.args:
        await update.message.reply_text("❌ Формат: /treasury_withdraw 10000")
        return
    try:
        amount = float(context.args[0])
        if amount <= 0:
            raise ValueError
    except:
        await update.message.reply_text("❌ Неверная сумма")
        return
    bal = get_treasury()
    if bal < amount:
        await update.message.reply_text(f"❌ В казне: {bal:,.2f} ₽")
        return
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('UPDATE treasury SET balance = balance - ? WHERE id = 0', (amount,))
    conn.commit()
    conn.close()
    add_money(user.id, amount)
    await update.message.reply_text(f"✅ Из казны: *{amount:,.2f} ₽*", parse_mode='Markdown')

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.photo:
        return
    if PHOTO_CHAT_ID and update.message.chat_id != PHOTO_CHAT_ID:
        return
    user = update.effective_user
    get_user(user.id, user.username or "", user.first_name or "")
    file_unique_id = update.message.photo[-1].file_unique_id
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('SELECT file_unique_id FROM photos WHERE file_unique_id = ?', (file_unique_id,))
    if c.fetchone():
        conn.close()
        return
    reward = random.randint(100, 500)
    c.execute('INSERT INTO photos VALUES (?, ?, ?, ?)',
              (file_unique_id, user.id, reward, datetime.now().strftime('%d.%m.%Y %H:%M')))
    conn.commit()
    conn.close()
    add_money(user.id, reward)
    add_history(user.id, "Фото-заработок", reward)
    await update.message.reply_text(f"📸 Уникальное фото! +*{reward} ₽*", parse_mode='Markdown')

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not context.args:
        await update.message.reply_text(
            "🆘 *Поддержка CryptoBank*\n\n/support <вопрос>",
            parse_mode='Markdown'
        )
        return
    text = ' '.join(context.args)
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('INSERT INTO support_tickets (user_id, username, text, status, date) VALUES (?, ?, ?, ?, ?)',
              (user.id, user.username or user.first_name, text, 'open', datetime.now().strftime('%d.%m.%Y %H:%M')))
    ticket_id = c.lastrowid
    conn.commit()
    conn.close()
    await update.message.reply_text(
        f"✅ *Обращение #{ticket_id} принято!*\n\n📝 {text}\n\n⏳ Администратор ответит вам скоро",
        parse_mode='Markdown'
    )
    if SUPPORT_CHAT_ID:
        try:
            await context.bot.send_message(
                SUPPORT_CHAT_ID,
                f"🆘 *Новое обращение #{ticket_id}*\n\n👤 @{user.username or user.first_name} (ID: {user.id})\n📝 {text}\n\nОтветить: /reply {ticket_id} <ответ>",
                parse_mode='Markdown'
            )
        except:
            pass

async def suggest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not context.args:
        await update.message.reply_text(
            "💡 *Предложения*\n\n/suggest <идея>",
            parse_mode='Markdown'
        )
        return
    text = ' '.join(context.args)
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('INSERT INTO suggestions (user_id, username, text, status, date) VALUES (?, ?, ?, ?, ?)',
              (user.id, user.username or user.first_name, text, 'new', datetime.now().strftime('%d.%m.%Y %H:%M')))
    suggestion_id = c.lastrowid
    conn.commit()
    conn.close()
    await update.message.reply_text(
        f"💡 *Идея #{suggestion_id} принята!*\n\n📝 {text}\n\nСпасибо!",
        parse_mode='Markdown'
    )
    if SUPPORT_CHAT_ID:
        try:
            await context.bot.send_message(
                SUPPORT_CHAT_ID,
                f"💡 *Новая идея #{suggestion_id}*\n\n👤 @{user.username or user.first_name}\n📝 {text}",
                parse_mode='Markdown'
            )
        except:
            pass

async def tickets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("❌ Нет доступа")
        return
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('SELECT id, username, text, date FROM support_tickets WHERE status = "open" ORDER BY id DESC LIMIT 10')
    rows = c.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("✅ Открытых обращений нет")
        return
    text = "🆘 *Открытые обращения:*\n\n"
    for tid, username, msg, date in rows:
        text += f"*#{tid}* @{username} ({date})\n{msg}\n\n"
    text += "Ответить: /reply <id> <ответ>\nЗакрыть: /closeticket <id>"
    await update.message.reply_text(text, parse_mode='Markdown')

async def suggestions_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("❌ Нет доступа")
        return
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('SELECT id, username, text, status FROM suggestions ORDER BY id DESC LIMIT 10')
    rows = c.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("📭 Предложений нет")
        return
    icons = {'new': '🆕', 'accepted': '✅', 'rejected': '❌'}
    text = "💡 *Предложения:*\n\n"
    for sid, username, msg, status in rows:
        text += f"{icons.get(status, '❓')} *#{sid}* @{username}\n{msg}\n\n"
    await update.message.reply_text(text, parse_mode='Markdown')

async def reply_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("❌ Нет доступа")
        return
    if len(context.args) < 2:
        await update.message.reply_text("❌ Формат: /reply 5 <ответ>")
        return
    try:
        ticket_id = int(context.args[0])
    except:
        await update.message.reply_text("❌ Неверный ID")
        return
    reply_text = ' '.join(context.args[1:])
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('SELECT user_id, text FROM support_tickets WHERE id = ?', (ticket_id,))
    ticket = c.fetchone()
    if not ticket:
        conn.close()
        await update.message.reply_text("❌ Обращение не найдено")
        return
    c.execute('UPDATE support_tickets SET status = "closed" WHERE id = ?', (ticket_id,))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ Ответ отправлен на обращение #{ticket_id}")
    try:
        await context.bot.send_message(
            ticket[0],
            f"📬 *Ответ на обращение #{ticket_id}*\n\n📝 Ваш вопрос: {ticket[1]}\n\n💬 Ответ:\n{reply_text}",
            parse_mode='Markdown'
        )
    except:
        pass

async def closeticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("❌ Нет доступа")
        return
    if not context.args:
        await update.message.reply_text("❌ Формат: /closeticket 5")
        return
    try:
        ticket_id = int(context.args[0])
    except:
        await update.message.reply_text("❌ Неверный ID")
        return
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('UPDATE support_tickets SET status = "closed" WHERE id = ?', (ticket_id,))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ Обращение #{ticket_id} закрыто")

async def acceptidea(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("❌ Нет доступа")
        return
    if not context.args:
        await update.message.reply_text("❌ Формат: /acceptidea 5")
        return
    try:
        sid = int(context.args[0])
    except:
        await update.message.reply_text("❌ Неверный ID")
        return
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('SELECT user_id, text FROM suggestions WHERE id = ?', (sid,))
    row = c.fetchone()
    if not row:
        conn.close()
        await update.message.reply_text("❌ Идея не найдена")
        return
    c.execute('UPDATE suggestions SET status = "accepted" WHERE id = ?', (sid,))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ Идея #{sid} принята!")
    try:
        await context.bot.send_message(
            row[0],
            f"🎉 *Ваша идея принята!*\n\n📝 {row[1]}",
            parse_mode='Markdown'
        )
    except:
        pass

async def rejectidea(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("❌ Нет доступа")
        return
    if not context.args:
        await update.message.reply_text("❌ Формат: /rejectidea 5")
        return
    try:
        sid = int(context.args[0])
    except:
        await update.message.reply_text("❌ Неверный ID")
        return
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('UPDATE suggestions SET status = "rejected" WHERE id = ?', (sid,))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"❌ Идея #{sid} отклонена")

async def addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_owner(user.id):
        await update.message.reply_text("❌ Только владелец")
        return
    if not context.args:
        await update.message.reply_text("❌ Формат: /addadmin @username или /addadmin 123456789")
        return
    arg = context.args[0].replace('@', '')
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    if arg.isdigit():
        c.execute('SELECT user_id, username FROM users WHERE user_id = ?', (int(arg),))
    else:
        c.execute('SELECT user_id, username FROM users WHERE username = ?', (arg,))
    target = c.fetchone()
    if not target:
        target_id = int(arg) if arg.isdigit() else abs(hash(arg)) % 1000000000
        account = f"CR{target_id}"[-10:]
        c.execute('INSERT OR IGNORE INTO users (user_id, username, first_name, balance, account_number, registered) VALUES (?, ?, ?, ?, ?, ?)',
                  (target_id, arg, arg, 0, account, 1))
        target = (target_id, arg)
    c.execute('INSERT OR REPLACE INTO admins VALUES (?, ?, ?)',
              (target[0], target[1], datetime.now().strftime('%d.%m.%Y')))
    conn.commit()
    conn.close()
    log_action(user.id, "addadmin", target[0], None)
    await update.message.reply_text(f"✅ {context.args[0]} назначен *администратором*!", parse_mode='Markdown')

async def removeadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_owner(user.id):
        await update.message.reply_text("❌ Только владелец")
        return
    if not context.args:
        await update.message.reply_text("❌ Формат: /removeadmin @username или /removeadmin 123456789")
        return
    arg = context.args[0].replace('@', '')
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    if arg.isdigit():
        c.execute('DELETE FROM admins WHERE user_id = ?', (int(arg),))
    else:
        c.execute('DELETE FROM admins WHERE username = ?', (arg,))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ {context.args[0]} снят с должности")

async def addowner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != OWNER_ID:
        await update.message.reply_text("❌ Только главный владелец")
        return
    if not context.args:
        await update.message.reply_text("❌ Формат: /addowner @username или /addowner 123456789")
        return
    arg = context.args[0].replace('@', '')
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    if arg.isdigit():
        c.execute('SELECT user_id, username FROM users WHERE user_id = ?', (int(arg),))
    else:
        c.execute('SELECT user_id, username FROM users WHERE username = ?', (arg,))
    target = c.fetchone()
    if not target:
        target_id = int(arg) if arg.isdigit() else abs(hash(arg)) % 1000000000
        account = f"CR{target_id}"[-10:]
        c.execute('INSERT OR IGNORE INTO users (user_id, username, first_name, balance, account_number, registered) VALUES (?, ?, ?, ?, ?, ?)',
                  (target_id, arg, arg, 0, account, 1))
        target = (target_id, arg)
    c.execute('INSERT OR REPLACE INTO owners VALUES (?, ?, ?)',
              (target[0], target[1], datetime.now().strftime('%d.%m.%Y')))
    conn.commit()
    conn.close()
    log_action(user.id, "addowner", target[0], None)
    await update.message.reply_text(f"✅ {context.args[0]} назначен *владельцем*!", parse_mode='Markdown')

async def removeowner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != OWNER_ID:
        await update.message.reply_text("❌ Только главный владелец")
        return
    if not context.args:
        await update.message.reply_text("❌ Формат: /removeowner @username или /removeowner 123456789")
        return
    arg = context.args[0].replace('@', '')
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    if arg.isdigit():
        c.execute('DELETE FROM owners WHERE user_id = ?', (int(arg),))
    else:
        c.execute('DELETE FROM owners WHERE username = ?', (arg,))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ {context.args[0]} снят с должности владельца")

async def admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('SELECT user_id, username, added_date FROM owners ORDER BY added_date')
    owners = c.fetchall()
    c.execute('SELECT user_id, username, added_date FROM admins ORDER BY added_date')
    admins_list = c.fetchall()
    conn.close()
    text = f"👑 *Администрация CryptoBank V2*\n\n👑 *Главный владелец:*\n• ID `{OWNER_ID}`\n\n"
    if owners:
        text += "👑 *Владельцы:*\n"
        for uid, username, date in owners:
            name = f"@{username}" if username and not username.isdigit() else f"ID {uid}"
            text += f"• {name} (с {date})\n"
        text += "\n"
    if admins_list:
        text += "🛡 *Администраторы:*\n"
        for uid, username, date in admins_list:
            name = f"@{username}" if username and not username.isdigit() else f"ID {uid}"
            text += f"• {name} (с {date})\n"
    else:
        text += "🛡 Администраторов пока нет"
    await update.message.reply_text(text, parse_mode='Markdown')

async def logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("❌ Нет доступа")
        return
    conn = sqlite3.connect('bank.db')
    c = conn.cursor()
    c.execute('SELECT admin_id, action, target_id, amount, created_at FROM admin_logs ORDER BY id DESC LIMIT 20')
    rows = c.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("📭 Логов нет")
        return
    text = "🔍 *Логи администрации*\n\n"
    for admin_id, action, target_id, amount, date in rows:
        amt = f" {amount:,.0f} ₽" if amount else ""
        text += f"• [{date}] {admin_id} → {action}{amt}\n"
    await update.message.reply_text(text, parse_mode='Markdown')

def create_bank_app():
    init_db()
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CommandHandler("register", register))
    bot.add_handler(CommandHandler("balance", balance))
    bot.add_handler(CommandHandler("details", details))
    bot.add_handler(CommandHandler("history", history))
    bot.add_handler(CommandHandler("give", givemoney))
    bot.add_handler(CommandHandler("addmoney", addmoney))
    bot.add_handler(CommandHandler("removemoney", removemoney))
    bot.add_handler(CommandHandler("setbalance", setbalance))
    bot.add_handler(CommandHandler("send", send))
    bot.add_handler(CommandHandler("card", card))
    bot.add_handler(CommandHandler("savings", savings))
    bot.add_handler(CommandHandler("loan", loan))
    bot.add_handler(CommandHandler("microloan", microloan))
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
    bot.add_handler(CommandHandler("treasury", treasury_cmd))
    bot.add_handler(CommandHandler("treasury_withdraw", treasury_withdraw))
    bot.add_handler(CommandHandler("support", support))
    bot.add_handler(CommandHandler("suggest", suggest))
    bot.add_handler(CommandHandler("tickets", tickets))
    bot.add_handler(CommandHandler("suggestions", suggestions_list))
    bot.add_handler(CommandHandler("reply", reply_ticket))
    bot.add_handler(CommandHandler("closeticket", closeticket))
    bot.add_handler(CommandHandler("acceptidea", acceptidea))
    bot.add_handler(CommandHandler("rejectidea", rejectidea))
    bot.add_handler(CommandHandler("addadmin", addadmin))
    bot.add_handler(CommandHandler("removeadmin", removeadmin))
    bot.add_handler(CommandHandler("addowner", addowner))
    bot.add_handler(CommandHandler("removeowner", removeowner))
    bot.add_handler(CommandHandler("admins", admins))
    bot.add_handler(CommandHandler("logs", logs))
    bot.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    return bot