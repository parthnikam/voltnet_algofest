from fastapi import APIRouter

from response_utils import api_error, success_response
from schemas import (
    BatterySummary,
    NodeRegistrationRequest,
    NodeStatus,
    NodeSummary,
    PortfolioResponse,
    WalletSummary,
)
from services.pb_client import pb

router = APIRouter(prefix="/api/users", tags=["Users & Portfolios"])


def normalize_node_name(node: dict) -> str:
    return (
        node.get("name")
        or node.get("label")
        or node.get("title")
        or f"Node {node.get('id', 'unknown')}"
    )


def coerce_float(value: object, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@router.post("/register")
async def register_new_grid_node(payload: NodeRegistrationRequest):
    if payload.initial_battery_kwh > payload.battery_capacity_kwh:
        raise api_error(400, "Initial battery cannot exceed battery capacity.")

    initial_wallet_balance = coerce_float(payload.initial_wallet_balance)
    node_payload = {
        "name": payload.name,
        "owner": payload.owner_user_id,
        "has_solar": payload.has_solar,
        "battery_capacity_kwh": payload.battery_capacity_kwh,
        "battery_current_kwh": payload.initial_battery_kwh,
        "battery_min_reserve_kwh": round(payload.battery_capacity_kwh * 0.15, 4),
        "max_charge_rate_kw": max(payload.battery_capacity_kwh * 0.35, 0.0),
        "max_discharge_rate_kw": max(payload.battery_capacity_kwh * 0.35, 0.0),
        "max_solar_kw": payload.max_solar_kw,
        "base_load_kw": payload.base_load_kw,
        "grid_import_enabled": True,
        "grid_export_enabled": payload.has_solar,
        "status": NodeStatus.ACTIVE.value,
        "wallet_balance": initial_wallet_balance,
        "public_key": f"ecdsa_pub_generated_mock_{payload.name.lower().replace(' ', '_')}",
    }

    try:
        await pb.update_user_wallet(payload.owner_user_id, initial_wallet_balance)
        record = await pb.create_node(node_payload)
        data = {
            "node_id": record["id"],
            "owner_user_id": payload.owner_user_id,
            "node_status": record.get("status", NodeStatus.ACTIVE.value),
            "wallet": WalletSummary(
                balance=initial_wallet_balance,
                reserved=0.0,
            ).model_dump(),
        }
        return success_response("Grid node registered successfully.", data)
    except Exception as exc:
        raise api_error(500, f"Internal database registration failure: {str(exc)}")


@router.get("/list")
async def list_grid_nodes():
    try:
        nodes = await pb.get_all_nodes()
        data = [
            NodeSummary(
                id=node["id"],
                name=normalize_node_name(node),
                owner_user_id=node.get("owner"),
                has_solar=node.get("has_solar", False),
                status=node.get("status", NodeStatus.ACTIVE.value),
            ).model_dump()
            for node in nodes
        ]
        return success_response("Grid nodes fetched successfully.", data)
    except Exception as exc:
        raise api_error(500, f"Failed to fetch grid nodes: {str(exc)}")


@router.get("/portfolio/{node_id}")
async def get_node_portfolio(node_id: str):
    try:
        node_data = await pb.get_node_by_id(node_id)
        owner_id = node_data.get("owner")
        owner_user = await pb.get_user_by_id(owner_id) if owner_id else None
        latest_order = await pb.get_latest_market_order(node_id)
        wallet_balance = coerce_float(
            (owner_user or {}).get("wallet_balance", (owner_user or {}).get("wallet_ballance", node_data.get("wallet_balance")))
        )

        portfolio = PortfolioResponse(
            id=node_data["id"],
            name=normalize_node_name(node_data),
            status=node_data.get("status", NodeStatus.ACTIVE.value),
            owner_user_id=node_data.get("owner"),
            has_solar=node_data.get("has_solar", False),
            max_solar_kw=node_data.get("max_solar_kw", node_data.get("max_solar", 0.0)) or 0.0,
            base_load_kw=node_data.get("base_load_kw", node_data.get("base_load", 0.0)) or 0.0,
            wallet=WalletSummary(
                balance=wallet_balance,
                reserved=coerce_float((owner_user or {}).get("wallet_reserved")),
            ),
            battery=BatterySummary(
                current_kwh=node_data.get("battery_current_kwh", node_data.get("battery_current", 0.0)) or 0.0,
                capacity_kwh=node_data.get("battery_capacity_kwh", node_data.get("battery_capacity", 0.0)) or 0.0,
            ),
            latest_order=latest_order,
        )
        return success_response("Portfolio fetched successfully.", portfolio.model_dump())
    except Exception:
        raise api_error(404, "Grid hardware node not found.")
