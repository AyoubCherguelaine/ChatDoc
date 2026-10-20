"use client";

import { forwardRef, type TextareaHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export const Textarea = forwardRef<
  HTMLTextAreaElement,
  TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea
    className={cn(
      "flex w-full rounded-md border border-zinc-300 bg-transparent px-3 py-2",
      "text-sm text-zinc-900 placeholder:text-zinc-500",
      "focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent",
      "  ",
      "resize-y min-h-[60px]",
      className,
    )}
    ref={ref}
    {...props}
  />
));
Textarea.displayName = "Textarea";
