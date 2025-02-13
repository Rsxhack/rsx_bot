import telebot
import sqlite3
import os

# Load sensitive information from environment variables
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("TELEGRAM_ADMIN_ID"))

bot = telebot.TeleBot(TOKEN)

# Pay-IDs for different exchanges
PAY_IDS = {
    "binance": "556736103",
    "bybit": "76098891",
    "bitget": "6255235662",
    "kucoin": "222810007"
}

# Initialize SQLite Database
def init_db():
    with sqlite3.connect("transactions.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                exchange TEXT,
                pay_id TEXT,
                amount REAL,
                status TEXT
            )
        """)
        conn.commit()

init_db()

# Start Command
@bot.message_handler(commands=["start"])
def send_welcome(message):
    bot.reply_to(message, "Welcome to the P2P Exchange Bot! Use /exchange to begin.")

# Exchange Command
@bot.message_handler(commands=["exchange"])
def exchange_request(message):
    user_id = message.chat.id
    bot.send_message(user_id, "Select an exchange:\n🔹 Binance\n🔹 Bybit\n🔹 Bitget\n🔹 KuCoin")

# Handle Exchange Selection
@bot.message_handler(func=lambda msg: msg.text.lower() in PAY_IDS)
def handle_exchange(msg):
    user_id = msg.chat.id
    exchange = msg.text.lower()
    pay_id = PAY_IDS[exchange]
    bot.send_message(user_id, f"Send your funds to **{pay_id}** and reply with the amount.")

# Handle Amount
@bot.message_handler(func=lambda msg: msg.text.replace('.', '', 1).isdigit())
def handle_amount(msg):
    user_id = msg.chat.id
    amount = float(msg.text)
    fee = round(amount * 0.05, 2)  # 5% Fee
    final_amount = round(amount - fee, 2)
    username = msg.chat.username

    try:
        with sqlite3.connect("transactions.db") as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO transactions (user_id, username, exchange, pay_id, amount, status) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, username, msg.text.lower(), PAY_IDS[msg.text.lower()], amount, "Pending")
            )
            conn.commit()
    except sqlite3.Error as e:
        bot.send_message(user_id, f"❌ An error occurred while recording the transaction: {e}")
        return

    bot.send_message(
        ADMIN_ID,
        f"🔔 New Transaction:\nUser: @{username}\nAmount: {amount} USDT\nExchange: {msg.text.lower()}\nFee: {fee} USDT\nFinal: {final_amount} USDT\nStatus: Pending"
    )
    bot.send_message(user_id, "✅ Transaction recorded! Please wait for admin confirmation.")

# Admin Confirmation
@bot.message_handler(commands=["confirm"])
def confirm_transaction(message):
    if message.chat.id != ADMIN_ID:
        bot.reply_to(message, "🚫 Only the admin can confirm transactions!")
        return

    bot.send_message(ADMIN_ID, "Enter the transaction ID to confirm:")

# Handle Confirmation
@bot.message_handler(func=lambda msg: msg.text.isdigit())
def handle_confirmation(msg):
    transaction_id = int(msg.text)
    try:
        with sqlite3.connect("transactions.db") as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE transactions SET status = 'Completed' WHERE id = ?",
                (transaction_id,)
            )
            conn.commit()
    except sqlite3.Error as e:
        bot.send_message(ADMIN_ID, f"❌ An error occurred while updating the transaction: {e}")
        return

    bot.send_message(ADMIN_ID, f"✅ Transaction {transaction_id} marked as Completed!")
    bot.send_message(transaction_id, "🎉 Your transaction is confirmed. Check your account!")

# Run the Bot
bot.polling()
