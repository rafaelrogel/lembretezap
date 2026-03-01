import type { ReactNode } from "react";

export interface PhonePreviewProps {
  /**
   * Optional content to render inside the phone screen (e.g. animated chat
   * messages built with Framer Motion). Renders in the scrollable area below
   * the notch. When omitted, the screen stays empty/static.
   */
  children?: ReactNode;
}

/**
 * Phone frame: solid black silhouette with centered notch. Screen area below
 * the notch is ready for animated chat content (e.g. Framer Motion).
 */
export function PhonePreview({ children }: PhonePreviewProps) {
  return (
    <div
      className="relative flex flex-shrink-0 items-center justify-end w-full max-w-[280px] sm:max-w-[320px] md:max-w-[min(380px,42vw)] md:mr-0 md:translate-x-[5%]"
      aria-hidden
    >
      <div className="relative flex aspect-[9/19.5] w-full flex-col overflow-hidden rounded-[2.5rem] bg-black shadow-xl">
        {/* Centered notch at top (cutout) */}
        <div
          className="absolute left-1/2 top-4 z-10 h-5 w-20 -translate-x-1/2 rounded-b-xl bg-black"
          aria-hidden
        />

        {/* Screen area below notch */}
        <div
          className="relative flex flex-1 flex-col overflow-hidden pt-[2.25rem]"
          style={{ minHeight: 0 }}
        >
          <div className="flex min-h-0 flex-1 flex-col overflow-y-auto bg-black">
            {children}
          </div>
        </div>
      </div>
    </div>
  );
}
