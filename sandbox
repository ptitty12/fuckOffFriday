import requests


def fetch_api_results(company):
    """Takes a company name and returns last 90 days in US english"""
    url = "https://api.dataforseo.com/v3/keywords_data/google_trends/explore/live"
    
    payload = f'[{{"time_range":"past_90_days", "keywords":["{company}"], "location_code":2840, "language_code":"en"}}]'
    headers = {
        'Authorization': 'Basic cGF0cmljay50YXlsb3JAaHVza2Vycy51bmwuZWR1OmVmOTFmN2U0YjMwZTIxMzA=',
        'Content-Type': 'application/json'
    }
    response = requests.request("POST", url, headers=headers, data=payload)
    return response
    #print(response.text)


import requests
import json
import pandas as pd
from datetime import datetime

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
    
    # Fetch data for each company
    for company in companies:
        payload = json.dumps([{
            "date_from": "2024-09-01",
            "date_to": "2024-12-31",
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

# Example usage:
df = fetch_historical_trends(companies)




import json

me = last_90['Salesforce'].text


import json
import pandas as pd

import json
import pandas as pd

def parse_trends_data(json_str):
    """Convert trends data to DataFrame with date, value, and day of week."""
    # Parse JSON string
    data = json.loads(json_str.replace("'", '"').replace("None", "null").replace("True", "true").replace("False", "false"))
    
    # Extract the time series data
    time_series = data['tasks'][0]['result'][0]['items'][0]['data']
    
    # Create DataFrame
    df = pd.DataFrame([
        {'date': item['date_to'], 'value': item['values'][0]}
        for item in time_series
    ])
    
    # Convert date column to datetime
    df['date'] = pd.to_datetime(df['date'])
    
    # Add day of week
    df['day_of_week'] = df['date'].dt.day_name()
    
    return df

df = parse_trends_data(me)
