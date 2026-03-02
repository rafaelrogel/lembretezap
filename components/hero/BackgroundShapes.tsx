"use client";

import type { RefObject } from "react";
import { useEffect, useRef } from "react";

const DEBUG = false;
/** Set true to exaggerate motion (parallax, hover spread, drift) and confirm animation is visible. */
const DEBUG_MOTION = false;

// ---------------------------------------------------------------------------
// PRESET VALUES (tuned for premium Apple/Linear feel)
// ---------------------------------------------------------------------------

const PARALLAX_STRENGTH_DEBUG = { back: 10, mid: 25, front: 45 } as const;
const PARALLAX_STRENGTH_FINAL = { back: 4, mid: 10, front: 18 } as const;
const PARALLAX_STRENGTH = DEBUG_MOTION ? PARALLAX_STRENGTH_DEBUG : PARALLAX_STRENGTH_FINAL;

const SMOOTHING_DEBUG = 0.15;
const SMOOTHING_FINAL = 0.09;
const SMOOTHING = DEBUG_MOTION ? SMOOTHING_DEBUG : SMOOTHING_FINAL;

const DRIFT_AMPLITUDE_DEBUG = 32;
const DRIFT_AMPLITUDE_FINAL = 22;
const DRIFT_AMPLITUDE = DEBUG_MOTION ? DRIFT_AMPLITUDE_DEBUG : DRIFT_AMPLITUDE_FINAL;
/** Loop duration (seconds) per ellipse – one full orbit. Shorter = more visible motion. */
const LOOP_DURATION = [20, 24, 18, 26, 22] as const;

const HOVER_SPREAD_DEBUG = 60;
const HOVER_SPREAD_FINAL = 52;
const HOVER_SPREAD = DEBUG_MOTION ? HOVER_SPREAD_DEBUG : HOVER_SPREAD_FINAL;
/** Snappier hover reaction so ellipses visibly move when entering hero center */
const HOVER_SPREAD_SMOOTHING = 0.065;
/** When hovering over one ellipse, others move away by this amount (px) */
const ELLIPSE_HOVER_SPREAD = 28;
/** Hovered ellipse moves slightly toward cursor (px per unit normalized) */
const ELLIPSE_HOVER_PULL = 12;
/** Smoothing for per-ellipse hover spread (afastar) */
const ELLIPSE_HOVER_SMOOTHING = 0.08;
const LAYER_OPACITY = { back: 0.25, mid: 0.35, front: 0.45 } as const;
const LAYER_SCALE = { back: 1, mid: 1.02, front: 1.04 } as const;

type Layer = keyof typeof PARALLAX_STRENGTH;

/* Blurred ellipses over gradient base – left blue-green, center yellow-green, right light green */
const ELLIPSES: ReadonlyArray<{
  width: string;
  height: string;
  top: string;
  left?: string;
  right?: string;
  bottom?: string;
  layer: Layer;
  borderRadius: number;
  background: string;
  outward: [number, number];
  driftPhase: number;
  driftDuration: number;
}> = [
  {
    width: "clamp(20rem, 55vw, 40rem)",
    height: "clamp(20rem, 55vw, 40rem)",
    top: "-20%",
    left: "-15%",
    layer: "back",
    borderRadius: 618,
    background: "rgba(217, 243, 242, 0.45)",
    outward: [-0.7, -0.7],
    driftPhase: 0,
    driftDuration: 18,
  },
  {
    width: "clamp(14rem, 42vw, 28rem)",
    height: "clamp(14rem, 42vw, 28rem)",
    top: "5%",
    right: "-10%",
    left: "auto",
    layer: "mid",
    borderRadius: 334,
    background: "rgba(233, 246, 224, 0.5)",
    outward: [0.8, -0.6],
    driftPhase: 2.1,
    driftDuration: 20,
  },
  {
    width: "clamp(14rem, 42vw, 28rem)",
    height: "clamp(14rem, 42vw, 28rem)",
    bottom: "-5%",
    left: "-10%",
    top: "auto",
    layer: "mid",
    borderRadius: 334,
    background: "rgba(168, 225, 229, 0.45)",
    outward: [-0.6, 0.8],
    driftPhase: 4.2,
    driftDuration: 17,
  },
  {
    width: "clamp(14rem, 42vw, 28rem)",
    height: "clamp(14rem, 42vw, 28rem)",
    bottom: "10%",
    right: "-5%",
    top: "auto",
    left: "auto",
    layer: "mid",
    borderRadius: 334,
    background: "rgba(224, 247, 224, 0.5)",
    outward: [0.7, 0.7],
    driftPhase: 1.3,
    driftDuration: 21,
  },
  {
    width: "clamp(24rem, 65vw, 48rem)",
    height: "clamp(24rem, 65vw, 48rem)",
    top: "30%",
    left: "20%",
    layer: "front",
    borderRadius: 805,
    background: "rgba(233, 246, 224, 0.4)",
    outward: [0.3, -0.3],
    driftPhase: 3,
    driftDuration: 19,
  },
];

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

export type PointerRef = RefObject<{ x: number; y: number; isHovering: boolean; clientX: number; clientY: number }>;

/** Index of ellipse whose center is closest to (cx, cy), or -1 if hero not hovered. */
function closestEllipse(nodeRefs: (HTMLDivElement | null)[], cx: number, cy: number): number {
  let best = -1;
  let bestD2 = Infinity;
  for (let i = 0; i < nodeRefs.length; i++) {
    const node = nodeRefs[i];
    if (!node) continue;
    const rect = node.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;
    const d2 = (cx - centerX) ** 2 + (cy - centerY) ** 2;
    if (d2 < bestD2) {
      bestD2 = d2;
      best = i;
    }
  }
  return best;
}

export function BackgroundShapes({ pointerRef }: { pointerRef: PointerRef }) {
  const nodeRefs = useRef<(HTMLDivElement | null)[]>([]);
  const currentPointer = useRef({ x: 0, y: 0 });
  const hoverCurrent = useRef(0);
  /** Which ellipse is under the cursor (-1 = none). Smoothed so "afastar" animates nicely. */
  const hoveredIndexTarget = useRef(-1);
  const hoveredIndexSmooth = useRef(0);
  const rafId = useRef<number>();
  const reducedMotionRef = useRef(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    reducedMotionRef.current = mq.matches;
    const handler = () => {
      reducedMotionRef.current = mq.matches;
    };
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  useEffect(() => {
    const start = performance.now() / 1000;

    const tick = () => {
      const raw = pointerRef.current;
      const pt = raw
        ? { x: raw.x, y: raw.y, isHovering: raw.isHovering, clientX: raw.clientX ?? 0, clientY: raw.clientY ?? 0 }
        : { x: 0, y: 0, isHovering: false, clientX: 0, clientY: 0 };
      const t = performance.now() / 1000 - start;
      const cp = currentPointer.current;
      const reducedMotion = reducedMotionRef.current;

      if (reducedMotion) {
        cp.x = pt.x;
        cp.y = pt.y;
      } else {
        cp.x = lerp(cp.x, pt.x, SMOOTHING);
        cp.y = lerp(cp.y, pt.y, SMOOTHING);
      }

      const hoverTgt = pt.isHovering ? 1 : 0;
      hoverCurrent.current = lerp(hoverCurrent.current, hoverTgt, HOVER_SPREAD_SMOOTHING);
      /* Strongest movement when cursor is near hero center; falls off toward edges */
      const distFromCenter = Math.sqrt(pt.x * pt.x + pt.y * pt.y);
      const centerStrength = 1 - 0.5 * Math.min(1, distFromCenter);
      const spread = hoverCurrent.current * HOVER_SPREAD * (pt.isHovering ? centerStrength : 0);

      /* Per-ellipse hover: which ellipse is closest to cursor? Others "afastar" (move away) */
      const hoveredIndex = pt.isHovering ? closestEllipse(nodeRefs.current, pt.clientX, pt.clientY) : -1;
      hoveredIndexTarget.current = hoveredIndex;
      const targetStrength = hoveredIndex >= 0 ? 1 : 0;
      hoveredIndexSmooth.current = reducedMotion ? targetStrength : lerp(hoveredIndexSmooth.current, targetStrength, ELLIPSE_HOVER_SMOOTHING);
      const ellipseSpreadAmount = hoveredIndexSmooth.current;

      if (DEBUG && t < 1) {
        console.log("[BackgroundShapes] RAF running", { pt, reducedMotion, hoveredIndex });
      }

      nodeRefs.current.forEach((node, i) => {
        if (!node) return;
        const cfg = ELLIPSES[i];
        const strength = PARALLAX_STRENGTH[cfg.layer];
        const scale = LAYER_SCALE[cfg.layer];
        const opacity = LAYER_OPACITY[cfg.layer];
        const px = cp.x * strength;
        const py = cp.y * strength;
        const sx = spread * cfg.outward[0];
        const sy = spread * cfg.outward[1];
        /* When one ellipse is hovered: it shifts slightly toward cursor; others move away (afastar) */
        const isHoveredOne = hoveredIndex >= 0 && i === hoveredIndex;
        const afastarX = ellipseSpreadAmount * (isHoveredOne ? ELLIPSE_HOVER_PULL * pt.x : ELLIPSE_HOVER_SPREAD * cfg.outward[0]);
        const afastarY = ellipseSpreadAmount * (isHoveredOne ? ELLIPSE_HOVER_PULL * pt.y : ELLIPSE_HOVER_SPREAD * cfg.outward[1]);
        const x = px + sx + afastarX;
        const y = py + sy + afastarY;
        node.style.transform = `translate3d(${x}px, ${y}px, 0) scale(${scale})`;
        node.style.opacity = String(opacity);
      });

      rafId.current = requestAnimationFrame(tick);
    };

    rafId.current = requestAnimationFrame(tick);
    return () => {
      if (rafId.current) cancelAnimationFrame(rafId.current);
    };
  }, [pointerRef]);

  return (
    <div className="absolute inset-0 -z-10 pointer-events-none overflow-hidden" aria-hidden>
      {/* Base: soft gradient left (blue-green) → center (yellow-green) → right (light green) */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: "linear-gradient(to right, rgb(217, 243, 242), rgb(233, 246, 224), rgb(224, 247, 224))",
          borderRadius: "2.5rem",
        }}
      />
      {ELLIPSES.map((ellipse, i) => (
        <div
          key={i}
          ref={(el) => {
            nodeRefs.current[i] = el;
          }}
          style={{
            position: "absolute",
            width: ellipse.width,
            height: ellipse.height,
            top: ellipse.top,
            left: ellipse.left,
            right: ellipse.right,
            bottom: ellipse.bottom,
            willChange: "transform",
          }}
        >
          <div
            className={`ellipse-loop ${i % 2 === 1 ? "reverse" : ""}`}
            style={{
              animationDuration: `${LOOP_DURATION[i]}s`,
              animationDelay: `${-ellipse.driftPhase}s`,
            }}
          >
            <div
              style={{
                width: "100%",
                height: "100%",
                borderRadius: `${ellipse.borderRadius}px`,
                filter: "blur(150px)",
                background: ellipse.background,
              }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
