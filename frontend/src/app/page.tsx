"use client";

import Link from "next/link";
import {
  ArrowRight,
  FileText,
  MessageSquare,
  ScanText,
  Check,
  Upload,
  Table2,
} from "lucide-react";
import { Brand } from "@/components/brand";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { LanguageToggle } from "@/components/ui/language-toggle";
import { useLanguage } from "@/components/providers/language-provider";
import { ServiceCatalog } from "@/components/services/service-catalog";

export default function Home() {
  const { t } = useLanguage();
  return (
    <div className="min-h-screen bg-white text-slate-900 dark:bg-[#090d12] dark:text-slate-100">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:bg-white focus:p-4 focus:text-slate-900"
      >
        {t("Skip to content", "انتقل إلى المحتوى")}
      </a>
      <header className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-5 py-5 sm:px-8">
        <Brand />
        <nav
          aria-label={t("Main navigation", "التنقل الرئيسي")}
          className="order-3 flex w-full justify-center gap-6 border-t border-slate-100 pt-4 text-sm text-slate-600 dark:border-slate-800 dark:text-slate-300 md:order-none md:w-auto md:border-0 md:pt-0"
        >
          <a
            href="#features"
            className="hover:text-emerald-700 dark:hover:text-emerald-400"
          >
            {t("Platform", "المنصة")}
          </a>
          <a
            href="#services"
            className="hover:text-emerald-700 dark:hover:text-emerald-400"
          >
            {t("Services", "الخدمات")}
          </a>
          <a
            href="#how-it-works"
            className="hover:text-emerald-700 dark:hover:text-emerald-400"
          >
            {t("How it works", "طريقة الاستخدام")}
          </a>
        </nav>
        <div className="flex items-center gap-2 sm:gap-3">
          <LanguageToggle />
          <ThemeToggle />
          <Link
            href="/login"
            className="rounded-lg bg-emerald-700 px-3 py-2 text-sm font-semibold text-white hover:bg-emerald-800"
          >
            {t("Log in", "تسجيل الدخول")}
          </Link>
        </div>
      </header>
      <main id="main">
        <section className="marketing-grid border-y border-slate-200 dark:border-slate-800">
          <div className="mx-auto grid max-w-6xl items-center gap-10 px-5 py-14 sm:px-8 sm:py-20 lg:grid-cols-2 lg:gap-16">
            <div>
              <p className="eyebrow mb-5">
                {t(
                  "Document processing workspace",
                  "مساحة عمل لمعالجة المستندات",
                )}
              </p>
              <h1 className="text-4xl font-bold leading-tight tracking-tight sm:text-5xl lg:text-[3.5rem]">
                {t(
                  "Read, search and extract data from your documents.",
                  "اقرأ مستنداتك وابحث فيها واستخرج بياناتها.",
                )}
              </h1>
              <p className="mt-6 max-w-xl text-base leading-8 text-slate-600 dark:text-slate-400">
                {t(
                  "Upload a PDF, Word document or spreadsheet. Ask questions about its contents, read text from scanned pages, or extract details from invoices, contracts and forms.",
                  "ارفع ملف PDF أو مستند Word أو جدول بيانات. اطرح أسئلة حول محتواه، أو استخرج النص من الصفحات الممسوحة ضوئيًا، أو استخرج تفاصيل الفواتير والعقود والنماذج.",
                )}
              </p>
              <div className="mt-7 flex flex-wrap items-center gap-4">
                <Link
                  href="/login?mode=signup"
                  className="inline-flex items-center gap-2 rounded-xl bg-emerald-700 px-5 py-3 text-sm font-semibold text-white hover:bg-emerald-800"
                >
                  {t("Create an account", "إنشاء حساب")}
                  <ArrowRight size={17} className="rtl:rotate-180" />
                </Link>
                <a
                  href="#services"
                  className="rounded-lg px-2 py-3 text-sm font-semibold text-emerald-700 hover:underline dark:text-emerald-400"
                >
                  {t("Browse services", "تصفح الخدمات")}
                </a>
              </div>
              <ul className="mt-6 flex flex-wrap gap-x-5 gap-y-2 text-xs text-slate-600 dark:text-slate-400">
                {[
                  t("PDF, Word, Excel & CSV", "PDF وWord وExcel وCSV"),
                  t("Arabic & English", "العربية والإنجليزية"),
                  t("Workspace & API access", "واجهة استخدام وAPI"),
                ].map((label) => (
                  <li key={label} className="flex items-center gap-1.5">
                    <Check size={14} className="text-emerald-600" />
                    {label}
                  </li>
                ))}
              </ul>
            </div>
            <div className="surface overflow-hidden shadow-lg">
              <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50 px-5 py-4 dark:border-slate-800 dark:bg-slate-900">
                <span className="text-sm font-semibold">
                  {t("Invoice processing", "معالجة الفواتير")}
                </span>
                <span className="text-xs text-slate-500 dark:text-slate-400">
                  {t("Example result", "مثال على النتيجة")}
                </span>
              </div>
              <div className="space-y-6 p-5 sm:p-7">
                <div className="flex items-center gap-3 rounded-xl border border-slate-200 p-4 dark:border-slate-700">
                  <FileText
                    size={26}
                    className="shrink-0 text-emerald-700 dark:text-emerald-400"
                  />
                  <div>
                    <p className="text-sm font-semibold" dir="ltr">
                      invoice-2026.pdf
                    </p>
                    <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                      {t(
                        "1 page · Sample document",
                        "صفحة واحدة · مستند توضيحي",
                      )}
                    </p>
                  </div>
                </div>
                <div>
                  <p className="mb-3 text-sm font-semibold">
                    {t("Extracted fields", "الحقول المستخرجة")}
                  </p>
                  <dl className="divide-y divide-slate-100 text-sm dark:divide-slate-800">
                    {[
                      [
                        t("Supplier", "المورد"),
                        t("Example Supplies Ltd.", "شركة التوريدات النموذجية"),
                      ],
                      [t("Invoice number", "رقم الفاتورة"), "INV-2026-042"],
                      [t("Subtotal", "المجموع الفرعي"), "1,000.00 SAR"],
                      [t("Tax", "الضريبة"), "150.00 SAR"],
                      [t("Total", "الإجمالي"), "1,150.00 SAR"],
                    ].map(([label, value]) => (
                      <div
                        key={label}
                        className="flex flex-wrap justify-between gap-2 py-3"
                      >
                        <dt className="text-slate-500 dark:text-slate-400">
                          {label}
                        </dt>
                        <dd className="font-medium">
                          <bdi>{value}</bdi>
                        </dd>
                      </div>
                    ))}
                  </dl>
                </div>
                <p className="flex items-center gap-2 rounded-lg bg-emerald-50 px-3 py-2.5 text-xs text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-300">
                  <Check size={15} className="shrink-0" />
                  {t(
                    "Subtotal + tax matches the total in this example.",
                    "المجموع الفرعي مع الضريبة يطابق الإجمالي في هذا المثال.",
                  )}
                </p>
              </div>
            </div>
          </div>
        </section>
        <section
          id="features"
          className="mx-auto max-w-6xl scroll-mt-6 px-5 py-14 sm:px-8"
        >
          <h2 className="text-2xl font-bold sm:text-3xl">
            {t("Choose a tool for the job", "اختر الأداة المناسبة لمهمتك")}
          </h2>
          <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-600 dark:text-slate-400">
            {t(
              "Use the workspace to process individual documents, or connect the same services to your application through the API.",
              "استخدم مساحة العمل لمعالجة المستندات، أو اربط الخدمات نفسها بتطبيقك عبر API.",
            )}
          </p>
          <div className="mt-7 grid gap-5 md:grid-cols-3">
            {[
              {
                icon: MessageSquare,
                title: t("Ask about a document", "اسأل عن مستند"),
                body: t(
                  "Find specific details or request a summary. Use the source references to check an answer against your file.",
                  "ابحث عن تفاصيل محددة أو اطلب ملخصًا. استخدم مراجع المصدر للتحقق من الإجابة في ملفك.",
                ),
              },
              {
                icon: ScanText,
                title: t("Read scanned pages", "اقرأ الصفحات الممسوحة"),
                body: t(
                  "Convert scanned pages into text with OCR. Review the extracted text before reusing it.",
                  "حوّل الصفحات الممسوحة ضوئيًا إلى نص باستخدام التعرف الضوئي على الحروف، وراجعه قبل إعادة استخدامه.",
                ),
              },
              {
                icon: Table2,
                title: t("Extract fields and tables", "استخرج الحقول والجداول"),
                body: t(
                  "Choose a service for invoices, receipts, contracts or forms. Get organized results instead of copying details by hand.",
                  "اختر خدمة للفواتير أو الإيصالات أو العقود أو النماذج، واحصل على نتائج منظمة بدلًا من نسخ التفاصيل يدويًا.",
                ),
              },
            ].map((feature) => (
              <article
                key={feature.title}
                className="rounded-xl bg-slate-50 p-6 dark:bg-slate-900"
              >
                <feature.icon
                  className="mb-4 text-emerald-700 dark:text-emerald-400"
                  size={24}
                />
                <h3 className="font-semibold">{feature.title}</h3>
                <p className="mt-2 text-sm leading-7 text-slate-600 dark:text-slate-400">
                  {feature.body}
                </p>
              </article>
            ))}
          </div>
        </section>
        <section
          id="services"
          className="border-y border-slate-200 bg-slate-50/50 dark:border-slate-800 dark:bg-slate-950/30"
        >
          <div className="mx-auto max-w-6xl space-y-7 px-5 py-14 sm:px-8">
            <div>
              <p className="eyebrow mb-2">{t("Services", "الخدمات")}</p>
              <h2 className="text-2xl font-bold sm:text-3xl">
                {t("Common document tasks", "مهام المستندات الشائعة")}
              </h2>
              <p className="mt-3 text-sm leading-7 text-slate-600 dark:text-slate-400">
                {t(
                  "Each service has a specific purpose and a clear output. Here are a few examples.",
                  "لكل خدمة مهمة محددة ونتيجة واضحة. إليك بعض الأمثلة.",
                )}
              </p>
            </div>
            <ServiceCatalog preview />
            <Link
              href="/services"
              className="inline-flex items-center gap-2 text-sm font-semibold text-emerald-700 hover:underline dark:text-emerald-400"
            >
              {t("View all services", "عرض كل الخدمات")}
              <ArrowRight size={16} className="rtl:rotate-180" />
            </Link>
          </div>
        </section>
        <section
          id="how-it-works"
          className="mx-auto max-w-6xl px-5 py-14 sm:px-8"
        >
          <h2 className="text-2xl font-bold sm:text-3xl">
            {t("How it works", "طريقة الاستخدام")}
          </h2>
          <ol className="mt-8 grid gap-8 md:grid-cols-3">
            {[
              [
                t("Upload your file", "ارفع ملفك"),
                t(
                  "Choose a file from your device. The upload screen shows supported formats and size limits.",
                  "اختر ملفًا من جهازك. توضح شاشة الرفع الصيغ المدعومة وحدود حجم الملف.",
                ),
              ],
              [
                t("Choose a task", "اختر المهمة"),
                t(
                  "Ask a question, run OCR, or select a service. Check its credit cost before running it.",
                  "اطرح سؤالًا أو استخرج النص أو اختر خدمة. راجع تكلفة الرصيد قبل التشغيل.",
                ),
              ],
              [
                t("Review the result", "راجع النتيجة"),
                t(
                  "Compare the output with your original document, then copy or export it where available.",
                  "قارن النتيجة بالمستند الأصلي، ثم انسخها أو صدّرها حيث تتوفر هذه الإمكانية.",
                ),
              ],
            ].map(([title, body], index) => (
              <li key={title}>
                <span className="mb-3 flex h-9 w-9 items-center justify-center rounded-full bg-emerald-100 text-sm font-bold text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                  {index + 1}
                </span>
                <h3 className="font-semibold">{title}</h3>
                <p className="mt-2 text-sm leading-7 text-slate-600 dark:text-slate-400">
                  {body}
                </p>
              </li>
            ))}
          </ol>
          <div className="mt-12 flex flex-wrap items-center justify-between gap-5 rounded-2xl bg-slate-900 p-7 text-white dark:bg-slate-800">
            <div>
              <h2 className="text-xl font-semibold">
                {t("Start with one document", "ابدأ بمستند واحد")}
              </h2>
              <p className="mt-2 text-sm text-slate-300">
                {t(
                  "Create an account and choose the tool you need.",
                  "أنشئ حسابًا واختر الأداة التي تحتاجها.",
                )}
              </p>
            </div>
            <Link
              href="/login?mode=signup"
              className="inline-flex items-center gap-2 rounded-lg bg-emerald-500 px-4 py-3 text-sm font-semibold text-slate-950 hover:bg-emerald-400"
            >
              <Upload size={16} />
              {t("Get started", "ابدأ الآن")}
            </Link>
          </div>
        </section>
      </main>
      <footer className="border-t border-slate-200 px-5 py-7 dark:border-slate-800">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4">
          <Brand />
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {t(
              "Document chat, text recognition and data extraction.",
              "محادثة المستندات والتعرف على النص واستخراج البيانات.",
            )}
          </p>
          <Link
            href="/docs"
            className="text-sm text-slate-600 hover:underline dark:text-slate-300"
          >
            {t("API documentation", "توثيق API")}
          </Link>
        </div>
      </footer>
    </div>
  );
}
