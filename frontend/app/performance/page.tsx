"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, downloadFile } from "@/lib/api";
import { PerformanceReport } from "@/lib/types";
import { RequireAuth } from "@/components/RequireAuth";
import { Button, ErrorText, Panel } from "@/components/ui";
import { StatCard } from "@/components/StatCard";

const RANGES = [
  { label: "7 days", days: 7 },
  { label: "30 days", days: 30 },
  { label: "90 days", days: 90 },
];

/** Industry-typical figures for context. Clearly labelled as benchmarks, not
 *  measurements — a dashboard that blurs that line cannot be trusted with the
 *  numbers next to it. */
const BENCHMARK = {
  responseRate: 31,
  medianHours: 90,
};

function pct(value: number | null): string {
  return value === null ? "—" : `${value}%`;
}

function hours(value: number | null): string {
  if (value === null) return "—";
  if (value < 1) return `${Math.round(value * 60)} min`;
  if (value < 48) return `${value.toFixed(1)} h`;
  return `${(value / 24).toFixed(1)} days`;
}

function Bar({ value, max, tone }: { value: number; max: number; tone: string }) {
  const width = max > 0 ? Math.max((value / max) * 100, value > 0 ? 3 : 0) : 0;
  return (
    <div className="h-2 w-full rounded-full bg-slate-100">
      <div className={`h-2 rounded-full ${tone}`} style={{ width: `${width}%` }} />
    </div>
  );
}

function Performance() {
  const [days, setDays] = useState(30);
  const [report, setReport] = useState<PerformanceReport | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get<PerformanceReport>(`/api/reports/performance?days=${days}`)
      .then((r) => {
        setReport(r);
        setError("");
      })
      .catch((e) => setError((e as Error).message));
  }, [days]);

  if (error) return <ErrorText>{error}</ErrorText>;
  if (!report) return <p className="text-sm text-slate-500">Loading…</p>;

  const noData = report.rfqs_received === 0;
  const maxDaily = Math.max(1, ...report.daily.map((d) => d.rfqs));
  const maxBucket = Math.max(1, ...report.win_rate_by_response_time.map((b) => b.quoted));

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Performance</h1>
          <p className="mt-1 text-sm text-slate-500">
            How fast enquiries are answered, and what that does to the win rate.
            {" "}
            {report.start_date} → {report.end_date}.
          </p>
        </div>
        <div className="flex gap-2">
          {RANGES.map((range) => (
            <Button
              key={range.days}
              variant={days === range.days ? "primary" : "secondary"}
              onClick={() => setDays(range.days)}
            >
              {range.label}
            </Button>
          ))}
          <Button
            variant="secondary"
            onClick={() =>
              downloadFile(
                `/api/reports/performance.csv?days=${days}`,
                "performance.csv"
              ).catch((e) => setError((e as Error).message))
            }
          >
            CSV
          </Button>
        </div>
      </div>

      {noData ? (
        <Panel title="No enquiries in this period">
          <p className="text-sm text-slate-600">
            Once RFQs start arriving — from a connected mailbox or entered by
            hand — response rate, response time and win rate by speed appear
            here.
          </p>
          <div className="mt-3">
            <Link href="/settings/mailbox">
              <Button>Connect a mailbox</Button>
            </Link>
          </div>
        </Panel>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              label="Response rate"
              value={pct(report.response_rate)}
              hint={`${report.rfqs_quoted} of ${report.rfqs_received} enquiries answered`}
            />
            <StatCard
              label="Median response"
              value={hours(report.median_response_hours)}
              hint={`90th percentile ${hours(report.p90_response_hours)}`}
            />
            <StatCard
              label="Unanswered"
              value={report.unanswered_total}
              hint="Still waiting for a first quotation"
            />
            <StatCard
              label="Win rate"
              value={pct(report.win_rate)}
              hint={`${report.quotes_won} won / ${report.quotes_lost} lost (decided)`}
            />
          </div>

          <Panel title="Win rate by response speed">
            <p className="mb-3 text-sm text-slate-500">
              Your own numbers, bucketed by how quickly the first quotation went
              out. This is the argument for speed — or the evidence against it.
            </p>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-slate-500">
                  <th className="py-1">Answered within</th>
                  <th className="w-1/3">Enquiries</th>
                  <th>Quoted</th>
                  <th>Won</th>
                  <th>Win rate</th>
                </tr>
              </thead>
              <tbody>
                {report.win_rate_by_response_time.map((bucket) => (
                  <tr key={bucket.label} className="border-t border-slate-100">
                    <td className="py-2 font-medium text-slate-800">{bucket.label}</td>
                    <td className="pr-4">
                      <Bar value={bucket.quoted} max={maxBucket} tone="bg-brand-500" />
                    </td>
                    <td className="text-slate-600">{bucket.quoted}</td>
                    <td className="text-slate-600">{bucket.won}</td>
                    <td className="font-medium text-slate-800">
                      {bucket.win_rate === null ? (
                        <span className="text-slate-400">no data</span>
                      ) : (
                        `${bucket.win_rate}%`
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>

          {report.unanswered_rfqs.length > 0 && (
            <Panel
              title={`Unanswered enquiries (${report.unanswered_total})`}
              actions={
                <span className="text-xs text-slate-500">longest wait first</span>
              }
            >
              <p className="mb-3 text-sm text-slate-500">
                Each of these is a quotation a competitor is writing instead.
              </p>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase text-slate-500">
                    <th className="py-1">Ref</th>
                    <th>Lane</th>
                    <th>Waiting</th>
                  </tr>
                </thead>
                <tbody>
                  {report.unanswered_rfqs.map((rfq) => (
                    <tr key={rfq.rfq_id} className="border-t border-slate-100 hover:bg-slate-50">
                      <td className="py-2">
                        <Link
                          className="text-brand-600 hover:underline"
                          href={`/rfqs/${rfq.rfq_id}`}
                        >
                          {rfq.reference ?? `#${rfq.rfq_id}`}
                        </Link>
                      </td>
                      <td className="text-slate-700">{rfq.lane}</td>
                      <td className="text-slate-600">{hours(rfq.waiting_hours)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Panel>
          )}

          <div className="grid gap-4 lg:grid-cols-2">
            <Panel title="Throughput">
              <dl className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <dt className="text-slate-500">Quotations sent</dt>
                  <dd className="font-medium text-slate-800">{report.quotes_sent}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-slate-500">Per day</dt>
                  <dd className="font-medium text-slate-800">{report.quotes_per_day}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-slate-500">
                    Per person per day ({report.active_users} active)
                  </dt>
                  <dd className="font-medium text-slate-800">
                    {report.quotes_per_user_per_day ?? "—"}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-slate-500">Follow-up compliance</dt>
                  <dd className="font-medium text-slate-800">
                    {pct(report.follow_up_compliance)}
                    <span className="ml-1 text-xs font-normal text-slate-400">
                      ({report.follow_ups_actioned}/{report.follow_ups_due})
                    </span>
                  </dd>
                </div>
              </dl>
            </Panel>

            <Panel title="Against the industry benchmark">
              <p className="mb-3 text-xs text-slate-500">
                Industry-typical figures for freight forwarding, shown for
                context. These are published benchmarks, not measurements of
                your business — only the left column is your data.
              </p>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase text-slate-500">
                    <th className="py-1"></th>
                    <th>You</th>
                    <th>Typical</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-t border-slate-100">
                    <td className="py-2 text-slate-600">Enquiries answered</td>
                    <td className="font-medium text-slate-900">
                      {pct(report.response_rate)}
                    </td>
                    <td className="text-slate-500">~{BENCHMARK.responseRate}%</td>
                  </tr>
                  <tr className="border-t border-slate-100">
                    <td className="py-2 text-slate-600">Median response</td>
                    <td className="font-medium text-slate-900">
                      {hours(report.median_response_hours)}
                    </td>
                    <td className="text-slate-500">~{BENCHMARK.medianHours} h</td>
                  </tr>
                </tbody>
              </table>
            </Panel>
          </div>

          <Panel title="Daily volume">
            <div className="space-y-1">
              {report.daily.map((point) => (
                <div key={point.date} className="flex items-center gap-3 text-xs">
                  <span className="w-20 shrink-0 text-slate-500">{point.date}</span>
                  <div className="flex-1">
                    <Bar value={point.rfqs} max={maxDaily} tone="bg-brand-500" />
                  </div>
                  <span className="w-28 shrink-0 text-right text-slate-500">
                    {point.rfqs} in · {point.quoted} quoted
                  </span>
                  <span className="w-20 shrink-0 text-right text-slate-400">
                    {point.median_response_hours === null
                      ? "—"
                      : hours(point.median_response_hours)}
                  </span>
                </div>
              ))}
            </div>
          </Panel>
        </>
      )}
    </div>
  );
}

export default function PerformancePage() {
  return (
    <RequireAuth>
      <Performance />
    </RequireAuth>
  );
}
