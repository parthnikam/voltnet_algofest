# VoltNet 



## Project Layout
```
voltnet-core/
│
├── pocketbase/                  # Local pocketbase binary directory
│   └── pocketbase.exe           # Run this locally to handle auth, user nodes, and ledger logs
│
├── backend/                     # Python asynchronous execution engine
│   ├── main.py                  # Entry point: Initializes FastAPI app, routes, and background loops
│   ├── config.py                # Configuration constants (Grid limits, Tick intervals, API keys)
│   │
│   ├── core/
│   │   ├── simulator.py         # The Time-Clock loop; calculates daily solar & consumption curves
│   │   ├── matcher.py           # The Double-Auction engine (collects bids, sorts, finds clearing price)
│   │   └── balancer.py          # Node logic: Manages battery charging/discharging and grid fallbacks
│   │
│   ├── services/
│   │   ├── pb_client.py         # PocketBase wrapper client to fetch/update node wallets and histories
│   │   └── crypto.py            # Keypair generation and telemetry digital signature verification
│   │
│   └── routers/
│       ├── market.py            # REST endpoints for current market state, historical data
│       ├── users.py             # Impersonation and profile switching endpoint handlers
│       └── websockets.py        # Broadcasts real-time state ticks to the frontend
│
├── frontend/                    # Next.js / React application
│   ├── src/
│   │   ├── components/
│   │   │   ├── Dashboard.tsx    # Parent container managing state and user switching
│   │   │   ├── NodeGrid.tsx     # Visual grid layout showing all active house cards
│   │   │   ├── MarketChart.tsx  # Live line chart tracking Market Clearing Price vs Utility Price
│   │   │   └── OrderBook.tsx    # Live ticker stream displaying executed matches
│   │   │
│   │   └── hooks/
│   │       └── useWebSocket.ts  # Custom hook to ingest real-time ticks from FastAPI smoothly
│   │
│   └── package.json
│
└── README.md

```



## Module Chart

```
                     ┌────────────────────────────────┐
                     │     pocketbase (Data Hub)      │
                     │  - Accounts, Wallets, Ledger   │
                     └───────────────▲────────────────┘
                                     │ (Reads / Writes)
                                     ▼
┌───────────────────────── backend (FastAPI) ─────────────────────────┐
│                                                                     │
│  ┌──────────────────┐    ┌─────────────────┐    ┌────────────────┐  │
│  │   simulator.py   │───►│   balancer.py   │───►│   matcher.py   │  │
│  │ (Ticks Clock &   │    │ (Manages Local  │    │ (Executes the  │  │
│  │  Generates Load) │    │  Battery State) │    │ Double Auction)│  │
│  └──────────────────┘    └─────────────────┘    └───────┬────────┘  │
│                                                         │           │
│                                                         ▼           │
│                                                [websockets.py]      │
│                                                         │           │
└─────────────────────────────────────────────────────────┼───────────┘
                                                          │ (Live Broadcast)
                                                          ▼
                                            ┌─────────────────────────┐
                                            │   frontend (Next.js)    │
                                            │ - Interactive Dashboard │
                                            └─────────────────────────┘
```