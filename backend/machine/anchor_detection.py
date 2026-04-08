import pandas as pd

df = pd.read_csv('/Users/alexoddsh/prosperity/backend/databook/round_0/prices_round_0_day_-2.csv', sep=';')
df = df[df["product"] == "TOMATOES"].copy()

# At each timestep, record the full top-of-book state
df['spread'] = df['ask_price_1'] - df['bid_price_1']
df['mid'] = (df['ask_price_1'] + df['bid_price_1']) / 2

# Key insight: normalize everything relative to mid
# If there's an anchor MM, their quotes should appear as
# consistent OFFSETS from mid, not consistent absolute prices
df['bid_offset'] = df['bid_price_1'] - df['mid']  # should cluster at e.g. -1
df['ask_offset'] = df['ask_price_1'] - df['mid']  # should cluster at e.g. +1

#check size consistency
print(df['bid_volume_1'].value_counts().head(10))
print(df['ask_volume_1'].value_counts().head(10))
print(df['spread'].value_counts().head(10))