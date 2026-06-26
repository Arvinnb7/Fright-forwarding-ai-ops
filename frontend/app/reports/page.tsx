"use client";

import { useState } from "react";
import { api, API_BASE_URL, getToken } from "@/lib/api";
import { RequireAuth } from "@/components/RequireAuth";
import { Button, CopyButton, ErrorText, Panel, TextArea } from "@/components/ui";

function Reports() {
  const [report, setReport] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function generate() {
    setBusy(true);
    setError("");
    try {
      const r = await api.get<{ report_text: string }>("/api/reports/daily");
      setReport(r.report_text);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function downloadPdf() {
    const res = await fetch(`${API_BASE_URL}/api/reports/daily/pdf`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "daily-report.pdf";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-900">Daily Report</h1>
      <Panel
        title="Management summary"
        actions={
          <div className="flex gap-2">
            <Button onClick={generate} disabled={busy}>
              {busy ? "Generating…" : "Generate today's report"}
            </Button>
            {report && <Button variant="secondary" onClick={downloadPdf}>PDF</Button>}
          </div>
        }
      >
        <ErrorText>{error}</ErrorText>
        {report ? (
          <div className="space-y-2">
            <TextArea value={report} onChange={setReport} rows={20} />
            <CopyButton text={report} />
          </div>
        ) : (
          <p className="text-sm text-slate-500">
            Generate a clean daily commercial &amp; operations summary from today&apos;s activity.
          </p>
        )}
      </Panel>
    </div>
  );
}

export default function ReportsPage() {
  return (
    <RequireAuth>
      <Reports />
    </RequireAuth>
  );
}
