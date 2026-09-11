# Board Geometry — data lock and ownership map

**Status:** LOCKED for the default-off V1 implementation · 2026-09-11
**Scope authority:** `docs/board_geometry_learning_scope.md`

## Population measured

The local production-shaped corpus contained 14,889 analyzed games, 15,569 game documents, 484 Play with Coach sessions, 301 postgame analyses, 71 motif profiles, and 90 learning sessions.

Rating coverage is concentrated in the target audience. Among 53 users with a usable assessed or detected rating, 22 were below 1000, 18 were 1000–1399, 10 were 1400–1799, and 3 were 1800+. The PWC corpus contained 50 sessions below 1000, 410 at 1000–1399, 1 at 1400–1799, and 23 at 1800+.

Stored, verified `got_positions` supply contains 677 forks across 45 profiles, 796 pins across 44, and 722 skewers across 42. Twenty-three of 71 profiles have no stored geometry position, so authored teaching content remains necessary and personal positions are an application stage rather than the lesson's only supply.

After removing duplicate motif labels on the same game move, 996 games contained at least one verified fork, pin, or skewer moment. Of those games, 649 contained one moment, 232 contained two, 72 contained three, and 43 contained four or more. Consecutive moments were close: the median gap was 3 player moves, p75 was 7, and p90 was 14.

## Decisions locked from the measurements

### Seriousness and soundness

Candidates were a new geometry-specific centipawn threshold, the old fixed motif gates, and ChessGuru's shared rating-aware move-quality tiers.

V1 does not add a new threshold. A personal **allowed** or **missed** card requires the existing shared mistake-or-blunder classification and canonical geometry evidence. A **found** card requires the existing sound-move gate and canonical geometry evidence. The stored motif pipeline's 100 cp allowed gate and 40 cp sound gate remain compatibility inputs for already-generated evidence; new live decisions use the central rating-aware classification. This keeps the severity wording identical to the caption and PWC pipelines.

### Live prompt quota

Candidates were one, two, or three geometry interruptions per game.

V1 locks **one learner-facing geometry prompt per game**. Sixty-five percent of games with verified geometry contained exactly one distinct moment. A second prompt would add coverage in 35% of opportunity games while doubling interruptions in those games. All later moments are still recorded silently for the postgame report.

### Cooldown and duplicate suppression

Candidates were four, eight, or twelve player moves.

V1 locks **eight player moves between distinct geometry prompts** as a future-safe suppression rule. The measured p75 gap is seven moves, so eight suppresses three quarters of closely clustered repeats. The one-prompt V1 quota is stricter, but the cooldown remains part of the contract if the quota is later raised. An unchanged relationship revision is always deduplicated regardless of move count.

### Lesson content coverage

Candidates were four, six, or eight fixed activities per module.

V1 locks **eight distinct fixed activities per module**, because the signed learning journey has eight non-personal roles that must not reuse an assessment position: flash, unguided baseline, attack map, relationship location, real-versus-fake counterexample, create-or-avoid practice, mixed unseen post-test, and delayed recall. A verified personal position is inserted separately when available. Both board orientations are required; diagonal modules also cover light and dark diagonals, and pawn modules cover both movement directions.

### Rollout

The implementation remains default-off. Training may be enabled for internal review once its content truth tests pass. Live PWC prompting remains disabled until all four modules pass content review and the repository's active experiment has ended or received an orthogonality ruling.

## Single source ownership

| Concept | Canonical authority | Geometry product use |
|---|---|---|
| Move-scoped board facts | `services.caption_facts.extract_facts` | The only entry point for facts after a played or candidate move. |
| Multi-target geometry | `multi_target_attack_evidence` emitted by `extract_facts` | Lesson and PWC adapters filter by attacker piece. |
| Teachable fork | `services.caption_facts.named_fork_shapes` / `named_fork_evidence` | The only fork naming and winnability view. |
| Sliding alignment | `aligned_pieces_evidence` emitted by `extract_facts` | Supplies attacker, front, rear, value order, and line kind. |
| Pin/skewer naming | `services.motif_profile_service._classify_aligned` | Reused through a public projection; no lesson-local taxonomy. |
| Shared attack square | A public helper beside the canonical caption facts | Pure board geometry used for square-selection lessons; one implementation only. |
| Personal attribution | `services.motif_profile_service` | Extended to project allowed, missed, and found moments from the same move records. |
| Lesson lifecycle and evidence | `services.teaching_engine` + `learning_sessions` | Board Geometry registers as a lesson type and uses the existing event store. |
| Learner state | `services.concept_mastery_service` | Board Geometry session evidence is projected into the existing learner-facing states. |
| Live rendering | Existing PWC coaching response and board annotation state | Geometry text and marks ship in one response; `geometry_plans.py` no longer supplies product truth. |

## Rejected alternatives

- RAG or semantic retrieval for chess truth: exact board geometry and engine evidence are available locally.
- An LLM detector or grader: it cannot provide deterministic accepted answers.
- Always-on arrows: the measured clustering would create repeated visual noise.
- A separate mastery collection or geometry detector catalog: it would split current authorities.
- Promoting raw `shape_detectors.py` output directly into lessons: its quality gate intentionally blocks unreviewed shapes.
