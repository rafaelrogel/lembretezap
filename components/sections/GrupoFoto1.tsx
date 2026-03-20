"use client";

/**
 * Grupo 1: foto + reação 🎨 (toque para mostrar/ocultar).
 */
import { motion, useReducedMotion } from "framer-motion";
import Image from "next/image";
import { useCallback, useState } from "react";

const PHOTO_1 =
  "/foto%20de%20homem%20de%20costas%20fazendo%20colagem%201.png";

function PhotoReactionBubble({
  emoji,
  reduceMotion,
}: {
  emoji: string;
  reduceMotion: boolean;
}) {
  return (
    <motion.div
      className="pointer-events-none absolute bottom-[calc(0.75rem-40px)] right-3 z-20 flex h-11 w-11 transform-gpu items-center justify-center rounded-full bg-white shadow-[0_4px_14px_rgba(0,0,0,0.14),0_1px_3px_rgba(0,0,0,0.08)] ring-1 ring-[rgba(0,0,0,0.06)] will-change-transform [backface-visibility:hidden]"
      initial={{ scale: 0, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={
        reduceMotion
          ? { duration: 0.18, ease: "easeOut" }
          : {
              opacity: { duration: 0.28, ease: [0.16, 1, 0.3, 1] },
              scale: {
                type: "spring",
                stiffness: 420,
                damping: 32,
                mass: 0.72,
                restDelta: 0.0005,
              },
            }
      }
      style={{ transformOrigin: "50% 50%" }}
    >
      <span
        className="relative inline-block -translate-y-[2px] select-none text-[22px] leading-none"
        aria-hidden
      >
        {emoji}
      </span>
    </motion.div>
  );
}

export function GrupoFoto1() {
  const reduceMotion = useReducedMotion();
  const [showReaction, setShowReaction] = useState(false);

  const handleActivate = useCallback(() => {
    setShowReaction((v) => !v);
  }, []);

  const hidden = reduceMotion
    ? { opacity: 0 }
    : {
        opacity: 0,
        scale: 0.82,
        rotate: -11,
        y: 36,
      };
  const visible = reduceMotion
    ? { opacity: 1 }
    : {
        opacity: 1,
        scale: 1,
        rotate: 0,
        y: 0,
      };

  return (
    <motion.div
      role="group"
      aria-label="Grupo de foto 1 — toque para mostrar ou ocultar reação com paleta"
      className="relative z-0 mb-10 mt-8 cursor-pointer overflow-visible rounded-[26px] border-[10px] border-solid border-[#FFFEFC] bg-[#FFFEFC] shadow-[0_5px_14px_-6px_rgba(33,33,33,0.1),0_2px_6px_-4px_rgba(33,33,33,0.06)] transition-shadow duration-300 ease-out select-none hover:shadow-[0_12px_32px_-8px_rgba(33,33,33,0.18),0_4px_12px_-4px_rgba(33,33,33,0.08)] focus-visible:shadow-[0_12px_32px_-8px_rgba(33,33,33,0.18),0_4px_12px_-4px_rgba(33,33,33,0.08)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600/45 focus-visible:ring-offset-2"
      tabIndex={0}
      onClick={handleActivate}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          handleActivate();
        }
      }}
      initial={hidden}
      animate={visible}
      transition={
        reduceMotion
          ? { duration: 0.35, ease: "easeOut" }
          : {
              delay: 0.32,
              opacity: {
                duration: 1.05,
                ease: [0.16, 1, 0.3, 1],
              },
              y: {
                type: "spring",
                stiffness: 118,
                damping: 38,
                mass: 1.4,
              },
              scale: {
                type: "spring",
                stiffness: 118,
                damping: 38,
                mass: 1.4,
              },
              rotate: {
                type: "spring",
                stiffness: 118,
                damping: 38,
                mass: 1.4,
              },
            }
      }
      style={reduceMotion ? undefined : { transformOrigin: "50% 100%" }}
    >
      <div className="relative aspect-square w-full rounded-[16px] bg-[#FFFEFC]">
        <div className="relative h-full w-full overflow-hidden rounded-[16px]">
          <Image
            src={PHOTO_1}
            alt="Homem de costas fazendo colagem"
            fill
            className="pointer-events-none object-cover object-center"
            sizes="(min-width: 768px) 480px, 100vw"
            draggable={false}
          />
        </div>
        {showReaction && (
          <PhotoReactionBubble emoji="🎨" reduceMotion={!!reduceMotion} />
        )}
      </div>
    </motion.div>
  );
}
