import Link from "next/link";
import {
  ArrowUpRight,
  ArrowRight,
  Check,
  FileText,
  FileSpreadsheet,
  Sparkles,
  ScanText,
  BookOpen,
  Bot,
  Layers,
  Quote,
  Search,
  Plus,
  Paperclip,
  Receipt,
  FileSignature,
  CreditCard,
  ShieldAlert,
  UserCheck,
  ClipboardCheck,
  SearchCheck,
  Zap,
} from "lucide-react";
import { Brand } from "@/components/brand";
import { ThemeToggle } from "@/components/ui/theme-toggle";

const documentAIServices = [
  {
    title: "Invoice Processing",
    badge: "JSON Verified",
    description: "Extract line items, tax IDs, payment terms, and totals with math checks.",
    icon: Receipt,
    color: "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-400",
    tags: ["Vendor details", "Line items", "Totals check"],
  },
  {
    title: "Receipt & Expenses",
    badge: "Expense AI",
    description: "Parse store receipts, meal vouchers, travel expenses, tips, and categories.",
    icon: CreditCard,
    color: "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-400",
    tags: ["Merchant", "Tax breakdown", "Expense taxonomy"],
  },
  {
    title: "Contract Analysis",
    badge: "Risk Engine",
    description: "Identify signatories, terms, indemnification, liabilities, and risk clauses.",
    icon: FileSignature,
    color: "bg-blue-50 text-blue-700 dark:bg-blue-950/50 dark:text-blue-400",
    tags: ["Parties", "Key clauses", "Risk alerts"],
  },
  {
    title: "PII & Compliance Audit",
    badge: "GDPR & HIPAA",
    description: "Detect sensitive PII, credential leaks, regulatory exposure, and preview redactions.",
    icon: ShieldAlert,
    color: "bg-rose-50 text-rose-700 dark:bg-rose-950/50 dark:text-rose-400",
    tags: ["SSN & Card detection", "0-100 Risk score", "Masked preview"],
  },
  {
    title: "Resume & Talent Intelligence",
    badge: "Talent AI",
    description: "Candidate profiling, skills taxonomy, work history, and seniority assessment.",
    icon: UserCheck,
    color: "bg-purple-50 text-purple-700 dark:bg-purple-950/50 dark:text-purple-400",
    tags: ["Skills taxonomy", "Career timeline", "Seniority level"],
  },
  {
    title: "Intelligent Form Parser",
    badge: "Form AI",
    description: "Extract form key-values, checkbox states ([X] / [ ]), and signatures.",
    icon: ClipboardCheck,
    color: "bg-amber-50 text-amber-700 dark:bg-amber-950/50 dark:text-amber-400",
    tags: ["Key-values", "Checkbox detection", "Signature status"],
  },
  {
    title: "Google AI Multimodal",
    badge: "Multimodal",
    description: "Deep document understanding, layout parsing, entities, and complex reasoning.",
    icon: Bot,
    color: "bg-cyan-50 text-cyan-700 dark:bg-cyan-950/50 dark:text-cyan-400",
    tags: ["Layout hierarchy", "Entity extraction", "Multimodal OCR"],
  },
  {
    title: "Deep Research & Citations",
    badge: "Grounded RAG",
    description: "Investigate claims, cross-reference pages, and verify facts with citations.",
    icon: SearchCheck,
    color: "bg-teal-50 text-teal-700 dark:bg-teal-950/50 dark:text-teal-400",
    tags: ["Hybrid search", "Page citations", "Evidence brief"],
  },
];

const features = [
  {
    icon: ScanText,
    title: "Every format. One workspace.",
    text: "Bring PDFs, Word documents, Excel workbooks, and CSVs together. Keep the context, lose the tab switching.",
  },
  {
    icon: Quote,
    title: "Answers you can trace.",
    text: "Move from a question to the source. Explore extracted pages and worksheet sections alongside your conversation.",
  },
  {
    icon: Bot,
    title: "Go a little deeper.",
    text: "Let the research agent search and read your document, or turn a dense report into an actionable brief.",
  },
];

export default function Home() {
  return (
    <div className="min-h-screen bg-white text-slate-900 dark:bg-[#090d12] dark:text-slate-100 transition-colors">
      <header className="mx-auto flex h-24 max-w-[1280px] items-center justify-between px-6 lg:px-12">
        <Brand />
        <nav
          className="hidden gap-9 text-sm text-slate-600 dark:text-slate-400 md:flex"
          aria-label="Main navigation"
        >
          <a href="#workspace" className="hover:text-emerald-600 dark:hover:text-emerald-400 transition-colors">
            The workspace
          </a>
          <a href="#services" className="hover:text-emerald-600 dark:hover:text-emerald-400 transition-colors">
            AI Services
          </a>
          <a href="#features" className="hover:text-emerald-600 dark:hover:text-emerald-400 transition-colors">
            Features
          </a>
          <a href="#how-it-works" className="hover:text-emerald-600 dark:hover:text-emerald-400 transition-colors">
            How it works
          </a>
        </nav>
        <div className="flex items-center gap-3 sm:gap-4 text-sm font-medium">
          <ThemeToggle />
          <Link href="/login" className="hidden sm:block text-slate-700 hover:text-emerald-600 dark:text-slate-300 dark:hover:text-emerald-400 transition-colors">
            Log in
          </Link>
          <Link
            href="/login?mode=signup"
            className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-teal-700 to-emerald-600 px-4 py-2.5 text-white shadow-sm hover:from-teal-800 hover:to-emerald-700 transition"
          >
            Get started <ArrowUpRight size={16} />
          </Link>
        </div>
      </header>

      <main>
        <section className="marketing-grid relative overflow-hidden border-b border-slate-200 px-6 pb-16 pt-12 lg:pb-24 lg:pt-20 dark:border-slate-800">
          <div className="mx-auto grid max-w-[1184px] items-center gap-14 lg:grid-cols-[1fr_1.04fr]">
            <div className="animate-enter">
              <div className="mb-7 inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3.5 py-1.5 text-xs font-semibold text-emerald-800 dark:border-emerald-800/60 dark:bg-emerald-950/40 dark:text-emerald-300">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                A clearer way to work with documents <ArrowRight size={13} />
              </div>
              <h1 className="hero-display max-w-xl text-[clamp(2.8rem,5.5vw,5rem)] font-extrabold text-slate-900 dark:text-white">
                Your documents.
                <br />A world of
                <br />
                <span className="bg-gradient-to-r from-teal-600 to-emerald-500 bg-clip-text text-transparent">
                  answers.
                </span>
              </h1>
              <p className="mt-7 max-w-md text-lg leading-relaxed text-slate-600 dark:text-slate-400">
                Less searching. More understanding. Turn your files into
                conversations, insights, and verified data.
              </p>
              <div className="mt-8 flex flex-wrap items-center gap-4">
                <Link
                  href="/login?mode=signup"
                  className="inline-flex items-center gap-3 rounded-xl bg-gradient-to-r from-teal-700 to-emerald-600 px-6 py-3.5 text-sm font-semibold text-white shadow-lg shadow-emerald-950/20 hover:from-teal-800 hover:to-emerald-700 transition"
                >
                  Create your workspace <ArrowRight size={17} />
                </Link>
                <a
                  href="#workspace"
                  className="text-sm font-semibold text-slate-700 hover:text-emerald-600 dark:text-slate-300 dark:hover:text-emerald-400 transition"
                >
                  Explore the workspace <span aria-hidden="true">↗</span>
                </a>
              </div>
              <div className="mt-6 flex flex-wrap gap-5 text-xs text-slate-500 dark:text-slate-400">
                <span className="flex items-center gap-1.5">
                  <Check size={14} className="text-emerald-600 dark:text-emerald-400" /> PDF, Word & Excel
                </span>
                <span className="flex items-center gap-1.5">
                  <Check size={14} className="text-emerald-600 dark:text-emerald-400" /> Grounded citations
                </span>
                <span className="flex items-center gap-1.5">
                  <Check size={14} className="text-emerald-600 dark:text-emerald-400" /> 100% Stateless & Private
                </span>
              </div>
            </div>

            <div id="workspace" className="relative animate-enter lg:py-10">
              <div className="absolute -inset-10 rounded-full bg-emerald-500/10 blur-3xl dark:bg-emerald-500/5 pointer-events-none" />
              <div className="relative overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xl lg:-rotate-1 dark:border-slate-800 dark:bg-[#121820] dark:shadow-2xl">
                <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3.5 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/40">
                  <div className="flex gap-1.5">
                    {[1, 2, 3].map((i) => (
                      <span
                        key={i}
                        className="h-2 w-2 rounded-full bg-slate-300 dark:bg-slate-700"
                      />
                    ))}
                  </div>
                  <span className="text-[10px] font-medium text-slate-400">
                    DOCTool Knowledge Studio
                  </span>
                  <Layers size={13} className="text-emerald-600 dark:text-emerald-400" />
                </div>
                <div className="grid min-h-[370px] grid-cols-[130px_1fr] sm:grid-cols-[155px_1fr]">
                  <div className="border-r border-slate-100 bg-slate-50 p-4 dark:border-slate-800 dark:bg-slate-900/60">
                    <div className="mb-6 flex items-center gap-1.5 text-xs font-bold text-slate-900 dark:text-slate-100">
                      <Layers size={15} className="text-emerald-600 dark:text-emerald-400" /> My workspace
                    </div>
                    <div className="mb-5 rounded-lg bg-emerald-50 border border-emerald-200 p-2 text-[10px] font-semibold text-emerald-800 dark:bg-emerald-950/40 dark:border-emerald-800/50 dark:text-emerald-300">
                      Documents <span className="float-right">3</span>
                    </div>
                    <p className="eyebrow !text-[8px] mb-3">Your sources</p>
                    {[
                      "Strategy report.pdf",
                      "Revenue.xlsx",
                      "Meeting notes.docx",
                    ].map((name, i) => (
                      <div
                        key={name}
                        className="mt-3 flex items-center gap-2 text-[9px] text-slate-600 dark:text-slate-400"
                      >
                        {i === 1 ? (
                          <FileSpreadsheet
                            size={13}
                            className="shrink-0 text-emerald-600 dark:text-emerald-400"
                          />
                        ) : (
                          <FileText
                            size={13}
                            className="shrink-0 text-amber-500"
                          />
                        )}
                        <span className="truncate">{name}</span>
                      </div>
                    ))}
                    <div className="mt-7 flex items-center gap-1.5 text-[9px] font-medium text-slate-400 dark:text-slate-500">
                      <Plus size={12} /> Add a source
                    </div>
                  </div>
                  <div className="p-5 flex flex-col justify-between">
                    <div>
                      <div className="flex items-center gap-2 border-b border-slate-100 pb-3 dark:border-slate-800">
                        <Sparkles size={14} className="text-emerald-600 dark:text-emerald-400" />
                        <span className="text-xs font-bold text-slate-900 dark:text-slate-100">
                          Instant Document Intelligence
                        </span>
                      </div>
                      <div className="ml-8 mt-4 rounded-xl rounded-br-xs bg-emerald-50/70 border border-emerald-100 p-3 text-[11px] leading-relaxed text-slate-800 dark:bg-emerald-950/40 dark:border-emerald-800/40 dark:text-emerald-100">
                        What should we focus on next quarter?
                      </div>
                      <div className="mt-4 flex gap-2.5">
                        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-emerald-600 text-white shadow-xs">
                          <Sparkles size={13} />
                        </span>
                        <div>
                          <p className="text-[10px] font-bold text-slate-900 dark:text-slate-100">
                            DOCTool Luna
                            <span className="ml-1 font-normal text-slate-400">
                              Illustrative preview
                            </span>
                          </p>
                          <p className="mt-1.5 text-[11px] leading-relaxed text-slate-600 dark:text-slate-300">
                            Your strategy document points to three key priorities:
                          </p>
                          <div className="mt-2.5 space-y-1.5 text-[10px] text-slate-600 dark:text-slate-300">
                            <p>
                              01{" "}
                              <strong className="ml-1 text-slate-900 dark:text-slate-100">
                                Strengthen customer retention
                              </strong>
                            </p>
                            <p>
                              02{" "}
                              <strong className="ml-1 text-slate-900 dark:text-slate-100">
                                Invest in the core product
                              </strong>
                            </p>
                            <p>
                              03{" "}
                              <strong className="ml-1 text-slate-900 dark:text-slate-100">
                                Build a repeatable sales motion
                              </strong>
                            </p>
                          </div>
                          <span className="mt-3 inline-flex items-center gap-1 rounded bg-emerald-50 border border-emerald-200 px-2 py-0.5 text-[9px] font-semibold text-emerald-800 dark:bg-emerald-950/60 dark:border-emerald-800/50 dark:text-emerald-300">
                            <Quote size={10} /> Strategy report · p. 12
                          </span>
                        </div>
                      </div>
                    </div>
                    <div className="mt-5 flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50/50 px-3.5 py-2.5 text-[10px] text-slate-400 dark:border-slate-800 dark:bg-slate-900/50 dark:text-slate-500">
                      <span>Ask anything about your files…</span>
                      <ArrowUpRight size={15} className="text-emerald-600 dark:text-emerald-400" />
                    </div>
                  </div>
                </div>
              </div>
              <div className="relative -mt-4 ml-auto mr-4 flex w-fit items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-lg dark:border-slate-800 dark:bg-slate-900">
                <span className="rounded-full bg-emerald-50 p-2 text-emerald-600 dark:bg-emerald-950/60 dark:text-emerald-400">
                  <Check size={16} />
                </span>
                <div>
                  <p className="text-xs font-bold text-slate-900 dark:text-slate-100">
                    From information to insight.
                  </p>
                  <p className="mt-0.5 text-[10px] text-slate-500 dark:text-slate-400">
                    A little less busywork. A lot more clarity.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="mx-auto flex max-w-[1184px] flex-wrap items-center justify-between gap-6 border-b border-slate-200 px-6 py-8 text-sm text-slate-600 dark:border-slate-800 dark:text-slate-400">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
            MADE FOR ENTERPRISE WORKFLOWS
          </span>
          {[
            "Research & discovery",
            "Business & finance",
            "Legal & compliance",
          ].map((x) => (
            <span key={x} className="flex items-center gap-2 font-medium">
              <Check size={15} className="text-emerald-600 dark:text-emerald-400" />
              {x}
            </span>
          ))}
        </section>

        <section id="services" className="mx-auto max-w-[1184px] px-6 py-24 border-b border-slate-200 dark:border-slate-800">
          <div className="mb-12 flex flex-wrap items-end justify-between gap-5">
            <div>
              <p className="eyebrow">Enterprise Document AI Suite</p>
              <h2 className="mt-3 text-3xl font-extrabold tracking-tight sm:text-4xl text-slate-900 dark:text-white">
                Specialized AI services for every document type.
              </h2>
            </div>
            <div className="flex flex-col items-start gap-3 sm:items-end">
              <p className="max-w-md text-sm leading-6 text-slate-600 dark:text-slate-400">
                Turn complex, unstructured files into structured, verified data with autonomous specialist agents.
              </p>
              <Link
                href="/services"
                className="inline-flex items-center gap-2 text-sm font-semibold text-emerald-700 hover:text-emerald-800 dark:text-emerald-400 dark:hover:text-emerald-300"
              >
                Launch in Services Workspace <ArrowRight size={15} />
              </Link>
            </div>
          </div>

          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {documentAIServices.map(({ title, badge, description, icon: Icon, color, tags }) => (
              <div
                key={title}
                className="group flex flex-col justify-between rounded-2xl border border-slate-200 bg-white p-6 shadow-xs transition hover:-translate-y-1 hover:border-emerald-500/50 hover:shadow-md dark:border-slate-800 dark:bg-[#121820]"
              >
                <div>
                  <div className="mb-4 flex items-center justify-between">
                    <span className={`flex h-11 w-11 items-center justify-center rounded-xl transition group-hover:scale-105 ${color}`}>
                      <Icon size={22} />
                    </span>
                    <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                      {badge}
                    </span>
                  </div>
                  <h3 className="text-base font-bold text-slate-900 group-hover:text-emerald-700 dark:text-slate-100 dark:group-hover:text-emerald-400 transition">
                    {title}
                  </h3>
                  <p className="mt-2 text-xs leading-5 text-slate-600 dark:text-slate-400">
                    {description}
                  </p>
                </div>

                <div className="mt-5 border-t border-slate-100 pt-3 dark:border-slate-800">
                  <div className="flex flex-wrap gap-1.5">
                    {tags.map((tag) => (
                      <span
                        key={tag}
                        className="rounded bg-slate-50 px-2 py-0.5 text-[10px] text-slate-600 border border-slate-200 dark:bg-slate-900 dark:text-slate-400 dark:border-slate-800"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Company API & Free Trial Banner */}
          <div className="mt-12 overflow-hidden rounded-2xl border border-emerald-500/30 bg-gradient-to-r from-slate-950 via-teal-950 to-slate-900 p-8 text-white shadow-xl">
            <div className="grid gap-6 md:grid-cols-12 md:items-center">
              <div className="md:col-span-8">
                <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-950/80 px-3 py-1 text-xs font-semibold text-emerald-300 border border-emerald-800/80">
                  <Zap size={13} className="text-emerald-400 fill-emerald-400" /> Free Trial Available
                </span>
                <h3 className="mt-3 text-2xl font-bold tracking-tight text-white">
                  1,200 Free Trial API Credits for Every Company
                </h3>
                <p className="mt-2 text-sm text-slate-300 leading-relaxed max-w-xl">
                  Test every Document AI capability with instant live API keys. Pay strictly by LLM compute usage — from 1 credit for conversational retrieval to 25 for verified invoices and 35 for contract risk analysis.
                </p>
                <div className="mt-4 flex flex-wrap gap-4 text-xs text-slate-300">
                  <span className="flex items-center gap-1.5">
                    <Check size={14} className="text-emerald-400" /> Instant API Key generation
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Check size={14} className="text-emerald-400" /> 1,200 initial credits included
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Check size={14} className="text-emerald-400" /> Zero credit card required
                  </span>
                </div>
              </div>
              <div className="md:col-span-4 flex flex-col sm:items-end gap-3">
                <Link
                  href="/login?mode=signup"
                  className="inline-flex items-center gap-2 rounded-xl bg-emerald-500 px-5 py-3 text-sm font-bold text-slate-950 shadow-md hover:bg-emerald-400 transition"
                >
                  Claim 1,200 Free Credits <ArrowRight size={16} />
                </Link>
                <Link
                  href="/docs"
                  className="text-xs font-medium text-emerald-300 hover:text-white transition"
                >
                  View API pricing & documentation ↗
                </Link>
              </div>
            </div>
          </div>
        </section>

        <section id="features" className="mx-auto max-w-[1184px] px-6 py-24">
          <div className="mb-12 flex flex-wrap items-end justify-between gap-5">
            <div>
              <p className="eyebrow">Less friction. More possibility.</p>
              <h2 className="mt-3 text-3xl font-extrabold tracking-tight sm:text-4xl text-slate-900 dark:text-white">
                Big ideas start with a better question.
              </h2>
            </div>
            <p className="max-w-xs text-sm leading-6 text-slate-600 dark:text-slate-400">
              A thoughtful workspace for the files you read, the questions you
              ask, and the work that follows.
            </p>
          </div>
          <div className="grid gap-5 md:grid-cols-3">
            {features.map(({ icon: Icon, title, text }, i) => (
              <article
                key={title}
                className="rounded-2xl border border-slate-200 bg-white p-7 shadow-xs transition hover:border-emerald-500/50 hover:shadow-md dark:border-slate-800 dark:bg-[#121820]"
              >
                <div className="mb-10 flex items-center justify-between">
                  <span className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-emerald-700 dark:border-slate-800 dark:bg-slate-900 dark:text-emerald-400">
                    <Icon size={23} />
                  </span>
                  <span className="text-xs font-semibold text-slate-400">0{i + 1}</span>
                </div>
                <h3 className="text-lg font-bold tracking-tight text-slate-900 dark:text-white">
                  {title}
                </h3>
                <p className="mt-3 text-sm leading-7 text-slate-600 dark:text-slate-400">{text}</p>
              </article>
            ))}
          </div>
        </section>

        <section
          id="how-it-works"
          className="border-t border-slate-800 bg-[#070b10] px-6 py-20 text-white"
        >
          <div className="mx-auto max-w-[1136px]">
            <p className="eyebrow !text-emerald-400">A simpler workflow</p>
            <h2 className="mt-3 text-3xl font-extrabold tracking-tight">
              Bring your files. Find your next step.
            </h2>
            <div className="mt-12 grid gap-10 md:grid-cols-3">
              {[
                [
                  Paperclip,
                  "01 / Bring your knowledge",
                  "Upload a report, a workbook, or your meeting notes.",
                ],
                [
                  Search,
                  "02 / Ask a better question",
                  "Find key details, summarize, or investigate with an agent.",
                ],
                [
                  BookOpen,
                  "03 / Make it useful",
                  "Review the source, keep the conversation, and export your findings.",
                ],
              ].map(([Icon, title, text]) => {
                const I = Icon as typeof Paperclip;
                return (
                  <div key={String(title)}>
                    <I size={22} className="mb-5 text-emerald-400" />
                    <h3 className="font-bold text-slate-100">{String(title)}</h3>
                    <p className="mt-3 max-w-xs text-sm leading-7 text-slate-400">
                      {String(text)}
                    </p>
                  </div>
                );
              })}
            </div>
            <Link
              href="/login?mode=signup"
              className="mt-12 inline-flex items-center gap-3 rounded-xl bg-gradient-to-r from-teal-500 to-emerald-500 px-6 py-3.5 text-sm font-bold text-slate-950 shadow-lg shadow-emerald-500/20 hover:from-teal-400 hover:to-emerald-400 transition"
            >
              Let’s make sense of it <ArrowRight size={16} />
            </Link>
          </div>
        </section>
      </main>

      <footer className="mx-auto flex max-w-[1280px] flex-wrap items-center justify-between gap-5 px-6 py-9 lg:px-12 border-t border-slate-200 dark:border-slate-800">
        <Brand />
        <p className="text-xs text-slate-500 dark:text-slate-400">
          A little clarity goes a long way.
        </p>
        <Link href="/login" className="text-sm font-semibold text-slate-600 hover:text-emerald-600 dark:text-slate-400 dark:hover:text-emerald-400 transition">
          Open your workspace <ArrowUpRight className="ml-1 inline" size={14} />
        </Link>
      </footer>
    </div>
  );
}
