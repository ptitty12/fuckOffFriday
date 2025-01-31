# database.py
import sqlite3
from datetime import datetime

def init_db():
    conn = sqlite3.connect('productivity.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS productivity
                 (date TEXT PRIMARY KEY, value REAL)''')
    conn.commit()
    conn.close()

def get_latest_productivity():
    conn = sqlite3.connect('productivity.db')
    c = conn.cursor()
    c.execute('SELECT value FROM productivity ORDER BY date DESC LIMIT 1')
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

def update_productivity(value):
    conn = sqlite3.connect('productivity.db')
    c = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    c.execute('INSERT OR REPLACE INTO productivity (date, value) VALUES (?, ?)',
              (today, value))
    conn.commit()
    conn.close()


init_db()