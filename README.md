# PerceptionAI · first ARC run

Use Python 3.9+ and open a terminal in this extracted folder. The starter uses Python's standard library. On Windows use `py`. On macOS or Linux use `python3`.

1. Run `py study0.py plan`. This overwrites only the generated plan CSV. It makes no network requests. Check the 20 fictional conversations in scenarios.json against the candidate table in instrument 3a. Each prompt contains the conversation and one question. The instrument's suggested interpretations are excluded from the model input.
2. At https://llm.arc.vt.edu sign in to your own VT account. Open your profile, Settings, Account, API keys. Generate your personal key. Enter it only in the local hidden terminal prompt. The runner also supports the ARC_API_KEY environment variable.
3. Run `py study0.py smoke`. This requests one response for each model and framing on scenario 1. Use one terminal at a time. A run folder is determined by the exact prompts, endpoint, models and settings. Running the same command again skips saved successes. If a call fails, the script records the failed attempt and stops. A timeout can mean the server generated a response that was never received. For a 401/403, check the key and account. For a 429, wait the specified retry time if provided. If a model is missing or the output is truncated, document it and review model choice or settings before running the experiment.
4. Inspect one JSON per cell. Check the final answer is present, the complete raw response is saved, and the request contains one independent user message. Run smoke a second time to check for six skips. Treat these as setup outputs.
5. Before running the full experiment, reconcile any prior logs with the team, freeze the models and exact prompts/settings, and agree on the two independent coders' instructions. This starter deliberately executes only the six-call setup. The CSV describes the complete 1,200-call design. Keep exploratory work separate from the final dataset.

Source of scenario text: Phase 1 Pilot Survey, IRB 26-1078, candidate scenarios table. Source of trial counts and framings: PerceptionAI Part 2 assignment. Model IDs come from the team's pilot. The specific question forms, temperature 0.7, top_p 1.0, and output limit of 2,048 are starter choices for testing. Server defaults and model revisions may change. Log any settings or revisions available before a formal run. This package contains only fictional inputs for the model study. Human responses belong in the PI's VT systems.

ARC service reference: https://docs.arc.vt.edu/ai/011_llm_api_arc_vt_edu.html

## Formal run and verification (added Nov 11)

Only start once decisions.md sections 2–4 are frozen (PI sign-off).

- `py study0.py run` runs all 1,200 trials into `runs/<hash>/`. The hash covers endpoint, settings, seed and the full trial list, so changing any of them starts a new folder. It asks you to type RUN before starting (`--yes` skips this). `--limit N` attempts at most N pending trials, for example `--limit 120` for one repeat round.
- Order: repeat round 1 first, then round 2, and so on; shuffled within each round with the fixed `SEED` (D4.1).
- Failures: up to 3 attempts per trial, waiting `Retry-After` or 10/30/90 s. Every attempt is saved as `<trial>-failed-<id>.json`. After 3 failed attempts the trial is a final failure and is never retried or replaced (D4.3–D4.4). The run stops on 401/403, after 10 failures in a row, if the server returns a different model name, or if gpt-oss's `system_fingerprint` changes (D4.6–D4.7).
- Stopping is safe: Ctrl+C, a crash or a closed window loses at most the call in progress. Rerun `run` to resume. A `.lock` file stops two runs in the same folder; delete it only if you are sure no run is active.
- `py study0.py verify` checks every saved record against the plan and current settings, prints success/final-failure/pending/invalid counts per model × framing, fingerprints, token use and the time range, and writes `trial_status.csv` in the run folder. Exit code 1 means a problem was found.

## Tests

`py -m unittest discover -s tests -v` runs 15 offline tests against a local mock server (about a minute; no ARC calls, no key needed).
