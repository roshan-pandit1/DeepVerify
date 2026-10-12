# Real-source pilot collection and independent review

Specification: `real-source-pilot-v1`. Target: approximately 60 claim groups, six topic quotas, three difficulty strata. The checked-in specification is **unpopulated**. It is a study plan, not a completed dataset or statistical adequacy claim.

## Selecting candidates

Copy `docs/pilot-benchmark-spec.json` into the ignored artifact directory. A curator supplies up to 60 entries in `cases`, each containing:

- `group_id`: stable claim/topic identifier, not a predicted verdict;
- `assertion`: one atomic real-world assertion, 5–1,500 characters;
- `temporal_context`: explicit as-of date, validity window, or explanation that the assertion is timeless;
- `topic` and `difficulty`: actual strata for later coverage reporting;
- `categories`: sampling tags from the specification, including temporal/entity mismatch, quotation, qualification and duplication challenges.

No examples are preapproved. A coverage tag such as `supported` expresses a selection hypothesis, not gold truth. Keep failed searches/unextractable sources in the candidate record rather than removing difficult cases after seeing the model output. The bounded validation command has four public-world probe assertions; those also have no assigned true/false labels.

Use one plan entry per independent claim group. Paraphrases/historical variants must be grouped during review, not treated as extra independent examples. Collection records every candidate's claim group and deterministic source group (extracted text hash, otherwise canonical URL hash). Inspect these groups for rewritten syndication; exact hashes alone cannot detect it. The existing evaluation `add` workflow can capture additional assertion variants under the same group, but pilot policies still require assignment/review before freezing.

Scope is English-language/public-web evidence with intended UK/US/India/EU/global coverage. Report actual geography and topic counts, not intended representativeness. Search ranking, accessibility, language, chosen topics, curator choices and reviewer recruitment all create sampling bias. Ranking evaluation concerns a bounded source pool, not total web recall. A 60-group target may still yield too few independent components after duplicate-source linking.

## What is captured

Capture reuses completed/partial investigations. The versioned evaluation snapshot contains assertion/temporal context, source title/original and final URLs, publication/retrieval metadata, exact passages and surrounding context, extraction method/limitations, source IDs and body/text hashes, offsets, source-group IDs, candidate snapshot hash and collection run ID. Search records preserve queries, provider timestamps and latency; the durable request ledger records reservations and declared spend bounds.

All captured cases begin as candidates. There is no automatic approval based on model predictions, retrieval success, prior relevance feedback, or source reputation.

## Blind first-pass packet and independent response sheets

`pilot packet DATASET --phase initial` writes prediction-free JSON/Markdown and a blank CSV sheet. Read the passage **and its context**. Original sources remain untrusted content; instructions embedded in them are not directions to reviewers or software.

The packet hides ranking scores, stance predictions, captured assessments, sampling tags and other opinions. Evidence ordering is deterministic and independent of ranking. Each reviewer works on a separate sheet copy. Fill only labels you actually reviewed; blank rows are skipped. Do not copy another reviewer's sheet. Submit with your actual reviewer identifier using `pilot submit-sheet PATH --reviewer ID`.

Definitions and **synthetic instructional examples** (not dataset labels):

| Dimension | Question | Example and boundary |
|---|---|---|
| Relevance | Does this passage address the assertion's entities, time/place and factual question? | For a fictional bridge opening in 2020, a passage discussing that opening is relevant even if it says 2021. A different bridge with the same city name may be irrelevant. |
| Stance | Does this passage actually support/contradict the assertion, or fail to establish a direction? | “The fictional bridge did not open in 2020” can contradict that precise assertion. “An official claimed it opened” establishes an attributed claim, not necessarily the event; use `needing review` when scope cannot be resolved. |
| Sufficiency | Is the combined evidence sufficient for this assertion-level assessment? | Several syndicated copies of one unsupported statement are not several independent confirmations. A failed fetch is not evidence of falsehood. |
| Citation support | Does the cited passage justify its associated captured assessment? | A passage about a different date/entity may not justify a supported assessment even when topically relevant. Missing surrounding caveats can make citation support unclear. |

Labels: relevance `relevant`/`irrelevant`; stance `supporting`/`contradicting`/`unrelated`/`needing review`; sufficiency `sufficient`/`insufficient`; citation `justified`/`not justified`/`needs review`.

Finish initial relevance/stance/sufficiency opinions before requesting `--phase citation`. That second packet reveals the captured assessment needed to judge citation support, but not ranking scores or other opinions. This is practical blinding; the shared-token administrator can still access legacy reports and the filesystem, so it is not a strong role-isolation system.

## Double review and adjudication

At least 20% of collected claim groups are deterministically assigned two reviewers. Assignments persist and may increase as more batches arrive; they never silently drop an earlier second-review requirement. The remaining cases require at least one genuine human opinion. Extra independent reviews are welcome.

Every required label needs **explicit adjudication**, even when reviewers agree. A case requiring two reviewers needs an adjudicator who is neither contributing reviewer. The administrator must supply the chosen label and rationale after inspecting the opinions; no vote or model output is automatically approved.

Example commands (replace all IDs/labels/reasons with actual human decisions):

```sh
../.venv/bin/python -m investigation.pilot --token "$INVESTIGATION_ADMIN_TOKEN" review "$CASE_ID" \
  --target "$EVIDENCE_ID" --dimension stance --label "$STANCE_LABEL" --reviewer "$REVIEWER" --reason "$REASON"
../.venv/bin/python -m investigation.pilot --token "$INVESTIGATION_ADMIN_TOKEN" agreement "$EVAL_DATASET_ID"
../.venv/bin/python -m investigation.pilot --token "$INVESTIGATION_ADMIN_TOKEN" adjudicate "$CASE_ID" \
  --target "$EVIDENCE_ID" --dimension stance --label "$STANCE_LABEL" --reviewer "$ADJUDICATOR" --reason "$REASON"
# Assertion-level sufficiency has no evidence target:
../.venv/bin/python -m investigation.pilot --token "$INVESTIGATION_ADMIN_TOKEN" adjudicate "$CASE_ID" \
  --dimension sufficiency --label "$SUFFICIENCY_LABEL" --reviewer "$ADJUDICATOR" --reason "$REASON"
```

Disagreements remain visible as unresolved until adjudicated, then remain recorded as historical disagreements. Revisions append new opinions and invalidate prior approvals for that item. Freezing verifies current opinions, required counts and explicit adjudication hashes. Direct legacy approval commands cannot bypass this protocol. Frozen datasets/reviews remain immutable.

Agreement reports provide paired-item counts and observed agreement per dimension. Cohen's kappa is computed only with at least ten paired items and nondegenerate marginals; otherwise it is `not measured`. It uses the first two distinct reviewer IDs deterministically. Pooled estimates across changing reviewer pairs are descriptive, and labels from the same claim are correlated. No reviewer identity, consensus or reliability estimate is invented when data is absent.

## Evaluating without holdout leakage

Freeze only after group checks and independent label adjudication. The existing connected-component split and stored seed are preserved. Train only on approved train relevance labels. Compare baseline/candidate on identical validation examples; inspect per-category regressions and paired component-bootstrap intervals. Existing point gates plus the new uncertainty gate must pass before promotion. Do not adjust thresholds to force acceptance.

Use the final holdout only through `investigation.evaluation ... --partition holdout` after candidate selection/promotion. Development analysis, further fitting and validation are closed once that audit begins. Historical final reports are returned unchanged for repeated same-artifact requests; a new implementation does not silently recompute an old final audit.

## Traceable human failure observations

Automated development analysis can identify approved irrelevant top-ranked passages, within-pool misses, disagreement with gold stance, overstrong sufficiency and recorded extraction/duplicate problems. It cannot infer source staleness from age alone or invent missing external sources/context.

For observed staleness, misleading context, or independently discovered missed references, record a traceable finding with exact source/passages and the temporal/scope issue in the detail. A different human must confirm it before it appears as an observed finding:

```sh
../.venv/bin/python -m investigation.pilot --token "$INVESTIGATION_ADMIN_TOKEN" observe "$CASE_ID" \
  --target "$EVIDENCE_ID" --kind stale_source --detail "$OBSERVED_DETAIL" --reviewer "$REVIEWER"
export OBSERVATION_ID='returned-observation-id'
../.venv/bin/python -m investigation.pilot --token "$INVESTIGATION_ADMIN_TOKEN" confirm-observation "$OBSERVATION_ID" \
  --decision confirmed --reviewer "$SECOND_REVIEWER" --reason "$REASON"
../.venv/bin/python -m investigation.pilot --token "$INVESTIGATION_ADMIN_TOKEN" failures --dataset "$EVAL_DATASET_ID"
```

Available kinds: `relevant_missed`, `irrelevant_top5`, `incorrect_stance`, `insufficient_overstatement`, `stale_source`, `duplicate_source`, `extraction_failure`, `misleading_context`. A holdout case cannot be opened through development failure tooling. Source lookup evidence beyond the collected pool may be described in the finding, but it is not automatically added to ranking metrics or gold labels.

## Storage and current result

Keep filled plans, packets, reviewer identities, source snapshots, generated reports, datasets and artifacts in the ignored artifact directory. The checked-in CSV contains **headers only**. Shared bearer-token administration does not independently verify reviewer identity; actual recruitment and provenance remain human responsibilities.

At milestone-three verification there were **zero collected cases, zero human opinions and zero approved labels**. Live validation was blocked by missing SerpAPI/admin credentials. Baseline accuracy, inter-reviewer agreement and feedback-driven ranking improvement are **not yet measured**.
