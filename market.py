import logging
import sqlite3
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from flask import Flask
from threading import Thread
import time

# ===== ВЕБ-СЕРВЕР =====
flask_app = Flask('')

@flask_app.route('/')
def home():
    return "Маркетплейс работает!"

Thread(target=lambda: flask_app.run(host='0.0.0.0', port=8080)).start()

# ===== НАСТРОЙКИ =====
TOKEN = "8794841327:AAGw31krYI2eoTdTrfzJw-Sh3VKGIM-9tS0"
OWNER_ID = 7845037971
BANK_DB = "bank.db"
MARKET_DB = "market.db"

# ===== БАЗА ДАННЫХ =====
def init_db():
    conn = sqlite3.connect(MARKET_DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        seller_id INTEGER,
        seller_username TEXT,
        title TEXT,
        description TEXT,
        price REAL,
        category TEXT,
        status TEXT DEFAULT 'pending',
        buyer_id INTEGER,
        created_date TEXT,
        checked_by TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS moderators (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        role TEXT,
        added_date TEXT
    )''')
    conn.commit()
    conn.close()

def is_owner(user_id):
    return user_id == OWNER_ID

def is_moderator(user_id):
    if is_owner(user_id):
        return True
    conn = sqlite3.connect(MARKET_DB)
    c = conn.cursor()
    c.execute('SELECT role FROM moderators WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    return row is not None and row[0] in ('moderator', 'admin')

def get_role(user_id):
    if is_owner(user_id):
        return 'owner'
    conn = sqlite3.connect(MARKET_DB)
    c = conn.cursor()
    c.execute('SELECT role FROM moderators WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 'user'

def get_bank_balance(user_id):
    try:
        conn = sqlite3.connect(BANK_DB)
        c = conn.cursor()
        c.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        row = c.fetchone()
        conn.close()
        return row[0] if row else 0
    except:
        return 0

def update_bank_balance(user_id, amount):
    try:
        conn = sqlite3.connect(BANK_DB)
        c = conn.cursor()
        c.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def add_bank_history(user_id, action, amount):
    try:
        conn = sqlite3.connect(BANK_DB)
        c = conn.cursor()
        c.execute('INSERT INTO history (user_id, action, amount, date) VALUES (?, ?, ?, ?)',
                  (user_id, action, amount, datetime.now().strftime('%d.%m.%Y %H:%M')))
        conn.commit()
        conn.close()
    except:
        pass

# ===== КОМАНДЫ =====

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"🛍 Добро пожаловать в *Маркетплейс*, {user.first_name}!\n\n"
        "📦 *Товары:*\n"
        "• /sell <цена> <категория> <название> | <описание> — выставить товар\n"
        "• /catalog — каталог товаров\n"
        "• /catalog услуги — по категории\n"
        "• /item <id> — подробнее о товаре\n"
        "• /buy <id> — купить товар\n"
        "• /myitems — мои товары\n"
        "• /mypurchases — мои покупки\n\n"
        "📂 *Категории:*\n"
        "• услуги\n"
        "• товары\n"
        "• другое\n\n"
        "💸 Оплата через CryptoBank",
        parse_mode='Markdown'
    )

async def sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not context.args or len(context.args) < 3:
        await update.message.reply_text(
            "❌ Формат:\n"
            "/sell <цена> <категория> <название> | <описание>\n\n"
            "Пример:\n"
            "/sell 5000 услуги Уборка квартиры | Профессиональная уборка за 2 часа"
        )
        return
    try:
        price = float(context.args[0])
        if price <= 0:
            raise ValueError
    except:
        await update.message.reply_text("❌ Неверная цена")
        return
    category = context.args[1].lower()
    if category not in ['услуги', 'товары', 'другое']:
        await update.message.reply_text("❌ Категория: услуги, товары, другое")
        return
    rest = ' '.join(context.args[2:])
    if '|' in rest:
        parts = rest.split('|', 1)
        title = parts[0].strip()
        description = parts[1].strip()
    else:
        title = rest.strip()
        description = "Без описания"
    if len(title) < 3:
        await update.message.reply_text("❌ Название слишком короткое")
        return
    conn = sqlite3.connect(MARKET_DB)
    c = conn.cursor()
    c.execute('''INSERT INTO products 
        (seller_id, seller_username, title, description, price, category, status, created_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (user.id, user.username or user.first_name, title, description,
         price, category, 'pending', datetime.now().strftime('%d.%m.%Y %H:%M')))
    product_id = c.lastrowid
    conn.commit()
    conn.close()
    await update.message.reply_text(
        f"✅ Товар *#{product_id}* отправлен на проверку!\n\n"
        f"📦 {title}\n"
        f"💰 {price:,.2f} ₽\n"
        f"📂 {category}\n\n"
        f"⏳ Ожидай одобрения модератора",
        parse_mode='Markdown'
    )

async def catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    category_filter = context.args[0].lower() if context.args else None
    conn = sqlite3.connect(MARKET_DB)
    c = conn.cursor()
    if category_filter:
        c.execute('SELECT id, title, price, category, seller_username FROM products WHERE status = ? AND category = ? ORDER BY id DESC LIMIT 20',
                  ('approved', category_filter))
    else:
        c.execute('SELECT id, title, price, category, seller_username FROM products WHERE status = ? ORDER BY id DESC LIMIT 20',
                  ('approved',))
    rows = c.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("📭 Товаров пока нет")
        return
    cat_icons = {'услуги': '🔧', 'товары': '📦', 'другое': '🔖'}
    text = "🛍 *Каталог товаров*\n\n"
    for row in rows:
        icon = cat_icons.get(row[3], '📦')
        text += f"{icon} *#{row[0]}* {row[1]}\n"
        text += f"💰 {row[2]:,.2f} ₽ | @{row[4]}\n\n"
    text += "Подробнее: /item <id>\nКупить: /buy <id>"
    await update.message.reply_text(text, parse_mode='Markdown')

async def item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Формат: /item 5")
        return
    try:
        item_id = int(context.args[0])
    except:
        await update.message.reply_text("❌ Неверный ID")
        return
    conn = sqlite3.connect(MARKET_DB)
    c = conn.cursor()
    c.execute('SELECT * FROM products WHERE id = ?', (item_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        await update.message.reply_text("❌ Товар не найден")
        return
    status_icons = {
        'pending': '⏳ На проверке',
        'approved': '✅ Доступен',
        'sold': '🔴 Продан',
        'rejected': '❌ Отклонён'
    }
    status = status_icons.get(row[7], row[7])
    await update.message.reply_text(
        f"📦 *{row[3]}*\n\n"
        f"📝 {row[4]}\n\n"
        f"💰 Цена: {row[5]:,.2f} ₽\n"
        f"📂 Категория: {row[6]}\n"
        f"👤 Продавец: @{row[2]}\n"
        f"📅 Дата: {row[9]}\n"
        f"🔘 Статус: {status}\n\n"
        f"Купить: /buy {row[0]}",
        parse_mode='Markdown'
    )

async def buy_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not context.args:
        await update.message.reply_text("❌ Формат: /buy 5")
        return
    try:
        item_id = int(context.args[0])
    except:
        await update.message.reply_text("❌ Неверный ID")
        return
    conn = sqlite3.connect(MARKET_DB)
    c = conn.cursor()
    c.execute('SELECT * FROM products WHERE id = ?', (item_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        await update.message.reply_text("❌ Товар не найден")
        return
    if row[7] != 'approved':
        conn.close()
        await update.message.reply_text("❌ Товар недоступен для покупки")
        return
    if row[1] == user.id:
        conn.close()
        await update.message.reply_text("❌ Нельзя купить свой товар")
        return
    price = row[5]
    seller_id = row[1]
    balance = get_bank_balance(user.id)
    if balance < price:
        conn.close()
        await update.message.reply_text(
            f"❌ Недостаточно средств\n"
            f"💰 Твой баланс: {balance:,.2f} ₽\n"
            f"💸 Цена товара: {price:,.2f} ₽"
        )
        return
    update_bank_balance(user.id, -price)
    update_bank_balance(seller_id, price)
    add_bank_history(user.id, f"Покупка #{item_id} {row[3]}", price)
    add_bank_history(seller_id, f"Продажа #{item_id} {row[3]}", price)
    c.execute('UPDATE products SET status = ?, buyer_id = ? WHERE id = ?',
              ('sold', user.id, item_id))
    conn.commit()
    conn.close()
    await update.message.reply_text(
        f"✅ *Покупка совершена!*\n\n"
        f"📦 {row[3]}\n"
        f"💸 Списано: {price:,.2f} ₽\n"
        f"👤 Продавец: @{row[2]}\n\n"
        f"Свяжись с продавцом для получения товара/услуги",
        parse_mode='Markdown'
    )
    try:
        await context.bot.send_message(
            seller_id,
            f"💰 *Твой товар куплен!*\n\n"
            f"📦 {row[3]}\n"
            f"💰 Получено: {price:,.2f} ₽\n"
            f"👤 Покупатель: @{user.username or user.first_name}",
            parse_mode='Markdown'
        )
    except:
        pass

async def myitems(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = sqlite3.connect(MARKET_DB)
    c = conn.cursor()
    c.execute('SELECT id, title, price, status FROM products WHERE seller_id = ? ORDER BY id DESC', (user.id,))
    rows = c.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("📭 У тебя нет выставленных товаров")
        return
    status_icons = {'pending': '⏳', 'approved': '✅', 'sold': '🔴', 'rejected': '❌'}
    text = "📦 *Мои товары*\n\n"
    for row in rows:
        icon = status_icons.get(row[3], '❓')
        text += f"{icon} *#{row[0]}* {row[1]} — {row[2]:,.2f} ₽\n"
    await update.message.reply_text(text, parse_mode='Markdown')

async def mypurchases(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = sqlite3.connect(MARKET_DB)
    c = conn.cursor()
    c.execute('SELECT id, title, price, seller_username FROM products WHERE buyer_id = ? ORDER BY id DESC', (user.id,))
    rows = c.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("📭 У тебя нет покупок")
        return
    text = "🛍 *Мои покупки*\n\n"
    for row in rows:
        text += f"✅ *#{row[0]}* {row[1]} — {row[2]:,.2f} ₽\n"
        text += f"👤 Продавец: @{row[3]}\n\n"
    await update.message.reply_text(text, parse_mode='Markdown')

# ===== МОДЕРАЦИЯ =====

async def pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_moderator(user.id):
        await update.message.reply_text("❌ Нет доступа")
        return
    conn = sqlite3.connect(MARKET_DB)
    c = conn.cursor()
    c.execute('SELECT id, title, price, category, seller_username FROM products WHERE status = ? ORDER BY id', ('pending',))
    rows = c.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("✅ Нет товаров на проверке")
        return
    text = "⏳ *Товары на проверке*\n\n"
    for row in rows:
        text += f"*#{row[0]}* {row[1]}\n"
        text += f"💰 {row[2]:,.2f} ₽ | 📂 {row[3]} | @{row[4]}\n\n"
    text += "Одобрить: /approve <id>\nОтклонить: /reject <id> <причина>"
    await update.message.reply_text(text, parse_mode='Markdown')

async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_moderator(user.id):
        await update.message.reply_text("❌ Нет доступа")
        return
    if not context.args:
        await update.message.reply_text("❌ Формат: /approve 5")
        return
    try:
        item_id = int(context.args[0])
    except:
        await update.message.reply_text("❌ Неверный ID")
        return
    conn = sqlite3.connect(MARKET_DB)
    c = conn.cursor()
    c.execute('SELECT seller_id, title FROM products WHERE id = ? AND status = ?', (item_id, 'pending'))
    row = c.fetchone()
    if not row:
        conn.close()
        await update.message.reply_text("❌ Товар не найден или уже проверен")
        return
    c.execute('UPDATE products SET status = ?, checked_by = ? WHERE id = ?',
              ('approved', user.username or str(user.id), item_id))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ Товар *#{item_id}* одобрен и добавлен в каталог!", parse_mode='Markdown')
    try:
        await context.bot.send_message(
            row[0],
            f"✅ *Твой товар одобрен!*\n\n"
            f"📦 {row[1]}\n"
            f"Он теперь виден в каталоге!",
            parse_mode='Markdown'
        )
    except:
        pass

async def reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_moderator(user.id):
        await update.message.reply_text("❌ Нет доступа")
        return
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("❌ Формат: /reject 5 причина")
        return
    try:
        item_id = int(context.args[0])
    except:
        await update.message.reply_text("❌ Неверный ID")
        return
    reason = ' '.join(context.args[1:])
    conn = sqlite3.connect(MARKET_DB)
    c = conn.cursor()
    c.execute('SELECT seller_id, title FROM products WHERE id = ? AND status = ?', (item_id, 'pending'))
    row = c.fetchone()
    if not row:
        conn.close()
        await update.message.reply_text("❌ Товар не найден или уже проверен")
        return
    c.execute('UPDATE products SET status = ?, checked_by = ? WHERE id = ?',
              ('rejected', user.username or str(user.id), item_id))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"❌ Товар *#{item_id}* отклонён", parse_mode='Markdown')
    try:
        await context.bot.send_message(
            row[0],
            f"❌ *Твой товар отклонён*\n\n"
            f"📦 {row[1]}\n"
            f"📝 Причина: {reason}\n\n"
            f"Исправь и выставь снова",
            parse_mode='Markdown'
        )
    except:
        pass

# ===== УПРАВЛЕНИЕ МОДЕРАТОРАМИ =====

async def addmod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_owner(user.id):
        await update.message.reply_text("❌ Только владелец может добавлять модераторов")
        return
    if len(context.args) < 2:
        await update.message.reply_text("❌ Формат: /addmod @username moderator\nРоли: moderator, admin")
        return
    target_username = context.args[0].replace('@', '')
    role = context.args[1].lower()
    if role not in ['moderator', 'admin']:
        await update.message.reply_text("❌ Роли: moderator, admin")
        return
    conn = sqlite3.connect(MARKET_DB)
    c = conn.cursor()
    fake_id = abs(hash(target_username)) % 1000000000
    c.execute('INSERT OR REPLACE INTO moderators VALUES (?, ?, ?, ?)',
              (fake_id, target_username, role, datetime.now().strftime('%d.%m.%Y')))
    conn.commit()
    conn.close()
    role_name = "Модератор" if role == 'moderator' else "Администратор"
    await update.message.reply_text(f"✅ @{target_username} назначен как {role_name}!")

async def removemod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_owner(user.id):
        await update.message.reply_text("❌ Только владелец может снимать модераторов")
        return
    if not context.args:
        await update.message.reply_text("❌ Формат: /removemod @username")
        return
    target_username = context.args[0].replace('@', '')
    conn = sqlite3.connect(MARKET_DB)
    c = conn.cursor()
    c.execute('DELETE FROM moderators WHERE username = ?', (target_username,))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ @{target_username} снят с должности")

async def modlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(MARKET_DB)
    c = conn.cursor()
    c.execute('SELECT username, role, added_date FROM moderators ORDER BY role')
    rows = c.fetchall()
    conn.close()
    text = "👮 *Команда маркетплейса*\n\n"
    text += f"👑 Владелец: ID `{OWNER_ID}`\n\n"
    admins = [r for r in rows if r[1] == 'admin']
    mods = [r for r in rows if r[1] == 'moderator']
    if admins:
        text += "🛡 *Администраторы:*\n"
        for r in admins:
            text += f"• @{r[0]} (с {r[2]})\n"
        text += "\n"
    if mods:
        text += "👮 *Модераторы:*\n"
        for r in mods:
            text += f"• @{r[0]} (с {r[2]})\n"
    if not rows:
        text += "Команды пока нет"
    await update.message.reply_text(text, parse_mode='Markdown')

async def delitem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_moderator(user.id):
        await update.message.reply_text("❌ Нет доступа")
        return
    if not context.args:
        await update.message.reply_text("❌ Формат: /delitem 5")
        return
    try:
        item_id = int(context.args[0])
    except:
        await update.message.reply_text("❌ Неверный ID")
        return
    conn = sqlite3.connect(MARKET_DB)
    c = conn.cursor()
    c.execute('DELETE FROM products WHERE id = ?', (item_id,))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ Товар *#{item_id}* удалён", parse_mode='Markdown')

# ===== ЗАПУСК =====
init_db()

while True:
    try:
        bot = ApplicationBuilder().token(TOKEN).build()
        bot.add_handler(CommandHandler("start", start))
        bot.add_handler(CommandHandler("sell", sell))
        bot.add_handler(CommandHandler("catalog", catalog))
        bot.add_handler(CommandHandler("item", item))
        bot.add_handler(CommandHandler("buy", buy_item))
        bot.add_handler(CommandHandler("myitems", myitems))
        bot.add_handler(CommandHandler("mypurchases", mypurchases))
        bot.add_handler(CommandHandler("pending", pending))
        bot.add_handler(CommandHandler("approve", approve))
        bot.add_handler(CommandHandler("reject", reject))
        bot.add_handler(CommandHandler("addmod", addmod))
        bot.add_handler(CommandHandler("removemod", removemod))
        bot.add_handler(CommandHandler("modlist", modlist))
        bot.add_handler(CommandHandler("delitem", delitem))
        bot.run_polling()
    except Exception as e:
        print(f"Ошибка: {e}")
        time.sleep(5)
