from datamodel import TradingState, Order

class Trader:

    def run(self, state: TradingState):
        result = {}
        orders = []

        product = "HYDROGEL_PACK"
        od = state.order_depths[product]
        already_traded = product in state.own_trades and len(state.own_trades[product]) > 0

        if not already_traded:
            bap = min(od.sell_orders.keys())
            bav = od.sell_orders[bap]  
            orders.append(Order(product, bap, -bav))  

        result[product] = orders
    
        conversions = 0
        traderData = ""

        return result, conversions, traderData