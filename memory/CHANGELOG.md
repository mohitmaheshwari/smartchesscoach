# Chess Coach - Changelog

## Feb 23, 2026

### Reflection Engine V1 - Phase 1A Complete ✅

Built deterministic reflection engine with rating-adaptive behavior.

**New Backend Modules:**
- `reflect_constants.py` - Enums, rating bands, adaptive defaults
- `reflect_predicates.py` - Board fact detection (predicate registry)
- `quick_tag_registry.py` - Config-driven tag generation
- `awareness_gap_rules.py` - Deterministic gap detection (8 rules)
- `adaptive_profile_engine.py` - User profile generator
- `reward_message_service.py` - Template-based coach messages

**New API Endpoints:**
- `GET /api/reflect/v1/profile`
- `POST /api/reflect/v1/quick-tags`
- `POST /api/reflect/v1/submit`
- `GET /api/reflect/v1/post-loss/{game_id}`

**Key Features:**
- Rating bands: A(500-799), B(800-1099), C(1100-1399), D(1400-1699), E(1700+)
- 3 reward tones: encouragement, pattern_progress, precision
- 8 awareness gap rules (confidence_gap, panic_pattern, aligned, etc.)
- Versioned rules (v1) for future A/B testing

---

### Move Arrow Implementation ✅

- Fixed arrow format in Lab.jsx: `[[from, to, color]]`
- Verified on Lab page (orange) and Reflect page (red/green)

### Account Linking Security Fix ✅

- Validation prevents importing from wrong accounts
- Added `/api/journey/unlink-account` endpoint
- Standardized field names (`chess_com_username`)

### Reflection Bug Fixes ✅

- Fixed "I saw X was undefended" when user clearly missed it
- Fixed "I didn't notice" for pieces giving check
- Added check-aware contextual tags
