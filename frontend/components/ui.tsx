"use client";

import { useState } from "react";

export function Button({
  children,
  onClick,
  type = "button",
  variant = "primary",
  disabled = false,
}: {
  children: React.ReactNode;
  onClick?: () => void;
  type?: "button" | "submit";
  variant?: "primary" | "secondary" | "danger" | "ghost";
  disabled?: boolean;
}) {
  const base =
    "inline-flex items-center justify-center rounded-md px-3 py-2 text-sm font-medium transition disabled:opacity-50 disabled:cursor-not-allowed";
  const styles = {
    primary: "bg-brand-600 text-white hover:bg-brand-700",
    secondary: "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50",
    danger: "bg-rose-600 text-white hover:bg-rose-700",
    ghost: "text-slate-600 hover:bg-slate-100",
  }[variant];
  return (
    <button type={type} onClick={onClick} disabled={disabled} className={`${base} ${styles}`}>
      {children}
    </button>
  );
}

export function Panel({
  title,
  children,
  actions,
}: {
  title?: string;
  children: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white">
      {(title || actions) && (
        <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
          {title && <h2 className="text-sm font-semibold text-slate-800">{title}</h2>}
          {actions}
        </div>
      )}
      <div className="p-4">{children}</div>
    </div>
  );
}

export function Field({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange?: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-slate-500">{label}</span>
      <input
        className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"
        value={value}
        placeholder={placeholder}
        readOnly={!onChange}
        onChange={(e) => onChange?.(e.target.value)}
      />
    </label>
  );
}

export function TextArea({
  value,
  onChange,
  rows = 8,
}: {
  value: string;
  onChange?: (v: string) => void;
  rows?: number;
}) {
  return (
    <textarea
      className="w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-sm focus:border-brand-500 focus:outline-none"
      rows={rows}
      value={value}
      readOnly={!onChange}
      onChange={(e) => onChange?.(e.target.value)}
    />
  );
}

export function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button
      variant="secondary"
      onClick={async () => {
        await navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
    >
      {copied ? "Copied" : "Copy"}
    </Button>
  );
}

export function ErrorText({ children }: { children: React.ReactNode }) {
  if (!children) return null;
  return <p className="text-sm text-rose-600">{children}</p>;
}

export function Spinner({ label = "Working..." }: { label?: string }) {
  return <span className="text-sm text-slate-500">{label}</span>;
}
