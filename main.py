import telebot
import sqlite3
import time
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import ssl
import uuid

try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass

# === CONFIG ===
TOKEN = "7273062152:AAG3CdkJ_lIXG8Tmwzss_JfFyPgXxk2_vW0"
ADMIN_ID = 6224320021
UPI_ID = "xxx-pay@axl"
PAY_IDS = {
    "binance": "556736103",
    "bybit": "76098891",
    "bitget": "6255235662",
    "kucoin": "222810007"
}

bot = telebot.TeleBot(TOKEN)
user_context = {}

# === SESSION FOR REQUESTS ===
def requests_session():
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retries))
    return session

session = requests_session()

# === CRYPTO PRICE FETCHING ===
def get_crypto_price(symbol):
    try:
        binance_price = bybit_price = kucoin_price = 0
        binance_url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}USDT"
        binance_response = session.get(binance_url, timeout=5)
        if binance_response.status_code == 200:
            binance_price = float(binance_response.json().get("price", 0))

        bybit_url = "https://api.bybit.com/v2/public/tickers"
        bybit_response = session.get(bybit_url, timeout=5)
        if bybit_response.status_code == 200:
            bybit_data = bybit_response.json()
            bybit_price = next((float(t.get("last_price", 0)) for t in bybit_data.get("result", []) if t.get("symbol") == f"{symbol}USDT"), binance_price)

        kucoin_url = "https://api.kucoin.com/api/v1/market/allTickers"
        kucoin_response = session.get(kucoin_url, timeout=5)
        if kucoin_response.status_code == 200:
            kucoin_data = kucoin_response.json()
            kucoin_price = next((float(t.get("last", 0)) for t in kucoin_data.get("data", {}).get("ticker", []) if t.get("symbol") == f"{symbol}-USDT"), binance_price)

        prices = [p for p in [binance_price, bybit_price, kucoin_price] if p > 0]
        if not prices:
            raise ValueError("No valid prices fetched from APIs.")
        return round(sum(prices) / len(prices), 2)
    except Exception as e:
        print(f"Price Fetch Error: {e}")
        return None

# === DB ===
def init_db():
    with sqlite3.connect("transactions.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                amount TEXT,
                currency TEXT,
                transaction_type TEXT,
                exchange TEXT,
                wallet_info TEXT,
                pay_info TEXT,
                txn_id TEXT,
                status TEXT,
                proof TEXT
            )
        """)
        conn.commit()

def get_user_id(txn_id):
    with sqlite3.connect("transactions.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM transactions WHERE txn_id = ?", (txn_id,))
        result = cursor.fetchone()
        return result[0] if result else None

init_db()

# === CHECK PENDING ===
def check_pending_transaction(user_id):
    with sqlite3.connect("transactions.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM transactions WHERE user_id = ? AND status = 'Pending'", (user_id,))
        return cursor.fetchone() is not None

# === BOT FLOW ===
@bot.message_handler(commands=["start"])
def start(message):
    if check_pending_transaction(message.chat.id):
        bot.send_message(message.chat.id, "⚠️ You have a pending transaction. Wait until it's completed.")
        return

    markup = InlineKeyboardMarkup()
    for exchange in PAY_IDS:
        markup.add(InlineKeyboardButton(exchange.title(), callback_data=f"exchange_{exchange}"))
    bot.send_message(message.chat.id, "Welcome to RSX Exchange Bot!\nSelect exchange:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("exchange_"))
def select_type(call):
    user_id = call.message.chat.id
    exchange = call.data.split("_")[1]
    user_context[user_id] = {"exchange": exchange}
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Buy", callback_data="type_Buy"))
    markup.add(InlineKeyboardButton("Sell", callback_data="type_Sell"))
    bot.send_message(user_id, "Select transaction type:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("type_"))
def select_currency(call):
    user_id = call.message.chat.id
    transaction_type = call.data.split("_")[1]
    user_context[user_id]["transaction_type"] = transaction_type
    markup = InlineKeyboardMarkup()
    currencies = ["BTC", "ETH", "USDT", "BNB", "LTC", "SOL", "TON", "XRP"] if transaction_type == "Buy" else ["INR", "USD"]
    for c in currencies:
        markup.add(InlineKeyboardButton(c, callback_data=f"currency_{c}"))
    bot.send_message(user_id, "Select currency:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("currency_"))
def get_amount(call):
    user_id = call.message.chat.id
    currency = call.data.split("_")[1]
    user_context[user_id]["currency"] = currency
    bot.send_message(user_id, "Enter amount:")
    bot.register_next_step_handler(call.message, get_wallet)

def get_wallet(message):
    user_id = message.chat.id
    user_context[user_id]["amount"] = message.text.strip()
    bot.send_message(user_id, "Enter your wallet address for (Crypto) or UPI for (Faith):")
    bot.register_next_step_handler(message, confirm_transaction)

def confirm_transaction(message):
    user_id = message.chat.id
    ctx = user_context[user_id]
    txn_id = str(uuid.uuid4())[:8]
    wallet_info = message.text.strip()

    # Update context with essential data
    ctx.update({
        "wallet_info": wallet_info,
        "txn_id": txn_id,
        "status": "Awaiting Proof",
        "user_id": user_id,
        "username": message.from_user.username or "unknown",
        "upi_id": UPI_ID,
        "pay_info": PAY_IDS.get(ctx["exchange"])
    })

    # Save transaction to DB
    with sqlite3.connect("transactions.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""INSERT INTO transactions 
            (user_id, username, amount, currency, transaction_type, exchange, wallet_info, pay_info, txn_id, status) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (ctx["user_id"], ctx["username"], ctx["amount"], ctx["currency"],
             ctx["transaction_type"], ctx["exchange"], ctx["wallet_info"],
             ctx["pay_info"], ctx["txn_id"], ctx["status"]))
        conn.commit()

    # Message setup based on transaction type
    msg = f"📤 Make payment now:\n\n🔁 *Type*: {ctx['transaction_type']}\n💱 *Exchange*: {ctx['exchange'].upper()}\n💰 *Amount*: {ctx['amount']} {ctx['currency']}\n\n"

    if ctx["transaction_type"].lower() == "buy":
        msg += f"💸 *Pay via UPI (INR)*:\n`{ctx['upi_id']}`"
        msg += "\n\n📌 Once paid, write *'Transaction ID or UTR No.'* below."
    else:
        msg += f"🚀 *Send Crypto to Pay ID*:\n`{ctx['pay_info']}`"
        msg += f"\n💰 *Asset*: {ctx['currency']}"
        msg += "\n\n📌 Once sent, write *'Transaction ID or UTR No.'* below."

    bot.send_message(user_id, msg, parse_mode="Markdown")
    bot.send_message(user_id, "🔁 After payment, send *Transaction Hash or UTR No.*:", parse_mode="Markdown")
    bot.register_next_step_handler(message, get_proof_of_payment)


def get_proof_of_payment(message):
    user_id = message.chat.id
    proof = message.text.strip()
    ctx = user_context.get(user_id)

    if not ctx:
        bot.send_message(user_id, "⚠️ Session expired. Please /start again.")
        return

    with sqlite3.connect("transactions.db") as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE transactions SET proof = ?, status = ? WHERE txn_id = ?", (proof, "Pending", ctx["txn_id"]))
        conn.commit()

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ Approve", callback_data=f"approve_{ctx['txn_id']}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"reject_{ctx['txn_id']}")
    )

    msg = f"""📥 *New Transaction for Approval*

👤 User: @{ctx['username']}
🆔 Txn ID: `{ctx['txn_id']}`
🔁 Type: {ctx['transaction_type']}
💱 Exchange: {ctx['exchange'].upper()}
💰 Amount: {ctx['amount']} {ctx['currency']}
🔐 Wallet/UPI: {ctx['wallet_info']}
📎 Proof: `{proof}`
📍 Status: Pending"""

    bot.send_message(ADMIN_ID, msg, reply_markup=markup, parse_mode="Markdown")
    bot.send_message(user_id, f"✅ Proof submitted!\nTxn ID: `{ctx['txn_id']}`\nWaiting for admin approval.", parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("approve_"))
def approve(call):
    txn_id = call.data.split("_")[1]
    with sqlite3.connect("transactions.db") as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE transactions SET status = 'Approved' WHERE txn_id = ?", (txn_id,))
        conn.commit()
    user_id = get_user_id(txn_id)
    if user_id:
        bot.send_message(user_id, f"✅ Transaction `{txn_id}` approved!", parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("reject_"))
def reject(call):
    txn_id = call.data.split("_")[1]
    with sqlite3.connect("transactions.db") as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE transactions SET status = 'Rejected' WHERE txn_id = ?", (txn_id,))
        conn.commit()
    user_id = get_user_id(txn_id)
    if user_id:
        bot.send_message(user_id, f"❌ Transaction `{txn_id}` rejected. Please contact support.", parse_mode="Markdown")

# === START POLLING ===

print("🤖 Bot is running...")
try:
    bot.polling(none_stop=True)
except Exception as e:
    print(f"🔥 Bot crashed! Error: {e}")
    time.sleep(5)

