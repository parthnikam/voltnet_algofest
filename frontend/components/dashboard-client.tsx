"use client";

import { useEffect, useEffectEvent, useRef, useState } from "react";

import { GraphView } from "@/components/graph-view";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { BACKEND_URL, MARKET_WS_URL, POCKETBASE_URL } from "@/lib/config";

type AuthUser = {
  id: string;
  email: string;
  name?: string;
  wallet_balance?: number;
  wallet_reserved?: number;
  public_key?: string;
  kyc_status?: string;
};

type NodeRecord = {
  id: string;
  name: string;
  owner_user_id?: string | null;
  has_solar: boolean;
  status: string;
};

type Portfolio = {
  id: string;
  name: string;
  status: string;
  owner_user_id?: string | null;
  has_solar: boolean;
  max_solar_kw: number;
  base_load_kw: number;
  wallet: {
    balance: number;
    reserved: number;
  };
  battery: {
    current_kwh: number;
    capacity_kwh: number;
  };
};

type RoundState = {
  tick: number;
  simulated_hour: number;
  status: string;
  window_open: boolean;
  simulation_enabled?: boolean;
  orders_collected?: number;
  telemetry_count?: number;
};

type FeedEvent = {
  id: string;
  title: string;
  detail: string;
  timestamp: string;
};

type TradeEvent = {
  buyer_node_id: string;
  seller_node_id: string;
  quantity_kwh: number;
  unit_price: number;
  total_cost: number;
};

type TelemetryEvent = {
  generation_kwh: number;
  consumption_kwh: number;
  battery_before_kwh: number;
  battery_after_kwh: number;
};

const storageKey = "voltnet-session";

function formatMoney(value: number) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(value);
}

function formatEnergy(value: number) {
  return `${value.toFixed(2)} kWh`;
}

async function parseEnvelope<T>(response: Response): Promise<T> {
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload?.message ?? "Request failed.");
  }
  return payload.data as T;
}

async function fetchGridSnapshot() {
  const [nodes, round] = await Promise.all([
    fetch(`${BACKEND_URL}/api/users/list`).then((response) =>
      parseEnvelope<NodeRecord[]>(response),
    ),
    fetch(`${BACKEND_URL}/api/market/rounds/current`).then((response) =>
      parseEnvelope<RoundState>(response),
    ),
  ]);

  return { nodes, round };
}

async function fetchPortfolioSnapshot(nodeId: string) {
  return fetch(`${BACKEND_URL}/api/users/portfolio/${nodeId}`).then((response) =>
    parseEnvelope<Portfolio>(response),
  );
}

export function DashboardClient() {
  const [mode, setMode] = useState<"login" | "signup">("signup");
  const [authUser, setAuthUser] = useState<AuthUser | null>(null);
  const [authToken, setAuthToken] = useState("");
  const [nodes, setNodes] = useState<NodeRecord[]>([]);
  const [ownedNodes, setOwnedNodes] = useState<NodeRecord[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState("");
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [roundState, setRoundState] = useState<RoundState | null>(null);
  const [feed, setFeed] = useState<FeedEvent[]>([]);
  const [telemetryByNode, setTelemetryByNode] = useState<Record<string, TelemetryEvent>>({});
  const [orderSideByNode, setOrderSideByNode] = useState<Record<string, "buy" | "sell" | undefined>>({});
  const [trades, setTrades] = useState<TradeEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const websocketRef = useRef<WebSocket | null>(null);

  const [authForm, setAuthForm] = useState({
    name: "",
    email: "",
    password: "",
    initialWallet: "250",
  });
  const [nodeForm, setNodeForm] = useState({
    name: "",
    hasSolar: "yes",
    batteryCapacity: "12",
    initialBattery: "6",
    maxSolar: "4.5",
    baseLoad: "1.4",
  });

  useEffect(() => {
    const raw = window.localStorage.getItem(storageKey);
    if (!raw) {
      return;
    }

    try {
      const session = JSON.parse(raw) as { user: AuthUser; token: string };
      const timeout = window.setTimeout(() => {
        setAuthUser(session.user);
        setAuthToken(session.token);
        setMessage(`Welcome back, ${session.user.email}`);
      }, 0);
      return () => window.clearTimeout(timeout);
    } catch {
      window.localStorage.removeItem(storageKey);
    }
  }, []);

  const appendFeed = useEffectEvent((title: string, detail: string) => {
    setFeed((prev) => [
      {
        id: `${Date.now()}-${Math.random()}`,
        title,
        detail,
        timestamp: new Date().toLocaleTimeString(),
      },
      ...prev,
    ].slice(0, 20));
  });

  const refreshGrid = useEffectEvent(async () => {
    const { nodes: fetchedNodes, round: currentRound } = await fetchGridSnapshot();

    setNodes(fetchedNodes);
    setRoundState(currentRound);

    if (authUser) {
      const mine = fetchedNodes.filter((node) => node.owner_user_id === authUser.id);
      setOwnedNodes(mine);
      if (!selectedNodeId && mine[0]) {
        setSelectedNodeId(mine[0].id);
      }
    }
  });

  const refreshPortfolio = useEffectEvent(async (nodeId: string) => {
    const data = await fetchPortfolioSnapshot(nodeId);
    setPortfolio(data);
  });

  useEffect(() => {
    if (!authUser) {
      return;
    }

    const timeout = window.setTimeout(() => {
      void refreshGrid();
    }, 0);
    const interval = window.setInterval(() => {
      void refreshGrid();
    }, 4000);

    return () => {
      window.clearInterval(interval);
      window.clearTimeout(timeout);
    };
  }, [authUser]);

  useEffect(() => {
    if (!selectedNodeId) {
      return;
    }

    const timeout = window.setTimeout(() => {
      void refreshPortfolio(selectedNodeId);
    }, 0);
    const interval = window.setInterval(() => {
      void refreshPortfolio(selectedNodeId);
    }, 4000);

    return () => {
      window.clearInterval(interval);
      window.clearTimeout(timeout);
    };
  }, [selectedNodeId]);

  useEffect(() => {
    if (!selectedNodeId || !authUser || !authToken) {
      websocketRef.current?.close();
      websocketRef.current = null;
      return;
    }

    const socket = new WebSocket(MARKET_WS_URL);
    websocketRef.current = socket;

    socket.onopen = () => {
      socket.send(
        JSON.stringify({
          type: "HELLO",
          payload: {
            node_id: selectedNodeId,
            owner_user_id: authUser.id,
            auth_token: authToken,
            client_pubkey: authUser.public_key ?? `frontend-${authUser.id}`,
          },
        }),
      );
    };

    socket.onmessage = (event) => {
      const incoming = JSON.parse(event.data) as {
        type: string;
        payload: Record<string, unknown>;
      };

      if (
        incoming.type === "ROUND_OPEN" ||
        incoming.type === "ROUND_SETTLED" ||
        incoming.type === "ROUND_CLOSED"
      ) {
        setRoundState((prev) => ({
          ...(prev ?? {}),
          ...(incoming.payload as unknown as RoundState),
        }));
      }

      if (incoming.type === "ORDER_ACCEPTED") {
        const payload = incoming.payload as unknown as {
          node_id: string;
          side: "buy" | "sell";
          quantity_kwh: number;
          limit_price: number;
          source?: string;
        };
        setOrderSideByNode((prev) => ({ ...prev, [payload.node_id]: payload.side }));
        appendFeed(
          `${payload.node_id} placed ${payload.side.toUpperCase()} order`,
          `${formatEnergy(payload.quantity_kwh)} at ${formatMoney(payload.limit_price)} ${payload.source ? `via ${payload.source}` : ""}`,
        );
      }

      if (incoming.type === "LEDGER_ENTRY") {
        if (incoming.payload.event === "telemetry") {
          const payload = incoming.payload as unknown as {
            node_id: string;
            generation_kwh: number;
            consumption_kwh: number;
            battery_before_kwh: number;
            battery_after_kwh: number;
          };
          setTelemetryByNode((prev) => ({
            ...prev,
            [payload.node_id]: {
              generation_kwh: payload.generation_kwh,
              consumption_kwh: payload.consumption_kwh,
              battery_before_kwh: payload.battery_before_kwh,
              battery_after_kwh: payload.battery_after_kwh,
            },
          }));
          return;
        }

        const payload = incoming.payload as unknown as TradeEvent;
        setTrades((prev) => [payload, ...prev].slice(0, 40));
        appendFeed(
          `${payload.seller_node_id} sold to ${payload.buyer_node_id}`,
          `${formatEnergy(payload.quantity_kwh)} at ${formatMoney(payload.unit_price)} for ${formatMoney(payload.total_cost)}`,
        );
      }

      if (incoming.type === "ERROR") {
        setMessage(String(incoming.payload.message ?? "WebSocket error"));
      }
    };

    socket.onclose = () => {
      websocketRef.current = null;
    };

    return () => {
      socket.close();
    };
  }, [authToken, authUser, selectedNodeId]);

  async function handleLogin(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setMessage("");
    try {
      const response = await fetch(
        `${POCKETBASE_URL}/api/collections/users/auth-with-password`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            identity: authForm.email,
            password: authForm.password,
          }),
        },
      );
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.message ?? "Login failed.");
      }
      const user = payload.record as AuthUser;
      const token = payload.token as string;
      setAuthUser(user);
      setAuthToken(token);
      window.localStorage.setItem(storageKey, JSON.stringify({ user, token }));
      setMessage(`Logged in as ${user.email}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Login failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSignup(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setMessage("");
    try {
      const signupResponse = await fetch(
        `${POCKETBASE_URL}/api/collections/users/records`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email: authForm.email,
            password: authForm.password,
            passwordConfirm: authForm.password,
            name: authForm.name,
            wallet_balance: Number(authForm.initialWallet),
            wallet_reserved: 0,
            public_key: `pb-user-${Date.now()}`,
            kyc_status: "verified",
          }),
        },
      );
      const signupPayload = await signupResponse.json();
      if (!signupResponse.ok) {
        throw new Error(signupPayload?.message ?? "Signup failed.");
      }

      const authResponse = await fetch(
        `${POCKETBASE_URL}/api/collections/users/auth-with-password`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            identity: authForm.email,
            password: authForm.password,
          }),
        },
      );
      const authPayload = await authResponse.json();
      if (!authResponse.ok) {
        throw new Error(authPayload?.message ?? "Could not log in after signup.");
      }

      const user = authPayload.record as AuthUser;
      const token = authPayload.token as string;
      setAuthUser(user);
      setAuthToken(token);
      window.localStorage.setItem(storageKey, JSON.stringify({ user, token }));
      const { nodes: fetchedNodes, round } = await fetchGridSnapshot();
      setNodes(fetchedNodes);
      setRoundState(round);
      setMessage(`Account created for ${user.email}. Add your home node below.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Signup failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateNode(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!authUser) {
      setMessage("Please login first.");
      return;
    }

    setLoading(true);
    setMessage("");
    try {
      await fetch(`${BACKEND_URL}/api/users/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          owner_user_id: authUser.id,
          name: nodeForm.name,
          has_solar: nodeForm.hasSolar === "yes",
          battery_capacity_kwh: Number(nodeForm.batteryCapacity),
          initial_battery_kwh: Number(nodeForm.initialBattery),
          initial_wallet_balance: Number(authForm.initialWallet),
          max_solar_kw: Number(nodeForm.maxSolar),
          base_load_kw: Number(nodeForm.baseLoad),
        }),
      }).then((response) => parseEnvelope<Record<string, unknown>>(response));

      const { nodes: fetchedNodes, round } = await fetchGridSnapshot();
      setNodes(fetchedNodes);
      setRoundState(round);
      const mine = fetchedNodes.filter((node) => node.owner_user_id === authUser.id);
      setOwnedNodes(mine);
      if (mine[0]) {
        setSelectedNodeId(mine[0].id);
      }
      setMessage("Home node created and attached to your PocketBase user.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to create node.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSimulation(action: "start" | "stop") {
    setLoading(true);
    try {
      const data = await fetch(`${BACKEND_URL}/api/market/simulation/${action}`, {
        method: "POST",
      }).then((response) => parseEnvelope<RoundState>(response));
      setRoundState(data);
      setMessage(action === "start" ? "Simulation running." : "Simulation paused.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Simulation control failed.");
    } finally {
      setLoading(false);
    }
  }

  function logout() {
    setAuthUser(null);
    setAuthToken("");
    setOwnedNodes([]);
    setSelectedNodeId("");
    setPortfolio(null);
    setTelemetryByNode({});
    setOrderSideByNode({});
    setTrades([]);
    setFeed([]);
    window.localStorage.removeItem(storageKey);
    setMessage("Signed out.");
  }

  const selectedTelemetry = selectedNodeId ? telemetryByNode[selectedNodeId] : null;
  const myNetMoney = trades.reduce((total, trade) => {
    if (trade.seller_node_id === selectedNodeId) {
      return total + trade.total_cost;
    }
    if (trade.buyer_node_id === selectedNodeId) {
      return total - trade.total_cost;
    }
    return total;
  }, 0);
  const latestMyTrade =
    trades.find(
      (trade) =>
        trade.seller_node_id === selectedNodeId || trade.buyer_node_id === selectedNodeId,
    ) ?? null;

  return (
    <div className="min-h-screen bg-black text-white">
      <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-6 px-4 py-6 md:px-8">
        <header className="flex flex-col gap-4 rounded-[28px] border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.08),rgba(255,255,255,0.02))] p-6 md:flex-row md:items-end md:justify-between">
          <div className="space-y-3">
            <Badge>VoltNet Console</Badge>
            <div>
              <h1 className="text-3xl font-semibold tracking-tight md:text-5xl">
                Local energy exchange in motion.
              </h1>
              <p className="mt-3 max-w-3xl text-sm leading-7 text-zinc-400 md:text-base">
                Sign in as a homeowner, create your node, then watch the grid generate,
                bid, clear, and settle in real time over the market stream.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Badge>{roundState?.simulation_enabled ? "Simulation live" : "Simulation idle"}</Badge>
            <Badge>
              Tick {roundState?.tick ?? 0} / Hour {roundState?.simulated_hour ?? 0}
            </Badge>
            {authUser ? (
              <Button variant="outline" onClick={logout}>
                Logout
              </Button>
            ) : null}
          </div>
        </header>

        {message ? (
          <div className="rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 text-sm text-zinc-300">
            {message}
          </div>
        ) : null}

        <div className="grid gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>{authUser ? "Operator Session" : "Homeowner Access"}</CardTitle>
                <CardDescription>
                  Use PocketBase auth for account creation and then register a node on the grid.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {!authUser ? (
                  <>
                    <div className="flex gap-2">
                      <Button
                        variant={mode === "signup" ? "default" : "outline"}
                        className="flex-1"
                        onClick={() => setMode("signup")}
                        type="button"
                      >
                        Create account
                      </Button>
                      <Button
                        variant={mode === "login" ? "default" : "outline"}
                        className="flex-1"
                        onClick={() => setMode("login")}
                        type="button"
                      >
                        Login
                      </Button>
                    </div>
                    <form
                      className="space-y-4"
                      onSubmit={mode === "signup" ? handleSignup : handleLogin}
                    >
                      {mode === "signup" ? (
                        <div className="space-y-2">
                          <Label htmlFor="name">Name</Label>
                          <Input
                            id="name"
                            value={authForm.name}
                            onChange={(event) =>
                              setAuthForm((prev) => ({ ...prev, name: event.target.value }))
                            }
                            placeholder="Parth's rooftop home"
                          />
                        </div>
                      ) : null}
                      <div className="space-y-2">
                        <Label htmlFor="email">Email</Label>
                        <Input
                          id="email"
                          type="email"
                          value={authForm.email}
                          onChange={(event) =>
                            setAuthForm((prev) => ({ ...prev, email: event.target.value }))
                          }
                          placeholder="homeowner@voltnet.local"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="password">Password</Label>
                        <Input
                          id="password"
                          type="password"
                          value={authForm.password}
                          onChange={(event) =>
                            setAuthForm((prev) => ({ ...prev, password: event.target.value }))
                          }
                          placeholder="Enter password"
                        />
                      </div>
                      {mode === "signup" ? (
                        <div className="space-y-2">
                          <Label htmlFor="wallet">Initial wallet balance</Label>
                          <Input
                            id="wallet"
                            type="number"
                            min="0"
                            step="1"
                            value={authForm.initialWallet}
                            onChange={(event) =>
                              setAuthForm((prev) => ({
                                ...prev,
                                initialWallet: event.target.value,
                              }))
                            }
                          />
                        </div>
                      ) : null}
                      <Button className="w-full" disabled={loading} type="submit">
                        {loading
                          ? "Working..."
                          : mode === "signup"
                            ? "Create PocketBase user"
                            : "Login"}
                      </Button>
                    </form>
                  </>
                ) : (
                  <div className="space-y-4">
                    <div className="rounded-2xl border border-white/10 bg-black/60 p-4">
                      <p className="text-xs uppercase tracking-[0.28em] text-zinc-500">Signed in</p>
                      <p className="mt-2 text-lg font-medium">{authUser.email}</p>
                      <p className="mt-1 text-sm text-zinc-400">
                        Wallet {formatMoney(authUser.wallet_balance ?? portfolio?.wallet.balance ?? 0)}
                      </p>
                    </div>

                    <form className="space-y-4" onSubmit={handleCreateNode}>
                      <div className="space-y-2">
                        <Label htmlFor="home-name">Home / node name</Label>
                        <Input
                          id="home-name"
                          value={nodeForm.name}
                          onChange={(event) =>
                            setNodeForm((prev) => ({ ...prev, name: event.target.value }))
                          }
                          placeholder="Alpha Prosumer"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="solar">Solar setup</Label>
                        <Select
                          id="solar"
                          value={nodeForm.hasSolar}
                          onChange={(event) =>
                            setNodeForm((prev) => ({ ...prev, hasSolar: event.target.value }))
                          }
                        >
                          <option value="yes">Has solar</option>
                          <option value="no">Consumer only</option>
                        </Select>
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div className="space-y-2">
                          <Label htmlFor="battery-capacity">Battery cap</Label>
                          <Input
                            id="battery-capacity"
                            type="number"
                            value={nodeForm.batteryCapacity}
                            onChange={(event) =>
                              setNodeForm((prev) => ({
                                ...prev,
                                batteryCapacity: event.target.value,
                              }))
                            }
                          />
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="battery-initial">Initial charge</Label>
                          <Input
                            id="battery-initial"
                            type="number"
                            value={nodeForm.initialBattery}
                            onChange={(event) =>
                              setNodeForm((prev) => ({
                                ...prev,
                                initialBattery: event.target.value,
                              }))
                            }
                          />
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div className="space-y-2">
                          <Label htmlFor="max-solar">Max solar kW</Label>
                          <Input
                            id="max-solar"
                            type="number"
                            value={nodeForm.maxSolar}
                            onChange={(event) =>
                              setNodeForm((prev) => ({ ...prev, maxSolar: event.target.value }))
                            }
                          />
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="base-load">Base load kW</Label>
                          <Input
                            id="base-load"
                            type="number"
                            value={nodeForm.baseLoad}
                            onChange={(event) =>
                              setNodeForm((prev) => ({ ...prev, baseLoad: event.target.value }))
                            }
                          />
                        </div>
                      </div>
                      <Button className="w-full" disabled={loading} type="submit">
                        Create node on grid
                      </Button>
                    </form>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Simulation control</CardTitle>
                <CardDescription>
                  Kick off the backend loop and watch grid telemetry and trades stream in live.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex gap-2">
                  <Button className="flex-1" disabled={loading} onClick={() => void handleSimulation("start")} type="button">
                    Run simulation
                  </Button>
                  <Button
                    className="flex-1"
                    disabled={loading}
                    onClick={() => void handleSimulation("stop")}
                    variant="outline"
                    type="button"
                  >
                    Pause
                  </Button>
                </div>
                <div className="grid grid-cols-2 gap-3 text-sm text-zinc-400">
                  <div className="rounded-2xl border border-white/10 p-3">
                    <div>Orders collected</div>
                    <div className="mt-2 text-2xl font-semibold text-white">
                      {roundState?.orders_collected ?? 0}
                    </div>
                  </div>
                  <div className="rounded-2xl border border-white/10 p-3">
                    <div>Telemetry events</div>
                    <div className="mt-2 text-2xl font-semibold text-white">
                      {roundState?.telemetry_count ?? 0}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="space-y-6">
            <div className="grid gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,0.9fr)]">
              <Card className="overflow-hidden">
                <CardHeader className="border-b border-white/10">
                  <CardTitle>Microgrid map</CardTitle>
                  <CardDescription>
                    Every house on the local circuit, with live order intent and energy flow.
                  </CardDescription>
                </CardHeader>
                <CardContent className="p-0">
                  <GraphView
                    nodes={nodes}
                    selectedNodeId={selectedNodeId}
                    telemetryByNode={telemetryByNode}
                    orderSideByNode={orderSideByNode}
                  />
                </CardContent>
              </Card>

              <div className="grid gap-6">
                <Card>
                  <CardHeader>
                    <CardTitle>Your home view</CardTitle>
                    <CardDescription>
                      Select one of your registered nodes to inspect production, demand, battery, and wallet changes.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <Select
                      value={selectedNodeId}
                      onChange={(event) => setSelectedNodeId(event.target.value)}
                    >
                      <option value="">Select your node</option>
                      {ownedNodes.map((node) => (
                        <option key={node.id} value={node.id}>
                          {node.name}
                        </option>
                      ))}
                    </Select>

                    <div className="grid grid-cols-2 gap-3">
                      <MetricCard
                        label="Production"
                        value={formatEnergy(selectedTelemetry?.generation_kwh ?? 0)}
                      />
                      <MetricCard
                        label="Consumption"
                        value={formatEnergy(selectedTelemetry?.consumption_kwh ?? 0)}
                      />
                      <MetricCard
                        label="Battery"
                        value={formatEnergy(portfolio?.battery.current_kwh ?? 0)}
                        subValue={`of ${formatEnergy(portfolio?.battery.capacity_kwh ?? 0)}`}
                      />
                      <MetricCard
                        label="Wallet"
                        value={formatMoney(portfolio?.wallet.balance ?? 0)}
                        subValue={`reserved ${formatMoney(portfolio?.wallet.reserved ?? 0)}`}
                      />
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Revenue pulse</CardTitle>
                    <CardDescription>
                      Your cumulative market result and the latest trade involving your node.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <MetricCard
                      label="Net market P&L"
                      value={formatMoney(myNetMoney)}
                    />
                    <MetricCard
                      label="Current sale / trade"
                      value={
                        latestMyTrade
                          ? formatMoney(latestMyTrade.total_cost)
                          : "No trade yet"
                      }
                      subValue={
                        latestMyTrade
                          ? `${formatEnergy(latestMyTrade.quantity_kwh)} at ${formatMoney(latestMyTrade.unit_price)}`
                          : "Waiting for a match"
                      }
                    />
                  </CardContent>
                </Card>
              </div>
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle>Order and trade feed</CardTitle>
                  <CardDescription>
                    Live broadcast of orders, telemetry snapshots, and settled trades.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {feed.length === 0 ? (
                      <p className="text-sm text-zinc-500">
                        Start the simulation to populate the live feed.
                      </p>
                    ) : (
                      feed.map((entry) => (
                        <div
                          key={entry.id}
                          className="rounded-2xl border border-white/10 bg-black/50 p-4"
                        >
                          <div className="flex items-center justify-between gap-4">
                            <p className="font-medium text-white">{entry.title}</p>
                            <span className="text-xs text-zinc-500">{entry.timestamp}</span>
                          </div>
                          <p className="mt-2 text-sm leading-6 text-zinc-400">
                            {entry.detail}
                          </p>
                        </div>
                      ))
                    )}
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Recent market settlements</CardTitle>
                  <CardDescription>
                    Buyer, seller, volume, and final value from the most recent fills.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {trades.length === 0 ? (
                      <p className="text-sm text-zinc-500">
                        No trades have cleared yet.
                      </p>
                    ) : (
                      trades.slice(0, 10).map((trade, index) => (
                        <div
                          key={`${trade.buyer_node_id}-${trade.seller_node_id}-${index}`}
                          className="grid grid-cols-[1fr_auto] gap-3 rounded-2xl border border-white/10 p-4"
                        >
                          <div>
                            <p className="font-medium text-white">
                              {trade.seller_node_id} to {trade.buyer_node_id}
                            </p>
                            <p className="mt-1 text-sm text-zinc-400">
                              {formatEnergy(trade.quantity_kwh)} at {formatMoney(trade.unit_price)}
                            </p>
                          </div>
                          <div className="text-right">
                            <p className="font-semibold text-white">
                              {formatMoney(trade.total_cost)}
                            </p>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function MetricCard({
  label,
  value,
  subValue,
}: {
  label: string;
  value: string;
  subValue?: string;
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-black/60 p-4">
      <p className="text-xs uppercase tracking-[0.24em] text-zinc-500">{label}</p>
      <p className="mt-3 text-xl font-semibold text-white">{value}</p>
      {subValue ? <p className="mt-1 text-sm text-zinc-400">{subValue}</p> : null}
    </div>
  );
}
