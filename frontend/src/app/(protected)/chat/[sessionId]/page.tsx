"use client";
import { use, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { ChatInput } from "@/components/chat/chat-input";
import { MessageBubble } from "@/components/chat/message-bubble";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import {
  streamChat,
  fetchSession,
  fetchCapabilities,
  fetchPage,
  ApiError,
} from "@/lib/api";
import type { ChatMode, Message } from "@/lib/types";
import { workflows } from "@/lib/workflows";
import {
  ArrowLeft,
  Download,
  FileText,
  BookOpen,
  ChevronLeft,
  ChevronRight,
  Sparkles,
  PanelRightClose,
  Bot,
  Settings2,
  ArrowUpRight,
} from "lucide-react";
export default function ChatPage({
  params,
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const { sessionId } = use(params);
  const search = useSearchParams();
  const initialWorkflow = workflows.find(
    (w) => w.id === search?.get("workflow"),
  );
  const [session, setSession] = useState<Awaited<
    ReturnType<typeof fetchSession>
  > | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState("");
  const [mode, setMode] = useState<ChatMode>(
    initialWorkflow?.mode || "conversational",
  );
  const [models, setModels] = useState<string[]>([]);
  const [model, setModel] = useState("");
  const [style, setStyle] = useState("balanced");
  const [sourceOpen, setSourceOpen] = useState(true);
  const [page, setPage] = useState(1);
  const [source, setSource] = useState("");
  const [sourceError, setSourceError] = useState("");
  const [sourceLoading, setSourceLoading] = useState(false);
  const [draft, setDraft] = useState(initialWorkflow?.prompt || "");
  const [draftKey, setDraftKey] = useState(0);
  const scroll = useRef<HTMLDivElement>(null);
  const abort = useRef<AbortController | null>(null);
  useEffect(() => {
    let active = true;
    fetchSession(sessionId)
      .then((s) => {
        if (active) {
          setSession(s);
          setMessages(s.messages);
        }
      })
      .catch((e) => {
        if (active)
          setError(
            e instanceof ApiError
              ? e.message
              : "Could not load the conversation.",
          );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    fetchCapabilities()
      .then((c) => {
        if (active) {
          setModels(c.models);
          setModel(c.defaultModel);
        }
      })
      .catch(() => {});
    return () => {
      active = false;
      abort.current?.abort();
    };
  }, [sessionId]);
  useEffect(() => {
    if (!session || !sourceOpen) return;
    let active = true;
    const load = async () => {
      setSourceLoading(true);
      setSourceError("");
      try {
        const p = await fetchPage(session.document.id, page);
        if (active) setSource(p.text);
      } catch {
        if (active) {
          setSource("");
          setSourceError(
            "Could not read this section. Try another page or reopen the panel.",
          );
        }
      } finally {
        if (active) setSourceLoading(false);
      }
    };
    void load();
    return () => {
      active = false;
    };
  }, [session, sourceOpen, page]);
  useEffect(() => {
    scroll.current?.scrollTo({
      top: scroll.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);
  const send = async (text: string) => {
    if (streaming) return;
    setError("");
    const now = new Date().toISOString();
    const id = crypto.randomUUID();
    setMessages((m) => [
      ...m,
      {
        id: crypto.randomUUID(),
        sessionId,
        role: "user",
        content: text,
        createdAt: now,
      },
      { id, sessionId, role: "assistant", content: "", createdAt: now },
    ]);
    setStreaming(true);
    const controller = new AbortController();
    abort.current = controller;
    let acc = "";
    try {
      for await (const chunk of streamChat(sessionId, text, mode, {
        model: model || undefined,
        responseStyle: style,
        signal: controller.signal,
      })) {
        acc += chunk;
        setMessages((m) =>
          m.map((item) => (item.id === id ? { ...item, content: acc } : item)),
        );
      }
    } catch (e) {
      if (!(e instanceof Error && e.name === "AbortError"))
        setError(
          e instanceof ApiError
            ? e.message
            : "The response was interrupted. Please try again.",
        );
    } finally {
      setStreaming(false);
      abort.current = null;
    }
  };
  const exportChat = () => {
    const text =
      `# ${session?.title}\n\n` +
      messages
        .map(
          (m) => `## ${m.role === "user" ? "You" : "DOCTool"}\n\n${m.content}`,
        )
        .join("\n\n");
    const url = URL.createObjectURL(
      new Blob([text], { type: "text/markdown" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = "doctool-conversation.md";
    a.click();
    URL.revokeObjectURL(url);
  };
  const apply = (id: string) => {
    const w = workflows.find((x) => x.id === id);
    if (w) {
      setMode(w.mode);
      setDraft(w.prompt);
      setDraftKey((n) => n + 1);
    }
  };
  if (loading)
    return (
      <div className="flex h-[70vh] items-center justify-center">
        <Spinner size={28} />
      </div>
    );
  if (!session)
    return (
      <div role="alert" className="surface p-8">
        <p className="text-sm text-rose-700">
          {error || "Conversation unavailable."}
        </p>
        <Link href="/drive" className="mt-5 inline-block text-sm text-teal-700">
          Return to documents
        </Link>
      </div>
    );
  const unit = /\.pdf$/i.test(session.document.originalFilename)
    ? "page"
    : "section";
  return (
    <div className="mx-auto flex max-w-[1600px] flex-col">
      <header className="mb-5 flex flex-wrap items-center justify-between gap-4">
        <div className="flex min-w-0 items-center gap-3">
          <Link
            href="/drive"
            aria-label="Back to documents"
            className="rounded-lg border border-slate-200 bg-white p-2 text-slate-500"
          >
            <ArrowLeft size={17} />
          </Link>
          <div className="min-w-0">
            <p className="eyebrow mb-1">Workspace / Conversations</p>
            <h1 className="max-w-[60vw] truncate text-lg font-semibold tracking-tight lg:max-w-xl">
              {session.title}
            </h1>
          </div>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={exportChat}
            disabled={!messages.length || streaming}
            className="gap-2 !border-slate-200 bg-white text-xs"
          >
            <Download size={14} /> Export
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setSourceOpen(!sourceOpen)}
            aria-expanded={sourceOpen}
            className="gap-2 !border-slate-200 bg-white text-xs"
          >
            <BookOpen size={14} /> Source
          </Button>
        </div>
      </header>
      <div
        className={`grid min-h-[76vh] gap-5 ${sourceOpen ? "xl:grid-cols-[minmax(0,1fr)_320px]" : "grid-cols-1"}`}
      >
        <section className="surface flex min-w-0 flex-col overflow-hidden">
          <div className="flex flex-wrap items-center gap-3 border-b border-slate-100 px-5 py-3">
            <div className="mr-auto flex items-center gap-2 text-xs text-slate-500">
              <span className="h-1.5 w-1.5 rounded-full bg-teal-500" /> Grounded
              in your document
            </div>
            <select
               aria-label="Assistant mode"
               disabled={streaming}
               value={mode}
               onChange={(e) => setMode(e.target.value as ChatMode)}
               className="rounded-md border border-slate-200 bg-white p-1.5 text-[11px]"
             >
              <option value="conversational">Document chat</option>
              <option value="agent">Research agent</option>
              <option value="summary">Summary agent</option>
              <option value="research">Deep research</option>
              <option value="extraction">Data extraction</option>
              <option value="comparison">Comparison</option>
              <option value="factcheck">Fact-check</option>
              <option value="invoice">Invoice processing</option>
              <option value="receipt">Receipt & Expenses</option>
              <option value="contract">Contract analysis</option>
              <option value="resume">Resume & Talent</option>
              <option value="compliance">PII & Compliance</option>
              <option value="form_parser">Form Parser</option>
              <option value="google_ai">Google AI Document</option>
              <option value="coordinator">Auto-routing</option>
            </select>
          </div>
          <div
            ref={scroll}
            aria-live="polite"
            aria-relevant="additions"
            className="h-[49vh] min-h-[310px] flex-1 overflow-y-auto px-5 py-4 sm:px-8"
          >
            {messages.length ? (
              messages.map((m, i) => (
                <MessageBubble
                  key={m.id}
                  message={m}
                  isStreaming={streaming && i === messages.length - 1}
                />
              ))
            ) : (
              <div className="mx-auto max-w-lg py-8">
                <span className="mb-5 inline-flex rounded-2xl bg-[#eef5ed] p-4 text-teal-700">
                  <Sparkles size={29} />
                </span>
                <h2 className="text-2xl font-semibold tracking-tight">
                  What would you like to discover?
                </h2>
                <p className="mt-3 text-sm leading-7 text-slate-400">
                  Ask about {session.document.originalFilename}, or start with a
                  little inspiration.
                </p>
                <div className="mt-7 grid gap-3 sm:grid-cols-2">
                  {workflows.map((w) => (
                    <button
                      key={w.id}
                      onClick={() => apply(w.id)}
                      className="rounded-xl border border-[#e2e9e4] p-4 text-left transition hover:border-teal-500 hover:bg-teal-50/20"
                    >
                      <span className="flex items-center justify-between text-xs font-semibold">
                        {w.title}
                        <ArrowUpRight size={13} className="text-teal-700" />
                      </span>
                      <span className="mt-2 block text-[11px] leading-5 text-slate-400">
                        {w.description}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
          <div className="border-t border-slate-100 p-4 sm:px-6">
            {error && (
              <div
                role="alert"
                className="mb-3 flex items-center justify-between rounded-lg bg-rose-50 p-3 text-xs text-rose-700"
              >
                <span>{error}</span>
                {error.toLowerCase().includes("credit") && (
                  <Link
                    href="/usage"
                    className="ml-3 shrink-0 rounded bg-rose-600 px-2.5 py-1 text-[11px] font-medium text-white hover:bg-rose-700 transition"
                  >
                    View API & Credits
                  </Link>
                )}
              </div>
            )}
            <ChatInput
              key={draftKey}
              initialText={draft}
              onSubmit={send}
              disabled={streaming}
              onStop={() => abort.current?.abort()}
            />
            <div className="mt-2 flex items-center justify-between gap-2 text-[9px] text-slate-400">
              <span>
                {streaming
                  ? mode === "agent" ||
                    mode === "research" ||
                    mode === "comparison" ||
                    mode === "factcheck" ||
                    mode === "coordinator"
                    ? "Agent is searching and reading your document…"
                    : mode === "extraction"
                      ? "Agent is extracting data from your document…"
                      : mode === "summary"
                        ? "Agent is summarizing your document…"
                        : mode === "invoice"
                          ? "Agent is processing the invoice…"
                          : mode === "contract"
                            ? "Agent is analyzing the contract…"
                            : "Preparing your answer…"
                  : "AI can make mistakes. Check important details against the source."}
              </span>
              <span className="hidden shrink-0 sm:block">
                {mode === "agent"
                  ? "Research agent"
                  : mode === "summary"
                    ? "Summary agent"
                    : mode === "research"
                      ? "Deep research"
                      : mode === "extraction"
                        ? "Data extraction"
                        : mode === "comparison"
                          ? "Comparison"
                          : mode === "factcheck"
                            ? "Fact-check"
                            : mode === "invoice"
                              ? "Invoice processing"
                              : mode === "contract"
                                ? "Contract analysis"
                                : mode === "coordinator"
                                  ? "Auto-routing"
                                  : "Document chat"}
              </span>
            </div>
          </div>
        </section>
        {sourceOpen && (
          <aside className="flex min-w-0 flex-col gap-4">
            <section className="surface p-5">
              <div className="flex items-center justify-between">
                <h2 className="flex items-center gap-2 text-xs font-semibold">
                  <Settings2 size={15} className="text-slate-400" />{" "}
                  Conversation settings
                </h2>
              </div>
              <label
                htmlFor="model"
                className="mb-2 mt-5 block text-[10px] text-slate-500"
              >
                Language model
              </label>
              <select
                id="model"
                disabled={streaming || !models.length}
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs"
              >
                {models.length ? (
                  models.map((m) => <option key={m}>{m}</option>)
                ) : (
                  <option value="">Server default</option>
                )}
              </select>
              <label
                htmlFor="style"
                className="mb-2 mt-4 block text-[10px] text-slate-500"
              >
                Answer length
              </label>
              <select
                id="style"
                disabled={streaming}
                value={style}
                onChange={(e) => setStyle(e.target.value)}
                className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs"
              >
                <option value="concise">Concise</option>
                <option value="balanced">Balanced</option>
                <option value="detailed">Detailed</option>
              </select>
              <p className="mt-4 flex items-center gap-2 text-[10px] leading-5 text-slate-400">
                <Bot size={14} className="shrink-0" />
                {mode === "agent" ||
                mode === "research" ||
                mode === "comparison" ||
                mode === "factcheck"
                  ? "Research tools: search, read pages, compare, verify."
                  : mode === "summary"
                    ? "Summary tools: search, read pages, summarize."
                    : mode === "extraction"
                      ? "Extraction tools: search, read, extract tables, calculate."
                      : mode === "coordinator"
                        ? "Coordinator: auto-routes to specialist agents."
                        : "Switch to a research agent for deeper investigation."}
              </p>
            </section>
            <section className="surface flex min-h-[340px] flex-1 flex-col p-5">
              <div className="flex items-center justify-between">
                <h2 className="flex items-center gap-2 text-xs font-semibold">
                  <BookOpen size={15} className="text-slate-400" /> Source
                  reader
                </h2>
                <button
                  aria-label="Close source reader"
                  onClick={() => setSourceOpen(false)}
                  className="text-slate-400"
                >
                  <PanelRightClose size={15} />
                </button>
              </div>
              <div className="my-4 flex items-center gap-2 rounded-lg bg-[#f5f7f4] p-3">
                <FileText size={18} className="shrink-0 text-teal-700" />
                <p
                  title={session.document.originalFilename}
                  className="truncate text-[11px] font-medium"
                >
                  {session.document.originalFilename}
                </p>
              </div>
              <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                <button
                  aria-label="Previous section"
                  disabled={page <= 1 || sourceLoading}
                  onClick={() => setPage((p) => p - 1)}
                  className="rounded p-1 text-slate-500 disabled:opacity-25"
                >
                  <ChevronLeft size={15} />
                </button>
                <span className="text-[10px] capitalize text-slate-500">
                  {unit} {page} of {session.document.pageCount}
                </span>
                <button
                  aria-label="Next section"
                  disabled={page >= session.document.pageCount || sourceLoading}
                  onClick={() => setPage((p) => p + 1)}
                  className="rounded p-1 text-slate-500 disabled:opacity-25"
                >
                  <ChevronRight size={15} />
                </button>
              </div>
              <div className="mt-4 max-h-[43vh] overflow-y-auto whitespace-pre-wrap break-words text-[11px] leading-6 text-slate-500">
                {sourceLoading ? (
                  <Spinner size={18} />
                ) : sourceError ? (
                  <p role="alert">{sourceError}</p>
                ) : (
                  source
                )}
              </div>
              <button
                disabled={streaming || sourceLoading || !source}
                onClick={() => {
                  setDraft(
                    `Explain the key points on ${unit} ${page} of this document, citing the source.`,
                  );
                  setDraftKey((k) => k + 1);
                }}
                className="mt-auto flex items-center justify-between border-t border-slate-100 pt-4 text-[10px] font-medium text-teal-700 disabled:opacity-40"
              >
                Ask about this {unit}
                <ArrowUpRight size={13} />
              </button>
            </section>
          </aside>
        )}
      </div>
    </div>
  );
}
