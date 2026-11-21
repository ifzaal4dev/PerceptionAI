# PerceptionAI: Did They Really Mean That?

**How AI interpretations shape perceptions of ambiguous messages.** Undergraduate research, Department of Computer Science, Virginia Tech.

Ifzaal Ahamed Imdad, Vikas Chowdary Meka, Vishal Meka. Advisor: Dr. Sehrish Basir Nizamani.
Presented at the VTURCS Research Symposium, Dec 1, 2026 ([poster PDF](poster/PerceptionAI_poster.pdf), [abstract](poster/abstract.txt)).

## The study

People ask AI chatbots what an unclear text message meant. This repo holds Part 2 of the project (the model study): does the *wording* of that question change the answer?

- 20 fictional conversations (`scenarios.json`), each ending in a message that can be read as sincere or passive-aggressive.
- 3 questions per conversation: neutral ("What did {sender} mean by the last message?"), negatively leading ("Is {sender} being passive-aggressive...?") and positively leading ("Is {sender} being sincere...?").
- 2 models on the VT ARC LLM API (gpt-oss-120b, DeepSeek-V4.1-Flash), 10 repeats each: 1,200 answers.
- Every answer coded on four fields (`codebook_v0.md`) by a model coder (GLM-5.3) and, for a 150-answer sample, by pairs of blinded human coders.

Part 1 (a human survey, VT IRB #26-1078) runs separately; only its aggregate pilot summary is here. All design and analysis choices, with dates, are in `decisions.md`.

## Results (descriptive only)

| Model | Question | n | % negative | % hedged | % mention other reading |
|---|---|---|---|---|---|
| gpt-oss-120b | Neutral | 200 | 26.5 | 2.5 | 15.0 |
| gpt-oss-120b | Passive-aggressive? | 200 | 47.5 | 89.5 | 99.0 |
| gpt-oss-120b | Sincere? | 200 | 60.0 | 79.0 | 93.5 |
| DeepSeek-V4.1-Flash | Neutral | 199 | 37.2 | 55.8 | 42.7 |
| DeepSeek-V4.1-Flash | Passive-aggressive? | 197 | 53.3 | 94.4 | 96.4 |
| DeepSeek-V4.1-Flash | Sincere? | 198 | 51.0 | 94.9 | 93.9 |

Model-coder labels; 1,194 of 1,200 answers coded (6 DeepSeek answers failed in both coding passes). Both leading questions raised negative readings, including the "sincere?" one. Agreement (Cohen's kappa, main reading): model coder vs. humans 0.72 (n 154), human vs. human 0.69 (3 pairs x 25 = 75). Full output: `results/judge_report.txt`, `results/judge_table.csv`, `coding/kappa_main.txt`.

## Repo layout

| Path | What it is |
|---|---|
| `study0.py` | Runner: plan, smoke, run, verify, sample, export, kappa, judge, judge-retry, judge-report |
| `tests/` | Offline tests against a mock server (no ARC key needed) |
| `scenarios.json`, `planned_trials.csv` | Inputs and the 1,200-trial design |
| `codebook_v0.md`, `coding_plan.csv`, `coding/` | Codebook, the fixed coding sample, blinded coder sheets and kappa reports |
| `results/` | Aggregate outputs: model-coder tables, pilot summary |
| `poster/` | Poster build script, chart script, final PDF/PPTX, abstract |
| `pilot_summary.py` | Aggregates the Part 1 pilot export per scenario (no individual responses written) |
| `qualtrics_build_spec.md` | Build spec for the Part 1 survey |
| `smoke_runs/` | Setup test calls only, not part of the dataset |

`runs/` (raw model answers and model-coder records, about 63 MB) is not committed yet; where the dataset is archived is a team/PI decision. `poster/make_charts.py` needs `runs/judge/ea34f421e7a9/judge_labels.csv`, which `py study0.py judge-report` writes.

## Reproducing

Python 3.9+ (`py` on Windows, `python3` elsewhere). The runner uses only the standard library; the poster and pilot scripts also need `python-pptx`, `matplotlib`, `openpyxl`.

1. `py study0.py plan` rebuilds `planned_trials.csv` (no network).
2. Get a personal key at https://llm.arc.vt.edu (Settings, Account, API keys). Enter it at the hidden prompt or set `ARC_API_KEY`. Never commit or paste it anywhere.
3. `py study0.py smoke`, then `py study0.py run` and `py study0.py verify` (details below).
4. Coding: `sample`, `export`, then `kappa`. Model coder: `judge`, `judge-retry`, `judge-report`.
5. Poster: `py poster/make_charts.py`, then from `poster/`: `python build_poster.py template_cs4974.pptx PerceptionAI_poster_final.pptx`.

ARC service reference: https://docs.arc.vt.edu/ai/011_llm_api_arc_vt_edu.html

## Formal run and verification (added Nov 11)

Only start once decisions.md sections 2–4 are frozen (PI sign-off).

- `py study0.py run` runs all 1,200 trials into `runs/<hash>/`. The hash covers endpoint, settings, seed and the full trial list, so changing any of them starts a new folder. It asks you to type RUN before starting (`--yes` skips this). `--limit N` attempts at most N pending trials, for example `--limit 120` for one repeat round.
- Order: repeat round 1 first, then round 2, and so on; shuffled within each round with the fixed `SEED` (D4.1).
- Failures: up to 3 attempts per trial, waiting `Retry-After` or 10/30/90 s. Every attempt is saved as `<trial>-failed-<id>.json`. After 3 failed attempts the trial is a final failure and is never retried or replaced (D4.3–D4.4). The run stops on 401/403, after 10 failures in a row, if the server returns a different model name, or if gpt-oss's `system_fingerprint` changes (D4.6–D4.7).
- Stopping is safe: Ctrl+C, a crash or a closed window loses at most the call in progress. Rerun `run` to resume. A `.lock` file stops two runs in the same folder; delete it only if you are sure no run is active.
- `py study0.py verify` checks every saved record against the plan and current settings, prints success/final-failure/pending/invalid counts per model × framing, fingerprints, token use and the time range, and writes `trial_status.csv` in the run folder. Exit code 1 means a problem was found.

## Tests

`py -m unittest discover -s tests -v` runs 33 offline tests against a local mock server (about 7 minutes; no ARC calls, no key needed).

## Coding (agreed with the PI Nov 11)

- `py study0.py sample` writes `coding_plan.csv`: the fixed-rule sample of 150 main items + 20 practice items. It was generated before any formal output and must not change; the command refuses if the file differs. **Raters must not open it**: it maps item IDs to model and question.
- `py study0.py export` (after the run) writes blinded sheets to `coding/`: `R1_main.csv`, `R2_main.csv`, `R3_main.csv` (100 items each, two pairs per rater) and `R*_practice.csv` (20 each). Sheets show only an item ID, the conversation and the answer. It never overwrites a sheet. Unavailable trials (final failures) are left out and listed in `coding/export_report.txt`.
- Each pair codes items from the top of its list: minimum 25, maximum 50 per pair. Fill `main_reading`, `mentions_alternative`, `certainty`, `no_clear_preference` with the exact words in `codebook_v0.md`; write `UNCODABLE` in `notes` for refusals. Excel is fine: save as CSV (either "CSV UTF-8" or plain CSV).
- `py study0.py kappa --practice` after the practice round; `py study0.py kappa` after main coding. Writes `coding/kappa_*.txt` with κ, raw agreement and confusion tables per pair and pooled.

## Model coder (GLM-5.3)

- `py study0.py judge` codes all 1,200 answers with a frozen prompt (temperature 0, never tuned on human labels) into `runs/judge/<hash>/`.
- `py study0.py judge-retry` re-codes only the main pass's final failures, streamed with a larger token budget, into a separate folder (rule fixed before any retry output; see decisions.md E3).
- `py study0.py judge-report` writes `results/judge_report.txt` and `results/judge_table.csv`: model-coder vs. human kappa and the model x framing table, with per-cell counts of items from the retry and items never coded. Human coders should not run it until their sheets are done.
