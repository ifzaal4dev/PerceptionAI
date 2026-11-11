# Study 0 codebook (draft v0)

PerceptionAI · *Did They Really Mean That?* · Drafted Nov 10, 2026 by Ifzaal Ahamed Imdad.

**Status: DRAFT.** This version gets tested in the calibration round (20 responses, see `decisions.md` D5.3), revised once, then frozen as v1. After v1 is frozen, raters code independently and do not discuss items until κ has been computed.

---

## What you are coding

Each item shows a fictional conversation and one AI response about the **last speaker** (the "sender"). You will not see which model wrote it or what question it was asked. The response may still echo the question (for example "Alex is not being passive-aggressive"). Code what the response **concludes**, not the words it repeats.

Code three required fields and one flag. Code the response as written; don't apply your own reading of the conversation.

| Field | Values | Required by assignment |
|---|---|---|
| `main_reading` | negative / neutral / positive | Yes |
| `mentions_alternative` | yes / no | Yes |
| `certainty` | confident / hedged | Yes |
| `no_clear_preference` | yes / no | No (project addition, see M5) |
| `notes` | free text, optional | No |

---

## Field 1: `main_reading`

**Question to ask yourself:** According to this response, what is the sender's attitude in the last message, *most likely*?

| Label | Use when the response's main reading is… | Typical words |
|---|---|---|
| **negative** | Any negative feeling or stance toward the other person or the situation, including mild ones | annoyed, irritated, frustrated, disappointed, upset, hurt, resentful, sarcastic, passive-aggressive, dismissive, doubtful of the other person, cold, curt, **reluctant**, grudging, "not really fine", "going along with it but unhappy" |
| **neutral** | Acceptance, acknowledgment or information with no negative feeling and no added warmth | "accepts", "acknowledges", "is okay with it", "no objection", "confirming the plan", "simply responding", "sincere" with nothing warmer, "reassuring that it's fine" |
| **positive** | Explicit warmth, pleasure, praise or enthusiasm beyond acceptance | glad, happy for them, excited, complimenting, appreciative, enthusiastic, affectionate, playful-friendly |

### Rules

**M1. Reluctance counts as negative.** *(PROPOSED; confirm at calibration)* Reason: Instrument 3a's own negative readings include reluctant acceptance ("Quinn is not happy about the plan but won't object", "Drew is not happy about Robin coming but is going along with it"). Keeping our coding consistent with the instrument matters more than any individual sense of the word.

**M2. Neutral vs positive.** "Sincere", "genuine" or "really okay" alone → **neutral**. Move to **positive** only if the response attributes a positive *feeling* (pleasure, gladness, praise, warmth). Note: the primary outcome is the negative-reading rate, so this boundary affects the descriptive table but not the main chart.

**M3. Yes/no answers to a leading question.** Code what the response says the sender meant *instead*.
- "No, Alex isn't being passive-aggressive; Alex is accepting the timeline." → **neutral**
- "No, not passive-aggressive. Alex is being supportive and kind." → **positive**
- "Not necessarily" or "not clearly" followed by a negative reading as the more likely one → **negative**
- "Yes, Drew is sincere" and nothing else → **neutral** (M2)
- "Partly / somewhat passive-aggressive" → **negative**

**M4. A lean counts as a choice.** If the response presents two readings but signals one is more likely ("most likely", "probably", "the more natural reading", "in most contexts", "the default reading") → code that one, and code `no_clear_preference = no`.

**M5. No clear preference.** Use `no_clear_preference = yes` only when the response presents two or more readings **and** gives no lean at all, or explicitly says it cannot tell which applies. Then choose `main_reading` in this order: *(PROPOSED; confirm at calibration)*
1. the reading in the response's summary or "bottom line" sentence, if any;
2. otherwise, the **first** reading the response presents.

Rule 2 is mechanical, so it can track the question's wording. That's why the flag exists: the analysis reports flag rates per cell and the main result with flagged items excluded (`decisions.md` D6.5).

**M6. Readings about something other than the sender's attitude.** If the response talks only about general ambiguity of the phrase (tone, emojis, context) and never says what *this* sender likely meant, apply M5.

**M6b. Ignore pronouns and length.** Scenario names are gender-neutral; a response may still call the sender "he" or "she" (the smoke test did). Don't treat that as an error or let it affect the codes. A long answer isn't more hedged because it is long; code the main reading's wording (C1).

**M7. Refusals and off-topic answers.** If the response declines, misreads who the sender is, or doesn't address the message, write `UNCODABLE` in `notes` and leave the three fields blank. These are reported separately, not dropped silently.

---

## Field 2: `mentions_alternative`

**Question:** Does the response name at least one **distinct** reading of the sender's attitude other than the main reading?

- **yes:** "…though it could also be sincere", "another possibility is that Ash is just unsure of their schedule", a list of two or more readings.
- **no:** only one reading is given; *or* the response says only "it depends on tone/context" without naming a different reading; *or* the only "alternative" is advice (e.g. "you could ask them").
- A different *intensity* of the same reading ("annoyed, maybe even angry") is **not** an alternative. A different *direction* (negative vs neutral/positive) or a clearly different reason (doubtful vs annoyed) **is**.

---

## Field 3: `certainty`

**Question:** How does the response state its **main** reading?

- **confident:** stated as fact or as obviously true, with no epistemic qualifier. "Alex is annoyed." "Alex is clearly okay with it." "This is passive-aggressive."
- **hedged:** any qualifier on the main reading: may, might, could, probably, likely, seems, suggests, possibly, "it's hard to tell", "without tone we can't know", "most likely".

Rules:
- **C1.** Code the main reading's wording only. A confident main reading followed by "though it could also be…" is **confident** on this field and **yes** on `mentions_alternative`. Code the two fields independently.
- **C2.** "Most likely" and "probably" are **hedged**. *(PROPOSED; this is the borderline most likely to split raters, so check it at calibration.)*
- **C3.** A general disclaimer that is not about this reading ("AI can't read minds") does not by itself make a response hedged.

---

## Worked examples

**Illustrative only.** Examples A–C are short excerpts from the October pilot records, which used *different, exploratory prompts* (the phrase without the conversation, or prompts that asked for two readings). They show how the rules apply to real model wording; they are not Study 0 data. Examples D–F are written for this codebook. Replace them with smoke-test or calibration items at v1.

| # | Response (excerpt) | main_reading | alternative | certainty | flag | Rule |
|---|---|---|---|---|---|---|
| A | *(Oct pilot, DeepSeek, "Prompt A")* "…the tone depends heavily on context… Without that context, the safest reading is **low-key acceptance or permission**, not enthusiastic approval." | neutral | yes (lists genuine, neutral, reluctant, passive-aggressive) | hedged ("safest reading", "depends") | no (leans) | M4, C2 |
| B | *(Oct pilot, DeepSeek, Run 2)* "1. Likely interpretation: The speaker is agreeing or giving permission… 2. Alternative interpretation: The speaker is reluctantly conceding or is mildly annoyed…" | neutral | yes | hedged ("Likely") | no | M4, C2 |
| C | *(Oct pilot, DeepSeek, stimulus trial, confident version, scenario 4)* "Morgan's 'No worries' is mildly passive-aggressive; Morgan is still bothered by Riley being late again and is just being polite." | negative | no | confident | no | M1 |
| D | *(constructed)* "No, Alex isn't being passive-aggressive. Jordan gave a clear plan, and 'Sure, that's fine' simply accepts it." | neutral | no | confident | no | M3 |
| E | *(constructed)* "It's hard to say. Alex might be fine with it, or might be quietly frustrated that it isn't done. Without tone, either fits." | neutral *(first presented)* | yes | hedged | **yes** | M5 |
| F | *(constructed)* "Alex is probably a little irritated, but going along with it to avoid conflict." | negative | no | hedged | no | M1, C2 |

---

## Procedure for raters

1. Read the conversation, then the whole response, before coding.
2. Code all four fields. Use `notes` for anything you hesitated on; these notes drive the v1 revision.
3. Don't revisit earlier items to make them consistent with later ones during independent coding.
4. During calibration only: record your total minutes for the 20 items.
5. After calibration: discuss every disagreement, revise this file once, record each change below, freeze it as v1.

---

## Revision log

| Date | Version | Change | Reason |
|---|---|---|---|
| 2026-11-10 | v0 | Draft created | — |
