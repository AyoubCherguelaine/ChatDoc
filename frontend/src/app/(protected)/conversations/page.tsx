"use client";

import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  MessageSquare,
  ArrowUpRight,
  Search,
  Plus,
  X,
  Upload,
  FileText,
  Zap,
  AlertCircle,
  ShieldCheck,
  Clock,
  Sparkles,
} from "lucide-react";
import {
  fetchSessions,
  uploadDocument,
  createSession,
  fetchCompanyAccount,
  type CompanyAccountInfo,
} from "@/lib/api";
import { Spinner } from "@/components/ui/spinner";
import type { ChatSession } from "@/lib/types";
import { formatDate } from "@/lib/utils";

export default function ConversationsPage() {
  const router = useRouter();

  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [account, setAccount] = useState<CompanyAccountInfo | null>(null);

  // New Chat Modal States
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [chatTitle, setChatTitle] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [modalError, setModalError] = useState("");
  const [isDragging, setIsDragging] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [allSessions, companyData] = await Promise.all([
          fetchSessions(),
          fetchCompanyAccount().catch(() => null),
        ]);
        if (active) {
          setSessions(allSessions);
          if (companyData) setAccount(companyData);
        }
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

  const handleOpenModal = () => {
    setSelectedFile(null);
    setChatTitle("");
    setModalError("");
    setIsModalOpen(true);
  };

  const handleCloseModal = () => {
    if (isUploading) return;
    setIsModalOpen(false);
    setSelectedFile(null);
    setChatTitle("");
    setModalError("");
  };

  const handleFileSelect = (file: File) => {
    setModalError("");
    const ext = file.name.split(".").pop()?.toLowerCase();
    const validExts = ["pdf", "docx", "xlsx", "xls", "csv", "txt", "md"];
    if (!ext || !validExts.includes(ext)) {
      setModalError("Please select a supported file (PDF, DOCX, XLSX, TXT, MD).");
      return;
    }
    if (file.size > 25 * 1024 * 1024) {
      setModalError("File size exceeds 25 MB limit.");
      return;
    }
    setSelectedFile(file);
    if (!chatTitle.trim()) {
      setChatTitle(`Chat: ${file.name.replace(/\.[^/.]+$/, "")}`);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) {
      handleFileSelect(file);
    }
  };

  const handleStartChat = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setModalError("Please choose a file to upload.");
      return;
    }

    const remainingCredits = account?.remainingCredits ?? 1200;
    if (remainingCredits < 1) {
      setModalError("Insufficient credits. Starting a chat requires at least 1 credit.");
      return;
    }

    setIsUploading(true);
    setModalError("");

    try {
      // Enforce max 3 pages limit on upload
      const uploadRes = await uploadDocument(selectedFile, { maxPages: 3 });

      // Create new chat session linked to this document
      const titleToUse = chatTitle.trim() || `Chat: ${uploadRes.filename}`;
      const sessionRes = await createSession(uploadRes.id, titleToUse);

      // Redirect immediately to the chat page
      setIsModalOpen(false);
      router.push(`/chat/${sessionRes.id}`);
    } catch (err: any) {
      setModalError(
        err.message ||
          "Failed to upload document or create chat session. Please verify it has at most 3 pages and try again."
      );
      setIsUploading(false);
    }
  };

  const remaining = account?.remainingCredits ?? 1200;

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      {/* Header with Title & Action Button */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="eyebrow">Workspace / Conversations</p>
          <h1 className="mt-1 text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900">
            Keep the conversation going.
          </h1>
          <p className="mt-1 text-xs sm:text-sm text-slate-500">
            Chat directly with your documents (max 3 pages per conversation).
          </p>
        </div>

        {/* NEW CHAT BUTTON */}
        <button
          onClick={handleOpenModal}
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-[#087f74] px-4 py-2.5 text-xs font-semibold text-white shadow-sm hover:bg-[#076c63] transition shrink-0 active:scale-95"
        >
          <Plus size={16} />
          <span>New Chat</span>
          <span className="ml-1 rounded bg-teal-800/80 px-1.5 py-0.5 text-[10px] font-mono text-teal-200">
            5 Credits
          </span>
        </button>
      </div>

      {/* Search Input Bar */}
      <div className="relative max-w-md">
        <Search size={16} className="absolute left-3.5 top-3 text-slate-400" />
        <input
          aria-label="Search conversations"
          placeholder="Find a conversation…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full rounded-xl border border-slate-200 bg-white py-2.5 pl-10 pr-4 text-xs shadow-2xs focus:border-teal-500 focus:outline-none"
        />
      </div>

      {error && (
        <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-xs text-rose-700">
          {error}
        </div>
      )}

      {/* Conversations List */}
      {loading ? (
        <div className="flex h-64 items-center justify-center">
          <Spinner size={24} />
        </div>
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
                className="surface flex items-center gap-4 p-4 sm:p-5 hover:!border-teal-300 transition group"
              >
                <span className="rounded-xl bg-teal-50 p-3 text-teal-700 group-hover:bg-teal-100 transition shadow-2xs">
                  <MessageSquare size={19} />
                </span>
                <div className="min-w-0 flex-1">
                  <h2 className="truncate text-sm font-semibold text-slate-800 group-hover:text-teal-900 transition">
                    {s.title}
                  </h2>
                  <p className="mt-1 text-xs text-slate-400">
                    {s.messageCount || 0} messages · Updated {formatDate(s.updatedAt)}
                  </p>
                </div>
                <ArrowUpRight size={18} className="text-slate-400 group-hover:text-teal-600 transition" />
              </Link>
            ))}
        </div>
      ) : (
        /* Empty State */
        <div className="surface p-10 text-center flex flex-col items-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-teal-50 text-teal-700 mb-4 shadow-2xs">
            <MessageSquare size={28} />
          </div>
          <h2 className="text-xl font-bold text-slate-900">
            Start your first document chat.
          </h2>
          <p className="mt-2 text-xs sm:text-sm text-slate-500 max-w-sm">
            Upload any document up to 3 pages and ask questions, extract insights, or summarize content with Luna.
          </p>
          <button
            onClick={handleOpenModal}
            className="mt-6 inline-flex items-center gap-2 rounded-xl bg-[#087f74] px-5 py-2.5 text-xs font-semibold text-white shadow-sm hover:bg-[#076c63] transition"
          >
            <Plus size={16} />
            <span>Upload Document &amp; Start Chat</span>
          </button>
        </div>
      )}

      {/* =========================================================================
          POPUP MODAL: UPLOAD FILE & START NEW CHAT (MAX 3 PAGES)
         ========================================================================= */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-4 backdrop-blur-xs animate-in fade-in duration-150">
          <div
            className="relative w-full max-w-lg overflow-hidden rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl animate-in zoom-in-95 duration-150 space-y-5"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="flex items-start justify-between border-b border-slate-100 pb-4">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-teal-50 text-teal-700 shadow-2xs">
                  <Upload size={18} />
                </div>
                <div>
                  <h3 className="text-base font-bold text-slate-900">
                    Start New Document Chat
                  </h3>
                  <p className="text-xs text-slate-500">
                    Upload a file (max 3 pages) to begin an interactive session.
                  </p>
                </div>
              </div>

              <button
                type="button"
                onClick={handleCloseModal}
                disabled={isUploading}
                aria-label="Close modal"
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition disabled:opacity-50"
              >
                <X size={18} />
              </button>
            </div>

            {/* Credit Quota & Cost Callout */}
            <div className="flex items-center justify-between rounded-xl border border-teal-200 bg-teal-50/60 p-3 text-xs">
              <div className="flex items-center gap-2 text-teal-900 font-medium">
                <Zap size={15} className="text-teal-600 fill-teal-600 shrink-0" />
                <span>
                  Balance: <strong className="font-bold">{remaining.toLocaleString()}</strong> credits
                </span>
              </div>
              <span className="rounded-md bg-teal-200/70 px-2 py-0.5 font-mono text-[11px] font-bold text-teal-800">
                1 Credit / Response
              </span>
            </div>

            {/* File Upload Zone */}
            <div className="space-y-2">
              <label className="block text-xs font-bold text-slate-700">
                Document File <span className="text-rose-500">*</span>
              </label>

              {!selectedFile ? (
                <div
                  onDragOver={(e) => {
                    e.preventDefault();
                    setIsDragging(true);
                  }}
                  onDragLeave={() => setIsDragging(false)}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                  className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-6 text-center cursor-pointer transition ${
                    isDragging
                      ? "border-teal-500 bg-teal-50/50"
                      : "border-slate-200 bg-slate-50/50 hover:bg-slate-50 hover:border-teal-400"
                  }`}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf,.docx,.xlsx,.xls,.csv,.txt,.md"
                    className="hidden"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) handleFileSelect(file);
                      e.target.value = "";
                    }}
                  />
                  <Upload size={24} className="text-teal-600 mb-2" />
                  <p className="text-xs font-semibold text-slate-700">
                    Click to browse or drag and drop your document
                  </p>
                  <p className="mt-1 text-[11px] text-slate-400">
                    PDF, DOCX, XLSX, TXT (up to 25 MB)
                  </p>
                  <div className="mt-2.5 inline-flex items-center gap-1 rounded bg-amber-100 px-2 py-0.5 text-[10px] font-bold text-amber-900">
                    <span>⚠️ Limit: 3 pages max</span>
                  </div>
                </div>
              ) : (
                <div className="flex items-center justify-between rounded-xl border border-teal-200 bg-teal-50/30 p-3 text-xs">
                  <div className="flex items-center gap-2.5 truncate">
                    <FileText size={18} className="text-teal-700 shrink-0" />
                    <div className="min-w-0">
                      <p className="truncate font-semibold text-slate-800">
                        {selectedFile.name}
                      </p>
                      <p className="text-[11px] text-slate-400">
                        {(selectedFile.size / 1024).toFixed(1)} KB • Max 3 pages limit
                      </p>
                    </div>
                  </div>
                  <button
                    type="button"
                    disabled={isUploading}
                    onClick={() => setSelectedFile(null)}
                    className="rounded p-1 text-slate-400 hover:bg-slate-200 hover:text-slate-600 transition"
                  >
                    <X size={15} />
                  </button>
                </div>
              )}
            </div>

            {/* Conversation Title (Optional) */}
            <div className="space-y-1.5">
              <label className="block text-xs font-bold text-slate-700">
                Conversation Title <span className="text-slate-400 font-normal">(optional)</span>
              </label>
              <input
                type="text"
                disabled={isUploading}
                value={chatTitle}
                onChange={(e) => setChatTitle(e.target.value)}
                placeholder="e.g. Invoice Q3 Review or Legal Clauses"
                className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-800 placeholder:text-slate-400 focus:border-teal-500 focus:outline-none"
              />
            </div>

            {/* 3 Pages Limit Notice */}
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-[11px] text-slate-500 leading-relaxed flex items-start gap-2">
              <ShieldCheck size={14} className="text-teal-600 shrink-0 mt-0.5" />
              <span>
                Conversations are strictly optimized for rapid interactive Q&amp;A on short documents (up to 3 pages). For 50+ page documents, please use <strong>Advanced OCR</strong>.
              </span>
            </div>

            {/* Error Message */}
            {modalError && (
              <div className="flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800">
                <AlertCircle size={15} className="shrink-0 text-rose-600 mt-0.5" />
                <span className="leading-snug">{modalError}</span>
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-slate-100">
              <button
                type="button"
                disabled={isUploading}
                onClick={handleCloseModal}
                className="rounded-xl border border-slate-200 px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50 transition disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={!selectedFile || isUploading || remaining < 1}
                onClick={handleStartChat}
                className="inline-flex items-center gap-2 rounded-xl bg-[#087f74] px-4 py-2 text-xs font-semibold text-white hover:bg-[#076c63] transition disabled:opacity-50 disabled:cursor-not-allowed shadow-xs"
              >
                {isUploading ? (
                  <>
                    <Spinner size={14} />
                    <span>Indexing Document…</span>
                  </>
                ) : (
                  <>
                    <Zap size={14} className="text-teal-200 fill-teal-200" />
                    <span>Start Chat &amp; Redirect</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
