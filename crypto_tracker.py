import requests
import time
import os
import csv
import random

# API URLs
API_URL = "https://api.coingecko.com/api/v3/simple/price"
MARKET_API_URL = "https://api.coingecko.com/api/v3/coins/markets"
FEAR_GREED_API = "https://api.alternative.me/fng/"
NEWS_API = "https://api.binance.com/api/v3/news"
HEADERS = {"User-Agent": "Mozilla/5.0"}

portfolio = {}
price_alerts = {}
refresh_rate = 10  # Default refresh rate in seconds


def get_crypto_price(crypto):
    """Fetch the current price of a cryptocurrency."""
    try:
        params = {"ids": crypto, "vs_currencies": "usd"}
        response = requests.get(API_URL, params=params, headers=HEADERS).json()
        return response.get(crypto, {}).get("usd", "N/A")
    except:
        return "Error fetching data"


def get_top_cryptos():
    """Fetch top 10 cryptos by market cap."""
    try:
        params = {"vs_currency": "usd", "order": "market_cap_desc", "per_page": 10, "page": 1}
        response = requests.get(MARKET_API_URL, params=params, headers=HEADERS).json()
        return [(coin["name"], coin["current_price"]) for coin in response]
    except:
        return []


def get_fear_greed_index():
    """Fetch the current Crypto Fear & Greed Index."""
    try:
        response = requests.get(FEAR_GREED_API, headers=HEADERS).json()
        return response["data"][0]["value"], response["data"][0]["value_classification"]
    except:
        return "N/A", "Error fetching data"


def get_crypto_news():
    """Fetch the latest crypto news headlines."""
    try:
        response = requests.get(NEWS_API, headers=HEADERS).json()
        news_list = [news["title"] for news in response[:5]]
        return news_list
    except:
        return ["Error fetching news"]


def predict_price():
    """A simple AI-based price prediction (randomized for now)."""
    crypto = input("Enter crypto name (e.g., bitcoin): ").strip().lower()
    current_price = get_crypto_price(crypto)
    if current_price == "N/A":
        print("Error fetching price. Try again!")
        return
    
    trend_factor = random.uniform(-5, 5)  # Randomized trend factor
    predicted_price = round(current_price * (1 + trend_factor / 100), 2)
    print(f"📈 AI Prediction: {crypto.capitalize()} might hit ${predicted_price} soon!")


def add_to_portfolio():
    """Add crypto holdings to track in the portfolio."""
    crypto = input("Enter crypto name (e.g., bitcoin): ").strip().lower()
    amount = float(input(f"Enter the amount of {crypto} you own: "))
    portfolio[crypto] = portfolio.get(crypto, 0) + amount
    print(f"✅ {amount} {crypto} added to your portfolio!")


def view_portfolio():
    """Display the total portfolio value."""
    total_value = 0
    print("\n📊 Your Portfolio:")
    for crypto, amount in portfolio.items():
        price = get_crypto_price(crypto)
        if price != "N/A":
            value = amount * price
            total_value += value
            print(f"- {crypto.capitalize()}: {amount} coins = ${value:.2f}")
    print(f"\n💰 Total Portfolio Value: ${total_value:.2f}\n")


def export_portfolio():
    """Export portfolio to a CSV file."""
    with open("portfolio.csv", "w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["Crypto", "Amount", "Current Price (USD)", "Total Value (USD)"])
        for crypto, amount in portfolio.items():
            price = get_crypto_price(crypto)
            value = amount * price if price != "N/A" else "N/A"
            writer.writerow([crypto.capitalize(), amount, price, value])
    print("✅ Portfolio exported to 'portfolio.csv'!")


def set_price_alert():
    """Set price alerts for a specific cryptocurrency."""
    crypto = input("Enter crypto name (e.g., bitcoin): ").strip().lower()
    target_price = float(input(f"Enter target price for {crypto} (USD): "))
    price_alerts[crypto] = target_price
    print(f"🚨 Alert set: Notify when {crypto} hits ${target_price}")


def check_price_alerts():
    """Check if any price alerts have been triggered."""
    for crypto, target_price in price_alerts.items():
        current_price = get_crypto_price(crypto)
        if current_price != "N/A" and current_price >= target_price:
            print(f"🔥 ALERT! {crypto.capitalize()} has reached ${current_price} (Target: ${target_price})")


def main():
    global refresh_rate
    os.system("cls" if os.name == "nt" else "clear")
    print("🔹 Ultimate Crypto CLI Tool 🔹\n")

    while True:
        print("\n🔝 Top 10 Cryptos by Market Cap:")
        for name, price in get_top_cryptos():
            print(f"{name}: ${price}")

        fear_greed_value, sentiment = get_fear_greed_index()
        print(f"\n🧠 Crypto Market Sentiment: {sentiment} ({fear_greed_value}/100)")

        print("\n📰 Latest Crypto News:")
        for news in get_crypto_news():
            print(f"- {news}")

        print("\n📌 Options:")
        print("1️⃣ Search for a crypto price")
        print("2️⃣ Add to portfolio")
        print("3️⃣ View portfolio")
        print("4️⃣ Export portfolio to CSV")
        print("5️⃣ Set price alert")
        print("6️⃣ AI Crypto Price Prediction")
        print("7️⃣ Change Auto-Refresh Time")
        print("8️⃣ Exit")

        choice = input("\nSelect an option: ").strip()

        if choice == "1":
            crypto = input("Enter crypto name (e.g., bitcoin): ").strip().lower()
            price = get_crypto_price(crypto)
            print(f"\n{crypto.capitalize()}: ${price}")
        elif choice == "2":
            add_to_portfolio()
        elif choice == "3":
            view_portfolio()
        elif choice == "4":
            export_portfolio()
        elif choice == "5":
            set_price_alert()
        elif choice == "6":
            predict_price()
        elif choice == "7":
            refresh_rate = int(input("Enter new refresh time (seconds): "))
            print(f"🔄 Refresh rate set to {refresh_rate} seconds.")
        elif choice == "8":
            print("🚀 Exiting... Happy Trading!")
            break

        check_price_alerts()
        print(f"\nRefreshing in {refresh_rate} seconds... Press Ctrl+C to exit.")
        time.sleep(refresh_rate)
        os.system("cls" if os.name == "nt" else "clear")


if __name__ == "__main__":
    main()
