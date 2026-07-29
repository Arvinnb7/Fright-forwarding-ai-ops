const COLORS: Record<string, string> = {
  // Booking lifecycle
  "Booking confirmed": "bg-blue-100 text-blue-800",
  "Awaiting documents": "bg-amber-100 text-amber-800",
  "In transit": "bg-indigo-100 text-indigo-800",
  "Under customs clearance": "bg-amber-100 text-amber-800",
  Delivered: "bg-green-100 text-green-800",
  Closed: "bg-slate-100 text-slate-500",
  // Documents
  Required: "bg-slate-100 text-slate-700",
  Received: "bg-green-100 text-green-800",
  Missing: "bg-rose-100 text-rose-800",
  Expired: "bg-rose-100 text-rose-800",
  "Needs correction": "bg-amber-100 text-amber-800",
  // Issues
  Open: "bg-rose-100 text-rose-800",
  "In progress": "bg-amber-100 text-amber-800",
  Resolved: "bg-green-100 text-green-800",
  Medium: "bg-amber-100 text-amber-800",
  Low: "bg-slate-100 text-slate-600",
  // Quotes / misc
  "Pending approval": "bg-amber-100 text-amber-800",
  Approved: "bg-blue-100 text-blue-800",
  Sent: "bg-violet-100 text-violet-800",
  Draft: "bg-slate-100 text-slate-600",
  Pending: "bg-slate-100 text-slate-600",
  Due: "bg-orange-100 text-orange-800",
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
  // Email intake
  "New RFQ": "bg-blue-100 text-blue-800",
  "Partner rate reply": "bg-indigo-100 text-indigo-800",
  "Customer reply": "bg-violet-100 text-violet-800",
  "Not relevant": "bg-slate-100 text-slate-500",
  Unclassified: "bg-slate-100 text-slate-600",
  Processed: "bg-green-100 text-green-800",
  Ignored: "bg-slate-100 text-slate-500",
  Failed: "bg-rose-100 text-rose-800",
  Replied: "bg-green-100 text-green-800",
};

export function StatusBadge({ value }: { value: string }) {
  const cls = COLORS[value] ?? "bg-slate-100 text-slate-700";
  return (
    <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${cls}`}>
      {value}
    </span>
  );
}
