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
                amount REAL,
                currency TEXT,
                transaction_type TEXT,
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
    currencies = ["BTC", "ETH", "USDT", "BNB"] if transaction_type == "Buy" else ["INR", "USD", "EUR"]
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
    bot.send_message(user_id, "Enter your Wallet Address (Crypto) or UPI/PayPal/Paxum (Fiat):")
    bot.register_next_step_handler_by_chat_id(user_id, lambda msg: provide_payment_details(msg, transaction_type, currency, amount, price))

print("🤖 Bot is running...")
bot.polling(none_stop=True)
