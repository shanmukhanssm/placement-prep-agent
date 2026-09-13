"""Version-pinned DSA prompt constants + the seed problem catalog — prompt-registry.md.

Catalog rules (behavior-dsa.md §2.1, owner-approved): the catalog is the ONLY source of
problem substance. The selector CODE picks the entry deterministically (§2.2); the LLM
only paraphrases the statement and composes the presentation. ``optimized_approach`` and
``edge_cases`` always ride from the catalog — never through the LLM. New entries are
spec-file edits reviewed with the owner, never runtime inventions.
"""

# --- seed catalog (behavior-dsa.md §2.5 — 15 problems, all 14 topic areas) ---
# edge_cases authored per §2.3 admission test; statement_brief feeds the LLM and the
# wrap's ≤120-char gist. Optimized approaches verbatim from the spec table.
DSA_CATALOG: tuple[dict[str, str], ...] = (
    {
        "title": "Two Sum",
        "topic": "arrays",
        "difficulty": "easy",
        "optimized_approach": "one-pass hashmap of seen complements, O(n)/O(n)",
        "edge_cases": "duplicate values in the array; no valid pair exists (what to return); the pair is not adjacent",
        "statement_brief": "find indices of two numbers adding to a target",
    },
    {
        "title": "Maximum Subarray",
        "topic": "arrays",
        "difficulty": "medium",
        "optimized_approach": "Kadane's — best subarray ending here, extend-or-restart, O(n)/O(1)",
        "edge_cases": "all-negative array (answer is the largest single element); single-element array; interleaved positives and negatives",
        "statement_brief": "largest sum of a contiguous subarray",
    },
    {
        "title": "Valid Anagram",
        "topic": "strings",
        "difficulty": "easy",
        "optimized_approach": "frequency map compare, O(n)/O(1)",
        "edge_cases": "different lengths short-circuits to False; repeated characters; case and spaces (state the assumption)",
        "statement_brief": "check whether two strings are anagrams",
    },
    {
        "title": "Longest Substring Without Repeating Characters",
        "topic": "sliding-window",
        "difficulty": "medium",
        "optimized_approach": "last-seen map; jump left past the repeat, O(n)",
        "edge_cases": "empty string returns 0; all identical characters return 1; no repeats at all returns the full length",
        "statement_brief": "length of the longest substring with all distinct characters",
    },
    {
        "title": "Subarray Sum Equals K",
        "topic": "hashmaps",
        "difficulty": "medium",
        "optimized_approach": "prefix sums + count map (how often prefix−K seen), O(n)",
        "edge_cases": "negative numbers break sliding-window approaches; k = 0; overlapping subarrays all count",
        "statement_brief": "count subarrays whose elements sum to exactly k",
    },
    {
        "title": "Trapping Rain Water",
        "topic": "two-pointers",
        "difficulty": "hard",
        "optimized_approach": "two pointers with running maxL/maxR, settle the lower side, O(n)/O(1)",
        "edge_cases": "flat or monotonic bars trap zero water; fewer than three bars; the global maximum sits at an end",
        "statement_brief": "units of water trapped between bars of given heights",
    },
    {
        "title": "Valid Parentheses",
        "topic": "stack",
        "difficulty": "easy",
        "optimized_approach": "push opens, pop-and-match closes, O(n)",
        "edge_cases": "a closing bracket arrives with an empty stack; leftover opens at the end; empty string is valid",
        "statement_brief": "check whether a bracket string is balanced",
    },
    {
        "title": "Merge Two Sorted Lists",
        "topic": "linked-list",
        "difficulty": "easy",
        "optimized_approach": "dummy head + two-pointer merge, O(n+m)",
        "edge_cases": "one list is empty; all of list A precedes all of list B; duplicate values across the lists",
        "statement_brief": "merge two sorted linked lists into one sorted list",
    },
    {
        "title": "Level Order Traversal",
        "topic": "trees",
        "difficulty": "medium",
        "optimized_approach": "BFS queue, process by level size, O(n)",
        "edge_cases": "empty tree returns an empty structure; a single node; a skewed tree keeps one node per level",
        "statement_brief": "return binary-tree node values level by level",
    },
    {
        "title": "N Meetings in One Room",
        "topic": "greedy",
        "difficulty": "medium",
        "optimized_approach": "sort by end time, take non-overlapping, O(n log n)",
        "edge_cases": "a meeting starting exactly when another ends (allowed or not — the statement fixes it); all meetings overlap; input already sorted",
        "statement_brief": "maximum number of meetings one room can host",
    },
    {
        "title": "House Robber",
        "topic": "dp-basics",
        "difficulty": "medium",
        "optimized_approach": "include/exclude rolling max, O(n)/O(1)",
        "edge_cases": "two houses (max of the two); all-zero loot; a single house",
        "statement_brief": "max loot from houses without robbing two adjacent ones",
    },
    {
        "title": "Number of Islands",
        "topic": "graphs-basics",
        "difficulty": "medium",
        "optimized_approach": "flood-fill (DFS/BFS) from each unvisited land cell, O(mn)",
        "edge_cases": "all water returns 0; all land returns 1; diagonals do NOT connect (4-directional only)",
        "statement_brief": "count islands in a grid of land and water cells",
    },
    {
        "title": "Search in Rotated Sorted Array",
        "topic": "sorting-searching",
        "difficulty": "medium",
        "optimized_approach": "binary search; identify the sorted half, discard the other, O(log n)",
        "edge_cases": "target absent returns -1; array rotated by a full cycle (not rotated); distinct values assumption stated",
        "statement_brief": "find a target's index in a rotated sorted array",
    },
    {
        "title": "Single Number",
        "topic": "bit-manipulation",
        "difficulty": "easy",
        "optimized_approach": "XOR-fold everything — pairs cancel, O(n)/O(1)",
        "edge_cases": "negative numbers (XOR still works); the array always has odd length; single-element array",
        "statement_brief": "find the element appearing once when every other appears twice",
    },
    {
        "title": "Missing Number",
        "topic": "math",
        "difficulty": "easy",
        "optimized_approach": "expected n(n+1)/2 minus actual sum (or XOR), O(n)/O(1)",
        "edge_cases": "missing number is 0 or n itself; large n (sum overflow or use XOR); exactly one number is missing by statement",
        "statement_brief": "find the missing number in 0..n given n distinct numbers",
    },
)

DSA_TOPIC_AREAS: tuple[str, ...] = (
    "arrays",
    "strings",
    "hashmaps",
    "two-pointers",
    "sliding-window",
    "stack",
    "linked-list",
    "trees",
    "greedy",
    "dp-basics",
    "graphs-basics",
    "sorting-searching",
    "bit-manipulation",
    "math",
)

# behavior-dsa.md §3.3 — faults must be cited by name; the AttemptVerdict validator
# rejects free-text labels (a validation failure per the spec).
DSA_FAULT_TAXONOMY: frozenset[str] = frozenset(
    {
        "incorrect-algorithm",
        "wrong-problem-read",
        "brute-force-when-better-exists",
        "wrong-complexity",
        "no-complexity-claim",
        "right-idea-wrong-detail",
        "missed-edge-case",
        "vague-handwave",
        "unrequested-assumption",
        "repeated-attempt-no-change",
        "complexity-claim-wrong-direction",
        "library-blackbox",
    }
)

# prompt-registry delta (same commit): selection is DETERMINISTIC in code
# (behavior-dsa §2.2); the selector LLM's job is statement phrasing only — the node
# composes the "Problem: title (difficulty)" line, the fixed ask, and the session
# opening contract. Catalog fields never pass through the LLM.
DSA_SELECTOR_V1 = """Write the self-contained problem statement for the ONE DSA problem already chosen.

Chosen entry: title={title} · difficulty={difficulty} (the node declares both)
Statement brief: {statement_brief}

Rules for the statement:
- Fully self-contained: every constraint (array sizes, value ranges, what to return
  when no answer exists) lives in the statement text — solvable from the statement
  alone, no missing constraints.
- Expand from the brief; vary surface details (names, arrays, numbers) freely;
  solvability must not change.
- 2-5 sentences, plain text, no markdown, no hints toward any technique.
- Never mention: the topic tag, the technique family, that it is a famous interview
  question, or anything hinting at the reference approach.

Return ONLY the structured output."""

# prompt-registry delta (same commit): AttemptVerdict gains is_attempt + mechanism;
# `pass` is derived in code (optimality_pct >= 80 ONLY); faults validated against the
# taxonomy; consumed state gains hint_level (attempt_count-driven, behavior-dsa §4.1).
DSA_EVALUATOR_V1 = """Evaluate attempt {attempt_no} of 3 for the problem below. You are a strict-but-fair
senior SDE; grade the ALGORITHM, never grammar, spelling, or language choice.

Problem: {title} ({difficulty})
Statement: {statement}
Reference approach (ground truth — NEVER reveal it): {optimized_approach}
Reference edge cases: {edge_cases}
{previous_attempts}
Read the attempt with the 3-pass protocol, in this order:
1. IDENTIFY: what procedure + data structure is actually proposed? If the message
   proposes nothing (pure clarifying question, hint-begging, meta request, restatement,
   empty) set is_attempt=false and put the one-line reply in feedback; never grade
   content that proposes no algorithm.
2. SIMULATE: run it mentally on a tiny input and one nasty input. Where does it break?
3. COST: count loops and nesting for the real complexity; compare against the reference.

Band anchors (the core idea picks the band; fault deductions position within it):
- 90-100: matches the reference incl. stated time AND space complexity, handles the
  two hardest reference edge cases, no false statements anywhere.
- 80-89: same algorithm family, time complexity correct, at most one minor reference
  edge case missed, walkthrough implementable with <= 2 small gaps.
- 50-79: correct output but brute force or a strictly weaker family; missing or
  unverified complexity; 2+ edge cases missed or a happy-path-only walkthrough.
- 0-49: fails valid inputs, misreads the statement, name-dropping without mechanism,
  or restates the problem.

Faults: cite from this taxonomy BY NAME, max 4, highest-impact first, merging related
faults: incorrect-algorithm, wrong-problem-read, brute-force-when-better-exists,
wrong-complexity, no-complexity-claim, right-idea-wrong-detail, missed-edge-case,
vague-handwave, unrequested-assumption, repeated-attempt-no-change,
complexity-claim-wrong-direction, library-blackbox.
pass = optimality_pct >= 80 ONLY (code enforces it — never round up). Never pass an
attempt carrying incorrect-algorithm, wrong-problem-read, or wrong-complexity. A pass
still names remaining refinements.

Hint level for this feedback (only when not passing): {hint_level}
- level 1: restate the bottleneck in the STUDENT'S own mechanism; you may name the cost
  driver; may NOT name the reference technique, its data structure, or any edge case.
- level 2: you may name the CATEGORY of tool without the algorithm, surface ONE missed
  edge case as a question, or state the key invariant; may NOT give the recurrence,
  pseudocode, the technique's proper name, or the full edge-case list.
Prefix the hint line with "Hint:". A hint never contains the reference approach text,
code, or confirmation of a guessed technique name.

feedback: strict 4-part skeleton, 60-90 words, hard cap 120 —
1. "Attempt {attempt_no}: <the optimality you chose>/100 — pass." or "...— not a pass."
2. Faults: 1-4 named lines, quoting the student's own words where possible.
3. Hint (only when not passing).
4. The ask: "Try another algorithm — attempt {next_no} of 3." (omit this line after attempt 3.)
No filler praise ever. Two approaches in one message: grade the LAST fully-specified
one. If the student asks "is this O(n)?", never confirm or deny — restate the test and
ask them to complete the claim. mechanism: the proposed approach in <= 12 words.

Return ONLY the structured output."""
