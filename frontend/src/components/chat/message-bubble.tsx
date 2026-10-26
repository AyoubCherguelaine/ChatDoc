"use client";
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
  const assistant = message.role === "assistant";
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopyError(true);
    }
  };
  return (
    <article
      className={`flex gap-3 py-4 ${assistant ? "" : "justify-end"}`}
      aria-label={assistant ? "Assistant response" : "Your message"}
    >
      {assistant && (
        <span className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-[#e7f2ec] text-teal-700">
          <Sparkles size={17} />
        </span>
      )}
      <div
        className={
          assistant
            ? "min-w-0 flex-1"
            : "max-w-[85%] rounded-2xl rounded-br-sm bg-[#eaf0ef] px-4 py-3"
        }
      >
        {assistant && (
          <p className="mb-3 text-xs font-semibold text-[#41645c]">DOCTool</p>
        )}
        <div
          className={`text-sm leading-7 ${assistant ? "markdown-content text-slate-600" : "whitespace-pre-wrap break-words text-slate-700"}`}
        >
          {assistant ? (
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content ||
                (isStreaming
                  ? "Reading your source…"
                  : "No response was received.")}
            </ReactMarkdown>
          ) : (
            message.content
          )}
        </div>
        {assistant && message.content && (
          <button
            onClick={copy}
            className="mt-3 flex items-center gap-1.5 rounded px-1 py-1 text-[10px] text-slate-400 hover:text-teal-700"
            aria-label="Copy response"
          >
            {copied ? <Check size={12} /> : <Copy size={12} />}{" "}
            {copyError
              ? "Select text to copy"
              : copied
                ? "Copied"
                : "Copy response"}
          </button>
        )}
      </div>
    </article>
  );
}
