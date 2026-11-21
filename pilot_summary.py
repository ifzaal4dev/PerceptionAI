"""Phase 1 pilot: aggregate-only summary per scenario. Never writes individual responses.

Usage:  py pilot_summary.py "<path to the pilot export .xlsx>"

Reads the export where it lives (keep it on the PI's VT OneDrive, not in this repo) and
writes results/pilot_summary.csv: for each of the 20 scenarios, n, mean and SD of the
negative-intent rating, mean confidence, and mean reasonableness of the negative and
neutral readings (all 1-7). Uses consenting adults who passed the attention check
("select 5"); counts of everyone else are printed.

Pilot rule (instrument 3a / build spec): mean negative intent about 3-5, relatively high
spread between people, both readings averaging 4 or higher. The spread cut-off and the
tie-break for picking 12 are not written yet (PI decision), so this only flags the first
and third conditions and ranks spread; it does not pick scenarios.
"""
import csv
import json
import statistics
import sys
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent
FIRST_SCENARIO_COL = 10   # after timestamp, consent, age check and 7 background items
ATTENTION_AFTER = 10      # the "select 5" item follows the 10th scenario


def main(path):
    scenarios = json.loads((ROOT / "scenarios.json").read_text(encoding="utf-8"))
    rows = list(openpyxl.load_workbook(path, read_only=True, data_only=True).worksheets[0].iter_rows(values_only=True))
    header, data = rows[0], [r for r in rows[1:] if any(v not in (None, "") for v in r)]

    # Locate each scenario block and the attention item, checking the headers match.
    blocks, col = [], FIRST_SCENARIO_COL
    for i, s in enumerate(scenarios):
        if i == ATTENTION_AFTER:
            if "select 5" not in str(header[col]):
                raise SystemExit(f"Expected the attention item at column {col}, found {header[col]!r}")
            attention_col = col
            col += 1
        h = str(header[col])
        if f"How negative is {s['sender']}'s intent" not in h:
            raise SystemExit(f"Scenario {s['id']}: expected {s['sender']} at column {col}, found {h!r}")
        blocks.append((s, col))
        col += 4

    def yes(v):
        return str(v or "").strip().lower().startswith("yes")

    consented = [r for r in data if yes(r[1]) and yes(r[2])]
    passed = [r for r in consented if r[attention_col] == 5]
    print(f"Responses: {len(data)}; consenting adults: {len(consented)}; "
          f"passed attention check: {len(passed)} (used below)")

    def num(v):
        return float(v) if isinstance(v, (int, float)) else None

    out = []
    for s, c in blocks:
        neg = [x for x in (num(r[c]) for r in passed) if x is not None]
        conf = [x for x in (num(r[c + 1]) for r in passed) if x is not None]
        r_neg = [x for x in (num(r[c + 2]) for r in passed) if x is not None]
        r_neu = [x for x in (num(r[c + 3]) for r in passed) if x is not None]
        m = statistics.mean(neg) if neg else float("nan")
        row = dict(scenario=s["id"], sender=s["sender"], n=len(neg),
                   mean_negative_intent=round(m, 2),
                   sd_negative_intent=round(statistics.stdev(neg), 2) if len(neg) > 1 else "",
                   mean_confidence=round(statistics.mean(conf), 2) if conf else "",
                   mean_reasonable_negative=round(statistics.mean(r_neg), 2) if r_neg else "",
                   mean_reasonable_neutral=round(statistics.mean(r_neu), 2) if r_neu else "",
                   n_neutral_reading=len(r_neu))
        row["mean_3_to_5"] = "yes" if 3 <= m <= 5 else "no"
        row["both_readings_4plus"] = ("yes" if r_neg and r_neu and statistics.mean(r_neg) >= 4
                                      and statistics.mean(r_neu) >= 4 else "no")
        out.append(row)
    ranked = sorted((r for r in out if r["sd_negative_intent"] != ""), key=lambda r: -r["sd_negative_intent"])
    for rank, r in enumerate(ranked, 1):
        r["sd_rank"] = rank

    columns = list(out[0].keys()) + ["sd_rank"]
    (ROOT / "results").mkdir(exist_ok=True)
    with open(ROOT / "results" / "pilot_summary.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        w.writerows(out)
    print(f"{'S':>3} {'sender':<7}{'n':>3}{'neg M':>7}{'SD':>6}{'conf':>6}{'rNeg':>6}{'rNeu':>6}  3-5  both>=4  SDrank")
    for r in out:
        print(f"{r['scenario']:>3} {r['sender']:<7}{r['n']:>3}{r['mean_negative_intent']:>7}{r['sd_negative_intent']:>6}"
              f"{r['mean_confidence']:>6}{r['mean_reasonable_negative']:>6}{r['mean_reasonable_neutral']:>6}"
              f"  {r['mean_3_to_5']:<4} {r['both_readings_4plus']:<8} {r.get('sd_rank', '')}")
    both = [r["scenario"] for r in out if r["mean_3_to_5"] == "yes" and r["both_readings_4plus"] == "yes"]
    print(f"Meet mean 3-5 and both readings >= 4: {len(both)} scenarios {both}")
    print("Wrote results/pilot_summary.csv (aggregates only).")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
