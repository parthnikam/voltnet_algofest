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
            "battery_current": battery,
        }
        return await self._request_json("PATCH", f"/nodes/records/{node_id}", json=payload)

    async def update_node_battery(self, node_id: str, battery: float):
        payload = {"battery_current": battery}
        return await self._request_json("PATCH", f"/nodes/records/{node_id}", json=payload)

    async def update_node_wallet(self, node_id: str, balance: float):
        payload = {"wallet_balance": balance}
        return await self._request_json("PATCH", f"/nodes/records/{node_id}", json=payload)

    async def update_market_order_status(self, order_id: str, status: str):
        payload = {"status": status}
        return await self._request_json("PATCH", f"/market_orders/records/{order_id}", json=payload)

    async def update_user_wallet(self, user_id: str, balance: float):
        try:
            return await self._request_json("PATCH", f"/users/records/{user_id}", json={"wallet_balance": balance})
        except Exception:
            return await self._request_json("PATCH", f"/users/records/{user_id}", json={"wallet_ballance": balance})

    async def create_market_order(
        self,
        node_id: str,
        owner_user_id: str,
        tick: int,
        side: str,
        qty: float,
        price: float,
        signature: str,
        source: str,
        telemetry_hash: Optional[str] = None,
        status: str = "pending",
    ):
        payload = {
            "node": node_id,
            "owner_user_id": owner_user_id,
            "tick": tick,
            "side": side,
            "quantity_kwh": qty,
            "remaining_kwh": qty,
            "limit_price": price,
            "signature": signature,
            "telemetry_hash": telemetry_hash,
            "source": source,
            "status": status,
        }
        try:
            return await self._request_json("POST", "/market_orders/records", json=payload)
        except Exception:
            fallback_payload = {
                "node": node_id,
                "tick": tick,
                "type": "buying" if side == "buy" else "selling",
                "quantity_kwh": qty,
                "target_price": price,
                "status": status,
            }
            return await self._request_json("POST", "/market_orders/records", json=fallback_payload)

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
            owner_match = not owner_user_id or item.get("owner_user_id") == owner_user_id
            tick_match = tick is None or item.get("tick") == tick
            status_match = not status or item.get("status") == status or item.get("order_status") == status
            side_match = not side or item.get("side") == side or item.get("type") == side
            return node_match and owner_match and tick_match and status_match and side_match

        return [item for item in items if matches(item)]

    async def get_latest_market_order(self, node_id: str) -> Optional[Dict[str, Any]]:
        orders = await self.list_market_orders(node_id=node_id, limit=100)
        if not orders:
            return None
        orders.sort(key=lambda item: item.get("created", ""), reverse=True)
        return orders[0]

    async def log_transaction(self, buyer_id: str, seller_id: str, qty: float, price: float):
        payload = {
            "buyer_node": buyer_id,
            "seller_node": seller_id,
            "quantity_kwh": qty,
            "clearing_price": price,
            "total_cost": round(qty * price, 4),
        }
        return await self._request_json("POST", "/ledger/records", json=payload)

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

        return [item for item in items if matches(item)]


pb = PocketBaseClient()
