"use client";

import clsx from "clsx";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";

/** Largura <= 1079px = mobile (compact); >= 1080 = desktop. Igual a `mobile`/`desktop` no tailwind. */
const HERO_CHAT_MOBILE_MAX_PX = 1079;

function useHeroChatCompact() {
  const query = `(max-width: ${HERO_CHAT_MOBILE_MAX_PX}px)`;
  return useSyncExternalStore(
    (onStoreChange) => {
      if (typeof window === "undefined") return () => {};
      const mq = window.matchMedia(query);
      mq.addEventListener("change", onStoreChange);
      return () => mq.removeEventListener("change", onStoreChange);
    },
    () => window.matchMedia(query).matches,
    () => false,
  );
}

function GreenCheckIcon({ className }: { className?: string }) {
  return (
    <img
      src="/check-verde.png"
      alt=""
      width={16}
      height={16}
      className={className}
      aria-hidden
    />
  );
}

function MessageReadCheckIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={14}
      height={8}
      viewBox="0 0 14 8"
      fill="none"
      className={className}
      aria-hidden
    >
      <path
        d="M13.5 0.595703L8.10059 8L5.91211 5.83887L6.83887 4.56641L8.10059 5.30273L13.002 0.109375L13.5 0.595703Z"
        fill="#3497F9"
      />
      <path
        d="M9.11816 0.487305L3.71875 7.8916L0 4.2334L0.830078 3.42383L3.71875 5.19336L8.61914 0L9.11816 0.487305Z"
        fill="#3497F9"
      />
    </svg>
  );
}

function SpeechBlobSvg({
  fill,
  filterId,
  className,
}: {
  fill: string;
  filterId: string;
  className?: string;
}) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 258 66"
      fill="none"
      className={className}
      preserveAspectRatio="none"
      style={{ overflow: "hidden" }}
    >
      <defs>
        <clipPath id={`${filterId}_clip`}>
          <path
            d="M12.3555 0H245.931C250.349 0 253.931 3.58172 253.931 8V49.5301C253.931 53.9484 250.349 57.5301 245.931 57.5301H11.9995C7.55446 57.5301 3.96173 53.9065 3.99983 49.4615L4.35583 7.93142C4.39348 3.54007 7.96404 0 12.3555 0Z"
          />
        </clipPath>
      </defs>
      <g clipPath={`url(#${filterId}_clip)`}>
        <rect width={258} height={66} fill={fill} />
      </g>
      <g>
        <path
          d="M12.3555 0H245.931C250.349 0 253.931 3.58172 253.931 8V49.5301C253.931 53.9484 250.349 57.5301 245.931 57.5301H11.9995C7.55446 57.5301 3.96173 53.9065 3.99983 49.4615L4.35583 7.93142C4.39348 3.54007 7.96404 0 12.3555 0Z"
          fill={fill}
        />
      </g>
    </svg>
  );
}

const WAVEFORM_HEIGHTS = [
  8, 4, 10, 5, 12, 6, 9, 4, 11, 6, 8, 5, 10, 7, 9, 6, 11, 5, 9, 7, 10, 6, 8, 4, 12, 7, 9, 5, 10,
];

function AudioBubble({ compact }: { compact: boolean }) {
  return (
    <div
      className={clsx(
        "relative inline-flex max-w-full flex-col overflow-hidden rounded-[8px] bg-[#DCF7C5] shadow-[0_4px_4px_0_rgba(0,0,0,0.08)]",
        compact ? "gap-0.5 px-2 py-1" : "gap-1 px-3 py-[7px]",
      )}
    >
      <div className={clsx("flex items-center", compact ? "gap-1.5" : "gap-2")}>
        <span
          className={clsx(
            "flex shrink-0 items-center justify-center rounded-full bg-[#2d5016]/25",
            compact ? "h-7 w-7" : "h-8 w-8",
          )}
          aria-hidden
        >
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="currentColor"
            className={clsx("ml-0.5 text-[#212121]", compact ? "h-3 w-3" : "h-[14px] w-[14px]")}
          >
            <path d="M8 5v14l11-7z" />
          </svg>
        </span>
        <div
          className={clsx(
            "flex min-w-0 flex-1 items-center",
            compact ? "h-3.5 max-w-[148px] gap-px overflow-hidden" : "h-4 gap-0.5",
          )}
          aria-hidden
        >
          {WAVEFORM_HEIGHTS.map((h, i) => (
            <span
              key={i}
              className="hero-audio-bar w-0.5 shrink-0 origin-bottom self-end rounded-full"
              style={{ height: h, backgroundColor: "rgba(45,80,22,0.45)" }}
            />
          ))}
        </div>
      </div>
      <div className="flex w-full items-center justify-between">
        <div className={clsx("flex shrink-0 items-center", compact ? "w-7" : "w-8")}>
          <span
            className={clsx(
              compact ? "ml-0.5" : "ml-[5px]",
              compact ? "text-[10px]" : "text-[11px]",
              "text-[#9e9e9e]",
            )}
          >
            0:15
          </span>
        </div>
        <span
          className={clsx(
            "inline-flex items-center text-[#9e9e9e]",
            compact ? "gap-0.5 text-[10px]" : "gap-1 text-[11px]",
          )}
        >
          <span>09:15</span>
          <MessageReadCheckIcon className={clsx("w-auto", compact ? "h-1.5" : "h-2")} />
        </span>
      </div>
    </div>
  );
}

function AvatarHero({ playKey, compact }: { playKey: number; compact: boolean }) {
  return (
    <div className={`shrink-0 self-end ${playKey > 0 ? "chat-avatar-enter" : ""}`}>
      <img
        src="/avatar-profile-hero.png"
        alt=""
        width={36}
        height={36}
        className={clsx(
          "rounded-full border border-[#e0e0e0] object-cover",
          compact ? "h-7 w-7" : "h-9 w-9",
        )}
        aria-hidden
      />
    </div>
  );
}

export function HeroChatMockup() {
  const compact = useHeroChatCompact();
  const containerRef = useRef<HTMLDivElement>(null);
  const [playKey, setPlayKey] = useState(0);
  const wasVisibleRef = useRef(false);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      (entries) => {
        const isVisible = entries[0]?.isIntersecting ?? false;
        if (isVisible && !wasVisibleRef.current) {
          wasVisibleRef.current = true;
          setPlayKey((k) => k + 1);
        }
      },
      { threshold: 0.2, rootMargin: "0px" },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const hidden = playKey === 0;

  const bubbleText = clsx(
    "leading-snug text-[#212121]",
    compact ? "text-[12px]" : "text-[14px]",
  );
  const timeText = clsx(compact ? "text-[10px]" : "text-[11px]", "text-[#9e9e9e]");
  const rowInset = clsx(compact ? "ml-3" : "ml-[68px]");
  const greyWrap = clsx(
    "relative inline-block w-full overflow-hidden rounded-[8px] bg-[#FBF7F2] shadow-[0_4px_4px_0_rgba(0,0,0,0.08)]",
    compact ? "mr-3 max-w-[90%]" : "mr-[72px] max-w-[85%]",
  );

  return (
    <div
      ref={containerRef}
      className={clsx(
        "hero-chat-mock mx-auto min-w-0 w-full max-w-full",
        compact ? "px-1.5 py-2.5" : "px-2 py-4",
      )}
      aria-hidden
    >
      <div
        className={clsx("hero-bubble-1 flex justify-end", rowInset, playKey > 0 && "chat-bubble-grey-enter")}
        style={hidden ? { opacity: 0, pointerEvents: "none" } : undefined}
      >
        <div className={greyWrap}>
          <div className="absolute inset-0 scale-x-[-1]">
            <SpeechBlobSvg fill="#FBF7F2" filterId="filter_blob_grey_hero_1" className="h-full w-full" />
          </div>
          <div
            className={clsx(
              "relative z-10 text-left",
              compact ? "px-2 py-1.5" : "px-[10px] py-2",
            )}
            style={{ transform: "translateY(-1px)" }}
          >
            <p className={bubbleText}>
              <span className={clsx("inline-flex items-center", compact ? "gap-0.5" : "gap-1")}>
                Feito{" "}
                <GreenCheckIcon
                  className={clsx("inline-block shrink-0", compact ? "h-3.5 w-3.5" : "h-4 w-4")}
                />{" "}
                adicionei o evento:
              </span>
            </p>
            <p className={clsx(bubbleText, compact ? "mt-0.5" : "mt-[2px]")}>• 12:00 - levar Bob no pet shop</p>
            <p className={clsx(bubbleText, compact ? "mt-0.5" : "mt-[2px]")}>
              <span className={clsx("flex w-full items-center justify-between", compact ? "gap-1.5" : "gap-2")}>
                <span>na sua agenda de terça</span>
                <span className={clsx("shrink-0", timeText, compact ? "translate-y-[2px]" : "translate-y-0.5")}>
                  09:16
                </span>
              </span>
            </p>
          </div>
        </div>
      </div>

      <div
        className={clsx(
          "hero-bubble-2 flex items-end justify-end",
          compact ? "mt-1.5 gap-1" : "mt-2 gap-[6px]",
          playKey > 0 && "chat-sent-bubble-enter",
        )}
        style={hidden ? { opacity: 0, pointerEvents: "none" } : undefined}
      >
        <AudioBubble compact={compact} />
        <AvatarHero playKey={playKey} compact={compact} />
      </div>

      <div
        className={clsx(
          "hero-bubble-3 flex justify-end",
          rowInset,
          compact ? "mt-1.5" : "mt-2",
          playKey > 0 && "chat-bubble-grey-enter",
        )}
        style={hidden ? { opacity: 0, pointerEvents: "none" } : undefined}
      >
        <div className={greyWrap}>
          <div className="absolute inset-0 scale-x-[-1]">
            <SpeechBlobSvg fill="#FBF7F2" filterId="filter_blob_grey_hero_2" className="h-full w-full" />
          </div>
          <div
            className={clsx(
              "relative z-10 text-left",
              compact ? "px-2 py-1" : "px-[10px] py-[6px]",
            )}
            style={{ transform: "translateY(-1px)" }}
          >
            <p className={bubbleText}>Sexta você tem os seguintes compromissos:</p>
            <ul
              className={clsx(
                "list-none",
                bubbleText,
                compact ? "mt-1 space-y-px" : "mt-1.5 space-y-0.5",
              )}
            >
              <li>• 9:00 - reunião com o time</li>
              <li>• 14:00 - enviar proposta para cliente</li>
              <li>• 18:30 - academia</li>
            </ul>
            <p className={clsx(bubbleText, compact ? "mt-1.5" : "mt-2")}>
              <span
                className={clsx(
                  "flex w-full",
                  compact ? "flex-col items-stretch gap-0.5" : "flex-row items-center justify-between gap-2",
                )}
              >
                <span>Quer ver também os lembretes da semana?</span>
                <span
                  className={clsx(
                    "shrink-0 self-end",
                    timeText,
                    compact ? "translate-y-0" : "inline-block translate-y-px",
                  )}
                >
                  09:14
                </span>
              </span>
            </p>
          </div>
        </div>
      </div>

      <div
        className={clsx(
          "hero-bubble-4 flex items-end",
          rowInset,
          compact ? "mt-1.5 gap-1" : "mt-2 gap-[6px]",
          playKey > 0 && "chat-sent-bubble-enter",
        )}
        style={hidden ? { opacity: 0, pointerEvents: "none" } : undefined}
      >
        <div className="relative min-w-0 flex-1">
          <div className="relative w-full overflow-hidden rounded-[8px] bg-[#DCF7C5] shadow-[0_4px_4px_0_rgba(0,0,0,0.08)]">
            <SpeechBlobSvg fill="#DCF7C5" filterId="filter_blob_green_hero_1" className="absolute inset-0 h-full w-full" />
            <div
              className={clsx(
                "relative z-10 text-left",
                compact ? "px-2 py-1.5" : "px-[10px] py-[7px]",
              )}
              style={{ transform: "translateY(-1px)" }}
            >
              <p className={bubbleText}>
                quais eventos eu tenho na minha<br />
                <span className={clsx("flex w-full items-center justify-between", compact ? "gap-1.5" : "gap-2")}>
                  <span>agenda de sexta feira</span>
                  <span
                    className={clsx(
                      "inline-flex shrink-0 items-center",
                      timeText,
                      compact ? "translate-y-0 gap-1" : "translate-y-0.5 gap-1.5",
                    )}
                    aria-hidden
                  >
                    <span>09:14</span>
                    <MessageReadCheckIcon className={clsx("w-auto", compact ? "h-1.5" : "h-2")} />
                  </span>
                </span>
              </p>
            </div>
          </div>
        </div>
        <AvatarHero playKey={playKey} compact={compact} />
      </div>
    </div>
  );
}
