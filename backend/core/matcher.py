from dataclasses import dataclass
from typing import Iterable

PLATFORM_FEE_PER_KWH = 0.42
MIN_SETTLEMENT_KWH = 0.0001


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


@dataclass(slots=True)
class _BookOrder:
    order_id: str
    node_id: str
    owner_user_id: str | None
    side: str
    remaining_kwh: float
    limit_price: float
    battery_after_kwh: float
    wallet_balance: float

    @classmethod
    def from_match_order(cls, order: MatchOrder) -> "_BookOrder":
        return cls(
            order_id=order.order_id,
            node_id=order.node_id,
            owner_user_id=order.owner_user_id,
            side=order.side,
            remaining_kwh=round(max(order.quantity_kwh, 0.0), 4),
            limit_price=order.limit_price,
            battery_after_kwh=order.battery_after_kwh,
            wallet_balance=max(order.wallet_balance, 0.0),
        )

    @property
    def settlement_owner_id(self) -> str:
        return self.owner_user_id or self.node_id


def _sort_orders(orders: Iterable[MatchOrder], side: str) -> list[MatchOrder]:
    filtered = [order for order in orders if order.side == side and order.quantity_kwh > 0]
    if side == "buy":
        return sorted(filtered, key=lambda order: (-order.limit_price, order.order_id))
    return sorted(filtered, key=lambda order: (order.limit_price, order.order_id))


def _sorted_book_orders(orders: Iterable[MatchOrder], side: str) -> list[_BookOrder]:
    return [_BookOrder.from_match_order(order) for order in _sort_orders(orders, side)]


def clear_market(orders: Iterable[MatchOrder]) -> MatchResult:
    buy_orders = _sorted_book_orders(orders, "buy")
    sell_orders = _sorted_book_orders(orders, "sell")
    buyer_cash_available: dict[str, float] = {}
    for order in buy_orders:
        buyer_cash_available[order.settlement_owner_id] = max(
            buyer_cash_available.get(order.settlement_owner_id, 0.0),
            order.wallet_balance,
        )

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

        trade_price = round((buy_order.limit_price + sell_order.limit_price) / 2, 4)
        buyer_id = buy_order.settlement_owner_id
        seller_id = sell_order.settlement_owner_id
        buyer_fee_per_kwh = 0.0 if buyer_id == seller_id else PLATFORM_FEE_PER_KWH
        buyer_unit_debit = trade_price + buyer_fee_per_kwh
        affordable_quantity = buyer_cash_available.get(buyer_id, 0.0) / buyer_unit_debit
        fill_quantity = round(min(buy_order.remaining_kwh, sell_order.remaining_kwh, affordable_quantity), 4)

        if fill_quantity <= MIN_SETTLEMENT_KWH:
            buy_order.remaining_kwh = 0.0
            buy_index += 1
            continue

        buyer_debit = round(fill_quantity * buyer_unit_debit, 4)
        if buyer_id != seller_id:
            buyer_cash_available[buyer_id] = round(max(buyer_cash_available.get(buyer_id, 0.0) - buyer_debit, 0.0), 4)

        total_cost = round(fill_quantity * trade_price, 4)
        if total_cost <= 0:
            break

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
        buy_order.remaining_kwh = round(buy_order.remaining_kwh - fill_quantity, 4)
        sell_order.remaining_kwh = round(sell_order.remaining_kwh - fill_quantity, 4)

        if buy_order.remaining_kwh <= MIN_SETTLEMENT_KWH:
            buy_index += 1
        if sell_order.remaining_kwh <= MIN_SETTLEMENT_KWH:
            sell_index += 1

    unmatched_buy = round(sum(max(order.remaining_kwh, 0.0) for order in buy_orders[buy_index:]), 4)
    unmatched_sell = round(sum(max(order.remaining_kwh, 0.0) for order in sell_orders[sell_index:]), 4)
    clearing_price = round(weighted_notional / matched_volume, 4) if matched_volume else 0.0

    return MatchResult(
        trades=trades,
        clearing_price=clearing_price,
        matched_volume_kwh=round(matched_volume, 4),
        unmatched_buy_volume_kwh=unmatched_buy,
        unmatched_sell_volume_kwh=unmatched_sell,
    )
