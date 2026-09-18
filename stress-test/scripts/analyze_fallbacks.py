"""analyze_fallbacks.py — quantify LLM failures & fallback triggers in the 4-persona sim.

Sources:
  1. sim/shim.log            — every HTTP request the repo's LangGraph made to the LLM seam
                               (134 TOOL_OK structured, 7 plain-text, N ERROR = HTTP 500
                               after 3 internal SDK 429s).
  2. sim/<p>/transcript.md   — exact-match templated fallback strings (each exact match is
                               direct evidence the corresponding plain-text/structured call
                               failed hard and the node's deterministic fallback fired).
  3. sim/<p>/data/**.json    — persisted judge verdicts ("Un-scored — judge error") and DSA
                               attempt feedback ("I couldn't score that...").

Model of the repo seam (config.py):
  call_structured  = 2 shim requests max (1 manual retry). hard fail => BOTH fail.
  plain-text nodes = 1 shim request (clarify/greet/progress/farewell/comm_wrap).
  E = R + 2S + P   (E=ERROR lines; R=structured recovered-on-retry; S=structured hard fail;
                    P=plain-text fail). Fallbacks fired = S + P.
"""
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from statistics import median

SIM = Path("/home/z/my-project/sim")
PERSONAS = ["rude", "chaotic", "weird", "normal"]

# ---------- exact fallback markers (from repo source, code-verified) ----------
MARKERS = {
    # plain-text failures (P bucket) — node templates, fired only when the LLM call failed
    "clarify_fail": "Just so I point you right — did you want to practice DSA, "
                    "communication, or your core subject, or see your progress?",
    "greet_fail*": "Here's where you stand:",
    "farewell_fail*": "See you tomorrow for another round!",
    # structured hard failures (S bucket)
    "dsa_evaluator_fail": "I couldn't score that — explain it differently.",
    "dsa_selector_fail": "Solve it for the general case and state any assumptions you need.",
    "core_examiner_fail": "Question: explain ",
    "comm_interviewer_fail*": "Describe a deadline you nearly missed — what happened, "
                              "and what did you change after?",
    "comm_all_judge_fail": "Honest snag on my side: I couldn't score any",
    "comm_wrap_fail": "Biggest pattern from your verdicts:",
    "progress_fail": "Honest read: Pick the weakest one",  # template has trend-prefix; match tail
    # disk-write fallbacks (NOT LLM) — for contrast
    "disk_save_fail": "hit a snag on my side",
}
SOFT = {"greet_fail*", "farewell_fail*", "comm_interviewer_fail*"}  # LLM could phrase alike

# ---------- 1. shim.log ----------
req_re = re.compile(r"^\[shim\] (\S+) tools=(TOOL_OK|TOOL_MISS|-) (\d+)ms len=(\d+)$")
err_re = re.compile(r"^\[shim\] ERROR (\d+)ms (.*)$")
succ, errs, listening = [], [], 0
for line in (SIM / "shim.log").read_text(errors="replace").splitlines():
    m = req_re.match(line)
    if m:
        succ.append({"ts": m.group(1), "kind": m.group(2),
                     "ms": int(m.group(3)), "len": int(m.group(4))})
        continue
    m = err_re.match(line)
    if m:
        # NOTE: ERROR lines carry only a duration, no timestamp. We reconstruct an
        # approximate completion time by bracketing between the surrounding SUCCESS
        # lines' timestamps (the log is completion-ordered, single shared server).
        errs.append({"idx": len(succ) + len(errs), "ms": int(m.group(1)),
                     "msg": m.group(2)})
        continue
    if "listening" in line:
        listening += 1

# true merge: walk the raw log keeping sequence, then bracket each error between
# the previous and next success completion timestamps
def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))

seq = []
for line in (SIM / "shim.log").read_text(errors="replace").splitlines():
    m = req_re.match(line)
    if m:
        seq.append(("s", m.group(1)))
        continue
    if err_re.match(line):
        seq.append(("e", None))
next_success = [None] * len(seq)
ns = None
for i in range(len(seq) - 1, -1, -1):
    if seq[i][0] == "s":
        ns = ts(seq[i][1])
    next_success[i] = ns
ls = None
err_est = []
for i, (kind, val) in enumerate(seq):
    if kind == "s":
        ls = ts(val)
    else:
        a, b = ls, next_success[i]
        est = a if b is None else (b if a is None else a + (b - a) / 2)
        err_est.append(est)
for e, est in zip(errs, err_est):
    e["ts_est"] = est.isoformat() if est else None

tools_split = Counter(s["kind"] for s in succ)
lat = sorted(s["ms"] for s in succ)
err_lat = sorted(e["ms"] for e in errs)
err_msgs = Counter(e["msg"] for e in errs)

def pctl(xs, q):
    return xs[min(len(xs) - 1, int(len(xs) * q))] if xs else 0

# storm timeline per minute (success exact, error approx-bracketed)
timeline = {}
for x in succ:
    timeline.setdefault(x["ts"][:16], [0, 0])[0] += 1
for e in errs:
    if e.get("ts_est"):
        timeline.setdefault(e["ts_est"][:16], [0, 0])[1] += 1
storm_minutes = sorted(timeline.items())

# pairing heuristic on RECONSTRUCTED timestamps: two consecutive errors <=3s apart
# are likely attempt1+attempt2 of the same call_structured
def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))

err_ts = [ts(e["ts_est"]) for e in errs if e.get("ts_est")]
gaps = [(err_ts[i + 1] - err_ts[i]).total_seconds() for i in range(len(err_ts) - 1)]
gap_hist = Counter()
for g in gaps:
    if g <= 3:
        gap_hist["<=3s (likely attempt1+attempt2 of one call_structured)"] += 1
    elif g <= 10:
        gap_hist["4-10s (adjacent failing requests)"] += 1
    else:
        gap_hist[">10s (separate events)"] += 1
paired_s = sum(1 for g in gaps if g <= 3)

# success right after an error (<=2.5s reconstructed) => retry recovered
recover_est = 0
s_ts = sorted(ts(s["ts"]) for s in succ)
import bisect
for et in err_ts:
    k = bisect.bisect_right(s_ts, et)
    if k < len(s_ts) and (s_ts[k] - et).total_seconds() <= 2.5:
        recover_est += 1

E = len(errs)

# ---------- 2. transcripts ----------
transcript_stats = {}
for p in PERSONAS:
    t = (SIM / p / "transcript.md").read_text(encoding="utf-8")
    turns = len(re.findall(r"^## Turn ", t, re.M))
    intents = re.findall(r"<!-- intent=(\S+?) session_active=(\S+?) -->", t)
    intent_c = Counter(i for i, _ in intents)
    markers = {k: t.count(v) for k, v in MARKERS.items()}
    transcript_stats[p] = {
        "turns": turns,
        "intent_counts": dict(intent_c),
        "markers": markers,
        "crashes": t.count("[GRAPH CRASH"),
    }

# ---------- 3. data files ----------
data_stats = {}
for p in PERSONAS:
    d = SIM / p / "data"
    out = {"unscored_judge_error": 0, "dsa_couldnt_score_attempts": 0,
           "records": [], "attempts": []}
    for h in sorted((d / "history").glob("*.json")):
        rec = json.loads(h.read_text(encoding="utf-8"))
        out["records"].append(h.name)
        for q in rec.get("q_and_a", []) or []:
            if "Un-scored" in str(q.get("verdict", "")):
                out["unscored_judge_error"] += 1
        for a in rec.get("attempts", []) or []:
            if "couldn't score" in str(a.get("feedback", "")):
                out["dsa_couldnt_score_attempts"] += 1
            out["attempts"].append({
                "file": h.name, "score": a.get("score"),
                "fb": str(a.get("feedback", ""))[:60]})
    data_stats[p] = out

# ---------- reconcile ----------
plain_ok = tools_split["-"]
soft_p = sum(transcript_stats[p]["markers"]["clarify_fail"] for p in PERSONAS)
# P lower bound = exact clarify template hits; plain-text calls that succeeded = plain_ok
print("=" * 72)
print("SHIM LOG (HTTP request level, repo -> LLM seam)")
print(f"  successful requests : {len(succ)}  {dict(tools_split)}")
print(f"    TOOL_OK  = structured call returned valid JSON (wrapped into tool_calls)")
print(f"    tools=-  = plain-text call (clarify/greet/progress/farewell/comm_wrap)")
print(f"  failed requests     : {E}  (each = HTTP 500 after 3x SDK 429 inside shim)")
print(f"  SDK-level 429s      : {E * 3} (shim retried every failure 3x, backoff 1.2/2.4/3.6s)")
print(f"  unique error kinds  : {dict(err_msgs)}")
print(f"  shim restarts       : {listening} 'listening' lines")
print(f"  success latency ms  : p50={pctl(lat, .5)} p95={pctl(lat, .95)} max={lat[-1] if lat else 0}")
print(f"  error duration ms   : p50={pctl(err_lat, .5)} (3x 429 + backoff 1.2/2.4s before 500)")
print(f"  TOOL_MISS           : {tools_split['TOOL_MISS']}  (structured call succeeded but "
      f"returned unparseable JSON -> repo content-parser retry path)")
print(f"  est. recoveries on repo-side retry (success <=2.5s after an error): ~{recover_est}")

print("\nERROR-gap histogram (on bracket-reconstructed timestamps):")
for k, v in sorted(gap_hist.items()):
    print(f"  {v:4d}  {k}")
print(f"  => est. structured hard-failures from pairing: ~{E - paired_s - (E - 2 * paired_s if 2 * paired_s <= E else 0)} "
      f"(naive: {paired_s} close pairs => {paired_s} hard fails, {E - 2 * paired_s} singletons)")

print("\nstorm timeline (min: ok/err):")
for m, (ok, er) in storm_minutes:
    print(f"  {m}  ok={ok:3d} err={er:3d}")

print("=" * 72)
print("TRANSCRIPT MARKERS (exact template matches = deterministic fallback fired)")
tot = Counter()
for p in PERSONAS:
    st = transcript_stats[p]
    print(f"\n[{p}] turns={st['turns']} crashes={st['crashes']}")
    print(f"  intents: {st['intent_counts']}")
    for k, v in st["markers"].items():
        flag = "(soft)" if k in SOFT else ""
        if v:
            print(f"    {k}: {v} {flag}")
        tot[k] += v
print("\nALL personas total:")
for k, v in tot.items():
    print(f"  {k}: {v}")

print("=" * 72)
print("DATA-FILE EVIDENCE (persisted judge/evaluator fallbacks)")
for p in PERSONAS:
    ds = data_stats[p]
    print(f"\n[{p}] history files: {ds['records']}")
    print(f"  'Un-scored — judge error' verdicts : {ds['unscored_judge_error']}")
    print(f"  dsa attempts w/ 'couldn't score'   : {ds['dsa_couldnt_score_attempts']}")
    for a in ds["attempts"]:
        print(f"    - {a['file']} score={a['score']} fb={a['fb']!r}")

# ---------- reconcile ----------
session_recorded = sum(
    (SIM / p / "transcript.md").read_text(encoding="utf-8").count("Session recorded.")
    for p in PERSONAS)
# final exact model, validated against the shim log:
#   plain-text calls  = clarify invocations (intent=smalltalk turns) + progress(3)
#                       + farewell(2) + comm_wrap("Session recorded." firings)
#   plain-text FAILS  = exact template matches (clarify + wrap "Biggest pattern...")
#   plain-text OK     = total - fails  -> must equal tools='-' count in shim log
#   structured fails  : E_struct = E - P  = R + 2*S  (call_structured = 2 attempts)
#   S_known           = template/json-verified hard fails
clarify_invocations = sum(
    transcript_stats[p]["intent_counts"].get("'smalltalk'", 0) for p in PERSONAS)
wrap_fails = tot["comm_wrap_fail"]
progress_fails = tot["progress_fail"]
P = tot["clarify_fail"] + wrap_fails + progress_fails
plain_total = clarify_invocations + 3 + 2 + session_recorded
plain_ok_expected = plain_total - P
S_known = tot["dsa_evaluator_fail"] + tot["comm_interviewer_fail*"]
E_struct = E - P
print("\n" + "=" * 72)
print("RECONCILIATION  (validated against shim log)")
print(f"  clarify invocations (intent=smalltalk turns)  = {clarify_invocations}")
print(f"  comm_wrap firings ('Session recorded.')       = {session_recorded}")
print(f"  plain-text calls total = {clarify_invocations}+3+2+{session_recorded} = {plain_total}")
print(f"  plain-text FAILS (templates) = clarify {tot['clarify_fail']} + wrap {wrap_fails} "
      f"+ progress {progress_fails} = {P}")
print(f"  plain-text OK (derived) = {plain_ok_expected}  vs shim log tools='-' = {tools_split['-']}"
      f"  {'MATCH' if plain_ok_expected == tools_split['-'] else 'MISMATCH!'}")
print(f"  S known (dsa evaluator {tot['dsa_evaluator_fail']} + comm interviewer "
      f"{tot['comm_interviewer_fail*']}) = {S_known}")
print(f"  structured request failures = E - P = {E} - {P} = {E_struct} = R + 2*S_other + 2*{S_known}")
print(f"  => R + 2*S_other = {E_struct - 2 * S_known}")
print(f"     R (structured calls recovered on the repo's single manual retry) ~= 0-{6} "
      f"(storm-straddle bound; storms fully covered both attempts)")
print(f"     S_other ~= {(E_struct - 2 * S_known) // 2} (if R=0) down to "
      f"{(E_struct - 2 * S_known - 6) // 2} (if R=6)")
S_other_lo = (E_struct - 2 * S_known - 6) // 2
S_other_hi = (E_struct - 2 * S_known) // 2
print(f"  => TOTAL structured hard fails  S = {S_known + S_other_lo}-{S_known + S_other_hi}")
print(f"  => TOTAL fallback-triggering LLM failures = S + P ~= {S_known + S_other_lo + P}"
      f"-{S_known + S_other_hi + P}")
S_total_mid = S_known + (E_struct - 2 * S_known) // 2
# structured calls = first-try OK + R + S ; requests_structured = (first-try OK) + 2*(R + S)
# => calls_structured = requests_structured - (R + S)
requests_structured = len(succ) - tools_split['-'] + (E - P)  # TOOL_OK structured + struct errors
calls_structured = requests_structured - 3 - S_total_mid  # mid estimate R=3
total_calls = plain_total + calls_structured
print(f"  ~total LLM calls (mid est) = {plain_total} plain + {calls_structured} structured "
      f"= {total_calls}; failure-affected = {S_total_mid + P} "
      f"({100 * (S_total_mid + P) / total_calls:.0f}%)")

json.dump({"shim": {"succ": len(succ), "tools": dict(tools_split), "errors": E,
                    "sdk429": E * 3, "recover_est": recover_est,
                    "lat_p50": pctl(lat, .5), "lat_p95": pctl(lat, .95),
                    "storm_minutes": {m: er for m, (ok, er) in storm_minutes if er}},
           "transcripts": transcript_stats, "data": data_stats,
           "reconcile": {"E": E, "P_plain_fails": P, "plain_total": plain_total,
                         "clarify_invocations": clarify_invocations,
                         "S_known": S_known, "R_range": [0, 6],
                         "S_total_range": [S_known + S_other_lo, S_known + S_other_hi],
                         "fallback_llm_failures_range":
                             [S_known + S_other_lo + P, S_known + S_other_hi + P]}},
          open("/home/z/my-project/sim/fallback_analysis.json", "w"), indent=1)
print("\nsaved /home/z/my-project/sim/fallback_analysis.json")
