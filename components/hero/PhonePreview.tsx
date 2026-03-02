import type { ReactNode } from "react";

export interface PhonePreviewProps {
  /**
   * Optional content to render inside the phone screen (e.g. animated chat
   * messages). When using the image placeholder, children are not shown.
   */
  children?: ReactNode;
}

/**
 * Phone mockup: SVG (phone-preview.svg). Same max dimensions; SVG scales with object-contain.
 */
export function PhonePreview({ children }: PhonePreviewProps) {
  return (
    <div
      className="relative flex flex-shrink-0 items-center justify-end w-full max-w-[280px] sm:max-w-[320px] md:max-w-[min(380px,42vw)] md:mr-0 bg-transparent"
      style={{ background: "transparent" }}
      aria-hidden
    >
      <div className="relative w-full bg-transparent" style={{ background: "transparent" }}>
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
