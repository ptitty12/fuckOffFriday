from datetime import datetime, timedelta
import json
import requests
import pandas as pd
from database import update_productivity

def fetch_historical_trends(companies):
    """
    Fetch historical trends for multiple companies and combine into a single DataFrame
    """
    url = "https://api.dataforseo.com/v3/keywords_data/google_trends/explore/live"
    headers = {
        'Authorization': 'Basic cGF0cmljay50YXlsb3JAaHVza2Vycy51bmwuZWR1OmVmOTFmN2U0YjMwZTIxMzA=',
        'Content-Type': 'application/json'
    }

    # Dictionary to store results for each company
    all_data = {}
    sub_ninety = datetime.today() - timedelta(days=90) #today minus ninety days
    # Fetch data for each company
    for company in companies:

        payload = json.dumps([{
            "date_from": sub_ninety.date().isoformat(),
            "date_to": datetime.today().date().isoformat(),
            "keywords": [company],
            "location_code": 2840,
            "language_code": "en"
        }])

        response = requests.post(url, headers=headers, data=payload)
        data = response.json()
        # Extract time series data
        try:
            time_series = data['tasks'][0]['result'][0]['items'][0]['data']
            # Store as {date: value} for this company
            all_data[company] = {item['date_to']: item['values'][0] for item in time_series}
        except (KeyError, IndexError) as e:
            print(f"Error processing data for {company}: {e}")
            continue

    # Create a DataFrame with dates as index
    dates = sorted(set().union(*[d.keys() for d in all_data.values()]))
    df = pd.DataFrame(index=dates)

    # Add each company's data as a column
    for company in companies:
        if company in all_data:
            df[company] = df.index.map(all_data[company].get)

    # Reset index to make date a column
    df.reset_index(names=['date'], inplace=True)

    # Convert date to datetime
    df['date'] = pd.to_datetime(df['date'])

    # Sort by date
    df = df.sort_values('date')

    return df

def turn_to_final_number(df,companies):
    df['Day'] = df['date'].apply(datetime.weekday)
    dayz = df.groupby(['Day']).median(numeric_only=True)
    td = df.sort_values(by='date').tail(1)
    val_current_day = td.reset_index().loc[0,'Day']
    j_df = td.join(dayz,on='Day',rsuffix='_median')
    j_df.reset_index(inplace=True)
    scores = []
    for company in companies:
        j_df[f'{company}_percent'] = (j_df[company]-j_df[f'{company}_median'])/j_df[f'{company}_median']
        scores.append(j_df.loc[0,f'{company}_percent'])

    final = sum(scores)/len(scores)
    return final

    #return turn_to_final_number(df,companies)
companies = ['Salesforce','Oracle','Workday']
df = fetch_historical_trends(companies)
df_time = df.copy()
df_time['average'] = df[companies].mean(axis=1)
#df.drop(columns=['average'],inplace=True) shoudln't be needed

fetch_historical_trends(companies)
# get number needs to take in the single number
update_productivity(get_number())