# Gratta e Vinci - Automazione GUI

Applicazione standalone con interfaccia grafica per l'automazione del gioco online "Gratta e Vinci", con impostazioni configurabili, visualizzazione coordinate del mouse in tempo reale e strategie di puntata personalizzabili.

---

## Indice

1. [Panoramica](#panoramica)
2. [Architettura del progetto](#architettura-del-progetto)
3. [Requisiti di sistema](#requisiti-di-sistema)
4. [Installazione](#installazione)
5. [Struttura dei file](#struttura-dei-file)
6. [Come funziona](#come-funziona)
7. [Guida all'interfaccia grafica](#guida-allinterfaccia-grafica)
8. [Strategie di puntata](#strategie-di-puntata)
9. [Configurazione delle coordinate](#configurazione-delle-coordinate)
10. [Modalità di gioco](#modalità-di-gioco)
11. [Sistema di rilevamento colori](#sistema-di-rilevamento-colori)
12. [File di configurazione](#file-di-configurazione)
13. [Sicurezza e arresto di emergenza](#sicurezza-e-arresto-di-emergenza)
14. [Risoluzione dei problemi](#risoluzione-dei-problemi)
15. [Note tecniche](#note-tecniche)

---

## Panoramica

Questa applicazione automatizza il gioco online "Gratta e Vinci" controllando il mouse per interagire con il gioco nel browser. Il bot:

- **Clicca automaticamente** sui pulsanti di gioco e sulle tessere del gratta e vinci
- **Rileva i colori** delle tessere scoperte tramite screenshot per determinare vincita o perdita
- **Gestisce la puntata** secondo una strategia di tipo Martingala modificata
- **Monitora le statistiche** in tempo reale (saldo, puntata, round, perdite)
- **Si ferma automaticamente** al raggiungimento degli obiettivi o dei limiti configurati

### Principio di funzionamento

Il gioco presenta una griglia 5×5 di tessere da "grattare". Il giocatore seleziona tessere a caso:
- **Tessera BLU** → scelta positiva (serve il numero di tessere blu impostato per vincere il round)
- **Tessera ROSSA** → round perso immediatamente

Dopo una vincita, la puntata viene resettata al minimo. Dopo una perdita, la puntata viene aumentata secondo la sequenza della modalità selezionata (strategia Martingala).

---

## Architettura del progetto

Il progetto usa Python e Tkinter:

### Implementazione Python (principale)
- **GUI completa** con Tkinter (`gratta_e_vinci_gui.py`)
- **GameEngine** (`game_engine.py`) per loop di gioco, stato e strategia
- **TileHistory** (`tile_history.py`) per storico delle 25 celle, frequenze e confronto delle scelte
- **Bulk Test** (`bulk_simulation.py`, `bulk_export.py`) per simulazioni indipendenti dei tre laptop, confronti e report
- **ColorDetector** (`color_detector.py`) per lettura pixel e classificazione colori
- **CoordinateManager** (`coordinate_manager.py`) per griglia coordinate e recorder
- **SettingsManager** (`settings_manager.py`) per load/save/validazione impostazioni

### Boundary modulo (Phase 2)
- `gratta_e_vinci_gui.py`: UI Tkinter, binding widget, dialog, orchestrazione
- `game_engine.py`: logica runtime e test mode tramite adapter I/O
- `tile_history.py`: registrazione JSONL, analisi per difficoltà e ordini delle celle
- `bulk_simulation.py`: simulazioni Bulk Test e statistiche per configurazione
- `bulk_export.py`: salvataggio risultati JSON ed esportazione Excel
- `bulk_ui.py`: tre configurazioni laptop e confronto di guadagni e perdite
- `color_detector.py`: logica colore riusabile
- `coordinate_manager.py`: calcolo coordinate e recorder
- `settings_manager.py`: persistenza JSON e default/schema merge

---

## Requisiti di sistema

### Software
- **Python 3.8+** 
- **Windows** (testato su Windows 10/11)
- Browser con il gioco Gratta e Vinci aperto e visibile sullo schermo

### Dipendenze Python

| Pacchetto | Versione | Utilizzo |
|-----------|----------|----------|
| `pyautogui` | 0.9.54 | Controllo mouse, screenshot, clic automatici |
| `pynput` | 1.8.1 | Monitoraggio tastiera per il tasto ESC |
| `Pillow` | 10.4.0 | Elaborazione immagini e rilevamento colori |
| `openpyxl` | ≥3.1.0 | Esportazione dei risultati Bulk Test in Excel |

---

## Installazione

### Metodo rapido (Windows)

1. Eseguire il file batch di setup:
   ```cmd
   setup.bat
   ```

2. Avviare l'applicazione:
   ```cmd
   run_gui.bat
   ```

### Metodo manuale

1. **Creare un ambiente virtuale** (consigliato):
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

2. **Installare le dipendenze Python:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Avviare l'applicazione GUI:**
   ```bash
   python gratta_e_vinci_gui.py
   ```

---

### Verifica rapida

Dalla cartella del progetto, verifica GUI, timer, simulazioni ed export Excel senza clic reali e senza salvare le impostazioni:

```cmd
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Struttura dei file

```
Gratta e vinci/
├── gratta_e_vinci_gui.py        # Interfaccia Tkinter e orchestrazione
├── game_engine.py              # Automazione e collegamento alle simulazioni
├── tile_history.py             # Storico delle 25 celle e confronto delle scelte
├── bulk_simulation.py          # Bulk Test, confronto configurazioni e statistiche
├── bulk_export.py              # Risultati JSON e report Excel
├── bulk_ui.py                  # Configurazioni e risultati dei tre laptop
├── game_config.py              # Costanti e tipi condivisi
├── color_detector.py           # Lettura pixel e riconoscimento colori
├── coordinate_manager.py       # Griglia e registrazione coordinate
├── settings_manager.py         # Caricamento, validazione e salvataggio JSON
├── mouseMonitoring.py          # Utility per monitoraggio posizione mouse
├── gratta_settings.json        # File di configurazione (auto-generato/salvato)
├── tile_history.jsonl          # Storico delle tavole reali (creato alla prima registrazione)
├── requirements.txt            # Dipendenze Python
├── run_gui.bat                 # Script avvio rapido Windows
├── setup.bat                   # Script installazione Windows
├── tests/test_smoke.py         # Verifica GUI e simulazione senza clic reali
└── Diagramma senza titolo.drawio  # Diagramma del flusso
```

### Descrizione dettagliata dei file principali

#### `gratta_e_vinci_gui.py`
L'applicazione principale con interfaccia grafica. Contiene:
- Classe `GrattaEVinciGUI` — gestisce l'interfaccia e richiama il motore di gioco
- 8 schede: Settings, Bulk Test, Coordinates, Betting Modes, Inizializzazione, Game Control, Statistics, Pause
- Sistema di salvataggio/caricamento impostazioni in JSON
- Monitoraggio mouse in tempo reale
- Automazione completa del gioco con rilevamento colori

#### `game_engine.py`
Contiene `GameEngine` per automazione e simulazioni e `TkAutomationAdapter` per le azioni sul gioco. La GUI avvia il motore nei thread di lavoro.

#### `mouseMonitoring.py`
Utility semplice per visualizzare le coordinate del mouse in tempo reale nel terminale. Utile per calibrare le posizioni delle tessere:
```bash
python mouseMonitoring.py
```

---

## Come funziona

### Flusso di gioco principale

```
1. INIZIALIZZAZIONE
   ├── Carica impostazioni da gratta_settings.json
   ├── Imposta saldo iniziale
   └── Forza puntata al minimo (clic multipli sul pulsante "diminuisci")

2. CICLO PRINCIPALE (per ogni round)
   ├── Controlla condizioni di arresto:
   │   ├── Round massimi raggiunti?
   │   ├── Obiettivo vincita raggiunto?
   │   ├── Perdita massima raggiunta?
   │   ├── Saldo insufficiente?
   │   └── Tasto ESC premuto?
   │
   ├── [Opzionale] Attesa casuale (1-6 minuti)
   │
   ├── Clicca "GIOCA" → Deduce puntata dal saldo
   │
   ├── SELEZIONE TESSERE (fino al numero di blu richiesto o 1 rossa):
   │   ├── Genera numero tessera casuale (non ripetuto)
   │   ├── Clicca sulla tessera
   │   ├── Cattura screenshot
   │   ├── Legge colore pixel alla posizione della tessera
   │   │
   │   ├── SE BLU:
   │   │   ├── Incrementa contatore tessere blu
   │   │   └── SE abbastanza blu → VITTORIA!
   │   │       ├── Clicca "RISCUOTI"
   │   │       ├── Aggiorna saldo (puntata × moltiplicatore)
   │   │       ├── Resetta puntata al minimo
   │   │       └── Resetta contatore tentativi
   │   │
   │   ├── SE ROSSA:
   │   │   ├── Round PERSO
   │   │   ├── Incrementa contatore tentativi
   │   │   ├── Aumenta puntata secondo la modalità selezionata
   │   │   └── Calcola perdita totale
   │   │
   │   └── SE COLORE SCONOSCIUTO:
   │       ├── Ritenta lettura (max 3 tentativi)
   │       └── Se fallisce, salta la tessera
   │
   └── Incrementa contatore round

3. FINE GIOCO
   └── Mostra statistiche finali
```

### Moltiplicatori di vincita

Quote confermate per **medium**, con **6 mine su 25 celle**. Il moltiplicatore indica il ritorno totale, inclusa la puntata:

| Celle blu da trovare | Ritorno totale | Valore atteso per 100 € puntati |
|---|---|---|
| 2 | 1,8× | +2,600 € |
| 4 | 3,2× | −1,951 € |
| 5 | 4,6× | +0,675 € |
| 6 | 6,8× | +4,177 € |
| 7 | 10× | +4,822 € |
| 8 | 15× | +4,822 € |

Il valore atteso usa tavole uniformi indipendenti: la probabilità di vincere è `C(19, celle) / C(25, celle)`. È una media teorica, non il risultato garantito di una giornata. Le altre quote del modello non sono confermate: verificale in **Regole del gioco** prima di usarle per un confronto.

---

## Guida all'interfaccia grafica

L'interfaccia è organizzata in **8 schede** (tab):

### 1. Scheda Impostazioni (Settings)

#### Coordinate Mouse
In alto viene mostrata la posizione corrente del mouse in tempo reale, aggiornata ogni 100ms.

#### Parametri di Gioco

| Parametro | Descrizione | Valore predefinito |
|-----------|-------------|-------------------|
| **Starting Cash** | Saldo iniziale disponibile | 2001.50 |
| **Target Win** | Obiettivo di vincita (il bot si ferma al raggiungimento) | 2100.00 |
| **Max Loss** | Perdita massima consentita dal picco più alto | 10.00 |
| **Max Rounds** | Numero massimo di round da giocare | 100 |
| **Max Picks** | Tessere blu necessarie: da 1 a 4; anche da 5 a 8 per `medium` | 3 |
| **Betting Mode** | Modalità strategica di puntata | normal |
| **Random Wait** | Attesa casuale tra i round (1-6 minuti) | Disattivato |

#### Punti di Controllo
Coordinate dei pulsanti del gioco sullo schermo:

| Pulsante | Funzione |
|----------|----------|
| **Play/Collect** | Pulsante per iniziare il round / riscuotere la vincita |
| **Raise Bet** | Pulsante per aumentare la puntata |
| **Lower Bet** | Pulsante per diminuire la puntata |

#### Pulsanti
- **Save Settings** — Salva tutte le impostazioni nel file JSON
- **Load Settings** — Carica le impostazioni dal file JSON
- **Reset to Defaults** — Ripristina i valori predefiniti

### 2. Scheda Bulk Test

Il **Bulk Test** ha una scheda dedicata e simula tre laptop senza controllare il mouse. Ogni laptop ha la propria configurazione e giocate casuali indipendenti, anche quando due o tutti e tre hanno impostazioni identiche. Le estrazioni di un laptop non vengono riutilizzate per gli altri; singoli risultati possono comunque coincidere per caso.

#### Impostare i tre laptop

1. Compila i riquadri **Laptop 1**, **Laptop 2** e **Laptop 3**. **Copia da Settings** importa le impostazioni correnti nel solo laptop scelto.
2. Inserisci il numero di **simulazioni per laptop**. Per esempio, 1.000 significa 1.000 sessioni per ciascun laptop, 3.000 in totale.
3. Scegli la cartella dei risultati (predefinita: `bulk_results`) e premi **AVVIA BULK TEST**.

| Campo di ciascun laptop | Significato |
|---|---|
| **Capitale iniziale €** | Saldo disponibile all'inizio di ogni simulazione |
| **Obiettivo guadagno €** | Profitto da raggiungere: con capitale 500 € e obiettivo 3 €, la sessione termina quando il saldo raggiunge almeno 503 € |
| **Limite perdita €** | Calo massimo consentito dal saldo più alto raggiunto nella sessione |
| **Massimo giocate** | Numero massimo di round per simulazione |
| **Modalità** | Sequenza di puntate: `normal`, `medium`, `high`, `safe` o `custom` |
| **Difficoltà** | Livello del gioco: `low`, `medium` o `high` |
| **Caselle da trovare** | Numero di caselle da scoprire per vincere: da 1 a 4; anche da 5 a 8 per `medium` |
| **Grinding** | Attiva il recupero con la modalità grinding; l'intervallo e l'opzione delle caselle casuali si impostano nello stesso riquadro |

Con **Modifica sequenza…** personalizzi la sequenza del singolo laptop. Per le modalità normali inserisci le puntate in ordine, separate da `;`, usando il punto per i decimali. In modalità **custom**, ogni passo ha puntata, caselle e difficoltà proprie: i campi generali di caselle e difficoltà sono disattivati. Modificare una sequenza non modifica quelle degli altri laptop.

Una candidata da confrontare è **custom** con un solo passo: **puntata 0,10 €**, **difficoltà medium**, **6 caselle**, **grinding disattivato**. Il passo unico mantiene la stessa puntata dopo vittorie e sconfitte; con le quote confermate il valore atteso è **+4,177 € ogni 100 € puntati**, ma singole giornate possono perdere. Considera riuscita una giornata con **saldo finale ≥ capitale iniziale**; guarda questa frequenza insieme al netto, non soltanto le giornate vincenti.

**Regole del gioco** apre mine e moltiplicatori comuni ai tre laptop. **Salva configurazioni** conserva i tre riquadri nel normale file delle impostazioni; caricando le impostazioni li ritrovi compilati.

I risultati e le configurazioni salvati conservano i moltiplicatori usati allora: i vecchi risultati **medium, 4 celle, 3,6×** non descrivono le quote reali ora confermate. Prima di un nuovo Bulk Test, in **Regole del gioco** usa **Ripristina defaults** oppure verifica per medium **2 celle: 1,8×; 4: 3,2×; 5: 4,6×; 6: 6,8×; 7: 10×; 8: 15×**.

#### Confronto giornaliero su tre PC

Tra 14 candidate confrontate su 500 giornate, la scelta con meno giornate negative è stata verificata su **10.000 nuove giornate simulate**, con tre PC indipendenti. Nei tre riquadri Bulk Test imposta gli stessi valori: **capitale 1.000 €**, **obiettivo guadagno 0,10 €**, **limite perdita dal picco 50 €**, **massimo 4.000 giocate**, con il passo **custom 0,10 €/medium/6 celle** e **grinding disattivato**.

| Risultato complessivo dei tre PC | Valore osservato |
|---|---|
| Netto medio per giornata | +0,947 € |
| Giornate con saldo complessivo inferiore al capitale iniziale | 121 su 10.000 (1,21%) |
| Peggiore giornata | −46,02 € |

Il modello usa tavole uniformi indipendenti e non include costi: non dimostra che il gioco reale segua queste ipotesi e non garantisce giornate sempre positive. Un confronto con obiettivo **3 € complessivi** ha ottenuto risultati migliori, ma richiede un coordinatore dei tre PC che **non è implementato nel bot**.

Il file [strategia_medium_6_12_ore.json](bulk_results/strategia_medium_6_12_ore.json) conserva la configurazione modello; puoi riportare manualmente i valori nei tre riquadri. **Load Settings** legge `gratta_settings.json`: non apre un selettore per questo file. Nel modello le attese casuali e la pausa fra round sono disattivate, mentre le pause tecniche restano attive; il limite di 4.000 giocate **non è un timer di 12 ore** e la durata reale non è stata misurata.

Per ripetere la ricerca, senza avviare il gioco reale: `.venv\Scripts\python.exe analysis/stable_daily_search.py`. Il [risultato della verifica](bulk_results/stable_daily_search_20261014_153641_632502.json) conserva configurazioni e dettagli.

#### Arresto collettivo e protezione del capitale

Gli script in `analysis` esplorano il coordinatore; **non sono collegati al bot reale**. Le cifre si riferiscono al saldo complessivo dei tre PC, non alla protezione del saldo di ogni singolo laptop.

Con puntata **0,10 € / medium / 6 celle** e massimo **4.000 giocate per PC**, il calcolo con partite completamente liquidate dà circa **0,34% di giornate negative** per obiettivo collettivo 3 €, oppure **0,11%** per obiettivo 1 €. Il confronto considera anche puntate maggiori: con 0,50 € e limite di calo 500 €, solo 4 giornate su 10.000 erano negative, ma la peggiore perdeva **250,60 €**. Frequenza e importo delle perdite vanno letti insieme.

Una variante protegge il capitale **dopo il primo guadagno disponibile**:

1. Il coordinatore deduce subito le puntate aperte dal denaro disponibile, senza aspettarne l'esito.
2. Al primo saldo disponibile superiore al capitale iniziale, consente nuove puntate soltanto se possono essere interamente pagate con gli utili rimasti.
3. Ferma nuove partite a +3 € complessivi, quando gli utili non bastano per un'altra puntata, dopo 4.000 giocate per PC o allo scadere delle 12 ore. Le partite già aperte vengono liquidate.

Verifica della variante su **20.000 nuove giornate**, con tre PC indipendenti in parallelo e limite di calo globale **50 €**:

| Risultato complessivo | Valore osservato |
|---|---|
| Giornate positive / a zero / negative | 18.272 / 1.719 / 9 |
| Netto medio per giornata, costi esclusi | +0,622 € |
| Peggiore giornata | −49,54 € |
| Giornate arrivate ad almeno +3 € | 3.365 |
| Giornate negative dopo l'attivazione della protezione | 0 |

Le nove perdite avvengono prima della protezione: il metodo **non garantisce** di recuperare il capitale durante quella fase. Dopo l'attivazione, la protezione vale nel modello perché tutte le puntate aperte sono già coperte. Per mantenerla nel bot, ogni laptop deve ottenere l'autorizzazione del coordinatore prima di puntare; una puntata dall'esito sconosciuto deve restare impegnata. Il limite di 50 € può essere superato dalle giocate aperte: il limite conservativo di perdita nel modello è **50,30 €**.

Il tempo simulato medio è circa **8 minuti**, ma rete, letture ripetute dei colori e guasti non sono misurati. Il limite di 12 ore blocca nuove puntate; l'ultima liquidazione può terminarne dopo la scadenza. Molte giornate chiudono con pochi centesimi o in pareggio.

Sono disponibili il [confronto degli obiettivi](bulk_results/collective_exact_20261014_155641_617138.json), il [confronto delle puntate](bulk_results/collective_bet_search_20261014_140156_022431Z.json) e la [verifica della protezione con tre PC in parallelo](bulk_results/floorlock_parallel_dd50_20261014_140815_851328.json). I calcoli di probabilità in `analysis/collective_exact.py` e `analysis/collective_floor_lock.py` usano NumPy, già presente nell'ambiente di ricerca.

#### Verifica consolidata: quattro laptop e un master

La configurazione verificata è **0,10 € / medium / 6 celle**, obiettivo giornaliero **+3 € complessivi**, limite di calo globale **500 €**, massimo **4.000 partite per laptop** e **12 ore per avviare nuove partite**. Le puntate aperte sono sempre sottratte dal denaro disponibile prima di autorizzarne altre; si completano dopo l'arresto. È l'arresto collettivo ordinario, senza protezione del capitale dopo il primo utile. Il master non gioca.

La verifica comprende **1.000 mesi indipendenti di 30 giorni**, con **1.000 € iniziali per laptop**. Dentro ogni mese i saldi individuali passano al giorno successivo, senza azzerare perdite, aggiungere denaro o trasferirlo fra PC. L'obiettivo di ogni giornata si misura dal suo saldo iniziale, non dal saldo iniziale del mese.

| Risultato dei 1.000 mesi simulati | Dopo l'elettricità ipotetica |
|---|---|
| Utile medio mensile | 106,73 € |
| Peggiore / migliore mese osservato | 52,25 € / 116,92 € |
| Intervallo contenente circa il 90% dei mesi simulati | 101,00–112,16 € |
| Mesi negativi osservati | 0 su 1.000 |

In queste **30.000 nuove giornate** si osservano **50 giorni negativi**, con peggiore giornata **−48,92 €**. Nessun laptop esaurisce i fondi. Il tempo simulato medio è circa **35 minuti al giorno**. L'elettricità costa mediamente **1,25 € al mese**, ipotizzando **240 W complessivi per tutti e cinque i computer**, **0,30 €/kWh** e accensione limitata alle sessioni; consumi e tariffa non sono misurati. Acquisto, usura, commissioni e imposte sono esclusi. Nessun mese negativo osservato significa soltanto che non è accaduto in questo campione.

Un controllo indipendente genera **500.000 tavole complete da 25 celle**, invece di usare soltanto il generatore rapido delle probabilità. Frequenze e risultati giornalieri sono compatibili con il modello. Questa verifica controlla il simulatore; non dimostra la casualità del sito reale.

Gli stress test mostrano le condizioni fragili: con attese quadruplicate le giornate negative aumentano; se una vittoria da 0,10 € paga realmente **0,65 € totali anziché 0,68 €**, il valore atteso diventa negativo. Anche tavole identiche fra PC aumentano la gravità delle perdite. Con sole sconfitte il limite globale porta all'arresto a circa **−500 €**: questa configurazione non garantisce il capitale iniziale a fine giornata.

Per ripetere la verifica: `.venv\Scripts\python.exe analysis/collective_validation.py`. Sono disponibili il [report mensile con saldi continui](bulk_results/collective_monthly_validation_20261014_145150_933004.json), il [controllo sulle tavole complete](bulk_results/collective_oracle_20261014_145048_106532.json) e gli [stress test](bulk_results/collective_stress_20261014_145040_061131Z.json). Il coordinatore resta simulato e non è collegato al bot reale.

#### Confronto con le nuove quote medium confermate

Con puntata **0,10 €**, i pagamenti totali confermati sono **0,18 € per 2 celle**, **0,68 € per 6**, **1 € per 7** e **1,50 € per 8**. App e Bulk Test supportano ora anche 7 e 8 celle per medium; low e high rimangono limitate alle quote già presenti.

La ricerca confronta **1.000 nuovi mesi di 30 giorni per ciascuna configurazione**, quattro laptop e un master separato, saldi continui senza reintegri, stesso obiettivo **+3 € complessivi**, limite dal picco 500 €, massimo 4.000 partite per laptop e 12 ore per avviare nuove partite. Il netto sottrae l'elettricità ipotetica di 240 W totali a 0,30 €/kWh durante le sessioni.

| Celle | Netto mensile medio | Giornate negative su 30.000 | Peggiore giornata | Peggiore mese netto |
|---|---|---|---|---|
| 2 | 95,68 € | 0 | +3,00 € | 93,36 € |
| 6 | 106,76 € | 44 | −54,36 € | 45,32 € |
| 7 | 109,97 € | 56 | −78,00 € | 27,32 € |
| 8 | 113,56 € | 119 | −104,50 € | 12,18 € |

Nel campione **2 celle** danno il risultato più stabile, con circa 34 minuti di attività media giornaliera. Sette e otto celle hanno lo stesso valore atteso per euro puntato: la differenza degli utili mensili deriva dall'arresto a obiettivo, dall'ultima vincita che lo supera e dalle partite aperte. Otto celle mostrano oscillazioni e perdite maggiori. Nessun mese simulato è negativo, ma i campioni non garantiscono il saldo futuro; consumi reali, commissioni e imposte non sono verificati.

Per ripetere il confronto: `.venv\Scripts\python.exe analysis/compare_medium.py`. Il [report completo delle quattro configurazioni](bulk_results/medium_monthly_comparison_20261014_165311_972068Z.json) conserva anche i singoli mesi e le quote usate. Questa ricerca usa un coordinatore simulato; non avvia giocate reali.

#### Capitale per quattro laptop: verifica di medium con due celle

Per ciascun laptop la configurazione rimane **puntata costante 0,10 €, medium, 2 celle**, senza progressione o grinding. Una vittoria restituisce **0,18 € totali**, quindi guadagna 0,08 €; una sconfitta perde 0,10 €. Il master non gioca. Il coordinatore conserva l'arresto a **+3 € complessivi**, massimo 4.000 partite per laptop e 12 ore per avviarne di nuove.

Il capitale operativo consigliato **nel modello** è **20 € per laptop, 80 € complessivi**. I saldi passano da un giorno al successivo, senza ricariche, trasferimenti o prelievi durante i 30 giorni. Un laptop senza denaro per la puntata successiva conta come un'interruzione anche quando gli altri mantengono il gruppo in utile.

| Capitale iniziale per laptop | Mesi con almeno un laptop senza fondi, su 2.000 percorsi |
|---|---|
| 5 € | 308 |
| 10 € | 5 |
| 15 € | 0 |
| 20 € | 0 |

Questa classificazione usa i saldi minimi dei percorsi con fondi sufficienti; altre 250 repliche mensili per capitale verificano direttamente le stesse classificazioni su tutti gli otto capitali provati. Gli utili dei percorsi con fondi sufficienti non vengono attribuiti ai laptop che avrebbero esaurito il saldo.

Per dare un significato al minimo, è stato adottato un criterio prudente: rischio teorico che **uno qualsiasi dei quattro laptop** scenda sotto 0,10 € dopo una partita inferiore allo **0,01%**. Un [limite matematico conservativo](https://arxiv.org/html/0807.3506) applicato alle probabilità del modello dà **16,37 € per laptop** come prima cifra al centesimo che soddisfa questo criterio; **20 €** è la scelta arrotondata verificata. Non è un minimo assoluto né il deposito minimo richiesto dal sito. Bastano 0,10 € per una sola partita, ma non per sostenere le oscillazioni del mese.

La verifica successiva, indipendente e con 20 € già scelti, comprende **3.000 nuovi mesi / 90.000 giornate**:

| Risultato | Osservato nel campione |
|---|---|
| Mesi con un laptop senza fondi | 0 su 3.000 |
| Mesi complessivamente negativi dopo elettricità ipotetica | 0 su 3.000 |
| Giornate negative | **3 su 90.000** |
| Peggiore giornata complessiva | **−2,68 €** |
| Utile mensile medio dopo elettricità ipotetica | **95,70 €** |
| Peggiore mese dopo elettricità ipotetica | 89,69 € |
| Attività media giornaliera | Circa 34 minuti |

Il costo elettrico medio è 1,22 € al mese, sempre nell'esempio di 240 W per tutti e cinque i PC e 0,30 €/kWh durante le sessioni. Il saldo minimo osservato di un laptop è **2,02 € con una puntata aperta**; in **9 mesi su 3.000** almeno un laptop termina sotto i suoi 20 € iniziali, pur con il gruppo in utile. Il risultato riguarda il gruppo, non la protezione del capitale di ciascun PC. Il campione più ampio corregge l'impressione data dalle precedenti 30.000 giornate senza perdite: **le giornate negative sono possibili**.

La verifica indipendente del generatore confronta 500.000 tavole complete da 25 celle con 500.000 estrazioni del generatore rapido: entrambe sono compatibili con le probabilità previste. Sono tavole sintetiche, non dati del sito. Negli stress test, ridurre artificialmente le vittorie dal 57% al 56% produce 28 giornate negative su 500. Con sole sconfitte tutti gli 80 € si esauriscono: il limite globale di 500 € non protegge un capitale totale di 80 €.

Per ripetere la ricerca: `.venv\Scripts\python.exe analysis/medium_bankroll.py`. Sono disponibili il [report dei capitali e dei 3.000 mesi](bulk_results/medium_two_bankroll_20261014_174734_173881Z.json), il [calcolo indipendente del rischio](bulk_results/medium2_bankroll_lundberg_20261014_174159_785819Z.json), il [controllo delle tavole complete](bulk_results/medium2_independent_boards_20261014_173946_684119Z.json) e gli [stress test per due celle](bulk_results/medium_two_adverse_checks_20261014_173935_135726Z.json). Il coordinatore rimane simulato; casualità reale, consumi, commissioni e tempi online non sono verificati.

#### Due sessioni al giorno con quattro laptop e un master

La variante esegue **due sessioni**, ciascuna con arresto collettivo a **+3 € rispetto al saldo di inizio sessione**. Rimangono medium, 2 celle, puntata costante di 0,10 € e **20 € iniziali per laptop, 80 € totali**. I saldi si conservano fra sessioni e giornate, senza ricariche, trasferimenti o prelievi. Le due sessioni condividono **12 ore complessive**: la seconda riceve solo il tempo rimasto dopo la prima, comprese le partite ancora aperte. Si avvia anche dopo una prima sessione negativa, se resta tempo.

Ogni sessione riparte con il limite di 4.000 giocate per laptop e calo dal picco di 500 €: il massimo teorico giornaliero diventa 8.000 giocate per laptop. Il traguardo nominale è +6 € al giorno, ma non è garantito se una sessione perde o si arresta prima dell'obiettivo. La media può superare il traguardo perché l'ultima vincita può oltrepassarlo e le partite già aperte vengono completate.

| Risultato per il gruppo | Una sessione al giorno | Due sessioni al giorno |
|---|---|---|
| Utile mensile medio dopo elettricità ipotetica | 95,70 € | **191,41 €** |
| Elettricità media mensile ipotetica | 1,22 € | 2,43 € |
| Attività media giornaliera | 34 minuti | **68 minuti** |
| Peggiore mese netto osservato | 89,69 € | 177,83 € |
| Giornate negative su 90.000 | 3 | **1** |
| Peggiore giornata osservata | −2,68 € | **−6,94 €** |

Il nuovo campione comprende **3.000 mesi indipendenti, 90.000 giornate e 180.000 sessioni**; quello con una sessione proviene dalla verifica precedente. Sono campioni separati: le poche perdite osservate non dimostrano che due sessioni siano meno rischiose. Tre sessioni sono negative, ma soltanto una giornata chiude sotto il saldo iniziale. Nessun mese è negativo e nessun laptop esaurisce il capitale. Il giorno più lungo dura 10 ore e 9 minuti; nessuna seconda sessione viene saltata per mancanza di tempo.

Il capitale operativo rimane 20 € per laptop: il limite matematico precedente vale anche continuando a giocare con gli stessi saldi, senza moltiplicarlo per il numero di sessioni. È un limite sul rischio di esaurire i fondi, non una protezione dell'utile già raggiunto. I consumi ipotetici di 240 W per i cinque PC e 0,30 €/kWh sono addebitati soltanto durante le sessioni; l'intervallo fra le due è escluso.

Per ripetere: `.venv\Scripts\python.exe analysis/medium_two_sessions.py`. Il [report delle due sessioni](bulk_results/medium_two_sessions_20261014_185618_103144Z.json) conserva i risultati mensili e distingue sessioni negative, giornate negative e limiti condivisi. Il coordinatore resta simulato; il bot reale non è stato modificato da questa ricerca.

#### Un solo laptop

Con un solo laptop il master non serve. Rimangono **20 € iniziali**, puntata costante **0,10 €/medium/2 celle**, obiettivo **+3 € per sessione**, massimo 4.000 giocate per sessione e 12 ore complessive al giorno per avviare nuove partite. Nelle due sessioni il saldo e il tempo residuo si conservano; non si aggiunge denaro. La ricerca verifica sia una sia due sessioni con **3.000 nuovi mesi di 30 giorni per caso**.

| Configurazione | Utile mensile medio dopo elettricità ipotetica | Attività media al giorno | Giornate negative su 90.000 | Peggiore giornata |
|---|---|---|---|---|
| Un laptop, una sessione | **85,82 €** | Circa 2 ore | 1.797 | −12,28 € |
| Un laptop, due sessioni | **171,44 €** | Circa 4 ore | **1.274** | **−15,44 €** |
| Quattro laptop e master, due sessioni | 191,41 € | Circa 68 minuti | 1 | −6,94 € |

I campioni sono indipendenti. Il laptop singolo deve raggiungere da solo gli stessi +3 € e dispone di 4.000 giocate per sessione, invece delle 16.000 complessive dei quattro laptop. Il guadagno medio resta positivo nel modello, ma il limite arresta più spesso una sessione prima dell'obiettivo. Con due sessioni si osserva circa **una giornata negativa ogni 71**: questa configurazione non soddisfa l'obiettivo di chiudere sempre almeno in pareggio.

Con un laptop e due sessioni nessun mese è negativo e il peggiore mese netto osservato è **126,04 €**. Nessun laptop esaurisce i fondi; il saldo minimo osservato, comprese le puntate aperte, è **2,86 €**. Il limite giornaliero interrompe 496 sessioni; nessuna seconda sessione viene saltata interamente. In 302 giornate l'ultima partita termina dopo le 12 ore, con massimo **5 secondi** aggiuntivi. Il capitale operativo consigliato rimane 20 €; il limite matematico prudente per un solo saldo dà 14,24 € per il criterio di rischio di esaurimento inferiore allo 0,01%, senza garantire utili giornalieri.

L'elettricità costa nell'esempio **0,91 € al mese** con una sessione e **1,81 €** con due, ipotizzando **50 W per il solo laptop**, 0,30 €/kWh e accensione limitata alle sessioni. Cinquanta watt sono un [esempio indicativo riportato da Virginia Tech](https://www.pubs.ext.vt.edu/2901/2901-9014/2901-9014.html), non una misura del portatile dell'utente.

Sono disponibili il [report completo dei due orari con un laptop](bulk_results/medium_one_laptop_20261014_194529_310874Z.json) e il [calcolo indipendente delle probabilità](bulk_results/single_laptop_medium2_math_20261014_193949_065729Z.json). Il generatore di ricerca `analysis.medium_two_sessions.run_research` accetta ora `laptop_count=1`, `sessions_per_day=1` oppure `2` e `total_power_watts=50`; i valori predefiniti precedenti restano quattro laptop e un master. Il bot reale e la sua programmazione non vengono modificati. Casualità, tempi, consumi e commissioni del gioco reale restano da verificare.

#### Sempre le stesse due caselle

La prova seleziona sempre **casella 1, poi casella 2**, su tutti e quattro i laptop. A ogni partita si generano sei nuove mine distinte su 25 celle; ciascun laptop mantiene tavole indipendenti. Rimangono master separato, due sessioni giornaliere da +3 € complessivi ciascuna, puntata 0,10 €, pagamento totale 0,18 €, capitale 20 € per laptop, saldi continui e gli stessi limiti di partite e tempo.

Il confronto su **500.000 tavole** dà **57,051% di vittorie con 1–2 fisse** e **57,0624% scegliendo una coppia casuale**. Le due scelte si confrontano sulla stessa tavola soltanto all'interno di ciascun confronto; i laptop non condividono tavole. Verificando tutte le **177.100 disposizioni possibili delle mine** per tre coppie distinte si ottiene sempre esattamente il 57%: nel modello uniforme scegliere sempre le stesse posizioni non cambia le probabilità. Il calcolo è quello della [selezione senza ripetizione](https://www.itl.nist.gov/div898/software/dataplot/refman2/ch8/hyppdf.pdf).

La simulazione economica usa davvero le posizioni fisse e **74.731.898 tavole complete**: **1.000 nuovi mesi, 30.000 giornate e 60.000 sessioni**.

| Risultato con caselle 1–2 fisse | Osservato |
|---|---|
| Lordo mensile medio | 193,77 € |
| Elettricità ipotetica mensile | 2,44 € |
| Netto mensile medio | **191,33 €** |
| Peggiore mese netto | 181,09 € |
| Giornate negative | **1 su 30.000**, perdita **−2,54 €** |
| Sessioni negative | 4 su 60.000, peggiore −5,92 € |
| Mesi negativi o laptop senza fondi | 0 su 1.000 |
| Attività media giornaliera | Circa 68 minuti |

Il precedente campione indipendente con selezione casuale dava 191,41 € netti medi: la differenza di circa 8 centesimi al mese è compatibile con la variabilità dei campioni e **non dimostra alcun vantaggio delle caselle fisse**. Il costo elettrico mantiene l'ipotesi di 240 W complessivi a 0,30 €/kWh durante le sessioni. Non è presente uno storico reale delle 25 celle, quindi il test non dimostra che il sito distribuisca le mine uniformemente.

Per ripetere: `.venv\Scripts\python.exe analysis/medium_fixed_two.py --months 1000 --workers 4`. Sono disponibili il [report economico delle caselle fisse](bulk_results/medium_fixed_two_20261015_162725_309535Z.json) e il [confronto delle scelte sulle tavole complete](bulk_results/fixed_two_board_comparison_20261015_162347_918012Z.json). Il bot reale e le impostazioni personali non sono stati modificati.

Nel normale Bulk Test ogni simulazione riparte dal capitale indicato: il saldo finale non passa alla simulazione successiva. Il limite di perdita viene controllato **dopo la giocata**, quindi la perdita effettiva può superarlo. Per esempio, partire da 500 €, salire a 550 € e scendere a 520 € significa un calo dal picco di 30 €, pur restando in guadagno di 20 € rispetto alla partenza.

#### Leggere il confronto

Al termine, il primo riepilogo mostra un riquadro per laptop:

| Risultato | Come leggerlo |
|---|---|
| **Guadagni** | Somma dei profitti delle simulazioni chiuse in positivo |
| **Perdite** | Somma delle perdite delle simulazioni chiuse in negativo, espressa come importo positivo |
| **Netto** | Guadagni meno perdite: è quanto il laptop ha prodotto complessivamente nel test |
| **Simulazioni complete** | Quante sessioni sono incluse nel confronto |
| **Giocate totali** | Numero di round giocati nelle sessioni complete; può differire anche quando i laptop raggiungono lo stesso guadagno |
| **Netto medio per simulazione** | Netto diviso per il numero di simulazioni complete |
| **Peggiore simulazione** | Risultato finale più basso fra le simulazioni complete |

Esempio: **Guadagni 274 €**, **Perdite 492 €**, **Netto −218 €**. Il laptop ha perso complessivamente 218 €, anche se molte sessioni erano positive.

Durante il test puoi seguire l'avanzamento e premere **FERMA**. Le sessioni interrotte restano nei dettagli ma sono escluse dal confronto economico e dalla griglia. Un avviso segnala che il confronto è incompleto e che i laptop possono avere un numero diverso di simulazioni concluse.

#### File dei risultati ed Excel

Il programma salva un **JSON completo** e un **Excel**. Il JSON conserva impostazioni e dettagli e si riapre con **Apri risultati salvati**. I nuovi test non producono file SQLite.

L'Excel contiene questi fogli:

| Foglio | Contenuto |
|---|---|
| **Confronto laptop** | Primo riepilogo con guadagni, perdite e netto di ciascun laptop |
| **Griglia Win Rate** | Griglie separate per laptop, con scala colori **rosso → giallo → verde** dalle percentuali più basse alle più alte |
| **Impostazioni** | Parametri, sequenze, mine e moltiplicatori usati nel test |
| **Sommario** | Statistiche e motivi di arresto delle sessioni |
| **Confronto** | Metriche dettagliate dei laptop |
| **Dettaglio simulazioni** | Una riga per sessione: laptop, saldo finale, profitto, giocate e motivo di arresto |
| **Distribuzione profitti** | Frequenze e istogrammi dei risultati finali |

Oltre 10.000 simulazioni totali l'Excel omette le righe del dettaglio per restare consultabile. **ESPORTA DETTAGLI CSV** permette di esportarle separatamente; il JSON contiene sempre tutti i dettagli.

Nella **Griglia Win Rate**, le colonne indicano obiettivi di profitto e le righe limiti di calo dal picco. Una cella `75,0`, nella colonna `5 €` e nella riga `10 €`, significa che il 75% delle sessioni complete ha raggiunto almeno +5 € senza aver prima subito un calo dal picco superiore a 10 €. I colori aiutano a leggere la frequenza: per sapere quanto hai guadagnato o perso usa il **Confronto laptop**. La griglia descrive i percorsi osservati; non riesegue il test con limiti di perdita diversi.

### 3. Scheda Coordinate (Coordinates)

Permette di configurare le posizioni delle 25 tessere sulla griglia 5×5.

#### Sistema Smart Grid
Invece di inserire tutte le 25 coordinate manualmente, è sufficiente definire:

- **Tessera 1** (punto di riferimento): coordinate X e Y complete
- **Tessere 2-5** (riga superiore): solo la coordinata X (la Y è condivisa con la tessera 1)
- **Tessere 6, 11, 16, 21** (colonna sinistra): solo la coordinata Y (la X è condivisa con la tessera 1)

Le restanti 16 tessere vengono **calcolate automaticamente** incrociando le coordinate X e Y conosciute.

```
Layout griglia 5×5:

  Col1    Col2    Col3    Col4    Col5
  (T1.x)  (T2.x)  (T3.x)  (T4.x)  (T5.x)
┌───────┬───────┬───────┬───────┬───────┐
│ T1 📌 │ T2    │ T3    │ T4    │ T5    │ ← Y = T1.y
├───────┼───────┼───────┼───────┼───────┤
│ T6    │ T7    │ T8    │ T9    │ T10   │ ← Y = T6.y
├───────┼───────┼───────┼───────┼───────┤
│ T11   │ T12   │ T13   │ T14   │ T15   │ ← Y = T11.y
├───────┼───────┼───────┼───────┼───────┤
│ T16   │ T17   │ T18   │ T19   │ T20   │ ← Y = T16.y
├───────┼───────┼───────┼───────┼───────┤
│ T21   │ T22   │ T23   │ T24   │ T25   │ ← Y = T21.y
└───────┴───────┴───────┴───────┴───────┘
  📌 = Punto di riferimento (Tile 1)
```

#### Pulsanti utili
- **Reset to Default Grid** — Ripristina la griglia ai valori predefiniti
- **Test Click Tile 1** — Esegue un clic di prova sulla tessera 1 (con ritardo di 1 secondo)
- **Show All Coordinates** — Mostra tutte le 25 coordinate calcolate in una finestra popup

#### Anteprima griglia
In basso è visibile un'anteprima in tempo reale di tutte le 25 coordinate calcolate, aggiornata automaticamente ad ogni modifica.

### 4. Scheda Modalità Puntata (Betting Modes)

Configura le strategie di escalation della puntata dopo le perdite.

#### Selezione modalità
- Combobox per selezionare la modalità attiva
- Pulsante "Refresh Preview" per aggiornare l'anteprima

#### Anteprima corrente
Mostra per la modalità selezionata:
- Numero di step nella progressione
- Puntata iniziale e massima
- Rischio totale (somma di tutte le puntate nella sequenza)
- Progressione completa delle puntate con rischio cumulativo
- Analisi statistica (incremento medio, minimo, massimo)
- Livello di rischio (basso/medio/alto) con bankroll consigliato

#### Pulsanti azione
- **Edit Betting Modes** — Apre l'editor per modificare le sequenze
- **Analyze Modes** — Mostra un'analisi comparativa dettagliata di tutte le modalità
- **Reset to Defaults** — Ripristina i valori predefiniti
- **Export Modes** — Esporta le modalità in un file JSON
- **Import Modes** — Importa le modalità da un file JSON

### 5. Scheda Inizializzazione

Configura la sequenza di azioni da eseguire prima dell'avvio del gioco reale.

### 6. Scheda Controllo Gioco (Game Control)

#### Pulsanti principali

| Pulsante | Funzione |
|----------|----------|
| 🎰 **START GAME** | Avvia l'automazione REALE — il mouse verrà controllato |
| 🛑 **STOP GAME** | Ferma immediatamente l'automazione |
| 🧪 **TEST MODE** | Simula 5 round SENZA controllare il mouse |

#### Analisi delle 25 celle

Nel gruppo **Analisi delle 25 celle** trovi:

- **Registra le 25 celle dopo vittorie e sconfitte**: attivo per impostazione predefinita.
- **Scegli le celle usando lo storico (sperimentale)**: disattivo per impostazione predefinita; normalmente la scelta resta casuale.
- **Mostra analisi celle**: apre una mappa 5×5 con percentuale osservata di rosse, conteggi, numero di tavole valide e confronto fra storico e caso; puoi aggiornarla dalla finestra.

Il gioco deve scoprire automaticamente tutte le 25 celle alla fine del round.
La registrazione riguarda soltanto le partite **reali**: dopo **RISCUOTI** in caso di vittoria, oppure dopo la sconfitta, prima di modificare puntata o difficoltà.
Ogni lettura usa un unico screenshot per i 25 punti; se la tavola non è completa, il bot ripete la lettura per un massimo di 3 tentativi.
In **Pause**, **Attesa scoperta delle 25 celle (s)** (`tile_reveal_delay`) regola l'attesa prima della lettura; il valore predefinito è **1 secondo**.

Lo storico si salva in `tile_history.jsonl`, accanto a `gratta_settings.json`.
Ogni riga contiene i 25 colori (`blue`, `red` o `null`), data e ora UTC, difficoltà, esito `win`/`loss`, identificativi e ordini delle celle stabiliti prima dell'esito.
Frequenze e scelte sono separate per difficoltà: entrano nell'analisi soltanto tavole con 25 colori riconosciuti e il numero atteso di rosse (predefiniti: **3 low, 6 medium, 10 high**).
Le letture parziali o incoerenti vengono salvate, ma escluse dall'analisi.

Le prime **100 tavole valide per ciascuna difficoltà** usano scelte casuali.
Poi, se attivi la scelta da storico, il bot prova prima le celle con minore frequenza passata di rosse; i pareggi sono casuali e tutte le 25 celle compaiono una sola volta nell'ordine.
Per confrontare le scelte, storico e caso preparano due ordini **prima** della nuova tavola e vengono valutati sulla stessa tavola completa.
Il confronto mostra quante volte ciascun ordine avrebbe vinto; non aggiunge giocate reali.

La soglia di 100 tavole non dimostra un vantaggio. Se le tavole sono indipendenti, lo storico non prevede quelle future: leggi il confronto su nuove tavole come un esperimento, senza aspettarti vittorie garantite.
**TEST MODE** e **Bulk Test** usano tavole uniformi indipendenti e non alimentano questo storico.
Il bot sceglie le celle da cliccare; i colori del gioco reale sono determinati dal sito.

#### Controllo log
- **Clear Log** — Cancella il log (con conferma)
- **Export Log** — Esporta il log in un file .txt con timestamp

#### Log di stato
Area di testo scorrevole che mostra in tempo reale:
- Eventi di gioco (inizio round, tessere cliccate, risultati)
- Colori rilevati con valori RGB
- Variazioni di puntata
- Messaggi di errore e avvisi
- Statistiche aggiornate

### 7. Scheda Statistiche (Statistics)

Mostra in tempo reale durante il gioco:

| Statistica | Descrizione |
|------------|-------------|
| 💰 **Current Cash** | Saldo attuale |
| 📈 **Highest Cash** | Saldo più alto raggiunto |
| 🎰 **Current Bet** | Puntata corrente |
| 🔝 **Highest Bet** | Puntata più alta effettuata |
| 🏁 **Rounds** | Numero di round giocati |
| 🔄 **Tries** | Perdite consecutive (si resetta dopo una vincita) |
| 📉 **Total Loss** | Perdita totale dal picco massimo |
| 🎉 **Total Win** | Vincita totale accumulata |

Include una **barra di progresso** che mostra l'avanzamento rispetto al numero massimo di round.

### 8. Scheda Pause

Configura le pause dell'automazione del gioco reale.

---

## Strategie di puntata

L'applicazione utilizza una **strategia di tipo Martingala modificata**: dopo ogni perdita, la puntata viene aumentata secondo una sequenza predefinita. Dopo una vincita, la puntata viene resettata al minimo della sequenza.

### Modalità disponibili

#### Normal (Normale)
```
Sequenza: 0.10 → 0.20 → 0.30 → 0.50 → 0.80 → 1.40 → 2.50 → 4.50 → 8.00 → 14.00 → 20.00
Step: 11 | Rischio totale: 52.30
```
Progressione moderata con incrementi graduali. Buon bilanciamento tra rischio e recupero.

#### Medium (Media)
```
Sequenza: 0.10 → 0.20 → 0.30 → 0.50 → 0.90 → 1.50 → 3.00 → 5.00 → 9.00 → 15.00 → 20.00
Step: 11 | Rischio totale: 55.50
```
Simile alla normale ma con incrementi leggermente superiori nei livelli medi.

#### High (Alta)
```
Sequenza: 0.20 → 0.30 → 0.60 → 1.00 → 1.80 → 3.00 → 5.00 → 9.00 → 16.00 → 20.00
Step: 10 | Rischio totale: 56.90
```
Parte da una puntata più alta e ha meno step. Più aggressiva, adatta a bankroll elevati.

#### Safe (Sicura)
```
Sequenza: 0.10 → 0.10 → 0.20 → 0.30 → 0.50 → 1.00 → 1.80 → 3.00 → 5.00 → 9.00 → 15.00 → 20.00
Step: 12 | Rischio totale: 56.00
```
Parte con due puntate minime consecutive. Più step, progressione più lenta. Adatta a sessioni lunghe.

### Valori di puntata consentiti

Le puntate nella sequenza devono essere scelte tra questi valori:
```
0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00,
1.20, 1.40, 1.50, 1.60, 1.80, 2.00, 2.50, 3.00, 3.50, 4.00,
4.50, 5.00, 6.00, 7.00, 8.00, 9.00, 10.00, 12.00, 14.00, 16.00,
18.00, 20.00, 25.00
```

### Come funziona l'escalation

1. Si parte dal primo valore della sequenza (es. 0.10 per la modalità "normal")
2. Dopo ogni **perdita**, il contatore `tries` aumenta di 1
3. La puntata viene impostata al valore in posizione `tries` nella sequenza
4. Se `tries` supera la lunghezza della sequenza, si usa l'ultimo valore (massimo)
5. Dopo una **vincita**, `tries` viene resettato a 0 e la puntata torna al minimo

### Editor delle modalità

L'editor (accessibile dalla scheda "Betting Modes") permette di:
- Modificare le sequenze inserendo valori separati da virgola
- Validazione automatica: i valori devono appartenere alla lista consentita
- Ordinamento automatico in ordine crescente al salvataggio
- Import/export delle modalità personalizzate in formato JSON

---

## Configurazione delle coordinate

### Procedura di calibrazione

1. **Aprire il gioco** nel browser e posizionare la finestra
2. **Avviare l'applicazione** GUI
3. **Andare alla scheda Impostazioni** e usare il display delle coordinate mouse
4. **Posizionare il mouse** su ogni elemento del gioco e annotare le coordinate:
   - Pulsante **Gioca/Riscuoti**
   - Pulsante **Aumenta puntata**
   - Pulsante **Diminuisci puntata**
5. **Andare alla scheda Coordinate** per configurare la griglia delle tessere:
   - Posizionare il mouse sulla **tessera 1** (angolo in alto a sinistra) e inserire X e Y
   - Posizionare il mouse sulle **tessere 2-5** (riga superiore) e inserire le X
   - Posizionare il mouse sulle **tessere 6, 11, 16, 21** (colonna sinistra) e inserire le Y
6. **Verificare** con "Show All Coordinates" che le posizioni siano corrette
7. **Testare** con "Test Click Tile 1" per verificare che il clic avvenga nella posizione giusta
8. **Salvare** le impostazioni

### Utility mouseMonitoring.py

Per una calibrazione più precisa, è possibile usare lo script dedicato:
```bash
python mouseMonitoring.py
```
Questo stampa nel terminale la posizione del mouse ogni 100ms. Premere `Ctrl+C` per fermare.

---

## Modalità di gioco

### Gioco reale (START GAME)

⚠️ **ATTENZIONE**: Questa modalità controlla effettivamente il mouse!

1. L'applicazione chiede conferma prima di iniziare
2. Il mouse viene spostato e cliccato automaticamente
3. Il bot interagisce con il gioco reale nel browser
4. Le tessere vengono cliccate e i colori vengono rilevati dallo screenshot
5. La puntata viene gestita automaticamente secondo la strategia selezionata
6. Il gioco si ferma automaticamente quando una condizione di arresto viene soddisfatta

**Prerequisiti**:
- La finestra del gioco deve essere visibile e nella posizione corretta
- Le coordinate devono essere calibrate correttamente
- Non muovere il mouse durante l'automazione

### Modalità test (TEST MODE)

🧪 Modalità sicura per verificare la strategia senza rischi.

1. **Non controlla il mouse** — nessuna interazione con il gioco reale
2. Simula 5 round su tavole uniformi indipendenti, secondo la difficoltà e il numero di celle da trovare
3. Applica la stessa logica di puntata del gioco reale
4. Mostra risultati e statistiche alla fine
5. Utile per:
   - Verificare che le impostazioni siano corrette
   - Testare nuove strategie di puntata
   - Capire il comportamento dell'escalation delle puntate

---

## Sistema di rilevamento colori

Il bot determina il risultato di ogni tessera leggendo il colore del pixel alla posizione della tessera dopo il clic.

### Colori target

| Colore | RGB Target | Significato |
|--------|------------|-------------|
| **Blu** | (1, 108, 238) | Tessera positiva — incrementa il contatore |
| **Rosso** | (200, 13, 1) | Tessera negativa — round perso |

### Tolleranza
La corrispondenza dei colori utilizza una **tolleranza di ±50** su ciascun canale RGB:
```
|colore_rilevato.R - colore_target.R| ≤ 50  E
|colore_rilevato.G - colore_target.G| ≤ 50  E
|colore_rilevato.B - colore_target.B| ≤ 50
```

### Meccanismo di retry
Se il colore rilevato non corrisponde né al blu né al rosso:
1. Attende 1 secondo
2. Fa un nuovo screenshot
3. Rilegge il colore
4. Dopo 3 tentativi falliti, salta la tessera e passa alla successiva

### Perché pixel e non OCR?
La versione corrente usa il rilevamento colori pixel anziché OCR (Tesseract) perché:
- **Più veloce**: leggere un singolo pixel è istantaneo vs. analizzare un'immagine con OCR
- **Più affidabile**: i colori del gioco sono consistenti, il testo OCR può avere errori
- **Più semplice**: non richiede configurazione di Tesseract né file di training

---

## File di configurazione

### gratta_settings.json

Le impostazioni vengono caricate automaticamente da questo file JSON e salvate manualmente tramite il pulsante "Save Settings". Struttura:

```json
{
  "starting_cash": 22.52,           // Saldo iniziale
  "target_win": 24.0,               // Obiettivo vincita
  "max_loss": 1.8,                  // Perdita massima
  "max_rounds": 100,                // Round massimi
  "max_picks": 3,                   // Celle da trovare (1-4; anche 5-8 per medium)
  "mode": "normal",                 // Modalità puntata
  "wait_selected": false,           // Attesa tra round
  "play_x": 1448,                   // Coordinata X pulsante Gioca
  "play_y": 811,                    // Coordinata Y pulsante Gioca
  "raise_x": 1328,                  // Coordinata X pulsante Aumenta
  "raise_y": 852,                   // Coordinata Y pulsante Aumenta
  "lower_x": 1184,                  // Coordinata X pulsante Diminuisci
  "lower_y": 852,                   // Coordinata Y pulsante Diminuisci
  "tiles": {                        // Coordinate tessere (griglia 5×5)
    "1": [1227, 482],
    "2": [1291, 482],
    ...
    "25": [x, y]
  },
  "betting_modes": {                // Modalità di puntata personalizzate
    "normal": [0.1, 0.2, ...],
    "medium": [...],
    "high": [...],
    "safe": [...]
  }
}
```

Il file viene:
- **Caricato automaticamente** all'avvio dell'applicazione
- **Salvato manualmente** tramite il pulsante "Save Settings"
- **Non salvato automaticamente** alla chiusura (per evitare sovrascritture accidentali)

---

## Sicurezza e arresto di emergenza

### Meccanismi di arresto

| Metodo | Come | Quando usarlo |
|--------|------|---------------|
| **Tasto ESC** | Premere il tasto Escape sulla tastiera | Arresto rapido durante il gioco reale (START GAME) |
| **Pulsante STOP** | Cliccare "STOP GAME" nella GUI | Quando l'interfaccia è accessibile |
| **Failsafe pyautogui** | Spostare il mouse nell'angolo in alto a sinistra dello schermo | Emergenza — arresto immediato con eccezione |

### Condizioni di arresto automatico

Il bot si ferma automaticamente quando:
1. **Round massimi** raggiunti (`max_rounds`)
2. **Obiettivo vincita** raggiunto (`current_cash >= target_win`)
3. **Perdita massima** raggiunta (`loss >= max_loss`, calcolata come differenza dal picco massimo)
4. **Saldo insufficiente** per la puntata corrente (`current_cash < bet`)

### Consigli di sicurezza

1. **Usare sempre la modalità TEST** prima del gioco reale per verificare le impostazioni
2. **Impostare limiti ragionevoli** per perdita massima e round massimi
3. **Non lasciare il bot incustodito** per periodi prolungati
4. **Verificare le coordinate** ogni volta che si sposta o ridimensiona la finestra del gioco
5. **Salvare le impostazioni** dopo ogni calibrazione riuscita

---

## Risoluzione dei problemi

### Il bot non clicca nella posizione giusta
- Verificare che la finestra del gioco non sia stata spostata o ridimensionata
- Ricalibrare le coordinate usando il display delle coordinate mouse
- Usare "Test Click Tile 1" per verificare
- Controllare la risoluzione dello schermo e il fattore di scala (DPI)

### Il rilevamento colori non funziona
- Verificare che le tessere siano completamente visibili (non coperte da altre finestre)
- Controllare i valori RGB nel log — potrebbero essere diversi a causa di:
  - Scala dello schermo diversa dal 100%
  - Modalità notturna / filtro luce blu attivo
  - Tema del browser diverso
- Provare ad aumentare la tolleranza nel codice

### L'applicazione non si avvia
- Verificare che Python 3.8+ sia installato
- Verificare che tutte le dipendenze siano installate: `pip install -r requirements.txt`
- Su Windows, potrebbe essere necessario eseguire come amministratore per il controllo del mouse

### Il tasto ESC non ferma il gioco
- Assicurarsi che la finestra dell'applicazione GUI sia attiva
- Il listener della tastiera `pynput` potrebbe non funzionare con alcune configurazioni di sicurezza
- Usare il failsafe di pyautogui (spostare il mouse nell'angolo in alto a sinistra)

### Errore "Insufficient cash"
- Verificare che il **Starting Cash** corrisponda al saldo effettivo nel gioco
- La puntata corrente potrebbe essere più alta del saldo disponibile dopo perdite consecutive

---

## Note tecniche

### Threading
L'applicazione usa thread separati per:
- **Monitoraggio mouse** — thread daemon che aggiorna le coordinate ogni 100ms
- **Loop di gioco** — thread daemon con event loop `asyncio` per le operazioni asincrone
- **Keyboard listener** — thread `pynput` per il rilevamento del tasto ESC

### Arrotondamento
Tutti i valori monetari vengono arrotondati a 2 decimali usando `round(value, 2)` per evitare errori di floating point. Il formato di visualizzazione usa `f"{value:.2f}"` per garantire sempre 2 cifre decimali.

### Precisione temporale
I ritardi tra le operazioni (clic, lettura colori) sono calibrati per dare tempo al gioco di aggiornare lo schermo:
- **1 secondo** tra un clic e la lettura del colore
- **1 secondo** prima di ogni clic su tessera
- **0.05 secondi** tra i clic rapidi (diminuzione forzata della puntata)
- **2 secondi** prima di aumentare la puntata dopo una perdita

### Limitazioni note
- Funziona solo con la finestra del gioco visibile sullo schermo (non funziona minimizzata)
- Le coordinate sono specifiche per risoluzione e posizione della finestra
- Non gestisce popup o finestre di dialogo del gioco
- Il rilevamento colori può fallire con scale DPI diverse dal 100%
- Richiede che il gioco sia nella lingua e nel layout previsti

### 🛡️ Risk Management
- Set reasonable **max loss** limits
- Use **target win** amounts to lock in profits
- Monitor **highest bet** to control risk escalation
- Review **statistics** regularly during play
