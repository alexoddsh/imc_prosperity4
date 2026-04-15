from datamodel import TradingState, Order

class Trader:

    def run(self, state: TradingState):
        result = {}
        orders = []

        od = state.order_depths["INTARIAN_PEPPER_ROOT"]
        
        # Check if we've already traded
        already_traded = "INTARIAN_PEPPER_ROOT" in state.own_trades and len(state.own_trades["INTARIAN_PEPPER_ROOT"]) > 0

        if not already_traded:
            # Hit the best ask to guarantee a fill
            bap = min(od.sell_orders.keys())
            bav = od.sell_orders[bap]  # negative quantity
            orders.append(Order("INTARIAN_PEPPER_ROOT", bap, -bav))  # flip sign to buy

        result["INTARIAN_PEPPER_ROOT"] = orders
        conversions = 0
        traderData = ""

        return result, conversions, traderData