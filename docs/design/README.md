# Approved design reference

## `chessguru-atelier.html`

The interactive visual study approved by Mohit on 2026-09-22 ("okay, go ahead, and
make this UX for all our pages please"). It is the appearance-and-interaction
reference for `../coaching_room_all_pages_scope.md` and
`../coaching_room_all_pages_spec.md`.

Copied verbatim from the authoring tool's output at
`~/.codex/visualizations/2026/08/28/01a04806-dc40-7bc0-b3d8-e126488e1214/`
(last written 2026-09-22 14:04). It lives here so the approval gate does not
depend on a conversation that can be lost.

### Status: reference only

- **Not routed, not served, not bundled.** `docs/` is outside CRA's build and
  outside `frontend/public`. Do not move this file into either.
- Its chess position, simplified move script, unsaved completion and placeholder
  account states are **design fiction**. Scope section 4 forbids copying them into
  real product paths.

### What it establishes

Canonical palette, taken from its `:root`:

| Token | Value | Role |
|---|---|---|
| `--cg-bg` | `#f7f7f2` | ivory working surface |
| `--cg-paper` | `#fffefa` | raised card |
| `--cg-text` | `#18362c` | primary text |
| `--cg-secondary` | `#58695f` | secondary text |
| `--cg-border` | `#dfe5da` | calm neutral border |
| `--cg-forest` | `#183c2d` | navigation |
| `--cg-lime` | `#d0ef91` | restrained accent |
| `--cg-square` | `#8eaa8d` | board dark square (sage) |
| `--cg-light` | `#e9eadb` | board light square |

Typefaces: **Instrument Serif** (editorial headings) and **Manrope** (interface
and body). Both are SIL OFL, so they can be self-hosted without a licence
purchase.

Measured contrast still has to be checked per spec section 6 — these values are the
design intent, not a passed accessibility check.

### Two dependencies that must NOT ship

The reference loads both from the network. The app must not.

1. `fonts.googleapis.com` — self-host the two families from an npm package instead.
2. `cdn.jsdelivr.net/gh/lichess-org/lila@master/public/piece/cburnett/` — a
   **mutable** `@master` ref for piece images. Exactly the live dependency scope
   section 2 prohibits. The app uses its existing bundled piece assets through the
   existing board renderer.
