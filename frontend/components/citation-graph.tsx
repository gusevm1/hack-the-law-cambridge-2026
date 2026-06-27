"use client";

// Treatment network for a focal authority — readability-first (CiteMeRight style).
// Instead of one radial hairball of 200+ nodes, citers are laid out in COLUMNS by
// how they treat the case — Negative · Approving · Neutral — as clean cards, with
// the focal authority on the left and bezier edges coloured by treatment. The
// neutral column is capped (most cites are bare/neutral) so the signal isn't
// drowned; `hideNeutral` drops it entirely. Click any card → grounding receipt.
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

const NEUTRAL_CAP = 18; // most cites are neutral; cap the column so it stays readable

const POLARITY = {
  negative: { stroke: "#ef4444", ring: "ring-red-500/60", dot: "bg-red-500", col: "Negative" },
  positive: { stroke: "#22c55e", ring: "ring-green-500/50", dot: "bg-green-500", col: "Approving" },
  neutral: { stroke: "#94a3b8", ring: "ring-slate-400/25", dot: "bg-slate-400", col: "Neutral" },
} as const;
type Pol = keyof typeof POLARITY;

const SIGNAL_GLOW: Record<string, string> = {
  red: "ring-red-500 shadow-[0_0_40px_-6px] shadow-red-500/60",
  amber: "ring-amber-400 shadow-[0_0_40px_-6px] shadow-amber-400/60",
  green: "ring-green-500 shadow-[0_0_40px_-6px] shadow-green-500/50",
  unknown: "ring-slate-400",
};

const year = (d: string | null | undefined) => (d ? d.slice(0, 4) : "");
const isApex = (c: string | null | undefined) => c === "scotus";

type CaseNodeData = {
  label: string; sub: string; polarity: Pol; apex: boolean;
  focal: boolean; signal: string; treatment: string | null;
};

function CaseNode({ data }: NodeProps) {
  const d = data as unknown as CaseNodeData;
  if (d.focal) {
    return (
      <div className={`w-52 rounded-2xl border border-white/15 bg-slate-900/90 px-4 py-3 text-center ring-2 ${SIGNAL_GLOW[d.signal] ?? SIGNAL_GLOW.unknown}`}>
        <Handle type="source" position={Position.Right} className="!opacity-0" />
        <p className="text-[10px] uppercase tracking-widest text-white/40">Focal authority</p>
        <p className="mt-1 text-sm font-semibold leading-snug text-white">{d.label}</p>
        <p className="mt-0.5 text-[11px] text-white/50">{d.sub}</p>
      </div>
    );
  }
  const p = POLARITY[d.polarity];
  return (
    <div className={`group w-44 rounded-xl border border-white/10 bg-slate-800/80 px-3 py-2 ring-1 ${p.ring} transition-transform hover:scale-[1.04]`}>
      <Handle type="target" position={Position.Left} className="!opacity-0" />
      <div className="flex items-center gap-1.5">
        <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${p.dot}`} />
        {d.apex && <span className="rounded bg-white/10 px-1 text-[8px] font-semibold uppercase tracking-wide text-white/60">SCOTUS</span>}
        {d.treatment && <span className="ml-auto truncate text-[9px] uppercase tracking-wide text-white/45">{d.treatment}</span>}
      </div>
      <p className="mt-1 line-clamp-2 text-[11px] font-medium leading-tight text-white/90">{d.label}</p>
      <p className="text-[10px] text-white/40">{d.sub}</p>
    </div>
  );
}

const nodeTypes = { caseNode: CaseNode };

export function CitationGraph({
  graph, onSelect, hideNeutral,
}: {
  graph: GraphResult;
  onSelect: (edge: GraphEdge) => void;
  hideNeutral: boolean;
}) {
  const { nodes, edges } = useMemo(() => {
    const meta = new Map(graph.nodes.map((n) => [n.case_id, n]));
    const byPol: Record<Pol, GraphEdge[]> = { negative: [], positive: [], neutral: [] };
    for (const e of graph.edges) byPol[(e.polarity as Pol) ?? "neutral"].push(e);
    const recent = (e: GraphEdge) => meta.get(e.citing_id)?.date_filed ?? "";
    (Object.keys(byPol) as Pol[]).forEach((k) =>
      byPol[k].sort((a, b) => recent(b).localeCompare(recent(a))),
    );
    const fullNeutral = byPol.neutral.length;
    if (hideNeutral) byPol.neutral = [];
    else byPol.neutral = byPol.neutral.slice(0, NEUTRAL_CAP);
    const hiddenNeutral = Math.max(0, fullNeutral - byPol.neutral.length);

    // Columns left→right: Negative, Approving, Neutral. Focal sits far left, centred.
    const COL_X = { negative: 360, positive: 620, neutral: 880 } as const;
    const ROW_H = 84;
    const tallest = Math.max(byPol.negative.length, byPol.positive.length, byPol.neutral.length, 1);
    const midY = (tallest * ROW_H) / 2;

    const flowNodes: Node[] = [{
      id: String(graph.focal.case_id),
      type: "caseNode",
      position: { x: 0, y: midY - 36 },
      draggable: false, selectable: false,
      data: {
        label: graph.focal.case_name ?? `Case ${graph.focal.case_id}`,
        sub: [graph.focal.citation, year(graph.focal.date_filed)].filter(Boolean).join(" · "),
        focal: true, signal: graph.signal, polarity: "neutral", apex: isApex(graph.focal.court),
      },
    }];
    const flowEdges: Edge[] = [];

    (["negative", "positive", "neutral"] as Pol[]).forEach((pol) => {
      const list = byPol[pol];
      const colTop = midY - (list.length * ROW_H) / 2;
      list.forEach((e, i) => {
        const m = meta.get(e.citing_id);
        flowNodes.push({
          id: String(e.citing_id),
          type: "caseNode",
          position: { x: COL_X[pol], y: colTop + i * ROW_H },
          data: {
            label: m?.case_name ?? `Case ${e.citing_id}`,
            sub: [year(m?.date_filed), m?.court].filter(Boolean).join(" · "),
            polarity: pol, apex: isApex(m?.court), focal: false,
            signal: graph.signal, treatment: e.treatment,
          },
        });
        const p = POLARITY[pol];
        flowEdges.push({
          id: `${e.citing_id}-${e.cited_id}`,
          source: String(graph.focal.case_id),
          target: String(e.citing_id),
          animated: pol === "negative",
          style: {
            stroke: p.stroke,
            strokeWidth: pol === "negative" ? 2.2 : pol === "positive" ? 1.5 : 0.9,
            opacity: pol === "neutral" ? 0.3 : 0.85,
          },
          data: { edge: e },
        });
      });
    });

    if (hiddenNeutral > 0) {
      const colTop = midY - (byPol.neutral.length * ROW_H) / 2;
      flowNodes.push({
        id: "more-neutral",
        type: "caseNode",
        position: { x: COL_X.neutral, y: colTop + byPol.neutral.length * ROW_H },
        selectable: false, draggable: false,
        data: {
          label: `+${hiddenNeutral} more neutral cites`, sub: "see Analyze for all",
          polarity: "neutral", apex: false, focal: false, signal: graph.signal, treatment: null,
        },
      });
    }
    return { nodes: flowNodes, edges: flowEdges };
  }, [graph, hideNeutral]);

  const onEdgeClick = useCallback((_: unknown, edge: Edge) => {
    const e = (edge.data as { edge?: GraphEdge })?.edge;
    if (e) onSelect(e);
  }, [onSelect]);
  const onNodeClick = useCallback((_: unknown, node: Node) => {
    const e = graph.edges.find((x) => String(x.citing_id) === node.id);
    if (e) onSelect(e);
  }, [graph, onSelect]);

  return (
    <ReactFlow
      nodes={nodes} edges={edges} nodeTypes={nodeTypes}
      onEdgeClick={onEdgeClick} onNodeClick={onNodeClick}
      fitView fitViewOptions={{ padding: 0.15 }}
      proOptions={{ hideAttribution: true }} minZoom={0.2}
      className="bg-transparent"
    >
      <Background color="#334155" gap={28} size={1} />
      <Controls showInteractive={false} className="!bg-slate-800 !border-white/10" />
    </ReactFlow>
  );
}
