from flask import Flask, render_template, request, redirect
import sqlite3

app = Flask(__name__)

# Function to fetch transactions from DB
def get_transactions():
    conn = sqlite3.connect("transactions.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM transactions")
    data = cursor.fetchall()
    conn.close()
    return data

# Function to update transaction status
def update_transaction_status(transaction_id):
    conn = sqlite3.connect("transactions.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE transactions SET status = 'Completed' WHERE id = ?", (transaction_id,))
    conn.commit()
    conn.close()

@app.route("/")
def dashboard():
    transactions = get_transactions()
    return render_template("dashboard.html", transactions=transactions)

@app.route("/confirm/<int:transaction_id>")
def confirm_transaction(transaction_id):
    update_transaction_status(transaction_id)
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)
