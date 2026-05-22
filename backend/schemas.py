from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResponseEnvelope(StrictModel):
    status: str
    message: str
    data: Any = None


class NodeStatus(str, Enum):
    ACTIVE = "active"
    OFFLINE = "offline"
    SUSPENDED = "suspended"


class RoundStatus(str, Enum):
    OPEN = "open"
    CLEARING = "clearing"
    SETTLED = "settled"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class WalletSummary(StrictModel):
    balance: Optional[float] = None
    reserved: float = 0.0
    currency: str = "INR"


class BatterySummary(StrictModel):
    current_kwh: float
    capacity_kwh: float


class NodeRegistrationRequest(StrictModel):
    owner_user_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    has_solar: bool
    battery_capacity_kwh: float = Field(..., ge=0)
    initial_battery_kwh: float = Field(..., ge=0)
    initial_wallet_balance: Optional[float] = Field(default=None, ge=0)
    max_solar_kw: float = Field(default=0.0, ge=0)
    base_load_kw: float = Field(default=0.0, ge=0)


class NodeSummary(StrictModel):
    id: str
    name: str
    owner_user_id: Optional[str] = None
    has_solar: bool
    status: str


class PortfolioResponse(StrictModel):
    id: str
    name: str
    status: str
    owner_user_id: Optional[str] = None
    has_solar: bool
    max_solar_kw: float = 0.0
    base_load_kw: float = 0.0
    wallet: WalletSummary
    battery: BatterySummary
    latest_order: Optional[dict[str, Any]] = None


class OrderRequest(StrictModel):
    node_id: str = Field(..., min_length=1)
    owner_user_id: str = Field(..., min_length=1)
    tick: int = Field(..., ge=0)
    side: OrderSide
    quantity_kwh: float = Field(..., gt=0)
    limit_price: float = Field(..., gt=0)
    signature: str = Field(..., min_length=1)
    telemetry_hash: Optional[str] = None


class OrderRecord(StrictModel):
    id: str
    node_id: Optional[str] = None
    owner_user_id: Optional[str] = None
    tick: Optional[int] = None
    side: Optional[str] = None
    quantity_kwh: Optional[float] = None
    remaining_kwh: Optional[float] = None
    limit_price: Optional[float] = None
    status: Optional[str] = None
    source: Optional[str] = None
    signature: Optional[str] = None
    telemetry_hash: Optional[str] = None
    created: Optional[str] = None
    updated: Optional[str] = None


class LedgerRecord(StrictModel):
    id: str
    tick: Optional[int] = None
    buyer_node_id: Optional[str] = None
    seller_node_id: Optional[str] = None
    quantity_kwh: Optional[float] = None
    unit_price: Optional[float] = None
    total_cost: Optional[float] = None
    settlement_status: Optional[str] = None
    created: Optional[str] = None


class WebSocketEnvelope(StrictModel):
    type: Literal["HELLO", "TELEMETRY_SUBMIT", "ORDER_SUBMIT", "ACK_LEDGER"]
    payload: dict[str, Any]


class WebSocketHelloPayload(StrictModel):
    node_id: str = Field(..., min_length=1)
    owner_user_id: str = Field(..., min_length=1)
    auth_token: str = Field(..., min_length=1)
    client_pubkey: Optional[str] = None


class TelemetryPayload(StrictModel):
    tick: int = Field(..., ge=0)
    node_id: str = Field(..., min_length=1)
    generation_kw: float = Field(..., ge=0)
    consumption_kw: float = Field(..., ge=0)
    battery_kwh: float = Field(..., ge=0)
    signature: str = Field(..., min_length=1)


class AckLedgerPayload(StrictModel):
    ledger_entry_id: str = Field(..., min_length=1)
    tick: int = Field(..., ge=0)
