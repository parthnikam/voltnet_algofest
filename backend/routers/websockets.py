import asyncio
import json
import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from core.matcher import MatchOrder, TradeFill, clear_market
from core.simulator import ProposedOrder, build_simulated_node, simulate_node_round
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
        self.simulated_orders_by_id: Dict[str, dict] = {}
        self.last_trades: List[dict] = []

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
            "orders_collected": len(self.collected_orders),
            "telemetry_count": len(self.telemetry_events),
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
                raw_nodes = await pb.get_all_nodes()
            except Exception as exc:
                logger.error("Failed to fetch nodes from PocketBase: %s", exc)
                await asyncio.sleep(2)
                continue

            if not raw_nodes:
                logger.warning("No PocketBase nodes available for simulation.")
                await asyncio.sleep(2)
                continue

            simulated_nodes = []
            for node in raw_nodes:
                owner_id = node.get("owner")
                if owner_id:
                    owner = await pb.get_user_by_id(owner_id)
                    if owner:
                        owner_wallet = owner.get("wallet_balance", owner.get("wallet_ballance", node.get("wallet_balance", 0.0)))
                        node = {**node, "wallet_balance": owner_wallet}
                simulated_nodes.append(build_simulated_node(node))
            sim_hour = self.current_tick % 24
            solar_factor = max(0.0, math.sin(math.pi * (sim_hour - 6) / 12))

            self.round_open_at = datetime.now(timezone.utc)
            self.round_close_at = self.round_open_at + timedelta(seconds=2)
            self.is_window_open = True
            self.collected_orders = []
            self.telemetry_events = {}
            self.simulated_orders_by_id = {}
            self.last_trades = []

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

            for simulated_node in simulated_nodes:
                telemetry, proposed_order = simulate_node_round(
                    simulated_node,
                    tick=self.current_tick,
                    simulated_hour=sim_hour,
                    solar_factor=solar_factor,
                )
                self.telemetry_events[simulated_node.node_id] = {
                    "node_id": simulated_node.node_id,
                    "owner_user_id": simulated_node.owner_user_id,
                    "generation_kwh": telemetry.generation_kwh,
                    "consumption_kwh": telemetry.consumption_kwh,
                    "battery_before_kwh": telemetry.battery_before_kwh,
                    "battery_after_kwh": telemetry.battery_after_kwh,
                    "unmet_demand_kwh": telemetry.unmet_demand_kwh,
                    "exportable_energy_kwh": telemetry.exportable_energy_kwh,
                    "signature": telemetry.signature,
                }
                try:
                    await pb.update_node_battery(simulated_node.node_id, telemetry.battery_after_kwh)
                except Exception as exc:
                    logger.warning("Failed to persist battery state for node %s: %s", simulated_node.node_id, exc)

                await self.broadcast(
                    {
                        "type": "LEDGER_ENTRY",
                        "payload": {
                            "event": "telemetry",
                            "tick": self.current_tick,
                            "node_id": simulated_node.node_id,
                            "generation_kwh": telemetry.generation_kwh,
                            "consumption_kwh": telemetry.consumption_kwh,
                            "battery_before_kwh": telemetry.battery_before_kwh,
                            "battery_after_kwh": telemetry.battery_after_kwh,
                        },
                    }
                )

                if proposed_order is None:
                    continue

                await self._persist_simulated_order(proposed_order)

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
        match_orders = [
            MatchOrder(
                order_id=order["order_id"],
                node_id=order["node_id"],
                owner_user_id=order.get("owner_user_id"),
                side=order["side"],
                quantity_kwh=order["quantity_kwh"],
                limit_price=order["limit_price"],
                battery_after_kwh=order["battery_after_kwh"],
                wallet_balance=order["wallet_balance"],
            )
            for order in self.collected_orders
        ]
        match_result = clear_market(match_orders)
        await self._settle_trades(match_result.trades)

        self.round_history[self.current_tick] = {
            "tick": self.current_tick,
            "simulated_hour": self.current_tick % 24,
            "status": RoundStatus.SETTLED.value,
            "window_open": False,
            "window_open_at": self.round_open_at.isoformat() if self.round_open_at else None,
            "window_close_at": self.round_close_at.isoformat() if self.round_close_at else None,
            "orders_collected": len(self.collected_orders),
            "telemetry_count": len(self.telemetry_events),
            "matched_volume_kwh": match_result.matched_volume_kwh,
            "clearing_price": match_result.clearing_price,
            "unmatched_buy_volume_kwh": match_result.unmatched_buy_volume_kwh,
            "unmatched_sell_volume_kwh": match_result.unmatched_sell_volume_kwh,
            "trades": self.last_trades,
        }
        await self.broadcast(
            {
                "type": "ROUND_SETTLED",
                "payload": {
                    "tick": self.current_tick,
                    "status": "success",
                    "clearing_price": match_result.clearing_price,
                    "volume_traded_kwh": match_result.matched_volume_kwh,
                    "unmatched_buy_volume_kwh": match_result.unmatched_buy_volume_kwh,
                    "unmatched_sell_volume_kwh": match_result.unmatched_sell_volume_kwh,
                    "trade_count": len(match_result.trades),
                    "trades": self.last_trades,
                },
            }
        )

    async def _persist_simulated_order(self, proposed_order: ProposedOrder):
        try:
            created_order = await pb.create_market_order(
                node_id=proposed_order.node_id,
                owner_user_id=proposed_order.owner_user_id or proposed_order.node_id,
                tick=proposed_order.tick,
                side=proposed_order.side,
                qty=proposed_order.quantity_kwh,
                price=proposed_order.limit_price,
                signature=proposed_order.signature,
                source="simulator",
                telemetry_hash=proposed_order.signature[:16],
                status="pending",
            )
            order_id = created_order["id"]
        except Exception as exc:
            logger.warning("Failed to persist simulated order for node %s: %s", proposed_order.node_id, exc)
            order_id = f"sim-{proposed_order.node_id}-{proposed_order.tick}-{proposed_order.side}"

        order_record = {
            "order_id": order_id,
            "node_id": proposed_order.node_id,
            "owner_user_id": proposed_order.owner_user_id,
            "tick": proposed_order.tick,
            "side": proposed_order.side,
            "quantity_kwh": proposed_order.quantity_kwh,
            "limit_price": proposed_order.limit_price,
            "battery_after_kwh": proposed_order.battery_after_kwh,
            "wallet_balance": proposed_order.wallet_balance,
            "signature": proposed_order.signature,
        }
        self.collected_orders.append(order_record)
        self.simulated_orders_by_id[order_id] = order_record
        await self.broadcast(
            {
                "type": "ORDER_ACCEPTED",
                "payload": {
                    "order_id": order_id,
                    "tick": proposed_order.tick,
                    "node_id": proposed_order.node_id,
                    "side": proposed_order.side,
                    "quantity_kwh": proposed_order.quantity_kwh,
                    "limit_price": proposed_order.limit_price,
                    "source": "simulator",
                },
            }
        )

    async def _settle_trades(self, trades: List[TradeFill]):
        self.last_trades = []
        order_filled_volume: Dict[str, float] = {}

        for trade in trades:
            buyer_order = self.simulated_orders_by_id.get(trade.buyer_order_id)
            seller_order = self.simulated_orders_by_id.get(trade.seller_order_id)
            if not buyer_order or not seller_order:
                continue

            buyer_wallet_after = round(max(buyer_order["wallet_balance"] - trade.total_cost, 0.0), 4)
            seller_wallet_after = round(seller_order["wallet_balance"] + trade.total_cost, 4)
            buyer_order["wallet_balance"] = buyer_wallet_after
            seller_order["wallet_balance"] = seller_wallet_after

            try:
                await pb.update_node_wallet(trade.buyer_node_id, buyer_wallet_after)
                await pb.update_node_wallet(trade.seller_node_id, seller_wallet_after)
                if buyer_order.get("owner_user_id"):
                    await pb.update_user_wallet(buyer_order["owner_user_id"], buyer_wallet_after)
                if seller_order.get("owner_user_id"):
                    await pb.update_user_wallet(seller_order["owner_user_id"], seller_wallet_after)
            except Exception as exc:
                logger.warning("Failed to persist wallet update for trade %s/%s: %s", trade.buyer_node_id, trade.seller_node_id, exc)

            try:
                await pb.log_transaction(
                    buyer_id=trade.buyer_node_id,
                    seller_id=trade.seller_node_id,
                    qty=trade.quantity_kwh,
                    price=trade.unit_price,
                )
            except Exception as exc:
                logger.warning("Failed to persist ledger transaction: %s", exc)

            order_filled_volume[trade.buyer_order_id] = order_filled_volume.get(trade.buyer_order_id, 0.0) + trade.quantity_kwh
            order_filled_volume[trade.seller_order_id] = order_filled_volume.get(trade.seller_order_id, 0.0) + trade.quantity_kwh

            trade_record = {
                "buyer_order_id": trade.buyer_order_id,
                "seller_order_id": trade.seller_order_id,
                "buyer_node_id": trade.buyer_node_id,
                "seller_node_id": trade.seller_node_id,
                "quantity_kwh": trade.quantity_kwh,
                "unit_price": trade.unit_price,
                "total_cost": trade.total_cost,
            }
            self.last_trades.append(trade_record)
            await self.broadcast({"type": "LEDGER_ENTRY", "payload": trade_record})

        for order_id, order in self.simulated_orders_by_id.items():
            filled = round(order_filled_volume.get(order_id, 0.0), 4)
            status = "pending"
            if filled >= order["quantity_kwh"] and filled > 0:
                status = "cleared"
            elif filled == 0:
                status = "cancelled"
            try:
                if not order_id.startswith("sim-"):
                    await pb.update_market_order_status(order_id, status)
            except Exception as exc:
                logger.warning("Failed to update market order status for %s: %s", order_id, exc)


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

                    order_record = {
                        "order_id": f"manual-{payload.node_id}-{payload.tick}-{len(orchestrator.collected_orders)}",
                        "node_id": payload.node_id,
                        "owner_user_id": payload.owner_user_id,
                        "tick": payload.tick,
                        "side": payload.side.value,
                        "quantity_kwh": payload.quantity_kwh,
                        "limit_price": payload.limit_price,
                        "battery_after_kwh": orchestrator.telemetry_events.get(payload.node_id, {}).get("battery_after_kwh", 0.0),
                        "wallet_balance": 0.0,
                        "signature": payload.signature,
                    }
                    orchestrator.collected_orders.append(order_record)
                    orchestrator.simulated_orders_by_id[order_record["order_id"]] = order_record
                    await orchestrator.send_message(
                        websocket,
                        "ORDER_ACCEPTED",
                        {
                            "order_id": order_record["order_id"],
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
