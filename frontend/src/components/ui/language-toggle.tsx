"use client";

import { Languages } from "lucide-react";
import { useLanguage } from "@/components/providers/language-provider";

export function LanguageToggle() {
  const { language, setLanguage } = useLanguage();
  return (
    <button
      type="button"
      onClick={() => setLanguage(language === "en" ? "ar" : "en")}
      lang={language === "en" ? "ar" : "en"}
      aria-label={
        language === "en" ? "التبديل إلى العربية" : "Switch to English"
      }
      className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-2 text-xs font-semibold text-slate-700 transition hover:bg-slate-100 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
    >
      <Languages size={16} aria-hidden="true" />
      {language === "en" ? "العربية" : "English"}
    </button>
  );
}
