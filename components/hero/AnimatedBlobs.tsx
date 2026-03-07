"use client";

import { useEffect, useRef } from "react";

const TAU = Math.PI * 2;

/** Set false later to reduce motion intensity. Keep true until motion is confirmed visible. */
const DEBUG = true;

const BLUR_PX = DEBUG ? 100 : 100;
const ORBIT_RADIUS_MIN = 80;
const ORBIT_RADIUS_MAX = 140;
const PERIOD_MIN = 12;
const PERIOD_MAX = 18;
const BREATH_SCALE_MIN = 1;
const BREATH_SCALE_MAX = 1.6;
const BREATH_PERIOD = 5;

/** Entrance: fade + scale in before rest of hero. Duration in seconds. */
const ENTRANCE_DURATION = 0.7;
const ENTRANCE_SCALE_START = 0.82;

const BLOBS: ReadonlyArray<{
  width: string;
  height: string;
  top?: string;
  left?: string;
  right?: string;
  bottom?: string;
  background: string;
  orbitRadius: number;
  period: number;
  phase: number;
  breathPhase: number;
  borderRadius?: number;
  blur?: number;
}> = [
  {
    width: "clamp(18rem, 50vw, 36rem)",
    height: "clamp(18rem, 50vw, 36rem)",
    top: "-15%",
    left: "-10%",
    background: "rgba(217, 243, 242, 0.5)",
    orbitRadius: 140,
    period: 4,
    phase: 0,
    breathPhase: 0,
  },
  {
    width: "clamp(14rem, 40vw, 28rem)",
    height: "clamp(14rem, 40vw, 28rem)",
    top: "8%",
    right: "-8%",
    left: undefined,
    background: "rgba(233, 246, 224, 0.55)",
    orbitRadius: 160,
    period: 3.5,
    phase: 2,
    breathPhase: 1.5,
  },
  {
    width: "clamp(14rem, 40vw, 28rem)",
    height: "clamp(14rem, 40vw, 28rem)",
    bottom: "-5%",
    left: "-8%",
    background: "rgba(168, 225, 229, 0.5)",
    orbitRadius: 150,
    period: 4.2,
    phase: 4,
    breathPhase: 0.8,
  },
  {
    width: "clamp(14rem, 40vw, 28rem)",
    height: "clamp(14rem, 40vw, 28rem)",
    bottom: "12%",
    right: "-5%",
    background: "rgba(224, 247, 224, 0.55)",
    orbitRadius: 155,
    period: 3.8,
    phase: 1.2,
    breathPhase: 2.2,
  },
  {
    width: "clamp(22rem, 60vw, 44rem)",
    height: "clamp(22rem, 60vw, 44rem)",
    top: "28%",
    left: "18%",
    background: "rgba(233, 246, 224, 0.45)",
    orbitRadius: 170,
    period: 3.6,
    phase: 3,
    breathPhase: 1,
  },
  {
    width: "clamp(14rem, 42vw, 28rem)",
    height: "clamp(14rem, 42vw, 28rem)",
    top: "calc(15% + 400px)",
    right: "-12%",
    left: undefined,
    background: "rgba(240, 245, 163, 0.82)",
    orbitRadius: 145,
    period: 4.5,
    phase: 1.5,
    breathPhase: 2,
    borderRadius: 334,
    blur: 150,
  },
];

export function AnimatedBlobs() {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const blobRefs = useRef<(HTMLDivElement | null)[]>([]);
  const startTimeRef = useRef(0);
  const rafIdRef = useRef<number>();
  const logIntervalRef = useRef(0);

  useEffect(() => {
    startTimeRef.current = performance.now() / 1000;

    const tick = () => {
      const time = performance.now() / 1000 - startTimeRef.current;

      const entranceProgress = Math.min(1, time / ENTRANCE_DURATION);
      const entranceScale = ENTRANCE_SCALE_START + (1 - ENTRANCE_SCALE_START) * entranceProgress;
      if (wrapperRef.current) {
        wrapperRef.current.style.opacity = String(entranceProgress);
        wrapperRef.current.style.transform = `scale(${entranceScale})`;
      }

      if (DEBUG) {
        if (logIntervalRef.current === 0) console.log("AnimatedBlobs RAF running");
        logIntervalRef.current += 1;
        if (logIntervalRef.current % 60 === 0) {
          console.log("AnimatedBlobs RAF running", { time: time.toFixed(1) });
        }
      }

      blobRefs.current.forEach((node, i) => {
        if (!node) return;
        const blob = BLOBS[i];
        const angle = (time / blob.period) * TAU + blob.phase;
        const x = Math.cos(angle) * blob.orbitRadius;
        const y = Math.sin(angle) * blob.orbitRadius;
        const breathAngle = (time / BREATH_PERIOD) * TAU + blob.breathPhase;
        const scale =
          BREATH_SCALE_MIN +
          (BREATH_SCALE_MAX - BREATH_SCALE_MIN) * (0.5 + 0.5 * Math.sin(breathAngle));

        node.style.transform = `translate3d(${x}px, ${y}px, 0) scale(${scale})`;
      });

      rafIdRef.current = requestAnimationFrame(tick);
    };

    rafIdRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafIdRef.current) cancelAnimationFrame(rafIdRef.current);
    };
  }, []);

  return (
    <div
      ref={wrapperRef}
      className="pointer-events-none"
      style={{
        position: "absolute",
        inset: 0,
        overflow: "visible",
        zIndex: 0,
        opacity: 0,
        transform: `scale(${ENTRANCE_SCALE_START})`,
        transformOrigin: "center center",
      }}
      aria-hidden
    >
      {BLOBS.map((blob, i) => (
        <div
          key={i}
          ref={(el) => {
            blobRefs.current[i] = el;
          }}
          style={{
            position: "absolute",
            width: blob.width,
            height: blob.height,
            top: blob.top,
            left: blob.left,
            right: blob.right,
            bottom: blob.bottom,
            borderRadius: blob.borderRadius ?? 9999,
            filter: `blur(${blob.blur ?? BLUR_PX}px)`,
            background: blob.background,
            willChange: "transform",
          }}
        />
      ))}
    </div>
  );
}
