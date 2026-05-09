"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { HelpCircle, X } from "lucide-react";

interface HelpTipProps {
  text: string;
}

interface TipPosition {
  left: number;
  top: number;
}

const TIP_WIDTH = 288;
const VIEWPORT_GAP = 16;

export default function HelpTip({ text }: HelpTipProps) {
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [position, setPosition] = useState<TipPosition>({ left: VIEWPORT_GAP, top: VIEWPORT_GAP });
  const buttonRef = useRef<HTMLButtonElement | null>(null);
  const tipRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!open) return;

    const updatePosition = () => {
      const rect = buttonRef.current?.getBoundingClientRect();
      if (!rect) return;

      const viewportWidth = window.innerWidth;
      const width = Math.min(TIP_WIDTH, viewportWidth - VIEWPORT_GAP * 2);
      let left = rect.left;
      if (viewportWidth < 640) {
        left = (viewportWidth - width) / 2;
      } else if (left + width > viewportWidth - VIEWPORT_GAP) {
        left = viewportWidth - width - VIEWPORT_GAP;
      }
      left = Math.max(VIEWPORT_GAP, left);

      setPosition({
        left,
        top: rect.bottom + 8,
      });
    };

    const closeOnOutside = (event: MouseEvent) => {
      const target = event.target as Node;
      if (buttonRef.current?.contains(target) || tipRef.current?.contains(target)) {
        return;
      }
      setOpen(false);
    };

    updatePosition();
    window.addEventListener("resize", updatePosition);
    window.addEventListener("scroll", updatePosition, true);
    document.addEventListener("mousedown", closeOnOutside);

    return () => {
      window.removeEventListener("resize", updatePosition);
      window.removeEventListener("scroll", updatePosition, true);
      document.removeEventListener("mousedown", closeOnOutside);
    };
  }, [open]);

  return (
    <span className="inline-flex shrink-0">
      <button
        ref={buttonRef}
        type="button"
        onClick={(event) => {
          event.stopPropagation();
          setOpen((current) => !current);
        }}
        className="inline-flex h-7 w-7 items-center justify-center rounded-full border border-df-border bg-df-surface-solid/40 text-df-text-secondary transition-colors hover:border-df-accent hover:text-df-accent sm:h-5 sm:w-5"
        aria-label="Show help"
        aria-expanded={open}
      >
        <HelpCircle size={13} />
      </button>
      {mounted && open
        ? createPortal(
            <div
              ref={tipRef}
              className="fixed z-[1000] max-w-[calc(100vw-2rem)] rounded-2xl border border-df-border bg-df-surface-solid p-3 text-left text-xs font-normal leading-relaxed text-df-text shadow-xl"
              style={{ left: position.left, top: position.top, width: Math.min(TIP_WIDTH, 320) }}
              role="dialog"
            >
              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  setOpen(false);
                }}
                className="absolute right-2 top-2 rounded-full p-1 text-df-text-secondary hover:text-df-text"
                aria-label="Close help"
              >
                <X size={12} />
              </button>
              <span className="block pr-5">{text}</span>
            </div>,
            document.body
          )
        : null}
    </span>
  );
}
