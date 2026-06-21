"use client";

// The differentiating coach-facing panel (doc 09 §7): plain-language SHAP
// findings already computed offline by the surrogate. We render the strings as
// data — the API never runs LightGBM/SHAP in the request (ADR-008). A "how?"
// affordance links to the methodology of record.

export interface InsightsPanelProps {
  insights: readonly string[];
  methodHref?: string;
}

export function InsightsPanel({
  insights,
  methodHref = "/docs/09-optimization-methodology",
}: InsightsPanelProps) {
  return (
    <section data-testid="insights" className="flex flex-col gap-2">
      <header className="flex items-baseline justify-between">
        <h3 className="text-sm font-semibold tracking-tight">What the search found</h3>
        <a href={methodHref} className="font-mono text-[10px] text-(--color-signal)/80 underline">
          how?
        </a>
      </header>
      {insights.length === 0 ? (
        <p className="font-mono text-xs opacity-50">no surrogate insights for this study</p>
      ) : (
        <ul className="flex flex-col gap-1.5">
          {insights.map((line, i) => (
            <li key={i} className="flex gap-2 text-sm">
              <span aria-hidden className="text-(--color-signal)">
                →
              </span>
              <span>{line}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
