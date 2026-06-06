
import sqlite3
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.environ.get("MARKET_TOKEN", "TOKEN = "8794841327:AAGw31krYI2eoTdTrfzJw-Sh3VKGIM-9tS0"")
BANK_DB = "bank.db"
MARKET_DB = "market.db"

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
        status TEXT DEFAULT 'active',
        buyer_id INTEGER,
        created_date TEXT
    )''')
    conn.commit()
    conn.close()

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"🛍 Добро пожаловать в *Маркетплейс*, {user.first_name}!\n\n"
        "📦 *Команды:*\n"
        "• /sell <цена> <категория> <название> | <описание>\n"
        "• /catalog — каталог\n"
        "• /catalog <категория> — по категории\n"
        "• /item <id> — подробнее\n"
        "• /buy <id> — купить\n"
        "• /myitems — мои товары\n"
        "• /mypurchases — мои покупки\n"
        "• /deleteitem <id> — удалить свой товар\n\n"
        "📂 *Категории:* услуги, товары, другое\n\n"
        "💸 Оплата через CryptoBank",
        parse_mode='Markdown'
    )

async def sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not context.args or len(context.args) < 3:
        await update.message.reply_text(
            "❌ Формат:\n/sell <цена> <категория> <название> | <описание>\n\n"
            "Пример:\n/sell 5000 услуги Уборка квартиры | Профессиональная уборка"
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
    c.execute('INSERT INTO products (seller_id, seller_username, title, description, price, category, status, created_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
              (user.id, user.username or user.first_name, title, description, price, category, 'active', datetime.now().strftime('%d.%m.%Y %H:%M')))
    product_id = c.lastrowid
    conn.commit()
    conn.close()
    await update.message.reply_text(
        f"✅ Товар *#{product_id}* добавлен в каталог!\n\n"
        f"📦 {title}\n💰 {price:,.2f} ₽\n📂 {category}",
        parse_mode='Markdown'
    )

async def catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    category_filter = context.args[0].lower() if context.args else None
    conn = sqlite3.connect(MARKET_DB)
    c = conn.cursor()
    if category_filter:
        c.execute('SELECT id, title, price, category, seller_username FROM products WHERE status = ? AND category = ? ORDER BY id DESC LIMIT 20',
                  ('active', category_filter))
    else:
        c.execute('SELECT id, title, price, category, seller_username FROM products WHERE status = ? ORDER BY id DESC LIMIT 20',
                  ('active',))
    rows = c.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("📭 Товаров пока нет")
        return
    cat_icons = {'услуги': '🔧', 'товары': '📦', 'другое': '🔖'}
    text = "🛍 *Каталог товаров*\n\n"
    for row in rows:
        icon = cat_icons.get(row[3], '📦')
        text += f"{icon} *#{row[0]}* {row[1]}\n💰 {row[2]:,.2f} ₽ | @{row[4]}\n\n"
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
    status_icons = {'active': '✅ Доступен', 'sold': '🔴 Продан'}
    await update.message.reply_text(
        f"📦 *{row[3]}*\n\n📝 {row[4]}\n\n"
        f"💰 Цена: {row[5]:,.2f} ₽\n"
        f"📂 Категория: {row[6]}\n"
        f"👤 Продавец: @{row[2]}\n"
        f"📅 Дата: {row[9]}\n"
        f"🔘 Статус: {status_icons.get(row[7], row[7])}\n\n"
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
    if row[7] != 'active':
        conn.close()
        await update.message.reply_text("❌ Товар недоступен")
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
            f"❌ Недостаточно средств\n💰 Баланс: {balance:,.2f} ₽\n💸 Цена: {price:,.2f} ₽"
        )
        return
    update_bank_balance(user.id, -price)
    update_bank_balance(seller_id, price)
    add_bank_history(user.id, f"Покупка #{item_id} {row[3]}", price)
    add_bank_history(seller_id, f"Продажа #{item_id} {row[3]}", price)
    c.execute('UPDATE products SET status = ?, buyer_id = ? WHERE id = ?', ('sold', user.id, item_id))
    conn.commit()
    conn.close()
    await update.message.reply_text(
        f"✅ *Покупка совершена!*\n\n📦 {row[3]}\n💸 {price:,.2f} ₽\n👤 Продавец: @{row[2]}\n\nСвяжись с продавцом для получения товара",
        parse_mode='Markdown'
    )
    try:
        await context.bot.send_message(
            seller_id,
            f"💰 *Твой товар куплен!*\n\n📦 {row[3]}\n💰 +{price:,.2f} ₽\n👤 Покупатель: @{user.username or user.first_name}",
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
        await update.message.reply_text("📭 У тебя нет товаров")
        return
    status_icons = {'active': '✅', 'sold': '🔴'}
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
        text += f"✅ *#{row[0]}* {row[1]} — {row[2]:,.2f} ₽\n👤 @{row[3]}\n\n"
    await update.message.reply_text(text, parse_mode='Markdown')

async def deleteitem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not context.args:
        await update.message.reply_text("❌ Формат: /deleteitem 5")
        return
    try:
        item_id = int(context.args[0])
    except:
        await update.message.reply_text("❌ Неверный ID")
        return
    conn = sqlite3.connect(MARKET_DB)
    c = conn.cursor()
    c.execute('SELECT seller_id, status FROM products WHERE id = ?', (item_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        await update.message.reply_text("❌ Товар не найден")
        return
    if row[0] != user.id:
        conn.close()
        await update.message.reply_text("❌ Это не твой товар")
        return
    if row[1] == 'sold':
        conn.close()
        await update.message.reply_text("❌ Нельзя удалить проданный товар")
        return
    c.execute('DELETE FROM products WHERE id = ?', (item_id,))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ Товар #{item_id} удалён")

import os

def create_market_app():
    init_db()
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CommandHandler("sell", sell))
    bot.add_handler(CommandHandler("catalog", catalog))
    bot.add_handler(CommandHandler("item", item))
    bot.add_handler(CommandHandler("buy", buy_item))
    bot.add_handler(CommandHandler("myitems", myitems))
    bot.add_handler(CommandHandler("mypurchases", mypurchases))
    bot.add_handler(CommandHandler("deleteitem", deleteitem))
    return bot