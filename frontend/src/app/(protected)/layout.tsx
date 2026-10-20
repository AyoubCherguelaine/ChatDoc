"use client";

import { Suspense } from "react";
import { Navbar } from "@/components/navbar";
import { useRequireAuth } from "@/components/providers/session-provider";
import { Spinner } from "@/components/ui/spinner";

export default function ProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, loading } = useRequireAuth();

  if (loading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 ">
        <Spinner size={24} />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#f6f8f9] lg:pl-[244px]">
      <Suspense fallback={null}>
        <Navbar />
      </Suspense>
      <main className="workspace-main p-5 md:p-8 lg:px-10 lg:py-8">
        <Suspense fallback={<Spinner size={24} />}>{children}</Suspense>
      </main>
    </div>
  );
}
