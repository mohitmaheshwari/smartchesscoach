# Data Sources by Page

This document maps each page/component to its data sources and when data is refreshed.

## Pages and Their Data Sources

### Dashboard (HomePage.jsx, Dashboard.jsx)
| Component | API Endpoint | Data Source | Refresh Trigger |
|-----------|--------------|-------------|-----------------|
| Biggest Weakness | `/api/dashboard` | `player_profiles` | Game analysis + data refresh |
| Progress Stats | `/api/dashboard` | `player_profiles` | Game analysis + data refresh |
| Blind Spots | `/api/dashboard` | `player_profiles.mistake_breakdown` | Game analysis + data refresh |
| Thinking Score | `/api/thinking-score` | `thinking_scores` | Game analysis + data refresh |

### Journey Page (Journey.jsx, JourneyV2.jsx)
| Component | API Endpoint | Data Source | Refresh Trigger |
|-----------|--------------|-------------|-----------------|
| Linked Accounts | `/api/journey/linked-accounts` | `linked_accounts` | Manual sync |
| Journey Stats | `/api/journey/v2` | `journey_stats`, `games` | Game analysis + data refresh |
| Daily Reward | `/api/gamification/daily-reward` | `gamification` | Daily reset |
| Focus Mastery | `/api/missions/focus-mastery` | `missions` | Mission completion |
| Evolution | `/api/progress/evolution` | `games`, `game_analyses` | Game analysis |
| Openings Progress | `/api/progress/openings` | `game_analyses` | Game analysis |

### Lab Page (LabV2.jsx)
| Tab | API Endpoint | Data Source | Refresh Trigger |
|-----|--------------|-------------|-----------------|
| Summary | `/api/game/{id}/enriched-analysis` | `game_analyses` | Single game analysis |
| Moments | `/api/game/{id}/enriched-analysis` | `game_analyses.critical_moments` | Single game analysis |
| Habits | `/api/analysis/{id}/opening-fundamentals` | Calculated from `game_analyses` | Single game analysis |
| Memory | `/api/coach/deep-memory` | `player_identities` | Game analysis + data refresh |

### Play with Coach (CoachPlay.jsx)
| Component | API Endpoint | Data Source | Refresh Trigger |
|-----------|--------------|-------------|-----------------|
| Pre-Move Checklist | Local + `/api/thinking-coach/pre-move-checklist` | `player_identities.behavioral_patterns` | Game analysis + data refresh |
| Coach Identity | `/api/coach/play/identity` | `player_identities` | Game analysis + data refresh |

### Training Page
| Component | API Endpoint | Data Source | Refresh Trigger |
|-----------|--------------|-------------|-----------------|
| Recommended Training | `/api/training/recommended` | `player_profiles.biggest_weakness` | Game analysis + data refresh |

## Collections Updated on Game Analysis

When a game is analyzed, the following collections are updated:

1. **`game_analyses`** - The analysis results (move evaluations, critical moments)
2. **`games`** - Game status updated to analyzed
3. **`analysis_queue`** - Job marked complete
4. **`player_identities`** - Recalculated from ALL games (wins, losses, patterns)
5. **`player_profiles`** - Dashboard stats recalculated
6. **`thinking_scores`** - Thinking score calculated for the game
7. **`journey_stats`** - Journey page stats recalculated

## Manual Data Refresh

To manually refresh all data: `POST /api/data/refresh`

This recalculates all aggregated data from the source game analyses.

## Known Issues Fixed

1. **Duplicate player_identities** - Now automatically cleaned up during refresh
2. **Stale consecutive losses** - Now recalculated from game results in order
3. **Missing thinking scores** - Now automatically calculated for all analyzed games
