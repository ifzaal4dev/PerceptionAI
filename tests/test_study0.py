"""Offline tests for study0.py against a local mock of the ARC API. No real API calls.

Run from the project folder:  py -m unittest discover -s tests -v
"""
from collections import Counter
import csv
import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import unittest
from unittest import mock

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
import study0  # noqa: E402


def answer(model, content="Alex is fine with Jordan finishing tonight.", finish="stop", fp="fp-1"):
    return 200, {}, {
        "id": "mock", "model": model, "system_fingerprint": fp,
        "choices": [{"index": 0, "finish_reason": finish,
                     "message": {"role": "assistant", "content": content}}],
        "usage": {"completion_tokens": 12},
    }


class MockARC:
    """Local HTTP server. `behavior(call_number, body)` returns (status, headers, payload)."""

    def __init__(self):
        self.calls = []
        self.behavior = lambda n, body: answer(body["model"])
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.calls.append(body)
                status, headers, payload = outer.behavior(len(outer.calls), body)
                streamed = isinstance(payload, str)  # server-sent events for stream=True
                data = (payload if streamed else json.dumps(payload)).encode("utf-8")
                self.send_response(status)
                for k, v in headers.items():
                    self.send_header(k, v)
                self.send_header("Content-Type", "text/event-stream" if streamed else "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/api/v1/chat/completions"

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class MockARCTestCase(unittest.TestCase):
    """Shared setup: temp project folder, mock ARC server, no real sleeping."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        shutil.copy(PROJECT / "scenarios.json", self.tmp / "scenarios.json")
        self.arc = MockARC()
        self.sleeps = []
        patches = [
            mock.patch.object(study0, "ROOT", self.tmp),
            mock.patch.object(study0, "API", self.arc.url),
            mock.patch.object(study0, "BACKOFF", (1, 2, 3)),
            mock.patch.object(study0.time, "sleep", self.sleeps.append),
            mock.patch.dict(os.environ, {"ARC_API_KEY": "test-key"}),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.arc.close)
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def out(self):
        return study0.formal_folder(study0.checked_trials())

    def run_quiet(self, **kw):
        with mock.patch("builtins.print"):
            study0.run(yes=True, **kw)

    def verify_quiet(self):
        return study0.verify(quiet=True)


class Study0Tests(MockARCTestCase):
    """plan, run and verify."""

    # --- planning -------------------------------------------------------

    def test_plan_is_1200_unique_and_order_is_round_by_round(self):
        jobs = study0.checked_trials()
        order = study0.run_order(jobs)
        self.assertEqual(len(order), 1200)
        self.assertEqual(len({j["trial_id"] for j in order}), 1200)
        self.assertEqual([j["repeat"] for j in order], sorted(j["repeat"] for j in order))
        self.assertEqual(order, study0.run_order(jobs))  # same seed, same order
        self.assertNotEqual(order[:120], [j for j in jobs if j["repeat"] == 1])  # shuffled

    def test_smoke_folder_hash_unchanged_by_refactor(self):
        # The real smoke folder for the current settings is b0db9a335181.
        with mock.patch.object(study0, "API", "https://llm-api.arc.vt.edu/api/v1/chat/completions"), \
             mock.patch.object(study0, "ROOT", PROJECT):
            jobs = [r for r in study0.trials() if r["scenario"] == 1 and r["repeat"] == 1]
            tag = study0.config_tag(dict(endpoint=study0.API, settings=study0.SETTINGS, jobs=jobs))
            formal = study0.formal_folder(study0.checked_trials()).name
        self.assertEqual(tag, "b0db9a335181")
        self.assertEqual(formal, "a2216350ebd7")  # the real formal run must keep resuming here

    # --- run ------------------------------------------------------------

    def test_limit_then_resume_makes_no_duplicate_calls(self):
        self.run_quiet(limit=12)
        self.assertEqual(len(self.arc.calls), 12)
        self.run_quiet(limit=12)
        self.assertEqual(len(self.arc.calls), 24)
        first_24 = study0.run_order(study0.checked_trials())[:24]
        for job in first_24:
            self.assertTrue((self.out() / f"{job['trial_id']}.json").exists())
        self.assertFalse((self.out() / ".lock").exists())

    def test_full_run_then_rerun_is_noop_and_verify_ok(self):
        self.run_quiet()
        self.assertEqual(len(self.arc.calls), 1200)
        self.run_quiet()
        self.assertEqual(len(self.arc.calls), 1200)
        ok, rows = self.verify_quiet()
        self.assertTrue(ok)
        self.assertEqual(sum(r["status"] == "success" for r in rows), 1200)
        self.assertTrue((self.out() / "trial_status.csv").exists())

    def test_retry_after_server_error_then_success(self):
        self.arc.behavior = lambda n, body: (500, {}, {"error": "boom"}) if n == 1 else answer(body["model"])
        self.run_quiet(limit=1)
        first = study0.run_order(study0.checked_trials())[0]["trial_id"]
        self.assertEqual(len(study0.failed_attempts(self.out(), first)), 1)
        self.assertTrue((self.out() / f"{first}.json").exists())
        self.assertEqual(self.sleeps, [1])

    def test_retry_after_header_is_honored(self):
        self.arc.behavior = lambda n, body: ((429, {"Retry-After": "7"}, {"error": "slow down"})
                                             if n == 1 else answer(body["model"]))
        self.run_quiet(limit=1)
        self.assertEqual(self.sleeps, [7.0])

    def test_truncated_answers_become_final_failure_and_are_not_retried_later(self):
        order = study0.run_order(study0.checked_trials())
        first = order[0]["trial_id"]
        self.arc.behavior = lambda n, body: answer(body["model"], finish="length") if n <= 3 \
            else answer(body["model"])
        self.run_quiet(limit=2)
        self.assertEqual(len(self.arc.calls), 4)  # 3 failures on trial 1, success on trial 2
        self.assertEqual(study0.trial_state(self.out(), first), "final_failure")
        self.assertEqual(self.sleeps, [1, 2])
        self.run_quiet(limit=1)  # resumes at trial 3, never trial 1
        self.assertEqual(len(self.arc.calls), 5)
        ok, rows = self.verify_quiet()
        self.assertTrue(ok)
        status = {r["trial_id"]: r["status"] for r in rows}
        self.assertEqual(status[first], "final_failure")

    def test_total_time_limit_abandons_a_hung_call_and_retries(self):
        def slow_first(n, body):
            if n == 1:
                threading.Event().wait(3)  # not time.sleep: that is patched in tests
            return answer(body["model"])
        self.arc.behavior = slow_first
        with mock.patch.object(study0, "TIMEOUT", 1):
            start = study0.time.monotonic()
            self.run_quiet(limit=1)
            took = study0.time.monotonic() - start
        first = study0.run_order(study0.checked_trials())[0]["trial_id"]
        failed = study0.failed_attempts(self.out(), first)
        self.assertEqual(len(failed), 1)
        record = json.loads(failed[0].read_text(encoding="utf-8"))
        # The socket timeout and the total limit are both 1 s here; either may fire first.
        self.assertTrue(record["error"].startswith("TimeoutError"), record["error"])
        self.assertLess(record["elapsed_s"], 2)
        self.assertTrue((self.out() / f"{first}.json").exists())
        self.assertLess(took, 3)

    def test_consecutive_failures_stop_the_run(self):
        self.arc.behavior = lambda n, body: (503, {}, {"error": "down"})
        with self.assertRaises(SystemExit):
            self.run_quiet()
        self.assertEqual(len(self.arc.calls), study0.MAX_CONSECUTIVE_FAILURES)
        self.assertFalse((self.out() / ".lock").exists())

    def test_auth_error_stops_immediately(self):
        self.arc.behavior = lambda n, body: (401, {}, {"error": "bad key"})
        with self.assertRaises(SystemExit):
            self.run_quiet()
        self.assertEqual(len(self.arc.calls), 1)

    def test_fingerprint_change_stops_but_keeps_response(self):
        fp = lambda n: "fp-A" if n < 3 else "fp-B"
        self.arc.behavior = lambda n, body: answer(body["model"], fp=fp(n))
        jobs = study0.checked_trials()
        order = study0.run_order(jobs)
        # make the first three trials the same model so the change is visible
        model = order[0]["model"]
        same = [j for j in order if j["model"] == model][:3]
        with mock.patch.object(study0, "run_order", lambda _jobs: same + [j for j in order if j not in same]):
            with self.assertRaises(SystemExit) as stop:
                self.run_quiet()
        self.assertIn("fingerprint changed", str(stop.exception))
        self.assertTrue((self.out() / f"{same[2]['trial_id']}.json").exists())
        self.assertEqual(len(self.arc.calls), 3)

    def test_returned_model_mismatch_stops(self):
        self.arc.behavior = lambda n, body: answer("some-other-model")
        with self.assertRaises(SystemExit) as stop:
            self.run_quiet()
        self.assertIn("Returned model", str(stop.exception))
        self.assertEqual(len(self.arc.calls), 1)

    def test_existing_lock_refuses_to_start(self):
        self.out().mkdir(parents=True)
        (self.out() / ".lock").write_text("other process")
        with self.assertRaises(SystemExit):
            self.run_quiet(limit=1)
        self.assertEqual(len(self.arc.calls), 0)

    # --- verify ---------------------------------------------------------

    def test_verify_flags_edited_record_and_unexpected_file(self):
        self.run_quiet(limit=3)
        first = study0.run_order(study0.checked_trials())[0]["trial_id"]
        path = self.out() / f"{first}.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        record["trial"]["prompt"] += " (edited)"
        path.write_text(json.dumps(record), encoding="utf-8")
        (self.out() / "notes.txt").write_text("stray file")
        ok, rows = self.verify_quiet()
        self.assertFalse(ok)
        row = next(r for r in rows if r["trial_id"] == first)
        self.assertEqual(row["status"], "invalid")
        self.assertIn("trial does not match plan", row["problems"])

    def test_verify_flags_stray_file_alone(self):
        self.run_quiet(limit=2)
        self.assertTrue(self.verify_quiet()[0])
        (self.out() / "S99-unknown-failed-abc.json").write_text("{}")
        self.assertFalse(self.verify_quiet()[0])

    def test_unicode_answers_survive_save_and_verify(self):
        text = "Alex’s “Sure” is non‑committal \U0001F642"
        self.arc.behavior = lambda n, body: answer(body["model"], content=text)
        self.run_quiet(limit=1)
        ok, rows = self.verify_quiet()
        self.assertTrue(ok)
        first = study0.run_order(study0.checked_trials())[0]["trial_id"]
        saved = json.loads((self.out() / f"{first}.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["response"]["choices"][0]["message"]["content"], text)


class CodingTests(MockARCTestCase):
    """Coding sample, blinded export and kappa. Reuses the mock-server setup."""

    def sample_rows(self):
        return study0.coding_sample(study0.checked_trials())

    # --- sample ---------------------------------------------------------

    def test_sample_shape_and_balance(self):
        rows = self.sample_rows()
        main = [r for r in rows if r["set"] == "main"]
        practice = [r for r in rows if r["set"] == "practice"]
        self.assertEqual(len(main), 150)
        self.assertEqual(len(practice), 20)
        self.assertEqual(len({r["item_id"] for r in rows}), 170)
        self.assertEqual(len({r["trial_id"] for r in rows}), 170)
        jobs = {j["trial_id"]: j for j in study0.checked_trials()}
        cell = lambda r: (jobs[r["trial_id"]]["model"], jobs[r["trial_id"]]["framing"])
        # 25 per model x framing; 20 from repeat 1 (one per scenario) + 5 from repeat 2
        for c, n in Counter(cell(r) for r in main).items():
            self.assertEqual(n, 25, c)
        self.assertEqual(Counter(jobs[r["trial_id"]]["repeat"] for r in main), {1: 120, 2: 30})
        # 50 per pair; each pair sees all six cells
        for pair in ("P1", "P2", "P3"):
            mine = [r for r in main if r["pair"] == pair]
            self.assertEqual(len(mine), 50)
            self.assertEqual(sorted(r["pair_rank"] for r in mine), list(range(1, 51)))
            self.assertEqual(len({cell(r) for r in mine}), 6)
        # the minimum (first 75 = 25 per pair) is balanced to within one per cell
        first = Counter(cell(r) for r in main if r["pair_rank"] <= study0.PAIR_MIN)
        self.assertLessEqual(max(first.values()) - min(first.values()), 1)
        # practice: repeat 4, one per scenario, disjoint from main
        self.assertEqual({jobs[r["trial_id"]]["repeat"] for r in practice}, {4})
        self.assertEqual(len({jobs[r["trial_id"]]["scenario"] for r in practice}), 20)
        # deterministic
        self.assertEqual(rows, self.sample_rows())

    def test_sample_refuses_to_change_frozen_plan(self):
        with mock.patch("builtins.print"):
            study0.sample()
            study0.sample()  # identical: fine
        path = self.tmp / "coding_plan.csv"
        path.write_text(path.read_text(encoding="utf-8").replace("P1", "P9", 1), encoding="utf-8")
        with mock.patch("builtins.print"), self.assertRaises(SystemExit):
            study0.sample()

    # --- export ---------------------------------------------------------

    def test_export_is_blinded_and_sized(self):
        self.run_quiet()
        with mock.patch("builtins.print"):
            sheets = study0.export()
        sizes = {p.name: len(s) for p, s in sheets.items()}
        self.assertEqual(sizes["R1_main.csv"], 100)
        self.assertEqual(sizes["R2_main.csv"], 100)
        self.assertEqual(sizes["R3_main.csv"], 100)
        self.assertEqual(sizes["R1_practice.csv"], 20)
        text = (self.tmp / "coding" / "R1_main.csv").read_text(encoding="utf-8-sig")
        for leak in ("gpt-oss", "DeepSeek", "neutral-R", "leading", "S01-"):
            self.assertNotIn(leak, text)
        self.assertNotIn("passive-aggressive in the last message", text)
        header = text.splitlines()[0]
        self.assertEqual(header, ",".join(study0.SHEET_COLUMNS))
        with mock.patch("builtins.print"), self.assertRaises(SystemExit):
            study0.export()  # never overwrite rater sheets

    def test_export_refuses_pending_unless_allowed(self):
        self.run_quiet(limit=10)
        with mock.patch("builtins.print"), self.assertRaises(SystemExit):
            study0.export()
        with mock.patch("builtins.print"):
            sheets = study0.export(allow_missing=True)
        self.assertLess(sum(len(s) for s in sheets.values()), 360)
        self.assertIn("Not available", (self.tmp / "coding" / "export_report.txt").read_text())

    # --- kappa ----------------------------------------------------------

    def test_cohen_kappa_textbook_example(self):
        # 50 items: both yes 20, A yes/B no 5, A no/B yes 10, both no 15 -> kappa 0.4
        a = ["yes"] * 20 + ["yes"] * 5 + ["no"] * 10 + ["no"] * 15
        b = ["yes"] * 20 + ["no"] * 5 + ["yes"] * 10 + ["no"] * 15
        self.assertAlmostEqual(study0.cohen_kappa(a, b), 0.4)
        self.assertAlmostEqual(study0.cohen_kappa(["x", "y"], ["x", "y"]), 1.0)
        self.assertTrue(study0.cohen_kappa(["x", "x"], ["x", "x"]) != study0.cohen_kappa(["x", "x"], ["x", "x"]))

    def fill(self, rater, fn, encoding="utf-8-sig"):
        path = self.tmp / "coding" / f"{rater}_main.csv"
        rows = study0.read_sheet(path)
        for i, row in enumerate(rows):
            row.update(fn(i, row) or {})
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=study0.SHEET_COLUMNS, lineterminator="\r\n")
        writer.writeheader()
        writer.writerows(rows)
        path.write_bytes(buffer.getvalue().encode(encoding, errors="replace"))

    def test_kappa_end_to_end_with_partial_and_excel_cp1252(self):
        self.run_quiet()
        with mock.patch("builtins.print"):
            study0.export()
        label = dict(main_reading="neutral", mentions_alternative="no",
                     certainty="confident", no_clear_preference="no")
        # R1 codes everything; R2 everything but disagrees on certainty for every 4th
        # item; R3 codes only its first 30 items and saves as cp1252 (Excel "CSV").
        self.fill("R1", lambda i, r: dict(label, main_reading="negative" if i % 2 else "neutral"))
        self.fill("R2", lambda i, r: dict(label, main_reading="negative" if i % 2 else "neutral",
                                          certainty="hedged" if i % 4 == 0 else "confident"))
        self.fill("R3", lambda i, r: dict(label) if i < 30 else None, encoding="cp1252")
        with mock.patch("builtins.print"):
            results = study0.kappa()
        k, agree, n = results[("R1+R2", "certainty")]
        self.assertEqual(n, 50)
        self.assertLess(agree, 1.0)
        report = (self.tmp / "coding" / "kappa_main.txt").read_text(encoding="utf-8")
        self.assertIn("R2+R3:", report)
        self.assertIn("Pooled", report)
        _, _, n_r2r3 = results[("R2+R3", "main_reading")]
        self.assertGreater(n_r2r3, 0)
        self.assertLessEqual(n_r2r3, 30)

    def test_invalid_and_uncodable_labels_are_reported_not_counted(self):
        self.run_quiet()
        with mock.patch("builtins.print"):
            study0.export()
        good = dict(main_reading="neutral", mentions_alternative="no",
                    certainty="confident", no_clear_preference="no")
        self.fill("R1", lambda i, r: dict(good, main_reading="Neg") if i == 0 else
                  (dict(notes="UNCODABLE: refused") if i == 1 else dict(good)))
        self.fill("R2", lambda i, r: dict(good))
        with mock.patch("builtins.print"):
            study0.kappa()
        report = (self.tmp / "coding" / "kappa_main.txt").read_text(encoding="utf-8")
        self.assertIn("1 uncodable, 1 invalid", report)
        self.assertIn("main_reading='neg'", report)

    def test_kappa_restores_excel_damaged_ids_only_in_original_order(self):
        self.run_quiet()
        with mock.patch("builtins.print"):
            study0.export()
        good = dict(main_reading="neutral", mentions_alternative="no",
                    certainty="confident", no_clear_preference="no")
        self.fill("R1", lambda i, r: dict(good, item_id="2.52E+08") if i == 0 else dict(good))
        self.fill("R2", lambda i, r: dict(good))
        with mock.patch("builtins.print"):
            results = study0.kappa()
        self.assertEqual(results[("R1+R2", "main_reading")][2], 50)  # the damaged row still counts
        report = (self.tmp / "coding" / "kappa_main.txt").read_text(encoding="utf-8")
        self.assertIn("1 Excel-damaged item IDs restored", report)
        # reordered rows: no guessing
        sheet = study0.read_sheet(self.tmp / "coding" / "R1_main.csv")
        expected = [r["item_id"] for r in sheet]
        swapped = [dict(r) for r in sheet]
        swapped[0], swapped[1] = swapped[1], swapped[0]
        self.assertEqual(study0.restore_ids(swapped, expected), 0)


def judge_reply(labels=None, uncodable=False, model=None, prefix=""):
    body = dict(reason="test", uncodable=uncodable, **(labels or dict(
        main_reading="negative", mentions_alternative="yes", certainty="hedged", no_clear_preference="no")))
    return answer(model or study0.JUDGE_RETURNED_MODEL, content=prefix + json.dumps(body))


def stream_reply(content, model=None, finish="stop", reasoning="Let me think. "):
    """A streamed reply: reasoning and content split into small chunks, then [DONE]."""
    model = model or study0.JUDGE_RETURNED_MODEL
    chunks = [dict(delta=dict(role="assistant"))]
    chunks += [dict(delta=dict(reasoning_content=reasoning[i:i + 5])) for i in range(0, len(reasoning), 5)]
    chunks += [dict(delta=dict(content=content[i:i + 7])) for i in range(0, len(content), 7)]
    chunks.append(dict(delta={}, finish_reason=finish))
    events = [f"data: {json.dumps(dict(id='mock', model=model, choices=[dict(index=0, **c)]))}\n\n"
              for c in chunks]
    return 200, {}, "".join(events) + ": keep-alive\n\ndata: [DONE]\n\n"


def judge_stream_reply(**kw):
    body = dict(reason="test", uncodable=False, main_reading="positive", mentions_alternative="no",
                certainty="confident", no_clear_preference="no")
    return stream_reply(json.dumps(body), **kw)


class JudgeTests(MockARCTestCase):
    """Model coder (E3): order, blinding, parsing, failures and the report."""

    fill = CodingTests.fill

    def judge_quiet(self, **kw):
        with mock.patch("builtins.print"):
            study0.judge(**kw)

    def test_parse_judge(self):
        labels, unc, _ = study0.parse_judge('Thinking {not json}\n```json\n{"reason": "r", "uncodable": false, '
                                            '"main_reading": "Neutral", "mentions_alternative": "no", '
                                            '"certainty": "hedged", "no_clear_preference": "no"}\n```')
        self.assertEqual(labels["main_reading"], "neutral")
        self.assertFalse(unc)
        self.assertEqual(study0.parse_judge('{"uncodable": true, "main_reading": null}')[:2], (None, True))
        with self.assertRaises(ValueError):
            study0.parse_judge('{"uncodable": false, "main_reading": "angry"}')
        with self.assertRaises(ValueError):
            study0.parse_judge("negative")

    def test_judge_codes_human_items_first_and_blind(self):
        self.run_quiet()
        self.arc.calls.clear()
        self.arc.behavior = lambda n, body: judge_reply()
        self.judge_quiet(limit=5)
        jobs = study0.checked_trials()
        out = study0.judge_folder(jobs)
        main = sorted((r for r in study0.coding_sample(jobs) if r["set"] == "main"),
                      key=lambda r: int(r["position"]))
        saved = sorted(p.stem for p in out.glob("S*.json"))
        self.assertEqual(saved, sorted(r["trial_id"] for r in main[:5]))
        for call in self.arc.calls:
            self.assertEqual(call["model"], study0.JUDGE_MODEL)
            self.assertEqual(call["temperature"], 0.0)
            prompt = call["messages"][0]["content"]
            for leak in ("gpt-oss", "DeepSeek", "Is Alex being", "What did Alex mean"):
                self.assertNotIn(leak, prompt)
            self.assertIn("Alex is fine with Jordan finishing tonight.", prompt)
        record = json.loads((out / f"{main[0]['trial_id']}.json").read_text(encoding="utf-8"))
        self.assertEqual(record["labels"]["main_reading"], "negative")

    def test_judge_bad_json_retries_then_final_failure_and_resumes(self):
        self.run_quiet()
        self.arc.behavior = lambda n, body: answer(study0.JUDGE_RETURNED_MODEL, content="I think it is negative.")
        self.judge_quiet(limit=1)
        out = study0.judge_folder(study0.checked_trials())
        self.assertEqual(len(list(out.glob("*-failed-*.json"))), 3)
        self.arc.behavior = lambda n, body: judge_reply()
        self.arc.calls.clear()
        self.judge_quiet(limit=1)  # skips the final failure, codes the next item
        self.assertEqual(len(self.arc.calls), 1)

    def test_judge_parallel_workers_code_everything_once(self):
        self.run_quiet()
        self.arc.calls.clear()
        self.arc.behavior = lambda n, body: (answer(study0.JUDGE_RETURNED_MODEL, content="oops")
                                             if n % 50 == 0 else judge_reply())
        self.judge_quiet(workers=4)
        out = study0.judge_folder(study0.checked_trials())
        self.assertEqual(len(list(out.glob("S*-R??.json"))), 1200)
        self.assertEqual(len(self.arc.calls), 1200 + len(list(out.glob("*-failed-*.json"))))
        self.arc.calls.clear()
        self.judge_quiet(workers=4)  # rerun is a no-op
        self.assertEqual(self.arc.calls, [])

    def test_assemble_stream(self):
        _, _, text = stream_reply("Hello world, this is the answer.", reasoning="Thinking hard.")
        reply = study0.assemble_stream(io.BytesIO(text.encode("utf-8")))
        self.assertEqual(reply["choices"][0]["message"]["content"], "Hello world, this is the answer.")
        self.assertEqual(reply["choices"][0]["message"]["reasoning_content"], "Thinking hard.")
        self.assertEqual(reply["choices"][0]["finish_reason"], "stop")
        self.assertEqual(reply["model"], study0.JUDGE_RETURNED_MODEL)
        with self.assertRaises(ValueError):
            study0.assemble_stream([b'data: {"error": {"message": "boom"}}'])

    def test_judge_retry_refuses_while_main_pass_unfinished(self):
        self.run_quiet()
        self.arc.behavior = lambda n, body: judge_reply()
        self.judge_quiet(limit=1)
        with mock.patch("builtins.print"), self.assertRaises(SystemExit):
            study0.judge(retry=True)

    def test_judge_retry_codes_only_final_failures_streamed(self):
        self.run_quiet()
        self.arc.calls.clear()
        # The first item fails all 3 main-pass attempts (token limit), everything else is coded.
        self.arc.behavior = lambda n, body: (answer(study0.JUDGE_RETURNED_MODEL, content='{"reason": "hm',
                                                    finish="length") if n <= 3 else judge_reply())
        self.judge_quiet()
        jobs = study0.checked_trials()
        failed = study0.judge_order(jobs)[0]
        self.assertEqual(study0.trial_state(study0.judge_folder(jobs), failed), "final_failure")
        main_prompt = self.arc.calls[0]["messages"][0]["content"]
        self.arc.calls.clear()
        # Retry: one streamed length failure, then a streamed success.
        self.arc.behavior = lambda n, body: (judge_stream_reply(finish="length") if n == 1
                                             else judge_stream_reply())
        self.judge_quiet(retry=True)
        self.assertEqual(len(self.arc.calls), 2)
        for call in self.arc.calls:
            self.assertTrue(call["stream"])
            self.assertEqual(call["max_tokens"], study0.RETRY_SETTINGS["max_tokens"])
            self.assertEqual(call["temperature"], 0.0)
            self.assertEqual(call["messages"][0]["content"], main_prompt)
        retry_out = study0.judge_retry_folder(jobs)
        record = json.loads((retry_out / f"{failed}.json").read_text(encoding="utf-8"))
        self.assertEqual(record["labels"]["main_reading"], "positive")
        self.assertEqual(record["response"]["choices"][0]["message"]["reasoning_content"], "Let me think. ")
        self.assertFalse((study0.judge_folder(jobs) / f"{failed}.json").exists())  # main pass untouched
        self.arc.calls.clear()
        self.judge_quiet(retry=True)  # rerun is a no-op
        self.assertEqual(self.arc.calls, [])
        with mock.patch("builtins.print"):
            _, table = study0.judge_report()
        self.assertEqual(sum(r["n_from_retry"] for r in table), 1)
        self.assertEqual(sum(r["n_not_coded"] for r in table), 0)
        with open(study0.judge_folder(jobs) / "judge_labels.csv", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual([r["trial_id"] for r in rows if r["judge_pass"] == "retry"], [failed])

    def test_judge_model_mismatch_stops(self):
        self.run_quiet()
        self.arc.behavior = lambda n, body: judge_reply(model="other-model")
        with mock.patch("builtins.print"), self.assertRaises(SystemExit):
            study0.judge(limit=1)

    def test_judge_report_agreement_and_table(self):
        self.run_quiet()
        with mock.patch("builtins.print"):
            study0.export()
        good = dict(main_reading="negative", mentions_alternative="yes",
                    certainty="hedged", no_clear_preference="no")
        self.fill("R1", lambda i, r: dict(good) if i < 50 else None)
        self.fill("R2", lambda i, r: dict(good, certainty="confident") if i % 2 else dict(good))
        self.arc.calls.clear()
        self.arc.behavior = lambda n, body: (judge_reply(uncodable=True, labels=dict(
            main_reading=None, mentions_alternative=None, certainty=None, no_clear_preference=None))
            if n == 3 else judge_reply())
        self.judge_quiet()
        with mock.patch("builtins.print"):
            results, table = study0.judge_report()
        k, agree, n = results[("main", "main_reading")]["judge_human"]
        self.assertEqual(agree, 1.0)
        self.assertEqual(n, 149)  # 50 (R1) + 100 (R2) minus the one item the judge called uncodable
        self.assertEqual(len(table), 6)
        self.assertEqual(sum(r["n_coded"] for r in table) + sum(r["n_uncodable"] for r in table), 1200)
        self.assertTrue((self.tmp / "results" / "judge_table.csv").exists())
        self.assertTrue((study0.judge_folder(study0.checked_trials()) / "judge_labels.csv").exists())


if __name__ == "__main__":
    unittest.main()
