"use client";

import { useEffect, useState } from "react";
import { api, downloadFile, uploadFile } from "@/lib/api";
import { LaneCoverage, TariffImportResult } from "@/lib/types";
import { RequireAuth } from "@/components/RequireAuth";
import { Button, ErrorText, Panel } from "@/components/ui";

function Rates() {
  const [lanes, setLanes] = useState<LaneCoverage[]>([]);
  const [result, setResult] = useState<TariffImportResult | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");

  function load() {
    api
      .get<LaneCoverage[]>("/api/rates/lanes")
      .then(setLanes)
      .catch(() => setLanes([]));
  }
  useEffect(load, []);

  async function importSheet(file: File) {
    setError("");
    setResult(null);
    setUploading(true);
    try {
      setResult(await uploadFile<TariffImportResult>("/api/rates/tariff/import", file));
      load();
    } catch (e) {
      setError((e as Error).message || "Import failed.");
    } finally {
      setUploading(false);
    }
  }

  const instantLanes = lanes.filter((lane) => lane.live_rate_count > 0).length;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Rates &amp; lanes</h1>
        <p className="mt-1 text-sm text-slate-500">
          A lane you already have a rate for can be quoted straight away. On a
          lane you do not, the clock keeps running while you wait for a partner
          to reply. Rate-request messages and rate comparison stay inside each
          RFQ.
        </p>
      </div>

      <Panel
        title="Load a rate sheet"
        actions={
          <Button
            variant="secondary"
            onClick={() =>
              downloadFile(
                "/api/rates/tariff/template.csv",
                "tariff-template.csv"
              ).catch((e) => setError((e as Error).message))
            }
          >
            Download template
          </Button>
        }
      >
        <p className="mb-3 text-sm text-slate-600">
          Upload a CSV of your contract rates. Required columns:{" "}
          <code className="rounded bg-slate-100 px-1 text-xs">
            origin, destination, partner_name, cost_amount
          </code>
          . Re-uploading the same sheet is safe — unchanged rows are skipped, not
          duplicated, and any row that cannot be read is reported with its line
          number rather than dropped.
        </p>
        <label className="inline-flex cursor-pointer items-center rounded-md bg-brand-600 px-3 py-2 text-sm font-medium text-white hover:bg-brand-700">
          {uploading ? "Importing…" : "Choose CSV file"}
          <input
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              e.target.value = "";
              if (file) importSheet(file);
            }}
          />
        </label>

        {result && (
          <div className="mt-3 text-sm">
            <p className="text-slate-700">
              {result.created} rate{result.created === 1 ? "" : "s"} added
              {result.skipped_duplicates > 0 &&
                ` · ${result.skipped_duplicates} already present`}
              {result.rejected > 0 && ` · ${result.rejected} rejected`}
            </p>
            {result.errors.length > 0 && (
              <ul className="mt-2 space-y-1 rounded-md bg-rose-50 p-3 text-xs text-rose-700">
                {result.errors.map((rowError) => (
                  <li key={rowError.line}>
                    Line {rowError.line}: {rowError.reason}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
        <div className="mt-2">
          <ErrorText>{error}</ErrorText>
        </div>
      </Panel>

      <Panel
        title={`Lane coverage (${lanes.length})`}
        actions={
          lanes.length > 0 ? (
            <span className="text-xs text-slate-500">
              {instantLanes} quotable from a live rate
            </span>
          ) : undefined
        }
      >
        {lanes.length === 0 ? (
          <p className="text-sm text-slate-500">
            No rates recorded yet. Rates entered against an RFQ build this list
            automatically; a rate sheet fills it in one step.
          </p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase text-slate-500">
                <th className="py-1">Lane</th>
                <th>Enquiries</th>
                <th>Live / total rates</th>
                <th>Partners</th>
                <th>Median cost</th>
                <th>Newest</th>
              </tr>
            </thead>
            <tbody>
              {lanes.map((lane) => (
                <tr key={lane.lane_key} className="border-t border-slate-100">
                  <td className="py-2 font-medium text-slate-800">
                    {lane.lane}
                    {lane.live_rate_count === 0 && (
                      <span className="ml-2 rounded bg-amber-100 px-1 text-xs font-normal text-amber-800">
                        all expired
                      </span>
                    )}
                  </td>
                  <td className="text-slate-600">{lane.enquiries}</td>
                  <td className="text-slate-600">
                    {lane.live_rate_count}/{lane.rate_count}
                  </td>
                  <td className="text-slate-600">{lane.partner_count}</td>
                  <td className="text-slate-700">{lane.median_cost ?? "—"}</td>
                  <td className="text-slate-500">
                    {lane.newest_rate_days === null
                      ? "—"
                      : lane.newest_rate_days === 0
                        ? "today"
                        : `${lane.newest_rate_days}d ago`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </div>
  );
}

export default function RatesPage() {
  return (
    <RequireAuth>
      <Rates />
    </RequireAuth>
  );
}
