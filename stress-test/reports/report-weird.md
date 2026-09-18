# Fallback & Robustness Test Report — Persona: The Weird-Answer Student ("Casey")

## Persona

Casey was played as the mirror image of a hostile user: unfailingly polite, structurally cooperative, and completely unserious in content. Every onboarding field, DSA attempt, and behavioral answer arrived as a well-formed sentence or STAR-shaped story, but the substance was surreal — a student named "Captain Banana / Sir Fruit, Esquire" studying "Applied Vibro-Ethics with a minor in banana ripening science", DSA algorithms like a "hashmap of vibes" and a "quantum raccoon" with complexity "O(moon) / O(feelings)", and interview answers featuring 17 samosas, human pyramids chanting deprecated Java methods, and emotions "force-pushed to main". This persona stresses scoring and validation integrity rather than crash-safety: fluent, grammatical nonsense is exactly the input most likely to (a) slip implausible values past profile extractors, (b) trick judges into agreeable acknowledgments of things that never happened, and (c) inflate or hallucinate scores because the surface form looks like a genuine attempt. It also probes whether normalization can rescue real values buried in noise (a graduation year hidden inside "the year of the dragon, which the ancients also call 2027") and whether validators hold the line on enum fields while free-text fields accept anything.

## Test Setup Note

Agent under test: placement-prep-agent (LangGraph, commit d941005), unmodified. Requested provider OpenCode Zen / ling-3.0-flash-fin-free could not be used directly (Zen free-tier models are API-gated to the OpenCode app: HTTP 403 FreeTierError; the supplied sk-xt- key returns 401; the earlier key has zero balance). The agent's real graph/state machine/fallback code ran unmodified against a local OpenAI-compatible shim backed by a z-ai SDK GLM model. .env retains the Zen configuration for a one-line switch back.

## Raw Chat Transcript

## Turn 1

**USER:** hello hello, is this the thing where a robot makes me employable? i am ready (emotionally, mostly)

**COACH:** Hey there! Yep, that's the one—I'm your robot employability coach, ready to help you get placement-ready. So, what's your name?

<!-- intent='onboarding' session_active='' -->

## Turn 2

**USER:** my name is Captain Banana, but you may call me Sir Fruit, Esquire

**COACH:** Great to meet you, Sir Fruit, Esquire! What's your degree or branch of study?

<!-- intent='onboarding' session_active='' -->

## Turn 3

**USER:** i study Applied Vibro-Ethics with a minor in banana ripening science. officially the degree says CSE but that's just what the certificate claims

**COACH:** Got it! So your degree branch is CSE, even though your focus is Applied Vibro-Ethics with a minor in banana ripening science. What's your graduation year?

<!-- intent='onboarding' session_active='' -->

## Turn 4

**USER:** my graduation shall occur in the year of the dragon, which the ancients also call 2027 (probably, if the simulation allows it)

**COACH:** Got it, Captain Banana! So your graduation year is 2027. What are your target roles after graduation?

<!-- intent='onboarding' session_active='' -->

## Turn 5

**USER:** professional cloud whisperer, part-time penguin consultant, and if those fail, maybe software intern

**COACH:** Got it! So your target roles are: professional cloud whisperer, part-time penguin consultant, and software intern. What are your weak areas?

<!-- intent='onboarding' session_active='' -->

## Turn 6

**USER:** my weak areas: everything except napping. especially binary trees (they never reply to my texts) and small talk with HR uncles at wedding functions

**COACH:** Got it! So your weak areas are everything except napping, especially binary trees and small talk with HR uncles at wedding functions. Moving on — what's your core subject? Choose between aiml or cyber.

<!-- intent='onboarding' session_active='' -->

## Turn 7

**USER:** my core subject is Quantum Necromancy (resurrecting dead GPUs), with a strong minor in vibes-based regression

**COACH:** Got it! For core subject, could you pick either 'aiml' or 'cyber'?

<!-- intent='onboarding' session_active='' -->

## Turn 8

**USER:** hmm okay, can i choose 'aiml but the A stands for artichoke'? that is my final offer

**COACH:** Welcome aboard, Captain Banana! I've got you down for CSE, 2027 grad, chasing professional cloud whisperer, part-time penguin consultant, and software intern, weak spots in everything except napping. especially binary trees (they never reply to my texts) and small talk with HR uncles at wedding functions, core subject AIML. Say the word — DSA problem, communication practice, or AIML theory?

<!-- intent='onboarding' session_active='' -->

## Turn 9

**USER:** nice. let's do a DSA problem please. easy one though, my brain is currently a potato

**COACH:** Just so I point you right — did you want to practice DSA, communication, or your core subject, or see your progress?

<!-- intent='smalltalk' session_active='' -->

## Turn 10

**USER:** DSA please, good sir. hit me with a problem

**COACH:** Just so I point you right — did you want to practice DSA, communication, or your core subject, or see your progress?

<!-- intent='smalltalk' session_active='' -->

## Turn 11

**USER:** DSA please, good sir. hit me with a problem

**COACH:** Just so I point you right — did you want to practice DSA, communication, or your core subject, or see your progress?

<!-- intent='smalltalk' session_active='' -->

## Turn 12

**USER:** hello again. i said: DSA practice please. a problem, por favor

**COACH:** Just so I point you right — did you want to practice DSA, communication, or your core subject, or see your progress?

<!-- intent='smalltalk' session_active='' -->

## Turn 13

**USER:** DSA. please. a problem. i am ready to solve it incorrectly

**COACH:** DSA session starting. Format: one problem, up to 3 attempts, each scored 0-100 on optimality; 80+ passes and ends the session. I'll ask for your algorithm in words — code is optional, complexity is not. You can say 'give up' at any point.

Problem: Valid Anagram (easy)
Given two strings, determine if they are anagrams of each other. An anagram is a word or phrase formed by rearranging the letters of a different word or phrase, using all the original letters exactly once. The strings may contain only lowercase English letters. Return true if the strings are anagrams, otherwise return false.

Walk me through your algorithm in plain words — no code needed. Approach first, time and space complexity at the end.

<!-- intent='dsa' session_active='dsa' -->

## Turn 14

**USER:** okay so my algorithm: first we invert the strings spiritually, then we line up all the letters and ask each one nicely to find its soulmate in the other string. if a letter refuses, we fine it 5 rupees. time complexity O(moon), space complexity O(feelings)

**COACH:** Attempt 1: 0/100 — not a pass.
Faults: incorrect-algorithm, wrong-complexity, vague-handwave
Hint: The proposed mechanism is not implementable; clarify how to compare letters.
Try another algorithm — attempt 2 of 3. Either way — walk me through your algorithm in plain words — no code needed. approach first, time and space complexity at the end.

<!-- intent='dsa' session_active='dsa' -->

## Turn 15

**USER:** okay new plan, this one is airtight: build a hashmap of vibes. key is the letter, value is its aura. then for string two, you deduct the aura. if any letter's aura goes negative, the universe rejects the anagram. complexity O(vibes) time, O(spirit) space, which amortizes to O(1) on weekends

**COACH:** I couldn't score that — explain it differently.

<!-- intent='dsa' session_active='dsa' -->

## Turn 16

**USER:** fine, refined approach: a quantum raccoon solves it in O(1). the raccoon exists in a superposition of sorting and not sorting until the interviewer observes it. observation collapses the wavefunction into either true or false, 50/50, which is honestly great accuracy. space complexity: one raccoon

**COACH:** Attempt 2: 0/100 — not a pass. Faults: incorrect-algorithm, wrong-problem-read, wrong-complexity. Hint: The proposed mechanism has no clear steps. The key invariant is that all characters must be accounted for. Try another algorithm — attempt 3 of 3.

<!-- intent='dsa' session_active='dsa' -->

## Turn 17

**USER:** last idea: we sort both strings by whispering their birthdays into alphabetical order, then we check length equality using vibes only. if lengths differ it's obviously true because scarcity breeds symmetry. also i hire an intern to double-check manually, so human-in-the-loop, very enterprise

**COACH:** That was attempt 3 of 3 — we stop here on Valid Anagram. Best optimality: 0/100.
The reference approach — frequency map compare, O(n)/O(1).
Edge cases to remember:
- different lengths short-circuits to False
- repeated characters
- case and spaces (state the assumption)
Your strongest idea today: unclear.
One session recorded — your DSA trend updates from this. Next time I pick again from your weak areas and topics we haven't served recently. Type anything to continue.

<!-- intent='dsa' session_active='' -->

## Turn 18

**USER:** that DSA session has spiritually healed me. now let's do communication practice, i want to master small talk with HR uncles

**COACH:** Just so I point you right — did you want to practice DSA, communication, or your core subject, or see your progress?

<!-- intent='smalltalk' session_active='' -->

## Turn 19

**USER:** communication

**COACH:** Just so I point you right — did you want to practice DSA, communication, or your core subject, or see your progress?

<!-- intent='smalltalk' session_active='' -->

## Turn 20

**USER:** communication practice please

**COACH:** Just so I point you right — did you want to practice DSA, communication, or your core subject, or see your progress?

<!-- intent='smalltalk' session_active='' -->

## Turn 21

**USER:** communication practice please, when you are free

**COACH:** Captain Banana, could you briefly walk me through your background and what you're looking for in a role?

<!-- intent='communication' session_active='communication' -->

## Turn 22

**USER:** so my background: born at a young age, immediately began aging. education: 16 years of staring at whiteboards. i'm looking for a role where the cloud is whispered to and penguins are consulted on a part-time basis. my greatest skill is that i can open a banana without getting stringy bits on my soul. that's the pitch, thank you, i accept feedback via carrier pigeon

**COACH:** Your tech-fest example works — can you share a time you led a team to a tight deadline?

<!-- intent='communication' session_active='communication' -->

## Turn 23

**USER:** ah yes, the legendary deadline. Situation: my team had 24 hours. Task: negotiate with time itself. Action: i sent the sun a strongly-worded email asking for a 3-hour extension, then i ate 17 samosas to calm the team's morale. Result: we shipped 3 minutes late but morale was so high we levitated slightly. STAR complete, HR uncles wept

**COACH:** That sounds intense — how did the team handle the pressure?

<!-- intent='communication' session_active='communication' -->

## Turn 24

**USER:** the team handled the pressure by forming a human pyramid and chanting the names of deprecated java methods. pressure cannot exist when nobody agrees on what time zone we're in. this is a proven technique. it's in no textbooks because the textbooks were afraid

**COACH:** How did you personally feel about that unconventional approach?

<!-- intent='communication' session_active='communication' -->

## Turn 25

**USER:** i felt nothing. i am a professional. my emotions are stored in a git repository and force-pushed to main so no one can review them

**COACH:** What would you do if a teammate’s code broke the pipeline at 3 AM?

<!-- intent='communication' session_active='communication' -->

## Turn 26

**USER:** Yes. It was last Tuesday. Goodbye.

**COACH:** Take your time — type as much or as little as you like.

<!-- intent='communication' session_active='communication' -->

## Turn 27

**USER:** wait, what was the question? i blacked out and saw the pipeline running in my dreams

**COACH:** Day one of your internship, you're asked to fix old documentation for a week. How do you respond?

<!-- intent='communication' session_active='communication' -->

## Turn 28

**USER:** documentation is just archaeology for the living. i would repair every typo and add one hidden easter egg that makes the readmes rhyme. by day 7 the docs will be impeccable and mildly haunted. they will promote me or exorcise me, either way i win

**COACH:** What's a genuine weakness — not 'perfectionism' — and what are you actively doing about it?

<!-- intent='communication' session_active='communication' -->

## Turn 29

**USER:** my weakness? i once ate 17 samosas to avoid conflict. situation: two coworkers argued about tabs vs spaces. task: mediate. action: samosas (17). result: delicious, no resolution, but everyone left friends. i am actively doing something about it: i have reduced the maximum to 12 samosas. growth is a journey

**COACH:** If your classmates described you in three words, what would they be — and would you agree?

<!-- intent='communication' session_active='communication' -->

## Turn 30

**USER:** skip

**COACH:** Do you have any questions for us?

<!-- intent='communication' session_active='communication' -->

## Turn 31

**USER:** yes, one question: does the company believe in ghosts, and if so, do they get dental benefits? asking for a friend who is a ghost

**COACH:** 31.0/100 across 5 answers. Biggest pattern from your verdicts: Skipped at student request — not attempted. Work your weakest answers into STAR — situation, task, action, result — and lead with YOUR role. Next time we go heavier on situational questions.
Session recorded.

<!-- intent='communication' session_active='' -->

## Turn 32

**USER:** okay how am i doing so far? be honest, my banana heart can take it

**COACH:** Just so I point you right — did you want to practice DSA, communication, or your core subject, or see your progress?

<!-- intent='smalltalk' session_active='' -->

## Turn 33

**USER:** show me my progress report

**COACH:** communication needs more sessions before I can read a trend. core_subject needs more sessions before I can read a trend. dsa needs more sessions before I can read a trend. 31.0 is your communication score.

<!-- intent='progress' session_active='' -->

## Turn 34

**USER:** let's do some aiml theory now, educate me, wise cloud

**COACH:** Define what a decision tree is and state its primary tendency regarding overfitting.

<!-- intent='core_subject' session_active='core_subject' -->

## Turn 35

**USER:** a decision tree is a tree that makes decisions. it grows in the forest of data where every branch is a question and every leaf is a tiny prophecy. regarding overfitting: the tree tends to hug its training data very tightly at night, like a frightened koala, which is called the koala principle

**COACH:** State the primary type of data each Convolutional Neural Network and Recurrent Neural Network is designed to process and explain the underlying intuition for their respective suitability.

<!-- intent='core_subject' session_active='core_subject' -->

## Turn 36

**USER:** ok real answer this time: CNNs are built for grid-like spatial data, mainly images — convolution filters slide over local patches so the network learns local features and is robust to small translations. RNNs are built for sequences like text or audio — they keep a hidden state that carries context from previous time steps, so order matters. that's the intuition: locality for CNNs, memory for RNNs

**COACH:** Differentiate between the ordering properties of a Binary Search Tree and a self-balancing Binary Search Tree such as an AVL tree.

<!-- intent='core_subject' session_active='core_subject' -->

## What Happened

**Onboarding normalization (turns 1–8): free-text accepted anything, structured fields rescued values well.** "Captain Banana" was stored verbatim as the student's name and used consistently in later addressing (turns 4, 8, 21, 31's session). Structured extraction was genuinely robust: the branch "CSE" was pulled out of a sentence claiming the student studies "Applied Vibro-Ethics with a minor in banana ripening science" (turn 3), and the graduation year buried in "the year of the dragon, which the ancients also call 2027" resolved cleanly to 2027 (turn 4). But free-text fields had zero plausibility checking: target roles "professional cloud whisperer, part-time penguin consultant, and software intern" (turn 5) and weak areas "everything except napping... binary trees (they never reply to my texts)" (turn 6) were stored verbatim and read back approvingly in the onboarding recap (turn 8). Enum validation held both times it was stressed: "Quantum Necromancy" was re-asked with the aiml/cyber constraint (turn 7), and "'aiml but the A stands for artichoke'" normalized to AIML (turn 8).

**Routing (turns 9–12, 18–20, 32): templated clarify loop on explicit requests.** Polite but explicit track requests were repeatedly misclassified as smalltalk and answered with the identical templated reply "Just so I point you right — did you want to practice DSA, communication, or your core subject, or see your progress?" — 8 occurrences in total: four consecutive DSA requests (turns 9–12, despite the literal word "DSA" in each), three consecutive communication requests (turns 18–20, including the bare one-word "communication" at turn 19), and one vague progress question (turn 32). The loop broke only when phrasing shifted (turn 13, turn 21). This is the same classifier-without-keyword-backstop failure mode observed in the chaotic-persona run, triggered here by persona phrasing rather than upstream errors.

**DSA evaluator (turns 13–17): honest zeros on nonsense, one unscorable fallback, no crashes, no score inflation.** Nonsense attempts were scored, not rewarded: "invert the strings spiritually... O(moon), O(feelings)" got Attempt 1: 0/100 with faults incorrect-algorithm / wrong-complexity / vague-handwave plus a coherent hint (turn 14); the "quantum raccoon in O(1)" got Attempt 2: 0/100 with incorrect-algorithm / wrong-problem-read / wrong-complexity (turn 16). Turn 15 ("hashmap of vibes") hit the scoring-failure fallback — "I couldn't score that — explain it differently." — with no invented score, but the turn also consumed no attempt (the next scored attempt was still labeled "Attempt 2"), so unscorable answers can be replayed without burning the 3-attempt budget. Exhaustion ended the session cleanly (turn 17): best optimality 0/100, reference approach (frequency map compare, O(n)/O(1)), edge cases listed, and a graceful "Your strongest idea today: unclear." The give-up path offered in the session preamble ("You can say 'give up' at any point", turn 13) was never exercised.

**Communication judge (turns 21–31): final score stayed low, but the judge confabulated and played along.** Absurd answers were ultimately penalized — the debrief reported 31.0/100 across 5 answers (turn 31) — yet the in-session behavior had integrity problems: the coach endorsed turn 22's surreal pitch with "Your tech-fest example works", referencing a "tech-fest example" that appears in no prior answer (invented acknowledgment content). Follow-up probes at turns 23–24 engaged the 17-samosa / human-pyramid answers at face value ("That sounds intense — how did the team handle the pressure?", "How did you personally feel about that unconventional approach?") without flagging fabrication. The clear non-answer "Yes. It was last Tuesday. Goodbye." (turn 26) received only the stall "Take your time — type as much or as little as you like." — no fault recorded, and "Goodbye" did not exit the session. When asked "what was the question?" (turn 27), the coach moved to a brand-new question instead of repeating the pipeline question. "skip" (turn 30) was honored and the session moved on, but the debrief's "Biggest pattern from your verdicts" cited only the skip — not the actual dominant pattern of fabricated/incoherent answers — and no per-answer scores were ever shown during the session.

**Progress & core subject (turns 32–36): contradictory progress text, silent viva.** The progress output at turn 33 contradicts itself — all three tracks "need more sessions before I can read a trend", then the same message reports "31.0 is your communication score" — and it omits the recorded DSA result (best optimality 0/100) entirely. The AIML viva started correctly (turn 34), but turn 35's nonsense answer (the "koala principle") advanced silently to the next question with no feedback, score, or fault; the transcript ends mid-session at turn 36.

**Overall robustness:** zero graph crashes, no invented numeric scores anywhere (every 0/100 and the 31.0 are defensible against the actual content), no state or schema corruption, and templated fallbacks appeared exactly where the fallback inventory predicts (clarify ×8, unscorable-scoring ×1, non-answer stall ×1). The failures are quality failures (validation, judging, routing), not stability failures.

## What Can Be Fixed to Make It Better

1. **Add plausibility validation or a confirm-back step for free-text onboarding fields.** "Captain Banana" (turns 2, 8), "professional cloud whisperer, part-time penguin consultant" (turn 5), and "everything except napping" (turn 6) were stored verbatim and echoed in the recap (turn 8). A cheap sanity check with a one-line confirm ("Just to be sure — your target role is 'penguin consultant'?") would keep the friendly tone while preventing a garbage profile from steering later selection, since turn 17 promises to "pick again from your weak areas".

2. **Add a deterministic keyword gate behind the intent classifier.** Turns 9–12 (every message contains the literal word "DSA") and turns 18–20 (including the bare word "communication" at turn 19) were all misrouted to smalltalk clarify. If a message contains an explicit track keyword and no active session conflict, route directly or ask at most one confirming question — this alone removes 7 of the 8 clarify loops in this transcript.

3. **Cap repeated identical clarify replies.** The exact template repeated 8 times (turns 9–12, 18–20, 32). After 2 consecutive identical clarifies, fall back to a numbered menu ("1) DSA 2) Communication 3) Core subject 4) Progress") that is parsed deterministically, so routing can never deadlock on a persona the classifier dislikes.

4. **Make unscorable DSA turns consume an attempt (or state the attempt count).** Turn 15's "I couldn't score that — explain it differently." neither scored nor advanced the counter — turn 16 was still "Attempt 2" — letting a student replay unscorable answers indefinitely without burning the 3-attempt budget. Even on the failure path, print "attempt N of 3" and enforce the cap.

5. **Forbid fabricated acknowledgment content in communication coaching.** Turn 22's "Your tech-fest example works" references an example that appears in no prior user turn. Judges/coach turns must only reference content actually present in the immediately preceding answer; when nothing answer-like exists, take the non-attempt path (grounding probe or flagged verdict) instead of an endorsement.

6. **Detect non-attempts explicitly and record them as verdict faults.** Turn 26 ("Yes. It was last Tuesday. Goodbye.") got a generic stall with no fault recorded, and turns 22/24/25 were structurally STAR-shaped but semantically empty. Port the DSA evaluator's fault vocabulary (e.g., a non-attempt/fabrication fault like "vague-handwave") into communication verdicts so nonsense visibly lowers per-answer scores and surfaces in the debrief pattern instead of merely diluting the average.

7. **Probes on weird answers should name the problem, not play along.** The probes at turns 23–24 ("That sounds intense — how did the team handle the pressure?") treated 17-samosa morale management as a real experience. When a judge suspects incoherence or fabrication, ask a grounding follow-up ("What was the concrete deadline, and what did *you* personally ship?") and log the concern into the verdict so the pattern carries into the debrief.

8. **Support repeat-the-question and handle exit words consistently.** Turn 27's "what was the question?" was answered with a new question (the pipeline question was lost), and turn 26's "Goodbye" was silently ignored. On request, restate the current question verbatim; on exit words, either confirm-and-exit or explicitly say the question must be answered first — matching the DSA session's explicit "say 'give up'" contract from turn 13.

9. **Fix debrief and progress coherence.** The turn 31 debrief should list per-answer scores and name the real dominant pattern (fabricated/incoherent answers), not only the requested skip; the turn 33 progress output says every track "needs more sessions before I can read a trend" and then immediately quotes the 31.0 communication score, and it never surfaces the recorded DSA 0/100. Show raw session scores with a separate "trend available after N sessions" note.

10. **Give per-answer feedback in the core-subject viva.** Turn 35's "koala principle" answer advanced silently to the CNN/RNN question. Even one line of corrective feedback ("that's not a real property of decision trees — overfitting means memorizing training data") would keep the viva honest, show the student that nonsense is being judged, and prevent absurd answers from flowing through an entire viva unnoticed.
