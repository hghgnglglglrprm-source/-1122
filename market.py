import sqlite3
from datetime import datetime

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

TOKEN = "8794841327:AAGbjVX33nZpYsHOJQ12xYr9gB0c6FHjLmc"
DB_NAME = "market.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        seller_id INTEGER,
        seller_name TEXT,
        title TEXT,
        description TEXT,
        price REAL,
        status TEXT DEFAULT 'active',
        created_at TEXT
    )
    """)

    conn.commit()
    conn.close()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🛍 Маркетплейс\n\n"
        "/sell <цена> <название> | <описание>\n"
        "/catalog\n"
        "/item <id>\n"
        "/deleteitem <id>"
    )


async def sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(
            "Пример:\n"
            "/sell 500 Наушники | Отличное состояние"
        )
        return

    try:
        price = float(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Неверная цена")
        return

    text = " ".join(context.args[1:])

    if "|" in text:
        title, description = text.split("|", 1)
    else:
        title = text
        description = "Без описания"

    user = update.effective_user

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO products
        (seller_id, seller_name, title, description, price, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        user.id,
        user.username or user.first_name,
        title.strip(),
        description.strip(),
        price,
        datetime.now().strftime("%d.%m.%Y %H:%M")
    ))

    item_id = cur.lastrowid

    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"✅ Товар добавлен\n\n"
        f"ID: {item_id}\n"
        f"Название: {title.strip()}\n"
        f"Цена: {price} ₽"
    )


async def catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        SELECT id, title, price
        FROM products
        WHERE status='active'
        ORDER BY id DESC
        LIMIT 20
    """)

    rows = cur.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("Каталог пуст")
        return

    text = "🛍 Каталог\n\n"

    for item_id, title, price in rows:
        text += f"#{item_id} | {title}\n💰 {price} ₽\n\n"

    await update.message.reply_text(text)


async def item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Используй: /item <id>")
        return

    try:
        item_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Неверный ID")
        return

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM products
        WHERE id=?
    """, (item_id,))

    row = cur.fetchone()
    conn.close()

    if not row:
        await update.message.reply_text("Товар не найден")
        return

    await update.message.reply_text(
        f"📦 {row[3]}\n\n"
        f"📝 {row[4]}\n\n"
        f"💰 {row[5]} ₽\n"
        f"👤 {row[2]}\n"
        f"📅 {row[7]}"
    )


async def deleteitem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Используй: /deleteitem <id>")
        return

    try:
        item_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Неверный ID")
        return

    user = update.effective_user

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute(
        "SELECT seller_id FROM products WHERE id=?",
        (item_id,)
    )

    row = cur.fetchone()

    if not row:
        conn.close()
        await update.message.reply_text("Товар не найден")
        return

    if row[0] != user.id:
        conn.close()
        await update.message.reply_text("Это не твой товар")
        return

    cur.execute(
        "DELETE FROM products WHERE id=?",
        (item_id,)
    )

    conn.commit()
    conn.close()

    await update.message.reply_text("✅ Товар удалён")


def main():
    init_db()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("sell", sell))
    app.add_handler(CommandHandler("catalog", catalog))
    app.add_handler(CommandHandler("item", item))
    app.add_handler(CommandHandler("deleteitem", deleteitem))

    print("Бот запущен")

    app.run_polling()


if __name__ == "__main__":
    main()