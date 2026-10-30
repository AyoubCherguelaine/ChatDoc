"use client";

import { Suspense, useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Navbar } from "@/components/navbar";
import { useSession } from "@/components/providers/session-provider";
import { Spinner } from "@/components/ui/spinner";

export default function ProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, loading } = useSession();
  const pathname = usePathname();
  const router = useRouter();
  const isChat = pathname?.startsWith("/chat");
  const isDocs = pathname?.startsWith("/docs");

  useEffect(() => {
    if (!isDocs && !loading && !user) {
      router.replace("/login");
    }
  }, [isDocs, loading, user, router]);

  if (!isDocs && (loading || !user)) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-white dark:bg-[#090d12]">
        <Spinner size={24} />
      </div>
    );
  }

  if (isChat) {
    return (
      <div className="h-screen flex flex-col bg-slate-50/60 dark:bg-[#090d12] lg:ps-[244px] overflow-hidden text-slate-900 dark:text-slate-100 transition-colors">
        <Suspense fallback={null}>
          <Navbar />
        </Suspense>
        <main className="flex-1 min-h-0 overflow-hidden p-3 sm:p-4 lg:px-6 lg:py-3.5 flex flex-col">
          <Suspense fallback={<Spinner size={24} />}>{children}</Suspense>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50/60 dark:bg-[#090d12] lg:ps-[244px] text-slate-900 dark:text-slate-100 transition-colors">
      <Suspense fallback={null}>
        <Navbar />
      </Suspense>
      <main className="workspace-main p-5 md:p-8 lg:px-10 lg:py-8">
        <Suspense fallback={<Spinner size={24} />}>{children}</Suspense>
      </main>
    </div>
  );
}
