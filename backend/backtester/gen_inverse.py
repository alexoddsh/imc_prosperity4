import pandas as pd

normal_prices = pd.read_csv("/Users/alexoddsh/prosperity/backend/backtester/resources-4/round1/prices_round_1_day_0.csv", sep=";")
normal_trades = pd.read_csv("/Users/alexoddsh/prosperity/backend/backtester/resources-4/round1/trades_round_1_day_0.csv", sep=";")

cols = [c for c in normal_prices.columns if c != "timestamp"]
reverse_prices = normal_prices.copy()
reverse_prices[cols] = normal_prices[cols].values[::-1]

cols = [c for c in normal_trades.columns if c != "timestamp"]
reverse_trades = normal_trades.copy()
reverse_trades[cols] = normal_trades[cols].values[::-1]

price_cols = ['bid_price_1', 'bid_price_2', 'bid_price_3',
                      'ask_price_1', 'ask_price_2', 'ask_price_3']
volume_cols = ['bid_volume_1', 'bid_volume_2', 'bid_volume_3',
                'ask_volume_1', 'ask_volume_2', 'ask_volume_3']

dfs = [reverse_prices, reverse_trades]

for df in dfs:
    for col in price_cols:
        if col in df.columns:
            df[col] = df[col].fillna(0).astype('int32')
    for col in volume_cols:
        if col in df.columns:
            df[col] = df[col].fillna(0).astype('int16')


reverse_prices.to_csv("/Users/alexoddsh/prosperity/backend/backtester/resources-4/round1/prices_round_1_day_1.csv", index=False, sep=";")
reverse_trades.to_csv("/Users/alexoddsh/prosperity/backend/backtester/resources-4/round1/trades_round_1_day_1.csv", index=False, sep=";")