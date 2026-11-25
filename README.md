# MTG — Multi-Turn Guard

**MTG (Multi-Turn Guard)** is a guardrail framework for detecting and mitigating
**multi-turn manipulation attacks** against Large Language Models (LLMs).

These attacks exploit the conversational nature of LLMs by gradually shifting
intent, framing, or domain across multiple turns to induce harmful,
unauthorized, or disallowed responses. MTG monitors each turn of an ongoing
conversation, scores how the risk evolves, and applies a threshold-based
security decision engine that allows, warns, or blocks an interaction.

---

## Features

- **Pattern-based risk scoring** — evaluates detected adversarial patterns
  (language change, domain shift, time sensitivity, prohibited content) using
  configurable weights.
- **Progressive risk tracking** — combines historical, interaction, and pattern
  risk into a single evolving score as a conversation advances.
- **Threshold-based decision engine** — maps the progressive risk score onto
  `allow`, `warn`, or `block` decisions with configurable thresholds.
- **Multi-LLM analysis** — analyzes conversation pairs using Command Code
  (DeepSeek V4.1 Flash), GPT, Claude, or Gemini (selectable per run).
- **Dataset-driven evaluation** — bundles a dataset of multi-turn conversations
  labeled with attack tactics and runs the full guardrail pipeline over it.

---

## Architecture

```
mtg-multi-turn-guard/
├── config/
│   ├── mtg_config.py        # MTGConfig: loads & validates config/*.yaml
│   └── config.yaml          # weights, pattern weights, thresholds
├── dataset/
│   └── dataset_manager.py   # DatasetManager: loads CSV, extracts turn pairs
├── intent/
│   └── conversation_analyzer.py  # ConversationAnalyzer: orchestrates a run
├── llms/
│   └── llm_manager.py       # LLMManager: calls Command Code/GPT/Claude/Gemini, parses JSON
├── prompts/
│   ├── prompt_templates.py  # PromptManager: per-LLM prompt templates
│   └── prompt_response.py   # pydantic models for parsed LLM responses
├── mtg/
│   ├── risk_calculator.py   # RiskCalculator: pattern & progressive risk
│   └── security_engine.py   # SecurityDecisionEngine: allow/warn/block
└── requirements.txt
```

### Data flow

1. `ConversationAnalyzer` loads `config/config.yaml` via `MTGConfig` and the
   conversation dataset via `DatasetManager`.
2. The user selects an attack tactic and the number of conversations to
   process.
3. For each conversation, consecutive assistant/human message pairs are
   extracted.
4. Each pair is sent to the selected LLM (`LLMManager`) using a prompt template
   from `PromptManager`. The LLM returns a JSON analysis: intent shift, prompt
   attack evidence, detected patterns, and a risk level.
5. `RiskCalculator` computes a *pattern risk* from the detected patterns and a
   *progressive risk* that blends historical, interaction, and pattern risk
   using configurable weights (`alpha`, `beta`, `gamma`).
6. `SecurityDecisionEngine` maps the progressive risk onto an `allow` / `warn` /
   `block` decision using the configured thresholds.

> **Note:** the `commandcode` backend parses the model's JSON response directly
> (`LLMManager.clean_and_parse_json`, which strips Markdown fences). The legacy
> `LLMManager.parse_content` used by the `gpt` backend is still a stub that
> returns an empty structure, so real risk figures are populated on the
> `commandcode` path.

---

## Installation

```bash
git clone [MY GITHUB REPOSITORY URL]
cd mtg-multi-turn-guard
pip install -e .
```

A `uv`-managed environment also works:

```bash
uv pip install -e .
```

### Dependencies

See `requirements.txt`. Core dependencies: `openai`, `anthropic`,
`google-generativeai`, `pandas`, `pyyaml`, `python-dotenv`, `pydantic`.

---

## Configuration

All runtime behavior is controlled by `config/config.yaml`:

```yaml
risk:
  weights:
    alpha: 0.3    # historical risk
    beta: 0.5     # interaction risk
    gamma: 0.2    # pattern risk
  pattern_weights:
    language_change: 0.2
    domain_shift: 0.3
    time_sensitivity: 0.2
    prohibited_content: 0.3
  warn_threshold: 1.65
  block_threshold: 2.475
file_path: "dataset/harmbench_behaviors.csv"
gcp_project_id: "[MY GCP PROJECT ID]"
```

The weights are validated to sum to `1.0`; `MTGConfig.validate_weights` raises
`ValueError` otherwise.

---

## Setup

Provide API keys via environment variables (a `.env` file is supported through
`python-dotenv`). Only the key for the provider you select is required:

```env
COMMAND_CODE_API_KEY=...   # for --llm-type commandcode (deepseek/deepseek-v4.1-flash)
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
GOOGLE_GENAI_API_KEY=...
# LLAMA_API_KEY=... (used for the optional Replicate/LLaMA backend)
```

`LLMManager` raises `ValueError` when the key for the selected provider is
missing. Clients are created lazily, so the other providers' keys are not
required.

### Command Code Provider API

The `commandcode` backend calls Command Code's OpenAI-compatible Provider API at
`https://api.commandcode.ai/provider/v1` with the model
`deepseek/deepseek-v4.1-flash` (1M context, $0.15/$0.60 per 1M input/output
tokens).

- Create a key at https://commandcode.ai/settings/keys and export it as
  `COMMAND_CODE_API_KEY`. The same key authenticates the CLI and the API.
- API access requires a plan other than **Go** (GOAT, Pro, Max, Team, or the
  pay-as-you-go Provider plan). Go keys get `403 upgrade_required`.
- The CLI login at `~/.commandcode/auth.json` is not read by this project; set
  the environment variable explicitly.

---

## Usage

Run the analyzer interactively to select an attack tactic and number of
conversations:

```bash
python intent/conversation_analyzer.py
```

You will be prompted to:

1. choose an LLM (`commandcode`, `gpt`, `claude`, `gemini`),
2. select an attack tactic from the dataset,
3. enter how many conversations to analyze.

The pipeline then prints, per turn: the parsed risk fields, the pattern risk,
the progressive risk, the resulting security decision, and the thresholds used.

Programmatic use:

```python
from config.mtg_config import MTGConfig
from dataset.dataset_manager import DatasetManager
from mtg.risk_calculator import RiskCalculator
from mtg.security_engine import SecurityDecisionEngine

config = MTGConfig("config/config.yaml")
manager = DatasetManager(config)
df = manager.load_data()

risk = RiskCalculator()
engine = SecurityDecisionEngine()
```

---

## Baseline evaluation

`baseline.py` runs the full guardrail pipeline (LLM analysis → pattern risk →
progressive risk → security decision) over a stratified sample of the bundled
dataset and reports detection metrics:

```bash
python baseline.py --per-tactic 5 --concurrency 8
```

| Flag | Default | Meaning |
| --- | --- | --- |
| `--per-tactic` | `2` | rows sampled per attack tactic (max 7 tactics) |
| `--concurrency` | `4` | concurrent LLM calls |
| `--llm-type` | `commandcode` | `commandcode`, `gpt`, `claude`, or `gemini` |
| `--out` | `results/baseline_<llm-type>.json` | per-row + summary JSON |
| `--verbose` | off | show the pipeline's internal logging |

`report_baseline.py` prints a saved result file:

```bash
python report_baseline.py results/baseline_commandcode_5pt.json
```

Rows with fewer than two usable conversation pairs cannot form a prev/current
comparison and are skipped before any LLM call; the run prints sampled versus
analyzed counts.

Reported metrics: rows and turn pairs analyzed, turn errors, mean final and mean
max progressive risk, detection rate (block or warn), block rate, escalation
rate, and a per-tactic breakdown.

### Baseline: deepseek/deepseek-v4.1-flash, 5 per tactic

29 rows (33 sampled; 4 skipped for having only one usable pair), 117 turn
pairs, 0 turn errors, 382s, thresholds warn `1.65` / block `2.475`:

```
mean final risk 2.417    mean max risk 2.733
detection (block|warn) 0.759    block rate 0.552    escalation 0.310
final decisions: block 16, allow 7, warn 6
```

```
tactic                       rows  block  warn  allow   blk%    mean
Direct Request                  5      3     0      2    0.8   2.305
Echoing                         3      1     0      2  0.333   1.579
Hidden Intention Streamline     4      2     2      0   0.75   2.813
Injection                       5      2     1      2    0.8    2.15
Obfuscation                     3      1     1      1  0.667   2.101
Output Format                   4      2     2      0    1.0     2.6
Request Framing                 5      5     0      0    1.0   3.024
```

`Request Framing` and `Output Format` are caught every time; `Echoing` (1.579)
is the weakest, sitting below the warn threshold on average. A single
conversation per tactic earlier gave 0.714 detection — with 5 per tactic it
settles at 0.759, so treat anything below ~5 per tactic as noise.

---

## Evaluation dataset

The bundled dataset (`dataset/harmbench_behaviors.csv`) is a CSV of multi-turn
conversations, each tagged with an attack `tactic` and metadata columns
(`Source`, `temperature`, `question_id`, `time_spent`, `submission_message`,
and `message_0` … `message_N`). `DatasetManager` parses the JSON-encoded
messages into assistant/human conversation pairs for analysis.

> This dataset is sourced from the MHJ dataset curated by Scale AI
> (see [Scale AI Research — MHJ](https://scale.com/research/mhj)) and is
> retained verbatim; do not redistribute it independently.

---

## Security

This tool is a defensive research artifact. It is intended to **study** and
**defend against** multi-turn manipulation of LLMs. Do not misuse the bundled
dataset or prompt templates to construct real attacks.

---

## License

Distributed under the MIT License. See `LICENSE` for details.

---

## Author

**[MY NAME]** — maintainer of MTG.

- GitHub: [MY GITHUB USERNAME]([MY GITHUB REPOSITORY URL])
- Email: [MY EMAIL]

---

## Acknowledgements

The risk-scoring and multi-turn analysis approach implemented here builds on the
**Temporal Context Awareness (TCA) framework**, introduced by Kulkarni, P. and
Namer, A. in:

> Kulkarni, P. & Namer, A. *Temporal Context Awareness (TCA) Framework for
> Securing LLMs.* Proc. IEEE Conference on Artificial Intelligence (CAI), 2025.
> arXiv: [2503.15560](https://arxiv.org/pdf/2503.15560).

The citation above is retained as attribution for the original research; the
framework code in this repository is a standalone implementation branded as
**MTG — Multi-Turn Guard**.

---

## References

- Scale AI, "Measuring Jailbreaking Vulnerabilities (MHJ),"
  https://scale.com/research/mhj
