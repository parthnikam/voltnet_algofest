from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from services.pb_client import pb
from routers import users, market, websockets
from pydantic import BaseModel
import asyncio 


app = FastAPI(title="VoltNet Microgrid Core Engine")

app.add_middleware(
    CORSMiddleware, 
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(users.router)
app.include_router(market.router)
app.include_router(websockets.router)

active_connections: list[WebSocket] = []

@app.get("/")
def read_root():
    return {"status":"VoltNet Engine Operational"}


@app.get("/api/portfolio/{node_id}")
async def get_user_portfolio(node_id: str):
    try: 
        node_data = await pb.get_node_by_id(node_id)
        return {
            "id": node_data["id"],
            "name": node_data["name"],
            "wallet_balance": node_data["wallet_balance"],
            "battery": {
                "current": node_data["battery_current"],
                "capacity": node_data["battery_capacity"]
            },
            "has_solar": node_data["has_solar"]
        }
    except Exception:
        raise HTTPException(status_code=404, detail="Grid hardware node not found")
    


class MarketOrder(BaseModel):
    node_id: str 
    type: str 
    quantity_kwh: float 
    target_price: float 

@app.post("/api/market/order")
async def submit_edge_order(payload: MarketOrder):
    
    if payload.type not in ["bid", "offer"]:
        raise HTTPException(status_code=400,detail="Invalid order type.")
    
    order = await pb.create_market_order(
        payload.node_id,
        payload.type,
        payload.quantity_kwh,
        payload.target_price
    )

    return {
        "status": "success",
        "order_id": order["id"],
        "msg": "Order placed in ledger pool."
    }


@app.websocket("/ws/market-stream")
async def market_stream_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)

    try: 
        while True:
            await asyncio.sleep(10)
    except WebSocketDisconnect:
        active_connections.remove(websocket)

async def broadcast_market_tick(data: dict):
    for connection in active_connections:
        try: 
            await connection.send_json(data)
        except Exception:
            active_connections.remove(connection)