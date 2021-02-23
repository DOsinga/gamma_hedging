import math
import os
import random
import time
import pandas as pd

import alpaca_trade_api as tradeapi
from alpaca_trade_api.rest import APIError

SECRET = 'dTBPPmsaGrpNXih2H0Ha9qbiTPjmtMp9qhzZ4TLL'
KEY = 'PKZ7KQH2TG87Y0D5D2ZU'
END_POINT = 'https://paper-api.alpaca.markets'

NEUTRAL_SYMBOL = 'SPY'
MINUTE = 60
SP500_FILE = 'sp500.txt'


def sell_all(api):
    api.cancel_all_orders()
    api.close_all_positions()
    while True:
        open_orders = api.list_orders()
        if not open_orders:
            break
        print('waiting...')
        time.sleep(0.25)


def go_squeeze(api, sp500):
    sell_all(api)
    all_tickers = [t for t in api.polygon.all_tickers() if t.ticker in sp500]
    tickers = sorted(
        all_tickers,
        key=lambda t: (t.lastTrade['p'] - t.prevDay['c'])
        / max(t.lastTrade['p'], t.prevDay['c']),
    )
    cash = float(api.get_account().cash)
    budget = cash / 20
    while cash > 0:
        ticker = tickers.pop()
        price = ticker.lastTrade['p']
        qty = budget / price
        qty_rounded = int(math.floor(qty))
        if random.random() < qty - qty_rounded:
            qty_rounded += 1
        print('buying', ticker.ticker, qty_rounded)
        try:
            api.submit_order(
                symbol=ticker.ticker,
                qty=qty_rounded,
                side='buy',
                type='market',
                time_in_force='gtc',
            )
            cash -= price * qty_rounded
        except APIError as ae:
            print(ticker, ae)


def go_neutral(api, buy_neutral=False):
    positions = api.list_positions()
    print('Liquidating positions')
    for position in positions:
        qty = abs(int(float(position.qty)))
        print('', position.symbol, qty)
    sell_all(api)
    cash = float(api.get_account().cash)
    print('Cash:', cash)
    if buy_neutral:
        spy = api.polygon.last_quote(NEUTRAL_SYMBOL)
        to_buy = int(math.floor(cash / spy.askprice))
        api.submit_order(
            symbol=('%s' % NEUTRAL_SYMBOL),
            qty=to_buy,
            side='buy',
            type='market',
            time_in_force='gtc',
        )


def trade(api, sp500):
    last_time = None
    while True:
        clock = api.get_clock()
        seconds_to_close = (clock.next_close - clock.timestamp).seconds
        if seconds_to_close < 120:
            go_neutral(api)
            time.sleep(2 * MINUTE)
        elif 29 * MINUTE < seconds_to_close < 31 * MINUTE:
            go_squeeze(api, sp500)
            time.sleep(3 * MINUTE)
        else:
            cur_time = seconds_to_close // 900
            if cur_time != last_time and cur_time <= 6:
                print(cur_time / 4, 'hours until market close')
                last_time = cur_time
            time.sleep(20)


def get_sp500():
    if os.path.isfile(SP500_FILE):
        sp500 = open(SP500_FILE).read().splitlines()
    else:
        table = pd.read_html(
            'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        )
        df = table[0]
        sp500 = [*df['Symbol']]
        with open(SP500_FILE, 'w') as fout:
            fout.write('\n'.join(sp500) + '\n')
    return sp500


def main():
    sp500 = set(get_sp500())
    api = tradeapi.REST(key_id=KEY, secret_key=SECRET, base_url=END_POINT)
    trade(api, sp500)
    #go_neutral(api)
    #go_squeeze(api, sp500)


if __name__ == '__main__':
    main()
