"use client";

import { forwardRef, type InputHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export type InputProps = InputHTMLAttributes<HTMLInputElement>;

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, type = "text", ...props }, ref) => (
    <input
      type={type}
      className={cn(
        "flex h-10 w-full rounded-md border border-zinc-300 bg-transparent px-3 py-2",
        "text-sm text-zinc-900 placeholder:text-zinc-500",
        "focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent",
        "  ",
        className,
      )}
      ref={ref}
      {...props}
    />
  ),
);
Input.displayName = "Input";
