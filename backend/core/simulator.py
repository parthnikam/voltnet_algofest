import hashlib
import random
from dataclasses import dataclass

from core.balancer import NodeEnergyState, balance_node_energy, compute_battery_reserve
from core.matcher import PLATFORM_FEE_PER_KWH


@dataclass(slots=True)
class SimulatedNode:
    node_id: str
    owner_user_id: str | None
    name: str
    has_solar: bool
    public_key: str
    wallet_balance: float
    battery_capacity_kwh: float
    battery_current_kwh: float
    max_solar_kw: float
    base_load_kw: float


@dataclass(slots=True)
class TelemetryEvent:
    node_id: str
    tick: int
    generation_kwh: float
    consumption_kwh: float
    battery_before_kwh: float
    battery_after_kwh: float
    unmet_demand_kwh: float
    exportable_energy_kwh: float
    signature: str


@dataclass(slots=True)
class ProposedOrder:
    node_id: str
    owner_user_id: str | None
    tick: int
    side: str
    quantity_kwh: float
    limit_price: float
    battery_after_kwh: float
    wallet_balance: float
    signature: str


def _rng_seed(node_id: str, tick: int, label: str) -> int:
    seed_material = f"{node_id}:{tick}:{label}".encode()
    return int(hashlib.sha256(seed_material).hexdigest()[:16], 16)


def _round_signature(node_id: str, tick: int, suffix: str) -> str:
    material = f"{node_id}:{tick}:{suffix}".encode()
    return hashlib.sha256(material).hexdigest()


def build_simulated_node(record: dict) -> SimulatedNode:
    return SimulatedNode(
        node_id=record["id"],
        owner_user_id=record.get("owner"),
        name=record.get("name", record["id"]),
        has_solar=bool(record.get("has_solar", False)),
        public_key=record.get("public_key", f"sim_pub_{record['id']}"),
        wallet_balance=float(record.get("wallet_balance", 0.0) or 0.0),
        battery_capacity_kwh=float(record.get("battery_capacity_kwh", record.get("battery_capacity", 0.0)) or 0.0),
        battery_current_kwh=float(record.get("battery_current_kwh", record.get("battery_current", 0.0)) or 0.0),
        max_solar_kw=float(record.get("max_solar_kw", record.get("max_solar", 0.0)) or 0.0),
        base_load_kw=float(record.get("base_load_kw", record.get("base_load", 1.0)) or 1.0),
    )


def simulate_node_round(node: SimulatedNode, tick: int, simulated_hour: int, solar_factor: float) -> tuple[TelemetryEvent, ProposedOrder | None]:
    load_rng = random.Random(_rng_seed(node.node_id, tick, "load"))
    price_rng = random.Random(_rng_seed(node.node_id, tick, "price"))
    cloud_rng = random.Random(_rng_seed(node.node_id, tick, "cloud"))

    if 6 <= simulated_hour <= 9 or 18 <= simulated_hour <= 22:
        load_multiplier = load_rng.uniform(1.55, 2.35)
    elif 0 <= simulated_hour <= 4:
        load_multiplier = load_rng.uniform(0.65, 0.95)
    else:
        load_multiplier = load_rng.uniform(0.85, 1.35)

    consumption_kwh = round(max(node.base_load_kw * load_multiplier, 0.05), 4)
    cloud_factor = cloud_rng.uniform(0.92, 1.08)
    generation_kwh = 0.0
    if node.has_solar and node.max_solar_kw > 0 and solar_factor > 0:
        generation_kwh = round(node.max_solar_kw * solar_factor * cloud_factor, 4)

    battery_state = NodeEnergyState(
        node_id=node.node_id,
        battery_capacity_kwh=node.battery_capacity_kwh,
        battery_current_kwh=node.battery_current_kwh,
        battery_min_reserve_kwh=compute_battery_reserve(node.battery_capacity_kwh),
    )
    balance = balance_node_energy(battery_state, generation_kwh, consumption_kwh)

    telemetry = TelemetryEvent(
        node_id=node.node_id,
        tick=tick,
        generation_kwh=generation_kwh,
        consumption_kwh=consumption_kwh,
        battery_before_kwh=balance.battery_before_kwh,
        battery_after_kwh=balance.battery_after_kwh,
        unmet_demand_kwh=balance.unmet_demand_kwh,
        exportable_energy_kwh=balance.exportable_energy_kwh,
        signature=_round_signature(node.node_id, tick, "telemetry"),
    )

    order: ProposedOrder | None = None
    is_peak_hour = 18 <= simulated_hour <= 22
    is_night = simulated_hour <= 5 or simulated_hour >= 19
    reserve = compute_battery_reserve(node.battery_capacity_kwh)
    local_energy_gap_kwh = max(consumption_kwh - generation_kwh, 0.0)
    stored_surplus_kwh = max(balance.battery_after_kwh - reserve, 0.0)
    same_tick_solar_surplus_kwh = max(generation_kwh - consumption_kwh, 0.0)
    battery_offer_kwh = 0.0

    if (
        balance.exportable_energy_kwh <= 0.01
        and same_tick_solar_surplus_kwh > 0.25
        and solar_factor >= 0.45
    ):
        battery_offer_kwh = round(min(same_tick_solar_surplus_kwh * 0.4, max(node.base_load_kw * 0.65, 0.25)), 4)

    if (
        balance.exportable_energy_kwh <= 0.01
        and is_peak_hour
        and node.has_solar
        and stored_surplus_kwh > 0.25
    ):
        battery_offer_kwh = max(
            battery_offer_kwh,
            round(min(stored_surplus_kwh * 0.35, max(node.base_load_kw * 0.75, 0.25)), 4),
        )

    if balance.exportable_energy_kwh > 0.01 or battery_offer_kwh > 0.01:
        sell_quantity = round(max(balance.exportable_energy_kwh, battery_offer_kwh), 4)
        battery_after_sale = balance.battery_after_kwh
        if battery_offer_kwh > 0:
            battery_floor = max(balance.battery_before_kwh, reserve)
            battery_after_sale = round(max(balance.battery_after_kwh - sell_quantity, battery_floor), 4)

        base_price = 4.1 + (0.4 if is_peak_hour else 0.1)
        limit_price = round(base_price + price_rng.uniform(0.2, 1.4), 2)
        order = ProposedOrder(
            node_id=node.node_id,
            owner_user_id=node.owner_user_id,
            tick=tick,
            side="sell",
            quantity_kwh=sell_quantity,
            limit_price=limit_price,
            battery_after_kwh=battery_after_sale,
            wallet_balance=node.wallet_balance,
            signature=_round_signature(node.node_id, tick, "sell-order"),
        )
    elif local_energy_gap_kwh > 0.01 and node.wallet_balance > 0:
        reserve_pressure = 0.8 if balance.battery_after_kwh <= reserve * 1.25 else 0.25
        consumer_pressure = 0.55 if not node.has_solar else 0.15
        time_pressure = 0.75 if is_peak_hour else 0.25 if is_night else 0.0
        base_price = 4.2 + reserve_pressure + consumer_pressure + time_pressure
        limit_price = round(base_price + price_rng.uniform(0.2, 1.25), 2)
        affordable_kwh = round(node.wallet_balance / max(limit_price + PLATFORM_FEE_PER_KWH, 0.01), 4)
        reserve_top_up = max((reserve * 1.25) - balance.battery_after_kwh, 0.0)
        buy_target_kwh = round(max(local_energy_gap_kwh, balance.unmet_demand_kwh) + reserve_top_up, 4)
        quantity_kwh = min(buy_target_kwh, affordable_kwh)
        if quantity_kwh > 0.01:
            order = ProposedOrder(
                node_id=node.node_id,
                owner_user_id=node.owner_user_id,
                tick=tick,
                side="buy",
                quantity_kwh=round(quantity_kwh, 4),
                limit_price=limit_price,
                battery_after_kwh=balance.battery_after_kwh,
                wallet_balance=node.wallet_balance,
                signature=_round_signature(node.node_id, tick, "buy-order"),
            )

    return telemetry, order
