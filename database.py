import sqlite3
def get_db():
    conn = sqlite3.connect("payease.db")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    #user table
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS users ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "full_name TEXT NOT NULL,"
        "email TEXT NOT NULL UNIQUE,"
        "phone TEXT NOT NULL UNIQUE,"
        "password TEXT NOT NULL,"
        "pin TEXT NOT NULL,"
        "created_at TEXT DEFAULT (datetime('now'))"
        ")"
    )
    #wallet table
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS wallets ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "user_id INTEGER NOT NULL REFERENCES users(id),"
        "wallet_number TEXT NOT NULL UNIQUE,"
        "balance REAL NOT NULL DEFAULT 0.00,"
        "created_at TEXT DEFAULT (datetime('now'))"
        ")"
    )
    #transaction table
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS transactions ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "from_wallet TEXT,"
        "to_wallet TEXT,"
        "amount REAL NOT NULL,"
        "type TEXT NOT NULL,"
        "status TEXT DEFAULT 'success',"
        "description TEXT,"
        "created_at TEXT DEFAULT (datetime('now'))"
        ")"
    )
    #bills table
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS bills ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "user_id INTEGER NOT NULL REFERENCES users(id),"
        "bill_type TEXT NOT NULL,"
        "provider TEXT NOT NULL,"
        "amount REAL NOT NULL,"
        "status TEXT DEFAULT 'pending',"
        "paid_at TEXT"
        ")"
    )

    conn.commit()
    conn.close()
    print("Database ready!")