from typing import Optional

from fastapi import APIRouter, Query

from response_utils import api_error, success_response
from routers.websockets import orchestrator
from schemas import LedgerRecord, OrderRecord, OrderRequest
from services.pb_client import pb

router = APIRouter(prefix="/api/market", tags=["Market Operations"])


def normalize_order_side(raw_side: Optional[str]) -> Optional[str]:
    if raw_side in {"buy", "buying", "bid"}:
        return "buy"
    if raw_side in {"sell", "selling", "offer"}:
        return "sell"
    return raw_side


@router.post("/order")
async def submit_edge_order(payload: OrderRequest):
    try:
        order = await pb.create_market_order(
            node_id=payload.node_id,
            owner_user_id=payload.owner_user_id,
            tick=payload.tick,
            side=payload.side.value,
            qty=payload.quantity_kwh,
            price=payload.limit_price,
            signature=payload.signature,
            source="api",
            telemetry_hash=payload.telemetry_hash,
            status="pending",
        )
        data = {
            "order_id": order["id"],
            "source": "api",
            "normalized_order": OrderRecord(
                id=order["id"],
                node_id=payload.node_id,
                owner_user_id=payload.owner_user_id,
                tick=payload.tick,
                side=payload.side.value,
                quantity_kwh=payload.quantity_kwh,
                remaining_kwh=payload.quantity_kwh,
                limit_price=payload.limit_price,
                status=order.get("status", "pending"),
                source="api",
                signature=payload.signature,
                telemetry_hash=payload.telemetry_hash,
                created=order.get("created"),
                updated=order.get("updated"),
            ).model_dump(),
        }
        return success_response("Order accepted through admin API path.", data)
    except Exception as exc:
        raise api_error(500, f"Order placement failed: {str(exc)}")


@router.get("/rounds/current")
async def get_current_round():
    return success_response("Current round fetched successfully.", orchestrator.get_round_state())


@router.post("/simulation/start")
async def start_simulation():
    orchestrator.start_simulation()
    return success_response("Simulation started.", orchestrator.get_round_state())


@router.post("/simulation/stop")
async def stop_simulation():
    orchestrator.stop_simulation()
    return success_response("Simulation stopped.", orchestrator.get_round_state())


@router.get("/rounds/{tick}")
async def get_round_by_tick(tick: int):
    round_data = orchestrator.get_round_state_for_tick(tick)
    if round_data is None:
        raise api_error(404, f"No round data available for tick {tick}.")
    return success_response("Round snapshot fetched successfully.", round_data)


@router.get("/orders")
async def list_market_orders(
    node_id: Optional[str] = None,
    owner_user_id: Optional[str] = None,
    tick: Optional[int] = Query(default=None, ge=0),
    status: Optional[str] = None,
    side: Optional[str] = None,
):
    if side and side not in {"buy", "sell"}:
        raise api_error(400, "Query parameter 'side' must be 'buy' or 'sell'.")

    try:
        orders = await pb.list_market_orders(
            node_id=node_id,
            owner_user_id=owner_user_id,
            tick=tick,
            status=status,
            side=side,
        )
        data = [
            OrderRecord(
                id=order["id"],
                node_id=order.get("node"),
                owner_user_id=order.get("owner_user_id"),
                tick=order.get("tick"),
                side=normalize_order_side(order.get("side") or order.get("type")),
                quantity_kwh=order.get("quantity_kwh"),
                remaining_kwh=order.get("remaining_kwh", order.get("quantity_kwh")),
                limit_price=order.get("limit_price", order.get("target_price")),
                status=order.get("order_status", order.get("status")),
                source=order.get("source"),
                signature=order.get("signature"),
                telemetry_hash=order.get("telemetry_hash"),
                created=order.get("created"),
                updated=order.get("updated"),
            ).model_dump()
            for order in orders
        ]
        return success_response("Market orders fetched successfully.", data)
    except Exception as exc:
        raise api_error(500, f"Failed to fetch market orders: {str(exc)}")


@router.get("/ledger")
async def list_ledger_entries(
    node_id: Optional[str] = None,
    owner_user_id: Optional[str] = None,
    tick: Optional[int] = Query(default=None, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    try:
        entries = await pb.list_ledger_entries(
            node_id=node_id,
            owner_user_id=owner_user_id,
            tick=tick,
            limit=limit,
        )
        data = [
            LedgerRecord(
                id=entry["id"],
                tick=entry.get("tick"),
                buyer_node_id=entry.get("buyer_node"),
                seller_node_id=entry.get("seller_node"),
                quantity_kwh=entry.get("quantity_kwh"),
                unit_price=entry.get("unit_price", entry.get("clearing_price")),
                total_cost=entry.get("total_cost"),
                settlement_status=entry.get("settlement_status"),
                created=entry.get("created"),
            ).model_dump()
            for entry in entries
        ]
        return success_response("Ledger entries fetched successfully.", data)
    except Exception as exc:
        raise api_error(500, f"Failed to fetch ledger entries: {str(exc)}")
