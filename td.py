from tda import auth
from tda.client import Client
from tda.orders.equities import equity_buy_market, equity_sell_market
import json
import platform
import time
from keys import buy, weights

with open('keys.json') as json_file:
    keys = json.load(json_file)

token_path = 'token.pickle'
api_key = keys['CONSUMER_KEY'] + '@AMER.OAUTHAP'
redirect_uri = keys['CALLBACK_URL']

try:
    c = auth.client_from_token_file(token_path, api_key)
except FileNotFoundError:
    from selenium import webdriver
    if 'Microsoft' in platform.release():
        with webdriver.Chrome(executable_path='../chromedriver.exe') as driver:
            c = auth.client_from_login_flow(driver, api_key, redirect_uri, token_path)
    else:
        with webdriver.Chrome(executable_path='../chromedriver') as driver:
            c = auth.client_from_login_flow(driver, api_key, redirect_uri, token_path)

positionsField = Client.Account.Fields('positions')
account = c.get_account(keys['ACCOUNT_NUMBER'], fields=positionsField).json()

accountId = account['securitiesAccount']['accountId']
liquidationValue = account['securitiesAccount']['currentBalances']['liquidationValue']
positions = account['securitiesAccount'].get('positions', [])
positions = {position['instrument']['symbol']: int(position['longQuantity']) for position in positions}
totalCash = account['securitiesAccount']['currentBalances']['totalCash']

# sell old positions
for stock in positions:
    if stock not in buy:
        print('Sell:', stock, positions[stock])
        c.place_order(
            keys['ACCOUNT_NUMBER'],
            equity_sell_market(stock, positions[stock])
                .build())

# get positions prices
positions_prices = {}
for stock in buy:
    r = c.get_quote(stock)
    response = r.json()
    stockPrice = response[stock]['lastPrice']
    print(stock, stockPrice)
    positions_prices[stock] = stockPrice
    time.sleep(1)

positions_prices = list(positions_prices.items())
positions_prices.sort(key = lambda x: -x[1])

if not weights or len(weights) != len(buy):
    weights = [1] * len(positions_prices)
weights = dict(zip(buy, weights))

# # balance positions
for i, (stock, price) in enumerate(positions_prices):
    if i == len(positions_prices) - 1:
        print('Last:', stock)
        continue
    price /= weights[stock]
    if i == len(positions_prices) - 1:
        cant = int(liquidationValue / (price * (len(positions_prices) - i)))
    else:
        cant = round(liquidationValue / (price * (len(positions_prices) - i)))
    liquidationValue -= price * cant
    cant = cant - positions.get(stock, 0)
    print(stock, cant)
    if cant > 0:
        c.place_order(
            keys['ACCOUNT_NUMBER'],
            equity_buy_market(stock, cant)
                .build())
    elif cant < 0:
        c.place_order(
            keys['ACCOUNT_NUMBER'],
            equity_sell_market(stock, -cant)
                .build())
    time.sleep(1)
