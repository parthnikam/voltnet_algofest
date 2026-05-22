from dataclasses import dataclass
from typing import Iterable


@dataclass(slots=True)
class MatchOrder:
    order_id: str
    node_id: str
    owner_user_id: str | None
    side: str
    quantity_kwh: float
    limit_price: float
    battery_after_kwh: float
    wallet_balance: float


@dataclass(slots=True)
class TradeFill:
    buyer_order_id: str
    seller_order_id: str
    buyer_node_id: str
    seller_node_id: str
    quantity_kwh: float
    unit_price: float
    total_cost: float


@dataclass(slots=True)
class MatchResult:
    trades: list[TradeFill]
    clearing_price: float
    matched_volume_kwh: float
    unmatched_buy_volume_kwh: float
    unmatched_sell_volume_kwh: float


def _sort_orders(orders: Iterable[MatchOrder], side: str) -> list[MatchOrder]:
    filtered = [order for order in orders if order.side == side and order.quantity_kwh > 0]
    if side == "buy":
        return sorted(filtered, key=lambda order: (-order.limit_price, order.order_id))
    return sorted(filtered, key=lambda order: (order.limit_price, order.order_id))


def clear_market(orders: Iterable[MatchOrder]) -> MatchResult:
    buy_orders = _sort_orders(orders, "buy")
    sell_orders = _sort_orders(orders, "sell")

    trades: list[TradeFill] = []
    weighted_notional = 0.0
    matched_volume = 0.0
    buy_index = 0
    sell_index = 0

    while buy_index < len(buy_orders) and sell_index < len(sell_orders):
        buy_order = buy_orders[buy_index]
        sell_order = sell_orders[sell_index]

        if buy_order.limit_price < sell_order.limit_price:
            break

        fill_quantity = round(min(buy_order.quantity_kwh, sell_order.quantity_kwh), 4)
        if fill_quantity <= 0:
            break

        trade_price = round((buy_order.limit_price + sell_order.limit_price) / 2, 4)
        total_cost = round(fill_quantity * trade_price, 4)
        trades.append(
            TradeFill(
                buyer_order_id=buy_order.order_id,
                seller_order_id=sell_order.order_id,
                buyer_node_id=buy_order.node_id,
                seller_node_id=sell_order.node_id,
                quantity_kwh=fill_quantity,
                unit_price=trade_price,
                total_cost=total_cost,
            )
        )

        weighted_notional += total_cost
        matched_volume += fill_quantity
        buy_order.quantity_kwh = round(buy_order.quantity_kwh - fill_quantity, 4)
        sell_order.quantity_kwh = round(sell_order.quantity_kwh - fill_quantity, 4)

        if buy_order.quantity_kwh <= 0:
            buy_index += 1
        if sell_order.quantity_kwh <= 0:
            sell_index += 1

    unmatched_buy = round(sum(max(order.quantity_kwh, 0.0) for order in buy_orders[buy_index:]), 4)
    unmatched_sell = round(sum(max(order.quantity_kwh, 0.0) for order in sell_orders[sell_index:]), 4)
    clearing_price = round(weighted_notional / matched_volume, 4) if matched_volume else 0.0

    return MatchResult(
        trades=trades,
        clearing_price=clearing_price,
        matched_volume_kwh=round(matched_volume, 4),
        unmatched_buy_volume_kwh=unmatched_buy,
        unmatched_sell_volume_kwh=unmatched_sell,
    )
