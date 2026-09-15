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
- **Multi-LLM analysis** — analyzes conversation pairs using GPT, Claude, or
  Gemini (selectable per run).
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
│   └── llm_manager.py       # LLMManager: calls GPT/Claude/Gemini, parses JSON
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

> **Note:** `LLMManager.parse_content` is currently a stub that returns an
> empty structure; wiring it to parse the LLM's actual JSON output is required
> to populate real risk figures during a run.

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
`python-dotenv`):

```env
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
GOOGLE_GENAI_API_KEY=...
# LLAMA_API_KEY=... (used for the optional Replicate/LLaMA backend)
```

`LLMManager` raises `ValueError` on startup if any required key is missing.

---

## Usage

Run the analyzer interactively to select an attack tactic and number of
conversations:

```bash
python intent/conversation_analyzer.py
```

You will be prompted to:

1. choose an LLM (`gpt`, `claude`, `gemini`),
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
