import { StatCard } from "@/components/StatCard";

// Phase 1 dashboard skeleton. The cards below mirror the spec's dashboard
// overview; they are wired to live metrics in a later phase.
const CARDS = [
  { label: "Today's RFQs", value: "—", hint: "Inquiries received today" },
  { label: "Quotes Sent", value: "—", hint: "Quotations sent today" },
  { label: "Pending Rates", value: "—", hint: "Awaiting partner replies" },
  { label: "Follow-ups Due", value: "—", hint: "Need action today" },
  { label: "Confirmed Bookings", value: "—", hint: "Won this week" },
  { label: "Estimated Pipeline", value: "—", hint: "Active opportunity value" },
  { label: "Estimated Margin", value: "—", hint: "Expected gross margin" },
  { label: "Operational Issues", value: "—", hint: "Open exceptions" },
];

export default function DashboardPage() {
  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-slate-900">Dashboard</h1>
        <p className="mt-1 text-sm text-slate-500">
          A fast overview of your commercial and operational workload.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {CARDS.map((c) => (
          <StatCard key={c.label} label={c.label} value={c.value} hint={c.hint} />
        ))}
      </div>

      <div className="mt-8 rounded-lg border border-dashed border-slate-300 bg-white p-6 text-sm text-slate-500">
        <p className="font-medium text-slate-700">Getting started</p>
        <p className="mt-1">
          The backend, database, AI agents and infrastructure are in place. The
          RFQ Inbox, rate comparison, quotation builder and follow-up center are
          delivered in the next phase. Open the API docs at{" "}
          <a
            className="text-brand-600 underline"
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noreferrer"
          >
            localhost:8000/docs
          </a>{" "}
          to try the RFQ parser endpoint.
        </p>
      </div>
    </div>
  );
}
