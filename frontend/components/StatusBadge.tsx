const COLORS: Record<string, string> = {
  New: "bg-slate-100 text-slate-700",
  Incomplete: "bg-amber-100 text-amber-800",
  "Ready for pricing": "bg-blue-100 text-blue-800",
  "Waiting for customer info": "bg-amber-100 text-amber-800",
  "Waiting for partner rates": "bg-indigo-100 text-indigo-800",
  Quoted: "bg-violet-100 text-violet-800",
  "Follow-up due": "bg-orange-100 text-orange-800",
  Won: "bg-green-100 text-green-800",
  Lost: "bg-rose-100 text-rose-800",
  Cancelled: "bg-slate-100 text-slate-500",
  High: "bg-orange-100 text-orange-800",
  Critical: "bg-rose-100 text-rose-800",
};

export function StatusBadge({ value }: { value: string }) {
  const cls = COLORS[value] ?? "bg-slate-100 text-slate-700";
  return (
    <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${cls}`}>
      {value}
    </span>
  );
}
