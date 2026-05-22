# backend/simulate_agents.py
import asyncio
import websockets
import json
import random
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("HouseAgent")

# WebSocket URI pointing to your running FastAPI server
WS_URI = "ws://127.0.0.1:8000/ws/market-stream"

class HouseAgent:
    def __init__(self, node_id: str, base_load: float, max_solar_capacity: float):
        self.node_id = node_id
        self.base_load = base_load  # Average continuous draw (e.g., fridge, idling tech) in kW
        self.max_solar_capacity = max_solar_capacity  # Max kW output at absolute solar peak

    def simulate_electricity(self, hour: int, solar_factor: float):
        """Pseudo-simulates electricity consumption and generation for this specific hour."""
        
        # 1. Base consumption behavior (Peaks around breakfast 7-9 AM and dinner 6-10 PM)
        if 7 <= hour <= 9 or 18 <= hour <= 22:
            consumption_factor = random.uniform(1.8, 2.5)  # Heavy appliance usage
        else:
            consumption_factor = random.uniform(0.8, 1.2)  # Low baseline usage
            
        current_consumption = self.base_load * consumption_factor
        
        # 2. Solar generation behavior (Driven directly by the core broadcast engine factor)
        # Adding a minor cloud/efficiency variance factor (-5% to +5%)
        cloud_noise = random.uniform(0.95, 1.05)
        current_generation = self.max_solar_capacity * solar_factor * cloud_noise if solar_factor > 0 else 0.0

        # Round values nicely for clean network payloads
        return round(current_generation, 3), round(current_consumption, 3)

    async def run(self):
        """Connects to the market stream, listens for ticks, and submits immediate bids."""
        logger.info(f"🏡 House [{self.node_id}] initializing agent loop...")
        
        async for websocket in websockets.connect(WS_URI):
            try:
                logger.info(f"✅ House [{self.node_id}] successfully linked to Microgrid Core.")
                
                async for raw_message in websocket:
                    message = json.loads(raw_message)
                    
                    # Intercept the broadcast heartbeat from main.py loop
                    if message.get("type") == "TELEMETRY_BROADCAST":
                        tick = message.get("tick")
                        hour = message.get("simulated_hour")
                        solar_factor = message.get("solar_availability_factor")
                        
                        # Execute our pseudo-simulation math formulas
                        generation, consumption = self.simulate_electricity(hour, solar_factor)
                        net_balance = generation - consumption
                        
                        # Decide market actions based on our net energy output
                        if net_balance > 0:
                            action = "SELL"
                            energy_amount = net_balance
                            # Sellers want to sell high, adjust baseline price target dynamically
                            target_price = round(random.uniform(4.5, 6.0), 2) 
                        else:
                            action = "BUY"
                            energy_amount = abs(net_balance)
                            # Buyers want to buy cheap
                            target_price = round(random.uniform(2.5, 4.0), 2)

                        # Assemble the strict JSON payload format your websockets.py router expects
                        bid_payload = {
                            "type": "SUBMIT_BID",
                            "payload": {
                                "node_id": self.node_id,
                                "tick": tick,
                                "action": action,
                                "quantity_kwh": energy_amount,
                                "price_per_kwh": target_price
                            }
                        }
                        
                        # Push the bid back over the wire while the 2s bidding window is open
                        await websocket.send(json.dumps(bid_payload))
                        logger.info(
                            f"\n🏠 House {self.node_id} (Hour {hour:02d}:00) -> "
                            f"\n⚡ Gen: {generation}kW | Con: {consumption}kW | "
                            f"\n💵 Fired Bid: {action} {energy_amount}kWh @ ₹{target_price}/kWh"
                        )
            
            except websockets.ConnectionClosed:
                logger.warning(f"❌ Connection lost for house {self.node_id}. Reconnecting in 3s...")
                await asyncio.sleep(3)
            except Exception as e:
                logger.error(f"Unexpected error in agent {self.node_id}: {e}")

# Runner block to spin up multiple distinct houses on the local async loop
async def main():
    # Creating 3 test nodes with varying energy profiles
    houses = [
        HouseAgent(node_id="NODE_ALPHA_SOLAR", base_load=1.2, max_solar_capacity=5.5),  # Big solar array
        HouseAgent(node_id="NODE_BRAVO_STANDARD", base_load=1.5, max_solar_capacity=2.0), # Moderate setup
        HouseAgent(node_id="NODE_CHARLIE_CONSUMER", base_load=2.5, max_solar_capacity=0.0) # Consumer only, no solar
    ]
    
    # Run all houses parallel concurrently in the background
    await asyncio.gather(*[house.run() for house in houses])

if __name__ == "__main__":
    asyncio.run(main())