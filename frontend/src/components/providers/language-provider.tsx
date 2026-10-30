"use client";

import {
  createContext,
  useContext,
  useSyncExternalStore,
  useCallback,
} from "react";

import { arabicLabels } from "@/lib/translations";

export type Language = "en" | "ar";
const LanguageContext = createContext<{
  language: Language;
  setLanguage: (language: Language) => void;
  t: (english: string, arabic?: string) => string;
}>({ language: "en", setLanguage: () => {}, t: (english) => english });

function subscribe(callback: () => void) {
  window.addEventListener("doctool-language", callback);
  const onStorage = (event: StorageEvent) => {
    if (event.key !== "doctool-language" && event.key !== null) return;
    const next = event.newValue === "ar" ? "ar" : "en";
    document.documentElement.lang = next;
    document.documentElement.dir = next === "ar" ? "rtl" : "ltr";
    callback();
  };
  window.addEventListener("storage", onStorage);
  return () => {
    window.removeEventListener("doctool-language", callback);
    window.removeEventListener("storage", onStorage);
  };
}

function getLanguage(): Language {
  return document.documentElement.lang === "ar" ? "ar" : "en";
}

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const language = useSyncExternalStore(
    subscribe,
    getLanguage,
    () => "en" as const,
  );
  function setLanguage(next: Language) {
    document.documentElement.lang = next;
    document.documentElement.dir = next === "ar" ? "rtl" : "ltr";
    try {
      localStorage.setItem("doctool-language", next);
    } catch {}
    window.dispatchEvent(new Event("doctool-language"));
  }
  const t = useCallback(
    (en: string, ar?: string) =>
      language === "ar" ? (ar ?? arabicLabels[en] ?? en) : en,
    [language],
  );
  return (
    <LanguageContext.Provider value={{ language, setLanguage, t }}>
      {children}
    </LanguageContext.Provider>
  );
}

export const useLanguage = () => useContext(LanguageContext);
