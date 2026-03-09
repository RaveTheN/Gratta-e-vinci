---
phase: 01-consolidation
plan: 01
subsystem: core
tags: [python, refactoring, code-dedup, shared-module]

# Dependency graph
requires: []
provides:
  - "game_config.py shared module with Point, BETTING_MODES, WIN_MULTIPLIERS, BET_VALUES, color targets, format_money"
  - "Single source of truth for all shared types, constants, and utilities"
affects: [02-extraction, 03-wiring]

# Tech tracking
tech-stack:
  added: []
  patterns: ["flat module with section comment headers", "deep-copy constants on assignment to instance attrs", "thin wrapper for instance methods delegating to module functions"]

key-files:
  created: [game_config.py]
  modified: [gratta_e_vinci_gui.py]

key-decisions:
  - "Used dict() and list() shallow copies when assigning constants to instance attributes to prevent mutation of module-level data"
  - "Kept format_money as thin instance method wrapper to avoid changing 60+ call sites"
  - "Replaced fallback bet_multipliers hardcoded array with BETTING_MODES['normal'] reference"

patterns-established:
  - "Shared constants in game_config.py: all new constants go here"
  - "Deep-copy pattern: {k: list(v) for k, v in BETTING_MODES.items()} when assigning to mutable instance state"

requirements-completed: [CLN-01, CLN-02]

# Metrics
duration: 3min
completed: 2026-03-09
---

# Phase 1 Plan 1: Code Consolidation Summary

**Shared game_config.py module with Point class, 4 betting modes, win multipliers, color targets, and format_money utility -- playM.py deleted**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-09T21:17:08Z
- **Completed:** 2026-03-09T21:20:34Z
- **Tasks:** 2
- **Files modified:** 3 (1 created, 1 modified, 1 deleted)

## Accomplishments
- Created game_config.py as single source of truth for shared types, constants, and utilities
- Removed all duplicate definitions from gratta_e_vinci_gui.py (Point, betting modes, bet values, color targets, format_money)
- Deleted playM.py entirely (543 lines of legacy code)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create game_config.py shared module** - `4e14dc8` (feat)
2. **Task 2: Update GUI imports, remove inline defs, delete playM.py** - `685bd25` (refactor)

## Files Created/Modified
- `game_config.py` - New shared module with Point, BETTING_MODES, BET_VALUES, WIN_MULTIPLIERS, color targets, GRINDING_STEP, test mode constants, format_money
- `gratta_e_vinci_gui.py` - Replaced inline definitions with imports from game_config; format_money instance method now wraps imported function
- `playM.py` - Deleted (git rm)

## Decisions Made
- Used dict()/list() copies when assigning constants to instance attributes to prevent mutation of module-level data
- Kept format_money as thin instance method wrapper (`return format_money(value)`) to avoid changing 60+ self.format_money() call sites
- Replaced hardcoded fallback bet_multipliers in test mode with `BETTING_MODES.get("normal", [0.1])` reference
- Also replaced hardcoded default_modes in editor dialog's reset_to_defaults() local function

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Replaced additional hardcoded betting arrays not listed in plan**
- **Found during:** Task 2 (search for remaining hardcoded arrays)
- **Issue:** Two additional hardcoded betting mode arrays found: one in editor dialog reset_to_defaults() (line 1975) and one in test mode fallback bet_multipliers (line 2800)
- **Fix:** Replaced with BETTING_MODES references
- **Files modified:** gratta_e_vinci_gui.py
- **Verification:** grep confirmed no remaining hardcoded betting arrays
- **Committed in:** 685bd25 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** Essential for completeness of deduplication goal. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- game_config.py is ready to receive additional extracted code in future plans
- GUI file is clean of duplicate constants and imports from shared module
- Zero-import leaf module pattern established for game_config.py

## Self-Check: PASSED

- FOUND: game_config.py
- CONFIRMED DELETED: playM.py
- FOUND: gratta_e_vinci_gui.py
- FOUND: 01-01-SUMMARY.md
- FOUND: commit 4e14dc8
- FOUND: commit 685bd25

---
*Phase: 01-consolidation*
*Completed: 2026-03-09*
