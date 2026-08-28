# Tactical alignment attribution evidence — 2026-08-27

Status: IMPLEMENTATION REPAIRED; PIN AND SKEWER REMAIN SHADOW

## Finding

The caption fact extractor already removed pin/skewer shapes that existed
before the played move. It compares both the full attacker/front/rear identity
and the front/rear target pair, so moving a slider along an already-active line
does not become a new coaching claim.

The remaining shared-fact defect was value ordering: the general material table
assigns the king no capturable exchange value. Reusing that zero in aligned
geometry made a piece in front of its king look more valuable than the rear
piece. Downstream motif classification could therefore call an absolute pin a
skewer or omit the pin.

## Repair

`caption_facts._aligned_pieces_evidence` now uses an ordering value of 10,000
for a king while keeping the ordinary material table unchanged. This is
taxonomy-only: it does not claim that a king is capturable material.

Regression coverage proves:

- an unrelated move cannot claim a pre-existing absolute pin;
- a newly created absolute pin is classified as pin, not skewer;
- moving a slider along an existing pin line is not new attribution;
- an unrelated move cannot claim a pre-existing skewer;
- a newly created queen-in-front-of-rook alignment remains a skewer.

## Read-only production impact scan

A random 50-game production sample contained:

- 1,512 evaluated moves;
- zero SAN/FEN parse errors;
- 230 move-attributed aligned shapes;
- 26 absolute-pin shapes encoded with the wrong front/rear relation.

The defect therefore affected 11.3% of aligned shapes in this sample. The scan
did not write to production.

## Authorization decision

The repair closes a deterministic taxonomy defect but does not supply
independent semantic gold. `shape:pin` and `shape:skewer` remain Shadow until
each passes the locked Caption-grade precision, negative-case and adversarial
requirements. Stored motif profiles must not be backfilled until that review
packet passes.
