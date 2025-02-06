#!/usr/bin/env python3
from database import (
    update_productivity, update_t_series
)
from cron import fetch_historical_trends, turn_to_final_number
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(
    filename='productivity_update.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def main():
    try:
        logging.info("Starting productivity update")
        
        companies = ['Salesforce', 'Oracle', 'Workday']
        
        # Fetch and process data
        df = fetch_historical_trends(companies)
        df_time = df.copy()
        df_time['average'] = df[companies].mean(axis=1)
        foo = turn_to_final_number(df, companies)
        
        # Update database
        update_productivity(foo)
        update_t_series(df_time)
        
        logging.info("Successfully completed productivity update")
    
    except Exception as e:
        logging.error(f"Error in productivity update: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main()
