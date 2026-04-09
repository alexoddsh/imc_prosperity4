from datamodel import TradingState, Order

class Trader:

    def run(self, state: TradingState):
        result = {}
        orders = []

        od = state.order_depths["TOMATOES"]
        
        # Check if we've already traded
        already_traded = "TOMATOES" in state.own_trades and len(state.own_trades["TOMATOES"]) > 0

        if not already_traded:
            # Hit the best ask to guarantee a fill
            bap = min(od.sell_orders.keys())
            bav = od.sell_orders[bap]  # negative quantity
            orders.append(Order("TOMATOES", bap, -bav))  # flip sign to buy

        result["TOMATOES"] = orders
        conversions = 0
        traderData = ""

        return result, conversions, traderData