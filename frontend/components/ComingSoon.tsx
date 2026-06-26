import { RequireAuth } from "@/components/RequireAuth";

export function ComingSoon({ title, note }: { title: string; note: string }) {
  return (
    <RequireAuth>
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">{title}</h1>
        <div className="mt-4 rounded-lg border border-dashed border-slate-300 bg-white p-6 text-sm text-slate-500">
          {note}
        </div>
      </div>
    </RequireAuth>
  );
}
