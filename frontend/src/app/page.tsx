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

const documentAIServices = [
  {
    title: "Invoice Processing",
    badge: "JSON Verified",
    description: "Extract line items, tax IDs, payment terms, and totals with math checks.",
    icon: Receipt,
    color: "bg-[#ecfdf5] text-[#059669]",
    tags: ["Vendor details", "Line items", "Totals check"],
  },
  {
    title: "Receipt & Expenses",
    badge: "Expense AI",
    description: "Parse store receipts, meal vouchers, travel expenses, tips, and categories.",
    icon: CreditCard,
    color: "bg-[#f0fdf4] text-[#16a34a]",
    tags: ["Merchant", "Tax breakdown", "Expense taxonomy"],
  },
  {
    title: "Contract Analysis",
    badge: "Risk Engine",
    description: "Identify signatories, terms, indemnification, liabilities, and risk clauses.",
    icon: FileSignature,
    color: "bg-[#eff6ff] text-[#2563eb]",
    tags: ["Parties", "Key clauses", "Risk alerts"],
  },
  {
    title: "PII & Compliance Audit",
    badge: "GDPR & HIPAA",
    description: "Detect sensitive PII, credential leaks, regulatory exposure, and preview redactions.",
    icon: ShieldAlert,
    color: "bg-[#fef2f2] text-[#dc2626]",
    tags: ["SSN & Card detection", "0-100 Risk score", "Masked preview"],
  },
  {
    title: "Resume & Talent Intelligence",
    badge: "Talent AI",
    description: "Candidate profiling, skills taxonomy, work history, and seniority assessment.",
    icon: UserCheck,
    color: "bg-[#f5f3ff] text-[#7c3aed]",
    tags: ["Skills taxonomy", "Career timeline", "Seniority level"],
  },
  {
    title: "Intelligent Form Parser",
    badge: "Form AI",
    description: "Extract form key-values, checkbox states ([X] / [ ]), and signatures.",
    icon: ClipboardCheck,
    color: "bg-[#fff7ed] text-[#ea580c]",
    tags: ["Key-values", "Checkbox detection", "Signature status"],
  },
  {
    title: "Google AI Multimodal",
    badge: "Multimodal",
    description: "Deep document understanding, layout parsing, entities, and complex reasoning.",
    icon: Bot,
    color: "bg-[#e8f0fe] text-[#1a73e8]",
    tags: ["Layout hierarchy", "Entity extraction", "Multimodal OCR"],
  },
  {
    title: "Deep Research & Citations",
    badge: "Grounded RAG",
    description: "Investigate claims, cross-reference pages, and verify facts with citations.",
    icon: SearchCheck,
    color: "bg-[#fdf4ff] text-[#c026d3]",
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
    <div className="bg-[#fcfdfb]">
      <header className="mx-auto flex h-24 max-w-[1280px] items-center justify-between px-6 lg:px-12">
        <Brand />
        <nav
          className="hidden gap-9 text-sm text-slate-600 md:flex"
          aria-label="Main navigation"
        >
          <a href="#workspace" className="hover:text-teal-700">
            The workspace
          </a>
          <a href="#services" className="hover:text-teal-700">
            AI Services
          </a>
          <a href="#features" className="hover:text-teal-700">
            Features
          </a>
          <a href="#how-it-works" className="hover:text-teal-700">
            How it works
          </a>
        </nav>
        <div className="flex items-center gap-5 text-sm font-medium">
          <Link href="/login" className="hidden sm:block">
            Log in
          </Link>
          <Link
            href="/login?mode=signup"
            className="flex items-center gap-2 rounded-lg bg-[#183a38] px-4 py-2.5 text-white hover:bg-teal-800"
          >
            Get started <ArrowUpRight size={16} />
          </Link>
        </div>
      </header>
      <main>
        <section className="marketing-grid relative overflow-hidden border-b border-[#e5ece6] px-6 pb-16 pt-12 lg:pb-24 lg:pt-20">
          <div className="mx-auto grid max-w-[1184px] items-center gap-14 lg:grid-cols-[1fr_1.04fr]">
            <div className="animate-enter">
              <div className="mb-7 inline-flex items-center gap-2 rounded-full border border-[#d8e8dc] bg-[#f1f7ed] px-3 py-1.5 text-xs font-medium text-[#467353]">
                <span className="h-1.5 w-1.5 rounded-full bg-[#6da66b]" /> A
                clearer way to work with documents <ArrowRight size={13} />
              </div>
              <h1 className="hero-display max-w-xl text-[clamp(3rem,5.5vw,5.1rem)] font-semibold">
                Your documents.
                <br />A world of
                <br />
                <span className="text-[#087f74]">answers.</span>
              </h1>
              <p className="mt-7 max-w-md text-lg leading-relaxed text-[#697b7d]">
                Less searching. More understanding. Turn your files into
                conversations, insights, and your next big idea.
              </p>
              <div className="mt-8 flex flex-wrap items-center gap-5">
                <Link
                  href="/login?mode=signup"
                  className="inline-flex items-center gap-5 rounded-lg bg-[#087f74] px-6 py-3.5 text-sm font-medium text-white shadow-lg shadow-teal-900/10 hover:bg-teal-800"
                >
                  Create your workspace <ArrowRight size={17} />
                </Link>
                <a
                  href="#workspace"
                  className="text-sm font-medium text-[#3d5b5b]"
                >
                  Explore the workspace <span aria-hidden="true">↗</span>
                </a>
              </div>
              <div className="mt-6 flex flex-wrap gap-5 text-xs text-[#758680]">
                <span className="flex gap-1.5">
                  <Check size={14} className="text-teal-700" /> PDF, Word &
                  Excel
                </span>
                <span className="flex gap-1.5">
                  <Check size={14} className="text-teal-700" /> Your files, in
                  context
                </span>
              </div>
            </div>
            <div id="workspace" className="relative animate-enter lg:py-10">
              <div className="absolute -inset-12 rounded-full bg-[#d9ecdb]/40 blur-3xl" />
              <div className="relative overflow-hidden rounded-2xl border border-[#d8e3dc] bg-white shadow-[0_24px_80px_-20px_#2c594533] lg:-rotate-1">
                <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3.5">
                  <div className="flex gap-1.5">
                    {[1, 2, 3].map((i) => (
                      <span
                        key={i}
                        className="h-2 w-2 rounded-full bg-slate-200"
                      />
                    ))}
                  </div>
                  <span className="text-[10px] text-slate-400">
                    Your knowledge workspace
                  </span>
                  <Layers size={13} className="text-teal-700" />
                </div>
                <div className="grid min-h-[370px] grid-cols-[130px_1fr] sm:grid-cols-[155px_1fr]">
                  <div className="border-r border-slate-100 bg-[#f8faf8] p-4">
                    <div className="mb-6 flex items-center gap-1.5 text-xs font-semibold">
                      <Layers size={15} className="text-teal-700" /> My
                      workspace
                    </div>
                    <div className="mb-5 rounded-md bg-[#e4f1eb] p-2 text-[10px] font-medium text-teal-800">
                      Documents <span className="float-right">3</span>
                    </div>
                    <p className="eyebrow !text-[8px]">Your sources</p>
                    {[
                      "Strategy report.pdf",
                      "Revenue.xlsx",
                      "Meeting notes.docx",
                    ].map((name, i) => (
                      <div
                        key={name}
                        className="mt-4 flex items-center gap-2 text-[9px] text-slate-500"
                      >
                        {i === 1 ? (
                          <FileSpreadsheet
                            size={13}
                            className="shrink-0 text-teal-700"
                          />
                        ) : (
                          <FileText
                            size={13}
                            className="shrink-0 text-orange-500"
                          />
                        )}
                        <span className="truncate">{name}</span>
                      </div>
                    ))}
                    <div className="mt-7 flex items-center gap-2 text-[9px] text-slate-400">
                      <Plus size={13} /> Add a source
                    </div>
                  </div>
                  <div className="p-5">
                    <div className="flex items-center gap-2 border-b border-slate-100 pb-4">
                      <Sparkles size={14} className="text-teal-700" />
                      <span className="text-xs font-semibold">
                        A little clarity, on demand.
                      </span>
                    </div>
                    <div className="ml-8 mt-5 rounded-xl rounded-br-sm bg-[#f0f4f3] p-3 text-[11px] leading-relaxed">
                      What should we focus on next quarter?
                    </div>
                    <div className="mt-5 flex gap-2">
                      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-teal-700 text-white">
                        <Sparkles size={13} />
                      </span>
                      <div>
                        <p className="text-[10px] font-semibold">
                          DOCTool{" "}
                          <span className="ml-1 font-normal text-slate-400">
                            Illustrative preview
                          </span>
                        </p>
                        <p className="mt-2 text-[11px] leading-relaxed text-slate-600">
                          Your strategy points to three priorities:
                        </p>
                        <div className="mt-3 space-y-2 text-[10px] text-slate-600">
                          <p>
                            01{" "}
                            <strong className="ml-2 text-slate-800">
                              Strengthen customer retention
                            </strong>
                          </p>
                          <p>
                            02{" "}
                            <strong className="ml-2 text-slate-800">
                              Invest in the core product
                            </strong>
                          </p>
                          <p>
                            03{" "}
                            <strong className="ml-2 text-slate-800">
                              Build a repeatable sales motion
                            </strong>
                          </p>
                        </div>
                        <span className="mt-3 inline-flex items-center gap-1 rounded bg-[#edf6ef] px-2 py-1 text-[9px] text-teal-800">
                          <Quote size={10} /> Strategy report · p. 12
                        </span>
                      </div>
                    </div>
                    <div className="mt-7 flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2.5 text-[10px] text-slate-400">
                      <span>Ask anything about your files…</span>
                      <ArrowUpRight size={16} className="text-teal-700" />
                    </div>
                  </div>
                </div>
              </div>
              <div className="relative -mt-4 ml-auto mr-4 flex w-fit items-center gap-3 rounded-xl border border-[#e1e8df] bg-[#fffffc] px-4 py-3 shadow-lg">
                <span className="rounded-full bg-[#edf5df] p-2 text-[#628b38]">
                  <Check size={16} />
                </span>
                <div>
                  <p className="text-xs font-semibold">
                    From information to insight.
                  </p>
                  <p className="mt-1 text-[10px] text-slate-500">
                    A little less busywork. A lot more clarity.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>
        <section className="mx-auto flex max-w-[1184px] flex-wrap items-center justify-between gap-6 border-b border-[#e7ebe5] px-6 py-8 text-sm text-[#7a8780]">
          <span className="text-xs font-medium">
            MADE FOR THE WAY YOU THINK
          </span>
          {[
            "Research & discovery",
            "Business & finance",
            "Learning & knowledge",
          ].map((x) => (
            <span key={x} className="flex items-center gap-2">
              <Check size={15} className="text-[#729476]" />
              {x}
            </span>
          ))}
        </section>
        <section id="services" className="mx-auto max-w-[1184px] px-6 py-24 border-b border-[#e7ebe5]">
          <div className="mb-12 flex flex-wrap items-end justify-between gap-5">
            <div>
              <p className="eyebrow">Enterprise Document AI Suite</p>
              <h2 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl text-slate-900">
                Specialized AI services for every document type.
              </h2>
            </div>
            <div className="flex flex-col items-start gap-3 sm:items-end">
              <p className="max-w-md text-sm leading-6 text-slate-500">
                Turn complex, unstructured files into structured, verified data with autonomous specialist agents.
              </p>
              <Link
                href="/services"
                className="inline-flex items-center gap-2 text-sm font-semibold text-teal-700 hover:text-teal-800"
              >
                Launch in Services Workspace <ArrowRight size={15} />
              </Link>
            </div>
          </div>

          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {documentAIServices.map(({ title, badge, description, icon: Icon, color, tags }) => (
              <div
                key={title}
                className="group flex flex-col justify-between rounded-2xl border border-[#e2e9e1] bg-white p-6 shadow-xs transition hover:-translate-y-1 hover:border-slate-300 hover:shadow-md"
              >
                <div>
                  <div className="mb-4 flex items-center justify-between">
                    <span className={`flex h-11 w-11 items-center justify-center rounded-xl transition group-hover:scale-105 ${color}`}>
                      <Icon size={22} />
                    </span>
                    <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-slate-600">
                      {badge}
                    </span>
                  </div>
                  <h3 className="text-base font-semibold text-slate-900 group-hover:text-teal-800 transition">
                    {title}
                  </h3>
                  <p className="mt-2 text-xs leading-5 text-slate-500">
                    {description}
                  </p>
                </div>

                <div className="mt-5 border-t border-slate-100 pt-3">
                  <div className="flex flex-wrap gap-1.5">
                    {tags.map((tag) => (
                      <span
                        key={tag}
                        className="rounded bg-slate-50 px-2 py-0.5 text-[10px] text-slate-500 border border-slate-100"
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
          <div className="mt-12 overflow-hidden rounded-2xl border border-teal-200 bg-gradient-to-r from-teal-900 via-[#183a38] to-slate-900 p-8 text-white shadow-xl">
            <div className="grid gap-6 md:grid-cols-12 md:items-center">
              <div className="md:col-span-8">
                <span className="inline-flex items-center gap-1.5 rounded-full bg-teal-800/80 px-3 py-1 text-xs font-semibold text-teal-200 border border-teal-700">
                  <Zap size={13} className="text-emerald-400" /> Free Trial Available Only
                </span>
                <h3 className="mt-3 text-2xl font-bold tracking-tight text-white">
                  1,200 Free Trial API Credits for Every Company
                </h3>
                <p className="mt-2 text-sm text-teal-100/90 leading-relaxed max-w-xl">
                  Test every Document AI capability with instant live API keys. Pay strictly by LLM compute usage — from 1 credit for conversational retrieval to 25 for verified invoices and 35 for contract risk analysis.
                </p>
                <div className="mt-4 flex flex-wrap gap-4 text-xs text-teal-200">
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
                  className="inline-flex items-center gap-2 rounded-lg bg-emerald-400 px-5 py-3 text-sm font-semibold text-slate-950 shadow-md hover:bg-emerald-300 transition"
                >
                  Claim 1,200 Free Credits <ArrowRight size={16} />
                </Link>
                <Link
                  href="/usage"
                  className="text-xs font-medium text-teal-200 hover:text-white transition"
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
              <h2 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">
                Big ideas start with a better question.
              </h2>
            </div>
            <p className="max-w-xs text-sm leading-6 text-slate-500">
              A thoughtful workspace for the files you read, the questions you
              ask, and the work that follows.
            </p>
          </div>
          <div className="grid gap-5 md:grid-cols-3">
            {features.map(({ icon: Icon, title, text }, i) => (
              <article
                key={title}
                className={`rounded-2xl border border-[#e2e9e1] p-7 ${i === 1 ? "bg-[#edf4eb]" : "bg-[#f6f8f2]"}`}
              >
                <div className="mb-10 flex items-center justify-between">
                  <span className="rounded-xl border border-white bg-white/80 p-3 text-teal-800">
                    <Icon size={23} />
                  </span>
                  <span className="text-xs text-slate-400">0{i + 1}</span>
                </div>
                <h3 className="text-lg font-semibold tracking-tight">
                  {title}
                </h3>
                <p className="mt-3 text-sm leading-7 text-[#6e7c75]">{text}</p>
              </article>
            ))}
          </div>
        </section>
        <section
          id="how-it-works"
          className="bg-[#153d37] px-6 py-20 text-white"
        >
          <div className="mx-auto max-w-[1136px]">
            <p className="eyebrow !text-[#9dc1ad]">A simpler workflow</p>
            <h2 className="mt-3 text-3xl font-medium tracking-tight">
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
                    <I size={22} className="mb-5 text-[#a0d5b3]" />
                    <h3 className="font-medium">{String(title)}</h3>
                    <p className="mt-3 max-w-xs text-sm leading-7 text-[#a8c1b8]">
                      {String(text)}
                    </p>
                  </div>
                );
              })}
            </div>
            <Link
              href="/login?mode=signup"
              className="mt-12 inline-flex items-center gap-6 rounded-lg bg-[#d5e8b9] px-5 py-3 text-sm font-semibold text-[#254332]"
            >
              Let’s make sense of it <ArrowRight size={16} />
            </Link>
          </div>
        </section>
      </main>
      <footer className="mx-auto flex max-w-[1280px] flex-wrap items-center justify-between gap-5 px-6 py-9 lg:px-12">
        <Brand />
        <p className="text-xs text-slate-500">
          A little clarity goes a long way.
        </p>
        <Link href="/login" className="text-sm text-slate-500">
          Open your workspace <ArrowUpRight className="ml-1 inline" size={14} />
        </Link>
      </footer>
    </div>
  );
}
