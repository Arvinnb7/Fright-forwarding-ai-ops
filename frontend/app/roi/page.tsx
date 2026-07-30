"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, downloadFile } from "@/lib/api";
import { RoiReport } from "@/lib/types";
import { RequireAuth } from "@/components/RequireAuth";
import { Button, ErrorText, Panel } from "@/components/ui";
import { StatCard } from "@/components/StatCard";

function money(value: number): string {
  return value.toLocaleString(undefined, {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
}

function hours(value: number | null): string {
  if (value === null) return "—";
  if (value < 1) return `${Math.round(value * 60)} min`;
  if (value < 48) return `${value.toFixed(1)} h`;
  return `${(value / 24).toFixed(1)} days`;
}

function Roi() {
  const [days, setDays] = useState(90);
  const [profit, setProfit] = useState("400");
  const [fastHours, setFastHours] = useState("4");
  const [seatPrice, setSeatPrice] = useState("99");
  const [report, setReport] = useState<RoiReport | null>(null);
  const [error, setError] = useState("");

  const query = () =>
    new URLSearchParams({
      days: String(days),
      gross_profit_per_shipment: profit || "0",
      fast_response_hours: fastHours || "4",
      subscription_per_user_per_month: seatPrice || "0",
    }).toString();

  useEffect(() => {
    api
      .get<RoiReport>(`/api/reports/roi?${query()}`)
      .then((r) => {
        setReport(r);
        setError("");
      })
      .catch((e) => setError((e as Error).message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [days, profit, fastHours, seatPrice]);

  if (error) return <ErrorText>{error}</ErrorText>;
  if (!report) return <p className="text-sm text-slate-500">Loading…</p>;

  const { measured, projection } = report;
  const noBenefit = projection !== null && projection.uplift_points <= 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">
            What answering faster is worth
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-500">
            Built from your own records. The projection uses{" "}
            <strong>your</strong> win rates by response speed — no industry
            averages enter the arithmetic, and if faster answers do not convert
            better here, this page says so.
          </p>
        </div>
        <div className="flex gap-2">
          {[30, 90, 180].map((option) => (
            <Button
              key={option}
              variant={days === option ? "primary" : "secondary"}
              onClick={() => setDays(option)}
            >
              {option}d
            </Button>
          ))}
          <Button
            variant="secondary"
            onClick={() =>
              downloadFile(
                `/api/reports/roi.pdf?${query()}`,
                "response-time-review.pdf"
              ).catch((e) => setError((e as Error).message))
            }
          >
            One-pager
          </Button>
        </div>
      </div>

      <Panel title="Measured — from your records">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            label="Enquiries received"
            value={measured.enquiries_received}
            hint={`${measured.enquiries_per_working_day}/day over ${measured.window_days} days`}
          />
          <StatCard
            label="Answered"
            value={
              measured.response_rate === null ? "—" : `${measured.response_rate}%`
            }
            hint={`${measured.enquiries_unanswered} never answered`}
          />
          <StatCard
            label="Median response"
            value={hours(measured.median_response_hours)}
            hint={`p90 ${hours(measured.p90_response_hours)}`}
          />
          <StatCard
            label="Won / lost"
            value={`${measured.quotes_won} / ${measured.quotes_lost}`}
            hint={measured.win_rate === null ? "no decided quotes" : `${measured.win_rate}% win rate`}
          />
        </div>
      </Panel>

      <Panel title="Assumed — change these if they are wrong">
        <div className="grid gap-4 sm:grid-cols-3">
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-slate-500">
              Gross profit per shipment (USD)
            </span>
            <input
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              value={profit}
              onChange={(e) => setProfit(e.target.value.replace(/[^0-9.]/g, ""))}
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-slate-500">
              &quot;Fast&quot; means answered within (hours)
            </span>
            <input
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              value={fastHours}
              onChange={(e) => setFastHours(e.target.value.replace(/[^0-9.]/g, ""))}
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-slate-500">
              Subscription per user per month (USD)
            </span>
            <input
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              value={seatPrice}
              onChange={(e) => setSeatPrice(e.target.value.replace(/[^0-9.]/g, ""))}
            />
          </label>
        </div>
        <p className="mt-3 text-xs text-slate-500">
          Only these three are assumptions. Everything above and below is
          measured.
        </p>
      </Panel>

      {projection === null ? (
        <Panel title="Not enough history to put a number on this yet">
          <ul className="space-y-1 text-sm text-slate-700">
            {report.blockers.map((blocker) => (
              <li key={blocker}>• {blocker}</li>
            ))}
          </ul>
          <p className="mt-3 text-sm text-slate-500">
            The measured figures above are already real. Keep going for a few
            more weeks — a projection built on this little data would be a guess.
          </p>
        </Panel>
      ) : noBenefit ? (
        <Panel title="Your data does not show speed winning more deals">
          <div className="space-y-2 text-sm text-slate-700">
            {report.narrative.map((line, index) => (
              <p key={index}>{line}</p>
            ))}
          </div>
          <p className="mt-3 text-sm text-slate-500">
            That is a real result, not a bug. Look at pricing or lane coverage
            before investing in being faster.
          </p>
        </Panel>
      ) : (
        <>
          <Panel title="Projected — your win rates applied to every enquiry">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatCard
                label="Win rate when fast"
                value={`${projection.fast_win_rate}%`}
                hint={`vs ${projection.slow_win_rate}% when slower`}
              />
              <StatCard
                label="Extra shipments / year"
                value={projection.additional_wins_per_year}
                hint="if every enquiry were answered that fast"
              />
              <StatCard
                label="Additional gross profit"
                value={money(projection.annual_gross_profit)}
                hint="per year, at your stated profit per shipment"
              />
              <StatCard
                label="Net of subscription"
                value={money(projection.net_annual_value)}
                hint={`${money(projection.annual_subscription)} for ${projection.seats} seat(s)`}
              />
            </div>
          </Panel>

          <Panel title="In plain words">
            <div className="space-y-2 text-sm text-slate-700">
              {report.narrative.map((line, index) => (
                <p key={index}>{line}</p>
              ))}
            </div>
            <p className="mt-4 border-t border-slate-100 pt-3 text-xs text-slate-500">
              Confidence: {report.confidence}. The projection assumes every
              enquiry could be answered within{" "}
              {report.assumptions.fast_response_hours}h and would convert at the
              rate this desk already achieves when it is fast. It does not assume
              any improvement the data has not already shown.
            </p>
          </Panel>
        </>
      )}

      <p className="text-xs text-slate-400">
        See also{" "}
        <Link className="text-brand-600 hover:underline" href="/performance">
          Performance
        </Link>{" "}
        for the full response-time breakdown.
      </p>
    </div>
  );
}

export default function RoiPage() {
  return (
    <RequireAuth>
      <Roi />
    </RequireAuth>
  );
}
