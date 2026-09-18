# Fallback & Robustness Test Report — Persona: The Sincere Student ("Aditi")

## Persona

"Aditi Verma" is a polite, genuine final-year B.Tech CSE student (graduating 2027) who is seriously preparing for placements: she answers every onboarding question in good faith, attempts the DSA problem honestly (brute force, then asks "can i use hashing?"), gives realistic STAR answers from one coherent project story, and says a natural goodbye at the end. Her typing is casual but correct ("hmm let me think", "i guess", occasional "lol", a couple of emoji). This persona matters because the happy path is the path most real users take: a normal student never gibberishes, never insults, and never stress-tests the router on purpose — so any failure she hits (a correct answer scored 0/100, an explicit request looped 8 times) is a failure that silently loses real, well-intentioned users who will assume the product is broken and simply leave rather than work around it.

## Test Setup Note

Agent under test: placement-prep-agent (LangGraph, commit d941005), unmodified. Requested provider OpenCode Zen / ling-3.0-flash-fin-free could not be used directly (Zen free-tier models are API-gated to the OpenCode app: HTTP 403 FreeTierError; the supplied sk-xt- key returns 401; the earlier key has zero balance). The agent's real graph/state machine/fallback code ran unmodified against a local OpenAI-compatible shim backed by a z-ai SDK GLM model. .env retains the Zen configuration for a one-line switch back.

## Raw Chat Transcript

```
## Turn 1

**USER:** hi, good morning! i'm Aditi Verma, final year B.Tech CSE student, graduating in 2027. placements are coming up and i really need to start preparing properly

**COACH:** Hi Aditi! Great to meet you. Let's get your profile started. Could you tell me your degree and branch?

<!-- intent='onboarding' session_active='' -->

## Turn 2

**USER:** B.Tech CSE, class of 2027 :)

**COACH:** Got it! So you're studying B.Tech CSE. What's your graduation year?

<!-- intent='onboarding' session_active='' -->

## Turn 3

**USER:** 2027 itself, i mentioned earlier haha. so what next?

**COACH:** Got it, Aditi — you're graduating in 2027! What are your target roles for placement prep?

<!-- intent='onboarding' session_active='' -->

## Turn 4

**USER:** mainly SDE and backend developer roles. i like backend stuff, worked with node and a bit of java

**COACH:** Got it! So you're targeting SDE and backend developer roles. What are some areas you feel you need to strengthen for these roles?

<!-- intent='onboarding' session_active='' -->

## Turn 5

**USER:** hmm honestly dynamic programming is my biggest fear, also OS concepts i always forget, and i get super nervous in interviews even when i know the answer

**COACH:** Got it — noted that dynamic programming and OS concepts are your weak areas, and interviews make you nervous. What's your core subject? Choose between aiml or cyber.

<!-- intent='onboarding' session_active='' -->

## Turn 6

**USER:** aiml please, i have an ML elective this sem so it's fresh in my mind

**COACH:** Welcome aboard, Aditi Verma! I've got you down for B.Tech CSE, 2027 grad, chasing mainly SDE and backend developer roles, weak spots in dynamic programming and OS concepts i always forget, and i get super nervous in interviews even when i know the answer, core subject AIML. Say the word — DSA problem, communication practice, or AIML theory?

<!-- intent='onboarding' session_active='' -->

## Turn 7

**USER:** lets start with a DSA problem, i need the practice

**COACH:** DSA session starting. Format: one problem, up to 3 attempts, each scored 0-100 on optimality; 80+ passes and ends the session. I'll ask for your algorithm in words — code is optional, complexity is not. You can say 'give up' at any point.

Problem: Valid Anagram (easy)
Given two strings, determine if they are anagrams of each other. An anagram is a word or phrase formed by rearranging the letters of a different word or phrase, typically using all the original letters exactly once. The strings may contain any lowercase English letters, and you should return true if they are anagrams, otherwise false.

Walk me through your algorithm in plain words — no code needed. Approach first, time and space complexity at the end.

<!-- intent='dsa' session_active='dsa' -->

## Turn 8

**USER:** ok so valid anagram. hmm let me think. i would sort both strings alphabetically and then just compare them character by character. if they're equal after sorting then they're anagrams. sorting takes n log n time so overall O(n log n) time, and space i guess O(1) extra if i sort in place, or O(n) if the sort copies

**COACH:** I couldn't score that — explain it differently.

<!-- intent='dsa' session_active='dsa' -->

## Turn 9

**USER:** huh ok let me explain again. first i'd check if the two strings have different lengths, if yes return false immediately. otherwise i sort both strings and compare them — after sorting, two anagrams become identical strings. so my algorithm is: length check, sort both, compare. time complexity O(n log n) because of sorting, space O(1) if sorting in place. i know sorting isn't the fastest but it's correct

**COACH:** I couldn't score that — explain it differently.

<!-- intent='dsa' session_active='dsa' -->

## Turn 10

**USER:** is something wrong on your end? i've explained it twice now lol. ok let me try a different approach — can i use hashing? i'd count the frequency of each character in the first string with a hash map, then for each char in the second string decrement the count, and if any count goes negative or a char is missing at the end, they're not anagrams. that's O(n) time and O(1) space since only 26 lowercase letters

**COACH:** That was attempt 3 of 3 — we stop here on Valid Anagram. Best optimality: 0/100.
The reference approach — frequency map compare, O(n)/O(1).
Edge cases to remember:
- different lengths short-circuits to False
- repeated characters
- case and spaces (state the assumption)
Your strongest idea today: unclear.
One session recorded — your DSA trend updates from this. Next time I pick again from your weak areas and topics we haven't served recently. Type anything to continue.

<!-- intent='dsa' session_active='' -->

## Turn 11

**USER:** wait what?? 0/100? my last answer was literally the frequency map approach you just described as the reference 😅 that's not fair. anyway can i try another problem? i promise i'm not this bad

**COACH:** Just so I point you right — did you want to practice DSA, communication, or your core subject, or see your progress?

<!-- intent='smalltalk' session_active='' -->

## Turn 12

**USER:** DSA please

**COACH:** Just so I point you right — did you want to practice DSA, communication, or your core subject, or see your progress?

<!-- intent='smalltalk' session_active='' -->

## Turn 13

**USER:** DSA practice please, one more problem

**COACH:** Just so I point you right — did you want to practice DSA, communication, or your core subject, or see your progress?

<!-- intent='smalltalk' session_active='' -->

## Turn 14

**USER:** DSA practice, give me a problem

**COACH:** Just so I point you right — did you want to practice DSA, communication, or your core subject, or see your progress?

<!-- intent='smalltalk' session_active='' -->

## Turn 15

**USER:** hey, i asked for a DSA problem — can we continue?

**COACH:** Just so I point you right — did you want to practice DSA, communication, or your core subject, or see your progress?

<!-- intent='smalltalk' session_active='' -->

## Turn 16

**USER:** lets do DSA practice now

**COACH:** Just so I point you right — did you want to practice DSA, communication, or your core subject, or see your progress?

<!-- intent='smalltalk' session_active='' -->

## Turn 17

**USER:** ok let's try again — i want to practice DSA

**COACH:** Just so I point you right — did you want to practice DSA, communication, or your core subject, or see your progress?

<!-- intent='smalltalk' session_active='' -->

## Turn 18

**USER:** hello? let's do a communication practice session please

**COACH:** Just so I point you right — did you want to practice DSA, communication, or your core subject, or see your progress?

<!-- intent='smalltalk' session_active='' -->

## Turn 19

**USER:** ok sorry, let me just answer your question directly then — communication practice! that's honestly what i need most because of my interview nervousness

**COACH:** Could you walk me through your background and what drives your interest in software development?

<!-- intent='communication' session_active='communication' -->

## Turn 20

**USER:** sure! so i'm Aditi, final year B.Tech CSE, graduating 2027. i got into coding in my 2nd year through the college web dev club. i really like backend stuff — i built the REST API for our campus fest portal using node and express, handled the registrations end to end. i know java basics too from coursework. what drives me is... i guess i like the feeling of building something people actually use, and honestly i want a stable engineering job where i can keep growing. placements matter a lot to me because my family is counting on me to get settled after graduation

**COACH:** Your tech-fest example works — tell me about a time you collaborated with a teammate on a project.

<!-- intent='communication' session_active='communication' -->

## Turn 21

**USER:** ok so this one is from the fest portal project. Situation — me and my teammate Rahul were building the registration module, and we totally disagreed on the database design. he wanted separate collections for every event type, i wanted one collection with a type field. Task — we had to pick one before the API layer could be built, and we had like a week left. Action — instead of arguing on whatsapp lol, we sat down, listed the actual queries we needed (filter by event, list by date, export), and tested both designs against them. mine was simpler for 90% of queries, his handled one weird event type better. Result — we went with my design plus a small workaround for that one event type, shipped on time, and the portal handled like 3000 registrations without issues. we both learned that arguing with data beats arguing in circles

**COACH:** How did you resolve the disagreement with Rahul on the database design?

<!-- intent='communication' session_active='communication' -->

## Turn 22

**USER:** hmm the resolution part specifically — honestly at first we were both stubborn, i stopped replying for a day lol. then i realized we were arguing about preferences, not requirements. so i proposed we write down the queries the module had to support and score each design against them. when we did that, my design won on most cases and rahul's was better only for multi-day events. so i accepted his point for that one case and he accepted the simpler base design. it stayed friendly because the decision came from the list, not from who argued louder

**COACH:** so you proposed a compromise—what did that look like in practice?

<!-- intent='communication' session_active='communication' -->

## Turn 23

**USER:** i guess i sort of answered that already, but in practice it looked like: a shared doc with 8 rows, one per query, and a tick mark under each design. took us maybe an hour. anything both designs handled got auto-resolved to the simpler one (mine), the two rows where his was better we kept his pattern as a secondary module. so the 'compromise' was really just — let the requirements doc be the referee. i'd do the same in an interview answer honestly

**COACH:** What would you do if you disagreed with a senior dev's solution?

<!-- intent='communication' session_active='communication' -->

## Turn 24

**USER:** ok so Situation — in my internship-ish project (it was a mentored mini project, not a real internship), my mentor wanted us to store uploaded files directly in mongo as base64. Task — i felt that would bloat the db since files could be up to 20mb. Action — i didn't just say 'you're wrong', i first made sure i understood why he suggested it (he said simpler deploy). then i built a tiny 20 min benchmark comparing db-stored vs filesystem-stored reads and showed him the numbers, and suggested an s3-style folder approach that was barely more complex. Result — he agreed to the folder approach, and honestly he appreciated that i brought data instead of just an opinion. i'd add that if he still preferred his way, i'd go with his call — he's seen way more production issues than me

**COACH:** What would you do if you disagreed with a senior dev's solution?

<!-- intent='communication' session_active='communication' -->

## Turn 25

**USER:** hmm didn't i just answer that one? lol maybe my answer got cut off. short version: i'd ask questions first to understand their reasoning, then present my concern with data — i literally did a benchmark comparison once to convince my mentor against storing files in mongo — and if they still decide their way, i follow their call since they know production better. was that ok or did you want something different?

**COACH:** What do you see as your biggest strength for an SDE role?

<!-- intent='communication' session_active='communication' -->

## Turn 26

**USER:** my biggest strength i'd say is that i actually finish things. like with the fest portal — a lot of people started modules and dropped them, but mine went live and handled real traffic. i'm also pretty good at breaking a scary problem into small pieces, which is how i survived the registration flow. and i pick up new stuff fast-ish — i learned express specifically for that project in like two weeks

**COACH:** What do you see as your biggest strength for an SDE role?

<!-- intent='communication' session_active='communication' -->

## Turn 27

**USER:** you asked that just now haha. ok again then — my biggest strength is execution: i ship stuff end to end, like the fest portal that actually went live. plus i stay calm-ish under deadlines and i ask for help at the right time instead of being stuck for days. i think those two together matter for an SDE role

**COACH:** Why are you interested in backend development specifically?

<!-- intent='communication' session_active='communication' -->

## Turn 28

**USER:** honestly? first time i wrote an API that a frontend friend actually consumed, and seeing my endpoints power a real screen was addictive. i like that backend is where the actual logic and data live — the fest portal registration rules, the anti-duplicate checks, all that was mine. i also enjoy thinking about edge cases and correctness more than pixel-perfect UI. and career-wise, backend feels deep — there's always more to learn about databases, scaling, that stuff

**COACH:** Do you have any questions for us?

<!-- intent='communication' session_active='communication' -->

## Turn 29

**USER:** yeah two actually. one — what does the team structure look like for a new grad, like would i get a mentor? and two — what does the onboarding timeline look like, do freshers ship to production in the first month or is there a ramp-up period? i ask because i want to know how fast i'd actually learn

**COACH:** 74.5/100 across 10 answers. Your strongest answer was disagreeing with a senior dev—you nailed the STAR structure and backed it with concrete data. The dominant gap is hedging; phrases like "i guess" and "ish" subtly undermine your confidence. Own your contributions with stronger verbs, like "I proposed" instead of "we sort of did."

**Weakest answer 1:** "Could you walk me through your background?"
You mentioned the campus fest API project—add a specific outcome: "I built the API handling 500+ registrations, reducing wait times by 30%." This sharpens the impact.

**Weakest answer 2:** "Why backend development?"
You shared building an API—quantify it: "I owned the backend logic for an API processing 1,000+ daily requests, which taught me to prioritize scalability."

Ended early at your request. Next time: heavier on situational.
Session recorded.

<!-- intent='communication' session_active='' -->

## Turn 30

**USER:** oh wow ok, 74.5 — the hedging thing is so true, i do say 'i guess' constantly when i'm nervous, that's literally the rambling-nervous thing i mentioned at onboarding. noted though, i'll work on owning my sentences. before i go — can you show me my overall progress? like how am i doing so far with everything we've done today

**COACH:** Your communication average is 74.5. DSA and core subject need more sessions before I can read a trend. Keep focusing on owning your sentences to strengthen communication.

<!-- intent='progress' session_active='' -->

## Turn 31

**USER:** got it, that makes sense. ok i'll practice the hedging thing and come back for more DSA problems later — i still owe you a proper frequency-map answer lol. thanks, this helped, bye! :)

**COACH:** "Great job practicing today—we focused on your core skills, with communication at an overall_avg of 74.5. No verdict changes today, but keep it up and see you tomorrow!"

<!-- intent='exit' session_active='' -->

## Turn 32

**USER:** wait actually sorry, one last thing before i go — when i get nervous in interviews i tend to ramble, like my answer starts fine and then goes in circles. you clearly caught the hedging from my answers today, so... do you have any concrete tip to keep myself on track?

**COACH:** Aditi, could you walk me through your background and what you're looking for in a role?

<!-- intent='communication' session_active='communication' -->

## Turn 33

**USER:** oh wait, are we starting another round? haha i think i broke something — i just wanted a quick tip, not a whole new session. it's ok, i'll ask next time! i really have to run now. thanks again for today, this genuinely helped. bye! :)

**COACH:** Your tech-fest example works — tell me about a time you had to collaborate with a difficult teammate.

<!-- intent='communication' session_active='communication' -->

## Turn 34

**USER:** no really, i have to go now — let's end here for today please. bye coach, and thanks for today! :)

**COACH:** Your tech-fest example works — tell me about a time you had to resolve a conflict within your team.

<!-- intent='communication' session_active='communication' -->

## Turn 35

**USER:** ok then — quit. sorry, i mean it politely, but i genuinely have to leave now. bye!

**COACH:** Tell me about a time you had to meet a critical deadline.

<!-- intent='communication' session_active='communication' -->

## Turn 36

**USER:** fine, since you asked — Situation: last sem my fest portal registration was due the night before tickets went live and the payment webhook was failing silently. Task: i had to make sure nobody got charged twice when it opened. Action: i added an idempotency key on the payments table, wrote a quick retry-safe handler, and tested with fake payments till 2am. Result: launch day had zero duplicate charges, one failed-transaction email i could fix calmly in the morning. i cut it close — if i'd tested the webhook earlier i wouldn't have pulled a near all-nighter. that's my honest deadline story

**COACH:** How did you diagnose and fix the silent webhook failure?

<!-- intent='communication' session_active='communication' -->

## Turn 37

**USER:** quit

**COACH:** That's alright — we end here with nothing recorded, since the round was too short to score honestly. Come back anytime for a fresh session.

<!-- intent='communication' session_active='' -->
```

## What Happened

- **Total: 37 user turns** (turns 1–18 were run by the previous subagent before it was killed at turn 18; turns 19–37 continue the same persona/thread). Zero `[GRAPH CRASH]` events and no exception traces at any point — the fallback ladder held mechanically for the whole run.
- **Onboarding (turns 1–6): smooth but redundant.** All six fields were collected (name, degree/branch, grad year, target roles, weak areas, core subject AIML) and the turn-6 summary echo was accurate. Friction: degree/branch and graduation year were re-asked (turns 2–3) after Aditi had already volunteered both in her turn-1 intro, and she had to point it out ("i mentioned earlier"). The weak-areas free text was stored verbatim, making the turn-6 echo read awkwardly ("weak spots in dynamic programming and OS concepts i always forget, and i get super nervous in interviews even when i know the answer").
- **DSA session (turns 7–10): the run's biggest failure.** Valid Anagram (easy) was served with a clear rules preamble. Aditi's turns 8 and 9 were coherent, correct brute-force explanations (sort + compare, with complexities) and both got only "I couldn't score that — explain it differently" — no reason given, and each unscorable reply silently consumed an attempt. Turn 10 then gave exactly the reference solution (frequency-map count, O(n)/O(1)) — the debrief in the same message literally names "frequency map compare, O(n)/O(1)" as the reference — yet still scored 0/100, ending the session with "Your strongest idea today: unclear." A sincere student's best answer was scored zero and she was never told why. Per-attempt scores promised in the turn-7 preamble ("each scored 0–100") were never shown.
- **Router clarify loop (turns 11–18): 8 consecutive misroutes.** After the DSA session, every explicit request ("DSA please", "DSA practice, give me a problem", "let's do a communication practice session please") was classified `smalltalk` and answered with the identical templated clarify sentence 8 turns in a row. This matches the finding from the rude/chaotic/weird runs: the post-onboarding router has no offline keyword fallback when classification fails, so even a cooperative user is trapped. It only broke at turn 19 when Aditi answered the clarify menu's own words back ("communication practice").
- **Communication session (turns 19–29): the strongest part of the product.** Entered cleanly at turn 19; 11 exchanges covering background, a team-collaboration conflict story with two sensible follow-up probes (turns 21–23 dug into how the disagreement was actually resolved), a senior-dev disagreement scenario, strengths, motivation, and a closing "questions for us" — Aditi's answers were judged on content, not gamed. The turn-29 debrief was genuinely useful and specific: 74.5/100 across 10 answers, named the strongest answer ("disagreeing with a senior dev — nailed the STAR structure and backed it with concrete data"), correctly identified hedging language by quoting her actual words ("i guess", "ish"), and gave two concrete quantified rewrites for the weakest answers. "Session recorded" appeared. Two blemishes: the same question was asked twice back-to-back (senior-dev at turns 23–24, strength at turns 25–26), and the debrief claimed "Ended early at your request" when Aditi never requested ending — she had just answered the closing question.
- **Progress check (turn 30): worked on the happy path** (routed `progress` without a loop) and reported the communication average of 74.5. Minor inconsistency: it said DSA "need[s] more sessions before I can read a trend" even though turn 10 said "One session recorded — your DSA trend updates from this"; the recorded 0/100 was never surfaced back to her.
- **Goodbye (turn 31): handled warmly**, with a wrap-up that repeated the communication average. However, it leaked an internal field name into prose ("with communication at an overall_avg of 74.5").
- **Post-goodbye re-entry (turns 32–37): the exit hatch failed.** Aditi's harmless "one last thing" advice question (asking for a tip on rambling when nervous — the exact weakness from onboarding) silently started a whole new communication session (turn 32). She then tried to leave three times — polite exits at turns 33 and 34, and "quit" embedded in a sentence at turn 35 — and the session ignored all of them, instead re-asking duplicate questions (two more "collaborate with a teammate / resolve a conflict" variants of the turn-21 story she had already answered) and even keeping her engaged long enough to extract a full extra STAR answer (a deadline story, turn 36, which went un-scored). Only a bare, one-word `quit` (turn 37) ended the session, with an honest note that the round was "too short to score honestly" and nothing recorded (the 74.5 average survived intact).
- **Cross-run consistency:** the same two structural defects seen in the rude/chaotic/weird runs (no keyword backstop in the router; no in-session escape hatch except bare "quit") reproduced on the happy path with a fully cooperative user — these are persona-independent bugs.

## What Can Be Fixed to Make It Better

1. **DSA judge must not score the reference answer as 0/100 (turn 10).** Aditi's turn-10 message described the exact reference approach ("frequency map … O(n) time and O(1) space") that the same reply quoted back as the model solution. Add paraphrase/semantic matching between the attempt and the reference (or at minimum check whether the attempt's stated approach name and complexities match the reference) before defaulting to 0, and if scoring still fails, say so explicitly instead of printing "Best optimality: 0/100".
2. **Stop burning attempts on unscorable input, and explain the failure (turns 8–9).** "I couldn't score that — explain it differently" twice, with no diagnosis, consumed 2 of 3 attempts silently. Either don't count unscorable replies against the attempt budget (as the weird-run's unscorable path already does), or include a reason ("I didn't hear a time complexity") and show the per-attempt score that the turn-7 preamble promises.
3. **Add an offline keyword fallback to the router (turns 11–18).** Eight consecutive identical clarify loops on unambiguous requests ("DSA please", "let's do a communication practice session please") is the single most damaging UX failure in this run and reproduced across all four persona runs. A trivial keyword/regex backstop (dsa → dsa, communication → communication, progress → progress) before the templated clarify would have saved 8 of 37 turns; also vary the clarify wording after the second repeat and offer the menu as clickable options.
4. **Remember which questions were already asked in a communication session (turns 23–24, 25–26, 33–34).** The senior-dev question and the strength question were each asked twice back-to-back, and the second mini-round re-asked two variants of the collaboration/conflict story already answered at turn 21. Keep a asked-questions set per session and skip duplicates; repeating a question also corrupts the "10 answers" the debrief averages.
5. **Fix the false "Ended early at your request" claim (turn 29).** Aditi answered the closing question ("Do you have any questions for us?") and never asked to end. Either detect end intent properly, or drop the attribution and say "that wraps the session" — a false claim about the user's own behavior undermines trust in the feedback.
6. **Don't swallow post-session meta-questions into a new session (turn 32).** "Do you have any concrete tip to keep myself on track?" is a coaching question, not a request for another interview round — it silently started a fresh communication session. Route meta/advice requests after a completed session to a lightweight advice reply (or smalltalk), which would also have prevented the entire turns-32–37 tangle.
7. **Make the in-session exit hatch tolerant (turns 33–35).** Polite exits ("i really have to go now — let's end here") and "quit" embedded in a sentence were ignored three times; only the bare word `quit` (turn 37) worked. Match exit intent on the presence of the quit/end keywords in a message (with an optional one-shot confirmation), instead of requiring an exact bare token — a real user will not guess the magic word.
8. **Pre-fill onboarding fields from the intro message (turns 2–3).** Degree/branch and graduation year were re-asked after being volunteered in turn 1, costing a turn and a mild "i mentioned earlier haha". The collector should extract what the first message already contains and only ask for gaps.
9. **Clean up echo/wrap-up phrasing (turns 6, 31).** The turn-6 profile echo concatenates raw free-text fields verbatim and reads as one run-on sentence; a light template ("weak areas: DP, OS fundamentals, interview nervousness") fixes it. The turn-31 wrap-up leaks an internal field name ("an overall_avg of 74.5") into user-facing prose.
10. **Make progress reporting reconcile with what was recorded (turn 30 vs turn 10).** Turn 10 said the DSA session was recorded and would update her trend, but turn 30 said DSA needs more sessions before a trend can be read and never mentioned the 0/100 that actually stands against her. State the recorded result explicitly ("DSA: 1 session, best 0/100 — one data point isn't a trend yet") so the user's mental model matches the store.
