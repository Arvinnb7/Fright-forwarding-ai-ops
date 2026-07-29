"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { MailboxConfig } from "@/lib/types";
import { RequireAuth } from "@/components/RequireAuth";
import { Button, ErrorText, Panel } from "@/components/ui";

const PRESETS: Record<string, { host: string; port: number }> = {
  Gmail: { host: "imap.gmail.com", port: 993 },
  "Outlook / Microsoft 365": { host: "outlook.office365.com", port: 993 },
  Yahoo: { host: "imap.mail.yahoo.com", port: 993 },
};

function MailboxSettings() {
  const [config, setConfig] = useState<MailboxConfig | null>(null);
  const [host, setHost] = useState("");
  const [port, setPort] = useState(993);
  const [useSsl, setUseSsl] = useState(true);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [folder, setFolder] = useState("INBOX");
  const [enabled, setEnabled] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  function apply(next: MailboxConfig | null) {
    setConfig(next);
    if (!next) return;
    setHost(next.host);
    setPort(next.port);
    setUseSsl(next.use_ssl);
    setUsername(next.username);
    setFolder(next.folder);
    setEnabled(next.is_enabled);
    setPassword("");
  }

  useEffect(() => {
    api
      .get<MailboxConfig | null>("/api/mailbox/config")
      .then(apply)
      .catch(() => setConfig(null));
  }, []);

  async function save() {
    setError("");
    setMessage("");
    if (!password) {
      setError(
        config
          ? "Enter the password again to save — it is stored encrypted and cannot be read back."
          : "A password (or app password) is required."
      );
      return;
    }
    setSaving(true);
    try {
      apply(
        await api.put<MailboxConfig>("/api/mailbox/config", {
          host,
          port,
          use_ssl: useSsl,
          username,
          password,
          folder,
          is_enabled: enabled,
        })
      );
      setMessage("Saved. Mail will be checked automatically from now on.");
    } catch (e) {
      setError((e as Error).message || "Could not save the mailbox.");
    } finally {
      setSaving(false);
    }
  }

  async function testConnection() {
    setError("");
    setMessage("");
    setTesting(true);
    try {
      const res = await api.post<{ ok: boolean; detail: string }>("/api/mailbox/test");
      if (res.ok) setMessage(res.detail);
      else setError(res.detail);
    } catch (e) {
      setError((e as Error).message || "Connection test failed.");
    } finally {
      setTesting(false);
    }
  }

  async function togglePolling() {
    const next = !enabled;
    setEnabled(next);
    apply(await api.patch<MailboxConfig>("/api/mailbox/config", { is_enabled: next }));
  }

  async function disconnect() {
    if (!window.confirm("Disconnect this mailbox? Ingested messages are kept.")) return;
    await api.del("/api/mailbox/config");
    apply(null);
    setHost("");
    setUsername("");
    setMessage("Mailbox disconnected.");
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Mailbox connection</h1>
        <p className="mt-1 text-sm text-slate-500">
          Connect the mailbox where customer enquiries arrive. Access is{" "}
          <strong>read-only</strong>: mail is never sent, deleted or marked as read,
          and every draft still needs your approval.
        </p>
      </div>

      <Panel
        title={config ? "Connected mailbox" : "Connect a mailbox"}
        actions={
          config && (
            <div className="flex gap-2">
              <Button variant="secondary" onClick={togglePolling}>
                {enabled ? "Pause polling" : "Resume polling"}
              </Button>
              <Button variant="danger" onClick={disconnect}>
                Disconnect
              </Button>
            </div>
          )
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-slate-500">
              Provider preset
            </span>
            <select
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              onChange={(e) => {
                const preset = PRESETS[e.target.value];
                if (preset) {
                  setHost(preset.host);
                  setPort(preset.port);
                  setUseSsl(true);
                }
              }}
              value=""
            >
              <option value="">Choose…</option>
              {Object.keys(PRESETS).map((name) => (
                <option key={name}>{name}</option>
              ))}
            </select>
          </label>

          <label className="block">
            <span className="mb-1 block text-xs font-medium text-slate-500">
              IMAP server
            </span>
            <input
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              value={host}
              placeholder="imap.example.com"
              onChange={(e) => setHost(e.target.value)}
            />
          </label>

          <label className="block">
            <span className="mb-1 block text-xs font-medium text-slate-500">Port</span>
            <input
              type="number"
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              value={port}
              onChange={(e) => setPort(Number(e.target.value))}
            />
          </label>

          <label className="block">
            <span className="mb-1 block text-xs font-medium text-slate-500">Folder</span>
            <input
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              value={folder}
              onChange={(e) => setFolder(e.target.value)}
            />
          </label>

          <label className="block">
            <span className="mb-1 block text-xs font-medium text-slate-500">
              Email address
            </span>
            <input
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              value={username}
              placeholder="sales@yourcompany.com"
              onChange={(e) => setUsername(e.target.value)}
            />
          </label>

          <label className="block">
            <span className="mb-1 block text-xs font-medium text-slate-500">
              Password or app password
            </span>
            <input
              type="password"
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              value={password}
              placeholder={config ? "Re-enter to change" : ""}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
        </div>

        <label className="mt-4 flex items-center gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={useSsl}
            onChange={(e) => setUseSsl(e.target.checked)}
          />
          Use SSL (recommended)
        </label>

        <p className="mt-4 text-xs text-slate-500">
          Gmail and Microsoft 365 accounts with two-factor authentication need an{" "}
          <strong>app password</strong> rather than your normal one. The password is
          encrypted before it is stored and is never shown again.
        </p>

        <div className="mt-4 flex items-center gap-2">
          <Button onClick={save} disabled={saving || !host || !username}>
            {saving ? "Saving…" : config ? "Update connection" : "Connect"}
          </Button>
          {config && (
            <Button variant="secondary" onClick={testConnection} disabled={testing}>
              {testing ? "Testing…" : "Test connection"}
            </Button>
          )}
          <Link href="/inbox" className="text-sm text-brand-600 hover:underline">
            Go to inbox →
          </Link>
        </div>

        {message && <p className="mt-3 text-sm text-green-700">{message}</p>}
        <div className="mt-1">
          <ErrorText>{error}</ErrorText>
        </div>
        {config?.last_error && (
          <p className="mt-3 text-xs text-rose-600">
            Last polling error: {config.last_error}
          </p>
        )}
      </Panel>
    </div>
  );
}

export default function MailboxSettingsPage() {
  return (
    <RequireAuth>
      <MailboxSettings />
    </RequireAuth>
  );
}
