# database.py
import sqlite3
from datetime import datetime

def init_db():
    conn = sqlite3.connect('productivity.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS productivity
                 (date TEXT PRIMARY KEY, value REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS t_series
                (date TEXT PRIMARY KEY, value REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS snapshots
                (date TEXT, Salesforce REAL,Oracle REAL,Workday REAL,snapshot TEXT)''')
    conn.commit()
    conn.close()
def get_latest_productivity():
    """fetch productivity number"""
    conn = sqlite3.connect('productivity.db')
    c = conn.cursor()
    c.execute('SELECT value FROM productivity ORDER BY date DESC LIMIT 1')
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

def get_latest_productivity_series():
    """fetch productivity df return df"""
    conn = sqlite3.connect('productivity.db')
    c = conn.cursor()
    c.execute('SELECT date, value FROM t_series ORDER BY date')
    result = c.fetchall()  # Get all rows
    conn.close()
    
    # Convert to DataFrame
    import pandas as pd
    df = pd.DataFrame(result, columns=['date', 'value'])
    # Optionally set date as index
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date')
    
    return df

def update_productivity(value):
    """takes single value updates the database"""
    conn = sqlite3.connect('productivity.db')
    c = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    c.execute('INSERT OR REPLACE INTO productivity (date, value) VALUES (?, ?)',
              (today, value))
    conn.commit()
    conn.close()
def update_t_series(df):
    """takes in df formatted date, value, where value is named average"""
    conn = sqlite3.connect('productivity.db')
    c = conn.cursor()
    for _, row in df.iterrows():
        # Convert timestamp to string format
        date_str = row['date'].strftime('%Y-%m-%d')
        c.execute('INSERT OR REPLACE INTO t_series (date, value) VALUES (?, ?)',
                (date_str, row['average']))
    conn.commit()
    conn.close()
def update_snapshots(df):
    """takes in the literal snapshot that we get from the api
    should be date (likely index, then 'Salesforce','Oracle','Workday' in order)"""
    conn = sqlite3.connect('productivity.db')
    c = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    for _, row in df.iterrows():
        c.execute('INSERT into snapshots (date, Salesforce, Oracle, Workday, snapshot) VALUES (?,?,?,?,?)',(row['date'],row['Salesforce'],row['Oracle'],row['Workday'],today))
    conn.commit()
    conn.close()
init_db()