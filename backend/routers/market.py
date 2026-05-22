from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from services.pb_client import pb

router = APIRouter(prefix="/api/market", tags=["Market Operations"])

class OrderPayload(BaseModel):
    node_id: str = Field(..., description="The unique PB ID of the house issuing the order")
    type: str = Field(..., description="Must be either 'bid' (buy) or 'offer' (sell)")
    quantity_kwh: float = Field(..., gt=0, description="Energy volume in kWh")
    target_price: float = Field(..., gt=0, description="Limit price for execution")


@router.post("/order")
async def submit_edge_order(payload: OrderPayload):
    """
    Ingests an autonomous market order from a smart meter.
    In a true decentralized deployment, this payload would also include a cryptographic 
    signature verify step before processing.
    """
    if payload.type not in ["bid", "offer"]:
        raise HTTPException(status_code=400, detail="Order type must be 'bid' or 'offer'.")
        
    try:
        order = await pb.create_market_order(
            node_id=payload.node_id,
            order_type=payload.type,
            qty=payload.quantity_kwh,
            price=payload.target_price
        )
        return {
            "status": "success",
            "order_id": order["id"],
            "message": "Order successfully routed to active liquidity pool."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Order placement failed: {str(e)}")