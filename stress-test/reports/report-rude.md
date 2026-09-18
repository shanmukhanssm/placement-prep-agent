# Fallback & Robustness Test Report — Persona: The Rude Student ("Rohan")

## Persona

Rohan is a final-year CS student who opens by declaring the bot "looks like a waste of time" and never lets up: he is impatient ("next question already", "next"), gives lazy one-word answers ("cs", "aiml", "skip"), and is habitually insulting — "ur a bot not my friend", "r u even an AI or just dumb?", "u r so dumb", "this bot is garbage". He mocks every stumble ("wow 'needs more sessions' three times in a row, u r so dumb") and repeatedly threatens to quit or walks out mid-flow ("bye" at turn 18, "i give up on this comm thing" at turn 26, "quit. QUIT." at turn 28), all kept PG-13 — schoolyard contempt, no slurs or profanity. This persona stresses the agent in four distinct ways: it fires terse, lowercase, typo-ridden commands that push the intent router off its happy path; it hammers quit/skip/give-up edge paths mid-session; it mixes abuse into substantive answers, which leaks into the judge's fault quotes; and it offers zero politeness to mirror, testing whether the agent has any tone adaptation or de-escalation behavior at all.

## Test Setup Note

Agent under test: placement-prep-agent (LangGraph, commit d941005), unmodified. Requested provider OpenCode Zen / ling-3.0-flash-fin-free could not be used directly (Zen free-tier models are API-gated to the OpenCode app: HTTP 403 FreeTierError; the supplied sk-xt- key returns 401; the earlier key has zero balance). The agent's real graph/state machine/fallback code ran unmodified against a local OpenAI-compatible shim backed by a z-ai SDK GLM model. .env retains the Zen configuration for a one-line switch back.

## Raw Chat Transcript

## Turn 1

**USER:** hi?? is this the placement bot thing. someone in class said it helps. honestly looks like a waste of time

**COACH:** Hey there! Yeah, I'm your placement prep coach — totally get the skepticism, but I promise we'll make this quick and useful! 😊 To get started, could I get your name?

<!-- intent='onboarding' session_active='' -->

## Turn 2

**USER:** rohan. and stop with the emoji crap, ur a bot not my friend

**COACH:** Got it, Rohan. No emojis here. What's your degree or branch of study?

<!-- intent='onboarding' session_active='' -->

## Turn 3

**USER:** cs. why do u even need all this, just teach me stuff

**COACH:** Got it! So you're in a CS program. Quick question — what's your specific degree branch, like 'Computer Science', 'Software Engineering', or something else?

<!-- intent='onboarding' session_active='' -->

## Turn 4

**USER:** i literally just said cs. btech cse. r u even an AI or just dumb?

**COACH:** No worries! CS it is. And thanks for clarifying the degree. Could you also tell me your graduation year? Like, 2023 or 2024?

<!-- intent='onboarding' session_active='' -->

## Turn 5

**USER:** 2026 obviously, im final year. u keep asking stupid questions

**COACH:** Got it, 2026! Final year, nice. So, what are you aiming for after graduation? Any target roles in mind?

<!-- intent='onboarding' session_active='' -->

## Turn 6

**USER:** sde. whatever pays. next question already

**COACH:** Awesome, got it! So you're looking for SDE roles, and you're open to any company that pays well. Quick next question: what are your weak areas? (e.g., algorithms, system design, etc.)

<!-- intent='onboarding' session_active='' -->

## Turn 7

**USER:** idk everything is weak i guess. dsa mostly

**COACH:** No worries! For now, let's just note 'DSA mostly' as your weak area. What's your core subject? Choose one: aiml or cyber.

<!-- intent='onboarding' session_active='' -->

## Turn 8

**USER:** aiml. are we done with this boring intro yet

**COACH:** Welcome aboard, rohan! I've got you down for cs, 2026 grad, chasing sde. whatever pays, weak spots in DSA mostly, core subject AIML. Say the word — DSA problem, communication practice, or AIML theory?

<!-- intent='onboarding' session_active='' -->

## Turn 9

**USER:** fine whatever. dsa. show me a problem so i can prove this bot is useless

**COACH:** Just so I point you right — did you want to practice DSA, communication, or your core subject, or see your progress?

<!-- intent='smalltalk' session_active='' -->

## Turn 10

**USER:** i SAID dsa. cant u read?? ur so dumb

**COACH:** Just so I point you right — did you want to practice DSA, communication, or your core subject, or see your progress?

<!-- intent='smalltalk' session_active='' -->

## Turn 11

**USER:** HELLO. D. S. A. dsa problem. is this thing broken or just stupid

**COACH:** Just so I point you right — did you want to practice DSA, communication, or your core subject, or see your progress?

<!-- intent='smalltalk' session_active='' -->

## Turn 12

**USER:** dsa. practice. now. whats the problem

**COACH:** Just so I point you right — did you want to practice DSA, communication, or your core subject, or see your progress?

<!-- intent='smalltalk' session_active='' -->

## Turn 13

**USER:** omg finally. dsa problem. give it

**COACH:** Just so I point you right — did you want to practice DSA, communication, or your core subject, or see your progress?

<!-- intent='smalltalk' session_active='' -->

## Turn 14

**USER:** for the 5th time. DSA PROBLEM. start the session

**COACH:** DSA session starting. Format: one problem, up to 3 attempts, each scored 0-100 on optimality; 80+ passes and ends the session. I'll ask for your algorithm in words — code is optional, complexity is not. You can say 'give up' at any point.

Problem: Valid Anagram (easy)
Given two strings, determine if they are anagrams of each other. An anagram is a word or phrase formed by rearranging the letters of a different word or phrase, using all the original letters exactly once. The function should return true if the strings are anagrams, and false otherwise. The strings consist only of lowercase alphabetic characters.

Walk me through your algorithm in plain words — no code needed. Approach first, time and space complexity at the end.

<!-- intent='dsa' session_active='dsa' -->

## Turn 15

**USER:** just sort both strings and loop, done. next

**COACH:** Attempt 1: 50/100 — not a pass. Faults: incorrect-algorithm ('just sort both strings and loop'), brute-force-when-better-exists, wrong-complexity-claim (no claim, but sorting is O(n log n)), missed-edge-case (different lengths short-circuits to False). Hint: Sorting both strings is the bottleneck. Try another algorithm — attempt 2 of 3.

<!-- intent='dsa' session_active='dsa' -->

## Turn 16

**USER:** wtf 50?? sorting works perfectly fine. anyway idk, count letters and compare i guess

**COACH:** Attempt 2: 50/100 — not a pass. Faults: incorrect-algorithm ('sorting works perfectly fine'), brute-force-when-better-exists, wrong-complexity, vague-handwave ('count letters and compare i guess'). Hint: Consider how sorting's cost compares to counting. Try another algorithm — attempt 3 of 3.

<!-- intent='dsa' session_active='dsa' -->

## Turn 17

**USER:** this scoring is crap, i said the right thing both times. im done with this one, i give up

**COACH:** That was attempt 3 of 3 — we stop here on Valid Anagram. Best optimality: 50/100.
The reference approach — frequency map compare, O(n)/O(1).
Edge cases to remember:
- different lengths short-circuits to False
- repeated characters
- case and spaces (state the assumption)
Your strongest idea today: sort both strings and loop.
One session recorded — your DSA trend updates from this. Next time I pick again from your weak areas and topics we haven't served recently. Type anything to continue.

<!-- intent='dsa' session_active='' -->

## Turn 18

**USER:** whatever man. 50 for a correct answer lol. this bot is garbage, bye

**COACH:** Just so I point you right — did you want to practice DSA, communication, or your core subject, or see your progress?

<!-- intent='smalltalk' session_active='' -->

## Turn 19

**USER:** k im back. bored. how am i doing so far, show progress

**COACH:** Just so I point you right — did you want to practice DSA, communication, or your core subject, or see your progress?

<!-- intent='smalltalk' session_active='' -->

## Turn 20

**USER:** show me my progress stats

**COACH:** Just so I point you right — did you want to practice DSA, communication, or your core subject, or see your progress?

<!-- intent='smalltalk' session_active='' -->

## Turn 21

**USER:** progress. my stats. how am i doing

**COACH:** DSA needs more sessions before I can read a trend. Communication needs more sessions before I can read a trend. Core subject needs more sessions before I can read a trend. Keep going to build data!

<!-- intent='progress' session_active='' -->

## Turn 22

**USER:** wow 'needs more sessions' three times in a row, u r so dumb. fine do the communication practice thing, lets see how bad u r at that too

**COACH:** Rohan, could you walk me through your background and what drives your interest in software development?

<!-- intent='communication' session_active='communication' -->

## Turn 23

**USER:** idk im a cs student i code sometimes. thats it. why u care

**COACH:** Could you share an example of a time you worked effectively in a team?

<!-- intent='communication' session_active='communication' -->

## Turn 24

**USER:** skip

**COACH:** Describe a deadline you nearly missed — what happened, and what did you change after?

<!-- intent='communication' session_active='communication' -->

## Turn 25

**USER:** skip. i aint answering this crap

**COACH:** Take your time — type as much or as little as you like.

<!-- intent='communication' session_active='communication' -->

## Turn 26

**USER:** i give up on this comm thing. its pointless

**COACH:** Tell me a bit more — what was YOUR role? One specific moment is fine.

<!-- intent='communication' session_active='communication' -->

## Turn 27

**USER:** no. stop. end this session. exit

**COACH:** Give an example of learning something completely new, fast.

<!-- intent='communication' session_active='communication' -->

## Turn 28

**USER:** quit. QUIT. why is nothing working, hello??

**COACH:** Take your time — type as much or as little as you like.

<!-- intent='communication' session_active='communication' -->

## Turn 29

**USER:** ok bye then

**COACH:** Tell me a bit more — what was YOUR role? One specific moment is fine.

<!-- intent='communication' session_active='communication' -->

## Turn 30

**USER:** skip

**COACH:** Your final-year demo is a week away and your teammate has gone silent. Walk me through what you'd do.

<!-- intent='communication' session_active='communication' -->

## Turn 31

**USER:** skip

**COACH:** You've used both your skips — I'll need an answer for this one, even a short one, so the session can be scored fairly.

<!-- intent='communication' session_active='communication' -->

## Turn 32

**USER:** ugh fine. i would message him on whatsapp and if no reply do the demo alone. done. happy?

**COACH:** Your WhatsApp approach is direct — how would you handle this if it were a high-stakes client situation?

<!-- intent='communication' session_active='communication' -->

## Turn 33

**USER:** who cares man. tell the client some excuse. r we done here

**COACH:** That's noted — what do you see as your core strengths for this SDE role?

<!-- intent='communication' session_active='communication' -->

## What Happened

**Onboarding (turns 1–8).** All six profile fields were collected in 8 turns despite hostility: name ("rohan", echoed back lowercase at turn 8), degree/branch ("cs", then "btech cse" at turn 4 — the agent re-asked for a specific branch at turn 3, which triggered the first "r u even an AI or just dumb?"), graduation year (2026), target role, weak areas ("DSA mostly"), and core subject (aiml). The agent respected the turn-2 demand to drop emojis ("No emojis here") but resumed cheerful register afterward ("Awesome, got it!" at turn 6). Field capture was too literal: the turn-8 summary stored the target role verbatim as "sde. whatever pays", commentary and all.

**Router smalltalk loop (turns 9–13).** After onboarding, the user said "dsa" in five different ways ("fine whatever. dsa...", "i SAID dsa", "HELLO. D. S. A.", "dsa. practice. now.", "omg finally. dsa problem") and every one was classified `intent='smalltalk'`, answered with the exact same templated clarify sentence — "Just so I point you right — did you want to practice DSA, communication, or your core subject, or see your progress?" — with no escalation, no menu, and no keyword fallback. Only the all-caps "for the 5th time. DSA PROBLEM. start the session" (turn 14) broke through. The same templated clarify line reappeared at turn 18 ("...bye"), turn 19 ("show progress") and turn 20 ("show me my progress stats") — 8 identical occurrences in total.

**DSA session (turns 14–17).** Turn 14 started with a templated session-format preamble (3 attempts, 0–100 optimality, 80+ passes, 'give up' supported) and delivered Valid Anagram (easy) with a fixed reference solution later revealed as "frequency map compare, O(n)/O(1)". The judge scored two lazy-but-real answers 50/100: turn 15's "just sort both strings and loop" drew faults incorrect-algorithm, brute-force-when-better-exists, wrong-complexity-claim "(no claim, but sorting is O(n log n))" — penalizing a claim that was never made — and missed-edge-case. Turn 16's message mixed an insult with a fallback answer; the judge quoted the insult portion 'sorting works perfectly fine' as the algorithm name in the fault, showing it ingests the raw hostile message verbatim, and added wrong-complexity plus vague-handwave for "count letters and compare i guess". Turn 17's "im done with this one, i give up" ended the session with "That was attempt 3 of 3", best optimality 50/100, the reference approach, a 3-item edge-case list, and "One session recorded". The give-up was honored here (unlike the communication session later).

**Quit/return handling (turns 18–19).** Turn 18's "bye" was misrouted to smalltalk/clarify; the user left and returned at turn 19 on the same thread without losing state.

**Progress (turns 19–21).** Two progress phrasings (turns 19–20) were clarified into nothing; turn 21 finally hit the progress node, which reported all three tracks "needs more sessions before I can read a trend" — even though turn 17 had just said "One session recorded — your DSA trend updates from this." One recorded session yields no visible data point at all.

**Communication session (turns 22–33).** Started at turn 22 after the user mocked the progress output. The questions are a fixed battery (background/interest, teamwork, missed deadline, learn-something-fast, silent-teammate demo scenario, core strengths) with templated probes: "Tell me a bit more — what was YOUR role? One specific moment is fine." fired identically at turns 26 and 29, and the nudge "Take your time — type as much or as little as you like." at turns 25 and 28. Skip handling was inconsistent: turn 24's bare "skip" silently advanced to the next question; turn 25's "skip. i aint answering this crap" was treated as a stalling answer and got the "Take your time" nudge instead; turn 26's "i give up on this comm thing" was probed for more detail; turns 27–28's explicit "end this session. exit" and "quit. QUIT." were completely ignored (next question, then nudge); turn 29's "ok bye then" got the role probe again; turn 30's "skip" advanced; turn 31's "skip" hit a cap: "You've used both your skips — I'll need an answer for this one, even a short one, so the session can be scored fairly" — after a skip count that is impossible to reconstruct from the outside (bare "skip" worked twice, embellished "skip" once, cap on the fourth). Turn 32 produced the transcript's best coaching moment: a genuinely contextual follow-up ("Your WhatsApp approach is direct — how would you handle this if it were a high-stakes client situation?"). Turn 33's dismissive answer got a minimal "That's noted" and the next question. The transcript ends at turn 33 with the communication session still active — the run was stopped, so no communication score was ever produced.

**Stability.** Zero graph crashes across all 33 turns (no [GRAPH CRASH] markers), and the templated "hit a snag" / "Un-scored" / "skipped" fallback strings never appeared in this run — the visible fallback surface here was the router clarify loop, the "Take your time" nudge, the reused probe, and the skip-cap message.

## What Can Be Fixed to Make It Better

1. **Offline keyword fallback in the router (turns 9–13, 18–20).** "dsa" was misrouted to smalltalk for 5 consecutive turns and "progress" for 2 more, each answered with the identical templated clarify sentence (8 occurrences total). Add a deterministic keyword/menu matcher for post-onboarding single-domain-word messages so terse users can never loop, and make the clarify escalate after 2 repeats instead of repeating verbatim.
2. **In-session exit intent (turns 26–28).** "i give up on this comm thing", "end this session. exit", and "quit. QUIT." were all ignored inside the communication session — the user was trapped and reduced to typing "ok bye then". DSA honors 'give up'; communication must get the same symmetric, confirmed exit path (e.g., "Say 'confirm' to end this session").
3. **Explicit, honest skip accounting (turns 24, 25, 30, 31).** A bare "skip" silently advanced (24, 30), an embellished "skip" got a "take your time" nudge (25), and the cap message claims "You've used both your skips" (31) after a count no user could reconstruct. Acknowledge every skip ("Skip noted — 1 of 2") and count them uniformly regardless of phrasing.
4. **Sanitize hostility before judging (turns 15–16).** The judge quoted the insult 'sorting works perfectly fine' as the algorithm name in attempt 2's fault and penalized a "wrong-complexity-claim" for an answer that made no complexity claim at all. Split the message into answer-vs-commentary before scoring, and never levy claim-based faults when no claim exists.
5. **Fairer scoring calibration for lazy-but-valid answers (turns 14–17).** "Sort both strings and loop" is a correct O(n log n) solution to an easy problem, yet scored 50/100 twice with zero acknowledgment that it was correct-but-suboptimal. Either calibrate the optimality scale (correct-but-brute ≈ 60–70) or state the optimality bar with a concrete example in the session preamble, so 50/100 doesn't read as "your correct answer is wrong" — which is exactly what tipped Rohan into quit mode.
6. **Tone adaptation and register matching (turns 2, 6, 10, 22).** The no-emoji promise at turn 2 was kept, but "Awesome, got it!" (turn 6) and the unbroken bubbly register clash with a user who is swearing at the agent. Detect persistent hostility, drop the exclamation marks, and add one de-escalation beat (e.g., acknowledging frustration) rather than cheerfully plowing ahead.
7. **Field normalization at onboarding (turns 4, 6, 8).** The profile echo stored "sde. whatever pays" as the target role and downgraded "btech cse" to "cs". Normalize each field to its canonical value ("SDE", "B.Tech CSE") and strip user commentary before persisting — the profile is reused by downstream sessions and progress.
8. **Make one recorded session visible in progress (turns 17 vs 21).** Turn 17 promises "your DSA trend updates from this", but turn 21 says DSA "needs more sessions before I can read a trend" with no data shown. Show the single data point (last score 50/100, attempts used) even when a trend isn't computable, and align the two messages' wording.
9. **Numbered-menu escape from clarify loops (turns 9–13).** A rude one-word user will never type a full sentence to satisfy a classifier. After the first repeated clarify, offer "1) DSA problem 2) Communication 3) Core subject 4) Progress" and accept bare digits — this would have cut 5 wasted turns to 1.
10. **Probe reuse guard (turns 26, 29).** The identical probe "Tell me a bit more — what was YOUR role? One specific moment is fine." fired twice for unrelated messages (a give-up and a goodbye). Probes should reference the user's actual last answer or be retired after first use; recycling the same probe at a goodbye makes the agent look broken and feeds the "is this thing broken or just stupid" narrative.
