import type { CSSProperties } from "react";

// A field of citation "nodes" with edges that slowly draw and dissolve: the
// product semantic (cases citing cases) reduced to a calm decorative texture.
// Ported from jobmatch-ch's sign-in backdrop, recoloured to our teal accent and
// re-expressed in pure CSS/SVG (no motion dependency). Coordinates live in a
// 1200x720 viewBox; the field is mask-faded so the auth card stays the subject.
type Node = { x: number; y: number; r?: number };
type Edge = { a: number; b: number; delay: number; duration: number };

const NODES: Node[] = [
  { x: 120, y: 110, r: 2.4 },
  { x: 240, y: 220, r: 1.8 },
  { x: 360, y: 90, r: 2.2 },
  { x: 480, y: 250, r: 2 },
  { x: 580, y: 130, r: 1.6 },
  { x: 110, y: 360, r: 2 },
  { x: 280, y: 460, r: 2.4 },
  { x: 430, y: 540, r: 1.8 },
  { x: 600, y: 420, r: 2 },
  { x: 760, y: 320, r: 2.2 },
  { x: 880, y: 180, r: 1.8 },
  { x: 1020, y: 250, r: 2.4 },
  { x: 1110, y: 380, r: 1.8 },
  { x: 940, y: 480, r: 2 },
  { x: 810, y: 590, r: 2.2 },
  { x: 1070, y: 620, r: 1.6 },
  { x: 660, y: 660, r: 1.8 },
  { x: 200, y: 600, r: 2 },
];

const EDGES: Edge[] = [
  { a: 0, b: 1, delay: 0.0, duration: 6.5 },
  { a: 1, b: 2, delay: 1.4, duration: 7.0 },
  { a: 2, b: 4, delay: 2.6, duration: 5.8 },
  { a: 3, b: 4, delay: 0.8, duration: 6.2 },
  { a: 1, b: 5, delay: 3.4, duration: 7.5 },
  { a: 5, b: 6, delay: 1.1, duration: 6.0 },
  { a: 6, b: 7, delay: 2.2, duration: 6.8 },
  { a: 7, b: 8, delay: 0.5, duration: 7.0 },
  { a: 8, b: 9, delay: 3.0, duration: 6.5 },
  { a: 9, b: 10, delay: 1.8, duration: 7.2 },
  { a: 10, b: 11, delay: 0.3, duration: 6.4 },
  { a: 11, b: 12, delay: 2.8, duration: 6.8 },
  { a: 12, b: 13, delay: 1.6, duration: 6.0 },
  { a: 13, b: 14, delay: 3.6, duration: 7.4 },
  { a: 14, b: 15, delay: 0.9, duration: 6.6 },
  { a: 16, b: 14, delay: 2.4, duration: 7.0 },
  { a: 17, b: 6, delay: 4.0, duration: 6.8 },
  { a: 17, b: 7, delay: 1.2, duration: 7.5 },
  { a: 4, b: 9, delay: 4.2, duration: 6.2 },
  { a: 11, b: 13, delay: 2.0, duration: 6.5 },
];

// Mask: visible field that dies at the edges and dims under the centred card.
const FIELD_MASK =
  "radial-gradient(ellipse 90% 80% at 50% 50%, #000 25%, transparent 78%), radial-gradient(ellipse 36% 32% at 50% 50%, transparent 0%, #000 70%)";

export function SignInBackdrop() {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
      {/* Hairline grid base, mask-faded at the edges. */}
      <div className="bg-grid bg-grid-fade absolute inset-0 opacity-[0.55]" />

      {/* Two drifting teal glows in our brand gradient. */}
      <div
        className="animate-drift absolute"
        style={{
          left: "-12%",
          top: "-18%",
          width: "55%",
          height: "60%",
          filter: "blur(60px)",
          background:
            "radial-gradient(closest-side, oklch(0.74 0.12 195 / 0.40), transparent 70%)",
        }}
      />
      <div
        className="animate-drift absolute"
        style={{
          right: "-10%",
          bottom: "-20%",
          width: "55%",
          height: "60%",
          filter: "blur(80px)",
          animationDelay: "-6s",
          background:
            "radial-gradient(closest-side, oklch(0.47 0.105 200 / 0.32), transparent 70%)",
        }}
      />

      {/* The constellation. */}
      <svg
        viewBox="0 0 1200 720"
        preserveAspectRatio="xMidYMid slice"
        className="absolute inset-0 h-full w-full"
        style={{ WebkitMaskImage: FIELD_MASK, maskImage: FIELD_MASK }}
      >
        {EDGES.map((e, i) => {
          const a = NODES[e.a];
          const b = NODES[e.b];
          return (
            <line
              key={`e-${i}`}
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              pathLength={1}
              stroke="var(--accent)"
              strokeWidth={1}
              className="edge"
              style={{ "--dur": `${e.duration}s`, "--delay": `${e.delay}s` } as CSSProperties}
            />
          );
        })}
        {NODES.map((n, i) => (
          <circle
            key={`n-${i}`}
            cx={n.x}
            cy={n.y}
            r={n.r ?? 2}
            fill="var(--accent)"
            className="node"
            style={{ "--delay": `${(i % 6) * 0.6}s` } as CSSProperties}
          />
        ))}
      </svg>

      {/* Faint paper grain. */}
      <div className="bg-grain absolute inset-0" />
    </div>
  );
}
