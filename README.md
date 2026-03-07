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
- **Tessera BLU** → scelta positiva (servono 2 o 3 tessere blu per vincere il round)
- **Tessera ROSSA** → round perso immediatamente

Dopo una vincita, la puntata viene resettata al minimo. Dopo una perdita, la puntata viene aumentata secondo la sequenza della modalità selezionata (strategia Martingala).

---

## Architettura del progetto

Il progetto ha due implementazioni principali:

### Implementazione Python (principale)
- **GUI completa** con Tkinter (`gratta_e_vinci_gui.py`)
- **Motore di automazione** con `pyautogui` per il controllo del mouse
- **Rilevamento colori** tramite screenshot e lettura pixel

### Implementazione JavaScript (legacy)
- Versione precedente con `nut-js` per il controllo del mouse
- OCR con `tesseract.js` per la lettura del testo su schermo
- Non più attivamente sviluppata

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
| `pytesseract` | 0.3.10 | OCR (opzionale, non usato nella versione corrente) |
| `opencv-python` | 4.8.1.78 | Elaborazione immagini (opzionale) |
| `pynput` | 1.8.1 | Monitoraggio tastiera per il tasto ESC |
| `Pillow` | 10.4.0 | Elaborazione immagini e rilevamento colori |
| `numpy` | 1.24.3 | Operazioni numeriche (opzionale) |

### Dipendenze JavaScript (legacy)

| Pacchetto | Utilizzo |
|-----------|----------|
| `@nut-tree-fork/nut-js` | Controllo mouse nativo |
| `jimp` | Elaborazione immagini |
| `screenshot-desktop` | Cattura schermo |
| `tesseract.js` | OCR per lettura testo |

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

### Installazione dipendenze JavaScript (opzionale)
Solo se si desidera usare la versione JavaScript legacy:
```bash
npm install
```

---

## Struttura dei file

```
Gratta e vinci/
├── gratta_e_vinci_gui.py       # Applicazione GUI principale (Tkinter, ~1900 righe)
├── playM.py                    # Motore di automazione Python (logica di gioco completa)
├── playM.js                    # Implementazione JavaScript (legacy)
├── autoplay.js                 # Script JavaScript con OCR (legacy)
├── mouseMonitoring.py          # Utility per monitoraggio posizione mouse
├── gratta_settings.json        # File di configurazione (auto-generato/salvato)
├── requirements.txt            # Dipendenze Python
├── package.json                # Dipendenze JavaScript (legacy)
├── run_gui.bat                 # Script avvio rapido Windows
├── setup.bat                   # Script installazione Windows
├── eng.traineddata             # Dati OCR per Tesseract (lingua inglese)
├── test_playM_safe.py          # Test unitari (versione safe)
├── test_playM_safe_fixed.py    # Test unitari (versione corretta)
├── test_coordinates.py         # Test delle coordinate
├── test_setup.py               # Test di configurazione
├── TESTING_GUIDE.md            # Guida ai test
├── ROUNDING_FIX.md             # Documentazione fix arrotondamenti
└── Diagramma senza titolo.drawio  # Diagramma del flusso
```

### Descrizione dettagliata dei file principali

#### `gratta_e_vinci_gui.py`
L'applicazione principale con interfaccia grafica. Contiene:
- Classe `GrattaEVinciGUI` — gestisce tutta l'interfaccia e la logica di gioco
- Classe `Point` — rappresenta una posizione (x, y) sullo schermo
- 5 schede (tab): Impostazioni, Coordinate, Modalità Puntata, Controllo Gioco, Statistiche
- Sistema di salvataggio/caricamento impostazioni in JSON
- Monitoraggio mouse in tempo reale
- Automazione completa del gioco con rilevamento colori

#### `playM.py`  
Versione standalone (senza GUI) del motore di automazione. Può essere eseguito direttamente da terminale:
```bash
python playM.py
```
Contiene la stessa logica di gioco della GUI ma con coordinate e impostazioni hardcoded.

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
   ├── SELEZIONE TESSERE (fino a 2-3 blu o 1 rossa):
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

| Tessere da trovare (Max Picks) | Moltiplicatore |
|-------------------------------|----------------|
| 2 tessere blu | 1.8× |
| 3 tessere blu | 2.4× |

**Esempio**: con puntata di 1.00€ e 3 picks, una vincita restituisce 1.00 × 2.4 = 2.40€ (profitto netto di 1.40€).

---

## Guida all'interfaccia grafica

L'interfaccia è organizzata in **5 schede** (tab):

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
| **Max Picks** | Tessere blu necessarie per vincere (2 o 3) | 3 |
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

### 2. Scheda Coordinate (Coordinates)

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

### 3. Scheda Modalità Puntata (Betting Modes)

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

### 4. Scheda Controllo Gioco (Game Control)

#### Pulsanti principali

| Pulsante | Funzione |
|----------|----------|
| 🎰 **START GAME** | Avvia l'automazione REALE — il mouse verrà controllato |
| 🛑 **STOP GAME** | Ferma immediatamente l'automazione |
| 🧪 **TEST MODE** | Simula 5 round SENZA controllare il mouse |

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

### 5. Scheda Statistiche (Statistics)

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
2. Simula 5 round con probabilità di vincita del 60%
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
  "max_picks": 3,                   // Tessere da trovare (2 o 3)
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
| **Ctrl+C** | Nel terminale (solo versione `playM.py`) | Quando si esegue da riga di comando |

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
