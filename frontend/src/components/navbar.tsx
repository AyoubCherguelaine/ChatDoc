"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  MessageSquare,
  Bot,
  LogOut,
  PanelLeftClose,
  Menu,
  ChevronDown,
  Settings,
  ScanText,
  Zap,
  Code2,
  X,
  User,
  Copy,
  Check,
  ShieldCheck,
  Cpu,
  History,
  FileCheck2,
  Users,
  Building,
  LayoutDashboard,
  BookOpen,
} from "lucide-react";
import { useState, useEffect, useRef } from "react";
import { Brand } from "@/components/brand";
import { useSession } from "@/components/providers/session-provider";
import { fetchCompanyAccount, type CompanyAccountInfo } from "@/lib/api";
import { cn } from "@/lib/utils";

function getPageTitle(pathname: string): string {
  if (pathname.startsWith("/overview")) return "Platform Overview";
  if (pathname.startsWith("/advanced-ocr")) return "Advanced OCR";
  if (pathname.startsWith("/services")) return "AI Services";
  if (pathname.startsWith("/docs")) return "Platform Documentation";
  if (pathname.startsWith("/playground")) return "Playground Sandbox";
  if (pathname.startsWith("/usage")) return "Credits & Usage Logs";
  if (pathname.startsWith("/conversations")) return "Chats";
  if (pathname.startsWith("/chat")) return "Document Chat";
  return "Document AI";
}

export function Navbar() {
  const { user, logout } = useSession();
  const pathname = usePathname();

  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [profileDropdownOpen, setProfileDropdownOpen] = useState(false);
  const [selectedGroup, setSelectedGroup] = useState<string>("main");
  const [account, setAccount] = useState<CompanyAccountInfo | null>(null);
  const [copiedKey, setCopiedKey] = useState(false);

  const profileMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let active = true;
    fetchCompanyAccount()
      .then((data) => {
        if (active) setAccount(data);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [pathname]);

  // Close profile dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        profileMenuRef.current &&
        !profileMenuRef.current.contains(event.target as Node)
      ) {
        setProfileDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const mainNavLinks = [
    {
      href: "/overview",
      label: "Overview",
      icon: LayoutDashboard,
      isActive: (p: string) => p.startsWith("/overview"),
    },
    {
      href: "/conversations",
      label: "Chats",
      icon: MessageSquare,
      isActive: (p: string) => p.startsWith("/conversations") || p.startsWith("/chat"),
    },
    {
      href: "/advanced-ocr",
      label: "Advanced OCR",
      icon: ScanText,
      isActive: (p: string) => p.startsWith("/advanced-ocr"),
    },
    {
      href: "/services",
      label: "AI Services",
      icon: Bot,
      isActive: (p: string) => p.startsWith("/services"),
    },
  ];

  function copyApiKey() {
    if (!account) return;
    const key = account.rawApiKey || account.apiKey || account.apiKeyPrefix;
    navigator.clipboard.writeText(key).then(() => {
      setCopiedKey(true);
      setTimeout(() => setCopiedKey(false), 2000);
    });
  }

  const remaining = account?.remainingCredits ?? 1200;
  const initial = user?.name?.[0]?.toUpperCase() || "U";
  const pageTitle = getPageTitle(pathname);

  return (
    <>
      {/* =========================================================================
          1. TOP HORIZONTAL NAVIGATION BAR (NAVBAR)
          Contains: small credit pill, profile with select group, settings, logout
         ========================================================================= */}
      <header className="sticky top-0 z-30 flex h-14 w-full items-center justify-between border-b border-slate-200 bg-white/95 px-4 backdrop-blur-md sm:px-6 lg:px-10">
        {/* Left: Mobile Toggle + Breadcrumb / Operation Title */}
        <div className="flex items-center gap-3">
          <button
            aria-label="Toggle operations sidebar"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 lg:hidden"
          >
            <Menu size={20} />
          </button>

          <div className="hidden sm:flex items-center gap-2 text-xs">
            <span className="font-semibold text-slate-400">DOC Tool</span>
            <span className="text-slate-300">/</span>
            <span className="font-bold text-slate-800">{pageTitle}</span>
          </div>

          <div className="sm:hidden">
            <Brand href="/overview" />
          </div>
        </div>

        {/* Right: Small Credit Pill + Profile with Select Group */}
        <div className="flex items-center gap-3">
          {/* SMALL CREDIT PILL */}
          <Link
            href="/usage"
            title="View remaining credit quota and usage logs"
            className="inline-flex items-center gap-1.5 rounded-full border border-teal-200 bg-teal-50 px-2.5 py-1 text-xs font-semibold text-teal-800 hover:bg-teal-100 transition shadow-2xs"
          >
            <Zap size={12} className="text-teal-600 fill-teal-600" />
            <span>{remaining.toLocaleString()}</span>
            <span className="hidden sm:inline text-[11px] font-normal text-teal-700">Credits</span>
          </Link>

          {/* PROFILE WITH SELECT GROUP (DROPDOWN) */}
          <div className="relative" ref={profileMenuRef}>
            <button
              onClick={() => setProfileDropdownOpen(!profileDropdownOpen)}
              className="flex items-center gap-2 rounded-full border border-slate-200 bg-white p-1 pr-2.5 text-left transition hover:border-teal-400 hover:shadow-2xs"
              aria-label="Profile and select group"
            >
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-teal-700 text-xs font-bold text-white shadow-2xs">
                {initial}
              </span>
              <span className="hidden md:inline max-w-[110px] truncate text-xs font-semibold text-slate-800">
                {user?.name || "Account"}
              </span>
              <ChevronDown size={13} className="text-slate-400" />
            </button>

            {/* Profile Dropdown / Slide Menu */}
            {profileDropdownOpen && (
              <div className="absolute right-0 top-11 z-50 w-80 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl animate-in fade-in zoom-in-95 duration-150">
                {/* Profile Header */}
                <div className="border-b border-slate-100 bg-slate-50/70 p-4">
                  <div className="flex items-center gap-3">
                    <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-teal-700 text-base font-bold text-white shadow-sm">
                      {initial}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-bold text-slate-900">{user?.name}</p>
                      <p className="truncate text-xs text-slate-500">{user?.email}</p>
                    </div>
                  </div>
                </div>

                {/* Workspace / Select Group */}
                <div className="border-b border-slate-100 p-3">
                  <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-2 px-1">
                    Select Group / Workspace
                  </p>
                  <div className="space-y-1">
                    <button
                      type="button"
                      onClick={() => setSelectedGroup("main")}
                      className={`flex w-full items-center justify-between rounded-lg px-2.5 py-2 text-xs font-medium transition ${
                        selectedGroup === "main"
                          ? "bg-teal-50 text-teal-900 font-semibold"
                          : "text-slate-700 hover:bg-slate-50"
                      }`}
                    >
                      <div className="flex items-center gap-2 truncate">
                        <Building size={14} className="text-teal-600" />
                        <span className="truncate">{account?.companyName || "Default Organization"}</span>
                      </div>
                      {selectedGroup === "main" && <Check size={14} className="text-teal-600" />}
                    </button>

                    <button
                      type="button"
                      onClick={() => setSelectedGroup("personal")}
                      className={`flex w-full items-center justify-between rounded-lg px-2.5 py-2 text-xs font-medium transition ${
                        selectedGroup === "personal"
                          ? "bg-teal-50 text-teal-900 font-semibold"
                          : "text-slate-700 hover:bg-slate-50"
                      }`}
                    >
                      <div className="flex items-center gap-2 truncate">
                        <Users size={14} className="text-slate-500" />
                        <span>Personal Workspace</span>
                      </div>
                      {selectedGroup === "personal" && <Check size={14} className="text-teal-600" />}
                    </button>
                  </div>
                </div>

                {/* Credit Balance & Logs Link */}
                <div className="border-b border-slate-100 p-3 bg-teal-50/40">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[11px] font-semibold text-slate-700 flex items-center gap-1">
                      <Zap size={13} className="text-teal-600 fill-teal-600" />
                      Available Balance
                    </span>
                    <span className="text-[10px] font-bold uppercase rounded bg-teal-100 px-1.5 py-0.5 text-teal-800">
                      {account?.planTier || "Free Trial"}
                    </span>
                  </div>
                  <div className="text-xl font-extrabold text-slate-900">
                    {remaining.toLocaleString()}{" "}
                    <span className="text-xs font-normal text-slate-500">credits</span>
                  </div>
                  <Link
                    href="/usage"
                    onClick={() => setProfileDropdownOpen(false)}
                    className="mt-2 flex items-center justify-between rounded-lg bg-white border border-teal-200 p-2 text-[11px] font-semibold text-teal-800 hover:bg-teal-50 transition"
                  >
                    <span className="flex items-center gap-1">
                      <History size={13} /> View Credit Usage Logs
                    </span>
                    <span>→</span>
                  </Link>
                </div>

                {/* API Key & Architecture */}
                <div className="border-b border-slate-100 p-3 space-y-2">
                  <div className="flex items-center justify-between text-xs font-semibold text-slate-700">
                    <span>Company API Key</span>
                    <button
                      onClick={copyApiKey}
                      className="text-[11px] text-teal-700 hover:underline flex items-center gap-1"
                    >
                      {copiedKey ? (
                        <>
                          <Check size={11} className="text-emerald-600" />
                          <span className="text-emerald-600">Copied</span>
                        </>
                      ) : (
                        <>
                          <Copy size={11} />
                          <span>Copy</span>
                        </>
                      )}
                    </button>
                  </div>
                  <div className="rounded bg-slate-900 p-1.5 font-mono text-[11px] text-emerald-400 truncate">
                    {account?.apiKeyPrefix || "docu_live_"}••••••••••••••••
                  </div>
                  <p className="text-[10px] text-slate-400">
                    Configured model: <span className="font-semibold text-slate-600 font-mono">Luna (gpt-6-luna)</span>
                  </p>
                </div>

                {/* Logout Button */}
                <div className="p-2 bg-slate-50/50">
                  <button
                    type="button"
                    onClick={() => {
                      setProfileDropdownOpen(false);
                      logout();
                    }}
                    className="flex w-full items-center justify-center gap-2 rounded-xl py-2 text-xs font-semibold text-rose-700 hover:bg-rose-50 transition"
                  >
                    <LogOut size={14} />
                    <span>Log Out</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* =========================================================================
          2. SIDEBAR FOR OPERATIONS (LEFT)
          Fixed on desktop, drawer on mobile
         ========================================================================= */}
      {/* Mobile Backdrop */}
      {sidebarOpen && (
        <button
          aria-label="Close navigation"
          className="fixed inset-0 z-40 bg-slate-950/30 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-[244px] flex-col border-r border-[#e4e9eb] bg-[#fcfdfd] px-4 py-6 transition-transform lg:visible lg:translate-x-0",
          sidebarOpen ? "visible translate-x-0" : "invisible -translate-x-full",
        )}
      >
        {/* Brand Header */}
        <div className="mb-8 flex items-center justify-between px-2">
          <Brand href="/overview" />
          <button
            className="text-slate-400 lg:hidden"
            aria-label="Close navigation"
            onClick={() => setSidebarOpen(false)}
          >
            <PanelLeftClose size={17} />
          </button>
        </div>

        {/* Operations / Workspace Label */}
        <p className="eyebrow mb-2 px-3 text-[11px] font-bold text-slate-400 uppercase tracking-wider">
          Workspace
        </p>

        {/* Primary Navigation Links */}
        <nav aria-label="Main operations navigation" className="space-y-1">
          {mainNavLinks.map(({ href, label, icon: Icon, isActive }) => {
            const active = isActive(pathname);
            return (
              <Link
                key={href}
                href={href}
                onClick={() => setSidebarOpen(false)}
                className={cn(
                  "flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] font-medium text-slate-600 transition-colors hover:bg-slate-100",
                  active && "bg-[#e9f4ef] !text-[#087f74] font-semibold",
                )}
              >
                <Icon size={17} className={active ? "text-[#087f74]" : "text-slate-500"} />
                <span>{label}</span>
              </Link>
            );
          })}
        </nav>

        {/* Secondary Developer & Quota Tools */}
        <div className="mt-5 pt-4 border-t border-slate-100">
          <p className="eyebrow mb-2 px-3 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
            Developer & Quota
          </p>
          <nav aria-label="Developer navigation" className="space-y-1">
            <Link
              href="/docs"
              onClick={() => setSidebarOpen(false)}
              className={cn(
                "flex items-center gap-3 rounded-xl px-3 py-2 text-[12px] font-medium text-slate-600 transition-colors hover:bg-slate-100",
                pathname.startsWith("/docs") && "bg-[#e9f4ef] !text-[#087f74] font-semibold",
              )}
            >
              <BookOpen size={16} />
              <span>Platform Docs</span>
              <span className="ml-auto rounded border border-teal-200 bg-teal-50 px-1.5 py-0.5 text-[9px] font-mono font-semibold text-teal-800">
                DOCS
              </span>
            </Link>
            <Link
              href="/playground"
              onClick={() => setSidebarOpen(false)}
              className={cn(
                "flex items-center gap-3 rounded-xl px-3 py-2 text-[12px] font-medium text-slate-600 transition-colors hover:bg-slate-100",
                pathname.startsWith("/playground") && "bg-[#e9f4ef] !text-[#087f74] font-semibold",
              )}
            >
              <Code2 size={16} />
              <span>Sandbox Demo</span>
              <span className="ml-auto rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-[9px] font-mono font-semibold text-slate-600">
                RUN
              </span>
            </Link>
            <Link
              href="/usage"
              onClick={() => setSidebarOpen(false)}
              className={cn(
                "flex items-center gap-3 rounded-xl px-3 py-2 text-[12px] font-medium text-slate-600 transition-colors hover:bg-slate-100",
                pathname.startsWith("/usage") && "bg-[#e9f4ef] !text-[#087f74] font-semibold",
              )}
            >
              <Zap size={16} />
              <span>Credits & Usage</span>
              <span className="ml-auto rounded bg-teal-100 px-1.5 py-0.5 text-[9px] font-bold text-teal-800">
                LOGS
              </span>
            </Link>
          </nav>
        </div>

        {/* Sidebar Footer Info */}
        <div className="mt-auto rounded-xl border border-slate-200 bg-slate-50/70 p-3.5 space-y-1 text-xs text-slate-500">
          <div className="flex items-center gap-1.5 font-semibold text-slate-800">
            <ShieldCheck size={14} className="text-teal-600" />
            <span>Stateless Engine</span>
          </div>
          <p className="text-[11px] text-slate-500 leading-relaxed">
            Zero permanent storage. All PDFs are processed on the fly and deleted immediately.
          </p>
        </div>
      </aside>
    </>
  );
}
