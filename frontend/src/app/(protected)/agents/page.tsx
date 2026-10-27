"use client";
import { UPLOAD_LIMIT_LABEL } from "@/lib/upload-limits";

import { useEffect, useState, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  Sparkles,
  ArrowRight,
  FileText,
  Receipt,
  FileSignature,
  FileSpreadsheet,
  Bot,
  UserCheck,
  ShieldAlert,
  ClipboardCheck,
  Search,
  Languages,
  ShieldBan,
  Tags,
  TrendingUp,
  AlertTriangle,
  Upload,
  Layers,
  Code2,
  CheckCircle2,
  Cpu,
  FileCheck,
} from "lucide-react";
import { fetchDocuments, uploadDocument } from "@/lib/api";
import type { Document } from "@/lib/types";
import { Spinner } from "@/components/ui/spinner";

export interface AgentDefinition {
  id: string;
  name: string;
  category: "finance" | "legal" | "forms" | "analysis" | "hr" | "translation";
  badge: string;
  badgeColor: string;
  description: string;
  icon: typeof Sparkles;
  tags: string[];
  outputFormat: string;
}

const AGENTS: AgentDefinition[] = [
  {
    id: "invoice",
    name: "Invoice Processing Agent",
    category: "finance",
    badge: "Finance & Tax",
    badgeColor: "bg-emerald-50 text-emerald-700 border-emerald-200",
    description:
      "Extracts line items, quantities, unit prices, vendor/client metadata, and validates subtotal + tax = total arithmetic.",
    icon: Receipt,
    tags: ["Line items", "Tax ID", "Arithmetic check", "JSON Strict"],
    outputFormat: "Structured JSON",
  },
  {
    id: "receipt",
    name: "Receipt & Expense Agent",
    category: "finance",
    badge: "Expense AI",
    badgeColor: "bg-emerald-50 text-emerald-700 border-emerald-200",
    description:
      "Itemized receipts, payment methods, merchant metadata, currency, tips, and financial reconciliation.",
    icon: Receipt,
    tags: ["Itemized items", "Tip/Tax breakdown", "Merchant OCR", "Math check"],
    outputFormat: "Structured JSON",
  },
  {
    id: "financial_statement",
    name: "Financial Statement Analyst",
    category: "finance",
    badge: "Ratio Engine",
    badgeColor: "bg-emerald-50 text-emerald-700 border-emerald-200",
    description:
      "Parses Balance Sheets and P&L statements. Computes Gross Margin, Net Margin, and Debt-to-Equity ratios.",
    icon: TrendingUp,
    tags: ["Balance Sheet", "P&L", "Margins", "Solvency Ratios"],
    outputFormat: "Structured JSON",
  },
  {
    id: "anomaly_audit",
    name: "Anomaly & Tax Auditor",
    category: "finance",
    badge: "ZATCA 15% & Math",
    badgeColor: "bg-amber-50 text-amber-700 border-amber-200",
    description:
      "Audits invoice mathematical integrity, verifies ZATCA 15% VAT calculation, and detects chronological date anomalies.",
    icon: AlertTriangle,
    tags: ["ZATCA 15% VAT", "Math verification", "Date chronology", "Risk scoring"],
    outputFormat: "Audit Report JSON",
  },
  {
    id: "contract",
    name: "Contract Analysis Agent",
    category: "legal",
    badge: "Legal Intelligence",
    badgeColor: "bg-blue-50 text-blue-700 border-blue-200",
    description:
      "Identifies parties, term dates, termination clauses, indemnities, liability caps, and governing law risk vectors.",
    icon: FileSignature,
    tags: ["Parties", "Key clauses", "Indemnity", "Risk flags"],
    outputFormat: "Structured JSON",
  },
  {
    id: "compliance",
    name: "PII & Compliance Audit Agent",
    category: "legal",
    badge: "GDPR / HIPAA",
    badgeColor: "bg-rose-50 text-rose-700 border-rose-200",
    description:
      "Scans enterprise documents for PII exposures, sensitive credentials, and GDPR/HIPAA compliance vulnerabilities.",
    icon: ShieldAlert,
    tags: ["GDPR / HIPAA", "Sensitive PII", "Credentials leak", "Severity score"],
    outputFormat: "Compliance Audit JSON",
  },
  {
    id: "redaction",
    name: "PII & Tax Redaction Agent",
    category: "legal",
    badge: "AR / EN Masking",
    badgeColor: "bg-rose-50 text-rose-700 border-rose-200",
    description:
      "Deterministic and vision-assisted masking of Saudi National IDs, GCC IBANs, and ZATCA 15-digit VAT IDs in Arabic & English.",
    icon: ShieldBan,
    tags: ["Saudi National ID", "GCC IBAN", "ZATCA VAT ID", "Arabic & English"],
    outputFormat: "Redacted Text & Audit",
  },
  {
    id: "form_parser",
    name: "Intelligent Form Parser",
    category: "forms",
    badge: "Form AI",
    badgeColor: "bg-violet-50 text-violet-700 border-violet-200",
    description:
      "Extracts key-value field pairs, checkbox states [X] or [ ], signature blocks, and highlights missing mandatory entries.",
    icon: ClipboardCheck,
    tags: ["Key-Value pairs", "Checkboxes [X]", "Signatures", "Missing fields"],
    outputFormat: "Structured JSON",
  },
  {
    id: "extraction",
    name: "Table & Data Extraction Agent",
    category: "forms",
    badge: "Tabular & OCR",
    badgeColor: "bg-teal-50 text-teal-700 border-teal-200",
    description:
      "Extracts complex unstructured tables, numerical matrices, and key metrics into clean Markdown or JSON tables.",
    icon: FileSpreadsheet,
    tags: ["OCR Layout Blocks", "Markdown tables", "Numerical data", "Row citations"],
    outputFormat: "Markdown Tables / JSON",
  },
  {
    id: "resume",
    name: "Resume & Talent Intelligence",
    category: "hr",
    badge: "Talent AI",
    badgeColor: "bg-purple-50 text-purple-700 border-purple-200",
    description:
      "Extracts candidate profiles, technical/soft skills taxonomy, career progression, certifications, and seniority level.",
    icon: UserCheck,
    tags: ["Skills taxonomy", "Work history", "Seniority score", "Certifications"],
    outputFormat: "Candidate Profile JSON",
  },
  {
    id: "classifier",
    name: "Document Classifier & Router",
    category: "forms",
    badge: "Classification & Lang",
    badgeColor: "bg-indigo-50 text-indigo-700 border-indigo-200",
    description:
      "Categorizes documents (invoice, contract, financial statement, resume, CR), detects language (EN/AR), and sets routing.",
    icon: Tags,
    tags: ["Doc type", "Language (EN/AR)", "Urgency level", "Target department"],
    outputFormat: "Classification JSON",
  },
  {
    id: "translation",
    name: "Bilingual Translation Agent",
    category: "translation",
    badge: "AR ⇄ EN",
    badgeColor: "bg-sky-50 text-sky-700 border-sky-200",
    description:
      "High-fidelity translation between Arabic and English preserving legal and financial terminology and layout integrity.",
    icon: Languages,
    tags: ["Bilingual AR/EN", "Legal terminology", "Table preservation", "Alignment notes"],
    outputFormat: "Bilingual Document",
  },
  {
    id: "summary",
    name: "Executive Summary Agent",
    category: "analysis",
    badge: "Executive Brief",
    badgeColor: "bg-emerald-50 text-emerald-700 border-emerald-200",
    description:
      "Generates structured executive briefs covering purpose, key findings, core metrics, and strategic recommendations.",
    icon: FileText,
    tags: ["Executive brief", "Core metrics", "Key takeaways", "Action items"],
    outputFormat: "Structured Summary",
  },
  {
    id: "research",
    name: "Deep Research Agent",
    category: "analysis",
    badge: "Multi-Step Reasoner",
    badgeColor: "bg-blue-50 text-blue-700 border-blue-200",
    description:
      "Multi-step investigation across document sections, cross-referencing claims, evidence, and gaps with citations.",
    icon: Search,
    tags: ["Evidence audit", "Source citations", "Fact vs inference", "Cross-section"],
    outputFormat: "Research Brief",
  },
  {
    id: "google_ai",
    name: "Google AI Document Intelligence",
    category: "analysis",
    badge: "Multimodal AI",
    badgeColor: "bg-cyan-50 text-cyan-700 border-cyan-200",
    description:
      "Multimodal document layout analysis, structured entity extraction, and structural intelligence powered by Google AI.",
    icon: Cpu,
    tags: ["Multimodal vision", "Layout hierarchy", "Entity extraction", "Form fields"],
    outputFormat: "Multimodal Entities JSON",
  },
];

type CategoryFilter = "all" | "finance" | "legal" | "forms" | "analysis" | "hr" | "translation";

export default function AgentsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [docs, setDocs] = useState<Document[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<string>("");
  const [activeCategory, setActiveCategory] = useState<CategoryFilter>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadError, setUploadError] = useState<string>("");

  useEffect(() => {
    let active = true;
    fetchDocuments()
      .then((d) => {
        if (!active) return;
        setDocs(d);
        const queryDoc = searchParams?.get("doc");
        if (queryDoc && d.some((doc) => doc.id === queryDoc)) {
          setSelectedDocId(queryDoc);
        } else if (d.length > 0) {
          setSelectedDocId(d[0].id);
        }
      })
      .catch(() => {
        // Silent fallback
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [searchParams]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setIsUploading(true);
    setUploadError("");
    try {
      const res = await uploadDocument(file);
      const newDoc: Document = {
        id: res.id,
        userId: "",
        filename: res.filename,
        originalFilename: file.name,
        fileSize: file.size,
        mimeType: file.type || "application/octet-stream",
        pageCount: res.pageCount,
        createdAt: new Date().toISOString(),
      };
      setDocs((prev) => [newDoc, ...prev]);
      setSelectedDocId(newDoc.id);
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Failed to upload document. Please try again.");
    } finally {
      setIsUploading(false);
    }
  };

  const handleLaunchAgent = (agentId: string) => {
    const params = new URLSearchParams();
    params.set("service", agentId);
    if (selectedDocId) {
      params.set("doc", selectedDocId);
    }
    router.push(`/playground?${params.toString()}`);
  };

  const filteredAgents = useMemo(() => {
    return AGENTS.filter((agent) => {
      const matchesCategory =
        activeCategory === "all" || agent.category === activeCategory;
      const q = searchQuery.toLowerCase().trim();
      const matchesQuery =
        !q ||
        agent.name.toLowerCase().includes(q) ||
        agent.description.toLowerCase().includes(q) ||
        agent.tags.some((t) => t.toLowerCase().includes(q)) ||
        agent.badge.toLowerCase().includes(q);
      return matchesCategory && matchesQuery;
    });
  }, [activeCategory, searchQuery]);

  const selectedDoc = docs.find((d) => d.id === selectedDocId);

  return (
    <div className="mx-auto max-w-7xl animate-enter pb-16">
      {/* Header */}
      <div className="flex flex-col gap-4 border-b border-slate-200 pb-6 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-[11px] font-semibold tracking-wider text-teal-700 uppercase">
              WORKSPACE / SPECIALIST AGENTS
            </span>
            <span className="rounded bg-slate-100 px-2 py-0.5 font-mono text-[10px] text-slate-500">
              gpt-6-luna
            </span>
          </div>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900 md:text-3xl">
            Specialized Document AI Agents
          </h1>
          <p className="mt-2 text-xs leading-relaxed text-slate-600 md:text-sm">
            Autonomous domain specialists for high-accuracy extraction, layout parsing, and regulatory compliance.
            Click any agent to launch directly in the interactive sandbox playground.
          </p>
        </div>

        {/* Quick Playground link */}
        <div className="flex items-center gap-2">
          <Link
            href={selectedDocId ? `/playground?doc=${selectedDocId}` : "/playground"}
            className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-3.5 py-2 text-xs font-semibold text-white shadow-xs hover:bg-slate-800 transition"
          >
            <Sparkles size={14} className="text-teal-400" />
            <span>Open Playground</span>
            <ArrowRight size={13} />
          </Link>
        </div>
      </div>

      {/* Target Document & Filter Control Bar */}
      <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-4 shadow-2xs">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          {/* Target Document Selector */}
          <div className="flex flex-1 flex-col gap-2 sm:flex-row sm:items-center">
            <label
              htmlFor="agent-doc-select"
              className="flex items-center gap-1.5 whitespace-nowrap text-xs font-semibold text-slate-700"
            >
              <FileCheck size={14} className="text-teal-700" />
              <span>Target Document:</span>
            </label>

            {loading ? (
              <div className="flex items-center gap-2 text-xs text-slate-400">
                <Spinner size={14} /> Loading drive documents…
              </div>
            ) : docs.length > 0 ? (
              <div className="flex flex-1 items-center gap-2">
                <select
                  id="agent-doc-select"
                  value={selectedDocId}
                  onChange={(e) => setSelectedDocId(e.target.value)}
                  className="w-full max-w-md rounded-lg border border-slate-200 bg-slate-50/60 px-3 py-2 text-xs font-medium text-slate-800 outline-none transition focus:border-teal-600 focus:bg-white"
                >
                  {docs.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.originalFilename} ({d.pageCount} {d.pageCount === 1 ? "page" : "pages"})
                    </option>
                  ))}
                </select>

                <label className="inline-flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition shadow-2xs">
                  {isUploading ? <Spinner size={13} /> : <Upload size={13} className="text-slate-500" />}
                  <span>{isUploading ? "Uploading…" : "Upload PDF"}</span>
                  <input
                    type="file"
                    className="hidden"
                    accept=".pdf,.docx,.xlsx,.xls,.csv,.txt,.md"
                    disabled={isUploading}
                    onChange={handleFileUpload}
                  />
                </label>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-500">No documents in drive.</span>
                <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg bg-teal-700 px-3 py-1.5 text-xs font-semibold text-white hover:bg-teal-800 transition">
                  {isUploading ? <Spinner size={13} /> : <Upload size={13} />}
                  <span>Upload your first document</span>
                  <input
                    type="file"
                    className="hidden"
                    accept=".pdf,.docx,.xlsx,.xls,.csv,.txt,.md"
                    disabled={isUploading}
                    onChange={handleFileUpload}
                  />
                </label>
              </div>
            )}
          </div>

          <p className="text-xs text-slate-500">{UPLOAD_LIMIT_LABEL}</p>

          {/* Search agents input */}
          <div className="relative w-full lg:w-72">
            <Search size={14} className="absolute left-3 top-2.5 text-slate-400" />
            <input
              type="text"
              placeholder="Search agents or capabilities…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full rounded-lg border border-slate-200 bg-slate-50/50 py-2 pl-9 pr-3 text-xs text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-teal-600 focus:bg-white"
            />
          </div>
        </div>

        {uploadError && (
          <p className="mt-2 text-xs font-medium text-rose-600">{uploadError}</p>
        )}

        {/* Selected Document Badge Confirmation */}
        {selectedDoc && (
          <div className="mt-3 flex items-center gap-2 border-t border-slate-100 pt-3 text-[11px] text-slate-500">
            <span className="flex h-1.5 w-1.5 rounded-full bg-emerald-500" />
            <span>Active context:</span>
            <span className="font-semibold text-slate-700">{selectedDoc.originalFilename}</span>
            <span className="text-slate-400">·</span>
            <span className="text-slate-500">{selectedDoc.pageCount} pages</span>
            <span className="text-slate-400">·</span>
            <span className="text-slate-400">Clicking any agent will open the playground pre-loaded with this file.</span>
          </div>
        )}
      </div>

      {/* Category Filter Pills */}
      <div className="mt-6 flex flex-wrap items-center gap-2 border-b border-slate-200 pb-3">
        {(
          [
            { id: "all", label: "All Specialists", count: AGENTS.length },
            { id: "finance", label: "Finance & Tax", count: AGENTS.filter((a) => a.category === "finance").length },
            { id: "legal", label: "Legal & Compliance", count: AGENTS.filter((a) => a.category === "legal").length },
            { id: "forms", label: "Forms & Tables", count: AGENTS.filter((a) => a.category === "forms").length },
            { id: "analysis", label: "Analysis & Research", count: AGENTS.filter((a) => a.category === "analysis").length },
            { id: "hr", label: "HR & Talent", count: AGENTS.filter((a) => a.category === "hr").length },
            { id: "translation", label: "Bilingual Translation", count: AGENTS.filter((a) => a.category === "translation").length },
          ] as const
        ).map((tab) => {
          const isActive = activeCategory === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveCategory(tab.id)}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                isActive
                  ? "bg-slate-900 text-white shadow-2xs"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200/70"
              }`}
            >
              <span>{tab.label}</span>
              <span
                className={`rounded-full px-1.5 py-0.2 text-[10px] ${
                  isActive ? "bg-slate-700 text-slate-200" : "bg-slate-200/80 text-slate-600"
                }`}
              >
                {tab.count}
              </span>
            </button>
          );
        })}
      </div>

      {/* Agents Grid */}
      {filteredAgents.length === 0 ? (
        <div className="mt-8 rounded-2xl border border-slate-200 bg-white p-12 text-center">
          <Bot size={36} className="mx-auto text-slate-300" />
          <p className="mt-3 text-sm font-semibold text-slate-700">No agents match your criteria</p>
          <p className="mt-1 text-xs text-slate-500">Try clearing your search query or selecting a different category.</p>
          <button
            onClick={() => {
              setActiveCategory("all");
              setSearchQuery("");
            }}
            className="mt-4 rounded-lg bg-slate-100 px-3.5 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-200 transition"
          >
            Reset Filters
          </button>
        </div>
      ) : (
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filteredAgents.map((agent) => {
            const Icon = agent.icon;
            return (
              <div
                key={agent.id}
                onClick={() => handleLaunchAgent(agent.id)}
                className="group relative flex cursor-pointer flex-col justify-between rounded-xl border border-slate-200 bg-white p-5 shadow-2xs transition hover:-translate-y-0.5 hover:border-teal-500/80 hover:shadow-md"
              >
                <div>
                  {/* Top Bar with Icon, Badge & Model */}
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-slate-200 bg-slate-50 text-teal-800 transition group-hover:border-teal-500 group-hover:bg-teal-50/50">
                      <Icon size={20} />
                    </div>
                    <div className="flex flex-col items-end gap-1">
                      <span
                        className={`rounded-md border px-2 py-0.5 font-mono text-[10px] font-semibold uppercase ${agent.badgeColor}`}
                      >
                        {agent.badge}
                      </span>
                      <span className="font-mono text-[9px] text-slate-400">
                        {agent.outputFormat}
                      </span>
                    </div>
                  </div>

                  {/* Title & Description */}
                  <h3 className="mt-3.5 text-sm font-semibold text-slate-900 group-hover:text-teal-900 transition">
                    {agent.name}
                  </h3>
                  <p className="mt-1.5 text-xs leading-relaxed text-slate-600 line-clamp-3">
                    {agent.description}
                  </p>

                  {/* Capabilities Tags */}
                  <div className="mt-3.5 flex flex-wrap gap-1.5">
                    {agent.tags.map((tag) => (
                      <span
                        key={tag}
                        className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] text-slate-600"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Footer Action Bar: Redirect directly to Playground */}
                <div className="mt-5 flex items-center justify-between border-t border-slate-100 pt-3">
                  <span className="inline-flex items-center gap-1 text-[11px] font-medium text-slate-400 group-hover:text-slate-600 transition">
                    <Code2 size={13} />
                    <span>REST / Python</span>
                  </span>

                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleLaunchAgent(agent.id);
                    }}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-teal-50 px-3 py-1.5 text-xs font-semibold text-teal-800 border border-teal-200/80 group-hover:bg-teal-700 group-hover:text-white group-hover:border-teal-700 transition"
                  >
                    <span>Launch in Playground</span>
                    <ArrowRight size={13} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
