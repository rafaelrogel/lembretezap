"use client";

import type { RefObject } from "react";
import { useEffect, useRef } from "react";
import type { ReactNode } from "react";

export interface PhonePreviewProps {
  /**
   * Optional content to render inside the phone screen (e.g. animated chat
   * messages). When using the image placeholder, children are not shown.
   */
  children?: ReactNode;
  /** When provided and hero is hovered, phone gets a slight pan (parallax) toward the cursor. */
  pointerRef?: RefObject<{ x: number; y: number; isHovering: boolean }>;
}

const PAN_STRENGTH = 6;
const TILT_DEG = 3;
const PAN_SMOOTHING = 0.08;

function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}

/**
 * Phone mockup: SVG. On hero hover: pan + 3D tilt (angle distortion) toward cursor.
 */
export function PhonePreview({ children, pointerRef }: PhonePreviewProps) {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const motionRef = useRef({ x: 0, y: 0, rotateX: 0, rotateY: 0 });

  useEffect(() => {
    if (!pointerRef) return;
    let rafId: number;
    const tick = () => {
      const raw = pointerRef.current;
      const pt = raw ? { x: raw.x, y: raw.y, isHovering: raw.isHovering } : { x: 0, y: 0, isHovering: false };
      const on = pt.isHovering ? 1 : 0;
      const targetX = pt.x * PAN_STRENGTH * on;
      const targetY = pt.y * PAN_STRENGTH * on;
      const targetRotateY = pt.x * TILT_DEG * on;
      const targetRotateX = -pt.y * TILT_DEG * on;
      const m = motionRef.current;
      m.x = lerp(m.x, targetX, PAN_SMOOTHING);
      m.y = lerp(m.y, targetY, PAN_SMOOTHING);
      m.rotateX = lerp(m.rotateX, targetRotateX, PAN_SMOOTHING);
      m.rotateY = lerp(m.rotateY, targetRotateY, PAN_SMOOTHING);
      if (wrapperRef.current) {
        wrapperRef.current.style.transform =
          `translate(${m.x}px, ${m.y}px) rotateX(${m.rotateX}deg) rotateY(${m.rotateY}deg)`;
      }
      rafId = requestAnimationFrame(tick);
    };
    rafId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafId);
  }, [pointerRef]);

  return (
    <div
      className="relative flex flex-shrink-0 items-center justify-end w-full max-w-[280px] sm:max-w-[320px] md:max-w-[min(380px,42vw)] md:mr-0 bg-transparent"
      style={{ background: "transparent", perspective: 900 }}
      aria-hidden
    >
      <div
        ref={wrapperRef}
        className="relative w-full bg-transparent will-change-transform"
        style={{ background: "transparent", transformStyle: "preserve-3d" }}
      >
        <img
          src="/phone-preview.svg"
          alt=""
          width={280}
          height={606}
          className="phone-mockup-img h-auto w-full max-w-[280px] sm:max-w-[320px] md:max-w-[min(380px,42vw)] object-contain object-top"
          style={{
            aspectRatio: "9 / 19.5",
            background: "transparent",
          }}
        />
      </div>
    </div>
  );
}
