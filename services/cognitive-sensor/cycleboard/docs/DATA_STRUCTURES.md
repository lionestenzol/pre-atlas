# CycleBoard Data Structures

Complete reference for all data structures used in the application.

---

## State Object

The root state object containing all application data.

```javascript
{
  screen: string,              // Current active screen
  AZTask: Task[],              // Array of A-Z tasks
  DayPlans: { [date]: DayPlan }, // Date-keyed day plans
  DayTypeTemplates: { [type]: DayTemplate }, // A/B/C templates
  Routine: { [name]: string[] }, // Named routine step arrays
  Journal: JournalEntry[],     // Journal entries
  FocusArea: FocusArea[],      // Focus areas with tasks
  EightSteps: { [date]: StepProgress }, // Daily 8-step tracking
  Contingencies: ContingencyConfig, // Emergency protocols
  MomentumWins: Win[],         // Quick wins log
  Reflections: { [period]: Reflection[] }, // Period reflections
  History: HistoryData,        // Activity history
  Settings: SettingsConfig,    // User preferences
  UI: UIState                  // UI state (filters, search)
}
```

---

## Task

An A-Z monthly task.

```typescript
interface Task {
  id: string;           // Unique identifier
  letter: string;       // Single letter A-Z
  task: string;         // Task description (max 500 chars)
  notes?: string;       // Optional notes (max 2000 chars)
  status: TaskStatus;   // 'Not Started' | 'In Progress' | 'Completed'
  createdAt: string;    // ISO timestamp
}
```

**Example:**
```json
{
  "id": "abc123def456",
  "letter": "A",
  "task": "Complete project proposal",
  "notes": "Due by end of month",
  "status": "In Progress",
  "createdAt": "2024-01-15T10:30:00.000Z"
}
```

---

## DayPlan

A single day's plan and progress.

```typescript
interface DayPlan {
  date: string;                    // YYYY-MM-DD
  day_type: DayType;               // 'A' | 'B' | 'C'
  baseline_goal: Goal;             // Primary goal
  stretch_goal: Goal;              // Stretch goal
  time_blocks: TimeBlock[];        // Scheduled blocks
  routines_completed: {            // Routine completion status
    [routineName]: RoutineProgress
  };
  activeRoutines?: string[];       // Active routine names
  rating?: number;                 // Day rating 0-5
  notes?: string;                  // Daily notes
}

interface Goal {
  text: string;
  completed: boolean;
}

interface TimeBlock {
  id: string;
  time: string;          // "9:00 AM" format
  title: string;
  duration?: number;     // Minutes
  completed: boolean;
}

interface RoutineProgress {
  completed: boolean;
  steps: { [index: number]: boolean };
}
```

**Example:**
```json
{
  "date": "2024-01-15",
  "day_type": "A",
  "baseline_goal": {
    "text": "Complete 4 deep work blocks",
    "completed": true
  },
  "stretch_goal": {
    "text": "Clear inbox",
    "completed": false
  },
  "time_blocks": [
    {
      "id": "tb001",
      "time": "9:00 AM",
      "title": "Deep Work",
      "duration": 90,
      "completed": true
    }
  ],
  "routines_completed": {
    "Morning": {
      "completed": true,
      "steps": { "0": true, "1": true, "2": true }
    }
  },
  "rating": 4
}
```

---

## DayTemplate

Template for a day type (A, B, or C).

```typescript
interface DayTemplate {
  name: string;              // Display name
  description: string;       // Template description
  timeBlocks: TemplateBlock[]; // Default time blocks
  routines: string[];        // Active routine names
  goals: {
    baseline: string;        // Default baseline goal
    stretch: string;         // Default stretch goal
  };
}

interface TemplateBlock {
  time: string;      // "9:00 AM" format
  title: string;
  duration: number;  // Minutes
}
```

**Example:**
```json
{
  "name": "Optimal Day",
  "description": "Full energy, maximum output",
  "timeBlocks": [
    { "time": "6:00 AM", "title": "Morning Routine", "duration": 60 },
    { "time": "7:00 AM", "title": "Deep Work Block 1", "duration": 90 }
  ],
  "routines": ["Morning", "Commute", "Evening"],
  "goals": {
    "baseline": "Complete 4 deep work blocks",
    "stretch": "Clear inbox + bonus task"
  }
}
```

---

## Routine

Routine definitions stored as named arrays of steps.

```typescript
interface Routines {
  [routineName: string]: string[];
}
```

**Example:**
```json
{
  "Morning": [
    "Wake up at 6 AM",
    "Drink water",
    "Exercise 30 min",
    "Shower",
    "Review today's plan"
  ],
  "Evening": [
    "Review day's accomplishments",
    "Plan tomorrow",
    "Read for 30 min",
    "Prepare for bed"
  ]
}
```

---

## JournalEntry

A journal entry of any type.

```typescript
interface JournalEntry {
  id: string;              // Unique identifier (j + timestamp)
  title: string;           // Entry title (max 200 chars)
  content: string;         // Entry content (max 5000 chars)
  entryType: EntryType;    // 'free' | 'weekly' | 'gratitude'
  tags?: string[];         // Optional tags
  mood?: string;           // Emoji mood indicator
  linkedTasks?: string[];  // Linked task IDs
  timestamp: string;       // ISO timestamp
  createdAt: string;       // ISO creation timestamp
  updatedAt?: string;      // ISO update timestamp
}
```

**Example:**
```json
{
  "id": "j1705312200000",
  "title": "Weekly Review - Week 3",
  "content": "This week was productive...",
  "entryType": "weekly",
  "tags": ["work", "reflection"],
  "mood": "\ud83d\ude0a",
  "linkedTasks": ["abc123"],
  "timestamp": "2024-01-15T10:30:00.000Z",
  "createdAt": "2024-01-15T10:30:00.000Z"
}
```

---

## FocusArea

A focus area with associated tasks.

```typescript
interface FocusArea {
  id: string;
  name: string;
  description?: string;
  color?: string;
  tasks: FocusTask[];
}

interface FocusTask {
  id: string;
  text: string;
  completed: boolean;
  createdAt: string;
}
```

**Example:**
```json
{
  "id": "fa001",
  "name": "Health & Fitness",
  "description": "Physical wellbeing goals",
  "color": "green",
  "tasks": [
    {
      "id": "ft001",
      "text": "Run 3 times this week",
      "completed": false,
      "createdAt": "2024-01-15T10:30:00.000Z"
    }
  ]
}
```

---

## EightSteps

Daily tracking for the 8 Steps to Success.

```typescript
interface EightSteps {
  [date: string]: {
    positiveAttitude?: boolean;
    beOnTime?: boolean;
    bePrepared?: boolean;
    workFullDay?: boolean;
    workTerritory?: boolean;
    greatAttitude?: boolean;
    knowWhy?: boolean;
    takeControl?: boolean;
  };
}
```

**Example:**
```json
{
  "2024-01-15": {
    "positiveAttitude": true,
    "beOnTime": true,
    "bePrepared": true,
    "workFullDay": false,
    "workTerritory": true,
    "greatAttitude": true,
    "knowWhy": true,
    "takeControl": false
  }
}
```

---

## Contingencies

Emergency protocol configurations.

```typescript
interface ContingencyConfig {
  runningLate: Contingency;
  lowEnergy: Contingency;
  freeTime: Contingency;
  disruption: Contingency;
}

interface Contingency {
  actions: string[];
}
```

**Example:**
```json
{
  "runningLate": {
    "actions": [
      "Skip non-essential morning tasks",
      "Notify relevant parties",
      "Focus on top priority only"
    ]
  },
  "lowEnergy": {
    "actions": [
      "Switch to B-Day mode",
      "Do only baseline tasks",
      "Rest when possible"
    ]
  }
}
```

---

## Win

A momentum win entry.

```typescript
interface Win {
  id: string;
  text: string;
  timestamp: string;  // ISO timestamp
  date: string;       // YYYY-MM-DD
}
```

**Example:**
```json
{
  "id": "win001",
  "text": "Finished report ahead of schedule",
  "timestamp": "2024-01-15T14:30:00.000Z",
  "date": "2024-01-15"
}
```

---

## Reflection

A periodic reflection entry.

```typescript
interface Reflections {
  weekly: WeeklyReflection[];
  monthly: MonthlyReflection[];
  quarterly: QuarterlyReflection[];
  yearly: YearlyReflection[];
}

interface BaseReflection {
  id: string;
  timestamp: string;
  mood?: 'excellent' | 'good' | 'neutral' | 'challenging' | 'difficult';
  responses: { [promptId: string]: string };
}

// Weekly prompts: wins, challenges, lessons, priorities
// Monthly prompts: accomplishments, goals_progress, improvements, focus
// Quarterly prompts: milestones, trends, growth, strategy
// Yearly prompts: top5, transformation, gratitude, vision
```

**Example:**
```json
{
  "id": "ref001",
  "timestamp": "2024-01-15T18:00:00.000Z",
  "mood": "good",
  "responses": {
    "wins": "1. Completed project\n2. Started new habit\n3. Good feedback",
    "challenges": "Time management was difficult",
    "lessons": "Need to block time for deep work",
    "priorities": "1. Finish proposal\n2. Exercise daily\n3. Read more"
  }
}
```

---

## History

Activity history data.

```typescript
interface HistoryData {
  completedTasks: TaskCompletion[];
  timeline: Activity[];
}

interface TaskCompletion {
  taskId: string;
  completedAt: string;
}

interface Activity {
  id: string;
  type: ActivityType;
  description: string;
  timestamp: string;
  details?: { [key: string]: any };
}

type ActivityType =
  | 'task_created'
  | 'task_updated'
  | 'task_completed'
  | 'task_deleted'
  | 'time_block_completed'
  | 'focus_task_added'
  | 'focus_task_completed'
  | 'routine_completed'
  | 'goal_achieved'
  | 'journal_created'
  | 'journal_updated'
  | 'journal_deleted'
  | 'day_type_changed'
  | 'template_updated'
  | 'routine_created'
  | 'routine_deleted'
  | 'contingency_activated'
  | 'momentum_win'
  | 'manual_note'
  | 'eight_step_completed';
```

---

## Settings

User preference configuration.

```typescript
interface SettingsConfig {
  darkMode: boolean;      // Dark theme enabled
  autoSave: boolean;      // Auto-save enabled
  showProgress: boolean;  // Show progress indicators
}
```

**Default:**
```json
{
  "darkMode": false,
  "autoSave": true,
  "showProgress": true
}
```

---

## UIState

Transient UI state.

```typescript
interface UIState {
  azFilter: 'all' | 'completed' | 'in-progress' | 'not-started';
  azSearch: string;
}
```

**Default:**
```json
{
  "azFilter": "all",
  "azSearch": ""
}
```

---

## Cognitive State (External)

The cognitive_state.json file structure.

```typescript
interface CognitiveState {
  closure: {
    ratio: number;    // Closure ratio percentage
    open: number;     // Number of open loops
  };
  loops?: OpenLoop[];
}

interface OpenLoop {
  title: string;
  priority?: string;
  dueDate?: string;
}
```

**Example:**
```json
{
  "closure": {
    "ratio": 12,
    "open": 15
  },
  "loops": [
    {
      "title": "Finish quarterly report",
      "priority": "high",
      "dueDate": "2024-01-20"
    }
  ]
}
```

---

## Validation Rules

### Task
- `letter`: Required, single uppercase A-Z
- `task`: Required, max 500 characters
- `notes`: Optional, max 2000 characters
- `status`: Must be valid TASK_STATUS value

### DayPlan
- `date`: Required, YYYY-MM-DD format
- `day_type`: Required, must be A, B, or C
- `rating`: Optional, 0-5

### JournalEntry
- `title`: Required, max 200 characters
- `content`: Required, max 5000 characters

### RoutineStep
- Non-empty string
- Max 200 characters

---

## Storage

All data is stored in localStorage under:
```
cycleboard-state
```

Additional metadata:
```
cycleboard-last-export    // ISO timestamp of last export
cycleboard-export-count   // Number of exports performed
cycleboard-last-import    // ISO timestamp of last import
```

---

## AI Context Structure

The `AIContext.getContext()` method returns a comprehensive snapshot for AI consumption.

```typescript
interface AIContextSnapshot {
  _meta: {
    generatedAt: string;    // ISO timestamp
    version: string;        // App version
    source: string;         // 'CycleBoard AI Context'
  };

  temporal: {
    today: string;          // YYYY-MM-DD
    todayFormatted: string; // Formatted date string
    dayOfWeek: string;      // e.g., 'Monday'
    currentTime: string;    // e.g., '10:30 AM'
  };

  navigation: {
    currentScreen: string;
    availableScreens: string[];
  };

  todayPlan: {
    date: string;
    dayType: DayType;
    dayTypeDescription: string;
    baselineGoal: Goal;
    stretchGoal: Goal;
    timeBlocks: TimeBlock[];
    timeBlocksSummary: {
      total: number;
      completed: number;
      pending: { time: string; title: string }[];
    };
    routinesCompleted: { [name: string]: RoutineProgress };
    notes?: string;
    rating?: number;
  };

  progress: {
    overall: number;        // 0-100 percentage
    breakdown: ProgressItem[];
    timeBlocks: number;
    goals: number;
    routines: number;
    focusAreas: number;
    streak: number;
    weeklyAverage: number;
  };

  tasks: {
    all: Task[];
    summary: {
      total: number;
      notStarted: number;
      inProgress: number;
      completed: number;
      completionPercentage: number;
    };
    byStatus: {
      notStarted: Task[];
      inProgress: Task[];
      completed: Task[];
    };
    availableLetters: string[];  // Unused A-Z letters
  };

  routines: {
    definitions: { [name: string]: string[] };
    routineNames: string[];
    todayCompletion: {
      [name: string]: {
        totalSteps: number;
        completedSteps: number;
        percentage: number;
        isComplete: boolean;
      };
    };
  };

  focusAreas: {
    areas: FocusArea[];
    summary: {
      name: string;
      taskCount: number;
      completedCount: number;
    }[];
  };

  journal: {
    totalEntries: number;
    recentEntries: JournalEntry[];  // Last 10
    entriesByType: {
      free: number;
      weekly: number;
      gratitude: number;
    };
  };

  history: {
    recentActivity: Activity[];    // Last 20
    completedTasksCount: number;
    streak: number;
  };

  weeklyStats: {
    completed: number;
    total: number;
    percentage: number;
  };

  progressHistory: ProgressSnapshot[];  // Last 7 days

  settings: SettingsConfig;

  cognitive: {
    mode: 'BUILD' | 'MAINTENANCE' | 'CLOSURE' | 'OFFLINE';
    risk: 'LOW' | 'MEDIUM' | 'HIGH' | 'UNKNOWN';
    openLoops: OpenLoop[];
    isClosureMode: boolean;
  };

  dayTypeTemplates: { [type: string]: DayTemplate };

  reflections: {
    weekly: number;
    monthly: number;
    quarterly: number;
    yearly: number;
    recent: Reflection[];
  };

  momentumWins: Win[];  // Today's wins
}

interface ProgressItem {
  label: string;
  completed: number;
  total: number;
  percentage: number;
}
```

---

## Quick Context Structure

The `AIContext.getQuickContext()` returns a minimal snapshot:

```typescript
interface QuickContext {
  today: string;           // YYYY-MM-DD
  dayType: DayType;
  overallProgress: number;
  tasksInProgress: number;
  pendingTimeBlocks: number;
  cognitiveMode: string;
  streak: number;
}
```

---

## AI Action Result Structure

All `AIActions` methods return:

```typescript
// Success
interface SuccessResult {
  success: true;
  [key: string]: any;  // Additional data (taskId, entry, etc.)
}

// Failure
interface FailureResult {
  success: false;
  error?: string;      // Single error message
  errors?: string[];   // Multiple validation errors
}
```

---

## AI Activity Types

AI actions log with these activity types:

```typescript
type AIActivityType =
  | 'ai_task_created'
  | 'ai_task_completed'
  | 'ai_task_status_changed'
  | 'ai_task_updated'
  | 'ai_day_type_set'
  | 'ai_goals_set'
  | 'ai_goal_toggled'
  | 'ai_time_block_added'
  | 'ai_time_block_toggled'
  | 'ai_time_block_deleted'
  | 'ai_routine_step_completed'
  | 'ai_routine_completed'
  | 'ai_journal_created'
  | 'ai_momentum_win';
```

All AI activity log entries include `source: 'AI'` in their details.
