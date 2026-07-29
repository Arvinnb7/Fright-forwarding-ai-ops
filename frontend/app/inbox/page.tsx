"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, downloadFile } from "@/lib/api";
import {
  EMAIL_CLASSIFICATIONS,
  EmailMessage,
  IngestRunResult,
  MailboxConfig,
} from "@/lib/types";
import { RequireAuth } from "@/components/RequireAuth";
import { Button, ErrorText, Panel } from "@/components/ui";
import { StatusBadge } from "@/components/StatusBadge";

function relativeTime(iso: string | null): string {
  if (!iso) return "—";
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function MessageDetail({ message }: { message: EmailMessage }) {
  const [error, setError] = useState("");

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge value={message.classification} />
        <StatusBadge value={message.status} />
        {message.rfq_id && (
          <Link
            className="text-sm text-brand-600 hover:underline"
            href={`/rfqs/${message.rfq_id}`}
          >
            Open RFQ →
          </Link>
        )}
        {message.quote_id && (
          <Link
            className="text-sm text-brand-600 hover:underline"
            href={`/quotes/${message.quote_id}`}
          >
            Open quotation →
          </Link>
        )}
      </div>

      {message.classification_reason && (
        <p className="text-xs text-slate-500">
          Why: {message.classification_reason}
          {message.classification_confidence != null &&
            ` (confidence ${(message.classification_confidence * 100).toFixed(0)}%)`}
        </p>
      )}
      {message.error && <ErrorText>Processing failed: {message.error}</ErrorText>}

      <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-md bg-slate-50 p-3 text-sm text-slate-700">
        {message.body || "(empty message)"}
      </pre>

      {message.attachments.length > 0 && (
        <div>
          <div className="mb-1 text-xs font-medium uppercase text-slate-500">
            Attachments
          </div>
          <ul className="space-y-1 text-sm">
            {message.attachments.map((attachment, index) => (
              <li key={index} className="flex items-center gap-2">
                <span className="text-slate-700">{attachment.filename}</span>
                <span className="text-xs text-slate-400">
                  {formatSize(attachment.size_bytes)}
                </span>
                {attachment.path ? (
                  <button
                    className="text-xs text-brand-600 hover:underline"
                    onClick={() =>
                      downloadFile(
                        `/api/mailbox/messages/${message.id}/attachments/${index}`,
                        attachment.filename
                      ).catch((e) => setError((e as Error).message))
                    }
                  >
                    Download
                  </button>
                ) : (
                  <span className="text-xs text-slate-400">
                    {attachment.error ?? "not stored"}
                  </span>
                )}
              </li>
            ))}
          </ul>
          <ErrorText>{error}</ErrorText>
        </div>
      )}
    </div>
  );
}

function Inbox() {
  const [config, setConfig] = useState<MailboxConfig | null>(null);
  const [messages, setMessages] = useState<EmailMessage[]>([]);
  const [selected, setSelected] = useState<EmailMessage | null>(null);
  const [filter, setFilter] = useState("");
  const [syncing, setSyncing] = useState(false);
  const [result, setResult] = useState<IngestRunResult | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    const query = filter ? `?classification=${encodeURIComponent(filter)}` : "";
    api
      .get<EmailMessage[]>(`/api/mailbox/messages${query}`)
      .then(setMessages)
      .catch(() => setMessages([]));
  }, [filter]);

  useEffect(() => {
    api
      .get<MailboxConfig | null>("/api/mailbox/config")
      .then(setConfig)
      .catch(() => setConfig(null));
  }, []);

  useEffect(load, [load]);

  async function syncNow() {
    setError("");
    setSyncing(true);
    try {
      setResult(await api.post<IngestRunResult>("/api/mailbox/sync"));
      load();
      setConfig(await api.get<MailboxConfig | null>("/api/mailbox/config"));
    } catch (e) {
      setError((e as Error).message || "Sync failed.");
    } finally {
      setSyncing(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Email Inbox</h1>
        <p className="mt-1 text-sm text-slate-500">
          Incoming mail is read automatically and triaged. New RFQs arrive here
          already parsed — nothing is ever sent or deleted on your behalf.
        </p>
      </div>

      {!config ? (
        <Panel title="No mailbox connected">
          <p className="text-sm text-slate-600">
            Connect your sales mailbox to have RFQs picked up automatically
            instead of pasting them by hand.
          </p>
          <div className="mt-3">
            <Link href="/settings/mailbox">
              <Button>Connect a mailbox</Button>
            </Link>
          </div>
        </Panel>
      ) : (
        <Panel
          title="Mailbox"
          actions={
            <div className="flex items-center gap-2">
              <Link href="/settings/mailbox">
                <Button variant="secondary">Settings</Button>
              </Link>
              <Button onClick={syncNow} disabled={syncing || !config.is_enabled}>
                {syncing ? "Checking…" : "Check now"}
              </Button>
            </div>
          }
        >
          <div className="flex flex-wrap gap-6 text-sm">
            <div>
              <div className="text-xs uppercase text-slate-500">Account</div>
              <div className="text-slate-800">{config.username}</div>
            </div>
            <div>
              <div className="text-xs uppercase text-slate-500">Last checked</div>
              <div className="text-slate-800">{relativeTime(config.last_polled_at)}</div>
            </div>
            <div>
              <div className="text-xs uppercase text-slate-500">Automatic polling</div>
              <div className="text-slate-800">
                {config.is_enabled ? "On" : "Paused"}
              </div>
            </div>
          </div>
          {config.last_error && (
            <div className="mt-3">
              <ErrorText>Last error: {config.last_error}</ErrorText>
            </div>
          )}
          {result && (
            <p className="mt-3 text-sm text-slate-600">
              Fetched {result.fetched} · {result.rfqs_created} new RFQ
              {result.rfqs_created === 1 ? "" : "s"} · {result.rate_replies_linked} rate
              repl{result.rate_replies_linked === 1 ? "y" : "ies"} ·{" "}
              {result.customer_replies_linked} customer repl
              {result.customer_replies_linked === 1 ? "y" : "ies"} · {result.ignored}{" "}
              ignored
              {result.failed > 0 && ` · ${result.failed} failed`}
            </p>
          )}
          <ErrorText>{error}</ErrorText>
        </Panel>
      )}

      <Panel
        title={`Messages (${messages.length})`}
        actions={
          <select
            className="rounded-md border border-slate-300 px-2 py-1 text-sm"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          >
            <option value="">All types</option>
            {EMAIL_CLASSIFICATIONS.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        }
      >
        {messages.length === 0 ? (
          <p className="text-sm text-slate-500">
            Nothing ingested yet. Messages appear here within a few minutes of
            arriving.
          </p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase text-slate-500">
                <th className="py-1">Received</th>
                <th>From</th>
                <th>Subject</th>
                <th>Type</th>
                <th>Linked</th>
              </tr>
            </thead>
            <tbody>
              {messages.map((m) => (
                <tr
                  key={m.id}
                  className="cursor-pointer border-t border-slate-100 hover:bg-slate-50"
                  onClick={() => setSelected(selected?.id === m.id ? null : m)}
                >
                  <td className="py-2 text-slate-500">{relativeTime(m.received_at)}</td>
                  <td className="text-slate-700">
                    {m.from_name || m.from_address || "—"}
                  </td>
                  <td className="text-slate-800">{m.subject || "(no subject)"}</td>
                  <td>
                    <StatusBadge value={m.classification} />
                  </td>
                  <td className="text-slate-500">
                    {m.rfq_id ? `RFQ #${m.rfq_id}` : m.quote_id ? `Quote #${m.quote_id}` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>

      {selected && (
        <Panel
          title={selected.subject || "(no subject)"}
          actions={
            <Button variant="ghost" onClick={() => setSelected(null)}>
              Close
            </Button>
          }
        >
          <MessageDetail message={selected} />
        </Panel>
      )}
    </div>
  );
}

export default function InboxPage() {
  return (
    <RequireAuth>
      <Inbox />
    </RequireAuth>
  );
}
