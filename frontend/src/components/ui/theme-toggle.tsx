"use client";
import { useLanguage } from "@/components/providers/language-provider";

import { useTheme } from "@/components/providers/theme-provider";
import { Sun, Moon } from "lucide-react";
import { useSyncExternalStore } from "react";

const subscribe = () => () => {};

export function ThemeToggle({
  className = "",
  compact = false,
}: {
  className?: string;
  compact?: boolean;
}) {
  const { t } = useLanguage();
  const { resolvedTheme, toggleTheme } = useTheme();
  const mounted = useSyncExternalStore(subscribe, () => true, () => false);

  if (!mounted) {
    return (
      <button
        type="button"
        aria-label={t("Toggle theme")}
        className={`flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500 opacity-70 transition dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400 ${className}`}
      >
        <span className="h-4 w-4" />
      </button>
    );
  }

  const isDark = resolvedTheme === "dark";

  return (
    <button
      type="button"
      onClick={toggleTheme}
      title={isDark ? t("Switch to White & Green Light mode") : t("Switch to Modern Dark mode")}
      aria-label={isDark ? t("Switch to Light mode") : t("Switch to Dark mode")}
      className={`group relative flex h-8 items-center justify-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 text-xs font-medium text-slate-700 shadow-2xs transition hover:border-emerald-500 hover:text-emerald-700 active:scale-95 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-emerald-500 dark:hover:text-emerald-400 ${
        compact ? "w-8 px-0" : ""
      } ${className}`}
    >
      {isDark ? (
        <>
          <Sun size={15} className="text-amber-400 transition group-hover:rotate-45" />
          {!compact && <span className="hidden sm:inline text-[11px] font-medium text-slate-300">{t("Light")}</span>}
        </>
      ) : (
        <>
          <Moon size={15} className="text-emerald-700 transition group-hover:-rotate-12" />
          {!compact && <span className="hidden sm:inline text-[11px] font-medium text-slate-600">{t("Dark")}</span>}
        </>
      )}
    </button>
  );
}

