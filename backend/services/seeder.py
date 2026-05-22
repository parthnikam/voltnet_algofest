import asyncio
import httpx

POCKETBASE_URL = "http://127.0.0.1:8090/api/collections"

# Hardcoded realistic test profiles for a 5-house microgrid ecosystem
TEST_NEIGHBORHOOD = [
    {
        "name": "Alpha Prosumer (Tesla Home)",
        "wallet_balance": 100.00,
        "has_solar": True,
        "battery_capacity_kwh": 13.5,
        "battery_current_kwh": 5.0,
        "battery_min_reserve_kwh": 2.025,
        "max_charge_rate_kw": 4.0,
        "max_discharge_rate_kw": 4.0,
        "max_solar_kw": 5.5,
        "base_load_kw": 1.2,
        "grid_import_enabled": True,
        "grid_export_enabled": True,
        "status": "active",
        "public_key": "ecdsa_pub_key_mock_alpha_01"
    },
    {
        "name": "Beta Prosumer (Solar Heavy)",
        "wallet_balance": 150.00,
        "has_solar": True,
        "battery_capacity_kwh": 20.0,
        "battery_current_kwh": 10.0,
        "battery_min_reserve_kwh": 3.0,
        "max_charge_rate_kw": 5.5,
        "max_discharge_rate_kw": 5.5,
        "max_solar_kw": 4.8,
        "base_load_kw": 1.5,
        "grid_import_enabled": True,
        "grid_export_enabled": True,
        "status": "active",
        "public_key": "ecdsa_pub_key_mock_beta_02"
    },
    {
        "name": "Gamma Prosumer (Solar Heavy)",
        "wallet_balance": 120.00,
        "has_solar": True,
        "battery_capacity_kwh": 20.0,
        "battery_current_kwh": 10.0,
        "battery_min_reserve_kwh": 3.0,
        "max_charge_rate_kw": 5.0,
        "max_discharge_rate_kw": 5.0,
        "max_solar_kw": 4.2,
        "base_load_kw": 1.4,
        "grid_import_enabled": True,
        "grid_export_enabled": True,
        "status": "active",
        "public_key": "ecdsa_pub_key_mock_gamma_06"
    },
    {
        "name": "Charlie Consumer (Standard AC Home)",
        "wallet_balance": 200.00,
        "has_solar": False,
        "battery_capacity_kwh": 0.0,
        "battery_current_kwh": 0.0,
        "battery_min_reserve_kwh": 0.0,
        "max_charge_rate_kw": 0.0,
        "max_discharge_rate_kw": 0.0,
        "max_solar_kw": 0.0,
        "base_load_kw": 2.1,
        "grid_import_enabled": True,
        "grid_export_enabled": False,
        "status": "active",
        "public_key": "ecdsa_pub_key_mock_charlie_03"
    },
    {
        "name": "Delta Consumer (EV Charging Station)",
        "wallet_balance": 500.00,
        "has_solar": False,
        "battery_capacity_kwh": 0.0,
        "battery_current_kwh": 0.0,
        "battery_min_reserve_kwh": 0.0,
        "max_charge_rate_kw": 0.0,
        "max_discharge_rate_kw": 0.0,
        "max_solar_kw": 0.0,
        "base_load_kw": 3.0,
        "grid_import_enabled": True,
        "grid_export_enabled": False,
        "status": "active",
        "public_key": "ecdsa_pub_key_mock_delta_04"
    },
    {
        "name": "Eco Balanced Cottage",
        "wallet_balance": 75.00,
        "has_solar": True,
        "battery_capacity_kwh": 7.0,
        "battery_current_kwh": 3.5,
        "battery_min_reserve_kwh": 1.05,
        "max_charge_rate_kw": 2.2,
        "max_discharge_rate_kw": 2.2,
        "max_solar_kw": 2.6,
        "base_load_kw": 0.9,
        "grid_import_enabled": True,
        "grid_export_enabled": True,
        "status": "active",
        "public_key": "ecdsa_pub_key_mock_eco_05"
    }
]


async def seed_microgrid():
    async with httpx.AsyncClient(base_url=POCKETBASE_URL) as client:
        print(" VoltNet Seeder: Connecting to PocketBase...")
        
        # 1. Clean up existing records to ensure idempotent test states
        try:
            get_existing = await client.get("/nodes/records?perPage=50")
            existing_nodes = get_existing.json().get("items", [])
            if existing_nodes:
                print(f" Found {len(existing_nodes)} old nodes. Purging for clean simulation run...")
                for node in existing_nodes:
                    await client.delete(f"/nodes/records/{node['id']}")
        except Exception as e:
            print(f" Clean step skipped or collection is empty: {e}")

        # 2. Populate new distinct test profiles
        print("Seeding a diverse test environment...")
        for house in TEST_NEIGHBORHOOD:
            try:
                response = await client.post("/nodes/records", json=house)
                if response.status_code in [200, 201]:
                    record = response.json()
                    print(f"Created {record['name']} | ID: {record['id']} | Solar: {record['has_solar']}")
                else:
                    print(f"Failed to create {house['name']}: {response.text}")
            except Exception as e:
                print(f"Network error creating node {house['name']}: {str(e)}")

        print("\nSeeding complete! Your local grid database is ready for testing.")

if __name__ == "__main__":
    # Allows you to execute this script standalone from your terminal
    asyncio.run(seed_microgrid())
