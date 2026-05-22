"use client";

type GridNode = {
  id: string;
  name: string;
  has_solar: boolean;
  status: string;
  owner_user_id?: string | null;
};

type Telemetry = {
  generation_kwh: number;
  consumption_kwh: number;
  battery_after_kwh: number;
};

type GraphViewProps = {
  nodes: GridNode[];
  selectedNodeId?: string | null;
  telemetryByNode: Record<string, Telemetry>;
  orderSideByNode: Record<string, "buy" | "sell" | undefined>;
};

export function GraphView({
  nodes,
  selectedNodeId,
  telemetryByNode,
  orderSideByNode,
}: GraphViewProps) {
  const centerX = 300;
  const centerY = 220;
  const radius = 150;
  const count = Math.max(nodes.length, 1);

  const positions = nodes.map((node, index) => {
    const angle = (Math.PI * 2 * index) / count - Math.PI / 2;
    return {
      ...node,
      x: centerX + radius * Math.cos(angle),
      y: centerY + radius * Math.sin(angle),
    };
  });

  return (
    <div className="relative overflow-hidden rounded-[28px] border border-white/10 bg-[radial-gradient(circle_at_top,rgba(255,255,255,0.08),transparent_40%),linear-gradient(180deg,rgba(255,255,255,0.02),rgba(255,255,255,0.01))] p-4">
      <svg viewBox="0 0 600 440" className="h-[440px] w-full">
        <defs>
          <radialGradient id="nodeGlow" cx="50%" cy="50%" r="65%">
            <stop offset="0%" stopColor="rgba(255,255,255,0.5)" />
            <stop offset="100%" stopColor="rgba(255,255,255,0)" />
          </radialGradient>
        </defs>

        {positions.flatMap((source, sourceIndex) =>
          positions.slice(sourceIndex + 1).map((target) => (
            <line
              key={`${source.id}-${target.id}`}
              x1={source.x}
              y1={source.y}
              x2={target.x}
              y2={target.y}
              stroke="rgba(255,255,255,0.1)"
              strokeWidth="1"
            />
          )),
        )}

        <circle
          cx={centerX}
          cy={centerY}
          r="74"
          fill="rgba(255,255,255,0.03)"
          stroke="rgba(255,255,255,0.08)"
          strokeDasharray="6 8"
        />
        <text
          x={centerX}
          y={centerY - 4}
          fill="rgba(255,255,255,0.9)"
          textAnchor="middle"
          fontSize="18"
          fontWeight="600"
        >
          VoltNet
        </text>
        <text
          x={centerX}
          y={centerY + 20}
          fill="rgba(255,255,255,0.45)"
          textAnchor="middle"
          fontSize="11"
          letterSpacing="2"
        >
          MICROGRID
        </text>

        {positions.map((node) => {
          const telemetry = telemetryByNode[node.id];
          const side = orderSideByNode[node.id];
          const isSelected = node.id === selectedNodeId;

          return (
            <g key={node.id}>
              <circle cx={node.x} cy={node.y} r="38" fill="url(#nodeGlow)" />
              <circle
                cx={node.x}
                cy={node.y}
                r="30"
                fill={isSelected ? "white" : "rgba(0,0,0,0.92)"}
                stroke={
                  side === "sell"
                    ? "rgba(255,255,255,0.9)"
                    : side === "buy"
                      ? "rgba(255,255,255,0.45)"
                      : "rgba(255,255,255,0.2)"
                }
                strokeWidth={isSelected ? "2.5" : "1.5"}
              />
              <text
                x={node.x}
                y={node.y + 4}
                fill={isSelected ? "black" : "white"}
                textAnchor="middle"
                fontSize="10"
                fontWeight="700"
              >
                {node.name.slice(0, 8).toUpperCase()}
              </text>
              <text
                x={node.x}
                y={node.y + 48}
                fill="rgba(255,255,255,0.78)"
                textAnchor="middle"
                fontSize="11"
              >
                {telemetry
                  ? `${telemetry.generation_kwh.toFixed(1)}G / ${telemetry.consumption_kwh.toFixed(1)}C`
                  : node.has_solar
                    ? "solar node"
                    : "consumer"}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
