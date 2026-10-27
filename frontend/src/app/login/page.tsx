"use client";

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

function LoginForm() {
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
          : (err as Error)?.message || "Something went wrong",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="grid min-h-screen bg-[#fcfdfb] lg:grid-cols-2">
      <aside className="relative hidden flex-col overflow-hidden bg-[#173e38] p-12 text-white lg:flex">
        <Brand light />
        <div className="my-auto py-20">
          <span className="inline-block rounded-2xl border border-[#416159] bg-[#244a42] p-5 text-[#cce3b8]">
            <Layers size={38} />
          </span>
          <h2 className="mt-9 max-w-lg text-5xl font-medium leading-tight tracking-tight">
            A little less searching.
            <br />
            <span className="text-[#c4dcae]">A lot more clarity.</span>
          </h2>
          <p className="mt-6 max-w-md text-sm leading-7 text-[#a6c2b5]">
            Bring your documents, spreadsheets, and ideas together. Your next
            insight is one good question away.
          </p>
          <div className="mt-10 flex gap-3 text-[11px] text-[#b2cdbf]">
            <span className="rounded-full border border-[#45695b] px-3 py-1">
              PDF
            </span>
            <span className="rounded-full border border-[#45695b] px-3 py-1">
              Word
            </span>
            <span className="rounded-full border border-[#45695b] px-3 py-1">
              Excel
            </span>
          </div>
        </div>
        <p className="text-xs text-[#8fac9d]">
          Your knowledge. A little more connected.
        </p>
      </aside>
      <div className="flex min-h-screen flex-col p-6 sm:p-12">
        <Link
          href="/"
          className="flex items-center gap-2 text-xs text-slate-500"
        >
          <ArrowLeft size={14} /> Back to home
        </Link>
        <div className="mx-auto my-auto w-full max-w-sm py-12">
          <div className="mb-8 lg:hidden">
            <Brand />
          </div>
          <Card className="w-full !border-0 !bg-transparent !shadow-none">
            <CardHeader className="!px-0 !pt-0">
              <CardTitle className="text-3xl tracking-tight">
                {mode === "login"
                  ? "Welcome back."
                  : "Make room for your next idea."}
              </CardTitle>
              <p className="mt-2 text-sm leading-6 text-slate-400">
                {mode === "login"
                  ? "Your documents and conversations are right where you left them."
                  : "Create your personal knowledge workspace."}
              </p>
            </CardHeader>
            <CardContent className="!px-0">
              <form onSubmit={handleSubmit} className="space-y-4">
                {mode === "signup" && (
                  <div className="space-y-1.5">
                    <Label htmlFor="name">Name</Label>
                    <Input
                      id="name"
                      name="name"
                      placeholder="Jane Doe"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      required
                      autoComplete="name"
                    />
                  </div>
                )}
                <div className="space-y-1.5">
                  <Label htmlFor="email">Email</Label>
                  <Input
                    id="email"
                    name="email"
                    type="email"
                    placeholder="jane@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    autoComplete="email"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="password">Password</Label>
                  <Input
                    id="password"
                    name="password"
                    type="password"
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
                  <p className="rounded-md bg-rose-50 p-2 text-sm text-rose-700">
                    {error}
                  </p>
                )}
                <Button type="submit" className="w-full" disabled={submitting}>
                  {submitting ? (
                    <Spinner size={18} />
                  ) : mode === "login" ? (
                    "Sign in"
                  ) : (
                    "Create account"
                  )}
                </Button>
              </form>

              <div className="mt-4 text-center text-sm">
                <button
                  type="button"
                  className="text-indigo-600 hover:underline"
                  onClick={() => setMode(mode === "login" ? "signup" : "login")}
                >
                  {mode === "login"
                    ? "Don't have an account? Sign up"
                    : "Already have an account? Sign in"}
                </button>
              </div>
            </CardContent>
          </Card>
          <p className="mt-8 text-center text-[10px] text-slate-400">
            A thoughtful workspace for your documents and ideas.
          </p>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center">
          <Spinner size={24} />
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
