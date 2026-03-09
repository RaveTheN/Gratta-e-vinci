# Requirements: Gratta e Vinci Refactor

**Defined:** 2026-03-09
**Core Value:** The codebase becomes maintainable — each module has a single responsibility, bugs can be found and fixed without reading 3000+ lines, and future features can be added without fear of breaking unrelated code.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Module Separation

- [ ] **MOD-01**: GameEngine extracted as standalone module — contains game loop, round execution, betting strategy, state management
- [ ] **MOD-02**: ColorDetector extracted as standalone module — contains pixel reading, color matching, tolerance logic
- [ ] **MOD-03**: CoordinateManager extracted as standalone module — contains grid calculation, tile position math, smart grid auto-fill
- [ ] **MOD-04**: SettingsManager extracted as standalone module — contains JSON load/save, settings validation
- [ ] **MOD-05**: GUIController slimmed to UI-only — delegates all logic to extracted modules

### Code Elimination

- [x] **CLN-01**: playM.py deleted from codebase
- [x] **CLN-02**: All duplicate constants, modes, and Point class consolidated into single source of truth

### Bug Fixes

- [ ] **FIX-01**: Bare except clauses replaced with specific exception types and error logging
- [ ] **FIX-02**: Thread safety flags (escape_pressed, game_running) replaced with threading.Event
- [ ] **FIX-03**: Color detection tolerance mismatch fixed — debug output matches actual tolerance value

### Performance

- [ ] **PERF-01**: Screenshot capture uses region grab instead of full-screen capture for pixel color reading

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Hardening

- **HARD-01**: Consolidate all hardcoded sleep durations with configurable pause variables
- **HARD-02**: Add screen bounds validation before pixel reading
- **HARD-03**: Add betting mode schema validation on load

### Testing

- **TEST-01**: Unit tests for game logic (bet calculations, win/loss state transitions)
- **TEST-02**: Unit tests for color detection (tolerance edge cases)
- **TEST-03**: Integration tests for coordinate system (grid auto-calculation)

### Cleanup

- **CLN-03**: Remove duplicate code between modules (shared constants already consolidated in v1)

## Out of Scope

| Feature | Reason |
|---------|--------|
| GUI redesign | Tkinter stays — refactor is structural, not visual |
| New game features | Pure refactor — no behavior changes |
| Cross-platform support | Windows only — no reason to change |
| Multi-account support | Separate feature, not a refactor concern |
| playM.py migration | Deleting entirely — no unique logic worth preserving |
| Framework change | Tkinter is adequate for this use case |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| MOD-01 | Phase 2 | Pending |
| MOD-02 | Phase 2 | Pending |
| MOD-03 | Phase 2 | Pending |
| MOD-04 | Phase 2 | Pending |
| MOD-05 | Phase 2 | Pending |
| CLN-01 | Phase 1 | Complete |
| CLN-02 | Phase 1 | Complete |
| FIX-01 | Phase 3 | Pending |
| FIX-02 | Phase 3 | Pending |
| FIX-03 | Phase 3 | Pending |
| PERF-01 | Phase 3 | Pending |

**Coverage:**
- v1 requirements: 11 total
- Mapped to phases: 11
- Unmapped: 0

---
*Requirements defined: 2026-03-09*
*Last updated: 2026-03-09 after roadmap creation*
