"use client";

import { type Message } from "@/lib/types";
import { MessageBubble } from "@/components/chat/message-bubble";
import { Spinner } from "@/components/ui/spinner";
import { Bot } from "lucide-react";

export function MessageList({
  messages,
  isStreaming,
}: {
  messages: Message[];
  isStreaming?: boolean;
}) {
  return (
    <div className="flex-1 space-y-4 overflow-y-auto px-1 py-4">
      {messages.map((m) => (
        <MessageBubble key={m.id} message={m} />
      ))}

      {isStreaming && (
        <div className="flex gap-3 px-1">
          <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-indigo-100 ">
            <Bot size={16} className="text-indigo-600 " />
          </div>
          <div className="max-w-[80%] rounded-2xl rounded-bl-none bg-zinc-100 px-4 py-3 ">
            <Spinner size={16} />
          </div>
        </div>
      )}
    </div>
  );
}
