"use client";
import { useLanguage } from "@/components/providers/language-provider";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { type Message } from "@/lib/types";
import { Sparkles, Copy, Check } from "lucide-react";

export function MessageBubble({
  message,
  isStreaming = false,
}: {
  message: Message;
  isStreaming?: boolean;
}) {
  const { t } = useLanguage();
  const assistant = message.role === "assistant";
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {}
  };

  return (
    <article
      className={`flex gap-3 py-3 ${assistant ? "" : "justify-end"}`}
      aria-label={assistant ? t("Assistant response") : t("Your message")}
    >
      {assistant && (
        <span className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-gradient-to-tr from-teal-700 to-emerald-600 text-white shadow-2xs">
          <Sparkles size={16} />
        </span>
      )}
      <div
        className={
          assistant
            ? "min-w-0 flex-1 space-y-1.5"
            : "max-w-[85%] rounded-2xl rounded-br-xs bg-emerald-50 border border-emerald-200 px-4 py-3 shadow-2xs dark:bg-emerald-950/40 dark:border-emerald-800/50"
        }
      >
        {assistant && (
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-bold text-slate-900 dark:text-white">Luna AI</span>
            <span className="rounded bg-emerald-50 border border-emerald-200 px-1.5 py-0.2 text-[10px] font-mono text-emerald-800 dark:bg-emerald-950/50 dark:border-emerald-800/50 dark:text-emerald-300 font-semibold">
              gpt-6-luna
            </span>
            {isStreaming && (
              <span className="flex items-center gap-1 text-[11px] text-emerald-700 dark:text-emerald-400 animate-pulse font-medium">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                {t("Thinking…")}</span>
            )}
          </div>
        )}
        <div
          className={`text-sm leading-7 ${
            assistant
              ? "markdown-content text-slate-800 dark:text-slate-200"
              : "whitespace-pre-wrap break-words text-slate-900 dark:text-emerald-100 font-medium"
          }`}
        >
          {assistant ? (
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content ||
                (isStreaming
                  ? t("Analyzing document with Luna…")
                  : t("No response was received."))}
            </ReactMarkdown>
          ) : (
            message.content
          )}
        </div>
        {assistant && message.content && (
          <div className="flex items-center gap-2 pt-1">
            <button
              onClick={copy}
              className="flex items-center gap-1.5 rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] font-medium text-slate-500 hover:text-slate-800 hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400 dark:hover:text-slate-200 dark:hover:bg-slate-800 transition shadow-2xs"
              aria-label={t("Copy response")}
            >
              {copied ? <Check size={12} className="text-emerald-600 dark:text-emerald-400" /> : <Copy size={12} />}
              <span>{copied ? t("Copied") : t("Copy")}</span>
            </button>
          </div>
        )}
      </div>
    </article>
  );
}
