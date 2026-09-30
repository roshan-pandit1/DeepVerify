"use client";

import React, { useState } from "react";
import { Globe, ExternalLink } from "lucide-react";
import { getLightShade } from "@/lib/colors";

export interface EvidenceItem {
  id: string;
  source_name: string;
  source_url?: string;
  content_snippet: string;
  stance: "supports" | "refutes" | "neutral" | string;
  credibility_score: number;
}

const STANCE_BADGES: Record<string, { label: string; bg: string; text: string }> = {
  supports: { label: "Supports Claim", bg: "#dcfce7", text: "#15803d" },
  refutes: { label: "Refutes Claim", bg: "#fee2e2", text: "#b91c1c" },
  neutral: { label: "Neutral / Background", bg: "#f1f5f9", text: "#475569" },
};

export function EvidenceSection({ items }: { items: EvidenceItem[] }) {
  const [filter, setFilter] = useState<"all" | "supports" | "refutes" | "neutral">("all");

  const filtered = items.filter((item) => (filter === "all" ? true : item.stance.toLowerCase() === filter));

  return (
    <section className="mb-8">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
        <div className="flex items-center gap-2">
          <Globe size={18} className="text-blue-600" />
          <h2 className="text-lg font-bold text-slate-900">
            Section 3: Corroborating OSINT Sources ({items.length})
          </h2>
        </div>

        {/* Filter buttons */}
        <div className="flex gap-1.5">
          {(["all", "supports", "refutes", "neutral"] as const).map((st) => (
            <button
              key={st}
              onClick={() => setFilter(st)}
              className={`px-2.5 py-1 rounded text-xs font-semibold capitalize border transition-all ${
                filter === st
                  ? "bg-blue-600 text-white border-blue-600"
                  : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
              }`}
            >
              {st}
            </button>
          ))}
        </div>
      </div>

      {filtered.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filtered.map((ev, idx) => {
            const shade = getLightShade(idx);
            const badge = STANCE_BADGES[ev.stance.toLowerCase()] || STANCE_BADGES.neutral;

            return (
              <div
                key={ev.id || idx}
                className="flash-card flex flex-col justify-between"
                style={{ backgroundColor: shade.bg, borderColor: shade.border }}
              >
                <div>
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <span className="text-xs font-bold uppercase tracking-wider" style={{ color: shade.text }}>
                      {ev.source_name}
                    </span>
                    <span
                      className="text-xs px-2 py-0.5 rounded-full font-bold"
                      style={{ backgroundColor: badge.bg, color: badge.text }}
                    >
                      {badge.label}
                    </span>
                  </div>

                  <p className="text-xs sm:text-sm text-slate-700 italic leading-relaxed">
                    &ldquo;{ev.content_snippet}&rdquo;
                  </p>
                </div>

                <div className="flex items-center justify-between pt-3 mt-3 border-t border-black/5 text-xs">
                  <span className="text-slate-500 font-medium">
                    Trust: <strong className="text-slate-900">{(ev.credibility_score * 100).toFixed(0)}%</strong>
                  </span>

                  {ev.source_url ? (
                    <a
                      href={ev.source_url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 font-bold hover:underline"
                      style={{ color: shade.accent }}
                    >
                      Source <ExternalLink size={12} />
                    </a>
                  ) : (
                    <span className="text-slate-400">Internal Search</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="card-box p-8 text-center text-slate-400 text-xs">
          No evidence items match the &ldquo;{filter}&rdquo; filter.
        </div>
      )}
    </section>
  );
}
