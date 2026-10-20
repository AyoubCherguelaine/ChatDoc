"use client";
import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { DocumentCard } from "@/components/drive/document-card";
import { UploadForm } from "@/components/drive/upload-form";
import { Dialog } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { fetchDocuments, fetchSessions, ApiError } from "@/lib/api";
import { useSession } from "@/components/providers/session-provider";
import {
  Plus,
  Search,
  Files,
  MessageSquare,
  HardDrive,
  ArrowUpRight,
  Sparkles,
  FileSearch,
  FileSpreadsheet,
  ListChecks,
  LayoutGrid,
  List,
  RefreshCw,
  ArrowRight,
} from "lucide-react";
import { formatBytes } from "@/lib/utils";
import { workflows } from "@/lib/workflows";
import type { Document, ChatSession } from "@/lib/types";
export default function DrivePage() {
  const { user } = useSession();
  const params = useSearchParams();
  const [docs, setDocs] = useState<Document[]>([]);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [type, setType] = useState("all");
  const [sort, setSort] = useState("recent");
  const [layout, setLayout] = useState("grid");
  const [sessionError, setSessionError] = useState(false);
  const loadDocs = useCallback(async () => {
    setLoading(true);
    setError("");
    setSessionError(false);
    try {
      const d = await fetchDocuments();
      setDocs(d);
      try {
        setSessions(await fetchSessions());
      } catch {
        setSessionError(true);
      }
    } catch (e) {
      setError(
        e instanceof ApiError ? e.message : "Could not load your workspace.",
      );
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    // Initial workspace fetch and explicit refresh share the same loading states.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadDocs();
  }, [loadDocs]);
  const filtered = docs
    .filter(
      (d) =>
        d.originalFilename.toLowerCase().includes(search.toLowerCase()) &&
        (type === "all" ||
          (type === "sheets"
            ? /\.(xlsx|xls|csv)$/i.test(d.originalFilename)
            : type === "word"
              ? /\.docx$/i.test(d.originalFilename)
              : /\.pdf$/i.test(d.originalFilename))),
    )
    .sort((a, b) =>
      sort === "name"
        ? a.originalFilename.localeCompare(b.originalFilename)
        : sort === "size"
          ? b.fileSize - a.fileSize
          : b.createdAt.localeCompare(a.createdAt),
    );
  const icons = [Sparkles, FileSearch, FileSpreadsheet, ListChecks];
  const library = params.get("view") === "documents";
  return (
    <div className="mx-auto max-w-[1500px] animate-enter">
      <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="eyebrow mb-2">
            Workspace / {library ? "Documents" : "Overview"}
          </p>
          <h1 className="text-[27px] font-semibold tracking-tight">
            {library
              ? "Your knowledge, organized."
              : `A little clarity, ${user?.name?.split(" ")[0] || "for your day"}.`}
          </h1>
          <p className="mt-2 text-sm text-[#87959c]">
            {library
              ? "All your sources. Ready for the next question."
              : "Here’s what’s happening in your knowledge workspace."}
          </p>
        </div>
        <Button className="gap-2 shadow-sm" onClick={() => setUploadOpen(true)}>
          <Plus size={16} /> Upload document
        </Button>
      </div>
      <div className="mb-8 grid grid-cols-2 gap-3 xl:grid-cols-4">
        {[
          {
            label: "Total documents",
            value: docs.length,
            icon: Files,
            note: "In your personal library",
          },
          {
            label: "Conversations",
            value: sessions.length,
            icon: MessageSquare,
            note: sessionError
              ? "Some conversations could not load"
              : "Ideas worth coming back to",
          },
          {
            label: "Pages & sections",
            value: docs.reduce((n, d) => n + d.pageCount, 0),
            icon: FileSearch,
            note: "Ready to explore",
          },
          {
            label: "Storage used",
            value: formatBytes(docs.reduce((n, d) => n + d.fileSize, 0)),
            icon: HardDrive,
            note: "PDF, Word, Excel & more",
          },
        ].map(({ label, value, icon: Icon, note }) => (
          <div key={label} className="surface p-5">
            <div className="flex items-center justify-between text-xs text-slate-500">
              {label}
              <Icon size={16} className="text-[#9caeb1]" />
            </div>
            <p className="mt-4 text-3xl font-semibold tracking-tight">
              {loading ? "—" : value}
            </p>
            <p className="mt-2 text-[10px] text-slate-400">{note}</p>
          </div>
        ))}
      </div>
      {!library && (
        <>
          <div className="mb-8 grid gap-5 xl:grid-cols-[1.75fr_1fr]">
            <section className="relative overflow-hidden rounded-2xl border border-[#dce8dd] bg-[#edf4e9] p-6 md:p-8">
              <div className="absolute -right-8 -top-12 h-56 w-56 rounded-full border-[28px] border-[#dfeadb]/60" />
              <p className="eyebrow !text-[#708b66]">Your thinking partner</p>
              <h2 className="relative mt-3 max-w-md text-2xl font-semibold tracking-tight text-[#314e3e]">
                There’s more in your documents
                <br className="hidden sm:block" /> than you think.
              </h2>
              <p className="relative mt-3 max-w-sm text-xs leading-6 text-[#7b8f77]">
                Uncover the key points, connect the dots, and turn information
                into your next move.
              </p>
              <Link
                href="/agents"
                className="relative mt-6 inline-flex items-center gap-4 rounded-lg bg-white px-4 py-2.5 text-xs font-medium text-[#456745] shadow-sm"
              >
                Find an insight <ArrowUpRight size={15} />
              </Link>
            </section>
            <section className="surface p-6">
              <div className="flex justify-between">
                <h2 className="text-sm font-semibold">
                  Pick up where you left off
                </h2>
                <MessageSquare size={16} className="text-slate-400" />
              </div>
              {sessions.slice(0, 3).map((s) => (
                <Link
                  key={s.id}
                  href={`/chat/${s.id}`}
                  className="mt-4 flex items-center gap-3 rounded-lg p-2 hover:bg-slate-50"
                >
                  <span className="rounded-lg bg-[#eef4f4] p-2 text-teal-700">
                    <MessageSquare size={14} />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-medium">{s.title}</p>
                    <p className="mt-1 text-[10px] text-slate-400">
                      {s.messageCount || 0} messages
                    </p>
                  </div>
                  <ArrowUpRight size={13} className="text-slate-400" />
                </Link>
              ))}
              {!sessions.length && (
                <div className="mt-6">
                  <p className="text-sm text-slate-500">
                    Your next good idea starts here.
                  </p>
                  <p className="mt-2 text-xs leading-6 text-slate-400">
                    Open a document to start a conversation. You can always come
                    back to it.
                  </p>
                  <button
                    onClick={() => setUploadOpen(true)}
                    className="mt-4 flex items-center gap-2 text-xs font-medium text-teal-700"
                  >
                    Add your first source <ArrowRight size={14} />
                  </button>
                </div>
              )}
            </section>
          </div>
          <section className="mb-9">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-sm font-semibold">
                A head start on your next task
              </h2>
              <Link
                href="/agents"
                className="flex gap-1 text-xs text-slate-400"
              >
                AI studio <ArrowUpRight size={13} />
              </Link>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {workflows.map((w, i) => {
                const Icon = icons[i];
                return (
                  <Link
                    key={w.id}
                    href={`/agents?workflow=${w.id}`}
                    className="surface group flex gap-3 p-4 transition hover:-translate-y-0.5 hover:border-[#aacdbf]"
                  >
                    <span
                      className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${["bg-[#eef4e8] text-[#7a925b]", "bg-[#eaf1fa] text-[#7197be]", "bg-[#fbefe6] text-[#c79773]", "bg-[#f1edfa] text-[#9c87bf]"][i]}`}
                    >
                      <Icon size={17} />
                    </span>
                    <div>
                      <p className="text-xs font-semibold">{w.title}</p>
                      <p className="mt-1.5 text-[10px] leading-4 text-slate-400">
                        {w.description}
                      </p>
                    </div>
                  </Link>
                );
              })}
            </div>
          </section>
        </>
      )}
      <section id="documents">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-base font-semibold">
            {library ? "All documents" : "Your documents"}{" "}
            <span className="ml-2 rounded-md bg-[#e9eef0] px-2 py-0.5 text-[10px] font-medium text-slate-500">
              {docs.length}
            </span>
          </h2>
          <div className="flex gap-2">
            <button
              aria-label="Refresh documents"
              onClick={loadDocs}
              disabled={loading}
              className="rounded-lg border border-slate-200 bg-white p-2 text-slate-400"
            >
              <RefreshCw size={15} />
            </button>
            <div className="flex rounded-lg border border-slate-200 bg-white p-1">
              {[
                { id: "grid", icon: LayoutGrid },
                { id: "list", icon: List },
              ].map(({ id, icon: Icon }) => (
                <button
                  key={id}
                  aria-label={`${id} view`}
                  aria-pressed={layout === id}
                  onClick={() => setLayout(id)}
                  className={`rounded p-1 ${layout === id ? "bg-[#eaf3ef] text-teal-700" : "text-slate-400"}`}
                >
                  <Icon size={15} />
                </button>
              ))}
            </div>
          </div>
        </div>
        <div className="mb-5 flex flex-wrap items-center gap-3">
          <div className="relative min-w-[180px] flex-1">
            <Search
              className="absolute left-3 top-3 text-slate-400"
              size={15}
            />
            <input
              aria-label="Search documents"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search your documents…"
              className="h-10 w-full rounded-lg border border-[#e2e8eb] bg-white pl-9 pr-3 text-xs outline-none focus:border-teal-600"
            />
          </div>
          <select
            aria-label="Filter document type"
            value={type}
            onChange={(e) => setType(e.target.value)}
            className="h-10 rounded-lg border border-slate-200 bg-white px-3 text-xs text-slate-500"
          >
            <option value="all">All file types</option>
            <option value="pdf">PDF documents</option>
            <option value="word">Word documents</option>
            <option value="sheets">Spreadsheets</option>
          </select>
          <select
            aria-label="Sort documents"
            value={sort}
            onChange={(e) => setSort(e.target.value)}
            className="h-10 rounded-lg border border-slate-200 bg-white px-3 text-xs text-slate-500"
          >
            <option value="recent">Recently added</option>
            <option value="name">Name A–Z</option>
            <option value="size">Largest first</option>
          </select>
        </div>
        {error && (
          <div
            role="alert"
            className="mb-4 flex items-center justify-between rounded-xl bg-rose-50 p-4 text-sm text-rose-700"
          >
            {error}
            <button onClick={loadDocs} className="ml-3 underline">
              Retry
            </button>
          </div>
        )}
        {loading ? (
          <div className="surface flex justify-center p-12">
            <Spinner size={25} />
          </div>
        ) : docs.length === 0 ? (
          <div className="surface grid items-center gap-8 p-7 md:grid-cols-[1fr_1fr]">
            <div>
              <span className="mb-4 inline-flex rounded-xl bg-[#edf4ef] p-3 text-teal-700">
                <Files size={26} />
              </span>
              <h3 className="text-lg font-semibold">
                Make room for your next idea.
              </h3>
              <p className="mt-2 max-w-sm text-sm leading-7 text-slate-400">
                Add a document to build your knowledge library. Ask questions,
                extract the essentials, and find what matters.
              </p>
              <div className="mt-5 flex flex-wrap gap-2">
                {["PDF reports", "Word documents", "Excel workbooks"].map(
                  (t) => (
                    <span
                      key={t}
                      className="rounded border border-slate-200 px-2 py-1 text-[10px] text-slate-500"
                    >
                      {t}
                    </span>
                  ),
                )}
              </div>
            </div>
            <UploadForm onDone={loadDocs} />
          </div>
        ) : filtered.length === 0 ? (
          <div className="surface p-12 text-center text-sm text-slate-500">
            No documents match your search.{" "}
            <button
              className="text-teal-700 underline"
              onClick={() => {
                setSearch("");
                setType("all");
              }}
            >
              Clear filters
            </button>
          </div>
        ) : (
          <div
            className={
              layout === "grid"
                ? "grid gap-4 md:grid-cols-2 2xl:grid-cols-3"
                : "grid gap-3"
            }
          >
            {filtered.map((doc) => (
              <DocumentCard key={doc.id} doc={doc} onSaved={loadDocs} />
            ))}
          </div>
        )}
      </section>
      <Dialog
        open={uploadOpen}
        onOpenChange={setUploadOpen}
        title="Add to your knowledge"
        description="Your next conversation starts with a source."
      >
        <UploadForm
          onDone={() => {
            setUploadOpen(false);
            void loadDocs();
          }}
        />
      </Dialog>
      <footer className="mt-9 flex flex-wrap justify-between gap-2 border-t border-slate-200 pt-5 text-[10px] text-slate-400">
        <span>YOUR KNOWLEDGE. A LITTLE MORE CONNECTED.</span>
        <span>PDF · Word · Excel · CSV · Text</span>
      </footer>
    </div>
  );
}
