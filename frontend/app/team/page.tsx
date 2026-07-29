"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { AuditEvent, Member, USER_ROLES, UserRole } from "@/lib/types";
import { RequireAuth } from "@/components/RequireAuth";
import { Button, ErrorText, Panel } from "@/components/ui";

function when(iso: string): string {
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return new Date(iso).toLocaleDateString();
}

function InviteForm({ onDone }: { onDone: () => void }) {
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<UserRole>("coordinator");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit() {
    setError("");
    setBusy(true);
    try {
      await api.post("/api/auth/users", {
        email,
        full_name: fullName || null,
        password,
        role,
      });
      setEmail("");
      setFullName("");
      setPassword("");
      onDone();
    } catch (e) {
      setError((e as Error).message || "Could not add the member.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-5">
        <input
          className="rounded-md border border-slate-300 px-2 py-1 text-sm sm:col-span-2"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <input
          className="rounded-md border border-slate-300 px-2 py-1 text-sm"
          placeholder="Full name"
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
        />
        <input
          className="rounded-md border border-slate-300 px-2 py-1 text-sm"
          type="password"
          placeholder="Initial password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <select
          className="rounded-md border border-slate-300 px-2 py-1 text-sm"
          value={role}
          onChange={(e) => setRole(e.target.value as UserRole)}
        >
          {USER_ROLES.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
        </select>
      </div>
      <div className="mt-2 flex items-center gap-3">
        <Button onClick={submit} disabled={busy || !email || password.length < 8}>
          {busy ? "Adding…" : "Add member"}
        </Button>
        <span className="text-xs text-slate-500">
          They can change the password after their first sign-in.
        </span>
      </div>
      <div className="mt-1">
        <ErrorText>{error}</ErrorText>
      </div>
    </div>
  );
}

function Team() {
  const [members, setMembers] = useState<Member[]>([]);
  const [me, setMe] = useState<Member | null>(null);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [error, setError] = useState("");

  function load() {
    api.get<Member[]>("/api/auth/users").then(setMembers).catch(() => setMembers([]));
    api.get<AuditEvent[]>("/api/audit?limit=50").then(setEvents).catch(() => setEvents([]));
  }
  useEffect(() => {
    api.get<Member>("/api/auth/me").then(setMe).catch(() => {});
    load();
  }, []);

  const isAdmin = me?.role === "admin";

  async function update(member: Member, patch: Partial<Member>) {
    setError("");
    try {
      await api.patch(`/api/auth/users/${member.id}`, patch);
      load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Team</h1>
        <p className="mt-1 text-sm text-slate-500">
          Who works here, what they may do, and a record of every pricing,
          status and permission change.
        </p>
      </div>

      {isAdmin && (
        <Panel title="Add a member">
          <InviteForm onDone={load} />
        </Panel>
      )}

      <Panel title={`Members (${members.length})`}>
        <ErrorText>{error}</ErrorText>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase text-slate-500">
              <th className="py-1">Name</th>
              <th>Email</th>
              <th>Role</th>
              <th>Status</th>
              {isAdmin && <th></th>}
            </tr>
          </thead>
          <tbody>
            {members.map((member) => {
              const isMe = member.id === me?.id;
              return (
                <tr key={member.id} className="border-t border-slate-100">
                  <td className="py-2 font-medium text-slate-800">
                    {member.full_name ?? "—"}
                    {isMe && <span className="ml-2 text-xs text-slate-400">you</span>}
                  </td>
                  <td className="text-slate-600">{member.email}</td>
                  <td>
                    {isAdmin && !isMe ? (
                      <select
                        className="rounded-md border border-slate-300 px-2 py-1 text-xs"
                        value={member.role}
                        onChange={(e) =>
                          update(member, { role: e.target.value as UserRole })
                        }
                      >
                        {USER_ROLES.map((r) => (
                          <option key={r.value} value={r.value}>
                            {r.label}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <span className="text-slate-700">
                        {USER_ROLES.find((r) => r.value === member.role)?.label ??
                          member.role}
                      </span>
                    )}
                  </td>
                  <td
                    className={member.is_active ? "text-green-700" : "text-slate-400"}
                  >
                    {member.is_active ? "Active" : "Deactivated"}
                  </td>
                  {isAdmin && (
                    <td className="text-right">
                      {!isMe && (
                        <Button
                          variant={member.is_active ? "secondary" : "primary"}
                          onClick={() =>
                            update(member, { is_active: !member.is_active })
                          }
                        >
                          {member.is_active ? "Deactivate" : "Reactivate"}
                        </Button>
                      )}
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
        <div className="mt-4 space-y-1 text-xs text-slate-500">
          {USER_ROLES.map((r) => (
            <div key={r.value}>
              <strong className="text-slate-600">{r.label}</strong> — {r.description}
            </div>
          ))}
        </div>
      </Panel>

      <Panel
        title="Activity"
        actions={<span className="text-xs text-slate-500">most recent first</span>}
      >
        {events.length === 0 ? (
          <p className="text-sm text-slate-500">
            Nothing recorded yet. Pricing, status and permission changes appear
            here automatically.
          </p>
        ) : (
          <ul className="space-y-2 text-sm">
            {events.map((event) => (
              <li
                key={event.id}
                className="flex items-start justify-between gap-4 border-b border-slate-100 pb-2"
              >
                <div>
                  <div className="text-slate-800">{event.summary}</div>
                  <div className="text-xs text-slate-400">
                    {event.actor} · {event.entity_type}
                    {event.entity_ref ? ` ${event.entity_ref}` : ""}
                  </div>
                </div>
                <span className="shrink-0 text-xs text-slate-400">
                  {when(event.created_at)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}

export default function TeamPage() {
  return (
    <RequireAuth>
      <Team />
    </RequireAuth>
  );
}
