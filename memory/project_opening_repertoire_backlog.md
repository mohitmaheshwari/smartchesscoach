---
name: Opening Repertoire Feature (Backlog)
description: Show player's opening win rates in Progress page, recommend sticking to 2 best openings, pass opening to Play with Coach as input parameter
type: project
---

**Feature:** Opening repertoire tracking + focused practice

**Progress page addition:**
- Show all openings player has played (from imported games), split by White/Black
- Win/loss record per opening
- Highlight "your best" opening per color
- Coach recommends sticking to top 1-2 openings per color

**Play with Coach integration:**
- Coach receives opening as input parameter
- Steers the game into that specific opening
- Uses opening_theory_tree.json data for coaching during the game
- Teaches the IDEAS behind the opening, not move memorization

**Why:** Real coaches focus students on 1-2 openings. Mastering two openings deeply > knowing ten superficially. This is how 1200s reach 1400.

**How to apply:** This is a backlog item, not current work. Build after the fundamentals coaching engine is done.
