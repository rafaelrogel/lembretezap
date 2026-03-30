"use client";

import type { CSSProperties } from "react";
import { useMemo } from "react";
import { createPortal } from "react-dom";

const PARTICLE_COUNT = 16;

export type PhotoSparkleBurstProps = {
  clientX: number;
  clientY: number;
  burstId: number;
};

export function PhotoSparkleBurst({
  clientX,
  clientY,
  burstId,
}: PhotoSparkleBurstProps) {
  const particles = useMemo(() => {
    return Array.from({ length: PARTICLE_COUNT }, (_, i) => {
      const angle = (Math.PI * 2 * i) / PARTICLE_COUNT + Math.random() * 0.4;
      const dist = 16 + Math.random() * 40;
      return {
        tx: Math.cos(angle) * dist,
        ty: Math.sin(angle) * dist,
        delay: Math.random() * 0.07,
        size: 2.5 + Math.random() * 5.5,
      };
    });
  }, []);

  if (typeof document === "undefined") return null;

  return createPortal(
    <div
      className="pointer-events-none fixed inset-0 z-[9998]"
      aria-hidden
    >
      <div
        className="absolute"
        style={{
          left: clientX,
          top: clientY,
        }}
      >
        {particles.map((p, i) => (
          <span
            key={`${burstId}-${i}`}
            className="profile-photo-sparkle"
            style={
              {
                width: p.size,
                height: p.size,
                animationDelay: `${p.delay}s`,
                "--tx": `${p.tx}px`,
                "--ty": `${p.ty}px`,
              } as CSSProperties
            }
          />
        ))}
      </div>
    </div>,
    document.body,
  );
}
