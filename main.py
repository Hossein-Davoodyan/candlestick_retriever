import os
import time
from datetime import date, datetime, timedelta

import requests
import pandas as pd

LABELS = [
    'open_time',
    'open',
    'high',
    'low',
    'close',
    'volume',
    'close_time',
    'quote_asset_volume',
    'number_of_trades',
    'taker_buy_base_asset_volume',
    'taker_buy_quote_asset_volume',
    'ignore'
]

def get_batch(symbol, interval, start_time=0, limit=1000):
    """get as many candlesticks as possible in one go"""

    params = {
        'symbol': symbol,
        'interval': interval,
        'startTime': start_time,
        'limit': limit
    }
    try:
        response = requests.get('https://api.binance.com/api/v3/klines', params)
    except requests.exceptions.ConnectionError:
        print('Cooling down for 5 mins...')
        time.sleep(5 * 60)
        return get_batch(symbol, interval, start_time, limit)
    if response.status_code == 200:
        return pd.DataFrame(response.json(), columns=LABELS)
    print(f'Got erroneous response back: {response}')
    return None


def all_candles_to_csv(base='BTC', quote='USDT', interval='1m'):
    """
    collect a list of candlestick batches with all candlesticks of a trading pair,
    concat into a dataframe and write it to csv
    """

    # see if there is any data saved already
    batches = []
    try:
        batches.append(pd.read_csv(f'data/{base}-{quote}.csv'))
        last_timestamp = batches[-1].iloc[-1, 0]
    except FileNotFoundError:
        batches.append(pd.DataFrame([], columns=LABELS))
        last_timestamp = 0

    # gather all batches available, starting from the last timestamp saved or 0
    # stop if the timestamp that comes back from the api is the same as the last one saved
    previous_timestamp = None
    if date.fromtimestamp(last_timestamp / 1000) < date.today():
        while previous_timestamp != last_timestamp:
            previous_timestamp = last_timestamp

            batches.append(get_batch(
                symbol=base+quote,
                interval=interval,
                start_time=last_timestamp
            ))

            last_timestamp = batches[-1].iloc[-1, 0]
            last_datetime = datetime.fromtimestamp(last_timestamp / 1000)

            covering_spaces = 20 * ' '
            print(base, quote, interval, str(last_datetime)+covering_spaces, end='\r', flush=True)

    # in the case that new data was gathered write it to a csv file
    if len(batches) > 1:
        df = pd.concat(batches, ignore_index=True)
        df.to_csv(f'data/{base}-{quote}.csv', index=False)
        return True

if __name__ == '__main__':
    # do a full update on all currency pairs that have BTC as their quote currency
    for pair in requests.get('https://api.binance.com/api/v3/exchangeInfo').json()['symbols']:
        if pair['quoteAsset'] == 'BTC':
            if all_candles_to_csv(base=pair['baseAsset'], quote=pair['quoteAsset']) is True:
                print(f'Wrote new candles to file for {pair["symbol"]}')
            else:
                print(f'Already up to date with {pair["symbol"]}')

    # clean the data folder and upload a new version of the dataset to kaggle
    try:
        os.remove('data/.DS_Storee')
    except FileNotFoundError:
        pass
    YESTERDAY = date.today() - timedelta(days=1)
    os.system(f'kaggle datasets version -p data/ -m "full update up till {str(YESTERDAY)}"')
