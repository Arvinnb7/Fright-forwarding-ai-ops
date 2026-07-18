"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Issue, ISSUE_TYPES } from "@/lib/types";
import { RequireAuth } from "@/components/RequireAuth";
import { Button, CopyButton, ErrorText, Panel, TextArea } from "@/components/ui";
import { StatusBadge } from "@/components/StatusBadge";

const SEVERITIES = ["Low", "Medium", "High", "Critical"];
const STATUSES = ["Open", "In progress", "Resolved", "Closed"];

function Issues() {
  const [items, setItems] = useState<Issue[]>([]);
  const [openOnly, setOpenOnly] = useState(true);
  const [selected, setSelected] = useState<Issue | null>(null);
  const [draft, setDraft] = useState("");
  const [draftKind, setDraftKind] = useState("escalation");
  const [form, setForm] = useState({
    issue_type: ISSUE_TYPES[0],
    severity: "Medium",
    description: "",
    booking_id: "",
  });
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  function load() {
    api
      .get<Issue[]>(`/api/issues${openOnly ? "?open_only=true" : ""}`)
      .then(setItems)
      .catch(() => {});
  }
  useEffect(load, [openOnly]);

  async function create() {
    setError("");
    try {
      await api.post("/api/issues", {
        ...form,
        booking_id: form.booking_id ? Number(form.booking_id) : null,
      });
      setForm({ ...form, description: "" });
      load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function setStatus(issue: Issue, status: string) {
    await api.patch(`/api/issues/${issue.id}`, { status });
    load();
  }

  async function genDraft() {
    if (!selected) return;
    setBusy("draft");
    setError("");
    try {
      const r = await api.post<{ draft: string }>(`/api/issues/${selected.id}/draft`, {
        kind: draftKind,
      });
      setDraft(r.draft);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900">Issues / Exceptions</h1>
        <label className="flex items-center gap-2 text-sm text-slate-600">
          <input type="checkbox" checked={openOnly} onChange={(e) => setOpenOnly(e.target.checked)} />
          Open only
        </label>
      </div>
      <ErrorText>{error}</ErrorText>

      <Panel title="Log an issue">
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-5">
          <select className="rounded-md border border-slate-300 px-2 py-2 text-sm" value={form.issue_type} onChange={(e) => setForm({ ...form, issue_type: e.target.value })}>
            {ISSUE_TYPES.map((t) => (<option key={t}>{t}</option>))}
          </select>
          <select className="rounded-md border border-slate-300 px-2 py-2 text-sm" value={form.severity} onChange={(e) => setForm({ ...form, severity: e.target.value })}>
            {SEVERITIES.map((s) => (<option key={s}>{s}</option>))}
          </select>
          <input className="rounded-md border border-slate-300 px-3 py-2 text-sm sm:col-span-2" placeholder="Description" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          <div className="flex gap-2">
            <input className="w-24 rounded-md border border-slate-300 px-2 py-2 text-sm" placeholder="Job #id" value={form.booking_id} onChange={(e) => setForm({ ...form, booking_id: e.target.value })} />
            <Button onClick={create}>Log</Button>
          </div>
        </div>
      </Panel>

      <Panel title="Issues">
        {items.length === 0 ? (
          <p className="text-sm text-slate-500">No issues — smooth sailing.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase text-slate-500">
                <th className="py-1">Type</th>
                <th>Severity</th>
                <th>Description</th>
                <th>Job</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {items.map((i) => (
                <tr key={i.id} className="border-t border-slate-100">
                  <td className="py-2 font-medium text-slate-800">{i.issue_type}</td>
                  <td><StatusBadge value={i.severity} /></td>
                  <td className="text-slate-500">{i.description ?? ""}</td>
                  <td>{i.booking_id ?? "—"}</td>
                  <td>
                    <select
                      className="rounded-md border border-slate-300 px-2 py-1 text-xs"
                      value={i.status}
                      onChange={(e) => setStatus(i, e.target.value)}
                    >
                      {STATUSES.map((s) => (<option key={s}>{s}</option>))}
                    </select>
                  </td>
                  <td className="text-right">
                    <Button variant="ghost" onClick={() => { setSelected(i); setDraft(""); }}>
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
          title={`Draft message for: ${selected.issue_type}`}
          actions={
            <div className="flex gap-2">
              <select className="rounded-md border border-slate-300 px-2 py-1 text-sm" value={draftKind} onChange={(e) => setDraftKind(e.target.value)}>
                <option value="escalation">escalation</option>
                <option value="customer_explanation">customer_explanation</option>
              </select>
              <Button variant="secondary" onClick={genDraft} disabled={busy === "draft"}>
                {busy === "draft" ? "Drafting…" : "Generate"}
              </Button>
            </div>
          }
        >
          {draft ? (
            <div className="space-y-2">
              <TextArea value={draft} onChange={setDraft} rows={9} />
              <CopyButton text={draft} />
            </div>
          ) : (
            <p className="text-sm text-slate-500">
              Generate an escalation message or a customer explanation for this issue.
            </p>
          )}
        </Panel>
      )}
    </div>
  );
}

export default function IssuesPage() {
  return (
    <RequireAuth>
      <Issues />
    </RequireAuth>
  );
}
