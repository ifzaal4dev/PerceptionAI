# Qualtrics build spec: pilot (3a) and main survey (3b)

For Vishal and Vikas · IRB #26-1078 · Drafted Nov 11, 2026 by Ifzaal

**Source of truth:** the approved instruments `3a_Instrument_Phase1_Pilot_Survey_26-1078.docx` and `3b_Instrument_Phase2_Main_Survey_26-1078.docx`. Copy wording **verbatim** from them; this file is a build checklist, not new wording. Items marked **[SUGGESTION]** are build conventions, not approved content. Items marked **[PI]** need Dr. Nizamani's decision before launch. Anything that changes participant-facing content or procedure goes through the PI and, if needed, an IRB amendment.

---

## 0. Settings for both surveys

- [ ] Built in the **VT-licensed Qualtrics** account. Participants use Qualtrics only, never Excel files or Microsoft Forms (IRB-approved platform).
- [ ] **Anonymize responses ON**: no IP address, no location. No names or emails anywhere.
- [ ] Information sheet text pasted verbatim from `2_Information_Sheet_26-1078.docx` as the first page.
- [ ] Exports go **only** to the PI's VT OneDrive. Never into the code repo, personal drives, email or chat.
- [ ] **[SUGGESTION]** Name every question with the IDs below, so exports have readable column names and merge cleanly.
- [ ] **[SUGGESTION]** Export as numeric values (1–7), with "Recode values" checked so 1 means 1.

---

## 1. Pilot survey (3a): about 15 min, 20–30 adults

| Block | Content (verbatim from 3a) | Question IDs [SUGGESTION] |
|---|---|---|
| Consent | Information sheet, then Q1 consent (No → end of survey) | `Q1` |
| Eligibility | Q2: 18 or older? (No → end of survey) | `Q2` |
| Background | B1–B7 exactly as in 3a | `B1`–`B7` |
| Scenarios | All **20** conversations, **one per page, random order** (every participant sees all 20) | see below |
| Attention check | After the **10th** scenario shown: "please select 5" (1–7) | `AC1` |
| Closing | C1 optional open text, then the end page text from 3a | `C1` |

**Each scenario page** (`S01`…`S20`):
- the conversation, exactly as in the 3a table (including the relationship line);
- `S01_R1` How negative is [sender]'s intent in the last message? (1–7);
- `S01_R4` How confident are you in your reading of [sender]'s message? (1–7);
- `S01_P1` / `S01_P2`: the **negative** and **neutral** readings from the 3a table, each rated "How reasonable is this reading?" (1–7). Randomize their order on the page, and **keep the IDs tied to the reading, not the position**: `_PNEG` and `_PNEU` are clearer **[SUGGESTION]**.

**Build tip [SUGGESTION]:** one block with **Loop & Merge** (20 rows: sender, conversation, negative reading, neutral reading) and "Randomize loop order" is much faster than 20 hand-built pages. Place AC1 with display logic on the current loop number = 10, or split into two loops of 10.

**What the pilot is for:** choosing the 12 main-study scenarios using the protocol rule: mean negative intent about 3–5, relatively high spread between people, and both readings averaging 4 or higher. **[PI]** The tie-break rule if more than 12 qualify (or fewer) isn't written yet.

---

## 2. Main survey (3b): about 15–20 min, 60–70 new adults

Can be built now as a shell, but the 12 scenarios and their AI texts are filled in **after the pilot**.

| Block | Content (verbatim from 3b) | Question IDs [SUGGESTION] |
|---|---|---|
| Consent and eligibility | Info sheet, Q1, Q2, **Q3 "taken part before?"** (Yes → end; No or Not sure continue) | `Q1`–`Q3` |
| Background | B1–B7 (same as pilot) | `B1`–`B7` |
| Pre-ratings | 12 scenarios, **random order**, R1–R4 each; AC1 placed among them | `PRE_Sxx_R1`…`R4`, `AC1` |
| Filler | 5 activity items (cooking, walking, movies, reading, music), 1–7 | `F1`–`F5` |
| Post-ratings | Same 12, **re-randomized**, each with its condition text; R1–R6 | `POST_Sxx_R1`…`R6` |
| AC2 | After the Alex/Jordan post screen: "what were Alex and Jordan working on?" | `AC2` |
| AI questions | M1–M4, **asked once** after all scenarios | `M1`–`M4` |
| Closing | G1, G2 (optional), then the debriefing text from `4_Debriefing_Statement_26-1078.docx` | `G1`, `G2` |

### Conditions and versions

Every participant sees all three conditions, 4 scenarios each. A Qualtrics **Randomizer (evenly present)** assigns one of three versions and stores it as embedded data `version` = V1/V2/V3.

Split the 12 selected scenarios into groups A, B, C of 4 each:

| Version | Group A | Group B | Group C |
|---|---|---|---|
| V1 | No AI | Confident AI | Hedged AI |
| V2 | Confident AI | Hedged AI | No AI |
| V3 | Hedged AI | No AI | Confident AI |

Within each AI condition, 2 scenarios get a **mildly negative** AI text and 2 get a **neutral** one.

**[PI] Direction counterbalancing:** with only 3 versions, each scenario's direction (negative or neutral) is the same for everyone, so direction is tied to scenario. Crossing direction too would take 6 versions. Ask which she wants.

**[SUGGESTION] Record for every participant**, as embedded data: `version`, and for each scenario `Sxx_cond` (none / confident / hedged) and `Sxx_dir` (neg / neu / none). The analysis needs these columns. The protocol says assigned condition and scenario order are recorded.

### Screen layouts (verbatim from 3b)

- **AI condition:** the conversation, then *Someone asked an AI assistant: "What did [sender] mean by the last message?" The AI assistant replied:* [AI text]
- **No-AI condition:** the conversation, then a box titled **"About this conversation"** with a neutral description of similar length.

### Text bank needed before launch (Part 1 deliverable)

For **each of the 20 scenarios** (so that whichever 12 the pilot picks are ready), prepare 4 AI texts plus 1 control:

| Text | Template (3b) |
|---|---|
| Confident, negative | Based on the wording, [sender]'s "[message]" is mildly passive-aggressive. [Sender] is clearly [negative reading]. |
| Hedged, negative | I'm not certain, but [sender]'s "[message]" may be mildly passive-aggressive. [Sender] might be [negative reading]. |
| Confident, neutral | Based on the wording, [sender]'s "[message]" is a sincere reply. [Sender] is clearly [neutral reading]. |
| Hedged, neutral | I'm not certain, but [sender]'s "[message]" may be a sincere reply. [Sender] might be [neutral reading]. |
| No-AI description | Neutral description of the relationship and situation, similar length |

Rules from the course brief: within a certainty pair, keep the interpretation identical and match length within a few words; keep drafts, edits, word counts and the ARC model settings used; freeze and review before use.

**[PI] Fix before writing the bank:** the template says "a sincere **reply**" but the 3b example says "a sincere **reassurance**"; the example also adds "their part" to the 3a reading. Pick one wording.

---

## 3. Testing checklist (both surveys)

- [ ] Preview each version (V1, V2, V3) start to finish, on desktop and phone.
- [ ] Check that each scenario shows the right condition text for each version (fill in the table above with real scenario numbers).
- [ ] Do a test export and check the column names, the `version` and `Sxx_cond`/`Sxx_dir` columns, numeric values, and timing.
- [ ] Time a full run-through (target 15 min pilot, 15–20 min main).
- [ ] **Delete all test responses** before launch (course requirement).
- [ ] Recruitment uses only the approved text in `1_Recruitment_Materials_26-1078.docx`.

## 4. Open decisions for the PI

1. **Scenario selection:** the tie-break rule (pilot → 12).
2. **Direction counterbalancing:** 3 versions or 6 (above).
3. **Manipulation check:** the protocol compares perceived certainty between conditions, but M1 is asked once overall. Change the analysis plan, or amend the survey?
4. **Template wording:** "reply" vs "reassurance".
5. **AC2:** it refers to Alex/Jordan, so it needs rewording if the pilot drops scenario 1.
6. **Exclusions:** the attention-check and "too fast" rules, written before data collection (the protocol promises this).
