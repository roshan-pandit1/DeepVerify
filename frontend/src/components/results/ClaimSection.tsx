"use client";

import React from "react";
import { FileText, ExternalLink } from "lucide-react";
import { getLightShade } from "@/lib/colors";

export interface Assertion {
  id: string;
  assertion_text: string;
  entities: string[];
  confidence_weight: number;
}

export interface ClaimDetail {
  id: string;
  raw_input: string;
  input_type: string;
  normalized_text?: string;
  status: string;
  created_at: string;
  assertions?: Assertion[];
}

export function ClaimSection({ claim }: { claim: ClaimDetail }) {
  return (
    <section className="mb-8">
      <div className="flex items-center gap-2 mb-3">
        <FileText size={18} className="text-blue-600" />
        <h2 className="text-lg font-bold text-slate-900">Section 2: Investigation Target &amp; Assertions</h2>
      </div>

      <div className="card-box p-6 flex flex-col gap-5">
        {/* Original Input */}
        <div>
          <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">Original Submitted Input</span>
          <div className="mt-1.5 p-3.5 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-900 break-all leading-relaxed">
            {claim.input_type === "url" ? (
              <div className="flex items-center justify-between flex-wrap gap-2">
                <span className="font-mono text-xs sm:text-sm">{claim.raw_input}</span>
                <a
                  href={claim.raw_input}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-xs text-blue-600 font-semibold hover:underline"
                >
                  Open Link <ExternalLink size={12} />
                </a>
              </div>
            ) : (
              claim.raw_input
            )}
          </div>
        </div>

        {/* Assertions as Light Shade Flash Cards */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">
              Extracted Assertions &amp; Entities ({claim.assertions?.length || 0})
            </span>
          </div>

          {claim.assertions && claim.assertions.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
              {claim.assertions.map((a, idx) => {
                const shade = getLightShade(idx);
                return (
                  <div
                    key={a.id || idx}
                    className="flash-card flex flex-col justify-between gap-3"
                    style={{ backgroundColor: shade.bg, borderColor: shade.border }}
                  >
                    <div>
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-xs font-bold uppercase tracking-wider" style={{ color: shade.accent }}>
                          Assertion #{idx + 1}
                        </span>
                        <span
                          className="text-xs px-2 py-0.5 rounded-full font-semibold"
                          style={{ backgroundColor: shade.badge, color: shade.text }}
                        >
                          {(a.confidence_weight * 100).toFixed(0)}% Weight
                        </span>
                      </div>
                      <p className="text-sm font-semibold text-slate-800 leading-snug">
                        &ldquo;{a.assertion_text}&rdquo;
                      </p>
                    </div>

                    {a.entities && a.entities.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 pt-2 border-t border-black/5">
                        {a.entities.map((ent, eIdx) => (
                          <span
                            key={eIdx}
                            className="text-xs px-2 py-0.5 rounded bg-white/70 text-slate-600 font-medium"
                          >
                            {ent}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="text-xs text-slate-400 italic">No assertions decomposed.</p>
          )}
        </div>
      </div>
    </section>
  );
}
