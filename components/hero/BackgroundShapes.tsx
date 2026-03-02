"use client";

import type { RefObject } from "react";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

/** Set true to show red overlay, RAF logs, bypass reduced-motion, and huge orbit. Set false for normal. */
const DIAG = false;
/** When true: throw once in RAF to verify this component is the one running. Set false after verifying. */
const THROW_DIAG_ERROR = false;
/** When true (or DIAG): large orbit, short duration. When false: premium subtle. */
const DEBUG = true;
/** Animate blob by moving radial-gradient center instead of transform (more reliably visible). */
const USE_GRADIENT_ORBIT = true;

// ---------------------------------------------------------------------------
// ORBIT & BREATH – premium “almost static” blob motion (Apple/Linear vibe)
// ---------------------------------------------------------------------------

/** Orbit radius X range (px). DEBUG = exaggerated so blobs visibly orbit within ~2s. */
const ORBIT_RADIUS_X_RANGE = DEBUG ? ([60, 100] as const) : ([6, 14] as const);
/** Orbit radius Y range (px). */
const ORBIT_RADIUS_Y_RANGE = DEBUG ? ([60, 100] as const) : ([4, 12] as const);
/** Orbit duration range (seconds per full circle). DEBUG = 5–8s so motion is obvious. */
const ORBIT_DURATION_RANGE = DEBUG ? ([5, 8] as const) : ([18, 34] as const);
/** Breathing scale range (1 = no change). DEBUG = stronger pulse. */
const BREATH_SCALE_RANGE = DEBUG ? ([1.0, 1.12] as const) : ([1.0, 1.03] as const);
/** Breathing cycle duration range (seconds). */
const BREATH_DURATION_RANGE = [20, 40] as const;

// ---------------------------------------------------------------------------
// INTERACTION (optional) – hover & parallax
// ---------------------------------------------------------------------------

/** Hover: orbit radius multiplier (1.2 = +20%). */
const HOVER_ORBIT_BOOST = 1.2;
/** Parallax max displacement (px) by layer – microscopic. */
const PARALLAX_MAX_PX = { back: 6, mid: 9, front: 12 } as const;
const SMOOTHING = 0.09;

const LAYER_OPACITY = { back: 0.25, mid: 0.35, front: 0.45 } as const;
const LAYER_SCALE = { back: 1, mid: 1.02, front: 1.04 } as const;

type Layer = keyof typeof PARALLAX_MAX_PX;

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
  /** Orbit config: radius (px), duration (s), phase (rad). */
  orbitRadiusX: number;
  orbitRadiusY: number;
  orbitDuration: number;
  orbitPhase: number;
  breathDuration: number;
  breathPhase: number;
}> = [
  {
    width: "clamp(20rem, 55vw, 40rem)",
    height: "clamp(20rem, 55vw, 40rem)",
    top: "-20%",
    left: "-15%",
    layer: "back",
    borderRadius: 618,
    background: "rgba(217, 243, 242, 0.45)",
    orbitRadiusX: 10,
    orbitRadiusY: 6,
    orbitDuration: 24,
    orbitPhase: 0,
    breathDuration: 28,
    breathPhase: 0,
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
    orbitRadiusX: 8,
    orbitRadiusY: 10,
    orbitDuration: 30,
    orbitPhase: 2.1,
    breathDuration: 22,
    breathPhase: 1.2,
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
    orbitRadiusX: 12,
    orbitRadiusY: 8,
    orbitDuration: 20,
    orbitPhase: 4.2,
    breathDuration: 36,
    breathPhase: 0.5,
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
    orbitRadiusX: 7,
    orbitRadiusY: 11,
    orbitDuration: 28,
    orbitPhase: 1.3,
    breathDuration: 24,
    breathPhase: 2.8,
  },
  {
    width: "clamp(24rem, 65vw, 48rem)",
    height: "clamp(24rem, 65vw, 48rem)",
    top: "30%",
    left: "20%",
    layer: "front",
    borderRadius: 805,
    background: "rgba(233, 246, 224, 0.4)",
    orbitRadiusX: 14,
    orbitRadiusY: 9,
    orbitDuration: 18,
    orbitPhase: 3,
    breathDuration: 32,
    breathPhase: 1.8,
  },
];

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

const TAU = Math.PI * 2;

export type PointerRef = RefObject<{ x: number; y: number; isHovering: boolean; clientX: number; clientY: number }>;

export function BackgroundShapes({ pointerRef }: { pointerRef: PointerRef }) {
  const nodeRefs = useRef<(HTMLDivElement | null)[]>([]);
  const startTimeRef = useRef(0);
  const currentPointer = useRef({ x: 0, y: 0 });
  const hoverAmount = useRef(0);
  const rafId = useRef<number>();
  const reducedMotionRef = useRef(false);
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (DIAG) console.log("[BackgroundShapes] mounted (this component instance)");
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    reducedMotionRef.current = mq.matches;
    const handler = () => {
      reducedMotionRef.current = mq.matches;
    };
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  useEffect(() => {
    startTimeRef.current = performance.now() / 1000;
    let frameCount = 0;

    const tick = () => {
      frameCount += 1;
      if (THROW_DIAG_ERROR && frameCount === 2) {
        throw new Error("BackgroundShapes DIAG: correct component (throw once to verify)");
      }
      if (DIAG && frameCount % 60 === 0) {
        const nodeCount = nodeRefs.current.filter(Boolean).length;
        console.log("[BackgroundShapes] RAF tick", { frameCount, nodes: nodeCount, time: (performance.now() / 1000 - startTimeRef.current).toFixed(1) });
      }

      const raw = pointerRef.current;
      const pt = raw
        ? { x: raw.x, y: raw.y, isHovering: raw.isHovering }
        : { x: 0, y: 0, isHovering: false };
      const time = performance.now() / 1000 - startTimeRef.current;
      const cp = currentPointer.current;
      const reducedMotion = DIAG ? false : reducedMotionRef.current;

      if (reducedMotion) {
        cp.x = 0;
        cp.y = 0;
        hoverAmount.current = 0;
      } else {
        cp.x = lerp(cp.x, pt.x, SMOOTHING);
        cp.y = lerp(cp.y, pt.y, SMOOTHING);
        hoverAmount.current = lerp(hoverAmount.current, pt.isHovering ? 1 : 0, 0.06);
      }

      const hoverBoost = 1 + (HOVER_ORBIT_BOOST - 1) * hoverAmount.current;

      nodeRefs.current.forEach((node, i) => {
        if (!node) return;
        const cfg = ELLIPSES[i];
        const layerScale = LAYER_SCALE[cfg.layer];
        const opacity = LAYER_OPACITY[cfg.layer];
        const maxPx = PARALLAX_MAX_PX[cfg.layer];

        let orbitX = 0;
        let orbitY = 0;
        let breathScale = 1;

        if (!reducedMotion) {
          const [rxLo, rxHi] = ORBIT_RADIUS_X_RANGE;
          const [ryLo, ryHi] = ORBIT_RADIUS_Y_RANGE;
          const [durLo, durHi] = ORBIT_DURATION_RANGE;
          const radiusXEff = rxLo + ((cfg.orbitRadiusX - 6) / 8) * (rxHi - rxLo);
          const radiusYEff = ryLo + ((cfg.orbitRadiusY - 4) / 8) * (ryHi - ryLo);
          const durationEff = durLo + ((cfg.orbitDuration - 18) / 16) * (durHi - durLo);
          const angle = (time / durationEff) * TAU + cfg.orbitPhase;
          const rX = radiusXEff * hoverBoost;
          const rY = radiusYEff * hoverBoost;
          orbitX = Math.cos(angle) * rX;
          orbitY = Math.sin(angle) * rY;
          const breathAngle = (time / cfg.breathDuration) * TAU + cfg.breathPhase;
          const [bMin, bMax] = BREATH_SCALE_RANGE;
          breathScale = bMin + (bMax - bMin) * (0.5 + 0.5 * Math.sin(breathAngle));
        }

        const parallaxX = reducedMotion ? 0 : cp.x * maxPx;
        const parallaxY = reducedMotion ? 0 : cp.y * maxPx;
        const finalX = orbitX + parallaxX;
        const finalY = orbitY + parallaxY;
        const scale = layerScale * breathScale;

        if (USE_GRADIENT_ORBIT) {
          const cx = Math.max(5, Math.min(95, 50 + (finalX / 100) * 28));
          const cy = Math.max(5, Math.min(95, 50 + (finalY / 100) * 28));
          node.style.background = `radial-gradient(circle at ${cx}% ${cy}%, ${cfg.background} 0%, transparent 65%)`;
          node.style.transform = `scale(${scale})`;
        } else {
          node.style.transform = `translate3d(${finalX}px, ${finalY}px, 0) scale(${scale})`;
        }
        node.style.opacity = String(opacity);
      });

      rafId.current = requestAnimationFrame(tick);
    };

    const startTick = () => {
      rafId.current = requestAnimationFrame(tick);
    };
    rafId.current = requestAnimationFrame(startTick);
    return () => {
      if (rafId.current) cancelAnimationFrame(rafId.current);
    };
  }, [pointerRef]);

  return (
    <>
      {DIAG && mounted && typeof document !== "undefined" &&
        createPortal(
          <div
            data-diagnostic="background-shapes-mounted"
            style={{
              position: "fixed",
              top: 8,
              right: 8,
              width: 48,
              height: 48,
              background: "red",
              opacity: 0.9,
              zIndex: 2147483647,
              pointerEvents: "none",
              borderRadius: 4,
            }}
            title="BackgroundShapes mounted"
          />,
          document.body
        )}
      <div className="absolute inset-0 z-0 pointer-events-none overflow-visible" aria-hidden>
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
          style={{
            position: "absolute",
            width: ellipse.width,
            height: ellipse.height,
            top: ellipse.top,
            left: ellipse.left,
            right: ellipse.right,
            bottom: ellipse.bottom,
          }}
        >
          <div
            ref={(el) => {
              nodeRefs.current[i] = el;
            }}
            style={{
              width: "100%",
              height: "100%",
              borderRadius: `${ellipse.borderRadius}px`,
              filter: "blur(40px)",
              background: USE_GRADIENT_ORBIT
                ? `radial-gradient(circle at 50% 50%, ${ellipse.background} 0%, transparent 65%)`
                : ellipse.background,
              willChange: USE_GRADIENT_ORBIT ? "background" : "transform",
            }}
          />
        </div>
      ))}
      </div>
    </>
  );
}
