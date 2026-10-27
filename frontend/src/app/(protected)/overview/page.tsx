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
  ArrowRight,
  ShieldCheck,
  Sparkles,
  Code2,
  CheckCircle2,
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
      color: "bg-emerald-50 text-emerald-800 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800/50",
      iconBg: "bg-gradient-to-tr from-teal-700 to-emerald-600 text-white",
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
      color: "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-800/50",
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
      color: "bg-emerald-50 text-emerald-800 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800/50",
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
      title: "Contract Risk & Liabilities",
      tag: "Legal Compliance",
      description:
        "Deep clause auditing for indemnity provisions, limitation of liability, non-compete terms, termination conditions, and cross-border regulatory exposure.",
      icon: FileSignature,
      color: "bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-950/40 dark:text-purple-300 dark:border-purple-800/50",
      iconBg: "bg-purple-600 text-white",
      href: "/services",
      cta: "Run Contract Audit",
      highlights: [
        "Party identification & jurisdictions",
        "Termination & breach covenants",
        "Indemnity & damage cap checks",
        "0-100 clause risk scoring",
      ],
    },
    {
      title: "PII & Compliance Auditing",
      tag: "GDPR & HIPAA",
      description:
        "Identify sensitive Personally Identifiable Information including national IDs, payment cards, credentials, and tax records with zero permanent retention.",
      icon: ShieldAlert,
      color: "bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800/50",
      iconBg: "bg-rose-600 text-white",
      href: "/services",
      cta: "Audit Compliance",
      highlights: [
        "SSN, National ID & Card detection",
        "Automated character redactions",
        "Data privacy compliance score",
        "Full audit trail logs",
      ],
    },
    {
      title: "Form & Table Field Parser",
      tag: "Structured Key-Values",
      description:
        "Extract dense application form fields, checkboxes, and signatures with spatial layout understanding into clean normalized JSON records.",
      icon: ClipboardCheck,
      color: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800/50",
      iconBg: "bg-amber-600 text-white",
      href: "/services",
      cta: "Parse Form Fields",
      highlights: [
        "Checkbox [X] vs [ ] classification",
        "Spatial key-value pairing",
        "Signature detection & verification",
        "Form taxonomy normalization",
      ],
    },
  ];

  return (
    <div className="mx-auto max-w-6xl space-y-8 animate-in fade-in duration-300 text-slate-900 dark:text-slate-100">
      {/* =========================================================================
          HERO & PLATFORM MISSION BANNER
         ========================================================================= */}
      <div className="relative overflow-hidden rounded-2xl border border-slate-200 bg-gradient-to-br from-white via-slate-50/50 to-emerald-50/30 p-6 sm:p-8 shadow-xs dark:border-slate-800 dark:from-[#121820] dark:via-[#0f151d] dark:to-emerald-950/20">
        <div className="relative z-10 flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="max-w-2xl space-y-3">
            <div className="inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50/80 px-3 py-1 text-xs font-semibold text-emerald-800 shadow-2xs dark:border-emerald-800/60 dark:bg-emerald-950/40 dark:text-emerald-300">
              <Sparkles size={13} className="text-emerald-600 dark:text-emerald-400" />
              <span>DOCTool Enterprise Document AI</span>
              <span className="text-emerald-300 dark:text-emerald-700">•</span>
              <span className="font-normal text-emerald-700 dark:text-emerald-400">Platform Overview</span>
            </div>

            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900 dark:text-white">
              Transform Unstructured Documents into Structured Intelligence
            </h1>

            <p className="text-sm sm:text-base text-slate-600 dark:text-slate-300 leading-relaxed">
              DOCTool is an enterprise-grade document intelligence platform that combines
              deep neural OCR, specialized AI reasoning microservices, and interactive
              grounded conversations — all operating on a <strong>100% stateless engine</strong> with
              zero permanent data retention.
            </p>

            <div className="flex flex-wrap items-center gap-3 pt-2">
              <Link
                href="/conversations"
                className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-teal-700 to-emerald-600 px-4 py-2.5 text-xs sm:text-sm font-semibold text-white shadow-xs hover:from-teal-800 hover:to-emerald-700 transition"
              >
                <MessageSquare size={16} />
                <span>Start Document Chat</span>
                <ArrowRight size={14} />
              </Link>

              <Link
                href="/advanced-ocr"
                className="inline-flex items-center gap-2 rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-xs sm:text-sm font-semibold text-slate-700 shadow-2xs hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700 transition"
              >
                <ScanText size={16} className="text-emerald-600 dark:text-emerald-400" />
                <span>Run Advanced OCR</span>
              </Link>

              <Link
                href="/services"
                className="inline-flex items-center gap-2 rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-xs sm:text-sm font-semibold text-slate-700 shadow-2xs hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700 transition"
              >
                <Bot size={16} className="text-emerald-600 dark:text-emerald-400" />
                <span>AI Services Catalog</span>
              </Link>
            </div>
          </div>

          {/* Quick Account / Quota Badge */}
          <div className="rounded-xl border border-slate-200 bg-white p-4 sm:p-5 shadow-xs lg:w-72 space-y-3 dark:border-slate-800 dark:bg-[#121820]">
            <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-2.5">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                Workspace Quota
              </span>
              <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] font-bold text-emerald-800 dark:bg-emerald-900/60 dark:text-emerald-300">
                {account?.planTier || "Active"}
              </span>
            </div>

            <div>
              <div className="flex items-baseline justify-between">
                <span className="text-2xl font-black text-slate-900 dark:text-white">
                  {remaining.toLocaleString()}
                </span>
                <span className="text-xs font-medium text-slate-500 dark:text-slate-400">Credits Remaining</span>
              </div>
              <p className="mt-1 text-[11px] text-slate-400 dark:text-slate-500 truncate">
                Organization:{" "}
                <span className="font-semibold text-slate-700 dark:text-slate-300">
                  {account?.companyName || user?.name || "DOCTool Workspace"}
                </span>
              </p>
            </div>

            <div className="flex items-center justify-between pt-1">
              <Link
                href="/usage"
                className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700 dark:text-emerald-400 hover:underline"
              >
                <History size={12} />
                <span>View usage history</span>
              </Link>
              <Link
                href="/playground"
                className="inline-flex items-center gap-1 text-[11px] font-semibold text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200"
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
          <h2 className="text-lg font-bold text-slate-900 dark:text-white">How DOCTool Works</h2>
          <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400">
            From raw, messy documents to clean, verified intelligence in four seamless steps.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-2 dark:border-slate-800 dark:bg-[#121820]">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-50 text-emerald-800 font-bold text-xs dark:bg-emerald-950/60 dark:text-emerald-300">
              01
            </div>
            <h3 className="text-sm font-bold text-slate-900 dark:text-white">Ephemeral Ingestion</h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
              Upload PDFs, scans, DOCX, or spreadsheets. Files are held in volatile memory with TTL
              expiry and never written to permanent disks.
            </p>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-2 dark:border-slate-800 dark:bg-[#121820]">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-50 text-blue-700 font-bold text-xs dark:bg-blue-950/60 dark:text-blue-300">
              02
            </div>
            <h3 className="text-sm font-bold text-slate-900 dark:text-white">Multilingual OCR</h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
              Neural OCR processes Arabic RTL orientation, bilingual text, multi-column articles, and
              converts tables into clean Markdown.
            </p>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-2 dark:border-slate-800 dark:bg-[#121820]">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-50 text-emerald-800 font-bold text-xs dark:bg-emerald-950/60 dark:text-emerald-300">
              03
            </div>
            <h3 className="text-sm font-bold text-slate-900 dark:text-white">Specialized AI Agents</h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
              Domain microservices extract verified JSON schemas for invoices, contracts, receipts,
              resumes, and compliance audits with math checks.
            </p>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-2 dark:border-slate-800 dark:bg-[#121820]">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-purple-50 text-purple-700 font-bold text-xs dark:bg-purple-950/60 dark:text-purple-300">
              04
            </div>
            <h3 className="text-sm font-bold text-slate-900 dark:text-white">Grounded Citations</h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
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
            <h2 className="text-lg font-bold text-slate-900 dark:text-white">Main Platform Services</h2>
            <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400">
              Purpose-built tools tailored for enterprise document workflows.
            </p>
          </div>
          <Link
            href="/services"
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-700 dark:text-emerald-400 hover:underline"
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
                className="flex flex-col justify-between rounded-xl border border-slate-200 bg-white p-5 shadow-xs transition hover:border-emerald-500/50 hover:shadow-sm dark:border-slate-800 dark:bg-[#121820]"
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
                    <h3 className="text-base font-bold text-slate-900 dark:text-white">{service.title}</h3>
                    <p className="mt-1 text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
                      {service.description}
                    </p>
                  </div>

                  <div className="border-t border-slate-100 dark:border-slate-800 pt-3 space-y-1.5">
                    {service.highlights.map((h, i) => (
                      <div key={i} className="flex items-center gap-2 text-[11px] text-slate-600 dark:text-slate-400">
                        <CheckCircle2 size={12} className="text-emerald-600 dark:text-emerald-400 shrink-0" />
                        <span>{h}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="pt-4 mt-4 border-t border-slate-100 dark:border-slate-800">
                  <Link
                    href={service.href}
                    className="inline-flex w-full items-center justify-center gap-1.5 rounded-lg bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-emerald-50 hover:text-emerald-800 transition dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-emerald-950/50 dark:hover:text-emerald-300"
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
      <div className="rounded-xl border border-slate-800 bg-slate-950 p-6 text-white shadow-sm">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="flex items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-500/20 text-emerald-400">
              <ShieldCheck size={22} />
            </span>
            <div className="space-y-1">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <span>Enterprise Privacy & Stateless Architecture Guarantee</span>
                <span className="rounded bg-emerald-500/20 px-2 py-0.5 font-mono text-[10px] text-emerald-300">
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
              className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-500 px-3.5 py-2 text-xs font-bold text-slate-950 hover:bg-emerald-400 transition shadow-xs"
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
