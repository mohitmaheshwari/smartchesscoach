# The chance is the unit, not the game — scope

Mohit, 2026-10-05, after two rounds of narrowing: *"it should be game
independent really, like quality of moves vs chances provided."*

## The idea in one line

**Of the chances the board gave you, how many did you take?**

- **Chances provided** is the denominator. The player does not control it. The
  board hands it over.
- **Chances taken** is the numerator. That part is entirely them.

No game counts, no rating, no accuracy percentage. The game is only a container
and it varies from one chance to sixteen, so it tells you nothing on its own.

## What a chance is, in plain words

A moment where the engine's best move was a tactic with a name — a pin, a
skewer, a fork, free material. `opportunity_gate.observe` already decides this,
and "took it" means playing that exact move.

Three real ones from his games, as the card would understand them:

| he played | the tactic was | shape |
|---|---|---|
| Bf5 | Bd5 | skewer |
| fxe6 | Qxd1 | pin |
| b5 | Bg4 | pin |

An earlier draft called these "questions the game asked". That word needed
explaining to Mohit, so it would fail with a 1200 player. The word is **chance**.

## Why game-independence is the right call, not just a simplification

**It dissolves two data problems instead of fixing them.** The previous draft was
going to add game de-duplication and a short-game filter: 1,054 duplicate PGN
groups exist across 19,229 games, and 2-move coach games repeat legitimately. A
2-move game provides no chances, so it contributes nothing to either side of the
ratio. The bad data stops mattering rather than needing cleaning.

**It makes periods comparable.** Three games one week and thirty the next compare
directly, because the denominator is chances rather than games.

**It separates what the player controls from what they do not.** A quiet week is
not their fault. A low conversion is.

## The readings

### 1. The ratio
His last 25 games: **153 chances, 77 taken.**

### 2. By shape — the actionable cut
Across 816 analysed games:

| shape | chances | took |
|---|---|---|
| free material | 855 | **83%** |
| fork | 663 | 51% |
| pin | 1,471 | 44% |
| skewer | 1,053 | **42%** |

This is where the reading earns its keep: alignment tactics drag his conversion
down and they are 59% of every chance he gets.

### 3. Is it moving
Flat between 51% and 65% over ten weeks. **The wording of this reading is
constrained — see the correction below.**

## A correction that must not be undone

I first read the flat rate as *"you are not improving"*. Over the same period his
rating went **1067 → 1307**. He improved a great deal; one narrow measure did
not move. Either tactical conversion is now his ceiling, or he is holding the
same rate against harder positions. **The product says the narrow true thing or
it says nothing.**

## A circularity that must not be repeated

A difficulty control was first built on the stored `threat` field, and returned a
take rate of 0% in every hard cell in every month against 72% in routine:

    threat=True   took=True      0
    threat=True   took=False  1283
    threat=False  took=True   2297

`threat` is written when the player missed or allowed something, so it is
downstream of whether they got it right. This is the second circularity in
`position_difficulty` after `is_critical`. **Any difficulty control uses only
phase and eval band, both of which exist before the player moves.**

## Out of scope

- **Chances GIVEN to the opponent.** The mirror measure — he hands over a shape
  about once in five moves. It needs the opponent's positions analysed, which
  `move_evaluations` does not store; enriching 50 games took 84 minutes. Real,
  measured, and a separate cost decision.
- **Accuracy over all moves.** That is chess.com's number and it is noisy.
- **Any rating.**

## What the player sees

```
┌───────────────────────────────────────────────┐
│  THE CHANCES YOU GOT                          │
│                                               │
│  You took about half of what the board         │
│  offered you.                                  │
│                                                │
│  free material   ████████▌                     │
│  forks           █████                         │
│  pins            ████▌                         │
│  skewers         ████▏                         │
│                                                │
│  Lining pieces up is what costs you.           │
│  [ One skewer, right now → ]                   │
└────────────────────────────────────────────────┘
```

## Numbers

Unresolved and deliberately deferred in the build: the authored strings carry
**no numbers**, and the counts ride in separate fields. The bars are shapes, not
figures. If Mohit decides plain counts may be shown, it becomes a UI change and
no server work. If he decides they may not, nothing has to be undone.

## Performance

Running the gate over one player's 21,485 moves takes about twenty seconds, so
it is not done on a page load. `scripts/compute_tactical_eye.py` already
batch-computes the pooled figure into `user_tactical_eye`; this extends that
document rather than adding a collection.

## How we will know it worked

Whether a player's take rate moves after they start seeing it. Same standard as
the pin and skewer drill, and it needs weeks of new games either way.
