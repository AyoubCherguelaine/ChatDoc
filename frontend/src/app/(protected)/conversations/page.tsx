"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { MessageSquare, ArrowUpRight, Search } from "lucide-react";
import { fetchSessions } from "@/lib/api";
import { Spinner } from "@/components/ui/spinner";
import type { ChatSession } from "@/lib/types";
import { formatDate } from "@/lib/utils";
export default function ConversationsPage() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const all = await fetchSessions();
        if (active) setSessions(all);
      } catch {
        if (active) setError("Could not load conversations. Refresh to retry.");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, []);
  return (
    <div className="mx-auto max-w-6xl">
      <p className="eyebrow">Workspace / Conversations</p>
      <h1 className="mt-3 text-3xl font-semibold tracking-tight">
        Keep the conversation going.
      </h1>
      <p className="mt-3 text-sm text-slate-500">
        Your questions, findings, and the ideas in between.
      </p>
      <div className="relative my-7 max-w-md">
        <Search size={17} className="absolute left-3 top-3 text-slate-400" />
        <input
          aria-label="Search conversations"
          placeholder="Find a conversation…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full rounded-lg border border-slate-200 bg-white py-3 pl-10 pr-3 text-xs"
        />
      </div>
      {error && (
        <p role="alert" className="mb-5 text-sm text-rose-700">
          {error}
        </p>
      )}
      {loading ? (
        <Spinner size={24} />
      ) : sessions.length ? (
        <div className="grid gap-3">
          {!sessions.some((s) =>
            s.title.toLowerCase().includes(search.toLowerCase()),
          ) && (
            <p className="surface p-6 text-sm text-slate-500">
              No conversations match your search.
            </p>
          )}
          {sessions
            .filter((s) => s.title.toLowerCase().includes(search.toLowerCase()))
            .map((s) => (
              <Link
                href={`/chat/${s.id}`}
                key={s.id}
                className="surface flex items-center gap-4 p-5 hover:!border-teal-300"
              >
                <span className="rounded-lg bg-teal-50 p-3 text-teal-700">
                  <MessageSquare size={19} />
                </span>
                <div className="min-w-0 flex-1">
                  <h2 className="truncate text-sm font-medium">{s.title}</h2>
                  <p className="mt-2 text-xs text-slate-400">
                    {s.messageCount || 0} messages · {formatDate(s.updatedAt)}
                  </p>
                </div>
                <ArrowUpRight size={18} className="text-slate-400" />
              </Link>
            ))}
        </div>
      ) : (
        <div className="surface p-10">
          <MessageSquare size={32} className="mb-5 text-teal-700" />
          <h2 className="text-xl font-semibold">
            Every insight starts with a question.
          </h2>
          <p className="mt-3 text-sm text-slate-500">
            Start a chat from any document in your library.
          </p>
          <Link
            href="/drive"
            className="mt-6 inline-flex gap-2 text-sm font-medium text-teal-700"
          >
            Explore your documents <ArrowUpRight size={17} />
          </Link>
        </div>
      )}
    </div>
  );
}
