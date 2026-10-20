"use client";

import { forwardRef, type LabelHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export const Label = forwardRef<
  HTMLLabelElement,
  LabelHTMLAttributes<HTMLLabelElement>
>(({ className, children, ...props }, ref) => (
  <label
    ref={ref}
    className={cn(
      "block text-sm font-medium leading-none text-zinc-900  mb-1",
      className,
    )}
    {...props}
  >
    {children}
  </label>
));
Label.displayName = "Label";
