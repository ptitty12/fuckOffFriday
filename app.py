from flask import Flask, render_template, jsonify
from database import get_latest_productivity
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




if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)