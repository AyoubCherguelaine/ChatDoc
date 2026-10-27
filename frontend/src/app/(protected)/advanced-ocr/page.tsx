"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Download, ScanText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { fetchDocuments, extractAdvancedOcr, type AdvancedOcrResult } from "@/lib/api";
import type { Document } from "@/lib/types";

export default function AdvancedOcrPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [documentId, setDocumentId] = useState("");
  const [start, setStart] = useState(1);
  const [end, setEnd] = useState(1);
  const [language, setLanguage] = useState<"auto" | "ar" | "en" | "mixed">("auto");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<AdvancedOcrResult | null>(null);
  const selected = documents.find((doc) => doc.id === documentId);
  const fieldClass = "mt-2 w-full rounded-lg border border-slate-300 bg-white p-3 text-sm disabled:opacity-50";

  useEffect(() => {
    let active = true;
    fetchDocuments().then((docs) => {
      if (active) setDocuments(docs.filter((doc) => /\.pdf$/i.test(doc.originalFilename)));
    }).catch((err: unknown) => {
      if (active) setError(err instanceof Error ? err.message : "Could not load documents");
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  async function run(event: React.FormEvent) {
    event.preventDefault();
    if (!selected || !Number.isInteger(start) || !Number.isInteger(end) || start < 1 || end < start || end > selected.pageCount || end - start + 1 > 50) {
      setError("Choose a valid page range of at most 50 pages.");
      return;
    }
    setBusy(true);
    setError("");
    setResult(null);
    try {
      setResult(await extractAdvancedOcr({ document_id: documentId, start_page: start, end_page: end, language }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "OCR extraction failed");
    } finally {
      setBusy(false);
    }
  }

  function download() {
    if (!result) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(result, null, 2)], { type: "application/json" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${result.filename.replace(/\.pdf$/i, "")}-blocks.json`;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return (
    <div className="mx-auto max-w-6xl space-y-8">
      <header>
        <ScanText className="mb-4 text-teal-700" size={28} />
        <h1 className="text-3xl font-semibold tracking-tight">Advanced OCR</h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-500">
          Extract meaningful blocks from PDF pages, including text, tables, formulas, and visual descriptions.
          Content adapts to your document, with links between blocks that continue onto the next page.
        </p>
      </header>
      <form onSubmit={run} className="space-y-5 rounded-2xl border border-slate-200 bg-white p-6">
        <label className="block text-sm font-medium">PDF document
          <select required disabled={loading || busy} value={documentId} className={fieldClass} onChange={(event) => {
            setDocumentId(event.target.value);
            setStart(1);
            setEnd(Math.min(documents.find((doc) => doc.id === event.target.value)?.pageCount || 1, 50));
            setResult(null);
            setError("");
          }}>
            <option value="">{loading ? "Loading documents…" : "Select a PDF"}</option>
            {documents.map((doc) => <option key={doc.id} value={doc.id}>{doc.originalFilename} ({doc.pageCount} pages)</option>)}
          </select>
        </label>
        {!loading && documents.length === 0 && <p className="text-sm text-slate-500">No PDFs available. <Link href="/drive?view=documents" className="text-teal-700 underline">Upload a PDF</Link> to get started.</p>}
        <div className="grid gap-5 sm:grid-cols-3">
          <label className="text-sm font-medium">Start page
            <input required disabled={busy} type="number" min={1} max={selected?.pageCount} value={start} onChange={(event) => setStart(Number(event.target.value))} className={fieldClass} />
          </label>
          <label className="text-sm font-medium">End page
            <input required disabled={busy} type="number" min={start} max={selected?.pageCount} value={end} onChange={(event) => setEnd(Number(event.target.value))} className={fieldClass} />
          </label>
          <label className="text-sm font-medium">Language
            <select disabled={busy} value={language} onChange={(event) => setLanguage(event.target.value as typeof language)} className={fieldClass}>
              <option value="auto">Auto detect</option><option value="ar">Arabic</option><option value="en">English</option><option value="mixed">Arabic &amp; English</option>
            </select>
          </label>
        </div>
        <p className="text-xs text-slate-500">Up to 50 pages per run. Extraction starts at the selected page. Visuals are described in the output.</p>
        <Button type="submit" disabled={busy || !selected} className="bg-teal-700 hover:bg-teal-800">{busy ? "Extracting pages…" : "Extract page blocks"}</Button>
        {busy && <p role="status" className="text-sm text-slate-500">Processing pages in order. This may take several minutes.</p>}
        {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      </form>
      {result && <section className="space-y-5" aria-label="OCR results">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div><h2 className="text-xl font-semibold">{result.filename}</h2><p className="mt-1 text-sm text-slate-500">{result.processed_pages} pages · {result.block_count} blocks</p></div>
          <Button variant="outline" onClick={download} leftIcon={<Download size={16} />}>Download JSON</Button>
        </div>
        {result.pages.map((page) => <article key={page.page_number} className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5">
          <h3 className="font-semibold">Page {page.page_number} <span className="text-sm font-normal text-slate-500">· {page.block_count} blocks</span></h3>
          {page.blocks.length === 0 && <p className="text-sm text-slate-500">No visible content on this page.</p>}
          {page.blocks.map((block) => <div key={block.id} className="rounded-xl border border-slate-100 bg-slate-50 p-4">
            <div className="flex flex-wrap gap-2 text-xs text-slate-500"><span className="font-semibold text-teal-800">{block.type}</span><span>{block.id}</span>{block.previous_block_id && <span>Continues {block.previous_block_id}</span>}</div>
            <pre dir="auto" className="mt-3 whitespace-pre-wrap break-words font-mono text-sm leading-6">{typeof block.content === "string" ? block.content : JSON.stringify(block.content, null, 2)}</pre>
            <details className="mt-3 text-sm text-slate-600"><summary className="cursor-pointer">OCR transcription</summary><pre dir="auto" className="mt-2 whitespace-pre-wrap break-words font-mono leading-6">{block.ocr_text || "No visible text in this block."}</pre></details>
            <details className="mt-3 text-xs text-slate-500"><summary className="cursor-pointer">All block fields</summary><pre className="mt-2 overflow-auto whitespace-pre-wrap break-words">{JSON.stringify(block, null, 2)}</pre></details>
          </div>)}
        </article>)}
      </section>}
    </div>
  );
}
