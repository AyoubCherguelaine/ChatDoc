"use client";

import { cn } from "@/lib/utils";

export function Spinner({
  className,
  size = 16,
}: {
  className?: string;
  size?: number;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 36 36"
      className={cn("animate-spin", className)}
    >
      <circle
        className="opacity-25"
        cx="18"
        cy="18"
        r="16"
        fill="none"
        strokeWidth="4"
        stroke="currentColor"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M17.64 2h.36a1 1 0 0 1 .99.86l.01.14v4.14a1 1 0 0 1-.99 1H17a1 1 0 0 1 0-2h.64V2z"
      />
    </svg>
  );
}
