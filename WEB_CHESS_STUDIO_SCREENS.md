# Elite Chess Studio — Web Frontend Design Showcase

A tactile, studio-lit **Web Frontend Application** designed for modern desktop browsers with full support for dual **White** and **Black** piece modes.

---

## Screen 1: Desktop Web Application — White Pieces Active (Light Studio Theme)

![Web Desktop Application - White Pieces](C:/Users/MIISCO/.gemini/antigravity-ide/brain/e0140cf9-d622-43b7-873a-bd02184f8f88/tactile_web_frontend_desktop_1790684594331.jpg)

### Desktop Web Layout Breakdown:
* **Top Web Application Navigation Bar**:
  * **Brand Identity**: *Elite Chess Studio* with custom pawn monogram.
  * **Primary Navigation Tabs**: `TRAINING GROUND` (Active), `MATCH CENTER`, `TACTICS LAB`, `COMMUNITY`.
  * **User Profile & Status**: *Alexandra K. (Master)* with live status indicator and notification bell.
* **Left Column — 3D Piece Academy**:
  * **Interactive Switcher**: Toggled to **White** with glowing active pill.
  * **3D Ceramic Centerpiece**: High-gloss pearl white 3D King on an illuminated studio pedestal.
  * **Typography**: Elegant serif **KING** display typography with valuation.
  * **Piece Carousel**: Horizontal selector across all 6 pieces (Pawn, Rook, Knight, Bishop, Queen, King).
  * **Floating Card**: Tactical **PAWN** preview with `Be5` move marker.
  * **Rules Card**: *"How to Move the King"* with clear FIDE movement guidelines.
* **Right Column — Interactive Match Center**:
  * **Player Header**: **Tomasz (Master)** vs. **Jessica (Junior)** with live dual circular analog chess clocks and turn indicator (`Tomasz move`).
  * **Pristine 3D Chessboard**: Metallic finish with coordinates (A–H, 1–8).
  * **Tactical Movement Vectors**: Active Bishop highlighted with cyan box and diagonal dashed attack rays with destination circles.
  * **Captured Pieces Trays**: Dual trays flanking the board for White and Black captured pieces.
  * **Move History Pills**: Compact notation pills (`[19] Nxe5`, `[20] d4`, `[20] ...Be5`, `[21] Nd7`).
  * **Web Player Controls**: Play/pause, step backward, step forward, undo, chat badge, and menu.

---

## Screen 2: Desktop Web Application — Black Pieces Active (Dark Studio Theme)

![Web Desktop Application - Black Pieces](C:/Users/MIISCO/.gemini/antigravity-ide/brain/e0140cf9-d622-43b7-873a-bd02184f8f88/tactile_web_desktop_black_1790684766697.jpg)

### Black Perspective & Dark Mode Features:
* **Color Switcher State**: Toggled to **Black** with active cyan rim lighting.
* **Obsidian Ceramic 3D King**: High-gloss obsidian black finish with studio reflections.
* **Inverted Board Orientation**: Board oriented with Black pieces positioned at the bottom rank.
* **Charcoal Slate Theme**: Dark tactile aesthetic optimized for evening training and low eye fatigue.
* **Dynamic Attack Vectors**: Cyan vector rays highlighting tactical piece trajectories and fork targets.
* **Synchronized Clocks & Move History**: Real-time match state tracking for competitive play.

---

## Component Architecture in Web Frontend

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                             TOP WEB NAVIGATION BAR                                      │
│  [Logo] Elite Chess Studio    [Training Ground]  [Match Center]  [Tactics]   [User Profile]│
├───────────────────────────────────────────┬──────────────────────────────────────────────┤
│       LEFT: 3D PIECE ACADEMY              │          RIGHT: MATCH CENTER                 │
│                                           │                                              │
│  [ Color Switcher: White ● / Black ○ ]   │   [Player: Tomasz]  (Clock)(Clock)  [Jessica]│
│                                           │                                              │
│               [3D KING]                   │            ┌────────────────────┐            │
│                 KING                      │  [White    │   8x8 METALLIC     │   [Black   │
│                                           │   Captured │   CHESSBOARD       │    Captured│
│  [Pawn] [Rook] [Knight] [Bishop] [King]   │   Tray]    │   + Cyan Vectors   │    Tray]   │
│                                           │            └────────────────────┘            │
│  [Card: How to Move the King]             │   [History: 19. Nxe5  20. d4  20... Be5]     │
│                                           │   [|◀]  [ ▶ / ⏸ ]  [▶|]  [⟲]  [💬 5]  [☰]   │
└───────────────────────────────────────────┴──────────────────────────────────────────────┘
```
