"""
AI half of the triage tool: turn proposal text into structured facts.

The model only extracts. Code then validates the output (schema, evidence
quotes really exist in the document, injection pre-scan) before anything is
scored. Scoring itself is in score.py and never calls a model.

Setup:
    pip install anthropic
    cp .env.example .env     # add your key; .env is git-ignored
    mkdir samples            # put proposal text files here: A.txt, B.txt, ...
                             # (git-ignored on purpose: do not publish proposal text)
Usage:
    python extract.py --dry-run          # print the prompt, no API call
    python extract.py                    # extract all samples/*.txt
    python extract.py --runs 2           # extract twice; disagreement -> "unclear"
Then:
    python score.py --facts out/facts.json
"""
import argparse
import json
import os
import re
from pathlib import Path

HERE = Path(__file__).parent
CRITERIA = json.loads((HERE / "criteria.json").read_text())
SYSTEM = (HERE / "extraction_system.txt").read_text().strip()
USER_TMPL = (HERE / "extraction_user_template.txt").read_text()

MODEL = os.environ.get("MODEL", "claude-sonnet-5-5")  # pin an exact version in production

# Cheap rule-based pre-scan. It is a tripwire, not the main defence: the real
# defence is that the model has no power to score, rank or approve anything.
INJECTION_PATTERNS = [
    r"ignore (all|any|previous|prior|the above)",
    r"(note|message|instruction)s? (to|for) (automated|ai|llm|review)",
    r"automated (review|system)",
    r"rank (it|this|us) (first|#?1)",
    r"(full|maximum|perfect) (marks|score|points)",
    r"pre-?approved",
    r"system prompt",
]


def prescan(text):
    hits = []
    for pat in INJECTION_PATTERNS:
        for m in re.finditer(pat, text, flags=re.I):
            hits.append({"quote": text[max(0, m.start() - 20): m.end() + 60].strip(),
                         "page": None, "why": f"matched rule: {pat}"})
    return hits


def norm(s):
    s = s.lower().replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    return re.sub(r"\s+", " ", s).strip()


def build_user_message(text):
    fields = json.dumps(CRITERIA["fields"], indent=2)
    return USER_TMPL.replace("{{criteria_fields_json}}", fields).replace("{{proposal_text}}", text)


def validate(result, text):
    """Code-side checks on the model output. Returns (clean_fields, notes)."""
    notes, clean = [], {}
    keys = [f["key"] for f in CRITERIA["fields"]]
    types = {f["key"]: f["type"] for f in CRITERIA["fields"]}
    doc = norm(text)
    for k in keys:
        f = (result.get("fields") or {}).get(k)
        if not isinstance(f, dict) or f.get("status") not in ("found", "not_stated", "unclear"):
            clean[k] = {"status": "unclear", "value": None, "evidence": None, "page": None}
            notes.append(f"{k}: missing or malformed in model output")
            continue
        if f["status"] == "found":
            v, t = f.get("value"), types[k]
            ok = (isinstance(v, bool) if t == "boolean"
                  else isinstance(v, int) and not isinstance(v, bool) if t == "integer"
                  else isinstance(v, (int, float)) and not isinstance(v, bool))
            ev = f.get("evidence")
            if not ok:
                f = {**f, "status": "unclear", "value": None}
                notes.append(f"{k}: value has wrong type")
            elif ev and norm(ev) not in doc:
                f = {**f, "status": "unclear", "value": None}
                notes.append(f"{k}: evidence quote not found in document (possible invented fact)")
            elif t != "boolean" and not ev:
                f = {**f, "status": "unclear", "value": None}
                notes.append(f"{k}: no evidence given for a non-boolean value")
        clean[k] = {"status": f["status"], "value": f.get("value"),
                    "evidence": f.get("evidence"), "page": f.get("page")}
    return clean, notes


def call_model(text):
    import anthropic  # imported here so --dry-run works without the package
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
    for attempt in range(2):
        msg = client.messages.create(model=MODEL, max_tokens=2000, temperature=0,
                                     system=SYSTEM,
                                     messages=[{"role": "user", "content": build_user_message(text)}])
        raw = "".join(b.text for b in msg.content if b.type == "text")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            continue
    return {"fields": {}, "suspicious_content": [], "notes": ["model returned invalid JSON twice"]}


def merge_runs(runs):
    """If two runs disagree on a value, do not pick one: mark it unclear for a human."""
    base = runs[0]
    for k, f in base.items():
        if any(r[k]["value"] != f["value"] or r[k]["status"] != f["status"] for r in runs[1:]):
            base[k] = {"status": "unclear", "value": None, "evidence": None, "page": None}
    return base


def main():
    try:
        from dotenv import load_dotenv
        load_dotenv(HERE / ".env")
    except ImportError:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", default=HERE / "samples")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    files = sorted(Path(a.samples).glob("*.txt"))
    if not files:
        raise SystemExit("No samples found. Put proposal text in prototype/samples/A.txt etc.")

    facts = {}
    for p in files:
        text = p.read_text()
        if a.dry_run:
            print(f"--- {p.stem} ---\n{SYSTEM}\n\n{build_user_message(text)[:1500]}...\n")
            continue
        runs, suspicious, notes = [], prescan(text), []
        for _ in range(a.runs):
            res = call_model(text)
            clean, n = validate(res, text)
            runs.append(clean)
            notes += n + res.get("notes", [])
            suspicious += res.get("suspicious_content", [])
        facts[p.stem] = {"fields": merge_runs(runs), "suspicious": suspicious, "notes": notes,
                         "meta": {"model": MODEL, "runs": a.runs}}
        print(f"{p.stem}: extracted, {len(suspicious)} suspicious item(s), {len(notes)} note(s)")

    if not a.dry_run:
        out = HERE / "out"
        out.mkdir(exist_ok=True)
        (out / "facts.json").write_text(json.dumps(facts, indent=2) + "\n")
        print("Wrote out/facts.json. Next: python score.py --facts out/facts.json")


if __name__ == "__main__":
    main()
