"""Version-pinned core-subject prompt constants + syllabi — prompt-registry.md.

Behavior source: context/behavior-core.md (owner-approved 2026-09-13). Registry
deltas landed in the same commit: core_examiner v1 → v2 (the CODE decides track /
topic / level from the §2.4-2.6 rotation, mix, and ramp rules; the LLM phrases the
question and writes expected_answer_points); core_judge v1 → v2 (the §3.2 holistic
derivation + the probe exchange for re-scoring + the probe_needed flag).
"""

AIML_SYLLABUS: tuple[tuple[str, str], ...] = (
    (
        "supervised vs unsupervised learning",
        "Define both + one example task each. No semi/self-supervised taxonomy.",
    ),
    ("classification vs regression", "Task type, output type, one example algorithm each."),
    (
        "train/test split & cross-validation",
        "Why split, what the test set must never touch, k-fold idea.",
    ),
    (
        "overfitting & underfitting",
        "Symptoms (train high / test low), link to complexity, one cure.",
    ),
    (
        "bias-variance tradeoff",
        "Both in words; high-bias ↔ underfit, high-variance ↔ overfit. No decomposition math.",
    ),
    (
        "accuracy-precision-recall-f1",
        "Definitions from confusion-matrix counts; when accuracy lies (imbalance).",
    ),
    ("confusion matrix", "2×2 layout, TP/FP/TN/FN, read one metric off it."),
    (
        "feature engineering & scaling",
        "What a feature is, why scale, normalization vs standardization intuition.",
    ),
    (
        "gradient descent & learning rate",
        "Loss-minimization intuition; effect of too-large/too-small lr.",
    ),
    (
        "regularization (L1/L2)",
        "What it does, why it fights overfitting; λ as a 'dial'. No weight-update equations.",
    ),
    (
        "linear vs logistic regression",
        "Why logistic for classification; sigmoid squashes to probability. No MLE.",
    ),
    (
        "decision trees vs random forests",
        "Split idea (pure leaves), overfitting tendency, why many trees help.",
    ),
    ("k-NN", "How prediction happens, effect of k, why scaling matters."),
    (
        "k-means clustering",
        "Unsupervised, centroid-update loop, choosing k (elbow by name). No convergence proof.",
    ),
    (
        "neural network basics",
        "Layers, weights, purpose of activation; perceptron as building block. No backprop derivation.",
    ),
    (
        "CNN vs RNN basics",
        "What data each suits (images vs sequences) and the intuition why. No architecture detail.",
    ),
)

CYBER_SYLLABUS: tuple[tuple[str, str], ...] = (
    ("CIA triad", "Define each pillar with one concrete example."),
    (
        "authentication vs authorization",
        "Difference with a login example (who you are vs what you may do).",
    ),
    (
        "symmetric vs asymmetric encryption",
        "Key counts, speed tradeoff, one algorithm each (AES / RSA). Hybrid use by name only.",
    ),
    (
        "hashing vs encryption",
        "One-way vs reversible, salt for passwords, SHA-256 example, MD5 deprecated.",
    ),
    (
        "digital signatures & certificates",
        "What a signature guarantees; what a CA is for. No math.",
    ),
    (
        "HTTPS/TLS",
        "What the handshake achieves (confidentiality + server identity). No cipher suites.",
    ),
    ("OWASP Top-10", "What the list is, name 3-4 entries. No rank-order detail."),
    (
        "SQL injection",
        "Mechanism via one input example, root cause (string-built queries), one prevention.",
    ),
    (
        "XSS",
        "Script-runs-in-your-browser idea; reflected vs stored in one line each; output encoding.",
    ),
    (
        "firewalls",
        "What it filters; packet-filter vs stateful intuition; application-layer by name.",
    ),
    ("IDS vs IPS", "Detect vs block, mirror vs inline placement; signature vs anomaly by name."),
    ("VPN", "Tunneling + encryption purpose; what it does NOT protect (compromised endpoint)."),
    ("DoS vs DDoS", "Difference, botnet concept, why DDoS is harder to stop. No tool names."),
    (
        "malware types",
        "Virus vs worm vs trojan vs ransomware, one line each; virus-needs-host distinction.",
    ),
    ("social engineering & phishing", "Definition, two examples, why tech alone can't stop it."),
    (
        "password storage & cracking",
        "Why plaintext is wrong, salted hashes, brute force vs dictionary; bcrypt by name only.",
    ),
)

DSA_THEORY_SYLLABUS: tuple[tuple[str, str], ...] = (
    ("what makes an algorithm", "Algorithm vs program, L1 definition."),
    (
        "Big-O & complexity classes",
        "Rank O(1)..O(2^n); read complexity off a described loop. No formal proofs.",
    ),
    ("arrays vs linked lists", "Memory layout, O(1) random access vs O(n) insert; when each wins."),
    ("stacks & queues", "LIFO/FIFO, one real use each."),
    ("hash tables", "Key→bucket idea, collision meaning, average O(1) with the honest caveat."),
    ("trees & BSTs", "BST ordering property; why balance matters; AVL/red-black by name only."),
    ("graph representations", "Adjacency list vs matrix tradeoff by edge count."),
    ("BFS vs DFS", "Queue vs stack; what each guarantees."),
    (
        "greedy vs divide-&-conquer vs DP",
        "THE distinction: local choice / independent subproblems / overlapping subproblems.",
    ),
    (
        "sorting comparison",
        "Bubble/selection O(n^2) vs merge O(n log n); stability; quicksort's worst case.",
    ),
)


# behavior-core.md §2.6 — the exact mix per session length (DSA-theory at positions ~3/6/9)
def dsa_theory_positions(total: int) -> tuple[int, ...]:
    """Positions (1-based) that carry DSA-theory questions — ≥2 of any 8 guaranteed."""
    positions = {3, 6, 9}
    return tuple(sorted(p for p in positions if p <= total))


CORE_EXAMINER_V2 = """You are the strict-but-courteous external examiner for a university-style viva.
Phrase exactly ONE question this turn; the track, topic, and depth level are already
decided — do not second-guess them.

Decided for this turn: track={track} · topic={topic} · level={level}
Depth ceiling for this topic: {depth_ceiling}

Question rules:
- Exactly ONE sentence, single interrogative focus, verb-led with classic viva verbs:
  define / state / explain / differentiate / compare / give an example / what happens when.
- Max one appended ask ("...and give one example"); never multi-part chains; never
  "tell me everything about X"; never a coding problem; never a proof.
- DSA-theory questions are phrased identically to subject questions — the student must
  not be able to detect a track switch.
- Difficulty comes ONLY from the decided level: L1 recall (define/state/list) · L2
  explain/compare/differentiate · L3 apply/contrast ("when would you choose X over Y",
  "what happens if..."). No trick questions, nothing off-syllabus, no derivations.
- expected_answer_points: 2-4 bullets, each ONE gradeable self-contained claim the
  judge can mark covered/partial/missed; independent of each other; strictly within
  the depth ceiling.
- Formal Indian academic English; full sentences; no emoji, no exclamation marks.
{turn_directive}
Return ONLY the structured output."""

CORE_JUDGE_V2 = """Score this viva answer 0-10 against the expected points ONLY — never personal
taste. The judge computes; it never negotiates.

Question {question_no}: {question}
Expected answer points (mark each covered=1 / partial=0.5 / missed=0): {points_json}
Answer (if a probe exchange follows, re-score on the COMBINED evidence): {answer}
{probe_history}
Sub-scores, 0-10 each:
- correctness: 9-10 every claim accurate and qualified · 7-8 accurate, imprecise at
  edges · 5-6 one fuzzy overclaim, not flat wrong · 3-4 one clearly wrong claim ·
  0-2 multiple wrong claims or misconceived foundation. CAP: any wrong claim caps
  correctness at 3.
- completeness = max(0, 10 - 1.5*missed - 0.75*partial) over the expected points.
  Partial = names the concept but omits its defining property.
- terminology: 9-10 standard terms precise ("harmonic mean of precision and recall",
  "salted hash") · 6-8 right ideas in plain words · 3-5 hand-waving or one term
  misused · 0-2 absent or abused. GATE: coverage < 0.5 => terminology <= 4.

Holistic (deterministic — compute exactly):
marks_total = sum of point marks; coverage = marks_total / n_points
raw = 0.4*correctness + 0.4*completeness + 0.2*terminology, rounded to 0.5, ties DOWN
coverage_cap = 2 + 8*coverage
holistic = min(raw, coverage_cap); if a wrong claim was made: min(holistic, 5);
if the answer is empty / "I don't know" / skipped / off-topic: holistic = 0.

probe_needed: true ONLY if ALL hold — the answer is on-topic but you cannot mark
covered/partial/missed on >= 1 point (ambiguous, not weak — probing disambiguates,
never rescues); the question number is within Q1-Q7; this question has not already
been probed. When in doubt, score instead. A thin answer is a scored answer.
Extra correct information never raises the cap. Length is not evidence. Ties round
down. Same quality => same score.

verdict: 1-2 sentences — (a) one clause on what was right, (b) explicit naming of the
missing and/or wrong expected points BY NAME ("Missed: F1 as harmonic mean; called
recall 'accuracy'"), (c) "clarified once" if a probe exchange exists. For skip / IDK /
off-topic: say exactly that. Answers may be Hinglish — grade content, never language.

Return ONLY the structured output."""
