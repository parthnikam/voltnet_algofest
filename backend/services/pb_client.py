import httpx
from typing import Dict, List

POCKETBASE_URL = "http://127.0.0.1:8090/api/collections"

class PocketBaseClient:
    def __init__(self):
        self.client = httpx.AsyncClient(base_url=POCKETBASE_URL)

    async def get_all_nodes(self) -> List[Dict]:
        response = await self.client.get("/nodes/records")
        return response.json().get("items", [])

    async def get_node_by_id(self, node_id: str) -> Dict:
        response = await self.client.get(f"/nodes/records/{node_id}")
        return response.json()

    async def update_wallet_and_battery(self, node_id: str, balance: float, battery: float):
        payload = {
            "wallet_balance": balance,
            "battery_current": battery
        }
        response = await self.client.patch(f"/nodes/records/{node_id}", json=payload)
        return response.json()

    async def create_market_order(self, node_id: str, order_type: str, qty: float, price: float):
        payload = {
            "node": node_id,
            "type": order_type,
            "quantity_kwh": qty,
            "target_price": price,
            "status": "pending"
        }
        response = await self.client.post("/market_orders/records", json=payload)
        return response.json()

    async def log_transaction(self, buyer_id: str, seller_id: str, qty: float, price: float):
        payload = {
            "buyer_node": buyer_id,
            "seller_node": seller_id,
            "quantity_kwh": qty,
            "clearing_price": price,
            "total_cost": round(qty * price, 4)
        }
        response = await self.client.post("/ledger/records", json=payload)
        return response.json()

pb = PocketBaseClient()