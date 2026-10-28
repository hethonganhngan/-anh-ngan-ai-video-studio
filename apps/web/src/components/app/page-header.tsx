import type { ReactNode } from "react";

export function PageHeader({ code, title, description, actions }: { code?: string; title: string; description?: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
      <div>
        {code && <p className="text-xs font-semibold uppercase tracking-wider text-brand-600">{code}</p>}
        <h1 className="text-2xl font-bold text-slate-900" data-testid="page-title">{title}</h1>
        {description && <p className="mt-1 text-sm text-slate-500">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
