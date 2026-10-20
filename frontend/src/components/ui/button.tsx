"use client";

import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { cn } from "@/lib/utils";

export type ButtonVariant =
  "default" | "destructive" | "outline" | "secondary" | "ghost" | "link";
export type ButtonSize = "sm" | "md" | "lg" | "icon";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  asChild?: boolean;
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
}

const variants = {
  default: "bg-indigo-600 text-white hover:bg-indigo-700",
  destructive: "bg-rose-600 text-white hover:bg-rose-700",
  outline: "border border-zinc-300 bg-transparent hover:bg-zinc-100  ",
  secondary: "bg-zinc-100 text-zinc-900 hover:bg-zinc-200  ",
  ghost: "hover:bg-zinc-100 hover:text-zinc-900  ",
  link: "text-indigo-600 underline-offset-4 hover:underline",
};

const sizes = {
  sm: "h-8 px-3 text-sm",
  md: "h-10 px-4 py-2",
  lg: "h-12 px-5 text-base",
  icon: "h-9 w-9",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = "default",
      size = "md",
      asChild = false,
      leftIcon,
      rightIcon,
      children,
      ...props
    },
    ref,
  ) => {
    const inner = (
      <>
        {leftIcon && <span className="mr-2">{leftIcon}</span>}
        {children}
        {rightIcon && <span className="ml-2">{rightIcon}</span>}
      </>
    );

    const cls = cn(
      "inline-flex items-center justify-center rounded-md font-medium transition-colors",
      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2",
      "disabled:pointer-events-none disabled:opacity-50",
      variants[variant],
      sizes[size],
      className,
    );

    if (asChild) {
      const child = children as ReactNode;
      return <div className={cls}>{child}</div>;
    }

    return (
      <button ref={ref} className={cls} {...props}>
        {inner}
      </button>
    );
  },
);
Button.displayName = "Button";
