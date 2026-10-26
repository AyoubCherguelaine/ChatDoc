"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Sparkles,
  ArrowRight,
  FileText,
  Receipt,
  FileSignature,
  ListChecks,
  SearchCheck,
  FileSpreadsheet,
  Loader2,
  Bot,
  UserCheck,
  ShieldAlert,
  ClipboardCheck,
  CreditCard,
  Search,
  Key,
  Coins,
  Languages,
  ShieldBan,
  Tags,
  TrendingUp,
  AlertTriangle,
} from "lucide-react";
import { fetchDocuments, fetchCompanyAccount, type CompanyAccount } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { ServiceLauncherModal, type ServiceCardInfo } from "@/components/services/service-modal";
import type { Document } from "@/lib/types";
import Link from "next/link";

export type ServiceCategory = "all" | "bilingual" | "finance" | "legal" | "hr" | "extraction" | "general";

const services: ServiceCardInfo[] = [
  {
    id: "chat",
    title: "Document Chat",
    category: "general",
    description: "Ask questions and get answers grounded in your documents.",
    badge: "Interactive",
    credits: 5,
    llmTier: "Light / Retrieval",
    icon: <FileText size={28} />,
    workflowId: "actions",
    color: "bg-[#eef4e8] text-[#7a925b]",
    detail: "Conversational Q&A over any uploaded document with inline source citations.",
  },
  {
    id: "summary",
    title: "Executive Summary",
    category: "general",
    description: "Get a concise overview of your document's key points and takeaways.",
    badge: "Executive",
    credits: 10,
    llmTier: "Standard Summarizer",
    icon: <ListChecks size={28} />,
    workflowId: "summary",
    color: "bg-[#f0fdf4] text-[#16a34a]",
    detail: "Purpose, findings, core metrics, and recommended next steps in one brief.",
  },
  {
    id: "extraction",
    title: "Data Extraction",
    category: "extraction",
    description: "Pull tables, metrics, and numerical figures into structured Markdown.",
    badge: "Tabular",
    credits: 15,
    llmTier: "Structured Extraction",
    icon: <FileSpreadsheet size={28} />,
    workflowId: "extract",
    color: "bg-[#fff7ed] text-[#ea580c]",
    detail: "Convert buried details and unstructured tables into clean, citable tables.",
  },
  {
    id: "form_parser",
    title: "Intelligent Form Parser",
    category: "extraction",
    description: "Extract form key-values, checkbox states, selection groups, and signatures.",
    badge: "Form AI",
    credits: 20,
    llmTier: "Form Field & Signature",
    icon: <ClipboardCheck size={28} />,
    workflowId: "form_parser",
    color: "bg-[#fff7ed] text-[#ea580c]",
    detail: "Form fields, checkbox detection [X], and signatory status verification.",
  },
  {
    id: "receipt",
    title: "Receipt & Expenses",
    category: "finance",
    description: "Itemized receipts, tax breakdowns, tips, and financial math verification.",
    badge: "Expense AI",
    credits: 20,
    llmTier: "Receipt Vision & Math",
    icon: <CreditCard size={28} />,
    workflowId: "receipt",
    color: "bg-[#f0fdf4] text-[#16a34a]",
    detail: "Merchant metadata, currency, itemized products/services, and category taxonomy.",
  },
  {
    id: "invoice",
    title: "Invoice Processing",
    category: "finance",
    description: "Extract structured invoice data — line items, totals, taxes — as JSON.",
    badge: "JSON Verified",
    credits: 25,
    llmTier: "JSON Strict Schema",
    icon: <Receipt size={28} />,
    workflowId: "invoice",
    color: "bg-[#ecfdf5] text-[#059669]",
    detail: "Vendor, client, dates, amounts, payment terms — verified JSON output.",
  },
  {
    id: "resume",
    title: "Resume & Talent Intelligence",
    category: "hr",
    description: "Candidate profiling, skills taxonomy, work history, and seniority assessment.",
    badge: "Talent AI",
    credits: 25,
    llmTier: "Talent Classification",
    icon: <UserCheck size={28} />,
    workflowId: "resume",
    color: "bg-[#f5f3ff] text-[#7c3aed]",
    detail: "Skills matrix, experience timeline, education, and seniority score evaluation.",
  },
  {
    id: "compliance",
    title: "PII & Compliance Audit",
    category: "legal",
    description: "Detect sensitive PII, GDPR/HIPAA risks, and secret leaks with redaction guidance.",
    badge: "GDPR & HIPAA",
    credits: 30,
    llmTier: "Privacy & PII Audit",
    icon: <ShieldAlert size={28} />,
    workflowId: "compliance",
    color: "bg-[#fef2f2] text-[#dc2626]",
    detail: "Automated risk rating (0-100), PII enumeration, and sensitive data masking preview.",
  },
  {
    id: "contract",
    title: "Contract Analysis",
    category: "legal",
    description: "Identify parties, clauses, obligations, and flag risk factors.",
    badge: "Risk Engine",
    credits: 35,
    llmTier: "Legal Clause Analysis",
    icon: <FileSignature size={28} />,
    workflowId: "contract",
    color: "bg-[#eff6ff] text-[#2563eb]",
    detail: "Clause extraction, indemnification, termination, and key date alerts.",
  },
  {
    id: "google_ai",
    title: "Google AI Document",
    category: "general",
    description: "Multimodal document intelligence — layout hierarchy, entities, and tables.",
    badge: "Multimodal",
    credits: 40,
    llmTier: "Multimodal Heavy",
    icon: <Bot size={28} />,
    workflowId: "google_ai",
    color: "bg-[#e8f0fe] text-[#1a73e8]",
    detail: "Multimodal document understanding, layout parsing, key entities, and table extraction.",
  },
  {
    id: "research",
    title: "Deep Research",
    category: "general",
    description: "Investigate claims, cross-reference sections, and gather grounded evidence.",
    badge: "Grounded RAG",
    credits: 50,
    llmTier: "Multi-Step ReAct",
    icon: <SearchCheck size={28} />,
    workflowId: "research",
    color: "bg-[#eff6ff] text-[#6366f1]",
    detail: "Evidence-based answers with source page citations and fact-inference distinction.",
  },
  {
    id: "redaction",
    title: "PII & Tax Redaction (AR / EN)",
    category: "legal",
    description: "Mask Saudi National IDs, GCC IBANs, ZATCA Tax IDs, CRs, and sensitive contact info.",
    badge: "Bilingual PII",
    credits: 25,
    llmTier: "Bilingual Masking",
    icon: <ShieldBan size={28} />,
    workflowId: "redaction",
    color: "bg-[#fef2f2] text-[#dc2626]",
    detail: "Saudi National ID, GCC/KSA IBAN, ZATCA 15-digit VAT ID, CR, emails, phones masked with [REDACTED_...] tokens.",
  },
  {
    id: "classifier",
    title: "Document Classification & Routing",
    category: "extraction",
    description: "Categorize documents, detect language (EN/AR), urgency, and target department.",
    badge: "AR / EN Classifier",
    credits: 15,
    llmTier: "Classification & Lang",
    icon: <Tags size={28} />,
    workflowId: "classifier",
    color: "bg-[#f5f3ff] text-[#7c3aed]",
    detail: "Invoice, contract, financial statement, resume, CR, letter detection with confidence scores and routing.",
  },
  {
    id: "financial_statement",
    title: "Financial Statement Analysis",
    category: "finance",
    description: "Analyze Income Statement and Balance Sheet metrics and calculate key ratios.",
    badge: "Balance & P&L",
    credits: 35,
    llmTier: "Financial Ratio Engine",
    icon: <TrendingUp size={28} />,
    workflowId: "financial_statement",
    color: "bg-[#f0fdf4] text-[#16a34a]",
    detail: "Revenue, Gross Profit, EBIT, Net Income, Assets, Liabilities, Equity, and margins & solvency ratios.",
  },
  {
    id: "translation",
    title: "Bilingual Legal & Financial Translation",
    category: "general",
    description: "High-precision translation between Arabic and English preserving terminology.",
    badge: "AR ⇄ EN",
    credits: 30,
    llmTier: "Fidelity Translation",
    icon: <Languages size={28} />,
    workflowId: "translation",
    color: "bg-[#e8f0fe] text-[#1a73e8]",
    detail: "Bidirectional Arabic and English translation preserving legal terminology, tabular structure, and layout.",
  },
  {
    id: "anomaly_audit",
    title: "Anomaly & Tax Audit",
    category: "finance",
    description: "Audit invoice math, ZATCA 15% VAT compliance, and date chronology.",
    badge: "ZATCA 15% & Math",
    credits: 30,
    llmTier: "Audit & Compliance",
    icon: <AlertTriangle size={28} />,
    workflowId: "anomaly_audit",
    color: "bg-[#fffbeb] text-[#d97706]",
    detail: "Automated verification of invoice subtotal math, ZATCA 15% VAT accuracy, and due date chronological checks.",
  },
];

const categoryTabs: { id: ServiceCategory; label: string }[] = [
  { id: "all", label: "All Services" },
  { id: "bilingual", label: "EN & AR Bilingual" },
  { id: "finance", label: "Finance & Expenses" },
  { id: "legal", label: "Legal & Compliance" },
  { id: "hr", label: "HR & Talent" },
  { id: "extraction", label: "Forms & Tables" },
  { id: "general", label: "Research & Summaries" },
];

export default function ServicesPage() {
  const [docs, setDocs] = useState<Document[]>([]);
  const [account, setAccount] = useState<CompanyAccount | null>(null);
  const [activeCategory, setActiveCategory] = useState<ServiceCategory>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeServiceModal, setActiveServiceModal] = useState<ServiceCardInfo | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([fetchDocuments(), fetchCompanyAccount().catch(() => null)])
      .then(([d, acc]) => {
        if (active) {
          setDocs(d);
          if (acc) setAccount(acc);
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

  const filteredServices = useMemo(() => {
    return services.filter((svc) => {
      const matchesCategory =
        activeCategory === "all" ||
        svc.category === activeCategory ||
        (activeCategory === "bilingual" &&
          (svc.badge.toLowerCase().includes("ar") ||
            svc.badge.toLowerCase().includes("bilingual") ||
            svc.title.toLowerCase().includes("ar / en") ||
            svc.title.toLowerCase().includes("bilingual")));
      const query = searchQuery.toLowerCase().trim();
      const matchesQuery =
        !query ||
        svc.title.toLowerCase().includes(query) ||
        svc.description.toLowerCase().includes(query) ||
        svc.detail.toLowerCase().includes(query) ||
        svc.badge.toLowerCase().includes(query);
      return matchesCategory && matchesQuery;
    });
  }, [activeCategory, searchQuery]);

  if (loading) {
    return (
      <div className="py-12 text-center">
        <Spinner size={28} />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl animate-enter">
      {/* Header */}
      <div className="mb-8">
        <p className="eyebrow mb-2">Workspace / Services</p>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-[28px] font-semibold tracking-tight text-slate-900">
              Enterprise Document AI Suite
            </h1>
            <p className="mt-1 text-sm text-[#87959c]">
              Specialized Document AI agents for invoices, receipts, legal contracts, talent screening, compliance, and forms.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Link
              href="/usage"
              className="inline-flex items-center gap-1.5 rounded-full border border-teal-200 bg-teal-50 px-3 py-1 text-xs font-medium text-teal-800 hover:bg-teal-100 transition"
            >
              <Key size={13} className="text-teal-600" />
              <span>
                {account
                  ? `${account.remainingCredits.toLocaleString()} / 1,200 Credits Available`
                  : "1,200 Free Trial Credits"}
              </span>
            </Link>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-700">
              <Sparkles size={13} className="text-teal-600" /> {services.length} AI Services Active
            </span>
          </div>
        </div>
      </div>

      {/* Filter and Mode Bar */}
      <div className="mb-6 flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-xs sm:flex-row sm:items-center sm:justify-between">
        <div className="relative flex-1">
          <Search size={15} className="absolute left-3.5 top-3 text-slate-400" />
          <input
            id="search"
            type="text"
            placeholder="Search AI services by keyword, extraction field, or capability…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full rounded-xl border border-slate-200 bg-slate-50/50 py-2.5 pl-10 pr-3 text-xs text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-teal-600 focus:bg-white"
          />
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-500 font-medium">
          <span className="flex h-2 w-2 rounded-full bg-emerald-500" />
          <span>Independent Document Source: Choose local file or from drive per service</span>
        </div>
      </div>

      {/* Category Tabs */}
      <div className="mb-6 flex flex-wrap gap-2 border-b border-slate-200 pb-3">
        {categoryTabs.map((tab) => {
          const isActive = activeCategory === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveCategory(tab.id)}
              className={`rounded-lg px-3.5 py-1.5 text-xs font-medium transition ${
                isActive
                  ? "bg-slate-900 text-white shadow-xs"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200/70"
              }`}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      {error && (
        <div
          role="alert"
          className="mb-4 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700"
        >
          {error}
        </div>
      )}

      {/* Services Grid */}
      {filteredServices.length === 0 ? (
        <div className="rounded-xl border border-slate-200 bg-white p-12 text-center">
          <p className="text-sm font-medium text-slate-600">No services match your search or filter.</p>
          <button
            onClick={() => {
              setActiveCategory("all");
              setSearchQuery("");
            }}
            className="mt-3 text-xs font-semibold text-teal-600 hover:underline"
          >
            Clear filters
          </button>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filteredServices.map((svc) => (
            <div
              key={svc.id}
              className="group flex flex-col justify-between rounded-xl border border-slate-200 bg-white p-6 shadow-xs transition hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-md"
            >
              <div>
                <div className="mb-4 flex items-center justify-between">
                  <span
                    className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl shadow-xs transition group-hover:scale-105 ${svc.color}`}
                  >
                    {svc.icon}
                  </span>
                  <div className="flex flex-col items-end gap-1">
                    <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[10px] font-semibold tracking-wide text-slate-600 uppercase">
                      {svc.badge}
                    </span>
                    <span className="inline-flex items-center gap-1 rounded bg-teal-50 px-1.5 py-0.5 text-[10px] font-semibold text-teal-700 border border-teal-100">
                      <Coins size={10} /> {svc.credits} credits
                    </span>
                  </div>
                </div>

                <h2 className="text-base font-semibold text-slate-900 group-hover:text-teal-900 transition">
                  {svc.title}
                </h2>
                <div className="mt-1 flex items-center gap-2">
                  <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[9px] text-slate-500">
                    {svc.llmTier}
                  </span>
                </div>
                <p className="mt-1.5 text-xs leading-5 text-slate-600">
                  {svc.description}
                </p>
                <p className="mt-3 rounded-lg bg-slate-50 p-2.5 text-[11px] leading-relaxed text-slate-500 border border-slate-100">
                  {svc.detail}
                </p>
              </div>

              <Button
                onClick={() => setActiveServiceModal(svc)}
                className="mt-5 w-full justify-between group-hover:bg-teal-700 transition"
              >
                <span className="flex items-center gap-2">
                  <Sparkles size={15} /> Launch {svc.title}
                </span>
                <ArrowRight size={14} />
              </Button>
            </div>
          ))}
        </div>
      )}

      {/* Service Source Picker & Direct Runner Modal */}
      <ServiceLauncherModal
        service={activeServiceModal}
        open={Boolean(activeServiceModal)}
        onClose={() => setActiveServiceModal(null)}
        docs={docs}
        onDocumentAdded={(newDoc) => {
          setDocs((prev) => [newDoc, ...prev.filter((d) => d.id !== newDoc.id)]);
        }}
        remainingCredits={account?.remainingCredits}
      />
    </div>
  );
}
