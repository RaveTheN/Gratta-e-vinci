# Bulk Test Mode - Piano di Implementazione (originale)

## Context

L'utente vuole una modalità "Bulk Test" che esegua il TEST mode un numero configurabile di volte e produca una griglia Excel con winrate per ogni combinazione (loss threshold × profit threshold). Prima di avviare il bulk test, l'utente vuole poter modificare dalla UI i 4 parametri fondamentali della simulazione: `BETTING_MODES`, `BET_VALUES`, `WIN_MULTIPLIERS`, `TEST_MODE_MINE_CONFIG`. Queste modifiche sono **locali al bulk test** e non influenzano le impostazioni globali del gioco.

---

## File da modificare

1. `game_engine.py` — Aggiungere logica simulazione bulk (metodi puri, senza toccare `self.app`)
2. `gratta_e_vinci_gui.py` — Aggiungere tab "Bulk Test" + metodi UI
3. `requirements.txt` — Aggiungere `openpyxl`

---

## Architettura

### Problema: stato sul `self.app`
I metodi test esistenti (`_apply_test_win`, `_apply_test_loss`, ecc.) leggono e scrivono su `self.app.*` (la GUI). Per il bulk test servono N simulazioni **indipendenti** senza toccare lo stato UI durante le run.

**Soluzione:** Scrivere una funzione di simulazione **pura** `_run_single_bulk_game(settings_snapshot)` che opera su variabili locali, non su `self.app`. Riutilizza solo `_simulate_test_board()` (già puro) e replica la logica di betting internamente.

---

## Implementazione

### 1. `requirements.txt`
Aggiungere `openpyxl>=3.1.0`.

---

### 2. `game_engine.py` — Metodi da aggiungere a `GameEngine`

#### `run_bulk_test(n_runs, progress_cb, log_cb, stop_check)`
- Legge settings da `self.app` UNA VOLTA all'inizio (snapshot, include i 4 parametri avanzati)
- Calcola `profit_thresholds` e `loss_thresholds` dai settings
  - `profit_thresholds`: step da 1 se target_profit ≤ 100, altrimenti `ceil(target_profit/100)`
  - `loss_thresholds`: step **5**, da 5 fino a `ceil(max_loss / 5) * 5` (arrotonda per eccesso al multiplo di 5 più vicino; se max_loss < 5 → massimo è 5)
- Inizializza `success_counts = {(L, P): 0 for L in loss_thresholds for P in profit_thresholds}`
- Loop `for i in range(n_runs)`:
  - Chiama `_run_single_bulk_game(snapshot)` → restituisce `{profit_threshold: max_dd_when_first_reached}`
  - Accumula in `success_counts`
  - Chiama `progress_cb(i+1, n_runs)` ogni run
  - Chiama `log_cb(...)` ogni run se show_logs abilitato
  - Ogni 2 run: segnala "clear log"
  - Controlla `stop_check()` per stop anticipato
- Restituisce `(success_counts, profit_thresholds, loss_thresholds, snapshot, runs_completed)`

#### `_run_single_bulk_game(snapshot)` → `dict[int, float]`
Simulazione pura (nessun accesso a `self.app` durante il loop):
- Parametri snapshot: starting_cash, target_win, max_loss, max_rounds, mode, betting_sequence, max_picks, difficulty, grinding_enabled, grinding_range, p_random, **win_multipliers** (dict), **mine_config** (dict)
- `p_random` usato nella logica grinding: quando nessun `p` in [1,2,3] copre la recovery e `p_random=True` → picks random(1,3), altrimenti picks=3 (replica `get_grinding_picks()`)
- Tutti i payout calcolati da `snapshot.win_multipliers[difficulty][picks]` (non da WIN_MULTIPLIERS globale)
- Mine count da `snapshot.mine_config[difficulty]` (non da TEST_MODE_MINE_CONFIG globale)
- Loop round-by-round:
  - Determina bet corrente da sequence[tries] (capped all'ultimo step)
  - Se cash < bet: stop (insufficient funds)
  - Deduce bet da cash
  - Chiama `self._simulate_test_board(difficulty, max_picks)` (già puro)
  - Win: cash += bet * multiplier, tries=0, bet=min_bet
  - Loss: tries++, bet=sequence[min(tries, max_step)]
  - Aggiorna `highest = max(highest, cash)`
  - `current_dd = highest - cash`
  - `max_dd_so_far = max(max_dd_so_far, current_dd)`
  - Per ogni profit threshold P non ancora registrato: se `cash - starting_cash >= P` → salva `profit_reached[P] = max_dd_so_far`
  - Stop se: `cash - starting_cash >= target_profit` OR `max_dd_so_far >= max_loss` OR rounds >= max_rounds
- Restituisce `profit_reached`

---

### 3. `gratta_e_vinci_gui.py` — Modifiche

#### Nuove variabili di istanza (in `__init__`)
```python
self.bulk_n_runs_var = tk.IntVar(value=100)
self.bulk_show_logs_var = tk.BooleanVar(value=True)
self.bulk_test_running = False
self.bulk_test_stop = False
self._bulk_results = None  # (success_counts, profit_thresholds, loss_thresholds, snapshot, n)

# Parametri avanzati bulk (override locali, inizializzati dai game_config defaults)
self.bulk_betting_modes = {k: list(v) for k, v in BETTING_MODES.items()}
self.bulk_bet_values = list(BET_VALUES)
# WIN_MULTIPLIERS: dict DoubleVar (diff → picks → DoubleVar)
self.bulk_win_multiplier_vars = {
    d: {p: tk.DoubleVar(value=WIN_MULTIPLIERS[d][p]) for p in [1,2,3,4]}
    for d in ["low", "medium", "high"]
}
# TEST_MODE_MINE_CONFIG: dict IntVar
self.bulk_mine_config_vars = {
    d: tk.IntVar(value=TEST_MODE_MINE_CONFIG[d]) for d in ["low", "medium", "high"]
}
```

#### `create_bulk_test_tab()` — nuovo tab nel notebook
Layout verticale (tab scrollabile via Canvas+Scrollbar se l'altezza lo richiede):

```
┌──────────────────────────────────────────────────────────────┐
│ Bulk Test                                                    │
├──────────────────────────────────────────────────────────────┤
│ Ripetizioni: [____100____]   [Mostra log ☑]                 │
│ [  ▶ AVVIA BULK TEST  ]   [  ■ FERMA  ]                    │
│ Progresso: [███████░░░░░░] 45/100 (45%)                     │
│ Stato: In esecuzione...                                      │
├─ Log (opzionale, nascosto se checkbox spento) ───────────────┤
│ [ScrolledText 8 righe]                                       │
├─ Parametri Avanzati ─────────────────────────────────────────┤
│                                                              │
│ WIN_MULTIPLIERS:                                             │
│              p=1    p=2    p=3    p=4                        │
│   low:     [1.1]  [1.3]  [1.5]  [1.7]                      │
│   medium:  [1.3]  [1.8]  [2.4]  [3.6]                      │
│   high:    [1.6]  [2.7]  [4.8]  [8.7]                      │
│                                                              │
│ MINE_CONFIG (mines per difficulty):                          │
│   low: [3]   medium: [6]   high: [10]                       │
│                                                              │
│ BETTING_MODES:  [✏ Modifica sequenze]                       │
│ BET_VALUES:     [✏ Modifica valori bet validi]              │
│                                                              │
│ [↩ Ripristina defaults]                                      │
├──────────────────────────────────────────────────────────────┤
│ [  💾 ESPORTA EXCEL  ]  (disabilitato finché non completato) │
└──────────────────────────────────────────────────────────────┘
```

Widgets principali:
- `self.bulk_n_runs_entry` — Entry collegato a `bulk_n_runs_var`
- `self.bulk_show_logs_check` — Checkbutton, toggle visibilità `bulk_log_frame`
- `self.bulk_start_button` / `self.bulk_stop_button`
- `self.bulk_progress_var` (DoubleVar), `self.bulk_progress_bar` (ttk.Progressbar)
- `self.bulk_progress_label` — "0/N (0%)"
- `self.bulk_status_label` — stato corrente
- `self.bulk_log_frame` + `self.bulk_log_text` (ScrolledText 8 righe)
- **WIN_MULTIPLIERS**: 12 Entry (DoubleVar) collegati a `bulk_win_multiplier_vars[d][p]`
- **MINE_CONFIG**: 3 Spinbox (IntVar) collegati a `bulk_mine_config_vars[d]`
- **BETTING_MODES button**: apre `open_bulk_betting_modes_editor()`
- **BET_VALUES button**: apre `open_bulk_bet_values_editor()`
- **Reset button**: chiama `reset_bulk_advanced_params()`
- `self.bulk_export_button` — Button ESPORTA EXCEL, inizialmente disabled

#### `start_bulk_test()`
1. Valida N > 0
2. Setta `bulk_test_running=True`, `bulk_test_stop=False`
3. Disabilita start, abilita stop, disabilita export
4. Resetta progress bar e label
5. Spawna daemon thread: `threading.Thread(target=self._bulk_test_worker, daemon=True).start()`

#### `stop_bulk_test()`
- Setta `self.bulk_test_stop = True`
- Aggiorna status label "Interruzione in corso..."

#### `_bulk_test_worker()` (gira nel daemon thread)
- Chiama `self.game_engine.run_bulk_test(n, progress_cb, log_cb, stop_check)`
- Al termine: `self.root.after(0, self._on_bulk_test_complete, results)`

#### `_on_bulk_test_complete(results)`
- `bulk_test_running = False`
- Salva risultati in `self._bulk_results`
- Abilita export button
- Abilita start button, disabilita stop
- Aggiorna status label "Completato N/N - Pronto per export"

#### `_bulk_log_message(msg)` — thread-safe log nel bulk tab
- Solo se `bulk_show_logs_var.get()` è True
- `self.root.after(0, lambda: self.bulk_log_text.insert(END, msg+"\n"))`
- `self.root.after(0, lambda: self.bulk_log_text.see(END))`

#### `_bulk_update_progress(i, n)` — thread-safe progress update
```python
pct = int(i / n * 100)
self.root.after(0, lambda: self.bulk_progress_var.set(i/n*100))
self.root.after(0, lambda: self.bulk_progress_label.config(text=f"{i}/{n} ({pct}%)"))
```

#### `_clear_bulk_log()` — svuota bulk_log_text (chiamato ogni 2 run)
- `self.root.after(0, lambda: self.bulk_log_text.delete("1.0", tk.END))`

#### `open_bulk_betting_modes_editor()`
- Apre finestra modale con editor semplificato (senza vincolo BET_VALUES - qualsiasi float positivo)
- 4 sezioni: normal, medium, high, safe
- Ogni sezione: TextArea con valori separati da virgola
- Pre-popolata da `self.bulk_betting_modes`
- Salva in `self.bulk_betting_modes` al confirm

#### `open_bulk_bet_values_editor()`
- Finestra modale con TextArea pre-popolata da `self.bulk_bet_values` (comma-separated)
- Valida che tutti i valori siano float positivi e univoci
- Salva in `self.bulk_bet_values` al confirm
- Nota UI: "Usato per validazione nel editor BETTING_MODES; non influisce direttamente sulla simulazione"

#### `reset_bulk_advanced_params()`
- Ripristina `bulk_betting_modes`, `bulk_bet_values`, `bulk_win_multiplier_vars`, `bulk_mine_config_vars` ai valori default di `game_config.py`

#### `export_bulk_excel()`
- Prende `self._bulk_results`
- File dialog (`asksaveasfilename`, default `bulk_test_YYYYMMDD_HHMMSS.xlsx`)
- Chiama `_write_excel(filepath, ...)`

#### `_write_excel(filepath, success_counts, profit_thresholds, loss_thresholds, snapshot, n_runs)`
Crea workbook openpyxl con 3 sheet:

**Sheet 1: "Griglia Win Rate"**
- Riga 1 header: "maxloss \ profitto", poi P=1, P=2, ...
- Righe successive: L=5 | % | % | ...
- Valori come percentuale con 1 decimale (es. "90.0%")
- Conditional formatting: 3-color scale verde (100%) → giallo (50%) → rosso (0%)
- Freeze panes: prima riga + prima colonna

**Sheet 2: "Impostazioni"**
- Bankroll iniziale, Target win, Max loss, Max rounds
- Modalità betting, Difficoltà, Max picks
- Grinding on/off, grinding_range, p_random
- N runs eseguiti
- WIN_MULTIPLIERS usati (tabella 3×4)
- MINE_CONFIG usato (3 valori)
- BETTING_MODES usato per il mode selezionato (sequenza)

**Sheet 3: "Sommario"**
- Totale run
- % run che hanno raggiunto il target (profit >= target_profit)
- % run terminate per max_loss
- Matrice riassuntiva delle celle estreme (es. cella [10, 1] e [max_loss, target_profit])

---

## Logica griglia - Semantica precisa

Per ogni run, si raccoglie `profit_reached[P] = max_dd_at_that_point`.

`cell[L][P]` = % di run dove `P in profit_reached AND profit_reached[P] <= L`

In italiano: "la percentuale di run in cui è stato raggiunto P€ di profitto PRIMA che il drawdown superasse L€".

---

## RAM Efficiency

- Nessuna lista per-round in memoria: solo `profit_reached` dict per run (piccolo: len=n_profit_thresholds)
- `success_counts` dict: al massimo `len(loss_thresholds) × len(profit_thresholds)` interi
- Log widget pulito ogni 2 run (se show_logs abilitato)
- Nessun sleep() artificiale nel bulk loop (velocità massima)

---

## Verifica

1. Avviare l'app: `python gratta_e_vinci_gui.py`
2. Configurare: bankroll=2000, target=2020, max_loss=500, mode=normal, difficulty=low, max_picks=3
3. Andare nel tab "Bulk Test", impostare N=100
4. Premere AVVIA BULK TEST - verificare progress bar che avanza
5. Al completamento: premere ESPORTA EXCEL
6. Aprire il file Excel - verificare:
   - Header riga 1: "maxloss \ profitto", poi 1, 2, ..., 20
   - Prima colonna: 5, 10, 15, ..., 500 (step 5)
   - Celle con valori percentuali
   - Colori condizionali verde/rosso
   - Sheet "Impostazioni" con tutti i parametri
7. Testare FERMA durante l'esecuzione - deve fermarsi entro il run corrente
8. Verificare che log venga pulito ogni 2 run (con show_logs abilitato)
9. Modificare WIN_MULTIPLIERS (es. abbassare il moltiplicatore di "low/3"), rieseguire e verificare che i risultati cambino
10. Modificare MINE_CONFIG (es. aumentare le mine "low" da 3 a 8), verificare che la simulazione cambi
11. Modificare una sequenza in BETTING_MODES, verificare che lo snapshot la usi
12. Premere "Ripristina defaults" e verificare che tutti i valori tornino ai game_config defaults
