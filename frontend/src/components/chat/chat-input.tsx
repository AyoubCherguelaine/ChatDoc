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
    <div className="rounded-xl border border-[#dce5e3] bg-white p-3 shadow-[0_3px_12px_#142e3805]">
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
        className="max-h-40 min-h-14 w-full resize-y bg-transparent p-1 text-sm leading-6 outline-none disabled:opacity-60"
      />
      <div className="mt-1 flex items-center justify-between">
        <span className="text-[10px] text-slate-400">
          Shift + Enter for a new line
        </span>
        {disabled ? (
          <button
            onClick={onStop}
            aria-label="Stop response"
            title="Stop"
            className="flex h-8 items-center gap-2 rounded-lg bg-[#183a38] px-3 text-xs text-white"
          >
            <Square size={12} /> Stop
          </button>
        ) : (
          <button
            onClick={submit}
            disabled={!value.trim()}
            aria-label="Send"
            title="Send"
            className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#087f74] text-white hover:bg-teal-800 disabled:opacity-40"
          >
            <ArrowUp size={17} />
          </button>
        )}
      </div>
    </div>
  );
}
