"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { RequireAuth } from "@/components/RequireAuth";
import { Panel } from "@/components/ui";

interface SettingsView {
  company_name: string;
  user_full_name: string;
  email_signature: string;
  default_markup_percent: number;
  default_currency: string;
  llm_provider: string;
  llm_model: string;
  llm_key_configured: boolean;
  app_env: string;
  edit_hint: string;
}

function Settings() {
  const [s, setS] = useState<SettingsView | null>(null);

  useEffect(() => {
    api.get<SettingsView>("/api/settings").then(setS).catch(() => {});
  }, []);

  if (!s) return <p className="text-sm text-slate-500">Loading…</p>;

  const Row = ({ label, value }: { label: string; value: React.ReactNode }) => (
    <div className="flex justify-between border-b border-slate-100 py-2 text-sm">
      <span className="text-slate-500">{label}</span>
      <span className="font-medium text-slate-800">{value}</span>
    </div>
  );

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-900">Settings</h1>
      <Panel title="Company defaults">
        <Row label="Company name" value={s.company_name} />
        <Row label="Your name" value={s.user_full_name} />
        <Row label="Email signature" value={s.email_signature} />
        <Row label="Default markup" value={`${s.default_markup_percent}%`} />
        <Row label="Default currency" value={s.default_currency} />
      </Panel>
      <Panel title="AI provider">
        <Row label="Provider" value={s.llm_provider} />
        <Row label="Model" value={s.llm_model} />
        <Row
          label="API key"
          value={
            s.llm_key_configured ? (
              <span className="text-green-700">configured</span>
            ) : (
              <span className="text-rose-700">missing — set it in .env</span>
            )
          }
        />
        <Row label="Environment" value={s.app_env} />
      </Panel>
      <p className="text-sm text-slate-500">{s.edit_hint}</p>
    </div>
  );
}

export default function SettingsPage() {
  return (
    <RequireAuth>
      <Settings />
    </RequireAuth>
  );
}
