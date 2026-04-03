from datamodel import TradingState, Order, Logger
from typing import List

class Trader:
    def run(self, state: TradingState):
        self.logger = Logger()
        result = {}

        for product in state.order_depths:
            order_depth = state.order_depths[product]
            orders: List[Order] = []

            if order_depth.buy_orders and order_depth.sell_orders:
                best_bid = max(order_depth.buy_orders.keys())
                best_ask = min(order_depth.sell_orders.keys())
                mid = (best_bid + best_ask) / 2

                position = state.position.get(product, 0)

                # Take any favorable trades against mid
                for ask_price in sorted(order_depth.sell_orders.keys()):
                    if ask_price < mid:
                        qty = -order_depth.sell_orders[ask_price]  # sell_orders have negative qty
                        orders.append(Order(product, ask_price, qty))

                for bid_price in sorted(order_depth.buy_orders.keys(), reverse=True):
                    if bid_price > mid:
                        qty = -order_depth.buy_orders[bid_price]
                        orders.append(Order(product, bid_price, qty))

                # Place passive quotes inside the spread
                spread = best_ask - best_bid
                if spread > 2:
                    buy_price = best_bid + 1
                    sell_price = best_ask - 1
                    size = 5

                    # Skew based on position
                    if position > 10:
                        size_buy = 2
                        size_sell = 8
                    elif position < -10:
                        size_buy = 8
                        size_sell = 2
                    else:
                        size_buy = size
                        size_sell = size

                    orders.append(Order(product, buy_price, size_buy))
                    orders.append(Order(product, sell_price, -size_sell))

            result[product] = orders

        self.logger.flush(state, result, 0, "")
        return result, 0, ""
