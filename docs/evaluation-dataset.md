# Evaluation dataset format and review protocol

Format version: **`reviewed-investigation-v1`**. Export with the protected `investigation.evaluation export` command documented in README. Exports live in the ignored artifact directory, not Git.

## Structure

- `dataset`: UUID, name, version, format version, seed, synthetic flag, draft/frozen status, creation time, and frozen content hash.
- `split_method`: `topic-source-components-v2`.
- `cases[]`: case UUID, dataset ID, assertion ID, human-assigned `related_group`, textual `temporal_context`, coverage `categories`, persisted `split` and connected `component`.
- `cases[].snapshot`: immutable assertion text, investigation ID, captured assessment and explanation, extracted entities, and `evidence[]`.
- Evidence includes passage/snippet text, source title/URL, publication/retrieval times, passage kind, fixture flag, ranking features/method, machine-predicted stance/method/explanation, and independent source metadata.
- `evidence[].source`: original/final URLs, source retrieval time, extraction method/status/error, title, main text, publication metadata provenance, content/body hashes, exact passage/context offsets, context text, original snippet, and passage selection method. Older evidence may have `null` source metadata and is counted as not attempted.
- `approved_feedback_at_capture` records provenance from the original feedback workflow. It is **not** approved evaluation ground truth.
- `cases[].reviews[]`: append-preserved label records with target evidence ID (empty for assertion sufficiency), dimension, label, actual reviewer identifier, proposed/approved/rejected/superseded status, reason and timestamp. Machine predictions stay in the snapshot and never fill approved reviews.

The hash covers the entire frozen export with `dataset.frozen_hash` temporarily null during hashing. Loading a frozen dataset verifies this fingerprint. Filesystem/database access remains trusted administration; hash verification detects ordinary accidental mutation, not a malicious database administrator rewriting both data and hash.

## Review separately

1. **Relevance:** Does this specific passage address the assertion? A relevant passage may not establish it. Labels: `relevant`, `irrelevant`.
2. **Stance:** Does it support or contradict the assertion in the same entity, place, time and scope? Treat quotations as attributed speech rather than established facts. Labels: `supporting`, `contradicting`, `unrelated`, `needing review`. Abstain when the passage does not establish a direction.
3. **Sufficiency:** Inspect all evidence and failures for the assertion, including source independence and time sensitivity. Labels: `sufficient`, `insufficient`. It is an assertion-level judgment, not a passage-level relevance label.
4. **Citation support:** Does this passage justify its associated **captured** assessment? Labels: `justified`, `not justified`, `needs review`. Inspect context, quotation, and omitted caveats. The citation audit metric uses citations attached to non-insufficient assessments; unresolved judgments are reported separately.

Use actual reviewer identifiers. The initial shared administrator token authenticates the operator, not independent human identity. No reviewer, real approval, or factual ground truth is prepopulated by this milestone. All test labels/reviewer strings are explicitly synthetic fixtures in temporary databases.

Coverage categories are sampling tags: supported, contradicted, mixed/partial, time-sensitive, insufficient evidence, relevant-but-not-entailing, and duplicate/syndicated sources. Supported/contradicted/mixed tags use the CLI spellings in README. These tags do not authorize model training or imply that labels are approved.

## Splits and frozen holdout

Assign related paraphrases and historical variants to the same topic group **before freezing**. Automatic linking adds investigation ID, lexical overlap, duplicate URLs, text hashes and exact normalized passages; it cannot reliably detect rewritten syndication or semantic paraphrases. Reviewer-assigned groups complement that baseline.

Freeze assigns connected components to train/validation/holdout, persists seed and membership, and requires approved independent labels for every required dimension. Unreviewed cases block freezing; no silent cherry-picking occurs. Shared sources may collapse many cases into one component and make training ineligible.

Validate the selected ranker on exactly the same examples as the baseline. Fit and select without the final holdout. Holdout evaluation is one-shot and closes subsequent model selection for the dataset. A baseline-only final audit is also possible but consumes that dataset's holdout. A repeated identical final request retrieves the stored report; it does not rerun the evaluation.

Frozen labels cannot be edited. Corrections require a new version and a disjoint final holdout; cross-version partition conflicts and copied holdout topics/sources are rejected. Preserve old reports rather than rewriting historical evaluation claims.

## Scope of current evidence

The software supplies capture, review, freeze, evaluation, training, promotion and rollback tooling. **There is no bundled real reviewed dataset, no demonstrated real-world ranking improvement, and no validated stance-accuracy improvement.** Synthetic regression tests deliberately construct easy/adversarial features to exercise promotion gates; their scores are not product benchmarks. Ranking evaluation measures reranking of collected sources, not the recall of the search provider.
