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

## 4b. Formal run record (`runs/a2216350ebd7/`)

- **Completed:** 1,200 / 1,200 trials saved and verified (`py study0.py verify`: OK, 0 invalid, 0 final failures, 0 pending). First call 2026-11-11 14:31 UTC, last 2026-11-12 04:17 UTC. Round 1 (`--limit 120`) ran first, then the remainder.
- **Drift:** gpt-oss returned one `system_fingerprint` for all 600 calls; DeepSeek returned none (model name matched on all 600).
- **Token use:** gpt-oss max 2,140 / 4,096 (median 901). DeepSeek max 3,610 / 4,096 (median 394); 3 DeepSeek answers used over 3,000, almost all hidden reasoning (one: 3,513 reasoning tokens, 62-word answer). None were cut off, but the margin was small; report this.
- **Failed attempts: 9, all retried successfully** (7 trials needed a second or third attempt). Five of the nine were gpt-oss, negatively leading, scenario 17 (R04 twice, R06 twice, R07 once). **Limitation:** if slow calls tend to produce longer answers, keeping only the successful retry could slightly under-represent long answers in that cell.
- **Total time limit:** one round-1 call hung 943 s because urllib's timeout is per socket operation, not per call. A total 180 s limit was added to `fetch()` before the remaining 1,080 calls (tested). Two later attempts still show long elapsed times (9,436 s ending in a dropped connection; 635 s ending in a timeout). The most likely cause is the computer sleeping mid-call, because nothing in the process runs while the machine sleeps. They were retried and do not affect any saved answer. **For future runs, keep the computer awake.**
- **Analysis note:** `elapsed_s` is not a reliable latency measure for calls that spanned sleep; don't analyse it.

## 5. Coding plan

| ID | Decision | Proposal | Status | Owner |
|---|---|---|---|---|
| D5.1 | Who the raters are | Three raters, labelled R1, R2, R3 in the sheets (Ifzaal, Vishal, Vikas; the name-to-label mapping is agreed within the team). They work in rotating pairs P1 = R1+R2, P2 = R2+R3, P3 = R1+R3 | DECIDED (PI, Nov 11) | Team |
| D5.2 | Codebook | `codebook_v0.md` → revised once after calibration → frozen as v1 before independent coding | PROPOSED | Ifzaal |
| D5.3 | Practice set | 20 repeat-4 items, one per scenario, model × framing spread evenly, fixed by `py study0.py sample` (`coding_plan.csv`, set = practice). All three raters code them, discuss, then freeze codebook v1. Not part of κ | DECIDED (rule) | Ifzaal |
| D5.4 | How much to code | **Agreed with PI Nov 11.** Fixed rule: repeat 1 of every scenario × model × framing (120) + 5 repeat-2 items per model × framing from randomly drawn scenarios (30) = 150, dealt so any stopping point stays balanced. Each pair codes in its list order: **minimum 25, maximum 50 per pair** = 75–150 double-coded responses, 50–100 per person. Generated by `py study0.py sample` (seed 20261113) on Nov 11 **before any formal output existed**; frozen in `coding_plan.csv`. Full human coding of all 1,200 is deferred to the conference paper | DECIDED (PI, Nov 11) | Team + PI |
| D5.5 | Blinding | Coders see a sheet shuffled once with a fixed seed (both raters use the same order, so a partly finished set is still a random subset; see section 8), with an opaque item ID, the conversation and the response text only. No model, framing, question line or repeat number. The key file stays with Ifzaal. Coders know responses may echo the question; that is a known limit of blinding | PROPOSED | Ifzaal |
| D5.6 | Independence | No discussion between raters between codebook freeze and κ computation | PROPOSED | Raters |
| D5.7 | Agreement statistic | Cohen's κ for each field, for each pair and pooled across pairs, on independent labels before reconciliation, with raw agreement and a confusion table (`py study0.py kappa`). Report whether each pair's coded items are the first k in its list | PROPOSED | Ifzaal |
| D5.8 | Reconciliation | The pair discusses each disagreement; if unresolved, the third rater (not in that pair) decides. Independent labels are kept unchanged in the original sheets | PROPOSED | Raters |
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
| E3 | Model coder (PI's 'LLM in the loop', Nov 11): a third ARC model, not gpt-oss or DeepSeek, codes all 1,200 ~~with codebook v1~~ with the codebook v0 rules (no v1 exists; see the Nov 19 log entry). Humans code blind to its labels. Report κ(model, each human) beside κ(human, human) on the same items. If comparable, show model labels on all 1,200 marked as validated on N items; otherwise report human-coded items only. Model labels never replace human labels in the κ requirement | PROPOSED (PI agreed in principle); implemented Nov 19 |

**E3 implementation (Nov 19, before any judge output existed):**
- **Model:** `GLM-5.3` on ARC (it returns the pinned name `GLM-5.3-0`), a different model family from both models being studied. Settings `temperature 0.0, max_tokens 8000` (ARC's cap for non-streaming requests), with a 600 s total time limit per call. One user message, no system prompt.
- **Smoke test** (folder `166b867f30ab`, `max_tokens 4096`): 3 of 3 items coded with valid JSON. GLM reasons before answering: 679–3,327 reasoning tokens and 53–151 s per item. The largest used 3,442 of 4,096 tokens, so the limit was raised to 8,192 before the full run. The smoke folder is kept and is not used in the analysis.
- **Parallelism:** `--workers N` sends N requests at once, with the same retry and stop rules. It changes speed only, not labels.
- **Prompt:** `JUDGE_PROMPT` in `study0.py`. It restates the codebook v0 rules M1–M7, C1–C3 and the alternative rule, then asks for JSON. The prompt is frozen: changing the model, settings or prompt creates a new folder under `runs/judge/`. **It is not tuned on human labels.** If it has to change, log the change here, with the reason, before the rerun.
- **Blinding:** the judge sees only the conversation and the response text, like the raters. Labels are never printed while it runs. Item-level labels stay in `runs/judge/<tag>/judge_labels.csv`, which is gitignored. R1 must not open it until R1's sheet is finished.
- **Order:** the 150 main-sample items in sheet order, then the 20 practice items, then the remaining 1,030 in run order. If time runs out, the human-coded items are already done.
- **Failures:** same rules as the run: 3 attempts, then final failure. A reply without valid JSON labels counts as a failed attempt. The run stops on 401/403, after 10 failures in a row, or if the returned model name differs.
- **Report:** `py study0.py judge-report` writes:
  - `results/judge_report.txt`: κ(judge, each human), pooled, beside κ(human, human).
  - `results/judge_table.csv`: the D6.4 table from judge labels, plus the D6.5 flag rate and the negative rate excluding flagged items.
- **Main pass result (folder `ea34f421e7a9`, finished Nov 20):** 1,125 of 1,200 coded. 75 final failures: in 195 of their 225 attempts GLM used all 8,000 tokens before answering (`finish_reason 'length'`); the other 30 were HTTP 504 gateway timeouts. By cell: DeepSeek negatively leading 24, positively leading 17, neutral 7; gpt-oss negatively leading 11, positively leading 11, neutral 5. 63 of 75 are under leading framings, so the missing labels are not random. 140 of the 150 human-sample items were coded.
- **Retry pass (rule fixed Nov 20, before any retry output):** `py study0.py judge-retry` re-codes **only** the main-pass final failures. Same model, prompt and temperature; streamed, `max_tokens 32000`, 1,500 s limit, up to 3 attempts. Streaming is used because ARC's 8,000 cap applies to non-streamed replies, and a stream keeps the gateway connection active. The results go in a separate folder (`e38a0c6d8477`) and the main pass is left unchanged. The report gives, per cell, how many labels came from the retry pass (`n_from_retry`) and how many items are still uncoded (`n_not_coded`). The item-level file marks each label `judge_pass` = main/retry. It refuses to start while the main pass is running or has pending items.

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
| 2026-11-11 | D5 | Coding plan agreed with PI: rotating pairs, 25-50 per pair, fixed-rule sample frozen in coding_plan.csv before formal outputs; model coder (E3) proposed | PI chat Nov 11 | PI |
| 2026-11-11 | D2-D4 | Formal run started by Ifzaal (runs/a2216350ebd7). PI received the settings; no explicit reply on them | Deadline | Ifzaal |
| 2026-11-12 | 4b | Formal run complete: 1,200/1,200 verified; 9 failed attempts all retried; total time limit added after round 1 | Run record | — |
| 2026-11-18 | D5.2 | Codebook v0 rewritten as a shared step-by-step guide for the raters. Rules unchanged | Raters found v0 hard to apply | Ifzaal |
| 2026-11-19 | D5.3 | **Deviation:** the practice round and calibration call did not happen. R2 and R3 coded main items with codebook v0; no v1 was frozen | Time (deadline Nov 20) | Team |
| 2026-11-19 | D5.4 | Sheets returned: R2 and R3 each coded their first 30 main rows (15 shared P2 items so far; minimum is 25 per pair). Two R3 item IDs damaged by Excel (scientific notation) were restored by position; text and order verified unchanged. `kappa` now does this automatically, and only when row order is unchanged | Sheet check | Ifzaal |
| 2026-11-19 | E3 | Model coder implemented (`judge`, `judge-report`; GLM-5.3, temperature 0, frozen prompt from codebook v0) | Planned exploratory analysis | Ifzaal (PI agreed in principle Nov 11) |
| 2026-11-19 | E3 | After the 3-item smoke test: expected returned name `GLM-5.3-0`; max_tokens 4096 → 8192; per-call limit 600 s; `--workers` added. Prompt unchanged | One item used 3,442 / 4,096 tokens; ~1 min per item sequentially | Ifzaal |
| 2026-11-19 | E3 | max_tokens 8192 → 8000. Folder `4ea32a807330` has only refused requests (8 × HTTP 413) and no labels; it is not used | ARC caps non-streaming requests at 8,000 tokens | Ifzaal |
| 2026-11-20 | E3 | Main pass finished: 1,125 / 1,200 coded, 75 final failures (63 under leading framings). Retry pass added (`judge-retry`): only those 75, streamed, max_tokens 32000, separate folder, counted separately in the report | Failures cluster in leading framings, so dropping them would bias the judge table | Ifzaal |
| 2026-11-20 | E3 | Retry pass finished (folder e38a0c6d8477): 69 of 75 recovered, 6 final failures (all DeepSeek-V4.1-Flash: 3 negatively leading, 2 positively leading, 1 neutral; all `finish_reason='length'` at 32,000). Total coded 1,194 / 1,200; 149 / 150 human-sample items. Counts taken from file names only; no labels opened | Records the missing-data count for the poster before judge-report is run | Ifzaal |
| 2026-11-20 | D6 | R1 finished coding the first 50 rows (coding/R1_main_updated.csv, same row order, copied to R1_main.csv; partial copy kept in coding/previous/). Then ran `kappa` (pooled human-human, 3 pairs x 25 = 75 items: main_reading 0.692, alternative 0.524, certainty 0.640, no_clear_preference 0.639) and `judge-report` (judge-human n 154: 0.722, 0.593, 0.704, 0.526). Poster main chart: pooled negative-reading rate per model x framing as bars, with each scenario's rate as a dot beside the bar, instead of the 20-row dot plot in D6.3 (too dense to read at poster distance; the same per-scenario rates are shown) | Blinding held: judge labels were first opened after R1's sheet was complete | Ifzaal |
