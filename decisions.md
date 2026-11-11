# Study 0 decisions file (draft v0)

PerceptionAI · *Did They Really Mean That?* · IRB #26-1078 (human study only; Study 0 uses model outputs and needs no participant data)

Drafted Nov 10, 2026 by Ifzaal Ahamed Imdad. Nothing below is decided until the **Status** column says DECIDED and the decision date is filled in. Proposals are proposals.

**Purpose.** Fix every choice that could be tuned after seeing results *before* the formal 1,200-call run and before any coding. If a decision changes after formal data exist, log it in the change log at the bottom with the date and reason.

**Status key.** OPEN = needs a choice. PROPOSED = a recommendation is written, waiting for agreement. DECIDED = frozen.

---

## 0. Deadlines that drive this file

| Date (ET) | What |
|---|---|
| Fri Nov 13, 11:59 p.m. | VTURCS title + author registration |
| Thu Nov 12 (target) | Freeze sections 1–4 so the full run can start |
| Fri Nov 13 (target) | Calibration round on 20 responses; freeze codebook v1 |
| Fri Nov 20, 11:59 p.m. | Abstract + poster submission (aim for early afternoon) |

---

## 1. Registration and credit

| ID | Decision | Proposal | Status | Owner | Decide by |
|---|---|---|---|---|---|
| D1.1 | Registered title | Official study title, or a poster title, per PI preference | OPEN | Ifzaal → PI | Nov 12 |
| D1.2 | Author list and order | Confirm with PI. Include all current contributors; ask PI how to acknowledge Jiale Peng's earlier work | OPEN | PI | Nov 12 |
| D1.3 | Registration submitted | Ifzaal submits and saves the confirmation | OPEN | Ifzaal | Nov 13 |

---

## 2. Run settings (fill after the smoke test)

Smoke test run Nov 11, 2026, 04:52–04:53 UTC (Nov 10 evening ET), `smoke_runs/a86d9d0da262/`. Six calls, scenario 1, repeat 1, all saved on the first attempt. These are setup data only (D4.9).

| ID | Setting | Starter value | Smoke observation | Proposal | Status |
|---|---|---|---|---|---|
| D2.1 | Models | `gpt-oss-120b`, `DeepSeek-V4.1-Flash` | Returned `model` matched the requested name on all 6 | Keep both | PROPOSED |
| D2.2 | temperature | 0.7 | Not echoed in the response, so the server's use of it can't be confirmed from the record | Keep 0.7: repeats are meant to sample variation. Note the limitation | PROPOSED |
| D2.3 | top_p | 1.0 | Not echoed | Keep | PROPOSED |
| D2.4 | max_tokens | 2048 | All 6 `finish_reason: stop`. Completion tokens: gpt-oss 186 / **1,497** / 988; DeepSeek 196 / 279 / 635. The gpt-oss negatively-leading answer used 73% of the budget in a single sample, so some of the 1,200 will likely hit the limit. gpt-oss reports `reasoning_tokens: 0` even though it returns reasoning text, so its reasoning count is not reliable | **Raised to 4096 in `study0.py` (Nov 10).** Re-run smoke to confirm (new settings hash → new folder; 6 calls, about 1 minute). Re-smoke folder: `smoke_runs/b0db9a335181/` (Nov 11, 04:58–04:59 UTC); saved request confirms `max_tokens: 4096`; all 6 `stop`; completion tokens gpt-oss 256 / **1,551** / 504, DeepSeek 222 / 370 / 182. Longest answer uses 38% of the new limit | PROPOSED (applied; re-smoke passed; awaiting team freeze) |
| D2.5 | Timeout | 180 s | Longest call ≈ 24 s (gpt-oss, negatively leading), from gaps between start times | Keep 180 s | PROPOSED |
| D2.6 | Reasoning text | Saved only inside the raw response | Both models return `message.reasoning` (347–2,445 characters) | Keep in raw JSON; never shown to coders; not analysed | PROPOSED |
| D2.7 | Estimated run time | — | ≈ 14 s per gpt-oss call, ≈ 5 s per DeepSeek call → about 3–3.5 h sequential for 1,200 at the current limit; allow up to 5 h with 4096 | One sequential process is enough (D4.8); start Thu Nov 12 morning to finish the same day | PROPOSED |
| D2.8 | Drift record | — | gpt-oss returns `system_fingerprint` (a vLLM build string); DeepSeek returns none | Save `model`, `system_fingerprint` and `created` per record; drift check (D4.7) uses the fingerprint for gpt-oss and the model name only for DeepSeek | PROPOSED |
| D2.9 | Console encoding | — | Printing answer text in a Windows console crashed on a non-breaking hyphen (cp1252) | Any script that prints or exports answers writes UTF-8 explicitly (`encoding="utf-8"` files; `py -X utf8` for console) | PROPOSED |

**Re-smoke check (`b0db9a335181`).** Same returned model names and same gpt-oss `system_fingerprint` as the first run. Gaps between call starts 4.7–21 s, consistent with the D2.7 estimate. No failed-attempt files in either folder.

**Setup observation (now n = 2 per cell across the two smoke runs; still not a result).** All twelve answers would be coded *neutral* under codebook v0, and the length pattern repeated (gpt-oss "passive-aggressive?" answer: 922 then 1,036 words). One new borderline for calibration: gpt-oss's second "sincere?" answer says "sincere… rather than sarcasm". Is naming a reading only to reject it a `mentions_alternative = yes`? Settle this at calibration. Earlier, about the first run: all six answers would be coded *neutral* under codebook v0. The two neutral-question answers were short (31–54 words), gave no alternative and were stated confidently. The four leading-question answers named an alternative and hedged, and gpt-oss's ran to 572 and 922 words. This suggests a **hypothesis to note before the run, not a finding**: framing may change hedging, alternatives and length more often than it changes the main reading. If so, the poster's story is about certainty rather than direction, which connects directly to the human study's confident-vs-hedged manipulation.

**Coding-time warning.** Long gpt-oss answers will take far longer than 60 seconds to code. Re-estimate D5.4 from the timed calibration round before choosing the coding set.

---

## 3. Prompts

| ID | Decision | Proposal | Status |
|---|---|---|---|
| D3.1 | Keep the three questions exactly as in `study0.py` `QUESTIONS` | Yes. The neutral question is word for word the question shown above the AI reply in Instrument 3b, which is worth stating on the poster | PROPOSED |
| D3.2 | Known asymmetry | "Passive-aggressive" and "sincere" are not opposites, so the two leading framings are not mirror images. Report this as a limitation; do not compare the two leading framings as if symmetric | PROPOSED |
| D3.3 | No system prompt, one user message, no conversation history | Yes (as in starter) | PROPOSED |
| D3.4 | Scenario text source | `scenarios.json`, verified Nov 10 to match the Instrument 3a candidate table line by line for all 20 scenarios | DECIDED (verified) |

---

## 4. Run procedure and failure rules

**Implementation (Nov 11).** D4.1–D4.8 are implemented in `study0.py` (`run` and `verify` commands) and covered by 15 offline tests against a local mock server (`tests/test_study0.py`, all passing). The rules are still PROPOSED until the PI signs off; the code just makes them enforceable.

| ID | Decision | Proposal | Status |
|---|---|---|---|
| D4.1 | Run order | Run in 10 rounds by repeat number (all R01 trials, then all R02, …). Within each round, shuffle the 120 trials with a fixed seed (seed = **20261112**, set as `SEED` in `study0.py`). Purpose: a mid-run change on ARC's side cannot line up with one framing or model | PROPOSED |
| D4.2 | Success | HTTP 200, parseable JSON, `finish_reason == "stop"`, non-empty string `content` | PROPOSED |
| D4.3 | Retries | Up to 3 attempts per trial. Wait `Retry-After` if given, otherwise 10 s, 30 s, 90 s. Every attempt is saved, including failures | PROPOSED |
| D4.4 | Truncation (`finish_reason == "length"`) | Counts as a failed attempt and is retried under D4.3. If a trial still has no success after 3 attempts, it is a **final failure**: reported in the denominator table, never coded, never replaced by hand | PROPOSED |
| D4.5 | Timeouts | Count as failed attempts. A retry is a fresh independent sample, which is acceptable because repeats are exchangeable | PROPOSED |
| D4.6 | Stop condition | Stop the whole run if 10 consecutive attempts fail, or on 401/403. Investigate before resuming | PROPOSED |
| D4.7 | Model drift check | Record the returned `model` field and any fingerprint/version field on every record. If it changes mid-run, stop and consult PI before continuing | PROPOSED |
| D4.8 | Concurrency | One process, sequential, unless D2.7 shows the run will not finish by Nov 13 | PROPOSED |
| D4.9 | Smoke outputs | Setup data only. Never part of the formal dataset | DECIDED (starter design) |
| D4.10 | October pilot (14 records) | Historical, different prompts. Never pooled with Study 0 | DECIDED (handoff) |

---

## 5. Coding plan

| ID | Decision | Proposal | Status | Owner |
|---|---|---|---|---|
| D5.1 | Who the two raters are | ___ and ___. If Ifzaal is a rater, a third person resolves disagreements | OPEN | Team |
| D5.2 | Codebook | `codebook_v0.md` → revised once after calibration → frozen as v1 before independent coding | PROPOSED | Ifzaal |
| D5.3 | Calibration set | 20 responses drawn with a fixed seed from **repeat 4**, one per scenario, model and framing balanced as far as possible. Repeat 4 finishes early under the round-by-round order (D4.1), lies outside the repeats 1–3 subset (D5.4 option B), and survives the repeats 1–5 fallback (section 8). Calibration items are excluded from the κ set | PROPOSED | Ifzaal |
| D5.4 | How much to code | **Nov 11: the PI called 1,200 a huge task and suggested splitting 400 per person among three people. Splitting alone gives one label per response, so no κ is possible.** Reply sent/pending with options: double-code repeats 1–3 (360 responses) in rotating pairs = 240 each; or single-code all 1,200 plus a 240-response double-coded overlap = 480 each. Earlier options: Option A: all 1,200 (≈ 20 h per rater at 60 s each). Option B: a prespecified subset, repeats 1–3 for all 120 cells = 360 responses (≈ 6 h per rater). Choose before seeing any outputs. If B, get PI agreement and state the rule on the poster | OPEN | Team + PI |
| D5.5 | Blinding | Coders see a sheet shuffled once with a fixed seed (both raters use the same order, so a partly finished set is still a random subset; see section 8), with an opaque item ID, the conversation and the response text only. No model, framing, question line or repeat number. The key file stays with Ifzaal. Coders know responses may echo the question; that is a known limit of blinding | PROPOSED | Ifzaal |
| D5.6 | Independence | No discussion between raters between codebook freeze and κ computation | PROPOSED | Raters |
| D5.7 | Agreement statistic | Cohen's κ for each of the three fields, computed on independent labels before reconciliation, with the confusion matrix and raw percent agreement for each field | PROPOSED | Ifzaal |
| D5.8 | Reconciliation | Raters discuss each disagreement; unresolved items go to a third person. Final labels are the reconciled labels; independent labels are kept | PROPOSED | Raters |
| D5.9 | Timing | Raters record total minutes for the calibration set; use it to confirm D5.4 | PROPOSED | Raters |

---

## 6. Analysis (Part 2: descriptive only, no significance tests)

| ID | Decision | Proposal | Status |
|---|---|---|---|
| D6.1 | Primary outcome | **Negative-reading rate** = responses with reconciled main reading *negative* ÷ successfully coded responses, for each model × framing | PROPOSED |
| D6.2 | Denominators | Every table and chart shows the actual n. Up to 200 per model × framing (from 20 scenarios), up to 10 per scenario × model × framing. A separate table lists attempts, final failures and truncations per cell | PROPOSED |
| D6.3 | Main chart | Dot plot: one row per scenario (20), one panel per model, x = negative-reading rate (0–100%), one marker per framing, n beside each point. Pooled model × framing row underneath | PROPOSED |
| D6.4 | Required descriptive table | Model × framing: n coded, % negative / neutral / positive, % mentioning an alternative, % hedged | PROPOSED |
| D6.5 | Flagged "no clear preference" responses | Main analysis uses the forced label (codebook rule M5). Also report the flag rate per cell and the negative-reading rate with flagged items excluded | PROPOSED |

**Exploratory (labelled as exploratory on the poster; not required by Part 2)**

| ID | Analysis | Status |
|---|---|---|
| E1 | Resampling reference: under the neutral question, how much does the negative-reading rate differ between repeats 1–5 and 6–10 of the same prompt? Compare with the shift between framings. Exact method to be fixed here before the run | OPEN |
| E2 | Scenario-level framing shift: how many of the 20 scenarios move, in which direction | PROPOSED |
| E3 | LLM-as-judge: a model applies codebook v1 blind to the double-coded items; report judge-vs-human κ beside human-vs-human κ. Judge labels never replace human labels. Judge model must differ from the two studied models if possible | OPEN |

---

## 7. What the poster may claim

| ID | Decision | Proposal | Status |
|---|---|---|---|
| D7.1 | Evidence boundary | Study 0 results + the human study's approved design. Human results only if they exist by the deadline and the PI approves showing them | PROPOSED |
| D7.2 | Linking the studies | Allowed: "the neutral question matches the survey wording." Not allowed: claiming a participant's rating shift came from any Study 0 output, or that we detected what a sender really meant | PROPOSED |
| D7.3 | Example responses on the poster | Chosen by a rule fixed here before coding (e.g., the repeat-1 response for scenario 1 from each model under each framing), not because they look striking | PROPOSED |

---

## 8. Fallbacks (fixed now, not after seeing data)

| If… | Then… |
|---|---|
| ARC run cannot finish by Nov 14 | Formal dataset = repeats 1–5 for all cells (600 trials). State this rule on the poster |
| Coding of the D5.4 set is incomplete by Nov 17 | Report κ and results only on items both raters finished, which are a prefix of a pre-shuffled order, so the completed part is still a random subset. Show denominators |
| No human data by Nov 20 | Model-only poster; human study shown as design and next steps, no results |

---

## 9. Questions for the PI

1. Author list and order (D1.2); registered title (D1.1).
2. Coding all 1,200 versus the prespecified subset (D5.4).
3. **Manipulation-check mismatch.** The protocol says perceived AI certainty "will be compared between the confident and uncertainty-aware conditions," but Instrument 3b asks M1 once after all scenarios, so that within-person comparison is not possible. Options: change the analysis plan to describe M1 overall, or amend the survey to ask certainty after each AI scenario. Either way, decide before Phase 2 launches.
4. The protocol promises exclusion rules and a simulation-based power analysis before data collection, and the scenario-selection rule has no tie-break. Who writes these, and by when?
5. Whether any pilot results may appear on the poster (D7.1).

## 10. Notes for Vishal and Vikas (Part 1 / surveys)

- Instrument 3b's neutral template says "is a sincere **reply**" but the Scenario 1 example says "is a sincere **reassurance**." Choose one before writing the 80 texts.
- The 3b examples say Alex is annoyed that Jordan "has not finished **their part** yet"; the 3a negative reading says "has not finished yet." Keep the content identical across certainty pairs either way.
- `Research.docx` writes "Okey"; Instrument 3a says "Okay." Use the instrument wording.

---

## Change log

| Date | ID | Change | Reason | Agreed by |
|---|---|---|---|---|
| 2026-11-10 | — | Draft v0 created | — | — |
| 2026-11-10 | D2.x | Filled section 2 from smoke run `a86d9d0da262`; proposed max_tokens 4096 | gpt-oss used 1,497 / 2,048 tokens on one answer | Pending |
| 2026-11-10 | D2.4 | `study0.py` SETTINGS max_tokens 2048 → 4096 | Same as above; Ifzaal approved applying it | Ifzaal (team/PI freeze pending) |
| 2026-11-10 | D2.4 | Re-smoke `b0db9a335181` passed: 6/6 `stop`, max 1,551 / 4,096 tokens | Confirms the new limit | — |
| 2026-11-11 | D4.x | `run` and `verify` added to `study0.py`; seed 20261112 | Implements section 4 so the rules are enforced by code | Pending PI |
| 2026-11-11 | D5.4 | PI raised coding load (400 each among three) | Options for κ-compatible split drafted | Pending PI |
