"use client";

import { usePathname } from "next/navigation";
import { Sidebar } from "@/components/Sidebar";
import { clearToken } from "@/lib/api";
import { useRouter } from "next/navigation";

export function AppChrome({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();

  if (pathname === "/login") {
    return <>{children}</>;
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 overflow-x-hidden">
        <div className="flex justify-end border-b border-slate-200 bg-white px-6 py-2">
          <button
            className="text-xs font-medium text-slate-500 hover:text-slate-800"
            onClick={() => {
              clearToken();
              router.replace("/login");
            }}
          >
            Sign out
          </button>
        </div>
        <div className="mx-auto max-w-7xl px-6 py-8">{children}</div>
      </main>
    </div>
  );
}
