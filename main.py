import telebot
import sqlite3
import time
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
import ssl

# Fix for environments without SSL support
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass

# Bot Token & Admin ID
TOKEN = "7273062152:AAG3CdkJ_lIXG8Tmwzss_JfFyPgXxk2_vW0"
ADMIN_ID = 6224320021  # Your Telegram Admin ID
bot = telebot.TeleBot(TOKEN)

# Payment Details
UPI_ID = "xxx-pay@axl"  # UPI ID for fiat payments
PAY_IDS = {
    "binance": "556736103",
    "bybit": "76098891",
    "bitget": "6255235662",
    "kucoin": "222810007"
}

# Setup requests session with retries
def requests_session():
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retries))
    return session

session = requests_session()

# Fetch real-time crypto rates
def get_crypto_price(symbol):
    try:
        binance_price = bybit_price = kucoin_price = 0
        
        # Fetch from Binance
        binance_url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}USDT"
        binance_response = session.get(binance_url, timeout=5)
        if binance_response.status_code == 200:
            binance_data = binance_response.json()
            binance_price = float(binance_data.get("price", 0))
        
        # Fetch from Bybit
        bybit_url = "https://api.bybit.com/v2/public/tickers"
        bybit_response = session.get(bybit_url, timeout=5)
        if bybit_response.status_code == 200:
            bybit_data = bybit_response.json()
            bybit_price = next((float(ticker.get("last_price", 0)) for ticker in bybit_data.get("result", []) if ticker.get("symbol") == f"{symbol}USDT"), binance_price)
        
        # Fetch from KuCoin
        kucoin_url = "https://api.kucoin.com/api/v1/market/allTickers"
        kucoin_response = session.get(kucoin_url, timeout=5)
        if kucoin_response.status_code == 200:
            kucoin_data = kucoin_response.json()
            kucoin_price = next((float(ticker.get("last", 0))
                                 for ticker in kucoin_data.get("data", {}).get("ticker", []) if ticker.get("symbol") == f"{symbol}-USDT"), binance_price)
        
        # Check if any price was fetched successfully
        prices = [p for p in [binance_price, bybit_price, kucoin_price] if p > 0]
        if not prices:
            raise ValueError("No valid prices fetched from APIs.")
        
        # Average price from all sources
        avg_price = round(sum(prices) / len(prices), 2)
        return avg_price
    except Exception as e:
        print(f"Error fetching price: {e}")
        return None

# Initialize SQLite Database
def init_db():
    with sqlite3.connect("transactions.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                balances REAL,
                amount REAL,
                currency TEXT,
                transaction_type TEXT,
                exchange TEXT,
                wallet_info TEXT,
                pay_info TEXT,
                txn_id TEXT,
                status TEXT
            )
        """)
        conn.commit()

init_db()

def check_pending_transaction(user_id):
    with sqlite3.connect("transactions.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM transactions WHERE user_id = ? AND status = 'Pending'", (user_id,))
        return cursor.fetchone() is not None

@bot.message_handler(commands=["start"])
def start(message):
    markup = InlineKeyboardMarkup()
    buy_btn = InlineKeyboardButton("Buy", callback_data="buy")
    sell_btn = InlineKeyboardButton("Sell", callback_data="sell")
    markup.add(buy_btn, sell_btn)
    bot.send_message(message.chat.id, "Welcome to the Exchange Bot! Select Buy or Sell:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ["buy", "sell"])
def select_currency(call):
    user_id = call.message.chat.id
    if check_pending_transaction(user_id):
        bot.send_message(user_id, "⚠️ You have a pending transaction. Please wait until it's completed.")
        return
    
    transaction_type = "Buy" if call.data == "buy" else "Sell"
    bot.answer_callback_query(call.id)
    markup = InlineKeyboardMarkup()
    currencies = ["BTC", "ETH", "USDT", "BNB", "LTC", "SOL","TON"] if transaction_type == "Buy" else ["INR", "USD", "EUR", "GBP"]
    for currency in currencies:
        markup.add(InlineKeyboardButton(currency, callback_data=f"currency_{transaction_type}_{currency}"))
    bot.edit_message_text("Select a currency:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("currency_"))
def show_price_and_enter_amount(call):
    user_id = call.message.chat.id
    _, transaction_type, currency = call.data.split("_")
    bot.answer_callback_query(call.id)
    
    price = get_crypto_price(currency)
    if price:
        bot.send_message(user_id, f"💰 Current {currency} Price: **${price}** per unit")
    else:
        bot.send_message(user_id, "⚠️ Unable to fetch the latest price. Proceed with caution.")
    
    bot.send_message(user_id, "Enter the amount:")
    bot.register_next_step_handler_by_chat_id(user_id, lambda msg: enter_wallet(msg, transaction_type, currency, price))

def enter_wallet(message, transaction_type, currency, price):
    user_id = message.chat.id
    amount = message.text
    bot.send_message(user_id, "Enter your Wallet Address for (Crypto) or Enter your UPI/PayPal/Paxum for (Fiat):")
    bot.register_next_step_handler_by_chat_id(user_id, lambda msg: provide_payment_details(msg, transaction_type, currency, amount, price))

def provide_payment_details(message, transaction_type, currency, amount, price):
    user_id = message.chat.id
    wallet_info = message.text
    pay_info = PAY_IDS.get(currency.lower(), UPI_ID) if transaction_type == "Buy" else "Your payment method details"
    
    with sqlite3.connect("transactions.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO transactions (user_id, username, amount, currency, transaction_type, wallet_info, pay_info, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, message.chat.username, amount, currency, transaction_type, wallet_info, pay_info, "Pending"))
        conn.commit()
    
    bot.send_message(user_id, f"✅ Transaction initiated!\n\n"
                              f"Amount: {amount} {currency}\n"
                              f"Transaction Type: {transaction_type}\n"
                              f"Wallet Info: {wallet_info}\n"
                              f"Payment Info: {pay_info}\n\n"
                              f"Please wait for confirmation.")
    # Add further logic for transaction confirmation if needed.
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Approve", callback_data=f"approve_{transaction_id}"))
    markup.add(types.InlineKeyboardButton("Reject", callback_data=f"reject_{transaction_id}"))
    bot.send_message(
    ADMIN_ID, 
    f"New Transaction Request:\nUser: {message.chat.username}\nTransaction ID: {transaction_id}\nExchange: {exchange}\nType: {transaction_type}\nAmount: {amount}\nWallet: {wallet_info}\nStatus: Pending",
    reply_markup=markup
    )
    
@bot.callback_query_handler(func=lambda call: call.data.startswith("approve_"))
def approve_transaction(call):
    transaction_id = call.data.split("_")[1]
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("UPDATE transactions SET status = ? WHERE transaction_id = ?", ("Approved", transaction_id))
    db.commit()
    db.close()
    bot.send_message(call.message.chat.id, f"Transaction {transaction_id} approved.")
    user_id = get_user_id(transaction_id)
    if user_id:
        bot.send_message(user_id, f"Your transaction {transaction_id} has been approved!")

@bot.callback_query_handler(func=lambda call: call.data.startswith("reject_"))
def reject_transaction(call):
    transaction_id = call.data.split("_")[1]
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("UPDATE transactions SET status = ? WHERE transaction_id = ?", ("Rejected", transaction_id))
    db.commit()
    db.close()
    bot.send_message(call.message.chat.id, f"Transaction {transaction_id} rejected.")
    user_id = get_user_id(transaction_id)
    if user_id:
        bot.send_message(user_id, f"Your transaction {transaction_id} has been rejected.")

@bot.message_handler(commands=["dashboard"])
def view_dashboard(message):
    if message.chat.id != ADMIN_ID:
        return
    with sqlite3.connect("transactions.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM transactions")
        transactions = cursor.fetchall()
    response = "📊 All Transactions:\n"
    for txn in transactions:
        response += f"\n🆔 {txn[0]} | @{txn[2]} | {txn[5]} {txn[6]} | {txn[7]} | {txn[9]}"
    bot.reply_to(message, response or "✅ No transactions in database.")

@bot.message_handler(commands=["alltransaction"])
def view_pending_transactions(message):
    if message.chat.id != ADMIN_ID:
        return
    with sqlite3.connect("transactions.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM transactions WHERE status = 'Pending'")
        transactions = cursor.fetchall()
    response = "📌 Pending Transactions:\n"
    for txn in transactions:
        response += f"\n🆔 {txn[0]} | @{txn[2]} | {txn[5]} {txn[6]} | {txn[7]} | {txn[9]}"
    bot.reply_to(message, response or "✅ No pending transactions.")

@bot.message_handler(commands=["balance"])
def check_balance(message):
    user_id = message.chat.id
    with sqlite3.connect("transactions.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT balances FROM transactions WHERE user_id = ?", (user_id,))
        balance = cursor.fetchone()[0]
    bot.reply_to(message, f"💰 Your current balance: {balance:.2f} USDT")

@bot.message_handler(commands=["confirm"])
def confirm_transaction(message):
    if message.chat.id != ADMIN_ID:
        bot.reply_to(message, "🚫 Only the admin can confirm transactions!")
        return
    bot.send_message(ADMIN_ID, "🔍 Enter the transaction ID to confirm:")
    bot.register_next_step_handler(message, handle_confirmation)

def handle_confirmation(msg):
    if msg.chat.id != ADMIN_ID:
        return
    if not msg.text.isdigit():
        bot.send_message(ADMIN_ID, "❌ Invalid input! Please enter a numeric transaction ID.")
        return
    transaction_id = int(msg.text)
    try:
        with sqlite3.connect("transactions.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, amount FROM transactions WHERE id = ? AND status = 'Pending'", (transaction_id,))
            transaction = cursor.fetchone()
            if not transaction:
                bot.send_message(ADMIN_ID, "❌ Transaction not found or already confirmed.")
                return
            user_id, amount = transaction
            cursor.execute("UPDATE transactions SET status = 'Completed' WHERE id = ?", (transaction_id,))
            cursor.execute("UPDATE transactions SET balances = balance + ? WHERE user_id = ?", (amount, user_id))
            conn.commit()
    except sqlite3.Error as e:
        bot.send_message(ADMIN_ID, f"❌ Database error: {e}")
        return
    bot.send_message(ADMIN_ID, f"✅ Transaction {transaction_id} has been confirmed!")
    bot.send_message(user_id, f"🎉 Your transaction has been confirmed! New balance: {amount} USDT")

# Status Command - Check user's transaction status
@bot.message_handler(commands=["status"])
def check_transaction_status(message):
    user_id = message.chat.id

    with sqlite3.connect("transactions.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, exchange, amount, status FROM transactions WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,))
        transaction = cursor.fetchone()

    if not transaction:
        bot.reply_to(message, "❌ No transactions found.")
        return

    txn_id, exchange, amount, status = transaction
    bot.reply_to(message, f"📊 **Latest Transaction:**\n🆔 ID: {txn_id}\n🏦 Exchange: {exchange.capitalize()}\n💰 Amount: {amount} USDT\n📌 Status: {status}")

# Cancel Command - Allows users to cancel their last pending transaction
@bot.message_handler(commands=["cancel"])
def cancel_transaction(message):
    user_id = message.chat.id

    with sqlite3.connect("transactions.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM transactions WHERE user_id = ? AND status = 'Pending' ORDER BY id DESC LIMIT 1", (user_id,))
        transaction = cursor.fetchone()

        if not transaction:
            bot.reply_to(message, "❌ No pending transactions to cancel.")
            return

        txn_id = transaction[0]
        cursor.execute("DELETE FROM transactions WHERE id = ?", (txn_id,))
        conn.commit()

    bot.reply_to(message, f"❌ Transaction ID {txn_id} has been canceled successfully.")

# Exchange Command - Allows users to start a transaction
@bot.message_handler(commands=["exchange"])
def start_exchange(message):
    user_id = message.chat.id
    bot.send_message(user_id, "🔄 Please select an exchange: Binance, Bybit, Bitget, KuCoin.")
    bot.register_next_step_handler(message, handle_exchange_selection)

def handle_exchange_selection(message):
    user_id = message.chat.id
    exchange = message.text.lower()

    if exchange not in PAY_IDS:
        bot.send_message(user_id, "❌ Invalid exchange! Please choose from Binance, Bybit, Bitget, KuCoin.")
        return

    pay_id = PAY_IDS[exchange]
    bot.send_message(user_id, f"✅ You've selected {exchange.capitalize()}. Use this Pay-ID: `{pay_id}`.\nSend the amount and share transaction details.")

print("🤖 Bot is running...")
try:
    bot.polling(none_stop=True)
except Exception as e:
    print(f"🔥 Bot crashed! Error: {e}")
    time.sleep(5)

