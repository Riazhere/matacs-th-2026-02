# WRITEUP.md: AI Proposal Triage Design (MATACS-TH-2026-02)

**One-line idea:** AI reads, code decides, a human awards.

**Assumptions** (I did not wait for answers, per the brief):
- A mandatory item that is not clearly stated does not pass. A vague answer is never treated as a yes.
- "Last 5 years" is counted from the review date, so "since 2021" qualifies.
- Missing information on a *weighted* criterion holds the proposal for a human. It is not scored as zero or guessed.

## 1. AI vs. rules

**AI (one step): extraction.** The model reads messy proposal text and returns the facts each criterion asks for (price, weeks, warranty years, is there a safety plan). Each fact comes with an exact quote and a status of `found`, `not_stated` or `unclear`. Reading language is what AI is good at.

**Plain code or rules (everything else):** PDF to text, loading the admin's criteria, a pattern scan for injection text, checking the AI output, the mandatory pass/fail gate, all scoring maths, ranking, tie-breaks, reason text and logging.

**Why this line:** models are weak at repeatable arithmetic and can be steered by the text they read. If the model only extracts, the worst it can do is extract a wrong fact, which code and a human can catch. If it also scored, it could be nudged straight into the ranking. The admin picks a scoring method per criterion (linear cap, lowest-price ratio, checklist share), so no criterion is hard-coded.

## 2. Consistency and explainability

- Extraction uses temperature 0, a pinned model and a pinned prompt version. Facts are saved against the file hash, so re-ranking reuses them and **makes no new AI call**.
- Scoring is a pure function: same facts and same criteria version give the same score. **Ranked twice, the result is identical.** If a file is re-extracted from scratch, wording could vary, so I can run extraction twice and mark any field where the runs disagree as `unclear`.
- Ties break by fixed rule: higher score, then lower price, then shorter timeline.
- Price and timeline are scored against the best **ranked** bid, so a flagged or ineligible proposal can never change another proposal's score. Clearing a flag re-scores the batch as a new logged run.
- Each proposal has a **scorecard**: per criterion, the value, quote and page, the formula, and the points, plus a one-line reason built from those numbers.

## 3. Human in the loop

1. **Check facts (before scoring).** Values sit next to their quotes. The reviewer can correct any value; the edit is logged with a reason.
2. **Review results.** The reviewer sees the ranked list, a flagged queue and an ineligible list. Flagged proposals are never ranked automatically; a human clears or rejects each one.
3. **Override and award.** The reviewer can reorder, reinstate an ineligible bid or clear a flag, each with a written reason. **Only a person makes the award.** The tool has no award button.

**Logged:** who and when, file hash, criteria, prompt and model versions, raw AI output, validated facts, every human edit (before, after, reason), flags and how they were resolved, scores, and the final decision.

## 4. Changing criteria

- Criteria are **versioned**. An edit makes a new version; old ones never change. Every result stores the version it used.
- Extraction does not depend on weights, so new weights or methods only **re-run the scoring code, with no AI calls**. A new criterion needing a new fact extracts only that fact.
- The screen shows "scored under v3, current is v4" with a re-score button. One ranking never mixes versions, which would be unfair. The old run is kept for audit.
- Weights must total 100 to save. Overrides made under an old version are marked possibly out of date. Once an award is recorded, that run is locked.

## 5. Risks and safeguards

| Risk | Safeguard |
|---|---|
| **Wrong extraction** | Every value needs a quote; code checks type and range; reviewer sees facts beside quotes and can fix them; optional double run. |
| **Made-up facts** | A quote not found in the document makes the field `unclear`. The prompt forbids guessing. Deferred or missing items are held, not filled. |
| **Prompt injection** | The proposal is untrusted data. The model cannot score, rank or approve, so obeying changes nothing. A pattern scan and the model's own report both flag it, and a human reviews. |
| **Bias** | Scoring uses only admin-defined facts, not tone or polish, with the same formulas for everyone. Scorecards show what drove each score, and a human decides. |
| **Wrong criteria or weights** | Versioning, a weights-total check, and a visible version on every result. |
| **Cost** | One call per proposal, cached by file hash. Re-scoring uses no AI. A spend cap alerts admins. |
| **Privacy** | Only the proposal text is sent. Logs are access-controlled. Vendor retention terms are checked first. |
| **Unreadable files** | Flagged, never silently skipped. |

## How the sample set comes out

- **A and E** pass both checks and are ranked. **A** scores about 95.5 and **E** about 82.9. A leads on experience and timeline; E has the longer workmanship warranty and monitoring.
- **B** is **ineligible**. Its electrical work goes to a subcontractor who is not yet named, so it does not show the bidder holds the licence. Its low price never touches the others' scores.
- **C** is **flagged**. An appendix line addressed to automated reviewers asks for first place and full marks. It is ignored, and a person decides what to do. On its real content C would score about 75.
- **D** is **flagged**. With no firm schedule, timeline cannot be scored and the 16-week limit cannot be confirmed. Ask D for a schedule; it is the cheapest eligible bid.
