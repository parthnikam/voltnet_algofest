import asyncio, json, logging, math
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from services.pb_client import pb
from typing import List, Dict


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GridWebSocket")

router = APIRouter(tags=["Real-time Streams"])


class GridOrchestrator:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.current_tick = 0
        self.collected_bids: Dict[str, dict] = {}
        self.is_window_open = False

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Dashboard/Agent connected. Total listeners: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """Pushes structured JSON string messages out to all live browser sessions."""
        if not self.active_connections:
            return
        payload = json.dumps(message)
        dead_connections = []

        for connection in self.active_connections:
            try:
                await connection.send_text(payload)
            except Exception:
                dead_connections.append(connection)

        for connection in dead_connections:
            self.active_connections.remove(connection)

    async def start_simulation_loop(self):
        """Background clock runner. Ticks every 5 seconds representing 1 hour."""
        logger.info("Initializing VoltNet Simulation Clock Loop...")
        await asyncio.sleep(3)

        while True:
            logger.info(f"\n🛜  --- SIMULATION TICK {self.current_tick} STARTED ---")

            # Fetch current live node profiles directly from pocketbase
            try:
                nodes = await pb.get_all_nodes()
            except Exception as e:
                logger.error(f"failed to fetch nodes from PocketBase {e}")
                await asyncio.sleep(2)
                continue 
            
            # compute solar factor based on simulated time (peaks at 12 PM)
            sim_hour = self.current_tick % 24 
            solar_factor = max(0.0, math.sin(math.pi * (sim_hour - 6)/12))

            # PHASE 1. broadcast production and consumption baselines to all connected nodes
            await self.broadcast({
                "type": "TELEMETRY_BROADCAST",
                "tick": self.current_tick,
                "simulated_hour": sim_hour, 
                "solar_availability_factor": round(solar_factor, 2)
            })

            # PHASE 2. open bidding window
            self.is_window_open = True 
            self.collected_bids = {} # clear past tick orders
            logger.info("🔓 Bidding window open for 2 seconds...")

            await asyncio.sleep(2.0)

            self.is_window_open = False # close bidding window
            logger.info(f"🔒 Bidding window closed. Ingested {len(self.collected_bids)} edge bids.")


            # PHASE 3. clear the market (bids matcher logic)
            await self.execute_market_clearing()

            self.current_tick += 1
            await asyncio.sleep(1.0)


    async def execute_market_clearing(self):
        """Triggers auction matchmaking algorithms against collected bids."""
        logger.info("Running double auction clearing calculations...")
        # (The matching engine will plug directly right here)
        await self.broadcast({
            "type": "MARKET_CLEARED",
            "tick": self.current_tick,
            "status": "success",
            "clearing_price": 0.0,
            "volume_traded_kwh": 0.0
        })


orchestrator = GridOrchestrator()

@router.websocket("/ws/market-stream")
async def websocket_endpoint(websocket: WebSocket):
    await orchestrator.connect(websocket)
    try:
        while True:
            # Listen continuously for incoming buy/sell submittals from clients
            raw_data = await websocket.receive_text()
            message = json.loads(raw_data)
            
            if message.get("type") == "SUBMIT_BID":
                if orchestrator.is_window_open:
                    payload = message.get("payload", {})
                    node_id = payload.get("node_id")
                    if node_id:
                        orchestrator.collected_bids[node_id] = payload
                else:
                    await websocket.send_text(json.dumps({
                        "type": "ERROR",
                        "message": "Transaction rejected: Bidding window closed!"
                    }))
    except WebSocketDisconnect:
        orchestrator.disconnect(websocket)