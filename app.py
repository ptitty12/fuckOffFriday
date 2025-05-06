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
    df = get_latest_productivity_series()
    # ensure datetime index
    if not pd.api.types.is_datetime64_any_dtype(df.index):
        df.index = pd.to_datetime(df.index)

    # tag weekday
    df['day_of_week'] = df.index.dayofweek

    # compute medians over non-zero history
    nonzero = df[df['value'] != 0]
    day_medians = nonzero.groupby('day_of_week')['value'].median()

    # percent change vs that weekday‐median
    df['percent_change'] = df.apply(
        lambda row: ((row['value'] / day_medians[row['day_of_week']]) - 1) * 100
                    if row['day_of_week'] in day_medians else 0,
        axis=1
    )

    # pick the most recent date in the series
    latest_date = df.index.max()
    latest_pct  = df.loc[latest_date, 'percent_change']

    # return a plain percent (e.g. 5.23)
    return jsonify({'value': round(latest_pct, 2)})


@app.route('/api/productivity_series')
def get_productivity_series():
    df = get_latest_productivity_series()
    # Convert index to datetime if it's not already
    if not pd.api.types.is_datetime64_any_dtype(df.index):
        df.index = pd.to_datetime(df.index)
    df['day_of_week'] = df.index.dayofweek
    
    # Calculate the median value for each day of the week
    day_medians = df.groupby('day_of_week')['value'].median()
    
    # Calculate percent change compared to the median for the same day of week
    df['percent_change'] = df.apply(
        lambda row: ((row['value'] / day_medians[row['day_of_week']]) - 1) * 100,
        axis=1
    )
    
    # Convert the result to dictionary format
    result = {}
    for date, row in df.iterrows():
        date_str = date.strftime('%Y-%m-%d')
        result[date_str] = {
            'value': row['value'],
            'percent_change': round(row['percent_change'], 2)
        }
    df.drop(columns=['day_of_week'],inplace=True)


    return jsonify({'value': result})



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80085) #hahahah boobz