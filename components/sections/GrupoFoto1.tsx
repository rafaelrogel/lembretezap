"use client";

/**
 * 1→🎨→2→❤️→3→🎭→4→✨→1 (ciclo).
 */
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import Image from "next/image";
import { useCallback, useEffect, useRef, useState } from "react";
import clsx from "clsx";

const PHOTO_1 =
  "/foto%20de%20homem%20de%20costas%20fazendo%20colagem%201.png";
const PHOTO_2 =
  "/foto%20de%20mulher%20com%20amigos%201.png";
const PHOTO_3 = "/grupo%20de%20carnaval%201.png";
const PHOTO_4 = "/calas%201.png";

const FADE_MS = { in: 0.32, out: 0.28 };

function PhotoReactionBubble({
  emoji,
  reduceMotion,
}: {
  emoji: string;
  reduceMotion: boolean;
}) {
  return (
    <motion.div
      className="pointer-events-none absolute bottom-[calc(0.75rem-28px)] right-4 z-20 flex h-11 w-11 transform-gpu items-center justify-center rounded-full bg-white shadow-[0_4px_14px_rgba(0,0,0,0.14),0_1px_3px_rgba(0,0,0,0.08)] ring-1 ring-[rgba(0,0,0,0.06)] will-change-transform [backface-visibility:hidden]"
      initial={{ scale: 0, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      exit={{ scale: 0, opacity: 0 }}
      transition={
        reduceMotion
          ? { duration: 0.22, ease: "easeOut" }
          : {
              opacity: { duration: 0.34, ease: [0.16, 1, 0.3, 1] },
              scale: {
                type: "spring",
                stiffness: 320,
                damping: 24,
                mass: 0.85,
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

export function GrupoFoto1({ className }: { className?: string }) {
  const reduceMotion = useReducedMotion();
  const [photo, setPhoto] = useState<1 | 2 | 3 | 4>(1);
  const [showReaction, setShowReaction] = useState(false);
  const swapTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (swapTimeoutRef.current) {
        clearTimeout(swapTimeoutRef.current);
      }
    };
  }, []);

  const schedulePhotoChange = useCallback((nextPhoto: 1 | 2 | 3 | 4) => {
    if (swapTimeoutRef.current) {
      clearTimeout(swapTimeoutRef.current);
    }
    setShowReaction(false);
    // Segura um pouco para ver a reação saindo.
    swapTimeoutRef.current = setTimeout(() => {
      setPhoto(nextPhoto);
      swapTimeoutRef.current = null;
    }, 240);
  }, []);

  const handleActivate = useCallback(() => {
    if (photo === 1) {
      if (!showReaction) {
        setShowReaction(true);
        return;
      }
      schedulePhotoChange(2);
      return;
    }

    if (photo === 2) {
      if (!showReaction) {
        setShowReaction(true);
        return;
      }
      schedulePhotoChange(3);
      return;
    }

    if (photo === 3) {
      if (!showReaction) {
        setShowReaction(true);
        return;
      }
      schedulePhotoChange(4);
      return;
    }

    if (photo === 4) {
      if (!showReaction) {
        setShowReaction(true);
        return;
      }
      schedulePhotoChange(1);
      return;
    }
  }, [photo, schedulePhotoChange, showReaction]);

  const hidden = reduceMotion
    ? { opacity: 0 }
    : {
        opacity: 0,
        scale: 0.9,
        rotate: -8,
        y: 30,
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
      aria-label={
        photo === 1
          ? "Grupo de foto — toque para reação; com a reação visível, toque para ver a foto com amigos"
          : photo === 2
            ? "Foto com amigos — toque para reação; com o coração visível, toque para ver o grupo de carnaval"
            : photo === 3
              ? "Grupo de carnaval — toque para reação; com a máscara visível, toque para ver a foto seguinte"
              : "Calas — toque para reação; com a reação visível, toque para voltar à primeira foto"
      }
      className={clsx("mb-10 mt-8 w-full overflow-visible", className)}
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
              delay: 0.14,
              duration: 0.72,
              ease: [0.22, 1, 0.36, 1],
            }
      }
      style={reduceMotion ? undefined : { transformOrigin: "50% 100%" }}
    >
      <div className="relative z-0 w-full origin-left scale-[0.96] cursor-pointer overflow-visible rounded-[26px] shadow-[0_5px_14px_-6px_rgba(33,33,33,0.1),0_2px_6px_-4px_rgba(33,33,33,0.06)] transition-[transform,box-shadow] duration-300 ease-out select-none hover:scale-100 hover:shadow-[0_12px_32px_-8px_rgba(33,33,33,0.18),0_4px_12px_-4px_rgba(33,33,33,0.08)] focus-visible:scale-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600/45 focus-visible:ring-offset-2 focus-visible:shadow-[0_12px_32px_-8px_rgba(33,33,33,0.18),0_4px_12px_-4px_rgba(33,33,33,0.08)] motion-reduce:scale-100">
        <div className="overflow-visible rounded-[26px] border-[10px] border-solid border-[#FFFEFC] bg-[#FFFEFC]">
          <div className="relative aspect-square w-full overflow-hidden rounded-[16px]">
            <Image
              src={
                photo === 1
                  ? PHOTO_1
                  : photo === 2
                    ? PHOTO_2
                    : photo === 3
                      ? PHOTO_3
                      : PHOTO_4
              }
              alt={
                photo === 1
                  ? "Homem de costas fazendo colagem"
                  : photo === 2
                    ? "Mulher com amigos"
                    : photo === 3
                      ? "Grupo em clima de carnaval"
                      : "Calas"
              }
              fill
              className="pointer-events-none object-cover object-center"
              sizes="(min-width: 768px) 480px, 100vw"
              draggable={false}
            />
          </div>
        </div>
        <AnimatePresence>
          {showReaction && (
            <PhotoReactionBubble
              emoji={
                photo === 1
                  ? "🎨"
                  : photo === 2
                    ? "❤️"
                    : photo === 3
                      ? "🎭"
                      : "✨"
              }
              reduceMotion={!!reduceMotion}
            />
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}
