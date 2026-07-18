"use client";

import { useEffect, useState } from "react";
import { api, API_BASE_URL, getToken } from "@/lib/api";
import { Customer, CustomerStats } from "@/lib/types";
import { RequireAuth } from "@/components/RequireAuth";
import { Button, ErrorText, Field, Panel, TextArea } from "@/components/ui";

function Customers() {
  const [items, setItems] = useState<Customer[]>([]);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Customer | null>(null);
  const [edit, setEdit] = useState<Partial<Customer>>({});
  const [profile, setProfile] = useState<{ stats: CustomerStats; summary: string } | null>(null);
  const [newCompany, setNewCompany] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  function load() {
    api
      .get<Customer[]>(`/api/customers${search ? `?search=${encodeURIComponent(search)}` : ""}`)
      .then(setItems)
      .catch(() => {});
  }
  useEffect(load, [search]);

  function select(c: Customer) {
    setSelected(c);
    setProfile(null);
    setEdit({
      company_name: c.company_name,
      contact_name: c.contact_name ?? "",
      email: c.email ?? "",
      phone: c.phone ?? "",
      country: c.country ?? "",
      city: c.city ?? "",
      industry: c.industry ?? "",
      notes: c.notes ?? "",
    });
  }

  async function create() {
    if (!newCompany.trim()) return;
    setError("");
    try {
      const c = await api.post<Customer>("/api/customers", { company_name: newCompany });
      setNewCompany("");
      load();
      select(c);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function save() {
    if (!selected) return;
    setBusy("save");
    try {
      await api.patch(`/api/customers/${selected.id}`, edit);
      load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }

  async function genProfile() {
    if (!selected) return;
    setBusy("profile");
    setError("");
    try {
      setProfile(await api.post(`/api/customers/${selected.id}/profile`));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }

  async function exportCsv() {
    const res = await fetch(`${API_BASE_URL}/api/exports/customers.csv`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "customers.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900">Customers / CRM</h1>
        <Button variant="secondary" onClick={exportCsv}>Export CSV</Button>
      </div>
      <ErrorText>{error}</ErrorText>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Panel
          title="Customers"
          actions={
            <input
              className="rounded-md border border-slate-300 px-2 py-1 text-sm"
              placeholder="Search…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          }
        >
          <div className="mb-3 flex gap-2">
            <input
              className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm"
              placeholder="New company name"
              value={newCompany}
              onChange={(e) => setNewCompany(e.target.value)}
            />
            <Button onClick={create} disabled={!newCompany.trim()}>Add</Button>
          </div>
          {items.length === 0 ? (
            <p className="text-sm text-slate-500">No customers yet.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-slate-500">
                  <th className="py-1">Company</th>
                  <th>Contact</th>
                  <th>Location</th>
                </tr>
              </thead>
              <tbody>
                {items.map((c) => (
                  <tr
                    key={c.id}
                    className={`cursor-pointer border-t border-slate-100 hover:bg-slate-50 ${
                      selected?.id === c.id ? "bg-brand-50" : ""
                    }`}
                    onClick={() => select(c)}
                  >
                    <td className="py-2 font-medium text-slate-800">{c.company_name}</td>
                    <td>{c.contact_name ?? "—"}</td>
                    <td>{[c.city, c.country].filter(Boolean).join(", ") || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>

        {selected && (
          <Panel
            title={selected.company_name}
            actions={
              <div className="flex gap-2">
                <Button variant="secondary" onClick={genProfile} disabled={busy === "profile"}>
                  {busy === "profile" ? "Analyzing…" : "AI profile"}
                </Button>
                <Button onClick={save} disabled={busy === "save"}>Save</Button>
              </div>
            }
          >
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field label="Contact" value={(edit.contact_name as string) ?? ""} onChange={(v) => setEdit({ ...edit, contact_name: v })} />
              <Field label="Email" value={(edit.email as string) ?? ""} onChange={(v) => setEdit({ ...edit, email: v })} />
              <Field label="Phone" value={(edit.phone as string) ?? ""} onChange={(v) => setEdit({ ...edit, phone: v })} />
              <Field label="Industry" value={(edit.industry as string) ?? ""} onChange={(v) => setEdit({ ...edit, industry: v })} />
              <Field label="Country" value={(edit.country as string) ?? ""} onChange={(v) => setEdit({ ...edit, country: v })} />
              <Field label="City" value={(edit.city as string) ?? ""} onChange={(v) => setEdit({ ...edit, city: v })} />
            </div>
            <div className="mt-3">
              <span className="mb-1 block text-xs font-medium text-slate-500">Notes</span>
              <TextArea value={(edit.notes as string) ?? ""} onChange={(v) => setEdit({ ...edit, notes: v })} rows={4} />
            </div>

            {profile && (
              <div className="mt-4 rounded-md bg-slate-50 p-3 text-sm">
                <p className="text-slate-700">{profile.summary}</p>
                <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-slate-500 sm:grid-cols-4">
                  <span>RFQs: {profile.stats.rfq_count}</span>
                  <span>Quotes: {profile.stats.quote_count}</span>
                  <span>Won/Lost: {profile.stats.won_count}/{profile.stats.lost_count}</span>
                  <span>Avg margin: {profile.stats.average_margin_percentage ?? "—"}%</span>
                </div>
                {profile.stats.typical_routes.length > 0 && (
                  <p className="mt-1 text-xs text-slate-500">
                    Routes: {profile.stats.typical_routes.join(" · ")}
                  </p>
                )}
              </div>
            )}
          </Panel>
        )}
      </div>
    </div>
  );
}

export default function CustomersPage() {
  return (
    <RequireAuth>
      <Customers />
    </RequireAuth>
  );
}
