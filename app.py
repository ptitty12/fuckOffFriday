from flask import Flask, render_template, jsonify
from database import get_latest_productivity,get_latest_productivity_series
import pandas as pd
from datetime import datetime

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/productivity')
def get_productivity():
    value = get_latest_productivity()
    return jsonify({'value': value})

@app.route('/api/productivity_series')
def get_productivity_series():
    df = get_latest_productivity_series()
    # Add debug print
    data = df.to_dict()['value']
    data = {k.strftime('%Y-%m-%d'): v for k, v in data.items()}
    return jsonify({'value': data})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)