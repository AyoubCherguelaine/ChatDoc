"use client";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import {
  LayoutDashboard,
  Files,
  MessageSquare,
  Sparkles,
  Bot,
  Key,
  LogOut,
  ArrowUpRight,
  PanelLeftClose,
  Menu,
  ChevronDown,
  Settings,
  ScanText,
} from "lucide-react";
import { useState } from "react";
import { Brand } from "@/components/brand";
import { useSession } from "@/components/providers/session-provider";
import { cn } from "@/lib/utils";
export function Navbar() {
  const { user, logout } = useSession();
  const pathname = usePathname();
  const search = useSearchParams();
  const [open, setOpen] = useState(false);
  const links = [
    { href: "/drive", label: "Overview", icon: LayoutDashboard },
    { href: "/drive?view=documents", label: "All documents", icon: Files },
    { href: "/conversations", label: "Conversations", icon: MessageSquare },
    { href: "/services", label: "AI Services", icon: Bot },
    { href: "/advanced-ocr", label: "Advanced OCR", icon: ScanText },
    { href: "/usage", label: "API & Credits", icon: Key },
  ];
  return (
    <>
      <header className="sticky top-0 z-40 flex items-center justify-between border-b border-slate-200 bg-white px-5 py-4 lg:hidden">
        <Brand />
        <button aria-label="Toggle navigation" onClick={() => setOpen(!open)}>
          <Menu size={23} />
        </button>
      </header>
      {open && (
        <button
          aria-label="Close navigation"
          className="fixed inset-0 z-40 bg-slate-950/30 lg:hidden"
          onClick={() => setOpen(false)}
        />
      )}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-[244px] flex-col border-r border-[#e4e9eb] bg-[#fcfdfd] px-4 py-7 transition-transform lg:visible lg:translate-x-0",
          open ? "visible translate-x-0" : "invisible -translate-x-full",
        )}
      >
        <div className="mb-9 flex items-center justify-between px-3">
          <Brand />
          <button
            className="text-slate-400 lg:hidden"
            aria-label="Close navigation"
            onClick={() => setOpen(false)}
          >
            <PanelLeftClose size={17} />
          </button>
        </div>
        <div className="mb-8 flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-3">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#f0ede4] text-sm font-semibold text-[#8c7959]">
            {user?.name?.[0]?.toUpperCase() || "M"}
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-semibold">
              {user?.name?.split(" ")[0] || "My"}’s workspace
            </p>
            <p className="mt-1 text-[10px] text-slate-400">
              Personal workspace
            </p>
          </div>
          <ChevronDown size={13} className="text-slate-400" />
        </div>
        <p className="eyebrow mb-3 px-3">Workspace</p>
        <nav aria-label="Workspace navigation" className="space-y-1">
          {links.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              onClick={() => setOpen(false)}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-3 text-[13px] font-medium text-[#77858b] transition-colors hover:bg-slate-100",
                (href.includes("?")
                  ? pathname === "/drive" && search?.get("view") === "documents"
                  : pathname === href &&
                    !(
                      href === "/drive" && search?.get("view") === "documents"
                    )) && "bg-[#e9f4ef] !text-[#087f74]",
              )}
            >
              <Icon size={18} />
              {label}
              {label === "AI studio" && (
                <span className="ml-auto rounded border border-[#d9e6d8] bg-[#f1f6e9] px-1.5 py-0.5 text-[8px] text-[#74825a]">
                  TOOLS
                </span>
              )}
              {label === "API & Credits" && (
                <span className="ml-auto rounded border border-teal-200 bg-teal-50 px-1.5 py-0.5 text-[8px] font-semibold text-teal-700">
                  1.2k Free
                </span>
              )}
            </Link>
          ))}
        </nav>
        <div className="mt-auto">
          <div className="mb-6 rounded-xl border border-[#e3e9dc] bg-[#f3f6ed] p-4">
            <Sparkles size={19} className="mb-3 text-[#728f56]" />
            <p className="text-xs font-semibold">
              Good questions, great insights.
            </p>
            <p className="mt-2 text-[11px] leading-5 text-[#82907b]">
              Try a research agent on your next report.
            </p>
            <Link
              href="/agents"
              onClick={() => setOpen(false)}
              className="mt-4 flex items-center justify-between text-xs font-medium text-[#53764e]"
            >
              Explore AI studio <ArrowUpRight size={14} />
            </Link>
          </div>
          <div className="flex items-center gap-3 border-t border-slate-200 px-2 pt-5">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-[#e4ecec] text-xs font-semibold text-slate-500">
              {user?.name?.[0]?.toUpperCase() || "U"}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-medium">
                {user?.name || "Your account"}
              </p>
              <p className="truncate text-[10px] text-slate-400">
                {user?.email}
              </p>
            </div>
            <button
              title="Settings (coming soon)"
              className="rounded p-1 text-slate-400 hover:text-slate-600 transition"
            >
              <Settings size={16} />
            </button>
            <button
              onClick={logout}
              aria-label="Sign out"
              title="Log out"
              className="rounded p-1 text-slate-400 hover:text-rose-600 transition"
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
