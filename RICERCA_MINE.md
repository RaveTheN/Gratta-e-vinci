# Ricerca Mine: memoria del progetto

Aggiornato il **19 ottobre 2026**. Progetto: `C:\Progetti\Gratta e vinci`.

Questo file raccoglie le decisioni e le verifiche emerse nella conversazione. I numeri sono stati ricontrollati nei report JSON esistenti durante la redazione; oggi non sono state eseguite nuove simulazioni. Le tabelle riportano medie arrotondate, mentre i JSON conservano i dettagli e la precisione disponibili.

## 1. Stato attuale e conclusioni principali

- L'ultima configurazione richiesta è **5 mine su 25 celle, 2 celle distinte, moltiplicatore totale 1,54×**, puntata fissa 0,10 €, quattro laptop con 20 € ciascuno e un master separato che non gioca.
- L'ultima modalità richiesta è **trigger collettivo a +3 € per sessione**, due sessioni al giorno. Gli esperimenti a lotti da 50/100 sono storici: l'utente ha esplicitamente chiesto di tornare al trigger.
- Nel modello con 5 mine e 1,54×, il rendimento teorico è 97,5333% delle somme puntate: perdita media di circa 2,47 € ogni 1.000 partite. Nei 3.000 mesi simulati tutti i mesi hanno perso e tutti i laptop sono infine rimasti sotto la puntata minima necessaria.
- Anche i casi con 7 mine e 1,80× / 1,84× / 1,92× hanno valore atteso negativo e hanno esaurito i fondi in tutti i rispettivi 3.000 mesi osservati.
- Il precedente caso con 6 mine e 1,80× è positivo **solo sotto le ipotesi del modello**: restituisce teoricamente il 102,6% delle puntate. I suoi profitti simulati non dimostrano che il sito reale offra tale vantaggio.
- Una sessione o una giornata possono chiudersi in perdita anche con un obiettivo di guadagno. Si può chiudere una giornata sotto gli 80 € iniziali, fino a perdere quasi tutto il capitale.
- Zero perdite osservate non significa rischio zero; tutti i risultati sono campioni finiti, non garanzie sui mesi futuri.

## 2. Regole condivise degli esperimenti principali

| Voce | Regola |
|---|---|
| Giocatori | 4 laptop, più un master separato che non gioca |
| Capitale iniziale di base | 20 € per laptop, 80 € totali; la variante da 40 € è indicata separatamente |
| Calendario | 2 sessioni al giorno, per 30 giorni |
| Puntata di base | 0,10 € fissi; niente progressioni o grinding |
| Tavola | 25 celle; numero di mine esplicito per ogni caso |
| Selezione | 2 celle distinte; si termina alla prima mina |
| Pagamento | Moltiplicatore e incasso **totali**, puntata inclusa |
| Obiettivo di base | +3 € per l'intero gruppo in ciascuna sessione, non +3 € per laptop |
| Seconda sessione | Nuovo obiettivo +3 € rispetto al saldo rimasto dopo la prima, anche se la prima ha perso |
| Saldi | Si conservano tra sessioni e giorni; nessun azzeramento, ricarica, trasferimento o prelievo durante il mese |
| Limite di partite | 4.000 per laptop per sessione, massimo teorico 8.000 per laptop al giorno |
| Tempo | Le due sessioni condividono 12 ore giornaliere per avviare partite; la seconda riceve solo il tempo residuo |
| Calo dal picco | 500 € per sessione; non costituisce protezione degli 80 € iniziali |
| Pause | Nessuna pausa volontaria tra partite; tempi tecnici modellati come sotto |
| Estrazioni | Uniformi e indipendenti tra partite e laptop, anche con configurazioni identiche |
| Fine sessione | Si interrompono i nuovi avvii e si completano tutte le partite aperte |

Ogni mese indipendente riparte una sola volta dal capitale iniziale. Questo riavvio tra repliche non è una ricarica durante il mese.

## 3. Cosa significa arresto al trigger

La puntata esce dal saldo del singolo laptop **prima** dell'estrazione. Un laptop senza denaro sufficiente non può prendere denaro dagli altri o ridurre automaticamente la puntata.

Il master confronta la somma dei saldi disponibili con il capitale presente all'inizio di quella sessione. Le puntate ancora aperte sono già state sottratte: non basta che i soli risultati conclusi mostrino +3 € se esistono altri impegni non conteggiati. Il master decide soltanto usando esiti già osservati e disponibilità attuali, senza conoscere esiti o durate future prima di autorizzare la puntata.

Al raggiungimento del trigger non partono nuove partite. Le partite aperte si completano, quindi il profitto finale può superare l'obiettivo. Questo spiega perché un mese positivo può superare i 180 € teoricamente corrispondenti a 60 obiettivi da 3 €.

Il limite delle 12 ore riguarda gli **avvii**: la conclusione delle ultime partite può richiedere qualche secondo in più. Nei report più recenti il massimo giornaliero osservato è circa 12 ore e 5 secondi, senza nuovi avvii oltre la scadenza.

## 4. Contabilità e conferme dell'utente

- Con puntata 0,10 € e incasso totale 0,18 €, una vittoria produce +0,08 € e una sconfitta -0,10 €. Non si deve aggiungere di nuovo la puntata al pagamento.
- Con puntata 0,20 € e incasso totale 0,36 €, il netto di una vittoria è +0,16 €.
- L'utente ha confermato esplicitamente che il sito **conserva 0,184 €** con puntata 0,10 € e moltiplicatore 1,84×. Questa è una dichiarazione dell'utente, non una misurazione indipendente del sito.
- Gli esperimenti da 0,184 / 0,192 / 0,154 € conservano i millesimi con contabilità intera per l'intero mese. Non arrotondano ogni pagamento a 0,18 / 0,19 / 0,15 €.
- Per 0,192 € e 0,154 € è stata applicata la stessa ipotesi di conservazione delle frazioni; non sono stati osservati accrediti reali di queste configurazioni.
- Nell'adattatore Python alcuni argomenti conservano il nome storico `_cents`, ma durante la simulazione scalata rappresentano millesimi: puntata 100, pagamento 154/184/192, capitale 20.000, obiettivo 3.000 e drawdown 500.000 unità. I report vengono poi convertiti in euro.
- Un saldo disponibile minimo pari a zero durante una puntata impegnata non implica necessariamente rovina: una vittoria può restituire denaro. Per "fondi esauriti" si intende un saldo, dopo il regolamento, inferiore alla prossima puntata richiesta.

## 5. Calcoli teorici

Per `m` mine, 25 celle e due selezioni distinte:

```text
P(vittoria) = C(25 - m, 2) / C(25, 2)
           = (25 - m) / 25 × (24 - m) / 24

Incasso totale = puntata × moltiplicatore
Valore atteso netto per partita = P(vittoria) × incasso totale - puntata
Ritorno teorico sulle puntate = P(vittoria) × moltiplicatore
Moltiplicatore di pareggio = 1 / P(vittoria), prima dell'elettricità
```

| Mine | Moltiplicatore | Puntata | Incasso totale | P(vittoria) | Ritorno teorico | Netto teorico ogni 1.000 partite |
|---|---|---|---|---|---|---|
| 6 | 1,80× | 0,10 € | 0,180 € | 57% | 102,60% | +2,60 € |
| 6 | 1,80× | 0,20 € | 0,360 € | 57% | 102,60% | +5,20 € |
| 7 | 1,80× | 0,10 € | 0,180 € | 51% | 91,80% | -8,20 € |
| 7 | 1,84× | 0,10 € | 0,184 € | 51% | 93,84% | -6,16 € |
| 7 | 1,92× | 0,10 € | 0,192 € | 51% | 97,92% | -2,08 € |
| 5 | 1,54× | 0,10 € | 0,154 € | 19/30 ≈ 63,33% | 97,5333% | -2,4667 € |

Moltiplicatori di pareggio, senza elettricità: circa **1,754386× con 6 mine**, **1,960784× con 7 mine**, **1,578947× con 5 mine**. Non sono pagamenti verificati sul sito né configurazioni raccomandate.

Nel caso con 6 mine, anche una piccola differenza nell'accredito cambia il segno: con 0,170 € totali il valore atteso è -3,10 € ogni 1.000 partite; con 0,175 € è -0,25 €; con 0,180 € è +2,60 €. Il guadagno simulato dipende quindi dall'esattezza del pagamento assunto.

Il trigger e i lotti cambiano il momento di arresto e le oscillazioni, non il valore atteso della singola puntata. Più vittorie non implicano necessariamente un rendimento migliore: occorre considerare anche quanto paga ogni vittoria.

## 6. Risultati osservati con arresto al trigger

Ogni riga rappresenta **3.000 nuovi mesi indipendenti da 30 giorni**, con 90.000 giornate e 180.000 sessioni pianificate. I campioni sono distinti, non abbinati partita per partita; un vecchio report usato per confronto non viene contato come nuova simulazione.

| Caso / report | Mine e incasso | Capitale per laptop | Puntata | Obiettivo per sessione |
|---|---|---|---|---|
| T1 / R01 | 6 mine, 1,80× | 20 € | 0,10 € | +3 € |
| T2 / R02 | 6 mine, 1,80× | 20 € | 0,20 € | +3 € |
| T3 / R03 | 6 mine, 1,80× | 40 € | 0,20 € | +6 €, quindi +12 € al giorno |
| T4 / R06 | 7 mine, 1,80× | 20 € | 0,10 € | +3 € |
| T5 / R07 | 7 mine, 1,84× | 20 € | 0,10 € | +3 € |
| T6 / R08 | 7 mine, 1,92× | 20 € | 0,10 € | +3 € |
| T7 / R09 | 5 mine, 1,54× | 20 € | 0,10 € | +3 € |

### Risultati mensili

Il lordo è il profitto/perdita di gioco, non il totale degli incassi. L'elettricità è un costo esterno d'esempio e non viene prelevata dai saldi dei laptop durante il gioco: per questo il netto può scendere sotto -80 €.

| Caso | Lordo mensile medio | Elettricità media | Netto mensile medio | Mesi negativi lordi/netti | Peggiore mese lordo |
|---|---|---|---|---|---|
| T1 | +193,82 € | 2,43 € | +191,39 € | 0 / 0 | +182,02 € |
| T2 | +207,70 € | 1,31 € | +206,39 € | 0 / 0 | +191,28 € |
| T3 | +387,72 € | 2,43 € | +385,29 € | 0 / 0 | +376,80 € |
| T4 | -79,82 € | 0,39 € | -80,21 € | 3.000 / 3.000 | -80,000 € |
| T5 | -79,78 € | 0,54 € | -80,32 € | 3.000 / 3.000 | -79,972 € |
| T6 | -79,79 € | 1,87 € | -81,66 € | 3.000 / 3.000 | -79,968 € |
| T7 | -79,77 € | 1,45 € | -81,22 € | 3.000 / 3.000 | -79,942 € |

Peggiori mesi netti, rispettivamente T1–T7: **+179,33; +189,73; +374,17; -80,530; -80,824; -84,816; -83,040 €**. I mesi che minimizzano lordo e netto non devono necessariamente coincidere.

### Sessioni, giornate e obiettivi

| Caso | Sessioni negative | Giornate negative | Peggiore sessione | Peggiore giornata | Sessioni pianificate senza obiettivo raggiunto |
|---|---|---|---|---|---|
| T1 | 5 | 1 | -7,72 € | -4,36 € | 6 |
| T2 | 3 | 2 | -6,08 € | -3,04 € | 3 |
| T3 | 0 | 0 | +1,12 € | +7,20 € | 5 |
| T4 | 3.113 | 3.001 | -83,200 € | -80,000 € | 179.995 |
| T5 | 4.661 | 3.042 | -83,372 € | -79,972 € | 179.957 |
| T6 | 12.916 | 8.761 | -70,220 € | -82,484 € | 176.022 |
| T7 | 10.876 | 6.702 | -69,928 € | -79,920 € | 179.335 |

Una giornata negativa significa una perdita rispetto all'inizio di **quella giornata**; è una metrica diversa dal chiudere sotto il capitale iniziale del mese. Nel campione T1 c'è una giornata negativa ma nessuna chiusura giornaliera di gruppo sotto gli 80 € iniziali. Questo non esclude che possa succedere in un altro mese.

Una sessione/giornata può perdere più degli 80 € originari dopo avere accumulato profitti precedenti. Questo non implica saldi negativi o denaro prestato tra laptop.

Per T1/T2/T3, i mancati obiettivi sono dovuti soltanto al limite di 4.000 partite per laptop. Per gli scenari negativi, i conteggi grezzi includono anche tentativi di sessione senza alcuna puntata dopo l'esaurimento dei fondi:

| Caso | Trigger raggiunti / sessioni con almeno una puntata | Tentativi senza puntate | Cause dei mancati obiettivi pianificati |
|---|---|---|---|
| T4 | 5 / 3.118 | 176.882 | Fondi 179.882; fondi e limite partite 113 |
| T5 | 43 / 4.704 | 175.296 | Fondi 178.296; fondi e limite 1.642; tempo 16; solo limite 3 |
| T6 | 3.978 / 16.981 | 163.019 | Fondi 166.019; fondi e limite 4.155; tempo 3.226; solo limite 2.622 |
| T7 | 665 / 11.567 | 168.433 | Fondi 171.432; fondi e limite 1.980; tempo 3.176; solo limite 2.747 |

Questi rapporti non sono probabilità di successo di sessioni sempre finanziate: i saldi cambiano continuamente. Le giornate ferme dopo la rovina hanno profitto e attività zero, non costituiscono giornate di gioco sicure. Nei report recenti i dettagli dei ripetuti tentativi senza puntate sono omessi per compattezza, ma il loro numero è conservato.

### Tempi e durata dei fondi

| Caso | Minuti medi per giorno di calendario | Massimo giornaliero in ore | Ore medie complessive nel mese | Mesi con almeno un laptop senza fondi |
|---|---|---|---|---|
| T1 | 67,39 | 8,276667 | 33,70 | 0 |
| T2 | 36,36 | 7,365556 | 18,18 | 12 |
| T3 | 67,40 | 9,464722 | 33,70 | 0 |
| T4 | 10,86 | 9,819722 | 5,43 | 3.000 |
| T5 | 14,89 | 12,001389 | 7,44 | 3.000 |
| T6 | 52,04 | 12,001389 | 26,02 | 3.000 |
| T7 | 40,23 | 12,001389 | 20,11 | 3.000 |

Le medie giornaliere T4–T7 includono molti giorni senza gioco dopo la rovina. Non vanno interpretate come attività di un gruppo ancora finanziato per tutti i 30 giorni.

Nei campioni T4–T7 **tutti e quattro i laptop** hanno finito sotto la propria puntata. Ultimo giorno con partite:

- T4: 2.999 mesi al giorno 1, un mese al giorno 2.
- T5: 2.958 mesi al giorno 1, 42 al giorno 2.
- T6: giorni 1–9, rispettivamente 16, 936, 1.168, 564, 218, 68, 23, 5, 2 mesi.
- T7: giorni 1–5, rispettivamente 31, 2.266, 643, 58, 2 mesi.

Con un valore atteso negativo, un pagamento più alto può far durare di più il capitale senza salvare il mese. Se alla fine si perdono comunque quasi tutti gli 80 €, le ore aggiuntive aumentano il costo elettrico.

### Saldi dei singoli laptop

Valori nell'ordine laptop 1 / 2 / 3 / 4. I minimi comprendono le puntate già impegnate; i saldi finali sono medie tra mesi, arrotondate.

| Caso | Minimi disponibili osservati (€) | Saldi finali medi (€) |
|---|---|---|
| T1 | 6,10 / 8,36 / 6,52 / 7,58 | 68,57 / 68,16 / 68,49 / 68,60 |
| T2 | 0,00 / 0,12 / 0,08 / 0,04 | 71,85 / 71,98 / 71,71 / 72,16 |
| T3 | 14,60 / 17,60 / 14,92 / 13,16 | 136,71 / 136,93 / 137,38 / 136,70 |
| T4 | 0 / 0 / 0 / 0 | 0,0470 / 0,0466 / 0,0454 / 0,0459 |
| T5 | 0 / 0 / 0 / 0 | 0,0546 / 0,0536 / 0,0533 / 0,0539 |
| T6 | 0 / 0 / 0 / 0 | 0,0530 / 0,0534 / 0,0534 / 0,0531 |
| T7 | 0 / 0 / 0 / 0 | 0,0584 / 0,0582 / 0,0586 / 0,0580 |

In T2, **12 mesi su 3.000 hanno avuto almeno un laptop senza fondi pur chiudendo il gruppo in utile**. Un gruppo profittevole non garantisce la sopravvivenza di ogni laptop. Anche in T1 un laptop ha chiuso un mese a 17,26 €, sotto i suoi 20 € iniziali, mentre il gruppo era positivo.

## 7. Esperimenti storici a lotti: non sono la modalità attuale

L'utente aveva autorizzato lotti di 50 o 100 partite **per laptop**, con barriera sincronizzata: tutti finiscono il proprio lotto, poi il master controlla il guadagno e decide se iniziare il successivo. Si mantengono puntata 0,10 €, plafond 20 € e due obiettivi collettivi da +3 €.

I limiti di fondi, partite e tempo possono interrompere forzatamente un lotto. L'obiettivo di profitto non lo interrompe a metà. I laptop più veloci aspettano quelli più lenti e i ritardi tecnici finali prima del riavvio comune.

| Mine / lotto | Mesi | Lordo medio | Elettricità | Netto medio | Mesi negativi | Giorni negativi | Peggiore giornata |
|---|---|---|---|---|---|---|---|
| 6 / 50 | 3.000 | +231,15 € | 2,96 € | +228,19 € | 0 | 1 | -1,10 € |
| 6 / 100 | 3.000 | +258,40 € | 3,28 € | +255,12 € | 0 | 2 | -1,90 € |
| 7 / 50 | 3.000 | -79,81 € | 0,39 € | -80,21 € | 3.000 | 3.000 | -80,00 € |
| 7 / 100 | 3.000 | -79,81 € | 0,39 € | -80,21 € | 3.000 | 3.000 | -80,00 € |

Fonti: R04 per 6 mine; R05 per 7 mine, sempre con incasso totale 0,18 €. Il test a lotti con 7 mine era stato inizialmente proseguito mantenendo la modalità precedente; l'utente ha poi corretto il contesto chiedendo il ritorno al trigger. Il confronto corretto al trigger è T4/R06.

Con 6 mine:

- Lotto 50: 6 sessioni negative, peggiore -4,48 €; 10 obiettivi mancati, tutti per limite partite; attività media 82,24 minuti/giorno, massimo 9,684444 ore; peggiore mese lordo +214,20 €.
- Lotto 100: 7 sessioni negative, peggiore -5,92 €; 9 obiettivi mancati, tutti per limite partite; attività media 91,15 minuti/giorno, massimo 10,052778 ore; peggiore mese lordo +233,82 €.
- Nessun laptop ha esaurito i fondi in questi due campioni. Minimi individuali: lotto 50 = 8,46 / 3,58 / 8,58 / 5,94 €; lotto 100 = 7,46 / 5,46 / 5,90 / 8,16 €.
- Saldi finali medi individuali: lotto 50 = 77,98 / 77,48 / 77,75 / 77,95 €; lotto 100 = 84,76 / 84,59 / 84,45 / 84,60 €.
- I maggiori profitti medi derivano da più partite e maggiore superamento dell'obiettivo, sotto l'ipotesi favorevole del 102,6% di ritorno; il vantaggio della singola partita non cambia.

Per un **singolo lotto completo e finanziato** del gruppo:

| Mine | 50 per laptop: 200 partite | 100 per laptop: 400 partite |
|---|---|---|
| 6 | Netto medio teorico +0,52 €; lotto negativo circa 35,95% | Netto medio teorico +1,04 €; lotto negativo circa 28,88% |
| 7 | Netto medio teorico -1,64 €; lotto negativo circa 91,06% | Netto medio teorico -3,28 €; lotto negativo circa 96,80% |

Queste percentuali riguardano il lotto, non una giornata o un mese. Il piccolo numero di giornate negative dei due campioni favorevoli non basta per ordinare con sicurezza il rischio dei lotti.

Un test costruito con 25 vittorie seguite da 25 sconfitte per ogni laptop porta il gruppo prima a +8 € e poi a **-2 € a fine lotto**. È un esempio deterministico, non un evento estratto nelle simulazioni. Se restano fondi e limiti, il lotto successivo può ancora partire.

Con 7 mine e 1,80×, in entrambi i campioni a lotti tutti i laptop sono rimasti senza fondi entro il primo giorno; l'attività media complessiva prima dell'esaurimento è stata circa 5,44/5,45 ore. Non trasferire questa conclusione ai diversi campioni al trigger o ai pagamenti maggiori.

## 8. Verifiche del simulatore e delle tavole

Sono stati controllati probabilità, incassi totali, conservazione del denaro per sessione/giorno/mese, prenotazione della puntata prima del gioco, indisponibilità di denaro altrui, causalità del coordinatore, completamento delle partite aperte, obiettivo della seconda sessione e tempo giornaliero condiviso.

I test deterministici comprendono sole vittorie, sole sconfitte, saldo insufficiente, target collettivo con puntate aperte, limite di partite, scadenza, riporto dei saldi, ritardi tecnici, drawdown e sincronizzazione dei lotti. Implementazioni indipendenti con scansione dei timer o coda di eventi sono state confrontate con il simulatore principale.

| Mine | Tavole complete possibili | Mina alla prima cella | Mina alla seconda dopo la prima sicura | Vittoria su entrambe |
|---|---|---|---|---|
| 6 | 177.100 | 6/25 = 24% | 19/100 = 19% | 57/100 = 57% |
| 7 | 480.700 | 7/25 = 28% | 21/100 = 21% | 51/100 = 51% |
| 5 | 53.130 | 1/5 = 20% | 1/6 ≈ 16,67% | 19/30 ≈ 63,33% |

Le probabilità di "mina alla seconda" sono incondizionate e comprendono il fatto che la prima sia sicura.

R01 include il confronto tra un milione di partite del generatore rapido e un milione con tavole complete, oltre a **300 mesi indipendenti con tavole complete**, separati dai 3.000 mesi principali. Le medie lorde mensili sono +193,81726 € e +193,74813 €, compatibili con la normale variabilità del campione. L'enumerazione completa conferma esattamente le probabilità.

### Coppia fissa e coppia casuale

Con tavole uniformi e indipendenti, qualunque coppia di celle distinte ha la stessa probabilità di vittoria. Ripetere sempre le celle 1 e 2 non richiede una tavola comune e non crea un vantaggio predittivo.

R10 confronta 500.000 tavole (125.000 per laptop), selezione fissa contro casuale, e verifica esaustivamente anche altre coppie. R11 aggiunge **1.000 mesi con tavole complete e celle sempre 1 poi 2**: lordo medio +193,77 €, elettricità 2,44 €, netto +191,33 €, un giorno negativo e quattro sessioni negative. Questo campione da 1.000 mesi non va presentato come un altro campione da 3.000.

### Errori e cautele emersi nel codice di ricerca

- I default degli helper non identificano la strategia: spesso sono 6 celle scelte, pagamento 0,68 €, capitale 1.000 € e una sessione. Occorre passare esplicitamente 2 celle, pagamento, capitale, numero di laptop/sessioni e obiettivo.
- Il numero di laptop di default può variare tra helper: alcuni simulatori di base usano 3. Controllare sempre i metadati del report.
- Il valore `round_cap_or_funds` nei report trattati significa che tutti i laptop hanno raggiunto il limite; `insufficient_funds` può comprendere una combinazione di laptop senza fondi e laptop al limite. I dettagli per laptop permettono di distinguere le cause.
- Nei test dei lotti sono stati corretti l'ordinamento iniziale della coda di riferimento e il trattamento causale del drawdown/scadenza con completamento delle partite aperte. I confronti dei tempi usano tolleranza per gli errori di rappresentazione numerica.
- Il riepilogo `observed` accetta `units_per_eur=1000` per non nascondere perdite di pochi millesimi arrotondandole al centesimo.
- Il file dal nome storico `analysis/seven_mine_trigger.py` è ora configurabile con `--mines`; i default restano 7 mine e pagamento 0,180 €, non l'ultimo caso 5 mine/0,154 €.
- I report passati restano fotografie della versione che li ha prodotti: i nomi delle chiavi possono differire. Esempio: `not_reaching_plus_3_eur` nei report iniziali, `not_reaching_session_target` nei recenti.

## 9. Tempi tecnici ed elettricità

Tempi letti dalle impostazioni nelle verifiche e conservati nei report; non sono misure effettuate sul sito:

| Impostazione | Valore usato |
|---|---|
| `sleep_play_or_collect` | 1,0 s prima di play/incasso |
| `sleep_after_play` | 0,5 s per cella |
| `sleep_click_tile` | 1,0 s per cella |
| `sleep_after_tile_click` | 0,5 s per cella |
| Tempo tecnico totale per cella | 2,0 s |
| `sleep_after_result` | 1,0 s aggiuntivo dopo sconfitta |
| `tile_reveal_delay` | 1,0 s, valore di default quando assente |
| `tile_record_enabled` | Assente nello snapshot iniziale: default attivo nel modello |
| `sleep_between_rounds` | 1,0 s nel file, escluso come pausa volontaria su richiesta dell'utente |

Durata fino al risultato: **3 s** per mina alla prima cella, **5 s** per mina alla seconda, **6 s** per vittoria con incasso. Cicli ordinari tra avvii consecutivi sullo stesso laptop: **5 / 7 / 7 s**. Durata media del ciclo: 6,52 s con 6 mine; 6,44 s con 7; 6,60 s con 5.

Sono esclusi setup iniziale, latenze di rete/rendering/click/coordinamento, riletture di colore, pause casuali e cambi di puntata. Mantenendo anche `sleep_between_rounds=1`, il ciclo medio del caso con 6 mine salirebbe da 6,52 a 7,52 s. Non assumere che il bot reale usi automaticamente i tempi senza pausa del modello.

L'elettricità è soltanto un esempio:

```text
Potenza totale dei cinque computer = 240 W = 0,240 kW
Tariffa = 0,30 €/kWh
Costo = ore di attività del gruppo × 0,240 × 0,30
      = ore × 0,072 €
```

Si usa il tempo trascorso, incluse attese di sincronizzazione dei lotti e regolamento finale; **non si moltiplica di nuovo per quattro**. Il costo elettrico mensile viene arrotondato una sola volta al centesimo. I nuovi report con incassi frazionari conservano tre decimali per lordo e netto. Potenza reale, tariffa reale e altri costi non sono stati misurati.

## 10. Stato del simulatore grafico "Mine - Lab"

La tab è presente in [Griglia Rossa 5×5.html](Griglia%20Rossa%205%C3%975.html), come simulatore locale; non controlla il bot né avvia partite reali.

Funzioni implementate: riquadro master, da 1 a 100 cloni visibili con tavole complete separate, nome/plafond/puntata per ogni laptop, avvio/arresto dal master, saldi e risultati individuali, attività simulata, storico, stima elettrica, modalità manuale per sessione o prosecuzione automatica per 30 giorni, velocità 1×/10×/100×/1.000×.

**La configurazione della tab è diversa dall'ultima analisi Python:** i default dell'interfaccia sono 4 laptop da 40 €, puntata 0,20 €, obiettivo +6 € per sessione e +12 € al giorno. Il modello grafico usa **6 mine, 2 celle e pagamento totale 1,80×**. Numero di mine e moltiplicatore non sono parametri aggiornati dalle ultime analisi. Le puntate della tab sono multipli di 0,10 € e la sua contabilità è in centesimi.

Il checkbox di prosecuzione automatica è inizialmente disattivato: la UI attende un nuovo avvio dal master tra le sessioni. Lo stop manuale completa le partite aperte; una ripresa conserva saldi e contatori; "Nuovo esperimento" ripristina i plafond. I dati sono in memoria della pagina e si perdono ricaricandola. La tab non ha un'opzione a lotti.

Le varianti successive con 5/7 mine, incassi 1,54×/1,84×/1,92× e i test a lotti sono state sviluppate nei moduli di ricerca, senza adeguare la tab grafica né le impostazioni del bot reale.

## 11. File e comandi di riferimento

| File | Ruolo |
|---|---|
| [analysis/collective_parallel.py](analysis/collective_parallel.py) | Simulatore a eventi, saldi individuali, trigger, regolamento delle partite aperte, tempi |
| [analysis/collective_validation.py](analysis/collective_validation.py) | Riporto dei saldi per 30 giorni, due sessioni e budget temporale condiviso, report |
| [analysis/medium_two_sessions.py](analysis/medium_two_sessions.py) | Esperimento iniziale a due sessioni, parametri 2 celle/0,18 €/20 € espliciti |
| [analysis/medium_bankroll.py](analysis/medium_bankroll.py) | Analisi precedenti del capitale e aggregazione delle repliche |
| [analysis/medium_two_verification.py](analysis/medium_two_verification.py) | Verifica indipendente, tavole complete, teoria e aggregazione `observed` |
| [analysis/medium_twenty_cents.py](analysis/medium_twenty_cents.py) | Puntata 0,20 €, capitale e obiettivo configurabili, 6 mine/1,80× |
| [analysis/medium_fixed_two.py](analysis/medium_fixed_two.py) | Coppia sempre 1 poi 2 su tavole complete nuove |
| [analysis/medium_batches.py](analysis/medium_batches.py) | Lotti sincronizzati 50/100, pagamento totale 0,18 €, default 6 mine |
| [analysis/seven_mine_trigger.py](analysis/seven_mine_trigger.py) | Trigger con numero di mine e pagamento configurabili; contabilità intera in millesimi |
| [tests/test_medium_two_config.py](tests/test_medium_two_config.py) | Verifiche deterministiche e riferimento indipendente del piano iniziale |
| [tests/test_medium_twenty_cents.py](tests/test_medium_twenty_cents.py) | Contabilità/rischio delle varianti da 0,20 € |
| [tests/test_medium_batches.py](tests/test_medium_batches.py) | Lotti, limiti, causalità, attese e confronto con riferimento a eventi |
| [tests/test_seven_mine_trigger.py](tests/test_seven_mine_trigger.py) | Trigger, precisione dei millesimi, parametrizzazione mine e tavole esaustive |
| [tests/test_mine_lab.cjs](tests/test_mine_lab.cjs) | 12 test del modello grafico JavaScript |

Comandi da eseguire nella cartella del progetto; i comandi di ricerca producono **nuove** repliche, non riproducono necessariamente le stesse estrazioni dei report salvati:

```powershell
# Ultimo caso richiesto: 5 mine, incasso totale 0,154 €, trigger
python -m analysis.seven_mine_trigger --mines 5 --payout-millieuro 154

# Varianti storiche al trigger
python -m analysis.seven_mine_trigger --mines 7 --payout-millieuro 180
python -m analysis.seven_mine_trigger --mines 7 --payout-millieuro 184
python -m analysis.seven_mine_trigger --mines 7 --payout-millieuro 192

# Piano iniziale verificato; 3.000 mesi rapidi più confronto con tavole complete
python -m analysis.medium_two_verification

# 6 mine, 0,20 €; default 20 € e +3 € per sessione
python -m analysis.medium_twenty_cents
python -m analysis.medium_twenty_cents --capital-cents 4000 --target-cents 600

# Lotti storici: non sostituiscono il trigger corrente
python -m analysis.medium_batches --mines 6

# Controlli pertinenti: ultima esecuzione nella conversazione, 31 test passati
python -m unittest tests.test_seven_mine_trigger tests.test_medium_two_config tests.test_medium_twenty_cents -q
python -m unittest tests.test_medium_batches -q
node --test tests/test_mine_lab.cjs
```

La suite dei lotti ha 13 test. Nell'esecuzione iniziale dei lotti furono confrontati anche 372 sottocasi; la versione successiva comprende la parametrizzazione 6/7 mine e i controlli aggiuntivi. Non attribuire retroattivamente a un vecchio report test aggiunti dopo la sua produzione. Oggi, per questo aggiornamento documentale, non è stata rieseguita alcuna suite di simulazione.

## 12. Indice dei report principali

Le date nei nomi sono timestamp UTC di generazione. Le sigle sotto identificano file specifici, non un generico "ultimo risultato".

- **R01** — [Verifica indipendente iniziale: 6 mine, 0,10 €, 20 €, trigger +3 €](bulk_results/medium_two_verification_20261015_101236_057704Z.json).
- **R02** — [6 mine, 0,20 €, plafond 20 €, trigger +3 €](bulk_results/medium_twenty_cents_20261017_121348_756004Z.json).
- **R03** — [6 mine, 0,20 €, plafond 40 €, due trigger da +6 €](bulk_results/medium_twenty_cents_20261017_132541_507806Z.json).
- **R04** — [6 mine, 0,10 €, lotti 50 e 100: 3.000 mesi ciascuno](bulk_results/medium_batches_20261017_195118_986011Z.json).
- **R05** — [7 mine, 1,80×, lotti 50 e 100: storico distinto dal trigger](bulk_results/medium_batches_7_mines_20261018_085000_041234Z.json).
- **R06** — [7 mine, 1,80×, trigger: 3.000 nuovi mesi](bulk_results/seven_mine_trigger_20261018_085438_209561Z.json).
- **R07** — [7 mine, 1,84×, trigger con pagamento esatto 0,184 €](bulk_results/seven_mine_trigger_184_millieuro_20261018_091411_364454Z.json).
- **R08** — [7 mine, 1,92×, trigger con pagamento esatto 0,192 €](bulk_results/seven_mine_trigger_192_millieuro_20261018_092429_697394Z.json).
- **R09** — [Ultimo caso: 5 mine, 1,54×, trigger con pagamento esatto 0,154 €](bulk_results/mine_trigger_5_mines_154_millieuro_20261018_093158_327894Z.json).
- **R10** — [Confronto coppia fissa/casuale su 500.000 tavole](bulk_results/fixed_two_board_comparison_20261015_162347_918012Z.json).
- **R11** — [Celle fisse 1 poi 2: 1.000 mesi con tavole complete](bulk_results/medium_fixed_two_20261015_162725_309535Z.json).

In `bulk_results/` esistono anche report preparatori, confronti e prove brevi, tra cui una prova da 8 mesi per le celle fisse. Non sommarli automaticamente ai campioni principali e non presentarli come nuove simulazioni dell'ultimo caso.

R05 è voluminoso (circa 381 MB): estrarre i riepiloghi con un parser JSON, evitando di riversare in chat tutti i dettagli mensili.

## 13. Ipotesi non verificate e conservazione del contesto

- Uniformità delle mine, indipendenza tra partite e laptop e numero effettivo di mine del sito non sono stati verificati su partite reali.
- Il pagamento del caso iniziale 6 mine/1,80× non è stato misurato: il suo rendimento superiore al 100% è una conseguenza dell'ipotesi, non una prova di redditività reale.
- Conservazione di 0,184 € confermata dall'utente; nessuna verifica indipendente di accrediti, commissioni, limiti, regole commerciali o condizioni del sito.
- Latenze reali, affidabilità del coordinatore e consumi elettrici sono assunzioni del modello, non misure hardware o online.
- Nessuna partita reale è stata avviata per questi esperimenti; i report non configurano automaticamente il bot reale.
- Questo riepilogo riporta risultati storici e calcoli; non prova né profitti garantiti né una probabilità futura di rovina esattamente uguale a quella osservata.

`AGENTS.md` richiama questo documento per le future attività. Aprire `C:\Progetti\Gratta e vinci` come cartella principale del progetto permette di trovare le sue istruzioni; la cartella primaria di questa conversazione era invece `C:\Progetti\previsione_bilancio` e il lavoro è stato indirizzato esplicitamente al progetto corretto.

I report JSON sono salvati sul disco ma **`bulk_results/` è esclusa da Git**. Per trasferire il lavoro su un'altra macchina occorrono anche quei file, oltre a questo riepilogo e al codice; i collegamenti locali da soli non costituiscono un backup. Nessun commit o push è stato eseguito automaticamente.

Per aggiornare la memoria: conservare le correzioni dell'utente, aggiungere una nuova riga/caso con parametri e report, annotare data e controlli eseguiti, separare le osservazioni dalle ipotesi e mantenere l'indice coerente. Le istruzioni e i risultati non richiedono che la memoria automatica dell'app sia attiva.
