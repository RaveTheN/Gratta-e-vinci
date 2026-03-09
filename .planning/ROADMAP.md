# Roadmap: Gratta e Vinci Refactor

## Overview

Transform a 3200-line monolith into 5 focused modules without changing external behavior. First, consolidate shared code and remove the legacy duplicate. Then extract modules one by one from the monolith. Finally, fix known bugs and optimize performance now that the code is structured enough to do so cleanly.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Consolidation** - Eliminate duplicates and establish shared foundations
- [ ] **Phase 2: Module Extraction** - Split monolith into 5 single-responsibility modules
- [ ] **Phase 3: Bug Fixes and Optimization** - Fix known bugs and improve performance on clean codebase

## Phase Details

### Phase 1: Consolidation
**Goal**: All duplicate code is eliminated and shared types/constants live in one place
**Depends on**: Nothing (first phase)
**Requirements**: CLN-01, CLN-02
**Success Criteria** (what must be TRUE):
  1. playM.py no longer exists in the codebase
  2. Point class is defined in exactly one location and imported wherever used
  3. Betting mode constants (normal, medium, high, safe) are defined in exactly one location
  4. The application runs identically to before -- same GUI, same game behavior
**Plans:** 1 plan

Plans:
- [x] 01-01-PLAN.md -- Create game_config.py, update GUI imports, delete playM.py

### Phase 2: Module Extraction
**Goal**: The monolith GUI file delegates all non-UI logic to extracted modules
**Depends on**: Phase 1
**Requirements**: MOD-01, MOD-02, MOD-03, MOD-04, MOD-05
**Success Criteria** (what must be TRUE):
  1. GameEngine module exists as a standalone file handling game loop, round execution, betting strategy, and state management
  2. ColorDetector module exists as a standalone file handling pixel reading, color matching, and tolerance logic
  3. CoordinateManager module exists as a standalone file handling grid calculation, tile positions, and smart grid auto-fill
  4. SettingsManager module exists as a standalone file handling JSON load/save and settings validation
  5. GUIController contains only Tkinter UI code -- all logic calls go through the extracted modules
**Plans**: TBD

Plans:
- [ ] 02-01: TBD

### Phase 3: Bug Fixes and Optimization
**Goal**: Known bugs are fixed and performance is improved, leveraging the clean module structure
**Depends on**: Phase 2
**Requirements**: FIX-01, FIX-02, FIX-03, PERF-01
**Success Criteria** (what must be TRUE):
  1. No bare except clauses remain in the codebase -- all exceptions are specific types with logging
  2. Thread synchronization uses threading.Event instead of boolean flags for escape_pressed and game_running
  3. Color detection debug output shows the same tolerance value actually used in comparison logic
  4. Screenshot capture grabs only the tile region instead of the full screen, reducing capture time
**Plans**: TBD

Plans:
- [ ] 03-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Consolidation | 1/1 | Complete | 2026-03-09 |
| 2. Module Extraction | 0/? | Not started | - |
| 3. Bug Fixes and Optimization | 0/? | Not started | - |
