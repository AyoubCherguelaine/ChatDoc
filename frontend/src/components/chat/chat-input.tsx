"use client";
import { useState } from "react";
import { ArrowUp, Square } from "lucide-react";

export function ChatInput({
  onSubmit,
  disabled,
  onStop,
  initialText = "",
}: {
  onSubmit: (text: string) => void;
  disabled?: boolean;
  onStop?: () => void;
  initialText?: string;
}) {
  const [value, setValue] = useState(initialText);
  const submit = () => {
    if (disabled || !value.trim()) return;
    onSubmit(value.trim());
    setValue("");
  };

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3 shadow-2xs transition-colors dark:border-slate-800 dark:bg-[#121820]">
      <textarea
        aria-label="Message"
        placeholder="Ask a question about your document…"
        value={value}
        maxLength={20000}
        disabled={disabled}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault();
            submit();
          }
        }}
        rows={2}
        className="max-h-40 min-h-14 w-full resize-y bg-transparent p-1 text-sm leading-6 text-slate-900 placeholder:text-slate-400 outline-none disabled:opacity-60 dark:text-slate-100 dark:placeholder:text-slate-500"
      />
      <div className="mt-1 flex items-center justify-between">
        <span className="text-[10px] text-slate-400 dark:text-slate-500">
          Shift + Enter for a new line
        </span>
        {disabled ? (
          <button
            onClick={onStop}
            aria-label="Stop response"
            title="Stop"
            className="flex h-8 items-center gap-1.5 rounded-lg bg-rose-600 px-3 text-xs font-semibold text-white hover:bg-rose-700 transition"
          >
            <Square size={12} /> Stop
          </button>
        ) : (
          <button
            onClick={submit}
            disabled={!value.trim()}
            aria-label="Send"
            title="Send"
            className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-tr from-teal-700 to-emerald-600 text-white hover:from-teal-800 hover:to-emerald-700 transition disabled:opacity-30 shadow-2xs"
          >
            <ArrowUp size={16} />
          </button>
        )}
      </div>
    </div>
  );
}
