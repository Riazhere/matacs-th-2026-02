"""
Deterministic half of the triage tool: gates, scoring, ranking, scorecards.

Price and timeline are scored against the best RANKED proposal. Flagged or
ineligible proposals never change anyone else's score.

No AI is called here. Input is (a) the admin criteria and (b) the validated
facts that the extraction step produced. Same inputs -> same output, always.

Usage:
    python score.py                                  # uses sample_facts.json
    python score.py --facts out/facts.json --out ../ranking.json
"""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).parent


# --------------------------------------------------------------------------
# Scoring methods. The admin picks a method + parameters; code never hard-codes
# a criterion. Each returns a 0-100 score, or None if a needed fact is missing.
# --------------------------------------------------------------------------
def val(facts, key):
    f = facts["fields"].get(key)
    if not f or f["status"] != "found":
        return None
    return f["value"]


def linear_cap(s, facts, pool):
    v = val(facts, s["field"])
    return None if v is None else 100 * min(v, s["cap"]) / s["cap"]


def lowest_ratio(s, facts, pool):
    """Lowest value in the pool gets 100; others get lowest/value*100, capped at 100.
    The pool is the RANKED proposals only (see run()). A value above the admin
    limit (budget ceiling, 16 weeks) scores 0."""
    v = val(facts, s["field"])
    if v is None:
        return None
    if v > s["limit"]:
        return 0.0
    return min(100.0, 100 * min(pool[s["field"]]) / v)


def capped_sum(s, facts, pool):
    total = 0.0
    for p in s["parts"]:
        v = val(facts, p["field"])
        if v is None:
            return None
        total += p["share"] * min(v, p["cap"]) / p["cap"]
    return total


def checklist_share(s, facts, pool):
    vals = [val(facts, k) for k in s["fields"]]
    if any(v is None and facts["fields"].get(k, {}).get("status") == "unclear"
           for v, k in zip(vals, s["fields"])):
        return None
    return 100 * sum(1 for v in vals if v) / len(vals)


METHODS = {"linear_cap": linear_cap, "lowest_ratio": lowest_ratio,
           "capped_sum": capped_sum, "checklist_share": checklist_share}


# --------------------------------------------------------------------------
# Gates
# --------------------------------------------------------------------------
def mandatory_gate(criteria, facts):
    """Returns ('pass'|'fail'|'unclear', [notes])."""
    notes, unclear = [], False
    for m in criteria["mandatory"]:
        for key in m["all_of"]:
            f = facts["fields"].get(key, {"status": "not_stated", "value": None})
            if f["status"] == "found" and f["value"] is True:
                continue
            if f["status"] == "found" and f["value"] is False:
                return "fail", [f"{m['label']}: not met ({key})"]
            unclear = True
            notes.append(f"{m['label']}: could not be confirmed ({key})")
    return ("unclear" if unclear else "pass"), notes


def score_one(criteria, facts, pool):
    """Weighted scoring for one proposal. Returns (criteria_detail, total_or_None, missing_labels)."""
    detail, total, missing = {}, 0.0, []
    for c in criteria["weighted"]:
        s = c["scoring"]
        raw = METHODS[s["method"]](s, facts, pool)
        if raw is None:
            missing.append(c["label"])
            detail[c["id"]] = {"raw": None, "points": None, "weight": c["weight"]}
        else:
            pts = raw * c["weight"] / 100
            total += pts
            detail[c["id"]] = {"raw": round(raw, 2), "points": round(pts, 2), "weight": c["weight"]}
    return detail, (None if missing else round(total, 2)), missing


def build_pool(criteria, all_facts, member_ids):
    pool = {}
    for c in criteria["weighted"]:
        s = c["scoring"]
        if s["method"] == "lowest_ratio":
            vals = [val(all_facts[p], s["field"]) for p in member_ids]
            vals = [v for v in vals if v is not None and v <= s["limit"]]
            pool[s["field"]] = vals or [s["limit"]]
    return pool


def run(criteria, all_facts):
    weights = sum(c["weight"] for c in criteria["weighted"])
    assert weights == 100, f"Weights must add up to 100, got {weights}"

    gates = {p: mandatory_gate(criteria, f) for p, f in all_facts.items()}

    # PASS 1: find out which proposals will be ranked. Flags do not depend on the
    # price/timeline baseline, so a throw-away pool is enough here.
    stub = build_pool(criteria, all_facts, list(all_facts))
    flags = {}
    for p, facts in all_facts.items():
        gate, notes = gates[p]
        if gate == "fail":
            continue
        f = []
        if facts.get("suspicious"):
            f.append("instructions aimed at the AI/reviewer found in the document")
        if gate == "unclear":
            f.append("; ".join(notes))
        _, _, missing = score_one(criteria, facts, stub)
        if missing:
            f.append("missing information for: " + ", ".join(missing))
        flags[p] = f
    rankable = [p for p in all_facts if gates[p][0] == "pass" and not flags.get(p)]

    # The price/timeline baseline comes from RANKED proposals only, so a held
    # proposal can never change the score of a ranked one. If nothing is rankable
    # yet, fall back to everything that did not fail a mandatory check.
    members = rankable or [p for p in all_facts if gates[p][0] != "fail"]
    pool = build_pool(criteria, all_facts, members)

    # PASS 2: final scores. Held proposals get a provisional score against the same baseline.
    cards = {}
    for p, facts in all_facts.items():
        gate, notes = gates[p]
        card = {"proposal": p, "gate": gate, "notes": list(notes), "criteria": {}, "total": None}
        if gate == "fail":
            card["status"] = "ineligible"
        else:
            card["criteria"], card["total"], _ = score_one(criteria, facts, pool)
            card["flags"] = flags[p]
            card["status"] = "flagged" if flags[p] else "ranked"
        cards[p] = card
    return cards


def build_ranking(cards, all_facts):
    ranked = [c for c in cards.values() if c["status"] == "ranked"]
    # Tie-break: higher score, then lower price, then shorter timeline, then letter.
    ranked.sort(key=lambda c: (-c["total"],
                               val(all_facts[c["proposal"]], "total_price_cad") or 1e12,
                               val(all_facts[c["proposal"]], "completion_weeks") or 1e12,
                               c["proposal"]))
    out = []
    for i, c in enumerate(ranked, 1):
        best = max(c["criteria"].items(), key=lambda kv: kv[1]["points"] / kv[1]["weight"])
        weak = min(c["criteria"].items(), key=lambda kv: kv[1]["points"] / kv[1]["weight"])
        out.append({"proposal": c["proposal"], "rank": i, "status": "ranked", "score": c["total"],
                    "reason": f"Passed both mandatory checks; strongest on {best[0]}, weakest on {weak[0]}."})
    for c in cards.values():
        if c["status"] == "flagged":
            prov = f" (provisional merit score {c['total']} if the flag is cleared)" if c["total"] else ""
            out.append({"proposal": c["proposal"], "rank": None, "status": "flagged", "score": None,
                        "reason": "Held for human review: " + " | ".join(c["flags"]) + prov})
    for c in cards.values():
        if c["status"] == "ineligible":
            out.append({"proposal": c["proposal"], "rank": None, "status": "ineligible", "score": None,
                        "reason": "Failed mandatory check: " + "; ".join(c["notes"])})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--criteria", default=HERE / "criteria.json")
    ap.add_argument("--facts", default=HERE / "sample_facts.json")
    ap.add_argument("--out", default=HERE / "out" / "ranking.json")
    a = ap.parse_args()

    criteria = json.loads(Path(a.criteria).read_text())
    all_facts = {k: v for k, v in json.loads(Path(a.facts).read_text()).items() if not k.startswith("_")}

    cards = run(criteria, all_facts)
    ranking = build_ranking(cards, all_facts)

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(ranking, indent=2) + "\n")
    (out.parent / "scorecards.json").write_text(json.dumps(cards, indent=2) + "\n")

    print(f"criteria v{criteria['version']}")
    for r in ranking:
        print(f"{r['proposal']}  rank={r['rank']}  {r['status']:<10} score={r['score']}")
    print("\nPer-criterion points (weighted):")
    for p, c in sorted(cards.items()):
        pts = {k: v["points"] for k, v in c["criteria"].items()}
        print(f"  {p}: {pts}  total={c['total']}")


if __name__ == "__main__":
    main()
