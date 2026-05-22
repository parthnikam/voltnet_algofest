from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

POCKETBASE_URL = "http://127.0.0.1:8090/api/collections"


class PocketBaseClient:
    def __init__(self):
        self.client = httpx.AsyncClient(base_url=POCKETBASE_URL)

    async def _request_json(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        response = await self.client.request(method, path, **kwargs)
        response.raise_for_status()
        return response.json()

    async def get_all_nodes(self) -> List[Dict]:
        response = await self._request_json("GET", "/nodes/records?perPage=200")
        return response.get("items", [])

    async def get_node_by_id(self, node_id: str) -> Dict:
        return await self._request_json("GET", f"/nodes/records/{node_id}")

    async def create_node(self, payload: Dict[str, Any]) -> Dict:
        return await self._request_json("POST", "/nodes/records", json=payload)

    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        try:
            return await self._request_json("GET", f"/users/records/{user_id}")
        except Exception:
            return None

    async def update_wallet_and_battery(self, node_id: str, balance: float, battery: float):
        payload = {
            "wallet_balance": balance,
            "battery_current_kwh": battery,
        }
        try:
            return await self._request_json("PATCH", f"/nodes/records/{node_id}", json=payload)
        except Exception:
            payload["battery_current"] = battery
            return await self._request_json("PATCH", f"/nodes/records/{node_id}", json=payload)

    async def update_node_battery(self, node_id: str, battery: float):
        payload = {"battery_current_kwh": battery}
        try:
            return await self._request_json("PATCH", f"/nodes/records/{node_id}", json=payload)
        except Exception:
            return await self._request_json("PATCH", f"/nodes/records/{node_id}", json={"battery_current": battery})

    async def update_node_wallet(self, node_id: str, balance: float):
        payload = {"wallet_balance": balance}
        try:
            return await self._request_json("PATCH", f"/nodes/records/{node_id}", json=payload)
        except Exception:
            return None

    async def update_market_order_status(self, order_id: str, status: str):
        order_status = {
            "pending": "open",
            "cleared": "filled",
            "cancelled": "cancelled",
        }.get(status, status)
        try:
            return await self._request_json("PATCH", f"/market_orders/records/{order_id}", json={"order_status": order_status})
        except Exception:
            return await self._request_json("PATCH", f"/market_orders/records/{order_id}", json={"status": status})

    async def update_user_wallet(self, user_id: str, balance: float):
        try:
            return await self._request_json("PATCH", f"/users/records/{user_id}", json={"wallet_balance": balance})
        except Exception:
            return await self._request_json("PATCH", f"/users/records/{user_id}", json={"wallet_ballance": balance})

    async def create_market_round(
        self,
        tick: int,
        simulated_hour: int,
        window_open_at: Optional[datetime],
        window_closed_at: Optional[datetime],
        status: str,
    ) -> Optional[Dict[str, Any]]:
        payload = {
            "tick": tick,
            "simulated_hour": simulated_hour,
            "window_open_at": window_open_at.isoformat() if window_open_at else None,
            "window_closed_at": window_closed_at.isoformat() if window_closed_at else None,
            "status": status,
            "clearing_price": 0.0,
            "total_buy_kwh": 0.0,
            "total_sell_kwh": 0.0,
            "matched_volume_kwh": 0.0,
        }
        payload = {key: value for key, value in payload.items() if value is not None}
        try:
            return await self._request_json("POST", "/market_rounds/records", json=payload)
        except Exception:
            return None

    async def update_market_round(
        self,
        round_id: Optional[str],
        *,
        window_closed_at: Optional[datetime] = None,
        status: Optional[str] = None,
        clearing_price: Optional[float] = None,
        total_buy_kwh: Optional[float] = None,
        total_sell_kwh: Optional[float] = None,
        matched_volume_kwh: Optional[float] = None,
        broadcast_hash: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        if not round_id:
            return None
        payload = {
            "window_closed_at": window_closed_at.isoformat() if window_closed_at else None,
            "status": status,
            "clearing_price": clearing_price,
            "total_buy_kwh": total_buy_kwh,
            "total_sell_kwh": total_sell_kwh,
            "matched_volume_kwh": matched_volume_kwh,
            "broadcast_hash": broadcast_hash,
        }
        payload = {key: value for key, value in payload.items() if value is not None}
        if not payload:
            return None
        try:
            return await self._request_json("PATCH", f"/market_rounds/records/{round_id}", json=payload)
        except Exception:
            return None

    async def create_telemetry_event(
        self,
        *,
        round_id: Optional[str],
        node_id: str,
        generation_kw: float,
        consumption_kw: float,
        net_energy_kwh: float,
        battery_before_kwh: float,
        battery_after_kwh: float,
        signature: str,
        accepted: bool = True,
    ) -> Optional[Dict[str, Any]]:
        payload = {
            "round": round_id,
            "node": node_id,
            "generation_kw": generation_kw,
            "consumption_kw": consumption_kw,
            "net_energy_kwh": net_energy_kwh,
            "battery_before_kwh": battery_before_kwh,
            "battery_after_kwh": battery_after_kwh,
            "signature": signature,
            "accepted": accepted,
        }
        payload = {key: value for key, value in payload.items() if value is not None}
        try:
            return await self._request_json("POST", "/telemetry_events/records", json=payload)
        except Exception:
            return None

    async def create_market_order(
        self,
        node_id: str,
        owner_user_id: Optional[str],
        tick: int,
        side: str,
        qty: float,
        price: float,
        signature: str,
        source: str,
        telemetry_hash: Optional[str] = None,
        status: str = "pending",
        round_id: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        rejection_reason: Optional[str] = None,
    ):
        order_status = {
            "pending": "open",
            "cleared": "filled",
            "cancelled": "cancelled",
        }.get(status, status)
        extended_payload = {
            "node": node_id,
            "owner_user_id": owner_user_id,
            "owner": owner_user_id,
            "round": round_id,
            "tick": tick,
            "side": side,
            "quantity_kwh": qty,
            "remaining_kwh": qty,
            "limit_price": price,
            "signature": signature,
            "telemetry_hash": telemetry_hash,
            "source": source,
            "order_status": order_status,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "rejection_reason": rejection_reason,
        }
        extended_payload = {key: value for key, value in extended_payload.items() if value is not None}
        try:
            return await self._request_json("POST", "/market_orders/records", json=extended_payload)
        except Exception:
            payload = {
                "owner": owner_user_id,
                "side": side,
                "quantity_kwh": qty,
                "remaining_kwh": qty,
                "limit_price": price,
                "signature": signature,
                "telemetry_hash": telemetry_hash,
                "source": source,
                "order_status": order_status,
                "expires_at": expires_at.isoformat() if expires_at else None,
                "rejection_reason": rejection_reason,
            }
            payload = {key: value for key, value in payload.items() if value is not None}
        try:
            return await self._request_json("POST", "/market_orders/records", json=payload)
        except Exception:
            fallback_payload = {
                "node": node_id,
                "owner_user_id": owner_user_id,
                "tick": tick,
                "type": "buying" if side == "buy" else "selling",
                "quantity_kwh": qty,
                "target_price": price,
                "status": status,
            }
            return await self._request_json("POST", "/market_orders/records", json=fallback_payload)

    async def update_market_order_fill(
        self,
        order_id: str,
        *,
        status: str,
        remaining_kwh: float,
        rejection_reason: Optional[str] = None,
    ):
        order_status = {
            "pending": "open",
            "partially_filled": "partially_filled",
            "cleared": "filled",
            "cancelled": "cancelled",
            "rejected": "rejected",
            "expired": "expired",
        }.get(status, status)
        payload = {
            "order_status": order_status,
            "remaining_kwh": max(round(remaining_kwh, 4), 0.0),
            "rejection_reason": rejection_reason,
        }
        payload = {key: value for key, value in payload.items() if value is not None}
        try:
            return await self._request_json("PATCH", f"/market_orders/records/{order_id}", json=payload)
        except Exception:
            fallback_payload = {
                "status": status,
                "remaining_kwh": max(round(remaining_kwh, 4), 0.0),
                "rejection_reason": rejection_reason,
            }
            fallback_payload = {key: value for key, value in fallback_payload.items() if value is not None}
            return await self._request_json("PATCH", f"/market_orders/records/{order_id}", json=fallback_payload)

    async def list_market_orders(
        self,
        node_id: Optional[str] = None,
        owner_user_id: Optional[str] = None,
        tick: Optional[int] = None,
        status: Optional[str] = None,
        side: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        records = await self._request_json("GET", f"/market_orders/records?perPage={limit}")
        items = records.get("items", [])

        def matches(item: Dict[str, Any]) -> bool:
            node_match = not node_id or item.get("node") == node_id
            owner_match = not owner_user_id or item.get("owner_user_id") == owner_user_id or item.get("owner") == owner_user_id
            tick_match = tick is None or item.get("tick") == tick
            status_match = not status or item.get("status") == status or item.get("order_status") == status
            side_match = not side or item.get("side") == side or item.get("type") == side
            return node_match and owner_match and tick_match and status_match and side_match

        matched = [item for item in items if matches(item)]
        matched.sort(key=lambda item: item.get("created", ""), reverse=True)
        return matched

    async def get_latest_market_order(self, node_id: str) -> Optional[Dict[str, Any]]:
        orders = await self.list_market_orders(node_id=node_id, limit=100)
        if not orders:
            return None
        orders.sort(key=lambda item: item.get("created", ""), reverse=True)
        return orders[0]

    async def log_transaction(
        self,
        buyer_id: str,
        seller_id: str,
        qty: float,
        price: float,
        buyer_user_id: Optional[str] = None,
        seller_user_id: Optional[str] = None,
        platform_fee: float = 0.0,
        net_buyer_debit: Optional[float] = None,
        net_seller_credit: Optional[float] = None,
        buyer_balance_before: Optional[float] = None,
        buyer_balance_after: Optional[float] = None,
        seller_balance_before: Optional[float] = None,
        seller_balance_after: Optional[float] = None,
        round_id: Optional[str] = None,
        buy_order_id: Optional[str] = None,
        sell_order_id: Optional[str] = None,
    ):
        total_cost = round(qty * price, 4)
        buyer_debit = total_cost if net_buyer_debit is None else net_buyer_debit
        seller_credit = total_cost if net_seller_credit is None else net_seller_credit
        payload = {
            "round": round_id,
            "buy_order": buy_order_id,
            "sell_order": sell_order_id,
            "buyer_node": buyer_id,
            "seller_node": seller_id,
            "buyer_user": buyer_user_id,
            "seller_user": seller_user_id,
            "quantity_kwh": qty,
            "unit_price": price,
            "gross_amount": total_cost,
            "platform_fee": platform_fee,
            "net_buyer_debit": buyer_debit,
            "net_seller_credit": seller_credit,
            "settlement_status": "settled",
            "buyer_balance_before": buyer_balance_before,
            "buyer_balance_after": buyer_balance_after,
            "seller_balance_before": seller_balance_before,
            "seller_balance_after": seller_balance_after,
        }
        payload = {key: value for key, value in payload.items() if value is not None}
        try:
            return await self._request_json("POST", "/ledger/records", json=payload)
        except Exception:
            fallback_payload = {
                "buyer_node": buyer_id,
                "seller_node": seller_id,
                "quantity_kwh": qty,
                "clearing_price": price,
                "total_cost": total_cost,
            }
            return await self._request_json("POST", "/ledger/records", json=fallback_payload)

    async def list_ledger_entries(
        self,
        node_id: Optional[str] = None,
        owner_user_id: Optional[str] = None,
        tick: Optional[int] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        records = await self._request_json("GET", f"/ledger/records?perPage={limit}")
        items = records.get("items", [])

        def matches(item: Dict[str, Any]) -> bool:
            node_match = not node_id or item.get("buyer_node") == node_id or item.get("seller_node") == node_id
            owner_match = not owner_user_id or item.get("buyer_user") == owner_user_id or item.get("seller_user") == owner_user_id
            tick_match = tick is None or item.get("tick") == tick
            return node_match and owner_match and tick_match

        matched = [item for item in items if matches(item)]
        matched.sort(key=lambda item: item.get("created", ""), reverse=True)
        return matched


pb = PocketBaseClient()
