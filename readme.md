# VoltNet

VoltNet is a decentralized peer-to-peer micro-grid energy market clearing engine. It simulates neighborhood homes that generate, consume, store, buy, and sell electricity in real time. The goal is simple: homes with excess electricity can sell it locally at a fair price, while homes with higher consumption can buy from nearby providers using real wallet settlement logic.

The project was built for Algofest Hackathon 2026.

## What It Does

- Simulates a local micro-grid with solar producers, consumers, batteries, wallets, and live telemetry.
- Opens short market rounds where nodes submit buy bids and sell asks.
- Clears the market with a double-auction matcher.
- Settles trades by actually debiting buyer wallets and crediting seller wallets.
- Prevents overdrawn wallets and unpaid fills.
- Streams telemetry, orders, round state, and ledger events to the dashboard over WebSockets.
- Persists nodes, market orders, wallets, and ledger records in PocketBase.

## Tech Stack

- Backend: FastAPI, Python, async WebSockets
- Market engine: custom Python double-auction matcher and settlement flow
- Data store: PocketBase
- Frontend: Next.js, React, TypeScript, Tailwind CSS, shadcn-style UI components
- Package manager: Bun for the frontend

## Project Structure

```text
.
|-- backend/
|   |-- main.py                  # FastAPI app entrypoint
|   |-- schemas.py               # API and WebSocket payload models
|   |-- response_utils.py         # API response helpers
|   |-- core/
|   |   |-- balancer.py           # Battery and local energy balance logic
|   |   |-- matcher.py            # Double-auction clearing engine
|   |   `-- simulator.py          # Simulated homes, load, solar, and order generation
|   |-- routers/
|   |   |-- market.py             # Market REST endpoints
|   |   |-- users.py              # Node registration and portfolio endpoints
|   |   `-- websockets.py         # Real-time market stream and settlement loop
|   `-- services/
|       |-- pb_client.py          # PocketBase API client
|       |-- seeder.py             # Demo data seeder
|       `-- crypto.py             # Crypto/signature helpers
|-- frontend/
|   |-- app/                      # Next.js app routes
|   |-- components/               # Dashboard and UI components
|   |-- lib/config.ts             # Backend/PocketBase/WebSocket URLs
|   `-- package.json
|-- pocketbase/
|   |-- pocketbase.exe            # Local PocketBase binary
|   |-- pb_data/                  # Local PocketBase data
|   `-- pb_migrations/            # PocketBase schema migrations
`-- README.md
```

## Runtime Architecture

```text
PocketBase
  stores nodes, wallets, orders, and ledger entries
      ^
      |
FastAPI backend
  simulates grid ticks, balances energy, clears orders, settles wallets
      ^
      |
Next.js frontend
  displays live telemetry, market rounds, wallet movement, and trades
```

## Prerequisites

Install these before running the project:

- Python 3.11+
- Bun
- PocketBase is already included at `pocketbase/pocketbase.exe`

If the Python dependencies are not installed yet:

```powershell
pip install fastapi uvicorn httpx pydantic
```

## How To Run

Run the app with three terminals: PocketBase, backend, and frontend.

### 1. Start PocketBase

From the project root:

```powershell
cd pocketbase
.\pocketbase.exe serve
```

PocketBase should run at:

```text
http://127.0.0.1:8090
```

Keep this terminal open.

### 2. Seed Demo Nodes

In a new terminal, from the project root:

```powershell
cd backend
python services/seeder.py
```

This creates a demo neighborhood with solar prosumers, consumers, batteries, and starting wallet balances.

### 3. Start The Backend

In a new terminal, from the project root:

```powershell
cd backend
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Backend URLs:

```text
REST API:   http://127.0.0.1:8000
WebSocket:  ws://127.0.0.1:8000/ws/market-stream
```

### 4. Start The Frontend

In a new terminal, from the project root:

```powershell
cd frontend
bun install
bun run dev
```

The dashboard should run at:

```text
http://localhost:3000
```

## Frontend Environment

The frontend defaults are defined in `frontend/lib/config.ts`:

```text
NEXT_PUBLIC_BACKEND_URL=http://127.0.0.1:8000
NEXT_PUBLIC_POCKETBASE_URL=http://127.0.0.1:8090
NEXT_PUBLIC_MARKET_WS_URL=ws://127.0.0.1:8000/ws/market-stream
```

You only need a `.env.local` file if you want to override those values.

## Demo Flow

1. Start PocketBase.
2. Seed the demo nodes.
3. Start the backend.
4. Start the frontend.
5. Open the dashboard.
6. Register or select a node.
7. Click "Run simulation".
8. Watch telemetry, orders, market clearing, wallet debits, seller credits, and ledger entries update live.

## Backend API Highlights

```text
GET  /                                  Health check
POST /api/users/register                Register a grid node
GET  /api/users/list                    List grid nodes
GET  /api/users/portfolio/{node_id}     Get node wallet, battery, and latest order

POST /api/market/order                  Submit an order through REST
GET  /api/market/orders                 List market orders
GET  /api/market/ledger                 List settled ledger entries
GET  /api/market/rounds/current         Current market round state
GET  /api/market/rounds/{tick}          Historical round state
POST /api/market/simulation/start       Start simulation loop
POST /api/market/simulation/stop        Stop simulation loop

WS   /ws/market-stream                  Live telemetry, orders, and settlements
```

## Settlement Rules

The backend settlement logic is designed around real wallet movement:

- Buy orders are limited by the buyer's available wallet balance.
- A buyer cannot clear more electricity than they can actually pay for.
- Buyer wallets are debited only when a trade settles.
- Seller wallets are credited only for settled electricity.
- Sellers do not go negative for exporting power.
- Same-owner internal transfers do not create fake profit or platform fees.

## Useful Commands

Compile-check the backend:

```powershell
python -m compileall backend
```

Lint the frontend:

```powershell
cd frontend
bun run lint
```

Build the frontend:

```powershell
cd frontend
bun run build
```

## Troubleshooting

If the dashboard shows no data:

- Make sure PocketBase is running on port `8090`.
- Make sure the backend is running on port `8000`.
- Seed the nodes with `python services/seeder.py`.
- Refresh the frontend after the backend starts.
- Click "Run simulation" in the dashboard.

If backend requests fail:

- Check that PocketBase collections/migrations are loaded.
- Confirm `http://127.0.0.1:8090` opens in the browser.
- Restart the backend after PocketBase is available.

If frontend WebSocket updates do not appear:

- Confirm `ws://127.0.0.1:8000/ws/market-stream` is reachable.
- Confirm `NEXT_PUBLIC_MARKET_WS_URL` points to the backend WebSocket URL.
- Restart `bun run dev` after changing any `.env.local` values.
