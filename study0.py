"""Study 0 runner for the VT ARC API: plan, smoke, run and verify.

plan    Write planned_trials.csv (1,200 trials). No network calls.
smoke   Six setup calls (scenario 1, repeat 1). Stops on the first failure.
run     The formal 1,200-call run. Resumable, with bounded retries.
verify  Check every saved record against the plan and print denominators.

Rules for `run` follow decisions.md section 4 (D4.1-D4.8).
"""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
from getpass import getpass
import hashlib
import http.client
import io
import json
import os
from pathlib import Path
import random
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parent
API = "https://llm-api.arc.vt.edu/api/v1/chat/completions"
MODELS = ("gpt-oss-120b", "DeepSeek-V4.1-Flash")
QUESTIONS = {
    "neutral": "What did {sender} mean by the last message?",
    "negatively_leading": "Is {sender} being passive-aggressive in the last message?",
    "positively_leading": "Is {sender} being sincere in the last message?",
}
# Proposed smoke-test settings. Review and freeze before the research run.
# max_tokens raised from 2048 on Nov 10: one gpt-oss smoke answer used 1,497 tokens
# (decisions.md D2.4). Changing SETTINGS changes the smoke_runs hash folder.
SETTINGS = dict(temperature=0.7, top_p=1.0, max_tokens=4096, stream=False)
REPEATS = 10
EXPECTED_TRIALS = len(MODELS) * len(QUESTIONS) * REPEATS * 20

# Formal-run rules (decisions.md section 4). Changing SEED changes the run folder.
SEED = 20261112                # D4.1: shuffle seed within each repeat round
MAX_ATTEMPTS = 3               # D4.3: attempts per trial before a final failure
BACKOFF = (10, 30, 90)         # D4.3: seconds to wait after attempt 1, 2, 3
MAX_CONSECUTIVE_FAILURES = 10  # D4.6: stop the run after this many failures in a row
TIMEOUT = 180                  # D2.5: seconds per request

NETWORK_ERRORS = (HTTPError, URLError, OSError, http.client.HTTPException,
                  ValueError, IndexError, KeyError, TypeError)
BOOKKEEPING = {"run_meta.json", "fingerprints.json", "trial_status.csv", ".lock"}


# ---------------------------------------------------------------- planning

def trials():
    scenarios = json.loads((ROOT / "scenarios.json").read_text(encoding="utf-8"))
    for scenario in scenarios:
        for model in MODELS:
            for framing, template in QUESTIONS.items():
                question = template.format(sender=scenario["sender"])
                prompt = scenario["conversation"] + "\n\n" + question
                for repeat in range(1, REPEATS + 1):
                    yield {
                        "trial_id": f"S{scenario['id']:02}-{model}-{framing}-R{repeat:02}",
                        "scenario": scenario["id"], "model": model, "framing": framing,
                        "repeat": repeat, "prompt": prompt,
                    }


def checked_trials():
    rows = list(trials())
    if len(rows) != EXPECTED_TRIALS or len({r["trial_id"] for r in rows}) != EXPECTED_TRIALS:
        raise ValueError(f"Expected {EXPECTED_TRIALS:,} unique trial IDs. Check inputs.")
    return rows


def plan():
    rows = checked_trials()
    with (ROOT / "planned_trials.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print("1,200 planned trials. No API calls made. See planned_trials.csv.")
    print("\nFirst prompt:\n" + rows[0]["prompt"])


def run_order(jobs):
    """D4.1: rounds by repeat number; within a round, a fixed-seed shuffle."""
    rng = random.Random(SEED)
    order = []
    for repeat in range(1, REPEATS + 1):
        round_jobs = [j for j in jobs if j["repeat"] == repeat]
        rng.shuffle(round_jobs)
        order.extend(round_jobs)
    return order


def config_tag(config):
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:12]


def formal_config(jobs):
    return dict(purpose="formal run", endpoint=API, settings=SETTINGS, seed=SEED, jobs=jobs)


def formal_folder(jobs):
    return ROOT / "runs" / config_tag(formal_config(jobs))


# ---------------------------------------------------------------- requests

def utc_now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, obj):
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def request_body(job):
    return dict(model=job["model"], messages=[dict(role="user", content=job["prompt"])], **SETTINGS)


def get_key():
    key = os.getenv("ARC_API_KEY") or getpass("Your personal ARC API key (hidden): ").strip()
    if not key:
        raise SystemExit("Enter a personal ARC API key and try again.")
    return key


def request_once(job, key, purpose, extra=None):
    """Make one call. Returns (ok, record, error). Never raises for network or reply errors."""
    body = request_body(job)
    request = Request(API, data=json.dumps(body).encode(), headers={
        "Authorization": "Bearer " + key, "Content-Type": "application/json",
    })
    record = dict(purpose=purpose, trial=job, request=body, endpoint=API,
                  started_utc=utc_now(), **(extra or {}))
    raw = None
    start = time.monotonic()
    try:
        with urlopen(request, timeout=TIMEOUT) as reply:
            raw = reply.read().decode("utf-8")
        record["response"] = json.loads(raw)
        choice = record["response"]["choices"][0]
        answer = choice["message"]["content"]
        if not isinstance(answer, str) or not answer.strip() or choice.get("finish_reason") != "stop":
            raise ValueError(f"Incomplete model answer (finish_reason={choice.get('finish_reason')!r}).")
        record["elapsed_s"] = round(time.monotonic() - start, 3)
        return True, record, None
    except NETWORK_ERRORS as exc:
        record["elapsed_s"] = round(time.monotonic() - start, 3)
        record["error"] = f"{type(exc).__name__}: {exc}"
        if raw is not None and "response" not in record:
            record["raw_body"] = raw
        if isinstance(exc, HTTPError):
            record["http_status"] = exc.code
            record["retry_after"] = exc.headers.get("Retry-After") if exc.headers else None
            try:
                record["server_body"] = exc.read().decode("utf-8", errors="replace")
            except Exception:  # the error body is optional evidence
                record["server_body"] = None
        return False, record, exc


def failed_path(out, trial_id):
    return out / f"{trial_id}-failed-{uuid4().hex}.json"


def failed_attempts(out, trial_id):
    return sorted(out.glob(f"{trial_id}-failed-*.json"))


# ---------------------------------------------------------------- smoke

def smoke():
    key = get_key()
    jobs = [r for r in trials() if r["scenario"] == 1 and r["repeat"] == 1]
    config = dict(endpoint=API, settings=SETTINGS, jobs=jobs)
    out = ROOT / "smoke_runs" / config_tag(config)
    out.mkdir(parents=True, exist_ok=True)
    for job in jobs:
        path = out / (job["trial_id"] + ".json")
        if path.exists():
            print("Already saved:", job["trial_id"])
            continue
        ok, record, exc = request_once(job, key, "setup test")
        if not ok:
            failed = failed_path(out, job["trial_id"])
            write_json(failed, record)
            raise SystemExit(f"Stopped: {exc}. Inspect {failed.name}, then rerun smoke.")
        write_json(path, record)
        print("Saved:", job["trial_id"])
    print(f"Six setup records ready in {out}")


# ---------------------------------------------------------------- run

def retry_wait(record, attempts_so_far):
    value = record.get("retry_after")
    if value is not None:
        try:
            return max(0.0, float(value))
        except ValueError:
            pass  # an HTTP-date Retry-After falls back to the fixed backoff
    return BACKOFF[min(attempts_so_far, len(BACKOFF)) - 1]


def acquire_lock(out):
    lock = out / ".lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise SystemExit(f"{lock} exists: another run may be active in this folder. "
                         "If you are sure none is running, delete .lock and try again.") from None
    os.write(fd, f"pid {os.getpid()} since {utc_now()}\n".encode())
    os.close(fd)
    return lock


def trial_state(out, trial_id):
    if (out / f"{trial_id}.json").exists():
        return "success"
    return "final_failure" if len(failed_attempts(out, trial_id)) >= MAX_ATTEMPTS else "pending"


def run(key=None, yes=False, limit=None):
    jobs = checked_trials()
    order = run_order(jobs)
    out = formal_folder(jobs)
    out.mkdir(parents=True, exist_ok=True)
    meta_path = out / "run_meta.json"
    if not meta_path.exists():
        write_json(meta_path, dict(
            purpose="formal run", created_utc=utc_now(), endpoint=API, settings=SETTINGS,
            seed=SEED, max_attempts=MAX_ATTEMPTS, backoff=BACKOFF, timeout=TIMEOUT,
            max_consecutive_failures=MAX_CONSECUTIVE_FAILURES, python=sys.version,
            trials=len(jobs), order=[j["trial_id"] for j in order]))

    states = Counter(trial_state(out, j["trial_id"]) for j in order)
    todo = [j for j in order if trial_state(out, j["trial_id"]) == "pending"]
    if limit is not None:
        todo = todo[:limit]
    print(f"Run folder: {out}")
    print(f"Settings: {SETTINGS} | seed {SEED} | up to {MAX_ATTEMPTS} attempts per trial")
    print(f"Already saved {states['success']}, final failures {states['final_failure']}, "
          f"pending {states['pending']}. This session will attempt {len(todo)}.")
    if not todo:
        print("Nothing to do. Run `verify` next.")
        return
    if not yes:
        answer = input("Only start once decisions.md section 2-4 are frozen. Type RUN to start: ")
        if answer.strip() != "RUN":
            raise SystemExit("Not started.")
    key = key or get_key()

    fp_path = out / "fingerprints.json"
    fingerprints = json.loads(fp_path.read_text(encoding="utf-8")) if fp_path.exists() else {}
    done = states["success"]
    consecutive = 0
    lock = acquire_lock(out)
    try:
        for job in todo:
            trial_id = job["trial_id"]
            attempts = len(failed_attempts(out, trial_id))
            while attempts < MAX_ATTEMPTS:
                extra = dict(order_index=order.index(job) + 1, attempt=attempts + 1)
                ok, record, exc = request_once(job, key, "formal run", extra)
                returned = (record.get("response") or {}).get("model") if ok else None
                if ok and returned != job["model"]:
                    record["error"] = f"Returned model {returned!r} != requested {job['model']!r}"
                    write_json(failed_path(out, trial_id), record)
                    raise SystemExit(f"Stopped: {record['error']} (D4.7). Consult the PI before resuming.")
                if ok:
                    write_json(out / f"{trial_id}.json", record)
                    consecutive = 0
                    done += 1
                    print(f"[{done}/{len(jobs)}] Saved {trial_id} ({record['elapsed_s']:.1f}s)")
                    fp = record["response"].get("system_fingerprint")
                    if job["model"] not in fingerprints:
                        fingerprints[job["model"]] = fp
                        write_json(fp_path, fingerprints)
                    elif fingerprints[job["model"]] != fp:
                        raise SystemExit(
                            f"Stopped: {job['model']} fingerprint changed from "
                            f"{fingerprints[job['model']]!r} to {fp!r} at {trial_id} (D4.7). "
                            "The response was saved. Consult the PI before resuming.")
                    break
                write_json(failed_path(out, trial_id), record)
                attempts += 1
                consecutive += 1
                print(f"Attempt {attempts}/{MAX_ATTEMPTS} failed for {trial_id}: {record['error']}")
                if record.get("http_status") in (401, 403):
                    raise SystemExit("Stopped: the server rejected the key (401/403). Check it and rerun.")
                if consecutive >= MAX_CONSECUTIVE_FAILURES:
                    raise SystemExit(f"Stopped after {consecutive} failures in a row (D4.6). "
                                     "Inspect the -failed- files, then rerun to resume.")
                if attempts < MAX_ATTEMPTS:
                    time.sleep(retry_wait(record, attempts))
                else:
                    print(f"Final failure: {trial_id} (reported in verify, never replaced).")
    except KeyboardInterrupt:
        raise SystemExit("Interrupted. Saved records are safe; rerun to resume.") from None
    finally:
        lock.unlink(missing_ok=True)
    print("Session finished. Run `py study0.py verify` next.")


# ---------------------------------------------------------------- verify

def check_record(path, job):
    """Return (problems, details) for one saved success record."""
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"unreadable: {exc}"], {}
    problems = []
    if record.get("trial") != job:
        problems.append("trial does not match plan")
    if record.get("request") != request_body(job):
        problems.append("request does not match plan or settings")
    response = record.get("response") or {}
    details = dict(returned_model=response.get("model"),
                   system_fingerprint=response.get("system_fingerprint"),
                   started_utc=record.get("started_utc"))
    try:
        choice = response["choices"][0]
        content = choice["message"]["content"]
        details["finish_reason"] = choice.get("finish_reason")
        details["content_words"] = len(content.split()) if isinstance(content, str) else 0
        if choice.get("finish_reason") != "stop":
            problems.append(f"finish_reason {choice.get('finish_reason')!r}")
        if not isinstance(content, str) or not content.strip():
            problems.append("empty answer")
    except (KeyError, IndexError, TypeError):
        problems.append("no answer in response")
    details["completion_tokens"] = (response.get("usage") or {}).get("completion_tokens")
    if details["returned_model"] != job["model"]:
        problems.append(f"returned model {details['returned_model']!r}")
    return problems, details


def verify(folder=None, quiet=False):
    """Check a formal run folder. Returns (ok, rows); writes trial_status.csv."""
    jobs = checked_trials()
    out = Path(folder) if folder else formal_folder(jobs)
    if not out.is_dir():
        raise SystemExit(f"No run folder at {out}. Start the run first.")
    say = (lambda *a: None) if quiet else print
    planned = {j["trial_id"]: j for j in jobs}
    rows = []
    for trial_id, job in planned.items():
        failures = failed_attempts(out, trial_id)
        success = out / f"{trial_id}.json"
        row = dict(trial_id=trial_id, scenario=job["scenario"], model=job["model"],
                   framing=job["framing"], repeat=job["repeat"],
                   failed_attempts=len(failures), status="", problems="",
                   returned_model="", system_fingerprint="", finish_reason="",
                   completion_tokens="", content_words="", started_utc="")
        if success.exists():
            problems, details = check_record(success, job)
            row.update({k: v for k, v in details.items() if v is not None})
            row["status"] = "invalid" if problems else "success"
            row["problems"] = "; ".join(problems)
        elif len(failures) >= MAX_ATTEMPTS:
            row["status"] = "final_failure"
        else:
            row["status"] = "pending"
        rows.append(row)

    expected_names = set(BOOKKEEPING) | {f"{t}.json" for t in planned}

    def is_expected(name):
        if name in expected_names or (name.startswith(".") and name.endswith(".tmp")):
            return True
        trial_id, marker, _ = name.partition("-failed-")
        return bool(marker) and trial_id in planned and name.endswith(".json")

    unexpected = sorted(p.name for p in out.iterdir() if not is_expected(p.name))

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    temporary = out / f".trial_status.csv.{uuid4().hex}.tmp"
    temporary.write_text(buffer.getvalue(), encoding="utf-8")
    temporary.replace(out / "trial_status.csv")

    cells = defaultdict(Counter)
    for r in rows:
        cells[(r["model"], r["framing"])][r["status"]] += 1
    say(f"Run folder: {out}")
    say(f"{'model':<22}{'framing':<22}{'planned':>8}{'success':>9}{'final_fail':>11}"
        f"{'pending':>9}{'invalid':>9}")
    for (model, framing), c in sorted(cells.items()):
        say(f"{model:<22}{framing:<22}{sum(c.values()):>8}{c['success']:>9}"
            f"{c['final_failure']:>11}{c['pending']:>9}{c['invalid']:>9}")
    totals = Counter(r["status"] for r in rows)
    say(f"Total: {dict(totals)}")
    good = [r for r in rows if r["status"] == "success"]
    for model in MODELS:
        mine = [r for r in good if r["model"] == model]
        if mine:
            tokens = [r["completion_tokens"] for r in mine if isinstance(r["completion_tokens"], int)]
            fps = Counter(r["system_fingerprint"] or None for r in mine)
            say(f"{model}: fingerprints {dict(fps)}; max completion tokens "
                f"{max(tokens) if tokens else 'n/a'} of {SETTINGS['max_tokens']}")
    if good:
        stamps = sorted(r["started_utc"] for r in good if r["started_utc"])
        say(f"Successful calls from {stamps[0]} to {stamps[-1]}")
    for r in rows:
        if r["status"] == "invalid":
            say(f"INVALID {r['trial_id']}: {r['problems']}")
    for name in unexpected:
        say(f"UNEXPECTED FILE {name}")
    ok = totals["invalid"] == 0 and not unexpected
    say("Verify: OK" if ok else "Verify: PROBLEMS FOUND (see above)")
    say(f"Per-trial status written to {out / 'trial_status.csv'}")
    return ok, rows


# ---------------------------------------------------------------- main

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["plan", "smoke", "run", "verify"])
    parser.add_argument("--yes", action="store_true", help="run: skip the RUN confirmation")
    parser.add_argument("--limit", type=int, help="run: attempt at most this many pending trials")
    parser.add_argument("--folder", help="verify: a run folder other than the current config's")
    args = parser.parse_args(argv)
    if args.command == "plan":
        plan()
    elif args.command == "smoke":
        smoke()
    elif args.command == "run":
        run(yes=args.yes, limit=args.limit)
    else:
        ok, _ = verify(args.folder)
        if not ok:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
