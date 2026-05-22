export const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://127.0.0.1:8000";

export const POCKETBASE_URL =
  process.env.NEXT_PUBLIC_POCKETBASE_URL ?? "http://127.0.0.1:8090";

export const MARKET_WS_URL =
  process.env.NEXT_PUBLIC_MARKET_WS_URL ?? "ws://127.0.0.1:8000/ws/market-stream";
