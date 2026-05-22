from fastapi import APIRouter, HTTPException
from services.pb_client import pb
from pydantic import BaseModel

router = APIRouter(prefix="/api/users", tags=["Users & Portfolios"])

class AddNodePaylod(BaseModel):
    name:str 
    owner: str 
    has_solar: bool 
    battery_capacity: float
    initial_wallet: float 



@router.post("/register")
async def register_new_grid_node(payload: AddNodePaylod):
    # add new houses into the grid 
    mock_house_data = {
        "name": payload.name,
        "owner": payload.owner,
        "wallet_balance": payload.initial_wallet,
        "has_solar": payload.has_solar,
        "battery_capacity": payload.battery_capacity,
        "battery_current": payload.battery_capacity * 0.5 if payload.has_solar else 0.0,
        "public_key": f"ecdsa_pub_generated_mock_{payload.name.lower().replace(' ', '_')}"
    }    

    try:
        # Reuses your standard HTTP client wrapper logic
        import httpx
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8090/api/collections") as client:
            response = await client.post("/nodes/records", json=mock_house_data)
            if response.status_code in [200, 201]:
                return {"status": "success", "node": response.json()}
            else:
                raise HTTPException(status_code=400, detail=f"PocketBase rejection: {response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal database registration failure: {str(e)}")


@router.get("/list")
async def list_grid_nodes():
    try:
        nodes = await pb.get_all_nodes()
        data = [{"id":node["id"], "name":node["name"],"has_solar":node["has_solar"]} for node in nodes]
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch grid nodes: {str(e)}")    


@router.get("/portfolio/{node_id}")
async def get_node_portfolio(node_id: str):
    try:
        node_data = await pb.get_node_by_id(node_id)
        data = {
            "id": node_data["id"],
            "name": node_data["name"],
            "wallet_balance": node_data["wallet_balance"],
            "battery": {
                "current": node_data["battery_current"],
                "capacity": node_data["battery_capacity"]
            },
            "has_solar": node_data["has_solar"]
        }

        return data
    except Exception:
        raise HTTPException(status_code=404, detail="Grid hardware node not found.")