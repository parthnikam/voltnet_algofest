from dataclasses import dataclass


@dataclass(slots=True)
class NodeEnergyState:
    node_id: str
    battery_capacity_kwh: float
    battery_current_kwh: float
    battery_min_reserve_kwh: float


@dataclass(slots=True)
class BalanceOutcome:
    battery_before_kwh: float
    battery_after_kwh: float
    unmet_demand_kwh: float
    exportable_energy_kwh: float


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def compute_battery_reserve(capacity_kwh: float) -> float:
    if capacity_kwh <= 0:
        return 0.0
    return round(capacity_kwh * 0.15, 4)


def balance_node_energy(
    state: NodeEnergyState,
    generation_kwh: float,
    consumption_kwh: float,
) -> BalanceOutcome:
    battery_before = clamp(state.battery_current_kwh, 0.0, max(state.battery_capacity_kwh, 0.0))
    reserve = clamp(state.battery_min_reserve_kwh, 0.0, max(state.battery_capacity_kwh, 0.0))
    net_energy_kwh = generation_kwh - consumption_kwh

    if net_energy_kwh >= 0:
        charge_room = max(state.battery_capacity_kwh - battery_before, 0.0)
        charged = min(net_energy_kwh, charge_room)
        battery_after = battery_before + charged
        exportable = max(net_energy_kwh - charged, 0.0)
        unmet = 0.0
    else:
        deficit = abs(net_energy_kwh)
        available_discharge = max(battery_before - reserve, 0.0)
        discharged = min(deficit, available_discharge)
        battery_after = battery_before - discharged
        unmet = max(deficit - discharged, 0.0)
        exportable = 0.0

    return BalanceOutcome(
        battery_before_kwh=round(battery_before, 4),
        battery_after_kwh=round(clamp(battery_after, 0.0, max(state.battery_capacity_kwh, 0.0)), 4),
        unmet_demand_kwh=round(unmet, 4),
        exportable_energy_kwh=round(exportable, 4),
    )
