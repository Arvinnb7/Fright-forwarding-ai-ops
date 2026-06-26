"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { FollowUp } from "@/lib/types";
import { RequireAuth } from "@/components/RequireAuth";
import { Button, CopyButton, ErrorText, Panel, TextArea } from "@/components/ui";
import { StatusBadge } from "@/components/StatusBadge";

const TYPES = [
  "polite",
  "short_whatsapp",
  "discount_response",
  "revised",
  "final",
  "lost_reason_request",
];

function FollowUps() {
  const [items, setItems] = useState<FollowUp[]>([]);
  const [dueOnly, setDueOnly] = useState(false);
  const [selected, setSelected] = useState<FollowUp | null>(null);
  const [type, setType] = useState(TYPES[0]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  function load() {
    api
      .get<FollowUp[]>(`/api/follow-ups${dueOnly ? "?due_only=true" : ""}`)
      .then(setItems)
      .catch(() => {});
  }
  useEffect(load, [dueOnly]);

  async function generate() {
    if (!selected) return;
    setBusy(true);
    setError("");
    try {
      const r = await api.post<{ draft: string }>(`/api/follow-ups/${selected.id}/draft`, {
        follow_up_type: type,
      });
      setDraft(r.draft);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function markSent() {
    if (!selected) return;
    await api.patch(`/api/follow-ups/${selected.id}`, { status: "Sent", sent_manually: true });
    load();
    setSelected(null);
    setDraft("");
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900">Follow-ups</h1>
        <label className="flex items-center gap-2 text-sm text-slate-600">
          <input type="checkbox" checked={dueOnly} onChange={(e) => setDueOnly(e.target.checked)} />
          Due only
        </label>
      </div>

      <Panel title="Follow-ups">
        {items.length === 0 ? (
          <p className="text-sm text-slate-500">Nothing here.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase text-slate-500">
                <th className="py-1">Quote</th>
                <th>Due</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {items.map((f) => (
                <tr key={f.id} className="border-t border-slate-100">
                  <td className="py-2">#{f.quote_id}</td>
                  <td>{f.due_date ?? "—"}</td>
                  <td>
                    <StatusBadge value={f.status} />
                  </td>
                  <td className="text-right">
                    <Button
                      variant="ghost"
                      onClick={() => {
                        setSelected(f);
                        setDraft(f.draft_message ?? "");
                      }}
                    >
                      Draft
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>

      {selected && (
        <Panel
          title={`Draft follow-up for quote #${selected.quote_id}`}
          actions={
            <div className="flex gap-2">
              <select
                className="rounded-md border border-slate-300 px-2 py-1 text-sm"
                value={type}
                onChange={(e) => setType(e.target.value)}
              >
                {TYPES.map((t) => (
                  <option key={t}>{t}</option>
                ))}
              </select>
              <Button variant="secondary" onClick={generate} disabled={busy}>
                {busy ? "Drafting…" : "Generate"}
              </Button>
            </div>
          }
        >
          <ErrorText>{error}</ErrorText>
          <TextArea value={draft} onChange={setDraft} rows={8} />
          <div className="mt-2 flex gap-2">
            <CopyButton text={draft} />
            <Button onClick={markSent}>Mark sent</Button>
          </div>
        </Panel>
      )}
    </div>
  );
}

export default function FollowUpsPage() {
  return (
    <RequireAuth>
      <FollowUps />
    </RequireAuth>
  );
}
