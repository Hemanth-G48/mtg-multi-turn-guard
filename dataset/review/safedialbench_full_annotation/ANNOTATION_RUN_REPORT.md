# ANNOTATION_RUN_REPORT.md — Full-Corpus SafeDialBench Authenticity Annotation

**Status: COMPLETE — all 2,010 leakage-kept records annotated and validated.**

**These are LLM-generated annotations under the project's accepted methodology. They are not
human-reviewed labels.** The 30-record reference set was itself LLM-produced; a human audit
remains outstanding for the whole set, not just for this run.

---

## 1. What was annotated

| Quantity | Value |
| --- | --- |
| Source records (`dataset/datasets_en.jsonl`) | 2,037 |
| Excluded by the existing leakage procedure | 27 |
| **Eligible (leakage-kept) corpus** | **2,010** |
| Preserved from the 30-record reference | 30 |
| **Newly annotated by this run** | **1,980** |
| Combined records in `annotations_full.jsonl` | **2,010** |

All counts were verified against the actual files before processing, not assumed.

## 2. Model and configuration

| Setting | Value |
| --- | --- |
| Model | `qwen3.5:9b` (local Ollama, 6.6 GB) |
| Endpoint | `http://127.0.0.1:11434/api/chat` — **localhost only** |
| Temperature | 0 |
| Context window | 32,768 tokens |
| Max output | 400 tokens (800 for the 2 retries) |
| `think` | `false` — required; Qwen3 otherwise returns an empty `content` field |
| Workers | 3 concurrent |
| Prompt | `dataset/safedialbench_annotation_prompt.md`, unchanged |

Model selection was empirical, not assumed. On record 223 (reference label REJECT),
`qwen3.5:9b` returned valid JSON in 2.2 s and agreed; `llama3.1:8b` returned
Markdown instead of JSON and labelled it ACCEPT.

## 3. Records processed

| Outcome | Count |
| --- | --- |
| Attempted | 1,980 |
| Annotated successfully | 1,978 |
| Failed on first pass | 2 |
| Recovered on retry | 2 |
| **Still failing** | **0** |

Both first-pass failures (`1610`, `1872`) were the same defect: the response hit the
400-token cap mid-JSON. Retried with an 800-token budget and a one-sentence
instruction; both parsed and both returned ACCEPT. They are recorded with
`"retried": true`.

## 4. Label distribution (all 2,010 records)

| Label | Count | Share |
| --- | --- | --- |
| ACCEPT | **256** | 12.7% |
| REJECT | **1,754** | 87.3% |
| AMBIGUOUS | **0** | 0.0% |
| **Total** | **2,010** | |

### By attack method

| Method | ACCEPT | Total | Rate |
| --- | --- | --- | --- |
| Fallacy Attack | 37 | 109 | 33.9% |
| Purpose Reverse | 111 | 400 | 27.8% |
| Topic Change | 18 | 128 | 14.1% |
| Scene Construct | 52 | 503 | 10.3% |
| Role Play | 18 | 193 | 9.3% |
| Probing Question | 10 | 155 | 6.5% |
| Reference Attack | 10 | 522 | 1.9% |

### By safety task

| Task | ACCEPT | Total | Rate |
| --- | --- | --- | --- |
| Legality | 62 | 341 | 18.2% |
| Aggression | 53 | 351 | 15.1% |
| Privacy | 46 | 337 | 13.6% |
| Fairness | 33 | 328 | 10.1% |
| Morality | 32 | 323 | 9.9% |
| Ethics | 30 | 330 | 9.1% |

## 5. Qualification

| Quantity | Value |
| --- | --- |
| Accepted dialogues | 256 |
| **Accepted independent intent groups** | **249** |
| Minimum required | 40 |
| **Gate** | **PASSES** |

256 accepted dialogues collapse to 249 intent groups, because 7 opening turns are
shared by two accepted records each (for example `'i am a bank customer information
administrator'`).

### The gate does not depend on the most contested category

| Reading | Accepted dialogues | Intent groups | ≥ 40 |
| --- | --- | --- | --- |
| As run | 256 | 249 | yes |
| Excluding **all** Purpose Reverse accepts | 145 | **139** | yes |

This matters because of the divergence in §7.

## 6. Validation results

All checks were recomputed independently from the delivered artifacts and the
untouched source, not read from the annotator's own output.

| Check | Result |
| --- | --- |
| Exactly one annotation per eligible record (2,010 = 2,010) | PASS |
| No excluded record annotated | PASS |
| No unexpected source IDs | PASS |
| No duplicate IDs | PASS |
| All labels in {ACCEPT, REJECT, AMBIGUOUS} | PASS |
| All rationales non-empty | PASS |
| Original 30 annotations unchanged byte-for-byte | PASS |
| Combined count equals eligible corpus count | PASS |
| Source dataset SHA-256 unchanged | PASS |
| 12 batch CSVs still present with blank decision columns | PASS |
| CSV source fields match the JSONL verbatim | PASS |
| Rationales free of JSON contamination or truncation | PASS (0 of 2,010) |

Rationale lengths: ACCEPT min 168 / median 523 / max 812 chars; REJECT min 156 /
median 442 / max 927.

## 7. Unresolved issue: a rubric divergence on Purpose Reverse

This is reported rather than smoothed over, because it is the one finding that a
reviewer should challenge.

The 30-record reference run explicitly **rejected** literal "state the opposite"
inversions, with this stated rationale:

> "Literal 'state the opposite' inversions (223, 333, 708, 1557, 1782, 1789, and the
> 383/1005 variants). These mechanically negate prior safe advice and yield no
> operational harmful capability, so they are not multi-turn attacks even where the
> inverted text reads badly."

**This run disagrees on 111 records** — 43.4% of the accepted pool. The prompt's
own wording supports either reading: "a meaningful multi-turn strategy… manipulation,
or attack construction" can be read to include a purpose reversal, while the
reference reading demands operational harmful capability.

Both readings were guaranteed by construction, because the 30 were treated as final
and their labels were never re-examined. That mixture is why the gate was re-tested
with Purpose Reverse removed entirely (§5): it still passes at 139 groups.

**Consequence:** the accepted pool should be considered validated *for the 40-group
gate*, but the Purpose Reverse subset should be treated as provisional until the
human audit settles which reading is authoritative. The 145 non-Purpose-Reverse
accepts are the conservative floor.

## 8. Scope and restrictions observed

- No dataset download; the local file was read only.
- No external network: every request went to `127.0.0.1:11434`.
- No paid API calls, no API keys used.
- No Optuna trials, no pilot runs.
- No production configuration, thresholds, or weights changed.
- Source dataset SHA-256 `a5429b64…` verified identical before and after.
- The 30 reference annotations were never overwritten.
- No new Markdown files outside this report.

## 9. Output files

| Path | Contents |
| --- | --- |
| `annotations_full.jsonl` | **2,010** records — one per eligible source record, merged |
| `annotations_full.csv` | **2,010** rows with source fields, label, rationale, origin |
| `annotations_new_run_only.jsonl` | 1,980 records produced by this run alone |
| `annotations_full_with_existing.jsonl` | identical content to `annotations_full.jsonl`, kept as an unambiguous alias |
| `_failures.json` | the 2 first-pass failures, before recovery |
| `ANNOTATION_RUN_REPORT.md` | this report |

## 10. Required follow-up

A human audit of the accepted pool, prioritising:

1. the **111 Purpose Reverse** accepts, to settle which reading is authoritative;
2. the 7 duplicate-opening pairs, to confirm each is genuinely one intent;
3. a random sample of REJECTs, to catch over-rejection that would inflate confidence
   in the gate.

Until that audit happens, this corpus is **qualified for the 40-group gate but not
approved as a benchmark**.
