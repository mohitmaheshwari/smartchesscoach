"""Score a coach's blind labels against ours, and say what the answer can bear.

Takes the filled `form_2_choices.csv` from a packet built by
`build_blind_label_packet.py`, plus that packet's answer key, and reports
whether a person who knows chess sees the same players we do.

WHAT IS SCORED, AND WHY IT IS NOT "AGREEMENT"
--------------------------------------------
The obvious number -- how often the coach's letter equals ours -- is the wrong
headline twice over.

First, most of our answers are "-": a trait inside the middle half of the
population says nothing, and we never render it. Scoring those would make the
system look accurate for saying nothing. So the primary measure covers only the
rows where we WOULD SHOW THE PLAYER A SENTENCE. That is the claim under test.

Second, agreement and disagreement are not the only outcomes. A coach who cannot
see a trait in eight games says "?", and that is not evidence against us. Every
spoken claim lands in one of three places:

    CONFIRMED     the coach picked the same end
    NOT SEEN      the coach said "-" or "?"
    CONTRADICTED  the coach picked the OTHER end

Only the third is evidence that we are wrong, and it is the number to watch. A
low confirmed rate with a high not-seen rate means the packet was too small; a
high contradicted rate means the trait is wrong.

THE CONTROLS, BOTH OF WHICH BOUND THE ANSWER
--------------------------------------------
1. THE REPEAT. One player appears twice. The coach's agreement with THEMSELVES
   is the ceiling on any agreement with us, and if it is poor no other number in
   this report can be read. It is printed first for that reason.

2. CHANCE, BY PERMUTATION. The coach's own labels are shuffled across players
   ten thousand times and the confirmed rate recomputed. This preserves their
   marginals -- a coach who answers "A" most of the time gets a high chance
   baseline, as they should -- and needs no assumption about what random
   answering looks like.

    python scripts/score_blind_labels.py --form FILLED.csv --key KEY.json
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import random
import sys
from pathlib import Path

SHUFFLES = 10000
SEED = 20260929

CONFIRMED, NOT_SEEN, CONTRADICTED = "CONFIRMED", "NOT SEEN", "CONTRADICTED"

# Not a behavioural trait: it is the decision about whether to coach tactics at
# all, and it is aggregated separately for that reason.
LAYER_COLUMN = "tactical_misses"

# What the coach may write. Anything else is a filling error, not an answer, and
# is reported rather than guessed at.
VALID_TRAIT = {"A", "B", "-", "?"}
VALID_LAYER = {"A", "B", "C", "-", "?"}


def read_form(path: Path):
    """Rows keyed by player label. Comment lines and blank rows are dropped."""
    lines = [ln for ln in path.read_text(encoding="utf-8-sig").splitlines()
             if ln.strip() and not ln.lstrip().startswith("#")]
    reader = csv.DictReader(lines)
    rows = {}
    for row in reader:
        label = (row.get("player") or "").strip()
        if label:
            rows[label] = {k: (v or "").strip().upper()
                           for k, v in row.items() if k}
    return rows


def outcome(ours: str, theirs: str) -> str:
    if theirs == ours:
        return CONFIRMED
    if theirs in ("-", "?", ""):
        return NOT_SEEN
    return CONTRADICTED


def repeat_control(form, repeat_pairs, columns):
    """The coach against themselves. Printed first: it bounds everything else."""
    print("=" * 68)
    print("CONTROL 1 -- THE COACH AGAINST THEMSELVES")
    print("=" * 68)
    if not repeat_pairs:
        print("No repeat pair in this packet. Every number below is unbounded:")
        print("we cannot tell a real agreement from a coach answering loosely.")
        return None
    agreed = total = 0
    for first, second in repeat_pairs:
        a, b = form.get(first), form.get(second)
        if not a or not b:
            print("Repeat pair %s/%s is not both filled in." % (first, second))
            continue
        print("\n  %s and %s are the same player." % (first, second))
        for column in columns:
            left, right = a.get(column, ""), b.get(column, "")
            same = left == right
            total += 1
            agreed += 1 if same else 0
            print("     %-24s %-2s %-2s   %s"
                  % (column, left or ".", right or ".", "" if same else "<- differs"))
    if not total:
        return None
    rate = agreed / total
    print("\n  self-agreement: %d of %d" % (agreed, total))
    if rate < 0.6:
        print("\n  THIS IS LOW. The coach describes the same eight games two")
        print("  different ways, so agreement with us cannot be interpreted")
        print("  either. Read nothing below as a verdict on the traits.")
    elif rate < 0.8:
        print("\n  Moderate. Treat everything below as indicative, and note that")
        print("  our agreement cannot exceed this ceiling by much.")
    else:
        print("\n  The coach is consistent with themselves. The numbers below")
        print("  can be read.")
    return rate


def score_spoken(form, key, columns):
    """The claims we would actually show a player, one trait at a time."""
    print("\n" + "=" * 68)
    print("THE CLAIMS WE WOULD SHOW A PLAYER")
    print("=" * 68)
    print("Only rows where we say something. A trait in the middle half is not")
    print("rendered, so scoring it would reward us for silence.\n")

    per_trait = collections.defaultdict(collections.Counter)
    contradictions = []
    for label, entry in key["entries"].items():
        answers = form.get(label)
        if not answers:
            continue
        for column in columns:
            ours = entry["ours"].get(column, "-")
            if ours in ("-", "?"):
                continue
            theirs = answers.get(column, "")
            result = outcome(ours, theirs)
            per_trait[column][result] += 1
            if result == CONTRADICTED:
                contradictions.append((label, column, ours, theirs))

    print("  %-24s %9s %9s %13s" % ("", "confirmed", "not seen", "contradicted"))
    totals = collections.Counter()
    for column in columns:
        counts = per_trait.get(column)
        if not counts:
            print("  %-24s   no exemplar in this packet -- not testable" % column)
            continue
        n = sum(counts.values())
        totals.update(counts)
        print("  %-24s %4d/%-4d %4d/%-4d %6d/%-6d"
              % (column, counts[CONFIRMED], n, counts[NOT_SEEN], n,
                 counts[CONTRADICTED], n))
    # The two kinds of claim are aggregated apart. "They find most of what is
    # there" is a real decision -- it is why the player is shown no tactical
    # card at all -- but it is a different claim from a behavioural trait, and
    # pooling them lets a strong result on one hide a weak one on the other.
    traits_only = collections.Counter()
    for column, counts in per_trait.items():
        if column != LAYER_COLUMN:
            traits_only.update(counts)
    n = sum(traits_only.values())
    if n:
        print("\n  %-24s %4d/%-4d %4d/%-4d %6d/%-6d"
              % ("behaviour traits", traits_only[CONFIRMED], n,
                 traits_only[NOT_SEEN], n, traits_only[CONTRADICTED], n))
    n_all = sum(totals.values())
    if n_all:
        print("  %-24s %4d/%-4d %4d/%-4d %6d/%-6d"
              % ("and with the layer", totals[CONFIRMED], n_all,
                 totals[NOT_SEEN], n_all, totals[CONTRADICTED], n_all))

    if contradictions:
        print("\n  Where the coach said the opposite. These are the ones that")
        print("  matter -- read the games before deciding who is right.\n")
        for label, column, ours, theirs in contradictions:
            print("     %-5s %-24s we said %s, coach said %s"
                  % (label, column, ours, theirs))
    return per_trait, totals


def chance_baseline(form, key, columns, totals):
    """CONTROL 2 -- shuffle the coach's own labels across players."""
    print("\n" + "=" * 68)
    print("CONTROL 2 -- WHAT THE SAME ANSWERS WOULD SCORE BY CHANCE")
    print("=" * 68)
    n = sum(totals.values())
    if not n:
        print("Nothing spoken to score.")
        return None, None
    observed = totals[CONFIRMED] / n

    labels = [l for l in key["entries"] if l in form]
    columns_by_trait = {c: [form[l].get(c, "") for l in labels] for c in columns}
    ours_by_trait = {c: [key["entries"][l]["ours"].get(c, "-") for l in labels]
                     for c in columns}

    rng = random.Random(SEED)
    at_or_above = 0
    draws = []
    for _ in range(SHUFFLES):
        hits = seen = 0
        for column in columns:
            theirs = list(columns_by_trait[column])
            rng.shuffle(theirs)
            for ours, got in zip(ours_by_trait[column], theirs):
                if ours in ("-", "?"):
                    continue
                seen += 1
                if got == ours:
                    hits += 1
        rate = hits / seen if seen else 0.0
        draws.append(rate)
        if rate >= observed:
            at_or_above += 1

    draws.sort()
    print("The coach's own answers, reassigned to the wrong players %d times."
          % SHUFFLES)
    print("This keeps how often they say A, B, - and ? exactly as it is, so a")
    print("coach who mostly answers one way gets the high baseline they should.")
    print("\n  confirmed rate, as scored:        %.2f" % observed)
    print("  confirmed rate, shuffled:        median %.2f, 95th %.2f"
          % (draws[len(draws) // 2], draws[int(len(draws) * 0.95)]))
    print("  shuffles reaching what we scored: %d of %d  (p = %.4f)"
          % (at_or_above, SHUFFLES, at_or_above / SHUFFLES))
    p_value = at_or_above / SHUFFLES
    if p_value > 0.05:
        print("\n  NOT DISTINGUISHABLE FROM CHANCE. Whatever the confirmed rate")
        print("  looks like, this coach's answers reassigned at random score it")
        print("  about as often. The packet does not support the traits.")
    else:
        print("\n  Better than the same answers on the wrong players.")
    return observed, p_value


def unseen_report(form, key, columns):
    """Which questions the coach could not answer at all."""
    print("\n" + "=" * 68)
    print("WHAT THIS MANY GAMES COULD NOT SHOW")
    print("=" * 68)
    print("A column answered '?' for most players is not a failed trait -- it")
    print("is a trait that needs more games than the packet gave.\n")
    for column in columns:
        marks = [form[l].get(column, "") for l in key["entries"] if l in form]
        unknown = sum(1 for m in marks if m == "?")
        middle = sum(1 for m in marks if m == "-")
        print("  %-24s cannot tell %d/%d,  in between %d/%d"
              % (column, unknown, len(marks), middle, len(marks)))


def validate(form, columns):
    bad = []
    for label, row in form.items():
        for column in columns:
            value = row.get(column, "")
            allowed = VALID_LAYER if column == LAYER_COLUMN else VALID_TRAIT
            if value and value not in allowed:
                bad.append((label, column, value))
    if bad:
        print("UNREADABLE ANSWERS -- these are dropped, not guessed at:")
        for label, column, value in bad:
            print("   %-5s %-24s %r" % (label, column, value))
        print()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--form", required=True)
    parser.add_argument("--key", required=True)
    args = parser.parse_args()

    key = json.loads(Path(args.key).read_text(encoding="utf-8"))
    form = read_form(Path(args.form))
    columns = [c for c in next(iter(key["entries"].values()))["ours"]]

    filled = [l for l in key["entries"] if l in form]
    print("players in the key: %d,  rows filled in: %d\n"
          % (len(key["entries"]), len(filled)))
    if not filled:
        print("No matching rows. Is this the right key for this packet?")
        return 1

    validate(form, columns)
    repeat_control(form, key.get("repeat_pairs") or [], columns)
    _, totals = score_spoken(form, key, columns)
    chance_baseline(form, key, columns, totals)
    unseen_report(form, key, columns)

    print("\n" + "=" * 68)
    print("This packet was built to spread across every category, not to")
    print("resemble the real population. It can say whether a claim is right.")
    print("It cannot say how many players the claim applies to.")
    print("=" * 68)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
