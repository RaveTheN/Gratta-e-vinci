# Mine · Client laptop

Client leggero per Windows 10/11 a 64 bit. Esegue i click autorizzati dal master sulla stessa rete locale e conserva un registro recuperabile. Ricerca e simulatore HTML restano strumenti separati.

## Pacchetti portatili

Estrarre **tutta** la cartella dello ZIP e avviare `MineLaptop.exe`. Non servono Python né un'installazione. Il progetto master è nella cartella sorella `../Gratta e vinci Master`; per aprirli insieme usare `../Gratta e vinci.code-workspace`.

1. Nel client, **Verifica / rettifica saldo** richiede il credito reale corrente del gioco: il campo iniziale è vuoto, senza una dotazione proposta. Un client nuovo o azzerato conserva 0,00 € non confermati e non può partire prima della verifica. Per un credito sul sito di `1,999.91`, inserire `1,999.91`, `1.999,91` oppure `1999,91`: valgono tutti 1.999,91 €.
2. Impostare nome e puntata. Default: 6 mine, due celle, pagamento totale 1,80×, puntata 0,10 €. A ogni abilitazione manuale del laptop, dopo il reset e l'impostazione della puntata e prima del **primo Gioca**, il client esegue quattro click su **Abbassa difficoltà** e uno su **Alza difficoltà** per impostare **Medium una sola volta**. Le partite successive ripartono da Gioca, senza ripetere quei cinque click. Non legge né verifica automaticamente la difficoltà o il moltiplicatore mostrati dal gioco: controllarli prima di abilitare il laptop.
3. **Calibrazione**: registrare i nove riferimenti della griglia e i cinque pulsanti Gioca/incassa, Alza e Abbassa puntata, Alza e Abbassa difficoltà. Entrambi i riferimenti della difficoltà sono obbligatori. Salvare la calibrazione sul monitor principale. È possibile importare il vecchio JSON: resta invariato; vengono recuperati anche `lower_diff_x/y` e `raise_diff_x/y`, se presenti. Se mancano, calibrare soltanto i due nuovi punti senza cancellare gli altri riferimenti, poi salvare e confermare la geometria.
4. In **Cambio/reset puntata** conservare o modificare la sequenza, i valori reali dei pulsanti e i colori. I valori delle puntate sono importi del sito, non una progressione. Il primo deve essere il minimo fisico ottenibile con Abbassa. La scheda **Tempi** contiene tutte le attese, spiegate nel punto del flusso in cui vengono applicate.
5. Avviare `MineMaster.exe`: nel pannello scegliere **Associa laptop → Genera codice monouso → Copia codice**. Incollare l'intero codice nel campo **Associazione** del client e premere **Associa codice del master**. Se il saldo non è confermato, viene richiesto in questo momento. **Abilita questo laptop** si abilita dopo l'associazione. Dopo un errore di rete riprovare anche lasciando vuoto il campo: la richiesta salvata viene recuperata senza creare un'altra identità. Se il codice è scaduto oppure appartiene a un'altra istanza del master, generare un nuovo codice e incollarlo: sostituisce il tentativo incompleto, mantenendo identità e credenziale. Un'associazione già completata non viene sostituita.
6. Verificare finestra, zoom, profilo, credito e coordinate; spuntare la conferma e premere **Abilita questo laptop**. Questo abilita la preparazione iniziale: reset puntata, puntata richiesta, poi Medium una sola volta. Lasciare libera e visibile la finestra del gioco, quindi usare **Avvia nuova sessione** dal master.

Le quattro schede sono **Stato**, **Calibrazione**, **Cambio/reset puntata** e **Tempi**. Non sono presenti Bulk Test, grinding o sequenze strategiche. Si selezionano sempre due celle distinte, casuali oppure fisse; alla prima mina la partita termina, dopo due esiti blu viene premuto Incassa. Tutte le 25 celle rivelate vengono lette; dopo tre tentativi una tavola incompleta rimane tale nell'archivio.

Il ciclo ordinario è **Gioca → due celle/letture → Incassa → griglia → nuovo Gioca**, saltando Incassa in caso di mina. Riconnessione, pausa/ripresa dal master e solo cambio puntata non ripetono Medium. Dopo una pausa locale o un'emergenza serve una nuova abilitazione manuale, che ripete la preparazione iniziale; anche dopo un riavvio il laptop resta disarmato e richiede questa abilitazione.

## Tempi dei click

Modificare e salvare i tempi con il laptop in pausa, poi confermare nuovamente il profilo. Ogni attesa accetta da 0 a 60 secondi, anche frazionari. Le pause prima e dopo un'azione si sommano: non rappresentano la durata totale della partita.

| Passaggio | Impostazioni indipendenti |
|---|---|
| Ogni click | **Dopo ogni click del mouse**, predefinito 0,1 s, si applica anche a puntata e difficoltà. Sostituisce la pausa automatica PyAutoGUI: non si aggiungono altri 0,1 s nascosti. |
| Medium iniziale | Una sola volta a ogni abilitazione manuale, dopo la puntata: attesa prima di ciascuno dei quattro click Abbassa, prima dell'unico Alza e dopo il quinto click. **Dopo Medium iniziale** precede soltanto il primo Gioca; non è un'attesa fra le partite. |
| Gioca e Incassa | **Prima di Gioca** e **Prima di Incassa** sono distinte; **Dopo Gioca** precede la preparazione della prima cella. |
| Prima e seconda cella | Ciascuna ha un'attesa prima del click e una dopo il click, prima di leggerne il colore. La seconda viene eseguita solo se la prima è blu. |
| Lettura colore | Attesa fra due letture della stessa cella non riconosciuta, fino a tre tentativi; non vengono cliccate altre celle per sostituirla. |
| Griglia finale | **Prima della prima cattura** è distinta dall'attesa **Fra due catture**, usata solo se occorre ritentare. |
| Cambio puntata | Attese prima dei click Abbassa e Alza, oltre alle eventuali azioni Attendi della sequenza. |
| Fra partite | Dopo il risultato, attesa prima di chiedere una nuova autorizzazione. La rete e la disponibilità del master possono aggiungere tempo; zero non elimina questo tempo esterno. |

Per esempio, fra Gioca e la prima cella si sommano la pausa comune dopo il click, **Dopo Gioca** e **Prima della prima cella**. Fra la seconda cella e Incassa si aggiungono la pausa comune, **Dopo seconda cella**, la lettura con eventuali retry e **Prima di Incassa**.

Le calibrazioni precedenti conservano coordinate, colori, puntate e attese già impostate. Le nuove attese vengono inizializzate copiando **Incassa da Gioca**, **seconda cella dalla prima**, **dopo seconda cella da dopo prima cella** e **retry griglia dall'attesa di rivelazione**; la pausa comune parte da 0,1 s. I due pulsanti difficoltà mancanti richiedono calibrazione: non vengono inventate coordinate.

## Arresto e recupero

- **Pausa laptop · P** e il tasto globale **P**, anche con il browser in primo piano, fermano soltanto questo laptop. Il tasto interviene solo mentre il laptop è abilitato o occupato: completa la partita già iniziata, poi libera il mouse; durante la preparazione di puntata o difficoltà interrompe i click prima di Gioca. Una riserva senza intento Gioca viene annullata senza perdita. **P non riprende il gioco**: verificare il gioco e premere manualmente **Abilita questo laptop**. Gli altri laptop continuano se il minimo operativo lo consente. La pausa di gruppo resta **Pausa / Riprendi sessione** nel master e non richiede di riabilitare i client rimasti pronti.
- **Dissocia**, nel client o nella scheda del laptop sul master, completa le operazioni aperte e attende la sincronizzazione prima di scollegare. Saldo, identità, calibrazione e storico sono conservati. Una partita incerta o aperta su un laptop offline richiede prima **Riconcilia partita** dal master. Il master deve essere raggiungibile per confermare la dissociazione. Per ricollegare usare un nuovo codice; sullo stesso master si recupera il saldo già archiviato.
- **ESC**, Emergenza e failsafe PyAutoGUI interrompono i click immediatamente. Dall'intento Gioca in avanti una partita interrotta può essere stata eseguita e rimane da riconciliare, anche se il click non è stato confermato: non viene ripetuta automaticamente. La preparazione iniziale della difficoltà avviene prima delle partite; gli eventuali vecchi intenti dei suoi pulsanti non fanno risultare iniziata una partita.
- Senza rete viene completata soltanto la partita già autorizzata. Gli eventi restano su disco e vengono reinviati, senza duplicare gli accrediti. Nessun funzionamento autonomo senza master.
- Dopo il riavvio il client è sempre disarmato. Se aveva registrato un intento di click, verificare l'esito prima di riarmarlo.
- **Verifica / rettifica saldo** riunisce importo e motivo in una sola finestra. Solo con una partita aperta richiede anche un esito, senza preselezionare una perdita: **Vinta e incassata**, **Persa**, **Mai iniziata** oppure **Esito non verificabile**. Usare quest'ultima voce se si conosce il saldo reale ma non si può ricostruire la partita. Il risultato sconosciuto resta tale e non viene contato come perdita o vittoria; la sua riserva viene neutralizzata e la differenza del saldo è un movimento di capitale escluso dal profitto. Il client mostra quando la rettifica attende ancora conferma dal master.
- Se cambia l'IP del master, disarmare e usare **Indirizzo…**: identità, certificato e credenziale restano invariati. Un'impronta TLS differente è un errore, non viene accettata automaticamente.

La contabilità usa millesimi interi, impegna la puntata prima di Play e conserva saldi fra sessioni e giornate. Il **saldo stimato** è calcolato da puntate/esiti/pagamenti configurati: il programma non legge il credito numerico visualizzato sul gioco. Un click inviato non dimostra da solo che sia stato accettato; in caso di dubbio verificare e riconciliare.

## Importi in euro

L'interfaccia mostra `0,10 €`, `20,00 €`, `3,00 €` e `1.999,91 €`. Il terzo decimale compare solo quando serve a conservare millesimi effettivi, per esempio `0,154 €` o `19,684 €`; non si arrotonda ogni vincita al centesimo. Nei campi modificabili il simbolo € e il separatore delle migliaia sono omessi.

`2000` e `2000,00` indicano duemila euro. Un unico punto o un'unica virgola indicano sempre i decimali: per compatibilità `20.000` significa venti euro, come `20,00`. Con entrambi i separatori sono accettati sia `1.999,91` sia `1,999.91`, con gruppi delle migliaia validi. Preferire `2000,00` a scritture potenzialmente ambigue. Gli importi già salvati non vengono moltiplicati o reinterpretati: se un saldo precedente è errato, correggerlo confrontandolo con il gioco.

## Archivia e riparti da zero

Il pulsante **Archivia e riparti da zero…** nel client crea un backup completo in `data/backups/laptop-<data>-<identificatore>.sqlite3`, assegna una nuova identità e richiede nuovamente il saldo reale e l'associazione. Conserva coordinate, colori, tempi e procedura di cambio puntata della calibrazione; gli altri dati correnti tornano ai valori iniziali. Se è ancora associato, il client attende prima la dissociazione confermata dal master e la sincronizzazione degli eventi. Partite incerte richiedono prima la riconciliazione; un master irraggiungibile non può confermare la dissociazione.

Per ripartire anche con il gruppo, usare la stessa funzione **nel pannello master**: richiede la conferma scritta `RIPARTI`, blocca il ripristino con partite aperte/incerte o click in corso e salva un backup automatico. Azzera la sessione corrente, il tempo consumato e i contatori giornalieri, ripristina i limiti predefiniti e dissocia i laptop precedenti; storico e saldi precedenti restano archiviati. I client collegati ricevono la richiesta di ripartenza; quelli offline la ricevono alla riconnessione. Occorre poi confermare i saldi effettivi, associare le nuove identità e avviare manualmente una nuova sessione. Il ripristino del solo client non azzera i risultati del gruppo.

## Dati e aggiornamenti

Il client salva identità, configurazione, calibrazione, saldo confermato, partita corrente e coda eventi in `data/laptop.sqlite3`, accanto all'eseguibile. La cartella deve essere scrivibile e non può essere utilizzata contemporaneamente da due istanze. **Non clonare la cartella data di un laptop su un altro**: ciascuna macchina deve avere identità propria. Per aggiornare l'applicazione, chiuderla e trasferire la sua cartella `data/` nel nuovo pacchetto.

Lo storico completo è sul master, con export CSV/JSON e backup SQLite coerente. I pacchetti distribuiti non contengono impostazioni personali, credenziali o database. Nessun commit o push automatico.

## Sviluppo e verifiche

```powershell
python -m pip install -r requirements.txt
python gratta_e_vinci_gui.py
python -m unittest tests.test_lan_system tests.test_lan_network tests.test_smoke tests.test_tile_recording -v
```

Per tutte le suite storiche e la produzione degli ZIP:

```powershell
python -m pip install -r requirements-build.txt
python -m unittest discover -s tests -q
node --test tests/test_mine_lab.cjs tests/test_master_controls.cjs tests/test_money_ui.cjs
python build_portables.py
```

Il build produce nomi unici in `dist/` di ciascun progetto e un manifest con SHA-256; non sostituisce pacchetti già utilizzati. Opzioni client: `--data-dir CARTELLA`; `--self-test FILE.json` esegue soltanto una verifica GUI nascosta, senza click né collegamenti. Il protocollo è documentato nel progetto master.

Le verifiche automatiche del flusso usano adattatori simulati e registri temporanei: non eseguono click sul gioco e non calibrano i due pulsanti difficoltà. La sequenza iniziale quattro Abbassa più un Alza, una volta per abilitazione manuale, è la procedura richiesta dall'utente; questi test non confermano che il sito abbia effettivamente applicato Medium. I tempi configurati sono attese del programma, a cui si aggiungono letture, elaborazione e rete, non durate totali garantite delle partite.

## Ricerca conservata

[RICERCA_MINE.md](RICERCA_MINE.md) distingue risultati osservati, modelli e ipotesi. `analysis/`, i test storici, `Griglia Rossa 5×5.html`, `bulk_simulation.py`, `bulk_export.py` e i vecchi report restano disponibili per la ricerca. Le dipendenze di export Excel sono separate in `requirements-research.txt` e non entrano nel client portatile. `bulk_results/` è esclusa da Git e richiede una copia separata per il trasferimento.

Le configurazioni del simulatore HTML, delle ricerche e dei laptop non si applicano automaticamente l'una all'altra. Nessuna nuova simulazione statistica né partita reale è necessaria per verificare il protocollo e i pacchetti.
