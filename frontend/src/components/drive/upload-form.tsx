"use client";
import { useState, useRef } from "react";
import { UploadCloud, FileText, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { uploadDocument, ApiError } from "@/lib/api";
import { formatBytes } from "@/lib/utils";
export function UploadForm({ onDone }: { onDone: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const select = (next: File | null) => {
    if (uploading) return;
    setError("");
    setFile(null);
    if (!next) return;
    if (!/\.(pdf|docx|xlsx|xls|csv|txt|md)$/i.test(next.name))
      return setError(
        "Choose a PDF, Word (.docx), Excel (.xlsx / .xls), CSV, TXT, or Markdown file.",
      );
    if (!next.size || next.size > 25 * 1024 * 1024)
      return setError("Choose a non-empty file up to 25 MB.");
    setFile(next);
  };
  const upload = async () => {
    if (!file) return;
    setUploading(true);
    setError("");
    try {
      await uploadDocument(file);
      setFile(null);
      onDone();
    } catch (e) {
      setError(
        e instanceof ApiError ? e.message : "Upload failed. Please try again.",
      );
    } finally {
      setUploading(false);
    }
  };
  return (
    <div>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          if (!uploading) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          select(e.dataTransfer.files[0] ?? null);
        }}
        className={`rounded-xl border-2 border-dashed p-8 text-center transition-colors ${dragging ? "border-emerald-500 bg-emerald-50 dark:border-emerald-500 dark:bg-emerald-950/40" : "border-slate-200 bg-white hover:border-emerald-400 dark:border-slate-800 dark:bg-[#121820]"}`}
      >
        <span className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-slate-50 text-emerald-700 shadow-sm dark:bg-slate-900 dark:text-emerald-400">
          <UploadCloud size={23} />
        </span>
        <p className="text-sm font-medium">A new file. A new perspective.</p>
        <p className="mt-2 text-xs leading-6 text-slate-500">
          Drop a document here, or{" "}
          <button
            disabled={uploading}
            onClick={() => input.current?.click()}
            className="font-semibold text-teal-700 underline underline-offset-4"
          >
            choose a file
          </button>
        </p>
        <input
          ref={input}
          aria-label="Choose document"
          type="file"
          accept=".pdf,.docx,.xlsx,.xls,.csv,.txt,.md"
          className="sr-only"
          disabled={uploading}
          onChange={(e) => select(e.target.files?.[0] ?? null)}
        />
        <p className="mt-4 text-[10px] text-slate-400">
          PDF · DOCX · XLSX · XLS · CSV · TXT · MD &nbsp; / &nbsp; Up to 25 MB
        </p>
      </div>
      {file && (
        <div className="mt-4 flex items-center gap-3 rounded-lg border border-slate-200 p-3">
          <FileText size={20} className="shrink-0 text-teal-700" />
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-medium">{file.name}</p>
            <p className="mt-1 text-[10px] text-slate-400">
              {formatBytes(file.size)}
            </p>
          </div>
          <CheckCircle2 size={17} className="text-teal-600" />
        </div>
      )}
      {error && (
        <p role="alert" className="mt-3 text-sm text-rose-700">
          {error}
        </p>
      )}
      <Button
        className="mt-4 w-full gap-2"
        disabled={!file || uploading}
        onClick={upload}
      >
        {uploading ? (
          <>
            <Spinner size={15} /> Reading and indexing…
          </>
        ) : (
          "Upload & process"
        )}
      </Button>
      {uploading && (
        <p className="mt-2 text-center text-xs text-slate-500" role="status">
          Extracting content and preparing your document for questions.
        </p>
      )}
    </div>
  );
}
