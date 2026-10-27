"use client";
import { useEffect, useId, useRef, type ReactNode } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
type DialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title?: string;
  description?: string;
  children?: ReactNode;
  footer?: ReactNode;
  className?: string;
};
export function Dialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  footer,
  className,
}: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null);
  const id = useId();
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      aria-labelledby={title ? `${id}-title` : undefined}
      aria-describedby={description ? `${id}-description` : undefined}
      onCancel={(e) => {
        e.preventDefault();
        onOpenChange(false);
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          const box = e.currentTarget.getBoundingClientRect();
          if (
            e.clientX < box.left ||
            e.clientX > box.right ||
            e.clientY < box.top ||
            e.clientY > box.bottom
          )
            onOpenChange(false);
        }
      }}
      className={cn(
        "fixed inset-0 m-auto max-h-[90dvh] w-[calc(100%-2rem)] max-w-lg overflow-y-auto rounded-2xl border border-slate-200 bg-white p-6 text-slate-900 shadow-2xl backdrop:bg-slate-950/60 backdrop:backdrop-blur-xs dark:border-slate-800 dark:bg-[#121820] dark:text-slate-100",
        className,
      )}
    >
      <button
        onClick={() => onOpenChange(false)}
        className="absolute right-3 top-3 rounded p-1 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition"
        aria-label="Close"
      >
        <X size={18} />
      </button>
      {title && (
        <h2 id={`${id}-title`} className="pr-6 text-lg font-semibold">
          {title}
        </h2>
      )}
      {description && (
        <p
          id={`${id}-description`}
          className="mt-2 text-xs leading-6 text-slate-500"
        >
          {description}
        </p>
      )}
      {open && <div className="mt-5">{children}</div>}
      {footer && <div className="mt-6 flex justify-end gap-2">{footer}</div>}
    </dialog>
  );
}
