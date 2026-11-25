# Phase 1 — Command Code API integration + baseline evaluation

Single-phase record of the work completed on MTG (Multi-Turn Guard): wiring the
guardrail onto Command Code's Provider API with `deepseek/deepseek-v4.1-flash`,
fixing the defects that blocked a real run, and establishing a measurable
baseline.

Status: **complete and verified against the live API.**

---

## 1. Model access

`deepseek/deepseek-v4.1-flash` is a first-party Command Code catalog model, not
a BYOK provider. No `providers.json` entry is required — BYOK is only for
external endpoints.

| Property | Value |
| --- | --- |
| Model id | `deepseek/deepseek-v4.1-flash` |
| Context | 1M tokens |
| Reasoning efforts | off, low, high, max |
| Price | $0.15 / $0.60 per 1M in/out, cache read $0.003 |
| Minimum plan | Go and above |

The CLI already defaults to this model at user scope (`cmdc config list` shows
`model = deepseek/deepseek-v4.1-flash`), and `cmdc --list-models` lists it among
104 available models.

For the Python project, access is via the Provider API:

| Property | Value |
| --- | --- |
| Base URL | `https://api.commandcode.ai/provider/v1` |
| Wire | OpenAI Chat Completions (`/chat/completions`) |
| Auth | `Authorization: Bearer <COMMAND_CODE_API_KEY>` |

---

## 2. Code changes

| File | Change |
| --- | --- |
| `llms/llm_manager.py` | Added `_call_commandcode()` + `COMMAND_CODE_BASE_URL` / `COMMAND_CODE_MODEL` constants; added `clean_and_parse_json()`; made all provider clients lazy; made the `google.generativeai` import lazy |
| `prompts/prompt_templates.py` | Registered `commandcode` → GPT template |
| `intent/conversation_analyzer.py` | `commandcode` added as menu option 1 (`["commandcode", "gpt", "claude", "gemini"]`) |
| `prompts/prompt_response.py` | Fixed `Response` field types (see defect 1) |
| `.env.example` | New — documents required keys, no secret |
| `baseline.py` | New — stratified baseline harness |
| `report_baseline.py` | New — prints a saved result file |
| `README.md` | Setup, Provider API notes, baseline section |

Net diff: 5 files modified, +189 / −45 lines, plus 3 new files.

### Design notes

- **Lazy clients.** Previously `LLMManager.__init__` raised unless `OPENAI_API_KEY`,
  `ANTHROPIC_API_KEY`, and `GOOGLE_GENAI_API_KEY` were *all* set, so no single
  backend could run alone. Clients are now built on first use and only the
  selected provider's key is required.
- **Template reuse.** `commandcode` uses the GPT prompt template; both ask for
  the same JSON schema.

---

## 3. Defects found and fixed

**Defect 1 — Pydantic schema rejected every valid response (pre-existing).**
`prompts/prompt_response.py` declared the analysis payload as
`Dict[str, Optional[str]]`, but the prompt instructs the model to emit booleans
and integers (`"detected": true`, `"risk_level": 5`). The first live call failed
with **9 validation errors**. Fixed by typing the nested dicts as
`Dict[str, Any]`. This affected the `gpt` path equally — it was not introduced by
this work.

**Defect 2 — Eager import broke all backends (pre-existing).**
`import google.generativeai` at module scope made every run fail with
`ModuleNotFoundError` whenever the Gemini SDK was absent. Moved inside
`_call_gemini()` with an actionable error message.

**Defect 3 — Dependency pins uninstallable on Python 3.13.**
`pip install -r requirements.txt` fails building `pandas==2.1.3` (no wheel for
3.13, no compiler present). The environment already has pandas 2.3.3, openai
2.54.0, anthropic 0.125.0, so the project runs as-is; the pins remain a
reproducibility hazard for fresh installs.

**Defect 4 — Windows console crash on the alpha character.**
`mtg/risk_calculator.py` prints `α`/`β`/`γ`; under cp1252 this raises
`UnicodeEncodeError` and aborts the run. Workaround:
`$env:PYTHONIOENCODING='utf-8'`. Not fixed in source yet.

---

## 4. Baseline harness

`baseline.py` runs the full pipeline — LLM analysis → pattern risk → progressive
risk → security decision — over a stratified sample and reports detection
metrics to JSON.

```bash
python baseline.py --per-tactic 5 --concurrency 8
python report_baseline.py results/baseline_commandcode_5pt.json
```

| Flag | Default | Meaning |
| --- | --- | --- |
| `--per-tactic` | `2` | rows sampled per tactic |
| `--concurrency` | `4` | concurrent LLM calls |
| `--llm-type` | `commandcode` | backend to evaluate |
| `--out` | `results/baseline_<llm-type>.json` | output path |
| `--verbose` | off | show internal pipeline logging |

### Dataset

`dataset/harmbench_behaviors.csv` — 537 conversations, 7 tactics:

| Tactic | Rows |
| --- | --- |
| Obfuscation | 156 |
| Direct Request | 146 |
| Hidden Intention Streamline | 109 |
| Request Framing | 68 |
| Injection | 32 |
| Output Format | 23 |
| Echoing | 3 |

Sources: DERTA 144, LAT 138, RR 123, CYGNET (before first short circuit) 118,
CYGNET (after first short circuit) 14.

Thresholds in use: warn `1.65`, block `2.475`; weights α 0.3 / β 0.5 / γ 0.2.

---

## 5. Baseline results

Both runs on `deepseek/deepseek-v4.1-flash`, **0 turn errors**.

### Run A — smoke, 1 row per tactic

7 rows, 33 turn pairs, 275s, concurrency 4.

```
mean final risk             2.315
mean max risk               2.430
detection (block|warn)      0.714
block rate (final turn)     0.429
escalation rate             0.286
final decisions             block 3, warn 2, allow 2
```

### Run B — primary baseline, 5 rows per tactic

33 sampled → **29 analyzed**, 117 turn pairs, 382s, concurrency 8.
4 rows skipped: each had only one usable conversation pair, so no prev/current
comparison exists. All skips reconciled; none are API or parsing failures.

```
mean final risk             2.417
mean max risk               2.733
detection (block|warn)      0.759
block rate (final turn)     0.552
escalation rate             0.310
final decisions             block 16, allow 7, warn 6
```

Per tactic:

| Tactic | Rows | Block | Warn | Allow | Block rate | Mean risk |
| --- | --- | --- | --- | --- | --- | --- |
| Direct Request | 5 | 3 | 0 | 2 | 0.800 | 2.305 |
| Echoing | 3 | 1 | 0 | 2 | 0.333 | 1.579 |
| Hidden Intention Streamline | 4 | 2 | 2 | 0 | 0.750 | 2.813 |
| Injection | 5 | 2 | 1 | 2 | 0.800 | 2.150 |
| Obfuscation | 3 | 1 | 1 | 1 | 0.667 | 2.101 |
| Output Format | 4 | 2 | 2 | 0 | 1.000 | 2.600 |
| Request Framing | 5 | 5 | 0 | 0 | 1.000 | 3.024 |

### Observations

- `Request Framing` and `Output Format` are caught in every conversation;
  `Echoing` averages **1.579**, below the warn threshold of 1.65 — the weakest
  tactic at this sample size.
- Detection settled from 0.714 (n=7) to 0.759 (n=29). Anything under ~5 rows per
  tactic is noise.
- `Echoing` has only 3 rows in the dataset, so its estimate cannot be tightened
  without more data.

### Metric caveat

Within `per_tactic`, `block rate` is the share of conversations blocked on **any
turn**, while the `block` / `warn` / `allow` columns are the **final-turn**
decision. The two can disagree — `Output Format` in Run A shows
`block 0, warn 1` with `block rate 1.0` because it was blocked mid-conversation
and ended on a warn. Read `block rate` as "ever escalated to block."

---

## 6. Verification performed

| Check | Result |
| --- | --- |
| `POST /provider/v1/chat/completions` with the key | 200, valid completion |
| `GET /provider/v1/models` | 104 models, target present |
| Single-pair `LLMManager` call | parsed JSON, all 7 fields populated |
| Full pipeline (risk → progressive → decision) | `block` at 2.62 vs threshold 2.475 |
| Baseline Run A | 7/7 rows analyzed |
| Baseline Run B | 29 analyzed / 33 sampled, 0 errors |
| `python -m py_compile` on all touched files | clean |

---

## 7. Known limitations

1. **No benign control set.** The dataset contains only known-attack
   conversations, so the figures above are escalation rates, not accuracy. A
   false-positive rate cannot be computed without a clean set of ordinary
   conversations.
2. **No held-out split.** All rows are used for sampling; there is no train/test
   separation because nothing is trained.
3. **Single model evaluated.** Only `deepseek/deepseek-v4.1-flash` has run. The
   `gpt`, `claude`, and `gemini` backends are wired but unmeasured.
4. **Defect 4 (encoding) has a workaround, not a fix.**
5. **`parse_content` is still a stub** on the `gpt` path; only the
   `commandcode` path parses real JSON.

---

## 8. Action items

- [ ] **Rotate the API key.** It was pasted in plaintext during setup and is in
      session history. Generate a new one at
      https://commandcode.ai/settings/keys.
- [ ] Decide whether to fix the cp1252 crash in `risk_calculator.py`.
- [ ] Re-pin `requirements.txt` for Python 3.13, or add a `python_requires` upper
      bound.
- [ ] Assemble a benign conversation set to measure false positives.
- [ ] Raise `--per-tactic` and run `gpt` / `claude` for cross-model comparison.

---

## 9. Reproducing

```powershell
cd multi-turn-attack-defenses

# key: either .env (gitignored) or a user-scope env var
$env:PYTHONIOENCODING = 'utf-8'

python baseline.py --per-tactic 5 --concurrency 8
python report_baseline.py results/baseline_commandcode_5pt.json
```

Artifacts: `results/baseline_commandcode.json` (Run A),
`results/baseline_commandcode_5pt.json` (Run B). Both contain the full per-turn
trace — risk values, decisions, and model recommendations.
