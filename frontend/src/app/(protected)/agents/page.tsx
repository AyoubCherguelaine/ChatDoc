"use client";
import { useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import {
  Bot,
  Sparkles,
  ArrowRight,
  FileText,
  FileSpreadsheet,
  ListChecks,
  SearchCheck,
  Receipt,
  FileSignature,
  FileSearch,
  Search,
} from "lucide-react";
import { workflows } from "@/lib/workflows";
import { fetchDocuments, createSession, uploadDocument } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import type { Document } from "@/lib/types";
import Link from "next/link";
export default function AgentsPage() {
  const params = useSearchParams();
  const router = useRouter();
  const [selected, setSelected] = useState(params?.get("workflow") || "summary");
  const [docs, setDocs] = useState<Document[]>([]);
  const [docId, setDocId] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    fetchDocuments()
      .then((d) => {
        if (active) {
          setDocs(d);
          setDocId(d[0]?.id || "");
        }
      })
      .catch(() => {
        if (active) setError("Could not load documents. Refresh to try again.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);
  const workflow = workflows.find((w) => w.id === selected) || workflows[0];
  const start = async () => {
    setBusy(true);
    setError("");
    try {
      const s = await createSession(docId, workflow.title);
      router.push(`/chat/${s.id}?workflow=${workflow.id}`);
    } catch {
      setError("Could not create the conversation. Please try again.");
      setBusy(false);
    }
  };
  const icons = [Sparkles, SearchCheck, FileSpreadsheet, ListChecks, FileSearch, Search, Bot, Receipt, FileSignature];
  const badgeColors = [
    "bg-[#eef4e8] text-[#7a925b]",
    "bg-[#eaf1fa] text-[#7197be]",
    "bg-[#fbefe6] text-[#c79773]",
    "bg-[#f1edfa] text-[#9c87bf]",
    "bg-[#fef3c7] text-[#d97706]",
    "bg-[#ecfdf5] text-[#059669]",
    "bg-[#eff6ff] text-[#2563eb]",
    "bg-[#ecfdf5] text-[#059669]",
    "bg-[#eff6ff] text-[#2563eb]",
  ];
  return (
    <div className="mx-auto max-w-6xl animate-enter">
      <p className="eyebrow">Workspace / AI studio</p>
      <h1 className="mt-3 text-3xl font-semibold tracking-tight">
        A head start on the hard part.
      </h1>
      <p className="mt-3 text-sm text-slate-500">
        Choose a workflow, add a source, and give your thinking a little
        momentum.
      </p>
      <div className="mt-8 grid items-start gap-7 xl:grid-cols-[1.5fr_1fr]">
        <div className="grid gap-4 sm:grid-cols-2">
          {workflows.map((w, i) => {
            const Icon = icons[i] || Sparkles;
            return (
              <button
                key={w.id}
                onClick={() => setSelected(w.id)}
                aria-pressed={selected === w.id}
                className={`surface p-6 text-left transition hover:border-teal-400 ${selected === w.id ? "!border-teal-600 ring-1 ring-teal-600" : ""}`}
              >
                <div className="mb-6 flex items-center justify-between">
                  <span className={`rounded-xl bg-[#ecf4ef] p-3 text-teal-700`}>
                    <Icon size={23} />
                  </span>
                  <span className={`rounded-full px-2 py-1 text-[10px] ${badgeColors[i % badgeColors.length]}`}>
                    {w.mode === "agent"
                      ? "Research agent"
                      : w.mode === "invoice"
                        ? "Invoice"
                        : w.mode === "contract"
                          ? "Contract"
                          : "Document assistant"}
                  </span>
                </div>
                <h2 className="font-semibold">{w.title}</h2>
                <p className="mt-2 text-xs leading-6 text-slate-500">
                  {w.description}
                </p>
                <div className="mt-6 flex items-center gap-2 text-xs text-teal-700">
                  {selected === w.id ? "Selected workflow" : "Choose workflow"}
                  <ArrowRight size={14} />
                </div>
              </button>
            );
          })}
        </div>
        <section className="surface p-6">
          <Bot size={24} className="text-teal-700" />
          <h2 className="mt-4 text-lg font-semibold">{workflow.title}</h2>
          <p className="mt-2 text-xs leading-6 text-slate-500">
            {workflow.prompt}
          </p>
          <label
            htmlFor="source"
            className="mb-2 mt-6 block text-xs font-semibold"
          >
            Choose your source
          </label>
          {loading ? (
            <Spinner size={20} />
          ) : docs.length ? (
            <div className="space-y-2">
              <select
                id="source"
                value={docId}
                onChange={(e) => setDocId(e.target.value)}
                className="w-full rounded-lg border border-slate-200 bg-white p-3 text-sm"
              >
                {docs.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.originalFilename}
                  </option>
                ))}
              </select>
              <div className="flex items-center justify-between text-xs text-slate-500 pt-1">
                <span>Or select a local file:</span>
                <label className="cursor-pointer font-semibold text-teal-700 hover:underline">
                  <span>Upload local file</span>
                  <input
                    type="file"
                    className="hidden"
                    accept=".pdf,.docx,.xlsx,.xls,.csv,.txt,.md"
                    onChange={async (e) => {
                      const f = e.target.files?.[0];
                      if (!f) return;
                      try {
                        const res = await uploadDocument(f);
                        const newDoc: Document = {
                          id: res.id,
                          userId: "",
                          filename: res.filename,
                          originalFilename: f.name,
                          fileSize: f.size,
                          mimeType: f.type || "application/octet-stream",
                          pageCount: res.pageCount,
                          createdAt: new Date().toISOString(),
                        };
                        setDocs((prev) => [newDoc, ...prev]);
                        setDocId(newDoc.id);
                      } catch {
                        setError("Failed to upload local file.");
                      }
                    }}
                  />
                </label>
              </div>
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-teal-300 bg-teal-50/50 p-4 text-center">
              <p className="text-xs text-slate-600 mb-2">No documents in your drive yet.</p>
              <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg bg-teal-700 px-3 py-1.5 text-xs font-semibold text-white hover:bg-teal-800 transition">
                <FileText size={14} /> Upload local document
                <input
                  type="file"
                  className="hidden"
                  accept=".pdf,.docx,.xlsx,.xls,.csv,.txt,.md"
                  onChange={async (e) => {
                    const f = e.target.files?.[0];
                    if (!f) return;
                    try {
                      const res = await uploadDocument(f);
                      const newDoc: Document = {
                        id: res.id,
                        userId: "",
                        filename: res.filename,
                        originalFilename: f.name,
                        fileSize: f.size,
                        mimeType: f.type || "application/octet-stream",
                        pageCount: res.pageCount,
                        createdAt: new Date().toISOString(),
                      };
                      setDocs((prev) => [newDoc, ...prev]);
                      setDocId(newDoc.id);
                    } catch {
                      setError("Failed to upload local file.");
                    }
                  }}
                />
              </label>
            </div>
          )}
          {error && (
            <p role="alert" className="mt-3 text-xs text-rose-700">
              {error}
            </p>
          )}
          <Button
            onClick={start}
            disabled={!docId || busy || loading}
            className="mt-5 w-full gap-2"
          >
            {busy ? <Spinner size={16} /> : <Sparkles size={16} />}Open in chat
          </Button>
          <p className="mt-4 text-[10px] leading-5 text-slate-400">
            You review the prompt before sending it. Agents can search and read
            the selected document.
          </p>
        </section>
      </div>
    </div>
  );
}
