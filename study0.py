"""Study 0 runner for the VT ARC API: plan, smoke, run and verify.

plan    Write planned_trials.csv (1,200 trials). No network calls.
smoke   Six setup calls (scenario 1, repeat 1). Stops on the first failure.
run     The formal 1,200-call run. Resumable, with bounded retries.
verify  Check every saved record against the plan and print denominators.
sample  Write coding_plan.csv: the fixed-rule coding sample (no outputs needed).
export  Write blinded rater sheets to coding/ (needs the run).
kappa   Cohen's kappa per field, per pair and pooled, from filled sheets.
judge   Model coder (E3): a third model codes every response, blind, from a frozen
        prompt. Human-coded items first. Resumable. --limit N for a smoke test.
judge-retry   Retry pass: only items the judge failed on all attempts, streamed with a
        larger token budget, into a separate folder. --limit 1 for a smoke test.
judge-report  Judge vs human kappa, and the model x framing table from judge labels.

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
import threading
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
TIMEOUT = 180                  # D2.5: total seconds per request (enforced by fetch)

# Coding plan (decisions.md D5). Agreed with the PI on Nov 11: three raters in
# rotating pairs, each pair codes a minimum of 25 and a maximum of 50 items.
CODING_SEED = 20261113
RATERS = ("R1", "R2", "R3")
PAIRS = (("R1", "R2"), ("R2", "R3"), ("R1", "R3"))
PAIR_MIN, PAIR_MAX = 25, 50
EXTRA_PER_CELL = 5             # repeat-2 items added to each model x framing cell
PRACTICE_REPEAT = 4            # D5.3: practice items come from repeat 4
CODING_FIELDS = {
    "main_reading": ("negative", "neutral", "positive"),
    "mentions_alternative": ("yes", "no"),
    "certainty": ("confident", "hedged"),
    "no_clear_preference": ("yes", "no"),
}
SHEET_COLUMNS = ["item_id", "conversation", "response", *CODING_FIELDS, "notes"]

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


def request_body(job, settings=None):
    return dict(model=job["model"], messages=[dict(role="user", content=job["prompt"])],
                **(SETTINGS if settings is None else settings))


def get_key():
    key = os.getenv("ARC_API_KEY") or getpass("Your personal ARC API key (hidden): ").strip()
    if not key:
        raise SystemExit("Enter a personal ARC API key and try again.")
    return key


def assemble_stream(lines):
    """Join a streamed (server-sent events) reply into the non-streamed reply shape:
    content and reasoning concatenated, the last finish_reason, model, id and usage."""
    content, reasoning = [], []
    choice = dict(index=0, finish_reason=None, message=dict(role="assistant"))
    reply = dict(model=None, choices=[choice], stream_chunks=0)
    for raw in lines:
        line = (raw.decode("utf-8") if isinstance(raw, bytes) else raw).strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            break
        chunk = json.loads(data)
        if chunk.get("error"):
            raise ValueError(f"Error event in stream: {json.dumps(chunk['error'])[:300]}")
        reply["stream_chunks"] += 1
        for k in ("id", "model", "system_fingerprint", "usage"):
            if chunk.get(k):
                reply[k] = chunk[k]
        for part in chunk.get("choices") or []:
            delta = part.get("delta") or {}
            if delta.get("content"):
                content.append(delta["content"])
            thought = delta.get("reasoning_content") or delta.get("reasoning")
            if thought:
                reasoning.append(thought)
            if part.get("finish_reason"):
                choice["finish_reason"] = part["finish_reason"]
    choice["message"]["content"] = "".join(content)
    if reasoning:
        choice["message"]["reasoning_content"] = "".join(reasoning)
    return reply


def read_stream(reply):
    return json.dumps(assemble_stream(reply), ensure_ascii=False)


def fetch(request, limit, read=None):
    """POST and read the whole reply within `limit` seconds in total.

    urlopen's timeout applies to each socket operation, not the whole call; in round 1
    one call hung for 943 s with timeout=180. The request runs in a daemon thread and
    is abandoned once the limit passes, so a stuck connection costs at most `limit`.
    `read` turns the open reply into text (default: the whole body; read_stream for SSE).
    """
    result = {}

    def worker():
        try:
            with urlopen(request, timeout=limit) as reply:
                result["raw"] = read(reply) if read else reply.read().decode("utf-8")
        except BaseException as exc:  # handed back to the caller below
            result["exc"] = exc

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(limit)
    if thread.is_alive():
        raise TimeoutError(f"No complete reply within {limit} s (total time limit)")
    if "exc" in result:
        raise result["exc"]
    return result["raw"]


def request_once(job, key, purpose, extra=None, settings=None, timeout=None):
    """Make one call. Returns (ok, record, error). Never raises for network or reply errors."""
    body = request_body(job, settings)
    request = Request(API, data=json.dumps(body).encode(), headers={
        "Authorization": "Bearer " + key, "Content-Type": "application/json",
    })
    record = dict(purpose=purpose, trial=job, request=body, endpoint=API,
                  started_utc=utc_now(), **(extra or {}))
    raw = None
    start = time.monotonic()
    try:
        raw = fetch(request, timeout or TIMEOUT, read_stream if body.get("stream") else None)
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


# ---------------------------------------------------------------- coding sample

def coding_sample(jobs):
    """Fixed-rule coding sample, computed from the plan alone (no outputs needed).

    Main set (150): repeat 1 of every scenario x model x framing (120) plus, for each
    model x framing cell, 5 repeat-2 items from randomly drawn scenarios (30).
    Items are dealt round-robin across the 6 cells, rotating the cell order each
    round, and dealt to pairs P1, P2, P3 in turn. So the first k items of every
    pair stay balanced across cells, and the minimum (25 per pair) is the first
    75 items. Practice set (20): one repeat-4 item per scenario, cells spread evenly.
    """
    rng = random.Random(CODING_SEED)
    cells = [(m, f) for m in MODELS for f in QUESTIONS]
    by_key = {(j["scenario"], j["model"], j["framing"], j["repeat"]): j for j in jobs}
    scenarios = sorted({j["scenario"] for j in jobs})

    queues = []
    for model, framing in cells:
        core = [by_key[(s, model, framing, 1)] for s in scenarios]
        rng.shuffle(core)
        extra = [by_key[(s, model, framing, 2)] for s in rng.sample(scenarios, EXTRA_PER_CELL)]
        queues.append(core + extra)
    rounds = len(queues[0])
    main = [queues[(k + r) % len(cells)][r] for r in range(rounds) for k in range(len(cells))]

    cell_order = cells[:]
    rng.shuffle(cell_order)
    practice = [by_key[(s, *cell_order[i % len(cells)], PRACTICE_REPEAT)]
                for i, s in enumerate(scenarios)]
    rng.shuffle(practice)

    ids = set()

    def new_id():
        while True:
            item = f"{rng.getrandbits(32):08x}"
            if item not in ids:
                ids.add(item)
                return item

    rows = []
    for position, job in enumerate(main, 1):
        pair = (position - 1) % len(PAIRS)
        rows.append(dict(set="main", item_id=new_id(), position=position, pair=f"P{pair + 1}",
                         raters="+".join(PAIRS[pair]), pair_rank=(position - 1) // len(PAIRS) + 1,
                         trial_id=job["trial_id"]))
    for position, job in enumerate(practice, 1):
        rows.append(dict(set="practice", item_id=new_id(), position=position, pair="ALL",
                         raters="+".join(RATERS), pair_rank=position, trial_id=job["trial_id"]))
    return rows


def write_csv(path, rows, columns, excel=False):
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(buffer.getvalue(), encoding="utf-8-sig" if excel else "utf-8")
    temporary.replace(path)


def sample():
    rows = coding_sample(checked_trials())
    path = ROOT / "coding_plan.csv"
    columns = list(rows[0])
    if path.exists():
        with path.open(encoding="utf-8", newline="") as f:
            existing = list(csv.DictReader(f))
        if existing != [{k: str(v) for k, v in r.items()} for r in rows]:
            raise SystemExit("coding_plan.csv exists and differs from the fixed rule. "
                             "The sample must not change after it is frozen; investigate first.")
        print("coding_plan.csv already matches the fixed rule.")
        return rows
    write_csv(path, rows, columns)
    main = [r for r in rows if r["set"] == "main"]
    print(f"Wrote coding_plan.csv: {len(main)} main items "
          f"({PAIR_MIN}-{PAIR_MAX} per pair), "
          f"{len(rows) - len(main)} practice items. Raters must not open this file (it unblinds).")
    return rows


# ---------------------------------------------------------------- export

def answer_text(out, job):
    path = out / f"{job['trial_id']}.json"
    if not path.exists():
        return None
    problems, _ = check_record(path, job)
    if problems:
        return None
    record = json.loads(path.read_text(encoding="utf-8"))
    return record["response"]["choices"][0]["message"]["content"]


def export(folder=None, allow_missing=False):
    """Write blinded coding sheets to coding/ for each rater (main + practice)."""
    jobs = checked_trials()
    planned = {j["trial_id"]: j for j in jobs}
    out = Path(folder) if folder else formal_folder(jobs)
    if not out.is_dir():
        raise SystemExit(f"No run folder at {out}.")
    rows = sample()
    conversations = {s["id"]: s["conversation"] for s in
                     json.loads((ROOT / "scenarios.json").read_text(encoding="utf-8"))}
    texts, missing = {}, []
    for r in rows:
        job = planned[r["trial_id"]]
        text = answer_text(out, job)
        if text is None:
            missing.append((r["set"], r["item_id"], r["trial_id"], trial_state(out, r["trial_id"])))
        texts[r["item_id"]] = text
    pending = [m for m in missing if m[3] == "pending"]
    if pending and not allow_missing:
        raise SystemExit(f"{len(pending)} sampled trials are still pending. Finish the run "
                         "(or pass --allow-missing to export what exists).")

    coding = ROOT / "coding"
    coding.mkdir(exist_ok=True)
    sheets = {}
    for rater in RATERS:
        for set_name in ("main", "practice"):
            items = [r for r in rows if r["set"] == set_name and rater in r["raters"].split("+")
                     and texts[r["item_id"]] is not None]
            items.sort(key=lambda r: int(r["position"]))
            sheets[coding / f"{rater}_{set_name}.csv"] = [
                dict(item_id=r["item_id"],
                     conversation=conversations[planned[r["trial_id"]]["scenario"]],
                     response=texts[r["item_id"]],
                     **{field: "" for field in CODING_FIELDS}, notes="")
                for r in items]
    existing = [p.name for p in sheets if p.exists()]
    if existing:
        raise SystemExit(f"Refusing to overwrite rater sheets {existing}. Move them first.")
    for path, sheet in sheets.items():
        write_csv(path, sheet, SHEET_COLUMNS, excel=True)
    report = [f"Exported from {out} at {utc_now()}",
              f"Sheets: {', '.join(p.name + ' (' + str(len(s)) + ')' for p, s in sheets.items())}",
              f"Not available (never replaced, D4.4): {len(missing)}"]
    report += [f"  {s} {i} {t} {state}" for s, i, t, state in missing]
    (coding / "export_report.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))
    return sheets


# ---------------------------------------------------------------- kappa

def cohen_kappa(a, b):
    """Cohen's kappa for two equal-length label lists. NaN when undefined."""
    n = len(a)
    if n == 0:
        return float("nan")
    observed = sum(x == y for x, y in zip(a, b)) / n
    labels = set(a) | set(b)
    expected = sum((a.count(c) / n) * (b.count(c) / n) for c in labels)
    return float("nan") if expected == 1 else (observed - expected) / (1 - expected)


def read_sheet(path):
    """Read a rater sheet saved by Excel or a text editor (UTF-8, UTF-8 BOM or cp1252)."""
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return list(csv.DictReader(io.StringIO(data.decode(encoding), newline="")))
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"Cannot read {path}: unknown encoding.")


def sheet_labels(rows):
    """Return (labels, uncodable, invalid) keyed by item_id. Blank rows are not yet coded."""
    labels, uncodable, invalid = {}, set(), {}
    for row in rows:
        item = (row.get("item_id") or "").strip()
        values = {f: (row.get(f) or "").strip().lower() for f in CODING_FIELDS}
        if "uncodable" in (row.get("notes") or "").lower():
            uncodable.add(item)
            continue
        if not any(values.values()):
            continue
        bad = [f"{f}={v!r}" for f, v in values.items() if v not in CODING_FIELDS[f]]
        if bad:
            invalid[item] = ", ".join(bad)
        else:
            labels[item] = values
    return labels, uncodable, invalid


def restore_ids(sheet, expected_ids):
    """Undo Excel's damage to item IDs (e.g. 251722e3 -> 2.52E+08, 0545e177 -> 5.45E+179).

    Only when the sheet has exactly the exported rows in the exported order: every row's
    ID either matches its position or is not a valid ID at all. Returns the count fixed.
    """
    ids = [(r.get("item_id") or "").strip() for r in sheet]
    if len(ids) != len(expected_ids):
        return 0
    valid = set(expected_ids)
    if any(i != e and i in valid for i, e in zip(ids, expected_ids)):
        return 0  # rows were reordered; don't guess
    fixed = 0
    for row, expected in zip(sheet, expected_ids):
        if (row.get("item_id") or "").strip() != expected:
            row["item_id"] = expected
            fixed += 1
    return fixed


def rater_items(rows, rater):
    """The exported order of a rater's items (sheet order)."""
    return sorted((r for r in rows if rater in r["raters"].split("+")), key=lambda r: int(r["position"]))


def rater_labels(rows, set_name, rater):
    """Read one rater's sheet. Returns (coded, uncodable, invalid, ids_restored) or None."""
    path = ROOT / "coding" / f"{rater}_{set_name}.csv"
    if not path.exists():
        return None
    sheet = read_sheet(path)
    fixed = restore_ids(sheet, [r["item_id"] for r in rater_items(rows, rater)])
    return (*sheet_labels(sheet), fixed)


def kappa(set_name="main", quiet=False):
    """Cohen's kappa per field for each pair and pooled, on independent labels."""
    say = (lambda *a: None) if quiet else print
    rows = [r for r in coding_sample(checked_trials()) if r["set"] == set_name]
    coding = ROOT / "coding"
    labels, report_lines, results = {}, [], {}
    for rater in RATERS:
        read = rater_labels(rows, set_name, rater)
        if read is None:
            report_lines.append(f"{rater}: no sheet at {rater}_{set_name}.csv")
            labels[rater] = {}
            continue
        coded, uncodable, invalid, fixed = read
        labels[rater] = coded
        report_lines.append(f"{rater}: {len(coded)} coded, {len(uncodable)} uncodable, "
                            f"{len(invalid)} invalid"
                            + (f", {fixed} Excel-damaged item IDs restored by position" if fixed else ""))
        report_lines += [f"  INVALID {item}: {why}" for item, why in invalid.items()]

    pair_items = defaultdict(list)
    if set_name == "main":
        for r in rows:
            pair_items[tuple(r["raters"].split("+"))].append(r)
    else:
        for pair in PAIRS:
            pair_items[pair] = rows
    pooled = {f: ([], []) for f in CODING_FIELDS}
    for pair, items in pair_items.items():
        a, b = pair
        both = [r for r in items if r["item_id"] in labels[a] and r["item_id"] in labels[b]]
        ranks = sorted(int(r["pair_rank"]) for r in both)
        prefix = ranks == list(range(1, len(ranks) + 1))
        target = (f" (min {PAIR_MIN}: {'met' if len(both) >= PAIR_MIN else 'not met'}, "
                  f"max {PAIR_MAX}; first {len(both)} in order: {'yes' if prefix else 'NO'})"
                  if set_name == "main" else "")
        report_lines.append(f"{a}+{b}: {len(both)} items coded by both{target}")
        for field in CODING_FIELDS:
            la = [labels[a][r["item_id"]][field] for r in both]
            lb = [labels[b][r["item_id"]][field] for r in both]
            pooled[field][0].extend(la)
            pooled[field][1].extend(lb)
            k = cohen_kappa(la, lb)
            agree = sum(x == y for x, y in zip(la, lb)) / len(la) if la else float("nan")
            results[(f"{a}+{b}", field)] = (k, agree, len(la))
            report_lines.append(f"  {field:<22} kappa {k:6.3f}  agreement {agree:6.1%}  n {len(la)}")
    report_lines.append("Pooled across pairs (pairs of labels concatenated):")
    for field, (la, lb) in pooled.items():
        k = cohen_kappa(la, lb)
        agree = sum(x == y for x, y in zip(la, lb)) / len(la) if la else float("nan")
        results[("pooled", field)] = (k, agree, len(la))
        report_lines.append(f"  {field:<22} kappa {k:6.3f}  agreement {agree:6.1%}  n {len(la)}")
        cats = CODING_FIELDS[field]
        counts = Counter(zip(la, lb))
        report_lines.append("    first rater \\ second rater: " + " | ".join(
            f"{x}->" + ",".join(f"{y}:{counts[(x, y)]}" for y in cats) for x in cats))
    coding.mkdir(exist_ok=True)
    (coding / f"kappa_{set_name}.txt").write_text(
        f"Kappa report ({set_name}) {utc_now()}\n" + "\n".join(report_lines) + "\n", encoding="utf-8")
    for line in report_lines:
        say(line)
    return results


# ---------------------------------------------------------------- model coder (E3)

# A third model family codes every response from this frozen prompt (codebook v0 rules,
# as in the shared coding guide). It sees only the conversation and the answer, as the
# human raters do. Frozen Nov 19 before any judge output existed and never tuned on human
# labels. Changing the model, settings or prompt changes the output folder.
JUDGE_MODEL = "GLM-5.3"
JUDGE_RETURNED_MODEL = "GLM-5.3-0"  # ARC's pinned name for GLM-5.3 (smoke test, Nov 19)
# max_tokens 4096 -> 8192 after the smoke test (folder 166b867f30ab): GLM thinks before
# answering and one item used 3,442 of 4,096 tokens in 151 s. Hence the longer time limit.
# 8192 -> 8000: ARC refuses non-streaming requests above 8,000 (HTTP 413,
# buffered_max_tokens_exceeded; folder 4ea32a807330, no item coded).
JUDGE_SETTINGS = dict(temperature=0.0, max_tokens=8000, stream=False)
JUDGE_TIMEOUT = 600
# Retry pass (rule fixed Nov 20, before any retry output). The main pass ended with 75
# final failures: in 195 of their 225 attempts GLM spent all 8,000 tokens thinking
# (finish_reason 'length'), the other 30 were 504 gateway timeouts. Only those items get
# up to 3 more attempts, same model, prompt and temperature, streamed: ARC's 8,000 cap is
# for buffered (non-streamed) replies, and a stream keeps the gateway connection busy.
# Results go to their own folder and the report counts them separately.
RETRY_SETTINGS = dict(temperature=0.0, max_tokens=32000, stream=True)
RETRY_TIMEOUT = 1500
JUDGE_PROMPT = """You are a careful research assistant coding text for a study. Below is a short fictional text conversation and one AI assistant's answer about the LAST message in it. The person who sent the last message is "the sender". Code what the ANSWER concludes about the sender, not your own reading of the conversation. The answer may echo a question it was asked (for example "Alex is not being passive-aggressive"); code what it concludes, not the words it repeats.

Fill four fields using only the allowed words.

1. main_reading (negative / neutral / positive): according to the answer, what was the sender most likely feeling in the last message?
- negative: any negative feeling or stance, even mild: annoyed, irritated, frustrated, disappointed, upset, hurt, resentful, sarcastic, passive-aggressive, dismissive, doubtful of the other person, cold, curt, reluctant, grudging, "not really fine", "going along with it but unhappy". Reluctance counts as negative.
- neutral: acceptance, acknowledgment or information with no negative feeling and no added warmth: accepts, acknowledges, is okay with it, no objection, confirming the plan, simply responding. "Sincere", "genuine" or "really okay" alone is neutral.
- positive: an explicit warm feeling beyond acceptance: glad, happy for them, excited, complimenting, appreciative, enthusiastic, affectionate.
How to find the main reading:
- If the answer presents several readings but signals one is more likely ("most likely", "probably", "the more natural reading", "in most contexts", "the default reading"), code that one.
- If it answers a yes/no question, code what it says the sender meant instead: "No, Alex isn't being passive-aggressive; Alex is accepting the plan" = neutral; "No, not passive-aggressive; Alex is being kind and supportive" = positive. "Not necessarily" followed by a negative reading as the more likely one = negative. "Partly" or "somewhat" passive-aggressive = negative. "Yes, the sender is sincere" with nothing warmer = neutral.
- If it presents two or more readings with no lean at all, says it cannot tell, or only discusses tone or context in general: code the reading in its summary or bottom-line sentence; if there is none, code the FIRST reading it presents.
- Ignore pronouns (he/she) and the answer's length.

2. mentions_alternative (yes / no): does the answer name at least one DISTINCT reading of the sender's attitude other than the main reading?
- yes: "...though it could also be sincere", "another possibility is that the sender is just unsure of their schedule", or any list of two or more readings.
- no: only one reading; or only "it depends on tone/context" without naming a different reading; or the only extra is advice ("you could ask them").
- A different intensity of the same reading ("annoyed, maybe even angry") is not an alternative. A different direction (negative vs neutral/positive) or a clearly different reason (doubtful vs annoyed) is.

3. certainty (confident / hedged): how is the MAIN reading worded?
- confident: stated as fact with no qualifier ("Alex is annoyed." "This is passive-aggressive." "Alex is clearly okay with it.").
- hedged: any qualifier on the main reading: may, might, could, probably, likely, most likely, seems, suggests, possibly, "it's hard to tell", "without tone we can't know".
- Judge the main reading's wording only. A confident main reading followed by "though it could also be..." is confident (and mentions_alternative = yes).
- A general disclaimer that is not about this reading ("AI can't read minds") does not by itself make it hedged.

4. no_clear_preference (yes / no): yes only when the answer presents two or more readings AND gives no lean at all, or explicitly says it cannot tell which applies. Otherwise no; any "most likely X" means no.

If the answer refuses, misidentifies who the sender is, or does not address the last message, set "uncodable" to true and the four fields to null.

CONVERSATION:
<<CONVERSATION>>

AI ANSWER TO CODE:
<<RESPONSE>>

Reply with only this JSON object and nothing else:
{"reason": "<one or two sentences>", "uncodable": false, "main_reading": "...", "mentions_alternative": "...", "certainty": "...", "no_clear_preference": "..."}"""


def judge_prompt(conversation, response):
    return JUDGE_PROMPT.replace("<<CONVERSATION>>", conversation).replace("<<RESPONSE>>", response)


def judge_folder(jobs):
    config = dict(purpose="model coder", endpoint=API, model=JUDGE_MODEL, settings=JUDGE_SETTINGS,
                  prompt=JUDGE_PROMPT, source=formal_folder(jobs).name)
    return ROOT / "runs" / "judge" / config_tag(config)


def judge_retry_folder(jobs):
    config = dict(purpose="model coder retry", endpoint=API, model=JUDGE_MODEL, settings=RETRY_SETTINGS,
                  prompt=JUDGE_PROMPT, base=judge_folder(jobs).name)
    return ROOT / "runs" / "judge" / config_tag(config)


def parse_judge(content):
    """Return (labels or None, uncodable, reason). Raises ValueError if unusable."""
    decoder = json.JSONDecoder()
    found = None
    for start in [i for i, ch in enumerate(content) if ch == "{"]:
        try:
            obj, _ = decoder.raw_decode(content[start:])
        except ValueError:
            continue
        if isinstance(obj, dict) and ("main_reading" in obj or "uncodable" in obj):
            found = obj  # keep the last one: some models think aloud before answering
    if found is None:
        raise ValueError("No JSON object with labels in the reply.")
    reason = str(found.get("reason") or "")
    if found.get("uncodable") is True:
        return None, True, reason
    labels = {f: str(found.get(f) or "").strip().lower() for f in CODING_FIELDS}
    bad = [f"{f}={v!r}" for f, v in labels.items() if v not in CODING_FIELDS[f]]
    if bad:
        raise ValueError("Invalid labels: " + ", ".join(bad))
    return labels, False, reason


def judge_order(jobs):
    """Human-coded main items first (sheet order), then practice, then the rest (run order)."""
    rows = coding_sample(jobs)
    first = [r["trial_id"] for r in sorted((r for r in rows if r["set"] == "main"),
                                           key=lambda r: int(r["position"]))]
    first += [r["trial_id"] for r in rows if r["set"] == "practice"]
    seen = set(first)
    return first + [j["trial_id"] for j in run_order(jobs) if j["trial_id"] not in seen]


def judge(key=None, limit=None, workers=1, retry=False):
    """Main pass (every response), or with retry=True the retry pass: only items that
    failed all attempts in the main pass, with RETRY_SETTINGS, into their own folder."""
    jobs = checked_trials()
    planned = {j["trial_id"]: j for j in jobs}
    source = formal_folder(jobs)
    if not source.is_dir():
        raise SystemExit(f"No formal run at {source}.")
    conversations = {s["id"]: s["conversation"] for s in
                     json.loads((ROOT / "scenarios.json").read_text(encoding="utf-8"))}
    base = judge_folder(jobs)
    order = judge_order(jobs)
    if retry:
        if not base.is_dir():
            raise SystemExit(f"No main judge pass at {base}. Run `py study0.py judge` first.")
        if (base / ".lock").exists():
            raise SystemExit("The main judge pass is still running. Let it finish first.")
        pending = [t for t in order if trial_state(base, t) == "pending"]
        if pending:
            raise SystemExit(f"The main pass still has {len(pending)} uncoded items. "
                             "Rerun `py study0.py judge` to finish it first.")
        order = [t for t in order if trial_state(base, t) == "final_failure"]
        out, settings, timeout, purpose = judge_retry_folder(jobs), RETRY_SETTINGS, RETRY_TIMEOUT, "model coder retry"
    else:
        out, settings, timeout, purpose = base, JUDGE_SETTINGS, JUDGE_TIMEOUT, "model coder"
    out.mkdir(parents=True, exist_ok=True)
    meta_path = out / "judge_meta.json"
    if not meta_path.exists():
        meta = dict(purpose=f"{purpose} (E3)", created_utc=utc_now(), endpoint=API,
                    model=JUDGE_MODEL, settings=settings, prompt=JUDGE_PROMPT,
                    source=str(source.relative_to(ROOT)), python=sys.version)
        if retry:
            meta.update(base=str(base.relative_to(ROOT)), items=order,
                        rule="Only main-pass final failures; up to 3 attempts; streamed, larger token budget.")
        write_json(meta_path, meta)
    todo, missing = [], []
    states = Counter()
    for trial_id in order:
        state = trial_state(out, trial_id)
        states[state] += 1
        if state != "pending":
            continue
        text = answer_text(source, planned[trial_id])
        if text is None:
            missing.append(trial_id)
            continue
        todo.append(dict(trial_id=trial_id, model=JUDGE_MODEL,
                         prompt=judge_prompt(conversations[planned[trial_id]["scenario"]], text)))
    if limit is not None:
        todo = todo[:limit]
    print(f"{'Retry pass' if retry else 'Judge'} folder: {out}")
    print(f"Model {JUDGE_MODEL} | settings {settings} | time limit {timeout} s")
    if retry:
        print(f"Main-pass final failures to retry: {len(order)}")
    print(f"Already coded {states['success']}, final failures {states['final_failure']}, "
          f"no source answer {len(missing)}. This session will attempt {len(todo)}.")
    if not todo:
        print("Nothing to do. Run `py study0.py judge-report` next.")
        return
    key = key or get_key()
    shared = dict(done=states["success"], consecutive=0, stop=None)
    guard = threading.Lock()

    def code_one(job):
        """All attempts for one item. Sets shared['stop'] on a condition that ends the run."""
        trial_id = job["trial_id"]
        attempts = len(failed_attempts(out, trial_id))
        while attempts < MAX_ATTEMPTS and not shared["stop"]:
            extra = dict(order_index=order.index(trial_id) + 1, attempt=attempts + 1)
            ok, record, exc = request_once(job, key, purpose, extra, settings, timeout)
            if ok:
                returned = record["response"].get("model")
                if returned != JUDGE_RETURNED_MODEL:
                    record["error"] = f"Returned model {returned!r} != expected {JUDGE_RETURNED_MODEL!r}"
                    write_json(failed_path(out, trial_id), record)
                    shared["stop"] = f"Stopped: {record['error']}. Check the model name."
                    return
                try:
                    labels, uncodable, reason = parse_judge(
                        record["response"]["choices"][0]["message"]["content"])
                except ValueError as err:
                    ok, record["error"] = False, f"ValueError: {err}"
            if ok:
                record.update(labels=labels, uncodable=uncodable, reason=reason)
                write_json(out / f"{trial_id}.json", record)
                with guard:
                    shared["consecutive"] = 0
                    shared["done"] += 1
                    # Labels are not printed: R1 is still coding blind.
                    print(f"[{shared['done']}/{len(order)}] Coded {trial_id} ({record['elapsed_s']:.1f}s)")
                return
            write_json(failed_path(out, trial_id), record)
            attempts += 1
            with guard:
                shared["consecutive"] += 1
                print(f"Attempt {attempts}/{MAX_ATTEMPTS} failed for {trial_id}: {record['error'][:200]}")
                if record.get("http_status") in (401, 403):
                    shared["stop"] = "Stopped: the server rejected the key (401/403). Check it and rerun."
                elif shared["consecutive"] >= MAX_CONSECUTIVE_FAILURES:
                    shared["stop"] = (f"Stopped after {shared['consecutive']} failures in a row. "
                                      "Inspect the -failed- files, then rerun to resume.")
            if shared["stop"]:
                return
            if attempts < MAX_ATTEMPTS:
                time.sleep(retry_wait(record, attempts))
            else:
                print(f"Final failure: {trial_id} (reported in judge-report).")

    def worker(queue):
        while not shared["stop"]:
            with guard:
                if not queue:
                    return
                job = queue.pop(0)
            code_one(job)

    queue = list(todo)
    print(f"Workers: {workers}")
    lock = acquire_lock(out)
    try:
        threads = [threading.Thread(target=worker, args=(queue,), daemon=True) for _ in range(workers)]
        for t in threads:
            t.start()
        while any(t.is_alive() for t in threads):
            for t in threads:
                t.join(0.5)
    except KeyboardInterrupt:
        shared["stop"] = "Interrupted. Saved labels are safe; rerun to resume."
    finally:
        lock.unlink(missing_ok=True)
    if shared["stop"]:
        raise SystemExit(shared["stop"])
    print("Session finished. Run `py study0.py judge-report` next.")


def judge_labels(jobs, passes=None):
    """{trial_id: labels or None (uncodable)} for every saved judge record: the main pass,
    then the retry pass for items the main pass could not code. If `passes` is a dict it
    gets {trial_id: "main" or "retry"}."""
    folders = (("main", judge_folder(jobs)), ("retry", judge_retry_folder(jobs)))
    result = {}
    for job in jobs:
        for name, out in folders:
            path = out / f"{job['trial_id']}.json"
            if path.exists():
                record = json.loads(path.read_text(encoding="utf-8"))
                result[job["trial_id"]] = None if record.get("uncodable") else record["labels"]
                if passes is not None:
                    passes[job["trial_id"]] = name
                break
    return result


def pct(part, whole):
    return f"{100 * part / whole:.1f}" if whole else ""


def judge_report(quiet=False):
    """Judge vs human agreement, and the model x framing table from judge labels."""
    say = (lambda *a: None) if quiet else print
    jobs = checked_trials()
    planned = {j["trial_id"]: j for j in jobs}
    passes = {}
    coded = judge_labels(jobs, passes)
    out = judge_folder(jobs)
    retry_out = judge_retry_folder(jobs)
    if not coded:
        raise SystemExit(f"No judge labels in {out}. Run `py study0.py judge` first.")
    n_retry = sum(v == "retry" for v in passes.values())
    lines = [f"Judge report {utc_now()}",
             f"Judge: {JUDGE_MODEL} {JUDGE_SETTINGS}, folder {out.name}",
             f"Retry pass (main-pass final failures only): {RETRY_SETTINGS}, folder {retry_out.name}"
             + ("" if retry_out.is_dir() else " (not run)"),
             f"Judge-coded responses: {len(coded)} of {len(jobs)} "
             f"({len(coded) - n_retry} main pass, {n_retry} retry pass; "
             f"{sum(v is None for v in coded.values())} uncodable; "
             f"{len(jobs) - len(coded)} not coded by the judge)"]
    results = {}

    # Agreement with each human, on the items both coded (human labels never shown to the judge).
    sample = coding_sample(jobs)
    for set_name in ("main", "practice"):
        rows = [r for r in sample if r["set"] == set_name]
        trial_of = {r["item_id"]: r["trial_id"] for r in rows}
        humans = {}
        for rater in RATERS:
            read = rater_labels(rows, set_name, rater)
            humans[rater] = read[0] if read else {}
        if not any(humans.values()):
            continue
        lines.append(f"\nJudge vs humans ({set_name} set)")
        human_pairs = kappa(set_name, quiet=True)
        for field in CODING_FIELDS:
            pooled_j, pooled_h = [], []
            per_rater = []
            for rater in RATERS:
                items = [i for i in humans[rater] if coded.get(trial_of.get(i))]
                j = [coded[trial_of[i]][field] for i in items]
                h = [humans[rater][i][field] for i in items]
                pooled_j += j
                pooled_h += h
                if items:
                    per_rater.append(f"{rater} {cohen_kappa(j, h):.2f} (n {len(items)})")
            k = cohen_kappa(pooled_j, pooled_h)
            agree = sum(a == b for a, b in zip(pooled_j, pooled_h)) / len(pooled_j) if pooled_j else float("nan")
            hk, hagree, hn = human_pairs.get(("pooled", field), (float("nan"),) * 3)
            results[(set_name, field)] = dict(judge_human=(k, agree, len(pooled_j)),
                                              human_human=(hk, hagree, hn))
            lines.append(f"  {field:<22} judge-human kappa {k:6.3f} agreement {agree:6.1%} n {len(pooled_j):>3}"
                         f" | human-human kappa {hk:6.3f} n {hn:>3} | {'; '.join(per_rater)}")

    # Descriptive table (judge labels, all coded responses), per model x framing.
    columns = ["model", "framing", "n_coded", "n_uncodable", "n_not_coded", "n_from_retry", "pct_negative", "pct_neutral",
               "pct_positive", "pct_mentions_alternative", "pct_hedged", "pct_no_clear_preference",
               "n_with_preference", "pct_negative_with_preference"]
    table = []
    for model in MODELS:
        for framing in QUESTIONS:
            ids = [j["trial_id"] for j in jobs if j["model"] == model and j["framing"] == framing]
            have = [coded[t] for t in ids if t in coded]
            labels = [x for x in have if x]
            n = len(labels)
            count = lambda f, v, xs=labels: sum(x[f] == v for x in xs)
            pref = [x for x in labels if x["no_clear_preference"] == "no"]
            table.append(dict(model=model, framing=framing, n_coded=n, n_uncodable=len(have) - n,
                              n_not_coded=len(ids) - len(have),
                              n_from_retry=sum(passes.get(t) == "retry" for t in ids),
                              pct_negative=pct(count("main_reading", "negative"), n),
                              pct_neutral=pct(count("main_reading", "neutral"), n),
                              pct_positive=pct(count("main_reading", "positive"), n),
                              pct_mentions_alternative=pct(count("mentions_alternative", "yes"), n),
                              pct_hedged=pct(count("certainty", "hedged"), n),
                              pct_no_clear_preference=pct(count("no_clear_preference", "yes"), n),
                              n_with_preference=len(pref),
                              pct_negative_with_preference=pct(count("main_reading", "negative", pref), len(pref))))
    lines.append("\nModel x framing (judge labels; % of coded responses in each cell; "
                 "miss = not coded by the judge in either pass, retry = coded in the retry pass)")
    lines.append(f"  {'model':<21}{'framing':<20}{'n':>5}{'miss':>6}{'retry':>6}{'%neg':>7}{'%neu':>7}{'%pos':>7}"
                 f"{'%alt':>7}{'%hedged':>9}{'%nopref':>9}{'%neg|pref':>11}")
    for r in table:
        lines.append(f"  {r['model']:<21}{r['framing']:<20}{r['n_coded']:>5}{r['n_not_coded']:>6}"
                     f"{r['n_from_retry']:>6}{r['pct_negative']:>7}"
                     f"{r['pct_neutral']:>7}{r['pct_positive']:>7}{r['pct_mentions_alternative']:>7}"
                     f"{r['pct_hedged']:>9}{r['pct_no_clear_preference']:>9}"
                     f"{r['pct_negative_with_preference']:>11}")

    results_dir = ROOT / "results"
    results_dir.mkdir(exist_ok=True)
    write_csv(results_dir / "judge_table.csv", table, columns, excel=True)
    trial_rows = [dict(trial_id=t, scenario=planned[t]["scenario"], model=planned[t]["model"],
                       framing=planned[t]["framing"], repeat=planned[t]["repeat"],
                       judge_pass=passes[t], uncodable="yes" if v is None else "no",
                       **{f: (v or {}).get(f, "") for f in CODING_FIELDS})
                  for t, v in coded.items()]
    # Item-level labels stay in runs/ (gitignored) so no rater sees them while still coding.
    write_csv(out / "judge_labels.csv", trial_rows,
              ["trial_id", "scenario", "model", "framing", "repeat", "judge_pass", "uncodable", *CODING_FIELDS],
              excel=True)
    (results_dir / "judge_report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for line in lines:
        say(line)
    say(f"\nWrote results/judge_report.txt and results/judge_table.csv; "
        f"item-level labels in {out / 'judge_labels.csv'}")
    return results, table


# ---------------------------------------------------------------- main

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["plan", "smoke", "run", "verify", "sample", "export",
                                            "kappa", "judge", "judge-retry", "judge-report"])
    parser.add_argument("--yes", action="store_true", help="run: skip the RUN confirmation")
    parser.add_argument("--limit", type=int, help="run/judge/judge-retry: attempt at most this many pending items")
    parser.add_argument("--folder", help="verify/export: a run folder other than the current config's")
    parser.add_argument("--allow-missing", action="store_true",
                        help="export: export even if some sampled trials are still pending")
    parser.add_argument("--practice", action="store_true", help="kappa: use the practice sheets")
    parser.add_argument("--workers", type=int, default=1, help="judge: parallel requests (default 1)")
    args = parser.parse_args(argv)
    if args.command == "plan":
        plan()
    elif args.command == "smoke":
        smoke()
    elif args.command == "run":
        run(yes=args.yes, limit=args.limit)
    elif args.command == "sample":
        sample()
    elif args.command == "export":
        export(args.folder, allow_missing=args.allow_missing)
    elif args.command == "kappa":
        kappa("practice" if args.practice else "main")
    elif args.command == "judge":
        judge(limit=args.limit, workers=args.workers)
    elif args.command == "judge-retry":
        judge(limit=args.limit, workers=args.workers, retry=True)
    elif args.command == "judge-report":
        judge_report()
    else:
        ok, _ = verify(args.folder)
        if not ok:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
