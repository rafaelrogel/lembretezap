"use client";

import { useEffect, useRef, useState } from "react";

export interface WaveLettersTextProps {
  /** Text to animate. Use \n for line breaks. */
  text: string;
  className?: string;
  /**
   * When true (default), animation resets when leaving viewport
   * so it runs again each time the user scrolls back into view.
   */
  triggerOncePerEntry?: boolean;
  /** Duration of each letter (ms). Default 420. Use 294 for 30% faster. */
  letterDurationMs?: number;
  /** Stagger between letters (ms). Default 42. Use 29 for 30% faster. */
  staggerMs?: number;
}

/** Scale peak for the letter pop (subtle). */
const SCALE_PEAK = 1.15;
const DEFAULT_LETTER_DURATION_MS = 420;
const DEFAULT_STAGGER_MS = 42;

export function WaveLettersText({
  text,
  className = "",
  triggerOncePerEntry = true,
  letterDurationMs = DEFAULT_LETTER_DURATION_MS,
  staggerMs = DEFAULT_STAGGER_MS,
}: WaveLettersTextProps) {
  const containerRef = useRef<HTMLSpanElement>(null);
  const [isInView, setIsInView] = useState(false);
  const [reduceMotion, setReduceMotion] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduceMotion(mq.matches);
    const handler = () => setReduceMotion(mq.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || reduceMotion) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsInView(true);
        } else if (triggerOncePerEntry) {
          // Reset when leaving so animation can run again on re-entry
          setIsInView(false);
        }
      },
      { threshold: 0.2, rootMargin: "0px" }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [reduceMotion, triggerOncePerEntry]);

  const lines = text.split("\n").filter(Boolean);

  if (reduceMotion) {
    return (
      <span className={className}>
        {lines.map((line, i) => (
          <span key={i}>
            {i > 0 && <br />}
            {line}
          </span>
        ))}
      </span>
    );
  }

  let charIndex = 0;
  return (
    <span
      ref={containerRef}
      className={`wave-letters ${isInView ? "wave-letters-active" : ""} ${className}`}
      style={
        {
          "--wave-scale-peak": SCALE_PEAK,
          "--wave-duration": `${letterDurationMs}ms`,
          "--wave-stagger": `${staggerMs}ms`,
        } as React.CSSProperties
      }
    >
      {lines.map((line, lineIdx) => (
        <span key={lineIdx} className={`wave-letters-line ${lineIdx > 0 ? "wave-letters-line-follow" : ""}`}>
          {Array.from(line).map((char, i) => {
            const index = charIndex++;
            const isSpace = char === " ";
            return (
              <span
                key={`${lineIdx}-${i}`}
                className={`wave-letters-char ${isSpace ? "wave-letters-space" : ""}`}
                style={{
                  animationDelay: isSpace ? undefined : `calc(var(--wave-stagger) * ${index})`,
                }}
                aria-hidden={false}
              >
                {isSpace ? "\u00A0" : char}
              </span>
            );
          })}
        </span>
      ))}
    </span>
  );
}
