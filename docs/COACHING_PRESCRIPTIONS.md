# Coaching Prescriptions Feature

**Date**: 2026-07-10  
**Status**: Complete and integrated  
**Replaces**: FocusCard component on HomePage

## Overview

The Coaching Prescriptions feature provides a comprehensive system for personalized training plan recommendations and progress tracking. Players see their active coaching plans with real-time progress metrics, and receive data-driven recommendations for their next focus area based on recent game analysis.

## Architecture

### Frontend Components

#### 1. **CoachingPrescriptions.jsx** (Main Container)
- Orchestrates prescription data fetching and display
- Manages loading, error, and empty states
- Coordinates active prescriptions display + next recommendation
- Location: `/src/components/CoachingPrescriptions.jsx`

**Props**: None (self-contained)

**State**:
- `prescriptions`: Array of active prescriptions
- `nextRec`: Next coach recommendation
- `loading`: Boolean loading state
- `error`: Error message if fetch fails
- `activeCount`: Number of active plans

**Key Features**:
- Automatic data refresh on component mount
- Staggered animations for UI polish
- Graceful error handling with user-friendly messages
- Empty state guidance

#### 2. **PrescriptionCard.jsx** (Individual Plan)
- Displays single prescription with progress tracking
- Shows metrics comparison (baseline vs current)
- Renders module completion status
- Provides action buttons (complete, pause)
- Location: `/src/components/PrescriptionCard.jsx`

**Props**:
```javascript
{
  prescription: {
    prescription_id: string,
    plan_id: string,
    plan_name: string,
    status: 'active' | 'pending' | 'paused' | 'completed',
    issue_detected: string,  // cognitive gap
    reasoning: string,
    baseline_metric: number,
    current_metric: number,
    improvement_pct: number,
    puzzles_completed: number,
    puzzle_accuracy: number,
    expected_completion_date: string (ISO),
    modules_completed: string[],
    created_at: string (ISO),
    updated_at: string (ISO)
  },
  onUpdate: () => void  // Callback when prescription changes
}
```

**Visual Features**:
- Cognitive gap color coding (9 distinct colors per gap type)
- Animated progress bar with smooth easing
- Metrics grid (baseline vs current with improvement %)
- Module completion counter
- Expected completion date
- Error state display

#### 3. **NextRecommendation.jsx** (Coach Recommendation)
- Displays coach's recommended next training plan
- Shows up to 3 alternative plans
- Explains reasoning with evidence (occurrence count, trend)
- Provides action buttons (accept, choose alternative, add parallel)
- Location: `/src/components/NextRecommendation.jsx`

**Props**:
```javascript
{
  recommendation: {
    recommended_plan_id: string,
    plan_name: string,
    reasoning: string,
    issue_severity: string,  // cognitive gap
    occurrence_count: number,
    trend: 'increasing' | 'stable',
    duration_weeks: number,
    weekly_commitment_hours: number,
    alternatives: [
      {
        plan_id: string,
        name: string,
        cognitive_gap: string
      }
    ],
    urgency: 'critical' | 'high' | 'medium' | 'low',
    current_prescriptions_count: number,
    can_add_parallel: boolean
  },
  hasActivePlans: boolean,
  onAccept: () => void
}
```

**Visual Features**:
- Urgency-based styling (red/orange/amber/neutral)
- Evidence display (occurrence count, trend indicator)
- Alternative plans as clickable cards
- Success/error states with animations
- Disabled state for "Add as Parallel" when max plans reached

### Backend Endpoints

All endpoints are in `/api/coaching/` prefix:

#### GET `/api/coaching/current-prescriptions`
Fetches all active and paused prescriptions for the user.

**Query Params**:
- `include_paused` (boolean, optional): Also return paused prescriptions

**Response**:
```json
{
  "current_prescriptions": [
    {
      "prescription_id": "uuid",
      "plan_id": "uuid",
      "plan_name": "string",
      "status": "active|pending|paused|completed",
      "issue_detected": "string",
      "reasoning": "string",
      "baseline_metric": 2.5,
      "current_metric": 1.8,
      "improvement_pct": 28,
      "priority_order": 1,
      "modules_completed": ["mod-1", "mod-2"],
      "current_module": "mod-3",
      "puzzles_completed": 12,
      "puzzle_accuracy": 0.85,
      "started_at": "2026-07-01T10:00:00Z",
      "completed_at": null,
      "expected_completion_date": "2026-07-24T00:00:00Z",
      "notes": "string",
      "created_at": "2026-07-01T10:00:00Z",
      "updated_at": "2026-07-10T15:30:00Z",
      "plan_details": { /* TrainingPlan object */ }
    }
  ],
  "total_active": 1,
  "highest_priority": { /* highest priority prescription */ }
}
```

#### GET `/api/coaching/next-prescription`
Gets the coach's recommendation for the next focus area.

**Response**:
```json
{
  "recommended_plan": {
    "plan_id": "uuid",
    "name": "string",
    "description": "string",
    "cognitive_gap": "string",
    "duration_weeks": 4,
    "weekly_commitment_hours": 3
  },
  "reasoning": "Coach detected 3 occurrences of missed_tactic in your last 10 games.",
  "issue_severity": "missed_tactic",
  "occurrence_count": 3,
  "trend": "increasing|stable",
  "alternatives": [
    {
      "plan_id": "uuid",
      "name": "string",
      "cognitive_gap": "string"
    }
  ],
  "urgency": "critical|high|medium|low",
  "current_prescriptions_count": 1,
  "can_add_parallel": true
}
```

#### POST `/api/coaching/accept-prescription`
User accepts a recommended prescription.

**Request Body**:
```json
{
  "prescription_id": "uuid",
  "start_immediately": true
}
```

**Response**:
```json
{
  "status": "success",
  "message": "Prescription activated successfully",
  "prescription": { /* PrescriptionResponse */ }
}
```

#### POST `/api/coaching/choose-alternative`
User selects a different plan instead of recommendation.

**Request Body**:
```json
{
  "plan_id": "uuid",
  "reason": "optional reason"
}
```

**Response**:
```json
{
  "status": "success",
  "message": "Alternative plan '...' added to your prescriptions",
  "prescription_id": "uuid",
  "prescription": { /* new prescription data */ }
}
```

#### POST `/api/coaching/add-parallel-plan`
Add a second concurrent training plan.

**Request Body**:
```json
{
  "plan_id": "uuid",
  "reason": "optional reason",
  "max_concurrent_plans": 2
}
```

**Response**:
```json
{
  "status": "success",
  "message": "Plan '...' added as parallel training focus",
  "prescription_id": "uuid",
  "active_plans_after": 2,
  "max_concurrent_plans": 2,
  "prescription": { /* new prescription data */ }
}
```

#### GET `/api/coaching/prescription-history`
Get historical record of all prescriptions and status changes.

**Query Params**:
- `status_filter` (optional): Filter by 'completed', 'abandoned', 'paused'
- `limit` (integer, default 50): Maximum entries to return

**Response**:
```json
{
  "history_entries": [
    {
      "prescription": { /* completed/abandoned prescription */ },
      "history": [
        {
          "history_id": "uuid",
          "prescription_id": "uuid",
          "action": "prescribed|activated|completed|abandoned|paused",
          "previous_status": "string",
          "new_status": "string",
          "metric_before": 2.5,
          "metric_after": 1.8,
          "reason": "string",
          "triggered_by": "user|system",
          "timestamp": "2026-07-10T15:30:00Z"
        }
      ]
    }
  ],
  "total_count": 5,
  "status_filter": "completed"
}
```

#### POST `/api/coaching/complete-prescription`
Mark a prescription as completed.

**Request Body**:
```json
{
  "prescription_id": "uuid"
}
```

**Response**: 
```json
{
  "status": "success",
  "message": "Prescription completed successfully",
  "prescription": { /* updated prescription */ }
}
```

#### POST `/api/coaching/pause-prescription`
Pause an active prescription (can be resumed later).

**Request Body**:
```json
{
  "prescription_id": "uuid"
}
```

**Response**:
```json
{
  "status": "success",
  "message": "Prescription paused. You can resume it anytime.",
  "prescription": { /* updated prescription */ }
}
```

## Database Schema

### Collections

#### `user_coaching_prescriptions`
Stores active and historical user prescriptions.

```javascript
{
  prescription_id: string,           // UUID
  user_id: string,
  plan_id: string,                   // Reference to training_plans
  plan_name: string,                 // Denormalized for quick access
  status: 'active'|'pending'|'paused'|'completed'|'abandoned',
  issue_detected: string,            // cognitive_gap type
  reasoning: string,                 // Why this plan was prescribed
  baseline_metric: number,           // Starting point
  current_metric: number,            // Latest measurement
  improvement_pct: number,           // % improvement from baseline
  priority_order: number,            // 1 = highest priority
  modules_completed: string[],       // Array of completed module IDs
  current_module: string | null,     // Currently working module
  puzzles_completed: number,
  puzzle_accuracy: number,           // 0-1 range
  started_at: ISOString | null,
  completed_at: ISOString | null,
  expected_completion_date: ISOString,
  notes: string,
  created_at: ISOString,
  updated_at: ISOString
}
```

**Indexes**:
```javascript
db.user_coaching_prescriptions.createIndex({ user_id: 1, status: 1 })
db.user_coaching_prescriptions.createIndex({ user_id: 1, priority_order: 1 })
```

#### `training_plans`
Master list of available training plans.

```javascript
{
  plan_id: string,                   // UUID
  name: string,
  description: string,
  cognitive_gap: string,             // piece_safety, missed_tactic, etc.
  related_gaps: string[],            // Other gaps this plan helps with
  difficulty: 'beginner'|'intermediate'|'advanced',
  target_rating_min: number,
  target_rating_max: number,
  duration_weeks: number,
  weekly_commitment_hours: number,
  learning_outcomes: string[],
  modules: [
    {
      module_id: string,
      title: string,
      description: string,
      content_type: 'puzzles'|'games'|'lessons',
      duration_minutes: number,
      puzzle_count: number
    }
  ],
  success_criteria: {
    puzzle_accuracy_threshold: number,  // e.g., 0.80 = 80%
    improvement_threshold: number,      // e.g., 25 = 25% improvement
    time_to_completion_weeks: number
  },
  is_active: boolean,
  created_at: ISOString,
  updated_at: ISOString
}
```

#### `coaching_prescription_history`
Audit trail of all prescription changes.

```javascript
{
  history_id: string,                // UUID
  prescription_id: string,
  user_id: string,
  action: 'prescribed'|'activated'|'completed'|'abandoned'|'paused'|'resumed',
  previous_status: string,
  new_status: string,
  metric_before: number | null,
  metric_after: number | null,
  reason: string,
  triggered_by: 'user'|'system'|'coach',
  timestamp: ISOString
}
```

## Integration

### HomePage Update
- Removed `<FocusCard />` component
- Added `<CoachingPrescriptions />` component in its place
- Location: `/src/pages/HomePage.jsx` line 334-340

### Required Database Collections
Ensure these collections exist with proper indexes:
1. `user_coaching_prescriptions`
2. `training_plans`
3. `coaching_prescription_history`

### Environment Variables
No new environment variables required. Uses existing `MONGO_URL` and `DB_NAME`.

## UI/UX Patterns

### Color Coding by Cognitive Gap
```javascript
{
  piece_safety: { bg: "#fef3c7", border: "#fbbf24", text: "#92400e" },     // amber
  missed_tactic: { bg: "#e0e7ff", border: "#a78bfa", text: "#3730a3" },    // indigo
  tactical_oversight: { bg: "#f0fdfa", border: "#2dd4bf", text: "#0d3b35" },// teal
  calculation_depth: { bg: "#fef2f2", border: "#f87171", text: "#7c2d12" }, // rose
  king_safety: { bg: "#dcfce7", border: "#4ade80", text: "#15803d" },      // green
  pawn_structure: { bg: "#fef08a", border: "#eab308", text: "#713f12" },   // yellow
  piece_activity: { bg: "#e9d5ff", border: "#d8b4fe", text: "#581c87" },   // purple
  opening_knowledge: { bg: "#cffafe", border: "#06b6d4", text: "#164e63" },// cyan
  endgame_technique: { bg: "#fecdd3", border: "#fb7185", text: "#831a27" } // red
}
```

### Urgency Indicators
- **Critical**: Red (6+ occurrences) - Immediate action needed
- **High**: Orange (4-5 occurrences) - Important to address
- **Medium**: Amber (2-3 occurrences) - Notice and consider
- **Low**: Gray (1 occurrence) - Optional

### Progress Display
- Animated progress bar shows puzzle completion percentage
- Current metric displayed against baseline with improvement %
- Green indicator (↓) when improvement detected
- Module completion counter with visual dots

## State Management

All state is fetched fresh from the API on component mount. Updates trigger full page reload for simplicity (can be optimized to partial refresh later).

### Data Flow
```
CoachingPrescriptions (container)
├─ fetch /api/coaching/current-prescriptions
├─ fetch /api/coaching/next-prescription
│
├─ PrescriptionCard[] (for each active prescription)
│  ├─ Display progress, metrics, modules
│  ├─ POST complete-prescription on "Complete" click
│  └─ POST pause-prescription on "Pause" click
│
└─ NextRecommendation (if recommendation exists)
   ├─ Display recommended plan + alternatives
   ├─ POST accept-prescription on "Accept" click
   ├─ POST choose-alternative on alternative click
   └─ POST add-parallel-plan on "Add as Parallel" click
```

## Error Handling

### API Errors
- 404 Not Found: Prescription/Plan not found → Show user-friendly error message
- 400 Bad Request: Invalid state transition → Show validation error
- 500 Server Error: Database/processing error → Show generic error with retry option

### Network Errors
- Network timeout → Show error with retry link
- CORS/Auth errors → Redirect to login or show permission error

### Graceful Degradation
- If fetch fails, component renders empty state
- If recommendations unavailable, only shows active prescriptions
- If active prescriptions empty, only shows recommendation
- If both empty, shows helpful guidance message

## Testing

See `/src/components/__tests__/CoachingPrescriptions.test.jsx` for:
- Loading state verification
- Prescription card rendering
- Next recommendation display
- Error handling
- Empty state scenarios
- API integration

**Run tests**:
```bash
npm test -- CoachingPrescriptions
```

## Performance Considerations

1. **Bundle Size**: Components use existing dependencies (framer-motion, lucide-react, shadcn/ui)
2. **API Calls**: 2 parallel requests on mount (current + next)
3. **Re-renders**: Minimal via motion.div optimizations
4. **Animations**: Hardware-accelerated via Framer Motion

## Future Enhancements

1. **Partial Updates**: Refresh prescriptions without full page reload
2. **Resume Paused Plans**: Add endpoint and UI for resuming paused prescriptions
3. **Plan Customization**: Allow users to adjust plan duration/intensity
4. **Insights Analytics**: Show improvement trends over time
5. **Plan Sharing**: Share progress with coach or community
6. **Mobile Optimizations**: Swipe gestures for card actions

## Troubleshooting

### Prescriptions Not Loading
1. Check MongoDB connection and `user_coaching_prescriptions` collection exists
2. Verify user is authenticated (check token/session)
3. Check browser console for API errors
4. Verify backend routes are registered in `server.py`

### Components Not Rendering
1. Check component imports in HomePage.jsx
2. Verify shadcn/ui components are installed
3. Check motion library import
4. Verify API endpoint URLs match backend routes

### Progress Not Updating
1. Ensure puzzle completion updates are sent to backend
2. Check metrics calculation in backend
3. Verify update endpoint is working (test via curl)

## Related Files

- Frontend: `/src/components/CoachingPrescriptions.jsx`
- Frontend: `/src/components/PrescriptionCard.jsx`
- Frontend: `/src/components/NextRecommendation.jsx`
- Frontend: `/src/pages/HomePage.jsx`
- Backend: `/routes/coaching.py`
- Backend: `/server.py` (route registration)
- Tests: `/src/components/__tests__/CoachingPrescriptions.test.jsx`
