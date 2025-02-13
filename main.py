import telebot
import sqlite3

# 🔹 Replace with your Telegram Bot Token
TOKEN = "7273062152:AAG3CdkJ_lIXG8Tmwzss_JfFyPgXxk2_vW0"
bot = telebot.TeleBot(TOKEN)

# 🔹 Replace with your Telegram Admin ID
ADMIN_ID = 6224320021

# 🔹 Pay-IDs for different exchanges
PAY_IDS = {
    "binance": "556736103",
    "bybit": "76098891",
    "bitget": "6255235662",
    "kucoin": "222810007"
}

# 🔹 Initialize SQLite Database
conn = sqlite3.connect("transactions.db", check_same_thread=False)
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


# 📌 Start Command
@bot.message_handler(commands=["start"])
def send_welcome(message):
    bot.reply_to(message,
                 "Welcome to the P2P Exchange Bot! Use /exchange to begin.")


# 📌 Exchange Command
@bot.message_handler(commands=["exchange"])
def exchange_request(message):
    user_id = message.chat.id
    bot.send_message(
        user_id, "Select an exchange:\n🔹 Binance\n🔹 Bybit\n🔹 Bitget\n🔹 KuCoin")

    @bot.message_handler(func=lambda msg: msg.text.lower() in PAY_IDS)
    def handle_exchange(msg):
        exchange = msg.text.lower()
        pay_id = PAY_IDS[exchange]
        bot.send_message(
            user_id,
            f"Send your funds to **{pay_id}** and reply with the amount.")

        @bot.message_handler(
            func=lambda msg: msg.text.replace('.', '', 1).isdigit())
        def handle_amount(msg):
            amount = float(msg.text)
            fee = round(amount * 0.05, 2)  # 5% Fee
            final_amount = round(amount - fee, 2)

            cursor.execute(
                "INSERT INTO transactions (user_id, username, exchange, pay_id, amount, status) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, msg.chat.username, exchange, pay_id, amount,
                 "Pending"))
            conn.commit()

            bot.send_message(
                ADMIN_ID,
                f"🔔 New Transaction:\nUser: @{msg.chat.username}\nAmount: {amount} USDT\nExchange: {exchange}\nFee: {fee} USDT\nFinal: {final_amount} USDT\nStatus: Pending"
            )
            bot.send_message(
                user_id,
                f"✅ Transaction recorded! Please wait for admin confirmation." transaction_id )


# 📌 Admin Confirmation
@bot.message_handler(commands=["confirm"])
def confirm_transaction(message):
    if message.chat.id != ADMIN_ID:
        bot.reply_to(message, "🚫 Only the admin can confirm transactions!")
        return

    bot.send_message(ADMIN_ID, "Enter the transaction ID to confirm:")

    @bot.message_handler(func=lambda msg: msg.text.isdigit())
    def handle_confirmation(msg):
        transaction_id = int(msg.text)
        cursor.execute(
            "UPDATE transactions SET status = 'Completed' WHERE id = ?",
            (transaction_id, ))
        conn.commit()

        bot.send_message(
            ADMIN_ID, f"✅ Transaction {transaction_id} marked as Completed!")
        bot.send_message(
            transaction_id,
            "🎉 Your transaction is confirmed. Check your account!")


# 🔹 Run the Bot
bot.polling()
