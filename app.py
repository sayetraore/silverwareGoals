from flask import Flask, request, jsonify, render_template
import sqlite3
from datetime import datetime
from cryptography.fernet import Fernet

import os
app = Flask(__name__, template_folder="templates")

# Generates a key ONCE and store it securely (Do not regenerate each time)
# key = Fernet.generate_key()
# print(key)  # Copy and replace 'YOUR_SECRET_KEY_HERE'

SECRET_KEY = b'3LmEiqWtxYPRmyB5m_NUcwrDN61jA5D9HxgkfJyvFiA='  #generated key
cipher_suite = Fernet(SECRET_KEY)

# Initialize the database
def init_db():
    conn = sqlite3.connect("times.db")
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS task_times (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT,
                        time_taken FLOAT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                     )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS earnings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT,
                        amount BLOB,
                        user_code BLOB,
                        date TEXT DEFAULT CURRENT_DATE,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                     )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS goals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        goal_amount FLOAT,
                        start_date TEXT DEFAULT CURRENT_DATE
                     )''')

    conn.commit()
    conn.close()

init_db()

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/submit_time", methods=["POST"])
def submit_time():
    data = request.json
    name = data.get("name")
    time_taken = data.get("time_taken")

    if not name or not time_taken:
        return jsonify({"error": "Missing data"}), 400

    conn = sqlite3.connect("times.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO task_times (name, time_taken) VALUES (?, ?)", (name, time_taken))
    conn.commit()
    conn.close()

    return jsonify({"message": "Time logged successfully!"})

@app.route("/leaderboard")
def leaderboard():
    conn = sqlite3.connect("times.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name, time_taken FROM task_times ORDER BY time_taken ASC LIMIT 10")
    results = cursor.fetchall()
    conn.close()

    ranked_results = [{"rank": i+1, "name": row[0], "time": row[1]} for i, row in enumerate(results)]
    return jsonify(ranked_results)

@app.route("/log_earnings", methods=["POST"])
def log_earnings():
    data = request.json
    name = data.get("name")
    amount = str(data.get("amount")).encode()  # Convert to bytes
    user_code = data.get("user_code").encode()  # Convert private code to bytes

    if not name or not amount or not user_code:
        return jsonify({"error": "Missing data"}), 400

    encrypted_amount = cipher_suite.encrypt(amount)  # Encrypt earnings
    encrypted_code = cipher_suite.encrypt(user_code)  # Encrypt private code

    conn = sqlite3.connect("times.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO earnings (name, amount, user_code) VALUES (?, ?, ?)", 
                   (name, encrypted_amount, encrypted_code))
    conn.commit()
    conn.close()

    return jsonify({"message": "Earnings logged securely!"})

@app.route("/earnings_history", methods=["POST"])
def earnings_history():
    data = request.json
    user_code = data.get("user_code").encode()  # Convert input to bytes

    conn = sqlite3.connect("times.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name, amount, user_code, date FROM earnings")
    results = cursor.fetchall()
    conn.close()

    decrypted_results = []
    for row in results:
        name, encrypted_amount, encrypted_code, date = row

        try:
            decrypted_code = cipher_suite.decrypt(encrypted_code).decode()  # Decrypt private code
            if decrypted_code == data.get("user_code"):  # Check if the entered code matches
                decrypted_amount = cipher_suite.decrypt(encrypted_amount).decode()  # Decrypt earnings
                decrypted_results.append((name, decrypted_amount, date))
        except:
            continue  # If decryption fails, ignore this row

    return jsonify(decrypted_results)

@app.route("/set_goal", methods=["POST"])
def set_goal():
    data = request.json
    goal_amount = data.get("goal_amount")

    if not goal_amount:
        return jsonify({"error": "Missing goal amount"}), 400

    conn = sqlite3.connect("times.db")
    cursor = conn.cursor()

    cursor.execute("DELETE FROM goals")
    cursor.execute("INSERT INTO goals (goal_amount) VALUES (?)", (goal_amount,))
    conn.commit()
    conn.close()

    return jsonify({"message": "Goal set successfully!"})

@app.route("/goal_progress", methods=["POST"])
def goal_progress():
    data = request.json
    user_code = data.get("user_code").encode()  # Convert input to bytes

    conn = sqlite3.connect("times.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name, amount, user_code FROM earnings")
    results = cursor.fetchall()
    conn.close()

    total_earnings = 0
    for row in results:
        name, encrypted_amount, encrypted_code = row

        try:
            decrypted_code = cipher_suite.decrypt(encrypted_code).decode()
            if decrypted_code == data.get("user_code"):  # Only show if code matches
                decrypted_amount = float(cipher_suite.decrypt(encrypted_amount).decode())
                total_earnings += decrypted_amount
        except:
            continue

    conn = sqlite3.connect("times.db")
    cursor = conn.cursor()
    cursor.execute("SELECT goal_amount FROM goals ORDER BY id DESC LIMIT 1")
    goal = cursor.fetchone()
    goal_amount = goal[0] if goal else 0
    conn.close()

    progress = (total_earnings / goal_amount) * 100 if goal_amount > 0 else 0

    return jsonify({"total_earnings": total_earnings, "goal_amount": goal_amount, "progress": progress})


@app.route("/earnings_trends", methods=["POST"])
def earnings_trends():
    data = request.json
    user_code = data.get("user_code").encode()

    conn = sqlite3.connect("times.db")
    cursor = conn.cursor()
    cursor.execute("SELECT date, amount, user_code FROM earnings")
    results = cursor.fetchall()
    conn.close()

    weekly_data = {}
    monthly_data = {}

    for row in results:
        date, encrypted_amount, encrypted_code = row

        try:
            decrypted_code = cipher_suite.decrypt(encrypted_code).decode()
            if decrypted_code == data.get("user_code"):
                amount = float(cipher_suite.decrypt(encrypted_amount).decode())

                # Accumulate earnings for weekly and monthly charts
                weekly_data[date] = weekly_data.get(date, 0) + amount
                monthly_data[date] = monthly_data.get(date, 0) + amount
        except:
            continue

    # Convert dictionary to sorted list (grouped earnings)
    weekly_earnings = sorted(weekly_data.items())
    monthly_earnings = sorted(monthly_data.items())

    return jsonify({"weekly": weekly_earnings, "monthly": monthly_earnings})


if __name__ == "__main__":
    app.run(debug=True)
