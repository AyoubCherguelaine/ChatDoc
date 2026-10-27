"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ScanText,
  MessageSquare,
  Bot,
  Receipt,
  FileSignature,
  ShieldAlert,
  ClipboardCheck,
  CreditCard,
  UserCheck,
  Zap,
  ArrowRight,
  ShieldCheck,
  Layers,
  Sparkles,
  Lock,
  Code2,
  FileCheck2,
  CheckCircle2,
  Server,
  Cpu,
  History,
} from "lucide-react";
import { fetchCompanyAccount, type CompanyAccountInfo } from "@/lib/api";
import { useSession } from "@/components/providers/session-provider";

export default function OverviewPage() {
  const { user } = useSession();
  const [account, setAccount] = useState<CompanyAccountInfo | null>(null);

  useEffect(() => {
    let active = true;
    fetchCompanyAccount()
      .then((data) => {
        if (active) setAccount(data);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);

  const remaining = account?.remainingCredits ?? 1200;

  const coreServices = [
    {
      title: "Advanced Multilingual OCR",
      tag: "Markdown & Layout",
      description:
        "High-fidelity OCR engine optimized for complex Arabic (RTL), bilingual documents, dense data tables, and mathematical formulas. Preserves original reading order and outputs structured Markdown and layout blocks.",
      icon: ScanText,
      color: "bg-teal-50 text-teal-700 border-teal-200",
      iconBg: "bg-teal-600 text-white",
      href: "/advanced-ocr",
      cta: "Launch OCR Studio",
      highlights: [
        "Arabic RTL & bilingual support",
        "Dense table to Markdown conversion",
        "Mathematical formula & equation capture",
        "Semantic block coordinates & JSON export",
      ],
    },
    {
      title: "Chats & Grounded RAG",
      tag: "Interactive Citations",
      description:
        "Multi-turn conversational intelligence over uploaded documents. Ask complex cross-document questions, extract evidence, and verify answers with verifiable page and line citations.",
      icon: MessageSquare,
      color: "bg-blue-50 text-blue-700 border-blue-200",
      iconBg: "bg-blue-600 text-white",
      href: "/conversations",
      cta: "Open Document Chats",
      highlights: [
        "Interactive Q&A with citations",
        "Cross-page evidence verification",
        "Hybrid semantic & vector retrieval",
        "Multi-document synthesis",
      ],
    },
    {
      title: "Invoice & Financial Intelligence",
      tag: "Verified JSON",
      description:
        "Extract vendor details, invoice numbers, line-item itemization, tax identification, and payment terms with automated mathematical verification.",
      icon: Receipt,
      color: "bg-emerald-50 text-emerald-700 border-emerald-200",
      iconBg: "bg-emerald-600 text-white",
      href: "/services",
      cta: "Explore Financial Services",
      highlights: [
        "Vendor & client tax ID extraction",
        "Itemized line-item arrays",
        "Math & VAT consistency checks",
        "Structured JSON schema export",
      ],
    },
    {
      title: "Contract Risk & Compliance",
      tag: "Legal Risk Engine",
      description:
        "Deconstruct contracts to identify signatories, term lengths, liability limits, indemnification clauses, and generate automated 0-100 risk assessments.",
      icon: FileSignature,
      color: "bg-amber-50 text-amber-800 border-amber-200",
      iconBg: "bg-amber-600 text-white",
      href: "/services",
      cta: "Analyze Legal Contracts",
      highlights: [
        "Key clauses & liability limits",
        "Signatory & party identification",
        "Automated risk scoring (0-100)",
        "Expiration & termination alerts",
      ],
    },
    {
      title: "PII & Regulatory Audit",
      tag: "GDPR & HIPAA",
      description:
        "Automatically scan documents for sensitive personal data (SSNs, emails, phone numbers, credentials) and preview confidential data masking.",
      icon: ShieldAlert,
      color: "bg-rose-50 text-rose-700 border-rose-200",
      iconBg: "bg-rose-600 text-white",
      href: "/services",
      cta: "Run Compliance Audit",
      highlights: [
        "Automated PII detection & categorization",
        "Masked redaction preview",
        "GDPR & HIPAA exposure rating",
        "Audit-ready compliance reports",
      ],
    },
    {
      title: "Intelligent Form Parser",
      tag: "Form AI",
      description:
        "Extract key-value pairs, checkbox states ([X] vs [ ]), selection groups, and signature locations from structured forms and surveys.",
      icon: ClipboardCheck,
      color: "bg-purple-50 text-purple-700 border-purple-200",
      iconBg: "bg-purple-600 text-white",
      href: "/services",
      cta: "Parse Structured Forms",
      highlights: [
        "Field key-value pair extraction",
        "Checkbox & radio button detection",
        "Signatory status verification",
        "Tabular form layout mapping",
      ],
    },
  ];

  return (
    <div className="mx-auto max-w-6xl space-y-8 animate-in fade-in duration-300">
      {/* =========================================================================
          HERO & PLATFORM MISSION BANNER
         ========================================================================= */}
      <div className="relative overflow-hidden rounded-2xl border border-slate-200 bg-gradient-to-br from-white via-slate-50/50 to-teal-50/30 p-6 sm:p-8 shadow-xs">
        <div className="relative z-10 flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="max-w-2xl space-y-3">
            <div className="inline-flex items-center gap-2 rounded-full border border-teal-200 bg-teal-50/80 px-3 py-1 text-xs font-semibold text-teal-800 shadow-2xs">
              <Sparkles size={13} className="text-teal-600" />
              <span>DOCTool Enterprise Document AI</span>
              <span className="text-teal-300">•</span>
              <span className="font-normal text-teal-700">Platform Overview</span>
            </div>

            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900">
              Transform Unstructured Documents into Structured Intelligence
            </h1>

            <p className="text-sm sm:text-base text-slate-600 leading-relaxed">
              DOCTool is an enterprise-grade document intelligence platform that combines
              deep neural OCR, specialized AI reasoning microservices, and interactive
              grounded conversations — all operating on a <strong>100% stateless engine</strong> with
              zero permanent data retention.
            </p>

            <div className="flex flex-wrap items-center gap-3 pt-2">
              <Link
                href="/conversations"
                className="inline-flex items-center gap-2 rounded-xl bg-[#087f74] px-4 py-2.5 text-xs sm:text-sm font-semibold text-white shadow-xs hover:bg-[#06675e] transition"
              >
                <MessageSquare size={16} />
                <span>Start Document Chat</span>
                <ArrowRight size={14} />
              </Link>

              <Link
                href="/advanced-ocr"
                className="inline-flex items-center gap-2 rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-xs sm:text-sm font-semibold text-slate-700 shadow-2xs hover:bg-slate-50 transition"
              >
                <ScanText size={16} className="text-teal-700" />
                <span>Run Advanced OCR</span>
              </Link>

              <Link
                href="/services"
                className="inline-flex items-center gap-2 rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-xs sm:text-sm font-semibold text-slate-700 shadow-2xs hover:bg-slate-50 transition"
              >
                <Bot size={16} className="text-teal-700" />
                <span>AI Services Catalog</span>
              </Link>
            </div>
          </div>

          {/* Quick Account / Quota Badge */}
          <div className="rounded-xl border border-slate-200 bg-white p-4 sm:p-5 shadow-xs lg:w-72 space-y-3">
            <div className="flex items-center justify-between border-b border-slate-100 pb-2.5">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                Workspace Quota
              </span>
              <span className="rounded bg-teal-100 px-1.5 py-0.5 text-[10px] font-bold text-teal-800">
                {account?.planTier || "Active"}
              </span>
            </div>

            <div>
              <div className="flex items-baseline justify-between">
                <span className="text-2xl font-black text-slate-900">
                  {remaining.toLocaleString()}
                </span>
                <span className="text-xs font-medium text-slate-500">Credits Remaining</span>
              </div>
              <p className="mt-1 text-[11px] text-slate-400 truncate">
                Organization:{" "}
                <span className="font-semibold text-slate-700">
                  {account?.companyName || user?.name || "DOCTool Workspace"}
                </span>
              </p>
            </div>

            <div className="flex items-center justify-between pt-1">
              <Link
                href="/usage"
                className="inline-flex items-center gap-1 text-[11px] font-semibold text-teal-700 hover:underline"
              >
                <History size={12} />
                <span>View usage history</span>
              </Link>
              <Link
                href="/playground"
                className="inline-flex items-center gap-1 text-[11px] font-semibold text-slate-600 hover:text-slate-900"
              >
                <Code2 size={12} />
                <span>API Sandbox</span>
              </Link>
            </div>
          </div>
        </div>
      </div>

      {/* =========================================================================
          WHAT OUR PLATFORM DOES (THE 4-PILLAR ARCHITECTURE)
         ========================================================================= */}
      <div className="space-y-4">
        <div>
          <h2 className="text-lg font-bold text-slate-900">How DOCTool Works</h2>
          <p className="text-xs sm:text-sm text-slate-500">
            From raw, messy documents to clean, verified intelligence in four seamless steps.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal-50 text-teal-700 font-bold text-xs">
              01
            </div>
            <h3 className="text-sm font-bold text-slate-900">Ephemeral Ingestion</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              Upload PDFs, scans, DOCX, or spreadsheets. Files are held in volatile memory with TTL
              expiry and never written to permanent disks.
            </p>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-50 text-blue-700 font-bold text-xs">
              02
            </div>
            <h3 className="text-sm font-bold text-slate-900">Multilingual OCR</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              Neural OCR processes Arabic RTL orientation, bilingual text, multi-column articles, and
              converts tables into clean Markdown.
            </p>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700 font-bold text-xs">
              03
            </div>
            <h3 className="text-sm font-bold text-slate-900">Specialized AI Agents</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              Domain microservices extract verified JSON schemas for invoices, contracts, receipts,
              resumes, and compliance audits with math checks.
            </p>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-purple-50 text-purple-700 font-bold text-xs">
              04
            </div>
            <h3 className="text-sm font-bold text-slate-900">Grounded Citations</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              Multi-turn document chats provide conversational answers backed by exact page and line
              source references for full traceability.
            </p>
          </div>
        </div>
      </div>

      {/* =========================================================================
          MAIN SERVICES EXPLAINED (CORE PLATFORM CAPABILITIES)
         ========================================================================= */}
      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <div>
            <h2 className="text-lg font-bold text-slate-900">Main Platform Services</h2>
            <p className="text-xs sm:text-sm text-slate-500">
              Purpose-built tools tailored for enterprise document workflows.
            </p>
          </div>
          <Link
            href="/services"
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-teal-700 hover:underline"
          >
            <span>View all 12+ microservices</span>
            <ArrowRight size={13} />
          </Link>
        </div>

        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3">
          {coreServices.map((service) => {
            const Icon = service.icon;
            return (
              <div
                key={service.title}
                className="flex flex-col justify-between rounded-xl border border-slate-200 bg-white p-5 shadow-xs transition hover:border-teal-300 hover:shadow-sm"
              >
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className={`flex h-10 w-10 items-center justify-center rounded-xl ${service.iconBg}`}>
                      <Icon size={20} />
                    </span>
                    <span className={`rounded-md border px-2 py-0.5 text-[10px] font-semibold ${service.color}`}>
                      {service.tag}
                    </span>
                  </div>

                  <div>
                    <h3 className="text-base font-bold text-slate-900">{service.title}</h3>
                    <p className="mt-1 text-xs text-slate-600 leading-relaxed">
                      {service.description}
                    </p>
                  </div>

                  <div className="border-t border-slate-100 pt-3 space-y-1.5">
                    {service.highlights.map((h, i) => (
                      <div key={i} className="flex items-center gap-2 text-[11px] text-slate-600">
                        <CheckCircle2 size={12} className="text-teal-600 shrink-0" />
                        <span>{h}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="pt-4 mt-4 border-t border-slate-100">
                  <Link
                    href={service.href}
                    className="inline-flex w-full items-center justify-center gap-1.5 rounded-lg bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-teal-50 hover:text-teal-800 transition"
                  >
                    <span>{service.cta}</span>
                    <ArrowRight size={12} />
                  </Link>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* =========================================================================
          SECURITY & PRIVACY GUARANTEE BANNER
         ========================================================================= */}
      <div className="rounded-xl border border-slate-200 bg-slate-900 p-6 text-white shadow-sm">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="flex items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-teal-500/20 text-teal-400">
              <ShieldCheck size={22} />
            </span>
            <div className="space-y-1">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <span>Enterprise Privacy & Stateless Architecture Guarantee</span>
                <span className="rounded bg-teal-500/20 px-2 py-0.5 font-mono text-[10px] text-teal-300">
                  Zero Data Retention
                </span>
              </h3>
              <p className="text-xs text-slate-300 leading-relaxed max-w-2xl">
                DOCTool processes customer documents strictly in-memory or transient storage with an
                automated 10-minute inactivity cleanup. No customer files or vector databases are
                ever used to train models or stored permanently on disk.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <Link
              href="/playground"
              className="inline-flex items-center gap-1.5 rounded-lg bg-teal-600 px-3.5 py-2 text-xs font-semibold text-white hover:bg-teal-500 transition shadow-xs"
            >
              <Code2 size={14} />
              <span>Developer API Sandbox</span>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

