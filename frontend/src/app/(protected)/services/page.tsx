"use client";

import Link from "next/link";
import { BookOpen } from "lucide-react";
import { useLanguage } from "@/components/providers/language-provider";
import { ServiceCatalog } from "@/components/services/service-catalog";

export default function ServicesPage() {
  const { t } = useLanguage();
  return (
    <div className="mx-auto max-w-6xl space-y-7 animate-enter">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="max-w-2xl">
          <p className="eyebrow mb-2">
            {t("Document tools", "أدوات المستندات")}
          </p>
          <h1 className="text-3xl font-bold tracking-tight">
            {t("Services", "الخدمات")}
          </h1>
          <p className="mt-3 text-sm leading-7 text-slate-600 dark:text-slate-400">
            {t(
              "Choose what you need to do with your document. Open a service, select a file, and review the result. Each card shows the output and credit cost.",
              "اختر ما تريد إنجازه بمستندك. افتح الخدمة، وحدد ملفًا، ثم راجع النتيجة. تعرض كل بطاقة نوع النتيجة وتكلفة الرصيد.",
            )}
          </p>
        </div>
        <Link
          href="/docs"
          className="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-700"
        >
          <BookOpen size={16} />
          {t("Integration guide", "دليل التكامل")}
        </Link>
      </header>
      <ServiceCatalog />
      <p className="rounded-xl bg-slate-100 p-4 text-sm leading-6 text-slate-600 dark:bg-slate-900 dark:text-slate-400">
        {t(
          "Check extracted data and generated answers against the original document before using them. Contract, privacy and financial reviews highlight items for your review; they do not certify a document.",
          "راجع البيانات المستخرجة والإجابات بمقارنتها مع المستند الأصلي قبل استخدامها. تحدد مراجعات العقود والخصوصية والمالية نقاطًا لتراجعها، ولا تمنح اعتمادًا للمستند.",
        )}
      </p>
    </div>
  );
}
