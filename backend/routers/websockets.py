import asyncio
import json
import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from schemas import (
    AckLedgerPayload,
    OrderRequest,
    RoundStatus,
    TelemetryPayload,
    WebSocketEnvelope,
    WebSocketHelloPayload,
)
from services.pb_client import pb

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GridWebSocket")

router = APIRouter(tags=["Real-time Streams"])


class GridOrchestrator:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.connection_sessions: Dict[WebSocket, dict] = {}
        self.current_tick = 0
        self.collected_orders: List[dict] = []
        self.telemetry_events: Dict[str, dict] = {}
        self.is_window_open = False
        self.round_open_at: Optional[datetime] = None
        self.round_close_at: Optional[datetime] = None
        self.round_history: Dict[int, dict] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("Dashboard/Agent connected. Total listeners: %s", len(self.active_connections))

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        self.connection_sessions.pop(websocket, None)

    def get_round_state(self) -> dict:
        status = RoundStatus.OPEN.value if self.is_window_open else RoundStatus.CLEARING.value
        if self.current_tick in self.round_history and not self.is_window_open:
            status = self.round_history[self.current_tick]["status"]

        return {
            "tick": self.current_tick,
            "simulated_hour": self.current_tick % 24,
            "status": status,
            "window_open": self.is_window_open,
            "window_open_at": self.round_open_at.isoformat() if self.round_open_at else None,
            "window_close_at": self.round_close_at.isoformat() if self.round_close_at else None,
        }

    def get_round_state_for_tick(self, tick: int) -> Optional[dict]:
        if tick == self.current_tick:
            return self.get_round_state()
        return self.round_history.get(tick)

    async def send_message(self, websocket: WebSocket, message_type: str, payload: dict):
        await websocket.send_text(json.dumps({"type": message_type, "payload": payload}))

    async def broadcast(self, message: dict):
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
            self.disconnect(connection)

    async def start_simulation_loop(self):
        logger.info("Initializing VoltNet Simulation Clock Loop...")
        await asyncio.sleep(3)

        while True:
            logger.info("Simulation tick %s started.", self.current_tick)

            try:
                await pb.get_all_nodes()
            except Exception as exc:
                logger.error("Failed to fetch nodes from PocketBase: %s", exc)
                await asyncio.sleep(2)
                continue

            sim_hour = self.current_tick % 24
            solar_factor = max(0.0, math.sin(math.pi * (sim_hour - 6) / 12))

            self.round_open_at = datetime.now(timezone.utc)
            self.round_close_at = self.round_open_at + timedelta(seconds=2)
            self.is_window_open = True
            self.collected_orders = []
            self.telemetry_events = {}

            await self.broadcast(
                {
                    "type": "ROUND_OPEN",
                    "payload": {
                        "tick": self.current_tick,
                        "simulated_hour": sim_hour,
                        "solar_availability_factor": round(solar_factor, 2),
                        "window_open": True,
                        "window_open_at": self.round_open_at.isoformat(),
                        "window_close_at": self.round_close_at.isoformat(),
                    },
                }
            )

            logger.info("Bidding window open for 2 seconds...")
            await asyncio.sleep(2.0)

            self.is_window_open = False
            await self.broadcast(
                {
                    "type": "ROUND_CLOSED",
                    "payload": {
                        "tick": self.current_tick,
                        "simulated_hour": sim_hour,
                        "window_open": False,
                        "window_open_at": self.round_open_at.isoformat() if self.round_open_at else None,
                        "window_close_at": self.round_close_at.isoformat() if self.round_close_at else None,
                    },
                }
            )

            logger.info("Bidding window closed. Ingested %s edge orders.", len(self.collected_orders))
            await self.execute_market_clearing()

            self.current_tick += 1
            await asyncio.sleep(1.0)

    async def execute_market_clearing(self):
        logger.info("Running double auction clearing calculations...")
        self.round_history[self.current_tick] = {
            "tick": self.current_tick,
            "simulated_hour": self.current_tick % 24,
            "status": RoundStatus.SETTLED.value,
            "window_open": False,
            "window_open_at": self.round_open_at.isoformat() if self.round_open_at else None,
            "window_close_at": self.round_close_at.isoformat() if self.round_close_at else None,
        }
        await self.broadcast(
            {
                "type": "ROUND_SETTLED",
                "payload": {
                    "tick": self.current_tick,
                    "status": "success",
                    "clearing_price": 0.0,
                    "volume_traded_kwh": 0.0,
                },
            }
        )


orchestrator = GridOrchestrator()


@router.websocket("/ws/market-stream")
async def websocket_endpoint(websocket: WebSocket):
    await orchestrator.connect(websocket)
    try:
        while True:
            try:
                raw_data = await websocket.receive_text()
                message = WebSocketEnvelope.model_validate_json(raw_data)

                if message.type == "HELLO":
                    payload = WebSocketHelloPayload.model_validate(message.payload)
                    orchestrator.connection_sessions[websocket] = payload.model_dump()
                    await orchestrator.send_message(
                        websocket,
                        "HELLO_ACK",
                        {
                            "node_id": payload.node_id,
                            "owner_user_id": payload.owner_user_id,
                            "current_round": orchestrator.get_round_state(),
                        },
                    )
                    continue

                session = orchestrator.connection_sessions.get(websocket)
                if not session:
                    await orchestrator.send_message(
                        websocket,
                        "ERROR",
                        {"message": "Handshake required before submitting telemetry or orders."},
                    )
                    continue

                if message.type == "TELEMETRY_SUBMIT":
                    payload = TelemetryPayload.model_validate(message.payload)
                    if payload.node_id != session["node_id"]:
                        await orchestrator.send_message(
                            websocket,
                            "ERROR",
                            {"message": "Telemetry node_id does not match authenticated websocket session."},
                        )
                        continue
                    orchestrator.telemetry_events[payload.node_id] = payload.model_dump()
                    await orchestrator.send_message(
                        websocket,
                        "TELEMETRY_ACCEPTED",
                        {"tick": payload.tick, "node_id": payload.node_id},
                    )
                    continue

                if message.type == "ORDER_SUBMIT":
                    payload = OrderRequest.model_validate(message.payload)
                    if payload.node_id != session["node_id"] or payload.owner_user_id != session["owner_user_id"]:
                        await orchestrator.send_message(
                            websocket,
                            "ORDER_REJECTED",
                            {"message": "Order identity does not match authenticated websocket session."},
                        )
                        continue

                    if not orchestrator.is_window_open or payload.tick != orchestrator.current_tick:
                        await orchestrator.send_message(
                            websocket,
                            "ORDER_REJECTED",
                            {"message": "Transaction rejected: bidding window closed or tick mismatch."},
                        )
                        continue

                    orchestrator.collected_orders.append(payload.model_dump())
                    await orchestrator.send_message(
                        websocket,
                        "ORDER_ACCEPTED",
                        {
                            "tick": payload.tick,
                            "node_id": payload.node_id,
                            "side": payload.side.value,
                            "quantity_kwh": payload.quantity_kwh,
                            "limit_price": payload.limit_price,
                        },
                    )
                    continue

                if message.type == "ACK_LEDGER":
                    payload = AckLedgerPayload.model_validate(message.payload)
                    await orchestrator.send_message(websocket, "ACK_RECEIVED", payload.model_dump())
            except ValidationError as exc:
                await orchestrator.send_message(
                    websocket,
                    "ERROR",
                    {"message": "Invalid websocket payload.", "details": exc.errors()},
                )
    except WebSocketDisconnect:
        orchestrator.disconnect(websocket)
