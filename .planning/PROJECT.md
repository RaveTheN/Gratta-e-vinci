# Gratta e Vinci Refactor

## What This Is

A completed structural refactor of the Gratta e Vinci automation app:
- monolith responsibilities split into focused modules,
- duplicate legacy runtime removed,
- key runtime reliability/performance issues addressed while preserving behavior.

## Core Value

Maintainability first: each subsystem is isolated enough that bugs and enhancements can be implemented without navigating a 3000+ line monolith.

## Current State

- **Shipped milestone:** `v1.0 Refactor` (2026-03-10)
- **Milestone archive:** `.planning/milestones/v1.0-ROADMAP.md`
- **Requirements archive:** `.planning/milestones/v1.0-REQUIREMENTS.md`
- **Milestone summary:** `.planning/MILESTONES.md`

## Delivered in v1.0

- Extracted modules: `GameEngine`, `ColorDetector`, `CoordinateManager`, `SettingsManager`
- Consolidated shared config/types and removed `playM.py`
- Hardened critical exception handling and event-based lifecycle signaling
- Added configurable color tolerance and improved unknown-color diagnostics
- Optimized detector pixel reads to region-based capture

## Next Milestone Goals (Draft)

- Define v1.1 scope and requirements from current production feedback
- Add focused test coverage for extracted modules
- Continue hardening deferred items (schema, bounds, timing consistency) if prioritized

## Constraints

- Keep Tkinter GUI stack
- Preserve core behavior unless explicitly scoped as feature work
- Prioritize low-risk incremental improvements over large rewrites

---
*Last updated: 2026-03-10 after v1.0 completion*
