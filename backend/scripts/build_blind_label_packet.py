"""Build a packet a human coach can label BLIND, to test whether the traits are true.

WHY THIS EXISTS
---------------
Every behavioural trait and both diagnosis layers were validated the same way:
stable within a player across halves of their games, and spread across players.
That is internal consistency. It is not evidence that the reading is CORRECT --
a measure can be perfectly reliable and measure the wrong thing.

Nothing in the system has ever been checked against a person who knows chess
saying "yes, that is this player". This packet is that check. A coach reads the
games and writes a diagnosis with no sight of ours; `score_blind_labels.py` then
compares the two.

WHAT MAKES THE ANSWER MEAN ANYTHING
-----------------------------------
Three things, and without all three an agreement number is decoration:

1. BLIND. The packet contains no ChessGuru output of any kind. The answer key is
   written to a separate path, never inside the packet directory.

2. FREE TEXT BEFORE FORCED CHOICE, in two files, with the second to be opened
   only when the first is finished. Showing our six traits first would tell the
   coach what to look for, and agreement would then measure suggestion.

3. A REPEAT. One player appears twice under two ids, with a DIFFERENT set of
   games each time. If the coach does not agree with themselves, no agreement
   with us can be interpreted -- it bounds every other number in the report.
   This is the positive control.

   Different games rather than the same file, for two reasons. The same eight
   games twice tests whether the coach remembers their own answer, which is not
   what we need to know. Different games test whether they describe the same
   PERSON the same way from different evidence -- which is precisely the
   property we claim for our own traits, measured on one half of a player's
   games against the other. It also means the repeat is far less likely to be
   spotted, and a spotted control is not a control.

SELECTION IS DELIBERATE, NOT RANDOM
-----------------------------------
A random draw would be mostly middle-of-the-population players, who say nothing
on most traits, and 38 of 48 eligible players have no tactical gap. The set is
chosen to carry at least two high and two low exemplars of every speaking trait,
every knowledge-layer player we have, several attention-layer, several with no
gap as controls, and at least one player the system calls featureless.

That makes it a discrimination test, not a prevalence test. It cannot tell us how
common a trait is -- the base rates are destroyed on purpose. It can tell us
whether, when we say a player is at an end, a coach sees the same thing.

THE CONFOUND, NAMED
-------------------
The coach reads eight games. We measure over a player's whole history, a median
of 145 clocked games. A disagreement can therefore mean our reading is wrong OR
that eight games are too few to see the trait. Eight is chosen to clear our own
MIN_TIMED_MOVES of 200, so the coach is not asked to judge from less evidence
than we require of ourselves, but it does not remove the confound and the report
must not read a disagreement as our error alone.

    python scripts/build_blind_label_packet.py                  # report only
    python scripts/build_blind_label_packet.py --apply --out DIR
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import json
import os
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from services.behaviour_profile import (  # noqa: E402
    CUTS, SILENT_TRAITS, build_profile, compute_traits,
)

# Eight games clears MIN_TIMED_MOVES (200) at a typical 30 moves a side, so the
# coach is not asked to judge from less evidence than we demand of ourselves.
GAMES_PER_PLAYER = 8
N_PLAYERS = 12
MIN_CLOCKED_GAMES = 8
SEED = 20260929

CLOCKED = r"%clk"

# Neutral wording for the forced choice. NOT the sentences we show the player --
# those are written to be recognised, which would make them leading here. Each
# trait is offered as two symmetric descriptions with no better end.
TRAIT_CHOICES = {
    "thinks_long": ("stops and works when the position gets hard",
                    "keeps moving; long thinks are rare"),
    "moves_fast": ("plays a lot of moves instantly",
                   "gives nearly every move a moment"),
    "clock_front_loaded": ("spends the clock early, finishes in a hurry",
                           "holds time back for the end"),
    "plays_on_when_lost": ("plays on in lost positions",
                           "games end soon after they go wrong"),
    "knowledge_breadth": ("brings a wide range of ideas",
                          "the same few ideas carry most games"),
    "throws_away_won_games": ("lets won positions slip",
                              "converts what they win"),
}

LAYER_TO_CHOICE = {"knowledge": "A", "attention": "B", "no_tactical_gap": "C"}


def speaking_traits():
    return [t for t in sorted(CUTS) if t not in SILENT_TRAITS]


# -- selection -------------------------------------------------------------

def select(players, n=N_PLAYERS):
    """Pick a set carrying both ends of every trait and every layer verdict.

    Greedy on unmet need, deterministic. Returns (chosen, unmet).
    """
    need = collections.Counter()
    for trait in speaking_traits():
        need["%s:high" % trait] = 2
        need["%s:low" % trait] = 2
    need["layer:knowledge"] = 2
    need["layer:attention"] = 3
    need["layer:no_tactical_gap"] = 3
    need["balanced"] = 1

    def offers(p):
        out = set()
        for line in p["lines"]:
            if line["trait"] == "balanced":
                out.add("balanced")
            else:
                out.add("%s:%s" % (line["trait"], line["end"]))
        if p.get("layer"):
            out.add("layer:%s" % p["layer"])
        return out

    pool = sorted(players, key=lambda p: (-p["games_with_clocks"], p["user_id"]))
    chosen = []
    while len(chosen) < n and pool:
        best, best_key = None, None
        for p in pool:
            score = sum(1 for k in offers(p) if need[k] > 0)
            # Tie-break on history, then id: reproducible, and prefers players
            # whose own trait estimates rest on the most games. Capped so a
            # single 1,896-game player does not win every tie.
            key = (score, min(p["games_with_clocks"], 400), p["user_id"])
            if best_key is None or key > best_key:
                best, best_key = p, key
        chosen.append(best)
        pool.remove(best)
        for k in offers(best):
            if need[k] > 0:
                need[k] -= 1

    return chosen, {k: v for k, v in need.items() if v > 0}


# -- pgn -------------------------------------------------------------------

# Dropped outright. Date goes with them: no trait we test needs it, and with the
# rating it is the tell that would let a coach spot the repeated player.
_STRIP_TAGS = re.compile(
    r'^\[(Site|Link|Date|UTCDate|UTCTime|Timezone|Annotator|CurrentPosition|'
    r'Currentposition|ECOUrl|Ecourl|Event|Round|StartTime|EndTime|EndDate|'
    r'Tournament|Match)\s.*\]\s*$', re.M)

_TAG = re.compile(r'^\[(\w+)\s+"(.*)"\]\s*$', re.M)


def _names(pgn: str):
    found = {m.group(1): m.group(2) for m in _TAG.finditer(pgn or "")}
    return found.get("White", ""), found.get("Black", "")


def anonymise(pgn: str, user_color: str) -> str:
    """Strip anything identifying, and mark which side the coach is watching.

    The usernames are replaced EVERYWHERE in the header block, not just in the
    White and Black tags. Chess.com writes the winner's name into Termination
    ("aydin_yashar won by resignation"), which a tag-by-tag rewrite leaves in
    place -- and one username is enough to look the player up and read their
    whole history.

    Termination itself is kept, with the name swapped. "won on time" is the most
    direct evidence there is for two of the clock traits, and dropping the tag to
    remove the name would take that with it.

    Ratings stay. A coach needs to know whether this is a 700 or a 1400 to read
    anything at all, and the rating is not an input to any trait we compute.
    """
    text = pgn or ""
    white, black = _names(text)
    subject = "White" if str(user_color).lower().startswith("w") else "Black"
    swap = [(white, "THE PLAYER" if subject == "White" else "opponent"),
            (black, "THE PLAYER" if subject == "Black" else "opponent")]

    def scrub(match):
        line = match.group(0)
        for name, replacement in swap:
            if name:
                line = re.sub(re.escape(name), replacement, line,
                              flags=re.IGNORECASE)
        return line

    # Header lines only. A username that happens to look like SAN would mangle
    # the movetext, and the movetext carries no names to begin with.
    text = re.sub(r'^\[.*\]\s*$', scrub, text, flags=re.M)
    text = _STRIP_TAGS.sub("", text)
    return re.sub(r'\n{3,}', '\n\n', text).strip() + "\n"


async def games_for(db, user_id: str, limit: int):
    """The most recent clocked games.

    Clocks are not optional: three of the six traits are about the clock, and a
    coach cannot be asked about what the file does not show.
    """
    return await db.games.find(
        {"user_id": user_id, "pgn": {"$regex": CLOCKED}},
        {"_id": 0, "game_id": 1, "pgn": 1, "user_color": 1, "result": 1,
         "played_at_utc": 1, "time_control": 1, "user_rating": 1,
         "opponent_rating": 1},
    ).sort("played_at_utc", -1).to_list(limit)


# -- writing ---------------------------------------------------------------

README = """# Reading these games

Thank you. This takes about three hours and it settles a question we cannot
settle ourselves.

We have built a system that watches a player's games and describes how they
play. Everything in it has been checked for consistency -- it says the same
thing about a player in March as in September. Nothing in it has ever been
checked for **correctness**. That is what you are for.

## What is here

{n} players, {g} recent games each. Names are removed. Ratings and clock times
are kept, because you need both. In every game one side is tagged **THE PLAYER**
-- that is the person you are describing. Ignore the opponent except as context.

Some of these games are blitz and some are longer. That is deliberate.

## What to do, in order

**1. Open `form_1_freetext.md` and finish it completely.**

For each player, read their games and write two or three sentences: what kind of
player is this, and what would you tell them to work on. Write it in your own
words. There is no list to pick from, on purpose.

**2. Only then open `form_2_choices.csv`.**

It asks the same thing as a set of choices. Do not open it first -- if you see
our categories before you have written your own, your answers stop being
independent and the whole exercise is worth nothing.

Every question there has a **"can't tell"** option. Please use it freely. "That
many games is not enough to see this" is a real and useful answer, and we would
much rather have it than a guess. A guess looks exactly like a judgement in the
results and we cannot separate them afterwards.

## What we will do with it

Compare your answers to ours, one question at a time, and report where we agree,
where we disagree, and where you said the question could not be answered.

Two honest warnings about how we will read it:

- You see a handful of games. We measure over a player's whole history, often
  more than a hundred games. If you and we disagree, that can mean we are wrong,
  or that this many games are too few. We will not report it as purely our
  error.
- These players are **not a random sample**. They were chosen to spread across
  every category, so the mix here is nothing like the real population. You
  cannot conclude anything about how common any of this is, and neither can we.

## One more thing

If you want to say something about a player that none of the questions in file 2
asks about -- write it in file 1. Those are the most valuable lines in the
packet. Three of the things we most wanted to measure (does this player attack
too much, do they calculate, do they play with a plan) we failed to measure at
all, and a sentence from you about what is observable would be worth more than
any of the agreement numbers.
"""

FREETEXT_HEADER = """# File 1 of 2 - in your own words

Finish this file before opening `form_2_choices.csv`.

For each player: what kind of player is this, and what should they work on?
Two or three sentences. Your words, not ours.

If nothing stands out about someone, say that. It is a real answer, and one of
these players is here precisely to see whether you say it.

---
"""


def choices_note():
    lines = [
        "# File 2 of 2 - the same question as choices",
        "#",
        "# Open this only after form_1_freetext.md is finished.",
        "#",
        "# One row per player. In each column put exactly one of:",
        "#     A     the first description fits",
        "#     B     the second description fits",
        "#     -     neither stands out, they are in between",
        "#     ?     cannot tell from these games",
        "#",
        "# Please use ? whenever it is true. A guess and a judgement look",
        "# identical to us afterwards and we cannot separate them.",
        "#",
        "# The columns:",
        "#",
    ]
    for trait in speaking_traits():
        a, b = TRAIT_CHOICES[trait]
        lines.append("#   %-22s A = %s" % (trait, a))
        lines.append("#   %-22s B = %s" % ("", b))
    lines += [
        "#",
        "#   When this player misses a tactic, which is it:",
        "#   %-22s A = does not know the shape yet" % "tactical_misses",
        "#   %-22s B = knows it, was not looking" % "",
        "#   %-22s C = they find most of what is there" % "",
        "#   %-22s ? = cannot tell" % "",
        "#",
        "#   confidence_1_to_5   how sure you are about this player overall",
        "#   notes               anything the columns do not cover",
        "#",
    ]
    return "\n".join(lines)


def write_packet(out_dir: Path, entries):
    """`entries` is a list of (player, games) in the order the coach sees them."""
    players_dir = out_dir / "players"
    players_dir.mkdir(parents=True, exist_ok=True)

    labels = []
    for i, (entry, rows) in enumerate(entries, start=1):
        label = "P%02d" % i
        labels.append((label, entry["user_id"]))
        pdir = players_dir / label
        pdir.mkdir(exist_ok=True)
        pgn = "\n\n".join(anonymise(r.get("pgn", ""), r.get("user_color", "white"))
                          for r in rows)
        (pdir / "games.pgn").write_text(pgn, encoding="utf-8")

        ratings = [r.get("user_rating") for r in rows if r.get("user_rating")]
        # Rounded to the nearest hundred, deliberately. The exact range is the
        # one field that would let a coach match the repeated player's two
        # appearances, and a coach needs the band, not the number.
        band = ("around %d" % (round(sum(ratings) / len(ratings) / 100) * 100)
                if ratings else "unknown")
        tcs = collections.Counter(
            dict(_TAG.findall(r.get("pgn") or "")).get("TimeControl", "?")
            for r in rows)
        colours = collections.Counter(str(r.get("user_color")) for r in rows)
        results = collections.Counter(str(r.get("result")) for r in rows)
        about = [
            "Player %s" % label,
            "",
            "%d games, most recent first." % len(rows),
            "Rating over these games: %s" % band,
            "Time controls: %s" % ", ".join(
                "%s (%d)" % (k, v) for k, v in tcs.most_common()),
            "Colours: %s" % ", ".join(
                "%s %d" % (k, v) for k, v in colours.most_common()),
            "Results as played: %s" % ", ".join(
                "%s %d" % (k, v) for k, v in results.most_common()),
            "",
            "In each game THE PLAYER is the side tagged so. Clock times are in",
            "the move comments.",
        ]
        (pdir / "about.txt").write_text("\n".join(about) + "\n", encoding="utf-8")

    (out_dir / "README.md").write_text(
        README.format(n=len(entries), g=GAMES_PER_PLAYER), encoding="utf-8")

    free = [FREETEXT_HEADER]
    for label, _ in labels:
        free.append("## %s\n\nWhat kind of player:\n\n\nWhat to work on:\n\n\n---\n"
                    % label)
    (out_dir / "form_1_freetext.md").write_text("\n".join(free), encoding="utf-8")

    header = ["player"] + speaking_traits() + [
        "tactical_misses", "confidence_1_to_5", "notes"]
    rows = [choices_note(), ",".join(header)]
    for label, _ in labels:
        rows.append(",".join([label] + [""] * (len(header) - 1)))
    (out_dir / "form_2_choices.csv").write_text("\n".join(rows) + "\n",
                                                encoding="utf-8")
    return labels


def write_key(key_path: Path, labels, repeat_pairs, entries):
    by_user = {entry["user_id"]: entry for entry, _ in entries}
    out = {}
    for label, user_id in labels:
        entry = by_user[user_id]
        ours = {}
        for line in entry["lines"]:
            if line["trait"] != "balanced":
                ours[line["trait"]] = "A" if line["end"] == "high" else "B"
        # A trait inside the middle half is not silence, it is our "-".
        for trait in speaking_traits():
            ours.setdefault(trait, "-")
        ours["tactical_misses"] = LAYER_TO_CHOICE.get(entry.get("layer"), "?")
        out[label] = {
            "user_id": user_id,
            "ours": ours,
            "layer": entry.get("layer"),
            "balanced": any(l["trait"] == "balanced" for l in entry["lines"]),
            "moves": entry["moves"],
            "timed_moves": entry["timed_moves"],
            "clocked_games": entry["games_with_clocks"],
            "_traits": entry["traits"],
        }
    key_path.write_text(json.dumps({
        "built_at": datetime.now(timezone.utc).isoformat(),
        "games_per_player": GAMES_PER_PLAYER,
        "repeat_pairs": repeat_pairs,
        "trait_choices": {k: {"A": v[0], "B": v[1]}
                          for k, v in TRAIT_CHOICES.items()},
        "entries": out,
    }, indent=1, default=str), encoding="utf-8")


# -- main ------------------------------------------------------------------

async def gather_players(db):
    eye = {}
    async for doc in db.user_tactical_eye.find({}, {"_id": 0}):
        eye[doc["user_id"]] = doc

    players = []
    for user_id in await db.move_observations.distinct("user_id"):
        try:
            measured = await compute_traits(db, user_id)
        except Exception:
            continue
        profile = build_profile(measured["traits"], measured["moves"],
                                measured["timed_moves"], measured["samples"])
        if not profile["measured"]:
            continue
        clocked = await db.games.count_documents(
            {"user_id": user_id, "pgn": {"$regex": CLOCKED}})
        if clocked < MIN_CLOCKED_GAMES:
            continue
        players.append({
            "user_id": user_id,
            "traits": measured["traits"],
            "moves": measured["moves"],
            "timed_moves": measured["timed_moves"],
            "games_with_clocks": clocked,
            "lines": [{"trait": l["trait"], "end": l["end"]}
                      for l in profile["lines"]],
            "layer": (eye.get(user_id) or {}).get("layer"),
        })
    return players


async def main_async(apply: bool, out: str) -> int:
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[
        os.environ.get("DB_NAME", "chess_coach")]

    players = await gather_players(db)
    print("eligible players: %d" % len(players))
    if len(players) < N_PLAYERS:
        print("REFUSING: fewer eligible players than the packet needs.")
        return 1

    chosen, unmet = select(players)
    print("chosen: %d" % len(chosen))
    if unmet:
        print("COVERAGE NOT MET: %s" % unmet)
        print("  a trait with no exemplar cannot be tested; the report must say")
        print("  so rather than score it")
    else:
        print("coverage: every trait end and every layer has its exemplars")

    print("\nlayer mix: %s" % dict(collections.Counter(
        c.get("layer") for c in chosen)))
    tally = collections.Counter()
    for c in chosen:
        for line in c["lines"]:
            tally["%s:%s" % (line["trait"], line["end"])] += 1
    print("\ntrait ends in the packet:")
    for trait in speaking_traits():
        print("   %-24s high %d  low %d"
              % (trait, tally["%s:high" % trait], tally["%s:low" % trait]))
    print("   %-24s %d" % ("balanced", tally["balanced:middle"]))

    # The repeat: the player carrying the most trait ends, so the retest runs on
    # the entry with the most to disagree about -- and with enough history to
    # give the second appearance a different set of games.
    def ends(player):
        return len([l for l in player["lines"] if l["trait"] != "balanced"])

    deep = [c for c in chosen if c["games_with_clocks"] >= 2 * GAMES_PER_PLAYER]
    repeat_src = max(deep or chosen,
                     key=lambda c: (ends(c), c["user_id"]))
    disjoint = bool(deep)

    entries = []
    short = []
    second = None
    for player in chosen:
        want = 2 * GAMES_PER_PLAYER if (player is repeat_src and disjoint) \
            else GAMES_PER_PLAYER
        rows = await games_for(db, player["user_id"], want)
        if len(rows) < want:
            short.append((player["user_id"], len(rows), want))
        if player is repeat_src and disjoint:
            # Interleaved, not first-half against second-half. Consecutive
            # blocks would put the two appearances in different months, and the
            # rating drift and the run of results between them are exactly the
            # tell that would let a coach spot the repeat. Odd-even also matches
            # how the traits themselves were validated.
            first, second = rows[0::2], rows[1::2]
        else:
            first = rows[:GAMES_PER_PLAYER]
            if player is repeat_src:
                second = first
        entries.append((player, first))
    if short:
        print("FEWER GAMES THAN ASKED: %s" % short)

    insert_at = random.Random(SEED).randrange(1, len(entries))
    entries.insert(insert_at, (repeat_src, second))
    print("\nrepeat control: one player appears twice among the %d entries"
          % len(entries))
    if disjoint:
        print("   the two appearances carry DIFFERENT games, so the control")
        print("   tests description of the player and not memory of an answer")
    else:
        print("   DEGRADED: no chosen player has %d clocked games, so the two"
              % (2 * GAMES_PER_PLAYER))
        print("   appearances carry the SAME games. That tests whether the coach")
        print("   remembers their answer, not whether they see the same player.")

    if not apply:
        print("\n(dry run -- nothing written; pass --apply --out DIR)")
        return 0

    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    labels = write_packet(out_dir, entries)

    seen, repeat_pairs = {}, []
    for label, user_id in labels:
        if user_id in seen:
            repeat_pairs.append([seen[user_id], label])
        else:
            seen[user_id] = label

    # The key lives OUTSIDE the packet. Anything inside it reaches the coach.
    key_path = out_dir.parent / ("%s_ANSWER_KEY.json" % out_dir.name)
    write_key(key_path, labels, repeat_pairs, entries)

    print("\npacket:     %s" % out_dir)
    print("answer key: %s" % key_path)
    print("            ^ NOT inside the packet. Do not send this file.")
    print("repeat pair: %s" % repeat_pairs)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--out", default="blind_label_packet")
    args = parser.parse_args()
    return asyncio.run(main_async(args.apply, args.out))


if __name__ == "__main__":
    raise SystemExit(main())
