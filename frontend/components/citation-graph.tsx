"use client";

// The treatment network for a focal authority: focal case in the centre, every
// citer around it, edges coloured by how they TREAT the case (red = negative,
// green = approving, grey = neutral citation). Built on React Flow. Clicking an
// edge or citer surfaces the grounding receipt (the passage + source link) via
// `onSelect`. Layout is a deterministic radial one (no physics) so the demo is
// stable: citers are ordered by polarity then date, so colours cluster into arcs.

import { useCallback, useMemo } from "react";
import {
  Background,
  Controls,
  Handle,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { GraphEdge, GraphResult } from "../lib/api";

const POLARITY = {
  negative: { stroke: "#ef4444", ring: "ring-red-500/60", dot: "bg-red-500" },
  positive: { stroke: "#22c55e", ring: "ring-green-500/50", dot: "bg-green-500" },
  neutral: { stroke: "#94a3b8", ring: "ring-slate-400/30", dot: "bg-slate-400" },
} as const;

const SIGNAL_GLOW: Record<string, string> = {
  red: "ring-red-500 shadow-[0_0_40px_-6px] shadow-red-500/60",
  amber: "ring-amber-400 shadow-[0_0_40px_-6px] shadow-amber-400/60",
  green: "ring-green-500 shadow-[0_0_40px_-6px] shadow-green-500/50",
  unknown: "ring-slate-400",
};

const year = (d: string | null) => (d ? d.slice(0, 4) : "");
const isApex = (court: string | null) => court === "scotus";

type CaseNodeData = {
  label: string;
  sub: string;
  polarity: keyof typeof POLARITY;
  apex: boolean;
  focal: boolean;
  signal: string;
  treatment: string | null;
};

function CaseNode({ data }: NodeProps) {
  const d = data as unknown as CaseNodeData;
  if (d.focal) {
    return (
      <div
        className={`w-52 rounded-2xl border border-white/15 bg-slate-900/90 px-4 py-3 text-center ring-2 ${
          SIGNAL_GLOW[d.signal] ?? SIGNAL_GLOW.unknown
        }`}
      >
        <Handle type="target" position={Position.Top} className="!opacity-0" />
        <p className="text-[10px] uppercase tracking-widest text-white/40">Focal authority</p>
        <p className="mt-1 text-sm font-semibold leading-snug text-white">{d.label}</p>
        <p className="mt-0.5 text-[11px] text-white/50">{d.sub}</p>
      </div>
    );
  }
  const p = POLARITY[d.polarity];
  return (
    <div
      className={`group w-40 rounded-xl border border-white/10 bg-slate-800/80 px-3 py-2 ring-1 ${p.ring} transition-transform hover:scale-105`}
    >
      <Handle type="source" position={Position.Bottom} className="!opacity-0" />
      <div className="flex items-center gap-1.5">
        <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${p.dot}`} />
        {d.apex && (
          <span className="rounded bg-white/10 px-1 text-[8px] font-semibold uppercase tracking-wide text-white/60">
            SCOTUS
          </span>
        )}
        {d.treatment && (
          <span className="ml-auto truncate text-[9px] uppercase tracking-wide text-white/40">
            {d.treatment}
          </span>
        )}
      </div>
      <p className="mt-1 line-clamp-2 text-[11px] font-medium leading-tight text-white/90">
        {d.label}
      </p>
      <p className="text-[10px] text-white/40">{d.sub}</p>
    </div>
  );
}

const nodeTypes = { caseNode: CaseNode };

const POLARITY_ORDER = { negative: 0, neutral: 1, positive: 2 } as const;

export function CitationGraph({
  graph,
  onSelect,
  hideNeutral,
}: {
  graph: GraphResult;
  onSelect: (edge: GraphEdge) => void;
  hideNeutral: boolean;
}) {
  const { nodes, edges } = useMemo(() => {
    const meta = new Map(graph.nodes.map((n) => [n.case_id, n]));
    let citers = graph.edges.slice();
    // Drop neutral citations so only edges that actually treat the case (negative
    // or positive) remain — cuts through the grey when most cites are neutral.
    if (hideNeutral) citers = citers.filter((e) => e.polarity !== "neutral");
    // Order by polarity then date so same-colour edges cluster into arcs.
    citers.sort(
      (a, b) =>
        POLARITY_ORDER[a.polarity] - POLARITY_ORDER[b.polarity] ||
        (meta.get(a.citing_id)?.date_filed ?? "").localeCompare(
          meta.get(b.citing_id)?.date_filed ?? "",
        ),
    );

    const cx = 0;
    const cy = 0;
    const n = Math.max(citers.length, 1);
    const flowNodes: Node[] = [
      {
        id: String(graph.focal.case_id),
        type: "caseNode",
        position: { x: cx - 104, y: cy - 36 },
        data: {
          label: graph.focal.case_name ?? `Case ${graph.focal.case_id}`,
          sub: [graph.focal.citation, year(graph.focal.date_filed)].filter(Boolean).join(" · "),
          focal: true,
          signal: graph.signal,
          polarity: "neutral",
          apex: isApex(graph.focal.court),
        },
        draggable: false,
        selectable: false,
      },
    ];
    const flowEdges: Edge[] = [];

    citers.forEach((e, i) => {
      const m = meta.get(e.citing_id);
      // Two rings to de-stagger when crowded; full-circle sweep.
      const ring = i % 2 === 0 ? 360 : 540;
      const ang = (i / n) * 2 * Math.PI - Math.PI / 2;
      const x = cx + Math.cos(ang) * ring;
      const y = cy + Math.sin(ang) * ring * 0.62;
      flowNodes.push({
        id: String(e.citing_id),
        type: "caseNode",
        position: { x: x - 80, y: y - 24 },
        data: {
          label: m?.case_name ?? `Case ${e.citing_id}`,
          sub: [year(m?.date_filed ?? null), m?.court].filter(Boolean).join(" · "),
          polarity: e.polarity,
          apex: isApex(m?.court ?? null),
          focal: false,
          signal: graph.signal,
          treatment: e.treatment,
        },
      });
      const p = POLARITY[e.polarity];
      flowEdges.push({
        id: `${e.citing_id}-${e.cited_id}`,
        source: String(e.citing_id),
        target: String(graph.focal.case_id),
        animated: e.polarity === "negative",
        style: {
          stroke: p.stroke,
          strokeWidth: e.polarity === "negative" ? 2.4 : e.polarity === "positive" ? 1.6 : 1,
          opacity: e.polarity === "neutral" ? 0.35 : 0.9,
        },
        data: { edge: e },
      });
    });
    return { nodes: flowNodes, edges: flowEdges };
  }, [graph, hideNeutral]);

  const onEdgeClick = useCallback(
    (_: unknown, edge: Edge) => {
      const e = (edge.data as { edge?: GraphEdge })?.edge;
      if (e) onSelect(e);
    },
    [onSelect],
  );
  const onNodeClick = useCallback(
    (_: unknown, node: Node) => {
      const e = graph.edges.find((x) => String(x.citing_id) === node.id);
      if (e) onSelect(e);
    },
    [graph, onSelect],
  );

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      onEdgeClick={onEdgeClick}
      onNodeClick={onNodeClick}
      fitView
      fitViewOptions={{ padding: 0.2 }}
      proOptions={{ hideAttribution: true }}
      minZoom={0.2}
      className="bg-transparent"
    >
      <Background color="#334155" gap={28} size={1} />
      <Controls showInteractive={false} className="!bg-slate-800 !border-white/10" />
    </ReactFlow>
  );
}
