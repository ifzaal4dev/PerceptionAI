"""Offline tests for study0.py against a local mock of the ARC API. No real API calls.

Run from the project folder:  py -m unittest discover -s tests -v
"""
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
                data = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                for k, v in headers.items():
                    self.send_header(k, v)
                self.send_header("Content-Type", "application/json")
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


class Study0Tests(unittest.TestCase):
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
        self.assertEqual(tag, "b0db9a335181")

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


if __name__ == "__main__":
    unittest.main()
