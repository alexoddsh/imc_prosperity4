## Prosperity 1
### **Round 1**
Pearls: <br>
market-making, 10k stable price <br><br>
Bananas: <br>
market-making but less stable price, LR trends on last few ticks linear-ish across days (e.g. LR coefs day 2 more similar to coefs day 1 compared to say day 0 etc.)
> For bananas, we ran a linear regression on the last few timesteps of banana prices to predict the next price. Using this to market-take worked reasonably, and market-making along with market-taking worked quite well. We tried to implement LR-on-the-fly, but this didn't work as well (and with the Lambda error bugs that were prevalent through the competition, it was for the best to skip this approach). We noticed that the banana trends were linear-ish across days (ie, day 2 was more similar to day 1 in LR coefficients than day -1 and so on), which could give an additional boost in PnL.

### **Round 2**
Coconuts & Pina-Coladas: <br>
no context yet other than the fact that pairs-trading worked.
> For the Coconuts/Pina Coladas, Konstantin wrote up code to perform pair-trading (arbitraging pina colada - 15/8 * coconut);

### **Round 3**
Berries & Diving Gear: <br>
ideas seem to be trying hardcoded checks based on market direction at intervals, but much more interestingly that the observations actually had some predictive value
> for Berries and Diving Gear, which seemed to work reasonably. The ideas were as follows: For berries, he hardcoded some values of the curve (buy at timestamp 350k, sell at 500k, either buy or sell at 750k depending on the overall day's trend). For diving gear, he noticed that Dolphin sightings would increase or decrease by a huge amount (+-5 or higher) if there was a true signal; a small change such as +-2 from the last dolphin sighting was very likely noise.

### **Round 4**
Picnic Basket (dip, baguette, ukulele): <br>
simple ETF arbitrage of the basket againt its underlying, not clear whether allowed to convert. <br>
interestingly, assumed a fixed premium between the basket and the constituents
> For the Picnic basket group, we decided to use the same pair trading strategy, assuming that the basket had a premium of 375$ attached to it (ie, arbitraging picnic basket - 4 * dip - 2 * baguette - ukulele - 375), and fine-tune this.

### **Round 5**
> this meant that the price of all the products were a leading indicator for the future price of picnic baskets, which made sense. Therefore, we decided to only trade Picnic Baskets on the signal of (picnic basket - 4 * dip - 2 * baguette - ukulele - 375).

> same thing as point 1 for pina coladas and coconuts (ie, only trade pina coladas);

## Prosperity 2
### **Round 1**
Amethysts (stable, market-making): <br>
> we discovered that many profitable trades were prevented by our position limits, as we were unable to long or short more than 20 amethysts (and starfruit) at any given moment. To fix this our algorithm would do 0 ev trades, if available, just to get our position closer to 0, so that we'd be able to do more positive ev trades later on. This strategy bumped our pnl up by about 3%.

Starfruit: <br>
Similar to all other G2s, market-making and taking but follows a slow randow walk. As others have talked about, finding a stable estimate of the true value was crucial to trade this good.
>  Looking at the orderbook, we found out that, at all times, there was a market making bot quoting relatively large sizes on both sides, at prices that were unaffected by smaller participants. Using this market maker's mid price as a fair turned out to be much less noisy and generated more pnl in backtests.

So interestingly, their strategy seems a bit more refined than the Frankfurt WallMid, but they (maybe by accident) achieve the same thing. (!important for this year to verify by trading one lot and comparing PnL graph against our estimate)
<br>
They also mention that they grid-searched for the best params for starfruit (e.g. what edge to quote at), so it's worth investigating whether the edge you quote at has any significant impact on your fill-probability.
<br>
Similar to remarks for good 2 other years is that it is slightly mean-reverting, however it seems like many teams were unable to actually extract very much from this.

Manual:
> With a large school of goldfish visiting, an opportunity arises to acquire some top grade SCUBA_GEAR. You only have two chances to offer a good price. Each one of the goldfish will accept the lowest bid that is over their reserve price. You know there’s a constant desire for scuba gear on the archipelago. So, at the end of the round, you’ll be able to sell them for 1000 SeaShells ****a piece. Whilst not every goldfish has the same reserve price, you know the distribution of their reserve prices. The reserve price will be no lower than 900 and no higher than 1000. The probability scales linearly from 0 at 900 to most likely at 1000. You only trade with the goldfish. Bids of other participants will not affect your results.

### **Round 2**
Orchids: <br>
Premise being that these were produced on a different island, whereby they could be imported/exported subject to tariff and shipping costs. Also data that was hinted at being related, such as sunlightIndex and humidiy, but like other years, it was hard to find any meaningful pattern and the data was likely there as a distraction. <br>
The key insight was rather in the market microstructure itself, with there existing a large taker that would consume sell orders close to the best bid. Combined with low implied ask prices in the foreign market, this lead to a simple arbitrage opportunity of selling locally and buying foreign.
> We tested out different prices for sell orders in the local market, and found that using a price of foreign ask price - 2 worked best. However, with this fixed level for our sell orders, we worried about changes in the market preventing this level from being consistently filled. As such, we came up with an "adaptive edge" algorithm, which looked at how much volume we got at each iteration (with the maximum, nominal volume being 100 lots). If the average volume we received was below some threshold, we'd start moving our sell order level around, automatically searching for a new level to maximize profits.

> Puerto Vallarta, who seemed to have figured something out this round that no other teams could find.
"Luck" shouldn't help that much under the described conditions, implying that there's something more nuanced to find in these goods.

Manual: <br>
You get the chance to do a series of trades in some foreign island currencies. The first trade is a conversion of your SeaShells into a foreign currency, the last trade is a conversion from a foreign currency into SeaShells. Everything in between is up to you. Give some thought to what series of trades you would like to do, as there might be an opportunity to walk away with more shells than you arrived with.To anyone who has taken Linear Algebra (or has ChatGPT lol), this is a pretty straightforward matrix calculation. You can also bruteforce a solution by looping through the entire search space and printing the combination that gives the max profit. We finished this in about 5 minutes.

### **Round 3** <br>
Gift baskets (chocolates, roses, strawberries): <br>
really just the same ETF stat arb idea as other years. They first looked for leading/lagging relationships between the basked and the synthetic, but did not have that much success. The key idea was that the basket-synthetic spread oscillated around ~370, allowing a mean-reverting strategy involving buying the basked and selling the synthetic when spread was below average and vice versa when above average. <br>
The key problem became optimizing when to enter a trade based on the spread, since position limits and liquidity made it unattractive to simply just buy/sell when the spread crossed its average. First they simply backtested to optmisize hard-coded thresholds for when the deviation was attractive.
>  A more adaptive algorithm for spreads. We traded on a modified z-score, using a hardcoded mean and a rolling window standard deviation, with the window set relatively small. The idea behind this was that there should be a fundamental reason behind the mean of spread (think the price of the basket itself), but the volatility each day would be less predictable. Then, we thresholded the z-score, selling spreads when our z-score went above a certain value and buying when the z-score dropped below. By using a small window for our rolling standard deviation, we'd see our z-score spike when the standard deviation drastically dropped–and this would often happen right as the price started reverting, allowing us to trade closer to local minima/maxima.

<br>
From Cove Capital - So, we figured that even if it wasn't the main strategy, we might as well just trade the premium if it falls below or above the mean premium price. This strategy actually made us a lot of money and we started to believe that this was actually what we should be trading on, but because of that we started to overfit the data. We couldn't answer questions like:
- What price level should we buy/sell at?
- Should we perfectly hedge gift baskets with it's components?
- How do we actually calculate the mean gift basket price (rolling mean, set mean)?

Manual: <br>
You get to go on a maximum of three expeditions to search for treasure. Your first expedition is free, but the second and third one will come at a cost. You’ll have to split the spoils with all the others that search in the same spot. Every spot has its treasure multiplier (up to 100) and the number of hunters (up to 8). The spot's total treasure is the product of the base treasure (7500, same for all spots) and the spot's specific treasure multiplier. However, the resulting amount is then divided by the sum of the hunters and the percentage of all the expeditions (from other players) that took place there. For example, if a field has 5 hunters, and 10% of all the expeditions (from other players) are also going there, the prize you get from that field will be divided by 15. After the division, expedition costs apply (if there are any), and profit is what remains.

> We knew that there was only so much mathematics we could do and just had to rely on Discord sentimentfor how people would bet. We did an iteration simulator that showed the best options based on how deep people would go. For example, if everyone calculates the best values on face value and choose it, what should we choose. Then assume almost everyone just did that (an iteration) and will diverge like us - now what is the best option? We really couldn't come to a consensus so we ended up choosing the second best values and shipped it. Turns out a lot of people like the number 73 (one of the ones we chose) so one of our options was great, but 73 was really really bad (like the worst option).

- options we could look into here are pshychological number theory, but also the "what is the average guess from 0-100 problem"
- i'm fairly sure there are studies on how more educated and intelligent groups of people converge towards certain values vs. the average
- a thing to consider is whether people will go for the game theoretical optimum, and how many depths deeper than nominal we should predict

### **Round 4**
Coconuts and Coconut Coupons: <br>
This year there seemed to be only one call option, while prosperity 3 had calls at several strikes. One heuristic prediction is that this year will introduce more to this category, maybe introducing puts, or other derivatives like futures or swaps.
<br>
Their strategy was to use BSM to find that IV oscillated around 16%, and then trade mean-reversion on IV. This required hedging by buying coconuts, but since position limits were 300/600, and the delta stayed around 0.53, it was impossible to be fully hedged at the position limits. Gamma was low since the options were far away from expiry.

<br>
manual:
Goldfish are back with more SCUBA_GEAR. Each will have new reserve prices, follow the same distribution as in Round 1.
Options are similar to before with two chances to offer a good price. Each of the goldfish will accept the lowest bid that is over their reserve. But this time, for your second bid, they account for the average of the second bids by other traders. They’ll trade with you when your offer is above the average of all second bids. If you end up under the average, the probability of a deal decreases rapidly. To simulate this probability, the PNL obtained from trading with a fish for which your second bid is under the average of all second bids will be scaled by a factor p:
$$p=(1000 -\text{ average bid})/(1000 - \text{ your bid})$$

> This was similar to the first round and we thought that it is optimal for everyone to put the optimal values calculated from part 1, since average bid wouldn't matter and everyone would stay optimal. However, the cynics among us thought that around 10-20% of the competitors were bad actors or just wanted to take a risk that might pay off and put them higher. So, we estimated the average would be a little higher than optimal and set our optimal values based on that. Turns out we guessed perfectly!

### **Round 5**
The key idea here was to replicate the massive success of Puerto Vallarta, hypothesis being that they must've found some way to reasonably predict the future due to their massive gains. However linear regressions on synchronous and lagged returns across all days and symbols did not yield anything particularly interesting -- starfruits seemed to hold some lagged predictive power for other symbols. <br>
The insight here became that last year's similar products were near perfect predictors of this year's, for example diving gear returns from last year scaled by 3 was a near perfect predictor of roses this year ($R² = 0.99$). The key then became optimizing the extracted returns from this.
> To do this systematically across the three symbols we wanted to trade (roses, coconuts, and gift baskets, due to their natural correlation with roses), we developed a dynamic programming algorithm. Our algorithm took many factors into account–costs of crossing spread, the volume we could take at iteration (the volume on the orderbook), and our volume limits.
The motivation behind the complexity of our dp algorithm was the fact that, at each iteration, we couldn't necessarily achieve our full desired position–therefore, we needed a state for each potential position that we could feasibly achieve. A simple example of this is to imagine a product going through the following prices:8→7→12→10. With a position limit of 2, and with sufficient volume on the orderbook, the optimal trades would be: sell 2 -> buy 4 -> sell 4, with a pnl of 16. Now imagine if you could only buy/sell 2 shares at each iteration. Then, the optimal solution would change–you'd want to buy 2 -> buy 2 -> sell 2, with an overall pnl of 14.
- basically they used predictor prices, volume-pct (percent of volume limit in the book) and the spread (cost of each trade) to optimise

From cove capital: <br>
> The only thing we were sure about is that Rhianna (one of the bots) would trade Roses at it's min/max, so we changed our basket hedging a little bit such that when Rhianna traded, we would trade Roses to our max position possible in the direction she traded. Other than that, we were pretty confident everything else was just noise,

Manual:
You’ve been invited to trade on the exchange of the north archipelago for one day only. An exclusive event and perfect opportunity to make some big final profits before the champion is crowned. The penguins have granted you access to their trusted news source: Iceberg. You’ll find all the information you need right there. Be aware that trading these foreign goods comes at a price. The more you trade in one good, the more expensive it will get. This is the final stretch. Make it count!
> This manual felt like a gamble, it was just reading news and determining how you felt about it. It was tough recognizing that we were trading the products, not their stock, which changes your answer drastically. For example, this was ablurb for one of the products:
>> "PS6 numbers steady on the rise. Narwal Ninja Warrior biggest driver of success Last quarter's viewer numbers for the game show were just disclosed, after the market closed. Since the popular Narwal Ninja Warrior game show is a PeriScope 6 (PS6) exclusive, sales of the device have surged with a staggering 39%. User retention remained steady in comparison to last quarter, with an acceptable 1% drop."

***
## Prosperity 3
###**General ideas from 'What's the impact'** <br>
- backing out fair value estimation by trading one lot
- We found that there were serious flow imbalances in multiple products, typically with the aggressor persistently selling throughout the session. We hoped to find some directional information encoded in these flow imbalances, however, there was no sign that the signed volume had any impact on the price of the asset. This was something that confused (and frustrated) us massively throughout the rounds, until in Round 5 details of counterparties were released and we were able to fit a narrative to these trading patterns. We found that two parties were simply trading with each other, one of which was market making and the other was either consistently buying or selling from them. For example Pablo consistently sold options regardless of the price to Camilla, who was market making and profiting consistently from him crossing the spread (He was consistently selling the 10500 strike options to her for 0 seashells !).
- test the common ideas, find the signals, validate, then optimize execution (making or taking, different size and edge requirements could give big boosts in PnL)
-  Through testing liquidation rates (how quickly you could reach a max short/long position at different edge requirements) for different products, we were able to convert our execution into a simple optimisation problem, allowing us to determine an optimal trade size and edge requirement.

### **Round 1**
Rainforest Resin:  <br>
became optimally solvable as a DP problem under some mild assumptions. What's the impact basically just say that they did market-making and that they optimised edge requirements. <br>
The Frankfurt team does not have a lot to add in this regard, but they do use rainforest resin to describe how the market engine handles order flow: <br>
- at the start of a new timestamp, the simulation first cleared all existing orders
- then it sequentially processed new submissions, first some deep-liquidity makers, then occassionally some takers, then the participant's actions, lastly followed by other bots - usually takers
- thus throughout the competition, speed and order cancellation remained irrelevant
- however, as a heurestic prediction, it could be worth considering whether an innovation to prosperity for this year could be modelling time in a more complex manner, such that the market's state does not "freeze" in time while waiting for your actions, which would increase complexity significantly and also put emphasis on other mechanisms, but this is just a prediction
- on this topic, another potential innovation could be the implementation of more order types, in all editions of the competition so far, one could describe the orders as being limit orders that only live for one timestamp, but they could implement limit orders that remain on the book, or market order, fill and kill etc.
<br>
To conclude, the Frankfurt team kept a simple algo for resin, simply taking any immediately profitable trades, and then quoting 1 tick away from the highest level in the book. If inventory became too skewed, they flattened it at fair value (10000).
<br>
Kelp: <br>
For taking they simply took max liquidity for all directly profitable trades, and they also flattened at 0 edge whenever possible. If the book was only 1 CU away from fair, they simply placed themselves top of book. Tried optimising edge similarly to rainforest problem but then decided to keep it simple.
- interestingly, "Olivia" exhibited the same informed trader pattern for kelp as she did for squid ink, however due to the lower variance of kelp, impact did not find it very profitable to try and incorporate this into their strategy.
<br>
The Frankfurt team didn't find the informed trader pattern for Kelp, and employed basically exactly the same strategy for Kelp as they did for Resin, simply quoting around their "wallMid" indicator (which was just the mean of the worst ask and bid - which basically functioned like liquidity walls imposed by some informed market maker - teams had very slightly different ways of estimating this fair value but they all achieve basically the same result).

<br>
Squid Ink: <br>
More volatile and a tighter spread.
> the most obvious of which occurred on 2 out of the 3 days of data given to us, where the price exhibited a massive price spike before immediately reverting to its previous level. One of these spikes gapped down over 100 seashells before reverting, presenting an opportunity to profit over 10k seashells in only 2 timestamps.We initially implemented a strategy to capture this opportunity by tracking the price in the previous timestamp and comparing it with the current price (current price - previous price). If the difference was < -50 (an arbitrary number that we set) we would clear the offer, and if it was > +50 we would clear the bid on the orderbook.

Then towards the end of the round, a hint was dropped that ink was mean-reverting. "What's the impact" used Bollinger Bands to trade this, and grid-searched for the optimal params, but found no params that were profitable across all 3 days of training data, and the risk of overfitting was large. They ended up using very conservative standard deviation conditions, entering when the moving average crossed +/- 3 deviations, and liquidiating when it went back 1 deviation. It is unclear how profitable this was for them; leaderboards show that they finished good (around 120th place) in the first round, but this was far away from the Frankfurt team who found the informed trader pattern already in round 1.

Impact recognized the informed trader pattern when trader IDs were released in the last round, which they discuss as:
> Following her trades netted roughly 10k profit on average per day. This strategy was extremely easy to implement, however it was important that we didn’t miss out on her trades when the opportunity only lasted one timestamp. There were multiple days where the single timestamp spikes corresponded to the global max/min before immediately reverting. If we had implemented a strategy that only followed Olivia’s trades we wouldn’t have gotten the trade data until the timestamp after, when the trading opportunity was gone. In order to ensure that we didn’t miss these spikes we kept our logic that traded in max size if the price spiked up or down in a single timestamp, regardless what position Olivia had on. Once the price had spiked we waited a small period before putting on the same position that Olivia had on. This strategy actually meant that we outperformed Olivia on days where the single timestamp spikes didn’t correspond to the global extrema.

<br>
Now Squid Ink is one of the products where the teams actually differed in their approaches during earlier rounds. The Frankfurt team found the informed trader pattern for Squid Ink in the first round. Their final strategy did not involve any active market-making or mean-reversion trading.
> he general approach involved tracking the daily running minimum and maximum. When a trade occurred at a daily extreme — and in the expected direction relative to the mid price — we flagged it as a signal and positioned accordingly. False positives were managed by monitoring for corresponding new extrema that contradicted earlier signals. Our final strategy for Squid Ink focused purely on following this daily-extrema trading behavior, dynamically updating our positions based on detected trades and resetting when invalidations occurred.

### **Round 2** <br>
Picnic Baskets (Croissants, Jams, Djembes): <br>
Impact don't talk about their ETF stat-arb explicitly but likely followed similar strategies to others. <br>
Interestingly, my interpretation of the baskets across prosperity editions is that have never been directly convertable to the underlying, and that an update from Prosperity 2 and onward was having 2 baskets rather than just 1. This leaves some room to theorise that maybe even more baskets are implemented, or maybe an institutional market-making agreement type of situation could be implemented that gives participants the ability to directly convert basket shares to the underlying.
<br>
The Frankfurt team discuss both trading the spread between the two baskets adjusted for Djembes (basket 1 had 6 croissants, 4 Jams, and 1 Djembe while basket 2 had 4 croissants and 2 jams) and trading the spread between the etf and its synthetic value (sum of the constituents). One nice remark from the Frankfurt team is their theory that the constituent's prices were independently randomized, and the basket data was then generated by adding a mean-reverting noise sequence on top of the constituent prices - this is somewhat important as it means that the basket has mean-reversion to its synthetic value rather than the synthetic having mean-reversion to the baskets. They mention the possibility of heding in the constituents, but that this actually reduced EV, especially considering the cost of trading (spread). <br>

A more general insight they have is that prosperity is mostly about first principles:
> This understanding had important implications for strategy design. Many teams might have rushed into using moving average crossovers or z-scores for trading signals — but applying such methods without a clear theoretical justification is dangerous. For instance, a moving average crossover only makes sense if you believe there is a short-term trend overlaying a longer-term mean, which was not suggested by the structure here. Similarly, using a z-score normalizes the spread by recent volatility, but unless volatility is known to vary meaningfully over time (which we did not observe here), this introduces unnecessary complexity and risk of overfitting. It's easy to fall into the trap of throwing fancy techniques at the problem after a few hours of backtesting — but if you can't explain why a strategy should work from first principles, then any "outperformance" in historical data is probably noise. From the beginning, we placed the highest value on building a deep structural understanding and keeping strategies simple, minimizing parameters whenever possible to maximize robustness.

Their final strategy for the baskets was to keep it more simple with fixed thresholds tuned through grid search - entering entering long basket positions when the spread fell below a certain threshold and vice-versa. Crucially, since they found "Olivia" before traderIDs were released, they did something similar to what Impact did in later rounds but from the get go by using her inferred long/short position to bias the basket spread thresholds dynamically.
<br>
They also mention that they found that the basket spreads carried a slight persistent premium (i.e. the mean was not 0), so they subtracted an estimated running premium from the spread during live trading (probably just some version of a moving average).
<br>
Lastly they discuss how they altered their strategy for the final round to be a bit more safe:
> for the final round, we were uncertain whether or not to fully hedge our basket exposure with the constituents. Recognizing that any trading strategy can be viewed as a linear combination of two other strategies — in this case, fully hedged and fully unhedged — we decided to hedge 50% of our exposure as a balanced compromise. Additionally, we adjusted our execution logic: instead of waiting for spreads to fully revert and cross opposite thresholds, we neutralized positions immediately upon spreads crossing zero (adjusted for the informed signal). This change aimed to reduce variance and lock in profits more consistently, while maintaining approximately zero expected value under the assumption that spreads did not exhibit momentum when crossing zero. It is important to note that here, "zero" still referred to the base threshold after incorporating informed adjustments.

### **Round 3**
Volcanic Rock and Volcanic Rock Vouchers: <br>
Unlike prosperity 2 where the call option (coconut coupon) was only offered at one strike, the Volcanic Rock Vouchers were offered at 5 strikes ranging from 9500 to 10500. Also, unlike the coconut coupons which had a very long time until expiration, the vouchers only had 5 days until expiration, with each remaining round of the competition representing a trading day. For Impact, trading these products was by far the most lucrative opportunity of the competition, but they also spent the most time on them. <br>
First, they explored options trading outside their arbitrage bounds, and found that the 9500 strike (deep in the money) sometimes traded at its intrinsic value (implying zero time value). So the initial idea was kind of to trade theta by trying to buy at these timestamps and then offload when they believed theta to be positive. The problem however was that due to time-price priority, they almost never got filled buying for parity. <br>
They then turned to analysing the orderbook flow, theorising that large options trades would front-run moves in the underlying, and although there were numerous instances when options would be sold simultaneously at all strikes, they could not find any signal in this. When trader IDs were revealed in round 5, it became apparent (according to them at least), that orderbook flow was benign.
<br>
Then a hint was released to plot the IV against moneyness, whereby Impact calculated the IV with the Newton-Rhapson method and then plotting IV using a window length of the last 50 timestamps, which they settled on through grid search. Then they simply fitted a second-order polynomial to the IV-smile and traded when volatility was mispriced. <br>

With respect to delta-hedging, their strategy became prone to accumulating large delta positions even when trying to hedge under certain circumstances. Seeing as there were large intraday moves in the underlying, this was not an acceptable risk, they decided to use the 9500 strike options (which basically traded at parity, meaning little opportunity to profit off gamma). To reduce the cost of hedging, they used the following strategy:
> we tried to capture edge in the 9500 strike options if it flattened our delta position. At each timestamp we would calculate our total delta position and if it was edgy to market take the 9500 options for edge relative to our volatility curve we would trade enough to hedge our delta completely, or as much as we could, whichever was less. As the stock traded very tight in large size it wasn’t possible to market make for edge, so we used the stock to hedge our delta whenever the magnitude of our delta position exceeded a threshold. This ensured that we didn’t over-hedge and kept the number of instances where we were crossing the spread to a minimum.

Impact then optimised their vol-smile strategy by weighting the different strikes rather than just nominally looking at all strikes equally. This made a lot more sense since the long out-of-the money calls had very low Vega, whereby IV-mispricing was much less likely. They first tried weighting by vega but that performed poorly, then they tried moneyness which gave a big performance increase.
<br>
They also note that some teams traded mean-reversion on the underlying (Volcanic Rock).
<br><br>
The Frankfurt team discuss a similar strategy to Impact's for Volcanic Rock and its vouchers. They constructed a volatility smile and then detrended (subtracting the fitted parabola from the observed values). To convert this into something actionable, they input the volatility-smile implied IV into Black-Scholes, and then compared to market quotes (thus transforming the visualisation into price space).
> We initially focused on the 10,000 strike, but dynamically expanded to include other strikes as the underlying shifted and expiry approached, tracking profitability thresholds in real time to decide when to activate scalping on new options. Statistical analysis, specifically testing for 1-lag negative autocorrelation in returns, strongly supported the existence of exploitable short-term inefficiencies across several strikes, further validating this approach.

They also remark on Gamma Scalping:
> The expected value from gamma scalping was consistently positive, as the gains from underlying price movements outweighed the losses from time decay. This made buying options and rehedging the resulting deltas from gamma exposure a relatively low-risk way to generate profit. However, while the approach was stable and mostly safe, the absolute returns were limited. It was a reliable source of small gains, but ultimately, we had a higher risk appetite and wanted better returns.

Lastly they mention mean-reversion trading in Volcanic rock. It exhibited similar dynamics to Squid Ink, and autocorrelation compared against randomized normal samples confirmed significant negative autocorrelation at various horizons, although caution was given to the presence of large price jumps and non-normal return distributions (e.g. no matter how mean-reverting it may be, one wrong false positive followed by a big price jump could eat into EV). Ultimately, they ended up using a basic mean-reversion model, trading deviations from a fast rolling exponential moving average using fixed thresholds, and they did not scale by rolling volatility.
> In the end, we deployed a hybrid strategy combining both sources. Our core focus remained on IV scalping, dynamically expanding across strikes and adjusting thresholds based on evolving conditions, while simultaneously maintaining a moderate mean reversion position — both in the underlying Volcanic Rock and in the deepest in-the-money call (the highest delta option available). Importantly, this was not a delta hedge in the traditional sense: the delta exposure from scalping was relatively small, and explicit delta hedging would have been prohibitively expensive bid-ask spreads. It was rather a hedge against bad luck. Because this hybrid model was designed to minimize maximum regret across different possible market outcomes.

- interestingly, Frankfurt and Impact seem to hold some slightly differing opinions on the topic of delta hedging
- also interestingly, the variance of PnL was quite high for the mean-reversion strategy, and they decided that it wasn't a standalone viable strategy in the last round, but still decided to trade it on the basis of an estimated 95% VaR to be 50K, making it a reasonable hedge against other top teams who might go all in on the strategy. This turned out to be the right decision.

### **Round 4**
Macarons: <br>
Similar to previous prosperity editions, a locational-arbitrage product was introduced in one of the later rounds. However the mechanisms don't seem to be exactly the same as in previous editions.
> in order to trade macarons on the other island you had to pay either an import or export fee (depending on whether you were buying or selling) and a transportation fee. It is also worth noting that the local market spread was quite wide (~ 6 seashells wide), whereas the spread on the other island was much tighter (1.5 seashells).
Export fees were too large (~8 seashells) to simply buy macarons locally and sell them in the other market. Import fees however, were negative, meaning it was possible to buy macarons in the other market and sell locally for a profit, however, this was constrained by the fact that you could only import if you had a corresponding short position - forcing you to sell macarons locally first.
> Before going short the macarons we needed to first decide whether it would be profitable to import them, and we determined this by defining a quantity which we called ‘shipping’. This value represented the net cost to import macarons, factoring in the import costs and the transportation costs and we computed it using the formula: Shipping = - Transportation Costs - Import Tariff. We considered including the spread on the other island in this quantity, but decided there was no need as the spread was a constant width the entire time. Our initial strategy involved going short macarons whenever ‘shipping’ was above a certain threshold, and once we had picked up a short position we imported macarons for edge, closing our position and locking in a profit. This threshold was determined by the width of the local spread. Our initial draft of this strategy picked up this short position simply by market taking, however, once we had established that this was the trade we wanted to do with the macarons we invested the rest of our time optimising our execution and we will see that this was the key to making this strategy extremely profitable.

Now crucially, this strategy fared poorly due to the cost of crossing the spread locally to enable the trade. They thus tried building the local short position through passive orders/market-making. They found that quoting for edge gave very low fill rates, making that unprofitable, the real breakthrough came when testing fill rates at negative edge (i.e. giving the taker immediate profitability by quoting below the estimation of fair value). Giving 1 one seashell of edge gave decent fill rates, but at 2 shells of edge there existed a big taker who could consistently fill these orders in large quantity, making it much more profitable to quote at -2 edge when the "shipping" metric was high:
> This meant that when ‘shipping’ was high (when we were getting paid a lot to import : 3+ seashells of edge) it was much more profitable to give up 2 seashells of edge locally in order to import as many macarons as possible. This boosted profitability stemmed from the fact that even when giving up an extra seashell of edge (as compared with making for 1 seashell below mid), the extra fills more than made up for the edge we gave up when making.
>  In instances where the shipping was greater than 2.77 (an amount that covered the spread cost locally and on the other island) we would market make locally in maximum size for 2 seashells below mid and once we had picked up a short position we imported the macarons from the other island. If shipping was less than 2.77 and greater than 1.77 we would market make for 1 seashell below mid locally before importing, and otherwise we wouldn’t trade.

About other market observations: <br>
As with similar goods in earlier prosperity editions, macarons came with associated data such as a sunlight index and a sugar index. The hint was that these could be used to look for directional signals, however, as with earlier editions, these were somewhat of a red-herring - with the much more profitable strategy focusing on market microstructure rather than fundamental analysis. A hint about a critical sunlight index was released by admins when round 4 was coming to a close. The hint stated that if the sunlight index goes below this CSI with an anticipation to remain under this critical level for a long period of time, macaron prices can increase by a substantial amount. But since there was a cost associated with holding macarons (0.1 shells per timestamp per macaron), so even if you timed it perfectly, the edge in this strategy was not that big. However, this fact was not completely useless:
> In spite of the opportunity only being a small one, we didn’t want to miss out on edge in instances where ‘shipping’ was low and we couldn’t perform the locational arb. We therefore included logic in our script that went long macarons if the slope of the sunlight index was below a certain threshold and if the sunlight index itself was below some threshold (CSI). This logic was only executed in instances where we couldn’t perform the locational arb.
<br>
<br>
Depending a bit on the interpretation, it seems like the Frankfurt team found a very similar pattern to exploit. They remarked that just nominal locational arbitrage was not profitable. But rather, they found that there existed a taker in the local market that would consistently fill at int(externalBid + 0.5). In essence, they found that while the book levels that first came in during the start of every timestamp made straightforward arbitrage unprofitable, they could quote local asks that were close to the local bid, but still above the external ask adjusted for fees, enabling arbitrage. <br>
Notably, they like other top teams did not focus on the other market data like sunlightIndex etc., finding that the predictive power, while maybe there, was weak, and that arbitrage was a far more convincing strategy.

### **Round 5**
The last round again released traderIDs. There were 11 traders, each focusing on their own subset of instruments. Impact analysed the traders by PnL, split by product and decomposed into execution and holding components. There were traders that generated good PnL by consistently trading at favourable prices - however this offered limited insight into improving algorithms since these behaviours were often already exploited, for example Impact were already market-making aggressively in several products. "Olivia" was identified as the lone trader with significant holding PnL - trading exclusively at the daily extremas for Kelp, Squid Ink, and Croissants. This held limited insight for kelp (due to its stable price dynamics), but was layered into Impact's mean-reversion strategy for Squid Ink, with the only modification being required in terms of the mean-reversion part being to shorten the liquidation horizon for mean-reverting trades whenever a directional trade was available. <br>

For Croissants, the informed trader pattern also held insight, and offered several alternatives. One could profitably trade Croissants directly or scale croissant exposure through trading baskets. Impact decided to kind of combine them and continue with their stat arb strategy, but introduced a croissant-based term into the basket's target position, with the weight of this term being decided through basic backtesting.
<br>
Lastly it is worth nothing that Impact had a much more maths heavy idea for trading Croissants, which relied on using the revealed daily extremas to trade on the resulting relative assymetries in the randow walk from those points. While they talk about how they would have started on the implementation, their write-up never finishes that section, and how profitable it could be is not explicitly discussed, but is is definitely an interesting idea to keep in mind.
<br><br>
The Frankfurt team did not mention anything about round 5 more than the fact that they continuously re-optimized all relevant parameters across rounds.
***
## Prosperity 4
**Some heuristic ideas of what might come**
- puts to introduce put-call parity
- futures/forwards to introduce contango vs. backwardation
- other order types (unlikely)
- more advanced taker behaviour, e.g. bots that target you specifically and try to steamroll you during market-making if your position becomes skewed
- multi-venue arbitrage (e.g. 3 markets, shortest path problem)
###**Round 1** <br>
###**Round 2** <br>
###**Round 3** <br>
###**Round 4**
