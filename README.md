# MATACS-TH-2026-02: AI Proposal Triage Design

- **Name:** Riaz Ijaz
- **Reference:** MATACS-TH-2026-02
- **Role:** Associate Software Developer
- **Time actually spent:** `<< FILL IN: your real hours, e.g. "about 2 hours, plus 30 minutes reviewing and editing" >>`

## In one paragraph

AI is used for one job only: reading each proposal and extracting facts with exact quotes. Everything else (checking the AI output, mandatory pass/fail checks, scoring, ranking, reasons) is plain code driven by admin-defined, versioned criteria. Suspicious or incomplete proposals are held for a person, and a person makes the final award. For the sample set: **A** ranks 1st, **E** ranks 2nd, **B** is ineligible, and **C** and **D** are flagged for human review.

## Files

| File | What it is |
|---|---|
| [WRITEUP.md](WRITEUP.md) | Answers to the five questions |
| [diagram/process-flow.png](diagram/process-flow.png) | Process flow from upload to ranked output, with AI steps, rule steps and human checkpoints |
| [PROMPTS.md](PROMPTS.md) | The extraction prompt, exactly as sent |
| [ranking.json](ranking.json) | Expected ranking of proposals A to E |
| [prototype/](prototype/) | Optional script (see below) |

## Prototype (optional)

- `prototype/score.py` is the deterministic half. It reads the criteria and extracted facts and produces the ranking and scorecards. It needs no API key. Run it with `python prototype/score.py`. It is how the numbers in `ranking.json` were produced.
- `prototype/extract.py` is the AI half. It builds the prompt from the criteria, calls the model, and checks the output (schema, quotes found in the document, injection pre-scan). It needs a key: copy `.env.example` to `.env` and add yours. **I could not run the live API call during preparation**, so this part is tested only offline (prompt building, validation and pre-scan). It is untested against a live model.
- `prototype/sample_facts.json` is a hand-made stand-in for the extraction output, with evidence paraphrased. Per the brief, no proposal text is in this repository. To try the live extraction, put your own copies of the proposal text in `prototype/samples/` (git-ignored).

## How I used AI tools

`<< FILL IN honestly, 2-3 sentences. Say which tool(s) you used and for what. Example shape: "I used Claude to draft the structure of the design, the extraction prompt, the scoring script and the write-up. I reviewed all of it and ran the scoring script myself." >>`

**One place where I disagreed with or corrected the AI:** The AI's first scoring script normalised price and timeline against the cheapest/fastest bid in the pool of every proposal that passed the mandatory gate, including proposals that were flagged and would not be ranked. I disagreed with this: a proposal held out of the ranking should not change the scores of the ones that are ranked.

The sample set shows the problem. D has the lowest eligible price but is flagged for having no firm schedule, so it set the price baseline. That pushed A's price score down to 97.06 instead of 100, and A's total to 94.76 instead of 95.50 (E moved from 82.88 to 82.16). The rank order did not change, but the scores depended on a proposal nobody had ranked. That weakens the "same inputs, same result" and explainability claims, and it could flip a close ranking in a different data set.

I changed `score.py` to a two-pass approach: pass 1 finds which proposals will be ranked (passed the gate, no open flag), and the baseline is then built from those only. Flagged proposals still get a provisional score against the same baseline, capped at 100 on price and timeline. I tested it by removing C, D and B and by making flagged C absurdly cheap: A and E's scores did not move. The trade-off is that clearing a flag changes the pool, so the batch is re-scored and logged as a new run under the same criteria version. That is cheap (no AI calls) and the audit log shows why the numbers moved.

## Assumptions

Listed at the top of [WRITEUP.md](WRITEUP.md). I did not email questions; I stated assumptions and moved on, as the brief allows.
