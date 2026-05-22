import asyncio
import hashlib
import json
import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from core.matcher import MIN_SETTLEMENT_KWH, PLATFORM_FEE_PER_KWH, MatchOrder, TradeFill, clear_market
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


def _coerce_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


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
        self.simulation_enabled = False
        self.current_solar_factor = 0.0
        self.current_round_record_id: Optional[str] = None

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

        simulated_hour = self.current_tick % 24
        buy_count = sum(1 for order in self.collected_orders if order.get("side") == "buy")
        sell_count = sum(1 for order in self.collected_orders if order.get("side") == "sell")
        return {
            "tick": self.current_tick,
            "simulated_hour": simulated_hour,
            "market_period": self._market_period(simulated_hour),
            "solar_availability_factor": round(self.current_solar_factor, 2),
            "status": status,
            "window_open": self.is_window_open,
            "window_open_at": self.round_open_at.isoformat() if self.round_open_at else None,
            "window_close_at": self.round_close_at.isoformat() if self.round_close_at else None,
            "orders_collected": len(self.collected_orders),
            "buy_order_count": buy_count,
            "sell_order_count": sell_count,
            "telemetry_count": len(self.telemetry_events),
            "simulation_enabled": self.simulation_enabled,
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
            if not self.simulation_enabled:
                await asyncio.sleep(0.5)
                continue

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
                        owner_wallet = _coerce_float(
                            owner.get("wallet_balance", owner.get("wallet_ballance", node.get("wallet_balance", 0.0)))
                        )
                        node = {**node, "wallet_balance": owner_wallet}
                    else:
                        node = {**node, "owner": None, "wallet_balance": _coerce_float(node.get("wallet_balance"), 250.0)}
                else:
                    node = {**node, "wallet_balance": _coerce_float(node.get("wallet_balance"), 250.0)}
                simulated_nodes.append(build_simulated_node(node))
            sim_hour = self.current_tick % 24
            solar_factor = max(0.0, math.sin(math.pi * (sim_hour - 6) / 12))
            self.current_solar_factor = solar_factor

            self.round_open_at = datetime.now(timezone.utc)
            self.round_close_at = self.round_open_at + timedelta(seconds=2)
            created_round = await pb.create_market_round(
                tick=self.current_tick,
                simulated_hour=sim_hour,
                window_open_at=self.round_open_at,
                window_closed_at=self.round_close_at,
                status=RoundStatus.OPEN.value,
            )
            self.current_round_record_id = created_round.get("id") if created_round else None
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
                        "market_period": self._market_period(sim_hour),
                        "solar_availability_factor": round(solar_factor, 2),
                        "window_open": True,
                        "window_open_at": self.round_open_at.isoformat(),
                        "window_close_at": self.round_close_at.isoformat(),
                    },
                }
            )

            if not self.simulation_enabled:
                self.is_window_open = False
                await self.broadcast({"type": "SIMULATION_STOPPED", "payload": self.get_round_state()})
                continue

            for simulated_node in simulated_nodes:
                if not self.simulation_enabled:
                    break

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
                await pb.create_telemetry_event(
                    round_id=self.current_round_record_id,
                    node_id=simulated_node.node_id,
                    generation_kw=telemetry.generation_kwh,
                    consumption_kw=telemetry.consumption_kwh,
                    net_energy_kwh=round(telemetry.generation_kwh - telemetry.consumption_kwh, 4),
                    battery_before_kwh=telemetry.battery_before_kwh,
                    battery_after_kwh=telemetry.battery_after_kwh,
                    signature=telemetry.signature,
                    accepted=True,
                )
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
                            "unmet_demand_kwh": telemetry.unmet_demand_kwh,
                            "exportable_energy_kwh": telemetry.exportable_energy_kwh,
                        },
                    }
                )

                if proposed_order is None:
                    continue

                await self._persist_simulated_order(proposed_order)

            if not self.simulation_enabled:
                self.is_window_open = False
                await self.broadcast({"type": "SIMULATION_STOPPED", "payload": self.get_round_state()})
                continue

            logger.info("Bidding window open for 2 seconds...")
            await asyncio.sleep(2.0)

            if not self.simulation_enabled:
                self.is_window_open = False
                await self.broadcast({"type": "SIMULATION_STOPPED", "payload": self.get_round_state()})
                continue

            self.is_window_open = False
            await pb.update_market_round(
                self.current_round_record_id,
                window_closed_at=self.round_close_at,
                status=RoundStatus.CLEARING.value,
                total_buy_kwh=round(sum(order["quantity_kwh"] for order in self.collected_orders if order.get("side") == "buy"), 4),
                total_sell_kwh=round(sum(order["quantity_kwh"] for order in self.collected_orders if order.get("side") == "sell"), 4),
            )
            await self.broadcast(
                {
                    "type": "ROUND_CLOSED",
                    "payload": {
                        "tick": self.current_tick,
                        "simulated_hour": sim_hour,
                        "market_period": self._market_period(sim_hour),
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

    def start_simulation(self):
        self.simulation_enabled = True

    async def stop_simulation(self):
        self.simulation_enabled = False
        self.is_window_open = False
        self.round_close_at = datetime.now(timezone.utc)
        await self.broadcast({"type": "SIMULATION_STOPPED", "payload": self.get_round_state()})

    def _market_period(self, simulated_hour: int) -> str:
        if 6 <= simulated_hour <= 17:
            return "day"
        if 18 <= simulated_hour <= 22:
            return "evening_peak"
        return "night"

    async def _get_wallet_balance(self, owner_user_id: Optional[str], node_id: str) -> float:
        if owner_user_id:
            owner = await pb.get_user_by_id(owner_user_id)
            if owner:
                return float(owner.get("wallet_balance", owner.get("wallet_ballance", 0.0)) or 0.0)
        try:
            node = await pb.get_node_by_id(node_id)
            return float(node.get("wallet_balance", 0.0) or 0.0)
        except Exception:
            return 0.0

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
        settled_volume_kwh = round(sum(trade["quantity_kwh"] for trade in self.last_trades), 4)
        settled_trade_count = len(self.last_trades)
        round_snapshot_hash = hashlib.sha256(
            json.dumps(
                {
                    "tick": self.current_tick,
                    "clearing_price": match_result.clearing_price,
                    "settled_volume_kwh": settled_volume_kwh,
                    "trade_count": settled_trade_count,
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        await pb.update_market_round(
            self.current_round_record_id,
            window_closed_at=self.round_close_at,
            status=RoundStatus.SETTLED.value,
            clearing_price=match_result.clearing_price,
            total_buy_kwh=round(sum(order["quantity_kwh"] for order in self.collected_orders if order.get("side") == "buy"), 4),
            total_sell_kwh=round(sum(order["quantity_kwh"] for order in self.collected_orders if order.get("side") == "sell"), 4),
            matched_volume_kwh=settled_volume_kwh,
            broadcast_hash=round_snapshot_hash,
        )

        self.round_history[self.current_tick] = {
            "tick": self.current_tick,
            "simulated_hour": self.current_tick % 24,
            "market_period": self._market_period(self.current_tick % 24),
            "status": RoundStatus.SETTLED.value,
            "window_open": False,
            "window_open_at": self.round_open_at.isoformat() if self.round_open_at else None,
            "window_close_at": self.round_close_at.isoformat() if self.round_close_at else None,
            "orders_collected": len(self.collected_orders),
            "buy_order_count": sum(1 for order in self.collected_orders if order.get("side") == "buy"),
            "sell_order_count": sum(1 for order in self.collected_orders if order.get("side") == "sell"),
            "telemetry_count": len(self.telemetry_events),
            "matched_volume_kwh": settled_volume_kwh,
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
                    "market_period": self._market_period(self.current_tick % 24),
                    "clearing_price": match_result.clearing_price,
                    "volume_traded_kwh": settled_volume_kwh,
                    "unmatched_buy_volume_kwh": match_result.unmatched_buy_volume_kwh,
                    "unmatched_sell_volume_kwh": match_result.unmatched_sell_volume_kwh,
                    "buy_order_count": sum(1 for order in self.collected_orders if order.get("side") == "buy"),
                    "sell_order_count": sum(1 for order in self.collected_orders if order.get("side") == "sell"),
                    "trade_count": settled_trade_count,
                    "trades": self.last_trades,
                },
            }
        )

    async def _persist_simulated_order(self, proposed_order: ProposedOrder):
        try:
            created_order = await pb.create_market_order(
                node_id=proposed_order.node_id,
                owner_user_id=proposed_order.owner_user_id,
                tick=proposed_order.tick,
                side=proposed_order.side,
                qty=proposed_order.quantity_kwh,
                price=proposed_order.limit_price,
                signature=proposed_order.signature,
                source="simulator",
                telemetry_hash=proposed_order.signature[:16],
                status="pending",
                round_id=self.current_round_record_id,
                expires_at=self.round_close_at,
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
            "battery_before_trade_kwh": self.telemetry_events.get(proposed_order.node_id, {}).get("battery_after_kwh", proposed_order.battery_after_kwh),
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
        wallet_by_owner: Dict[str, float] = {}

        for trade in trades:
            buyer_order = self.simulated_orders_by_id.get(trade.buyer_order_id)
            seller_order = self.simulated_orders_by_id.get(trade.seller_order_id)
            if not buyer_order or not seller_order:
                continue

            buyer_owner_id = buyer_order.get("owner_user_id")
            seller_owner_id = seller_order.get("owner_user_id")
            buyer_wallet_key = buyer_owner_id or trade.buyer_node_id
            seller_wallet_key = seller_owner_id or trade.seller_node_id
            is_internal_transfer = buyer_wallet_key == seller_wallet_key
            buyer_wallet_before = _coerce_float(
                wallet_by_owner.get(buyer_wallet_key, buyer_order.get("wallet_balance"))
            )
            seller_wallet_before = _coerce_float(
                wallet_by_owner.get(seller_wallet_key, seller_order.get("wallet_balance"))
            )
            fee_per_kwh: float = 0.0 if is_internal_transfer else PLATFORM_FEE_PER_KWH
            buyer_unit_debit: float = trade.unit_price + fee_per_kwh
            affordable_quantity: float = (
                trade.quantity_kwh if is_internal_transfer else buyer_wallet_before / buyer_unit_debit
            )
            settled_quantity: float = round(min(trade.quantity_kwh, affordable_quantity), 4)

            if settled_quantity <= MIN_SETTLEMENT_KWH:
                logger.warning(
                    "Skipping trade %s/%s because buyer %s has insufficient wallet balance.",
                    trade.buyer_order_id,
                    trade.seller_order_id,
                    buyer_wallet_key,
                )
                continue

            total_cost: float = round(settled_quantity * trade.unit_price, 4)
            fee_total: float = round(settled_quantity * fee_per_kwh, 4)
            buyer_debit: float = round(total_cost + fee_total, 4)
            seller_credit: float = 0.0 if is_internal_transfer else total_cost
            buyer_wallet_after: float = (
                buyer_wallet_before if is_internal_transfer else round(buyer_wallet_before - buyer_debit, 4)
            )
            seller_wallet_after: float = (
                buyer_wallet_after if is_internal_transfer else round(seller_wallet_before + seller_credit, 4)
            )

            if buyer_wallet_after < -MIN_SETTLEMENT_KWH:
                logger.warning(
                    "Skipping trade %s/%s because settlement would overdraw buyer wallet.",
                    trade.buyer_order_id,
                    trade.seller_order_id,
                )
                continue

            buyer_wallet_after = round(max(buyer_wallet_after, 0.0), 4)
            buyer_order["wallet_balance"] = buyer_wallet_after
            seller_order["wallet_balance"] = seller_wallet_after
            wallet_by_owner[buyer_wallet_key] = buyer_wallet_after
            wallet_by_owner[seller_wallet_key] = seller_wallet_after

            try:
                await pb.update_node_wallet(trade.buyer_node_id, buyer_wallet_after)
                await pb.update_node_wallet(trade.seller_node_id, seller_wallet_after)
            except Exception as exc:
                logger.warning("Failed to persist legacy node wallet update for trade %s/%s: %s", trade.buyer_node_id, trade.seller_node_id, exc)

            seller_battery_before = seller_order.get("battery_before_trade_kwh", seller_order.get("battery_after_kwh"))
            full_fill_battery_after = seller_order.get("battery_after_kwh")
            seller_battery_after = full_fill_battery_after
            if seller_battery_before is not None and full_fill_battery_after is not None:
                full_fill_delta = max(seller_battery_before - full_fill_battery_after, 0.0)
                if full_fill_delta > 0 and seller_order.get("quantity_kwh", 0) > 0:
                    fill_ratio = min(settled_quantity / seller_order["quantity_kwh"], 1.0)
                    seller_battery_after = round(seller_battery_before - (full_fill_delta * fill_ratio), 4)
            if seller_battery_after is not None:
                try:
                    await pb.update_node_battery(trade.seller_node_id, seller_battery_after)
                except Exception as exc:
                    logger.warning("Failed to persist seller battery after trade for node %s: %s", trade.seller_node_id, exc)

            if buyer_owner_id:
                try:
                    await pb.update_user_wallet(buyer_owner_id, buyer_wallet_after)
                except Exception as exc:
                    logger.warning("Failed to persist buyer wallet for user %s: %s", buyer_owner_id, exc)
            if seller_owner_id:
                try:
                    await pb.update_user_wallet(seller_owner_id, seller_wallet_after)
                except Exception as exc:
                    logger.warning("Failed to persist seller wallet for user %s: %s", seller_owner_id, exc)

            try:
                await pb.log_transaction(
                    buyer_id=trade.buyer_node_id,
                    seller_id=trade.seller_node_id,
                    qty=settled_quantity,
                    price=trade.unit_price,
                    buyer_user_id=buyer_owner_id,
                    seller_user_id=seller_owner_id,
                    platform_fee=fee_total,
                    net_buyer_debit=buyer_debit,
                    net_seller_credit=seller_credit,
                    buyer_balance_before=buyer_wallet_before,
                    buyer_balance_after=buyer_wallet_after,
                    seller_balance_before=seller_wallet_before,
                    seller_balance_after=seller_wallet_after,
                    round_id=self.current_round_record_id,
                    buy_order_id=trade.buyer_order_id if not trade.buyer_order_id.startswith("sim-") else None,
                    sell_order_id=trade.seller_order_id if not trade.seller_order_id.startswith("sim-") else None,
                )
            except Exception as exc:
                logger.warning("Failed to persist ledger transaction: %s", exc)

            order_filled_volume[trade.buyer_order_id] = order_filled_volume.get(trade.buyer_order_id, 0.0) + settled_quantity
            order_filled_volume[trade.seller_order_id] = order_filled_volume.get(trade.seller_order_id, 0.0) + settled_quantity

            trade_record = {
                "buyer_order_id": trade.buyer_order_id,
                "seller_order_id": trade.seller_order_id,
                "buyer_node_id": trade.buyer_node_id,
                "seller_node_id": trade.seller_node_id,
                "quantity_kwh": settled_quantity,
                "unit_price": trade.unit_price,
                "total_cost": total_cost,
                "platform_fee": fee_total,
                "buyer_debit": buyer_debit,
                "seller_credit": seller_credit,
            }
            self.last_trades.append(trade_record)
            await self.broadcast({"type": "LEDGER_ENTRY", "payload": trade_record})

        for order_id, order in self.simulated_orders_by_id.items():
            filled = round(order_filled_volume.get(order_id, 0.0), 4)
            remaining_kwh = round(max(order["quantity_kwh"] - filled, 0.0), 4)
            status = "pending"
            if filled >= order["quantity_kwh"] and filled > 0:
                status = "cleared"
            elif filled > 0:
                status = "partially_filled"
            elif filled == 0:
                status = "cancelled"
            try:
                if not order_id.startswith("sim-"):
                    await pb.update_market_order_fill(
                        order_id,
                        status=status,
                        remaining_kwh=remaining_kwh,
                        rejection_reason="No matching counterparty in this round." if status == "cancelled" else None,
                    )
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
                    orchestrator.telemetry_events[payload.node_id] = {
                        **payload.model_dump(),
                        "generation_kwh": payload.generation_kw,
                        "consumption_kwh": payload.consumption_kw,
                        "battery_before_kwh": payload.battery_kwh,
                        "battery_after_kwh": payload.battery_kwh,
                    }
                    await pb.create_telemetry_event(
                        round_id=orchestrator.current_round_record_id,
                        node_id=payload.node_id,
                        generation_kw=payload.generation_kw,
                        consumption_kw=payload.consumption_kw,
                        net_energy_kwh=round(payload.generation_kw - payload.consumption_kw, 4),
                        battery_before_kwh=payload.battery_kwh,
                        battery_after_kwh=payload.battery_kwh,
                        signature=payload.signature,
                        accepted=True,
                    )
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

                    try:
                        created_order = await pb.create_market_order(
                            node_id=payload.node_id,
                            owner_user_id=payload.owner_user_id,
                            tick=payload.tick,
                            side=payload.side.value,
                            qty=payload.quantity_kwh,
                            price=payload.limit_price,
                            signature=payload.signature,
                            source="websocket",
                            telemetry_hash=payload.telemetry_hash,
                            status="pending",
                            round_id=orchestrator.current_round_record_id,
                            expires_at=orchestrator.round_close_at,
                        )
                        order_id = created_order["id"]
                    except Exception as exc:
                        logger.warning("Failed to persist websocket order for node %s: %s", payload.node_id, exc)
                        order_id = f"manual-{payload.node_id}-{payload.tick}-{len(orchestrator.collected_orders)}"

                    order_record = {
                        "order_id": order_id,
                        "node_id": payload.node_id,
                        "owner_user_id": payload.owner_user_id,
                        "tick": payload.tick,
                        "side": payload.side.value,
                        "quantity_kwh": payload.quantity_kwh,
                        "limit_price": payload.limit_price,
                        "battery_after_kwh": orchestrator.telemetry_events.get(payload.node_id, {}).get("battery_after_kwh", 0.0),
                        "wallet_balance": await orchestrator._get_wallet_balance(payload.owner_user_id, payload.node_id),
                        "signature": payload.signature,
                    }
                    orchestrator.collected_orders.append(order_record)
                    orchestrator.simulated_orders_by_id[order_record["order_id"]] = order_record
                    await orchestrator.send_message(
                        websocket,
                        "ORDER_ACCEPTED",
                        {
                            "order_id": order_id,
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
