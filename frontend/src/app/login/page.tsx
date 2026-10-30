"use client";
import { useLanguage } from "@/components/providers/language-provider";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { Brand } from "@/components/brand";
import { ArrowLeft, Layers } from "lucide-react";
import { useSearchParams, useRouter } from "next/navigation";
import { useSession } from "@/components/providers/session-provider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { ApiError } from "@/lib/api";
import { LanguageToggle } from "@/components/ui/language-toggle";
import { ThemeToggle } from "@/components/ui/theme-toggle";

function LoginForm() {
  const { t } = useLanguage();
  const search = useSearchParams();
  const router = useRouter();
  const { user, login, register } = useSession();
  const [mode, setMode] = useState<"login" | "signup">(
    search?.get("mode") === "signup" ? "signup" : "login",
  );
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (user) router.replace("/overview");
  }, [user, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      if (mode === "login") {
        await login(email, password);
      } else {
        await register(name, email, password);
      }
      router.replace("/overview");
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : (err as Error)?.message || t("Something went wrong"),
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="grid min-h-screen bg-white text-slate-900 dark:bg-[#090d12] dark:text-slate-100 lg:grid-cols-2 transition-colors">
      <aside className="relative hidden flex-col overflow-hidden bg-gradient-to-b from-[#061816] via-[#09221f] to-[#040e0d] p-12 text-white lg:flex border-r border-slate-800">
        <Brand light />
        <div className="my-auto py-20">
          <span className="inline-block rounded-2xl border border-emerald-700/50 bg-emerald-950/60 p-5 text-emerald-400 shadow-lg shadow-emerald-950/40">
            <Layers size={38} />
          </span>
          <h2 className="mt-9 max-w-lg text-5xl font-extrabold leading-tight tracking-tight">
            {t("Read your documents.")}<br />
            <span className="text-emerald-400">{t("Find the details you need.")}</span>
          </h2>
          <p className="mt-6 max-w-md text-sm leading-7 text-slate-300">
            {t("Upload documents and spreadsheets. Ask questions about their contents or extract specific data.")}</p>
          <div className="mt-10 flex gap-3 text-[11px] text-emerald-200">
            <span className="rounded-full border border-emerald-800/80 bg-emerald-950/40 px-3.5 py-1">
              {t("PDF Documents")}</span>
            <span className="rounded-full border border-emerald-800/80 bg-emerald-950/40 px-3.5 py-1">
              {t("Word & DOCX")}</span>
            <span className="rounded-full border border-emerald-800/80 bg-emerald-950/40 px-3.5 py-1">
              {t("Excel & Sheets")}</span>
          </div>
        </div>
        <p className="text-xs text-slate-400">
          {t("Document chat, OCR and data extraction.")}</p>
      </aside>

      <div className="flex min-h-screen flex-col p-6 sm:p-12">
        <div className="flex items-center justify-between">
          <Link
            href="/"
            className="flex items-center gap-2 text-xs font-semibold text-slate-500 hover:text-emerald-600 dark:text-slate-400 dark:hover:text-emerald-400 transition"
          >
            <ArrowLeft size={14} /> {t("Back to home")}</Link>
          <LanguageToggle /><ThemeToggle />
        </div>

        <div className="mx-auto my-auto w-full max-w-sm py-12">
          <div className="mb-8 lg:hidden">
            <Brand />
          </div>
          <Card className="w-full !border-0 !bg-transparent !shadow-none">
            <CardHeader className="!px-0 !pt-0">
              <CardTitle className="text-3xl font-extrabold tracking-tight text-slate-900 dark:text-white">
                {mode === "login"
                  ? t("Sign in to DOCTool")
                  : t("Create your account")}
              </CardTitle>
              <p className="mt-2 text-sm leading-6 text-slate-500 dark:text-slate-400">
                {mode === "login"
                  ? t("Sign in to use the document tools.")
                  : t("Create an account to upload documents and use the services.")}
              </p>
            </CardHeader>
            <CardContent className="!px-0">
              <form onSubmit={handleSubmit} className="space-y-4">
                {mode === "signup" && (
                  <div className="space-y-1.5">
                    <Label htmlFor="name">{t("Name")}</Label>
                    <Input
                      id="name"
                      name="name"
                      placeholder={t("Your name", "اسمك")}
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      required
                      autoComplete="name"
                    />
                  </div>
                )}
                <div className="space-y-1.5">
                  <Label htmlFor="email">{t("Email")}</Label>
                  <Input
                    id="email"
                    name="email"
                    type="email"
                    dir="ltr"
                    placeholder="jane@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    autoComplete="email"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="password">{t("Password")}</Label>
                  <Input
                    id="password"
                    name="password"
                    type="password"
                    dir="ltr"
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    minLength={6}
                    autoComplete={
                      mode === "login" ? "current-password" : "new-password"
                    }
                  />
                </div>
                {error && (
                  <p role="alert" className="rounded-md bg-rose-50 border border-rose-200 p-2.5 text-sm text-rose-700 dark:bg-rose-950/40 dark:border-rose-800 dark:text-rose-300">
                    {t(error)}
                  </p>
                )}
                <Button type="submit" className="w-full bg-gradient-to-r from-teal-700 to-emerald-600 hover:from-teal-800 hover:to-emerald-700 text-white font-semibold" disabled={submitting}>
                  {submitting ? (
                    <Spinner size={18} />
                  ) : mode === "login" ? (
                    t("Sign in")
                  ) : (
                    t("Create account")
                  )}
                </Button>
              </form>

              <div className="mt-5 text-center text-sm">
                <button
                  type="button"
                  className="font-semibold text-emerald-700 hover:text-emerald-800 hover:underline dark:text-emerald-400 dark:hover:text-emerald-300"
                  onClick={() => setMode(mode === "login" ? "signup" : "login")}
                >
                  {mode === "login"
                    ? t("Don't have an account? Sign up")
                    : t("Already have an account? Sign in")}
                </button>
              </div>
            </CardContent>
          </Card>
          <p className="mt-8 text-center text-[10px] text-slate-400 dark:text-slate-500">
            {t("Tools for reading documents and extracting data.")}</p>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-white dark:bg-[#090d12]">
          <Spinner size={24} />
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
