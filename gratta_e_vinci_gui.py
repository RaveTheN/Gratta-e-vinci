"""Portable laptop UI. Master owns sessions and accounting; this UI owns calibration."""
import argparse
import asyncio
import json
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

import pyautogui
from pynput import keyboard

from client_store import ClientStore, validate_calibration
from coordinate_manager import CoordinateManager, CoordinateRecorder
from laptop_client import LaptopClient, associate
from mine_protocol import InstanceLock, config, data_directory, display, euro, money


class BalanceDialog(simpledialog.Dialog):
    outcomes = {"Esito non noto": "unknown", "Vinta e incassata": "win", "Persa (mina)": "loss",
                "Mai iniziata (annulla puntata)": "cancel"}

    def __init__(self, parent, state):
        self.state = state
        super().__init__(parent, title="Verifica saldo (€)")

    def body(self, parent):
        heading = (f"Saldo calcolato dal programma: {euro(self.state['balance'])}" if self.state["confirmed"]
                   else "Primo utilizzo: il saldo iniziale effettivo è obbligatorio")
        ttk.Label(parent, text=heading).pack(anchor="w", pady=5)
        ttk.Label(parent, text="Il programma non legge gli importi a schermo. Inserisci il saldo effettivo mostrato dal gioco.\n"
                  "Esempi: 1999,91 oppure 1,999.91 = 1.999,91 €; 20 = 20,00 €.", wraplength=550).pack(anchor="w", pady=5)
        ttk.Label(parent, text="Saldo effettivo sul gioco (€)").pack(anchor="w")
        self.amount_var = tk.StringVar(value=display(self.state["balance"]) if self.state["confirmed"] else "")
        entry = ttk.Entry(parent, textvariable=self.amount_var, width=30)
        entry.pack(anchor="w", pady=(0, 8))
        ttk.Label(parent, text="Motivo della verifica").pack(anchor="w")
        self.reason_var = tk.StringVar(value="Saldo verificato sul gioco")
        ttk.Entry(parent, textvariable=self.reason_var, width=65).pack(fill="x", pady=(0, 8))
        self.outcome_var = tk.StringVar(value="Esito non noto")
        self.opened = self.state.get("master_round") or self.state.get("round")
        if self.opened:
            ttk.Label(parent, text="C'è una partita da verificare. Scegli l'esito soltanto se lo conosci.", wraplength=550).pack(anchor="w")
            ttk.Combobox(parent, textvariable=self.outcome_var, values=list(self.outcomes), state="readonly", width=38).pack(anchor="w", pady=5)
            ttk.Label(parent, text="Esito non noto aggiorna il saldo senza registrare una perdita inventata.", wraplength=550).pack(anchor="w")
        ttk.Label(parent, text="Conferma aggiorna il saldo; le rettifiche di capitale non valgono per l'obiettivo.\n"
                  "Se associato, il laptop resta disabilitato e attende la conferma del master.", wraplength=550).pack(anchor="w", pady=5)
        return entry

    def validate(self):
        try:
            balance = money(self.amount_var.get())
            reason = self.reason_var.get().strip()
            if not reason or len(reason) > 500:
                raise ValueError("Inserire il motivo della verifica (massimo 500 caratteri)")
            self.result = {"balance": balance, "reason": reason}
            if self.opened:
                self.result["outcome"] = self.outcomes[self.outcome_var.get()]
            return True
        except (ValueError, KeyError) as exc:
            messagebox.showerror("Verifica saldo", str(exc), parent=self)
            return False


class GrattaEVinciGUI:
    def __init__(self, root, store=None, start_services=True):
        self.root = root
        self.store = store or ClientStore(data_directory() / "laptop.sqlite3")
        self.ui_queue = queue.Queue()
        self.client = LaptopClient(self.store, self.ui_queue)
        self.coordinate_manager, self.coordinate_recorder = CoordinateManager(), None
        self.keyboard_listener, self.pair_thread = None, None
        self.closing, self.last_reply, self.edit_revision = False, None, 0
        root.title("Mine · Laptop")
        root.geometry("980x760")
        root.minsize(840, 650)
        root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.status_var = tk.StringVar(value="Disarmato · in attesa del master")
        self.connection_var = tk.StringVar(value="Non collegato")
        self.balance_var, self.session_var = tk.StringVar(), tk.StringVar(value="Nessuna sessione")
        self.error_var = tk.StringVar()
        self.balance_command_id = next((c["id"] for c in self.store.snapshot()["commands"]
                                        if c["action"] in ("balance", "reconcile")), None)
        self.balance_sync_var = tk.StringVar(value="Rettifica in attesa della conferma del master" if self.balance_command_id else "")
        self.profile_confirmed = tk.BooleanVar(value=False)
        self.fields = {k: tk.StringVar() for k in ("name", "stake", "mines", "multiplier", "selection", "first", "second")}
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=12)
        self.tabs = []
        self.scroll_canvases = {}
        for name in ("Stato", "Calibrazione", "Cambio/reset puntata", "Tempi"):
            frame = ttk.Frame(self.notebook, padding=15)
            self.notebook.add(frame, text=name)
            self.tabs.append(frame)
        self._status_tab(self._scrollable_content(self.tabs[0]))
        self._calibration_tab(self._scrollable_content(self.tabs[1]))
        self._bet_tab(self._scrollable_content(self.tabs[2]))
        self._timing_tab(self.tabs[3])
        self.root.bind("<MouseWheel>", self._timing_scroll, add="+")
        self.root.bind("<FocusIn>", self._scroll_focus, add="+")
        ttk.Label(root, textvariable=self.error_var, foreground="#a12535", wraplength=930).pack(fill="x", padx=18, pady=(0, 10))
        self.reload_fields()
        self.load_calibration()
        self._render_status()
        if start_services:
            self.client.start()
            self.pause_key_down = False
            self.keyboard_listener = keyboard.Listener(on_press=self._key, on_release=self._key_release)
            self.keyboard_listener.start()
        self.services_started = start_services
        self.poll_id = root.after(100, self._poll)

    def _scrollable_content(self, parent):
        canvas = tk.Canvas(parent, highlightthickness=0)
        scroll = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        content = ttk.Frame(canvas)
        window = canvas.create_window((0, 0), window=content, anchor="nw")
        content.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))
        self.scroll_canvases[str(parent)] = canvas
        return content

    def _status_tab(self, parent):
        for variable, size in ((self.connection_var, 11), (self.status_var, 17), (self.balance_var, 19), (self.session_var, 11)):
            ttk.Label(parent, textvariable=variable, font=("Segoe UI", size), wraplength=900).pack(anchor="w", pady=4)
        ttk.Label(parent, text="Saldo stimato dagli esiti: non viene letto dal gioco. Verifica/rettifica prima di giocare se differisce.", wraplength=900).pack(anchor="w")
        ttk.Label(parent, textvariable=self.balance_sync_var, wraplength=900).pack(anchor="w")
        buttons = ttk.Frame(parent)
        buttons.pack(fill="x", pady=10)
        self.ready_button = ttk.Button(buttons, text="Abilita questo laptop", command=self.arm)
        self.ready_button.pack(side="left", padx=(0, 8))
        for text, action in (("Pausa laptop · P", self.pause_local), ("EMERGENZA · ESC", self.emergency)):
            ttk.Button(buttons, text=text, command=action).pack(side="left", padx=(0, 8))
        ttk.Label(parent, text="P completa la partita e mette in pausa questo laptop. ESC interrompe subito: verifica la partita prima di ripartire.", wraplength=900).pack(anchor="w")
        ttk.Checkbutton(parent, text="Ho verificato profilo del gioco, finestra, zoom, coordinate e credito", variable=self.profile_confirmed).pack(anchor="w")
        form = ttk.LabelFrame(parent, text="Configurazione sincronizzata", padding=12)
        form.pack(fill="x", pady=10)
        labels = {"name": "Nome", "stake": "Puntata (€)", "mines": "Mine", "multiplier": "Moltiplicatore totale",
                  "selection": "Selezione", "first": "Prima cella", "second": "Seconda cella"}
        for index, (key, label) in enumerate(labels.items()):
            row, col = divmod(index, 4)
            cell = ttk.Frame(form)
            cell.grid(row=row, column=col, padx=6, pady=5, sticky="w")
            ttk.Label(cell, text=label).pack(anchor="w")
            if key == "selection":
                ttk.Combobox(cell, textvariable=self.fields[key], values=("random", "fixed"), state="readonly", width=17).pack()
            else:
                ttk.Entry(cell, textvariable=self.fields[key], width=20).pack()
        actions = ttk.Frame(form)
        actions.grid(row=2, column=0, columnspan=4, sticky="w", pady=8)
        for text, action in (("Salva / sincronizza", self.save_profile), ("Ricarica dal master", self.reload_fields),
                             ("Verifica / rettifica saldo", self.correct_balance)):
            ttk.Button(actions, text=text, command=action).pack(side="left", padx=4)
        pairing = ttk.LabelFrame(parent, text="Associazione", padding=12)
        pairing.pack(fill="x")
        ttk.Label(pairing, text="Nel master: Associa laptop → Genera codice monouso. Incolla qui il codice e premi Associa.\n"
                  "Poi verifica il gioco e premi Abilita questo laptop. Dissocia conserva saldo, calibrazione e storico.",
                  wraplength=870).pack(anchor="w", pady=(0, 8))
        pairing_actions = ttk.Frame(pairing)
        pairing_actions.pack(fill="x")
        self.pair_code = ttk.Entry(pairing_actions, width=40)
        self.pair_code.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.pair_button = ttk.Button(pairing_actions, text="Associa codice del master", command=self.pair)
        self.pair_button.pack(side="left")
        self.address_button = ttk.Button(pairing_actions, text="Indirizzo…", command=self.change_address)
        self.address_button.pack(side="left", padx=4)
        self.unpair_button = ttk.Button(pairing_actions, text="Dissocia", command=self.unpair)
        self.unpair_button.pack(side="left", padx=4)
        ttk.Button(pairing, text="Archivia e riparti da zero…", command=self.reset_local).pack(anchor="e", pady=(8, 0))
        self.log = tk.Text(parent, height=3, state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True, pady=(14, 0))

    def _calibration_tab(self, parent):
        self.mouse_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.mouse_var).pack(anchor="w")
        ttk.Label(parent, text="Monitor principale. Registra nove riferimenti, Gioca/incassa, i due pulsanti puntata e i due pulsanti difficoltà.\n"
                  "A ogni Abilita questo laptop, prima del primo Gioca: 4 click su Abbassa difficoltà e 1 su Alza → Medium. Una sola volta, dopo la puntata; tutti i riferimenti sono obbligatori.", wraplength=880).pack(anchor="w", pady=8)
        self.tile_vars = {i: (tk.IntVar(value=0), tk.IntVar(value=0)) for i in range(1, 26)}
        references = ttk.Frame(parent)
        references.pack(fill="x", pady=12)
        for index, tile in enumerate((1, 2, 3, 4, 5, 6, 11, 16, 21)):
            row, col = divmod(index, 5)
            cell = ttk.LabelFrame(references, text=f"Cella {tile}", padding=6)
            cell.grid(row=row, column=col, padx=4, pady=4)
            for name, variable in zip(("X", "Y"), self.tile_vars[tile]):
                ttk.Label(cell, text=name).pack(side="left")
                ttk.Entry(cell, textvariable=variable, width=6).pack(side="left", padx=2)
        controls = ttk.Frame(parent)
        controls.pack(fill="x", pady=12)
        for index, (prefix, label) in enumerate((("play", "Gioca / incassa"), ("raise", "Alza puntata"), ("lower", "Abbassa puntata"),
                                                ("difficulty_lower", "Abbassa difficoltà"), ("difficulty_raise", "Alza difficoltà"))):
            group = ttk.LabelFrame(controls, text=label, padding=8)
            row, col = divmod(index, 3)
            group.grid(row=row, column=col, padx=6, pady=4, sticky="w")
            for axis in ("x", "y"):
                variable = tk.IntVar(value=0)
                setattr(self, f"{prefix}_{axis}_var", variable)
                ttk.Label(group, text=axis.upper()).pack(side="left")
                ttk.Entry(group, textvariable=variable, width=7).pack(side="left", padx=2)
        actions = ttk.Frame(parent)
        actions.pack(fill="x", pady=12)
        for text, action in (("Registra coordinate", self.record_coordinates), ("Calcola griglia", self.update_all_tiles),
                             ("Salva calibrazione", self.save_calibration), ("Importa vecchie impostazioni…", self.import_settings)):
            ttk.Button(actions, text=text, command=action).pack(side="left", padx=4)
        self.grid_preview = tk.Text(parent, height=10, state="disabled")
        self.grid_preview.pack(fill="both", expand=True, pady=12)
        ttk.Label(parent, text="Coordinate e tempi possono essere modificati soltanto a laptop disarmato. Salvare conferma la geometria attuale.", wraplength=880).pack(anchor="w")

    def _bet_tab(self, parent):
        ttk.Label(parent, text="Sequenza per impostare la puntata: reset, attese/click facoltativi, target. Non è una progressione di gioco.", wraplength=880).pack(anchor="w", pady=8)
        values = ttk.LabelFrame(parent, text="Pulsanti del gioco", padding=8)
        values.pack(fill="x", pady=5)
        self.bet_values_var = tk.StringVar()
        ttk.Label(values, text="Puntate in euro, in ordine crescente e separate da ; (esempio: 0,10; 0,20; 0,50; 1,00)").pack(anchor="w")
        ttk.Entry(values, textvariable=self.bet_values_var).pack(fill="x", pady=4)
        self.step_list = []
        self.step_labels = {"Reset al minimo": "reset", "Imposta puntata richiesta": "target", "Attendi": "wait", "Click a coordinate": "click"}
        self.steps_tree = ttk.Treeview(parent, columns=("action", "parameters"), show="headings", height=5)
        self.steps_tree.heading("action", text="Azione")
        self.steps_tree.heading("parameters", text="Parametri")
        self.steps_tree.pack(fill="both", expand=True, pady=8)
        controls = ttk.Frame(parent)
        controls.pack(fill="x", pady=5)
        self.step_type = tk.StringVar(value="Attendi")
        ttk.Combobox(controls, textvariable=self.step_type, values=list(self.step_labels), state="readonly", width=25).pack(side="left", padx=3)
        self.step_seconds = tk.StringVar(value="1")
        self.step_x, self.step_y = tk.StringVar(value="0"), tk.StringVar(value="0")
        for label, variable in (("Secondi", self.step_seconds), ("X", self.step_x), ("Y", self.step_y)):
            ttk.Label(controls, text=label).pack(side="left", padx=3)
            ttk.Entry(controls, textvariable=variable, width=6).pack(side="left")
        ttk.Button(controls, text="Aggiungi", command=lambda: self.guarded(self.add_step)).pack(side="left", padx=5)
        for text, action in (("Su", lambda: self.move_step(-1)), ("Giù", lambda: self.move_step(1)), ("Rimuovi", self.remove_step)):
            ttk.Button(controls, text=text, command=action, width=8).pack(side="left", padx=2)
        colors = ttk.LabelFrame(parent, text="Rilevamento", padding=8)
        colors.pack(fill="x", pady=5)
        self.blue_var, self.red_var, self.tolerance_var = tk.StringVar(), tk.StringVar(), tk.IntVar(value=50)
        for label, variable in (("Blu · R;G;B", self.blue_var), ("Rosso · R;G;B", self.red_var), ("Tolleranza RGB", self.tolerance_var)):
            group = ttk.Frame(colors)
            group.pack(side="left", padx=8)
            ttk.Label(group, text=label).pack(anchor="w")
            ttk.Entry(group, textvariable=variable, width=22).pack()
        ttk.Button(parent, text="Salva sequenza e colori", command=self.save_advanced).pack(anchor="w", pady=12)
        ttk.Label(parent, text="Il primo valore della puntata deve corrispondere al minimo fisico del gioco. Reset precede sempre l'applicazione della puntata richiesta.", wraplength=880).pack(anchor="w")

    def _timing_tab(self, parent):
        ttk.Label(parent, text="Attese in secondi · da 0 a 60 · modifica a laptop in pausa", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Label(parent, text="Preparazione iniziale a ogni Abilita: reset puntata → puntata richiesta → Medium UNA VOLTA.\n"
                  "Poi: Gioca → celle / letture → Incassa → griglia → nuovo Gioca, senza ripetere Medium. Una mina salta Incassa.\n"
                  "Le attese prima/dopo si sommano, inclusa la pausa comune dopo ogni click.", wraplength=870).pack(anchor="w", pady=6)
        self.timing_help_var = tk.StringVar(value="Seleziona un campo per sapere esattamente quando viene atteso quel tempo.")
        ttk.Label(parent, textvariable=self.timing_help_var, wraplength=860, relief="groove", padding=8).pack(fill="x", pady=(0, 8))
        area = ttk.Frame(parent)
        area.pack(fill="both", expand=True)
        self.timing_canvas = tk.Canvas(area, highlightthickness=0)
        scroll = ttk.Scrollbar(area, orient="vertical", command=self.timing_canvas.yview)
        self.timing_canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.timing_canvas.pack(side="left", fill="both", expand=True)
        content = ttk.Frame(self.timing_canvas)
        window = self.timing_canvas.create_window((0, 0), window=content, anchor="nw")
        content.bind("<Configure>", lambda event: self.timing_canvas.configure(scrollregion=self.timing_canvas.bbox("all")))
        self.timing_canvas.bind("<Configure>", lambda event: self.timing_canvas.itemconfigure(window, width=event.width))
        self.scroll_canvases[str(parent)] = self.timing_canvas
        groups = (
            ("0 · Pausa comune a tutti i click", (
                ("after_click", "Dopo ogni click del mouse", "Pausa tecnica dopo ciascun click: puntata, difficoltà, Gioca, celle e Incassa. Si somma a ogni altra attesa dopo il click o prima del successivo; sostituisce la pausa automatica del mouse, senza altri 0,1 secondi nascosti."),)),
            ("1 · Medium iniziale · una volta per abilitazione", (
                ("difficulty_lower", "Prima di ciascuno dei 4 click Abbassa difficoltà", "Solo nella preparazione iniziale di ogni abilitazione manuale, dopo la puntata: attesa prima di ciascuno dei quattro click Abbassa difficoltà. Poi segue un solo click Alza difficoltà."),
                ("difficulty_raise", "Prima del click Alza difficoltà (1 click iniziale)", "Attesa prima dell'unico click Alza difficoltà che imposta Medium nella preparazione iniziale. Non viene ripetuto fra le partite."),
                ("after_difficulty", "Dopo Medium iniziale, prima del primo Gioca", "Attesa una sola volta dopo il quinto click della preparazione iniziale. Non si ripete alle partite successive, alla riconnessione, alla ripresa dal master o al solo cambio puntata. Una nuova abilitazione manuale ripete la preparazione."))),
            ("2 · Avvio partita", (
                ("play", "Prima di Gioca", "Attesa immediatamente prima di ciascun click Gioca. Medium è già pronto: la sua preparazione si esegue soltanto prima del primo Gioca di ogni abilitazione manuale. Questa attesa non viene usata per Incassa."),
                ("after_play", "Dopo Gioca, prima di preparare la prima cella", "Attesa dopo il click Gioca. Si somma a Prima della prima cella: dopo Gioca → prima cella → click della prima cella."))),
            ("3 · Prima cella", (
                ("tile", "Prima del click sulla prima cella", "Attesa prima del click sulla prima cella. Dall'apertura della partita si somma a Dopo Gioca."),
                ("after_tile", "Dopo prima cella, prima di leggerne il colore", "Attesa dopo il primo click e prima della lettura del colore. Se la cella è blu, seguono la lettura ed eventualmente Prima della seconda cella."))),
            ("4 · Seconda cella · solo se la prima è blu", (
                ("second_tile", "Prima del click sulla seconda cella", "Attesa dopo aver letto blu sulla prima cella e prima di cliccare la seconda. Fra i due click: Dopo prima cella + lettura/retry + Prima seconda cella."),
                ("after_second_tile", "Dopo seconda cella, prima di leggerne il colore", "Attesa dopo il secondo click e prima della lettura del colore. Soltanto due letture blu consentono il successivo Incassa."))),
            ("5 · Incasso · solo dopo due celle blu", (
                ("collect", "Prima di Incassa", "Attesa prima del click Incassa, distinta da Prima di Gioca. Si somma a Dopo seconda cella e al tempo necessario a leggerne il colore."),)),
            ("6 · Letture e griglia finale", (
                ("retry", "Fra due letture del colore della stessa cella", "Attesa soltanto quando il colore di una cella non è riconosciuto: al massimo tre letture, con questa attesa fra i tentativi."),
                ("reveal", "Prima della prima cattura della griglia finale", "Attesa dopo una mina oppure Incassa, prima di catturare tutte le 25 celle per la prima volta. Dopo Incassa si aggiunge alla pausa comune dopo il click."),
                ("board_retry", "Fra due catture della griglia finale", "Attesa fra una cattura non valida della griglia finale e il tentativo successivo. Al massimo tre catture; separata da Nuova lettura colore di una singola cella."))),
            ("7 · Puntata · all'inizio, poi solo quando cambia", (
                ("reset", "Prima di ogni click Abbassa puntata nel reset", "Attesa prima di ogni click Abbassa puntata della sequenza di reset. Le eventuali azioni Attendi nella sequenza si aggiungono a questo tempo."),
                ("bet", "Prima di ogni click Alza puntata verso il target", "Attesa prima di ogni click Alza puntata necessario a raggiungere la puntata richiesta, dopo il reset al minimo."))),
            ("8 · Fra partite sul laptop", (
                ("between", "Dopo la partita, prima di chiederne un'altra", "Attesa dopo la registrazione del risultato prima di richiedere una nuova autorizzazione. La rete e la disponibilità del master possono aggiungere altro tempo."),)),
        )
        self.delay_vars, self.delay_hints, self.delay_entries = {}, {}, {}
        for title, rows in groups:
            group = ttk.LabelFrame(content, text=title, padding=8)
            group.pack(fill="x", padx=(0, 8), pady=5)
            group.columnconfigure(0, weight=1)
            for row, (key, label, explanation) in enumerate(rows):
                ttk.Label(group, text=label, wraplength=650).grid(row=row, column=0, sticky="w", pady=5)
                variable = tk.StringVar()
                entry = ttk.Entry(group, textvariable=variable, width=10)
                entry.grid(row=row, column=1, sticky="e", padx=(12, 4), pady=5)
                ttk.Label(group, text="s").grid(row=row, column=2)
                entry.bind("<FocusIn>", lambda event, text=explanation: self.timing_help_var.set(text))
                self.delay_vars[key], self.delay_hints[key], self.delay_entries[key] = variable, explanation, entry
        ttk.Button(parent, text="Salva tempi", command=lambda: self.save_advanced("timing")).pack(anchor="w", pady=(10, 0))

    def _timing_scroll(self, event):
        canvas = self.scroll_canvases.get(self.notebook.select())
        if canvas is not None and not isinstance(getattr(event, "widget", None), tk.Text):
            canvas.yview_scroll(-int(event.delta / 120), "units")

    def _scroll_focus(self, event):
        canvas = self.scroll_canvases.get(self.notebook.select())
        widget = event.widget
        ancestor = widget
        while ancestor is not None and ancestor is not canvas:
            ancestor = getattr(ancestor, "master", None)
        if canvas is None or ancestor is None or widget is canvas:
            return
        bounds = canvas.bbox("all")
        if not bounds or bounds[3] <= canvas.winfo_height():
            return
        top = canvas.canvasy(widget.winfo_rooty() - canvas.winfo_rooty())
        bottom = top + widget.winfo_height()
        if top < canvas.canvasy(0):
            canvas.yview_moveto(max(0, top) / bounds[3])
        elif bottom > canvas.canvasy(canvas.winfo_height()):
            canvas.yview_moveto(max(0, bottom - canvas.winfo_height()) / bounds[3])

    def render_steps(self):
        self.steps_tree.delete(*self.steps_tree.get_children())
        labels = {value: key for key, value in self.step_labels.items()}
        for index, step in enumerate(self.step_list):
            detail = f"{step['seconds']} s" if step["action"] == "wait" else str(step["point"]) if step["action"] == "click" else ""
            self.steps_tree.insert("", "end", iid=str(index), values=(labels[step["action"]], detail))

    def add_step(self):
        self.idle_required()
        action = self.step_labels[self.step_type.get()]
        step = {"action": action}
        if action == "wait":
            step["seconds"] = float(self.step_seconds.get().replace(",", "."))
        elif action == "click":
            step["point"] = [int(self.step_x.get()), int(self.step_y.get())]
        self.step_list.append(step)
        self.render_steps()

    def move_step(self, direction):
        def move():
            self.idle_required()
            selected = self.steps_tree.selection()
            if selected:
                index = int(selected[0])
                target = index + direction
                if 0 <= target < len(self.step_list):
                    self.step_list[index], self.step_list[target] = self.step_list[target], self.step_list[index]
                    self.render_steps()
                    self.steps_tree.selection_set(str(target))
        self.guarded(move)

    def remove_step(self):
        def remove():
            self.idle_required()
            selected = self.steps_tree.selection()
            if selected:
                self.step_list.pop(int(selected[0]))
                self.render_steps()
        self.guarded(remove)

    def guarded(self, action):
        try:
            action()
            self.error_var.set("")
        except Exception as exc:
            self.error_var.set(str(exc))
            self.log_message(str(exc))

    def idle_required(self):
        if self.client.armed.is_set() or self.client.busy.is_set() or not self.client.jobs.empty():
            raise ValueError("Disarmare e attendere il completamento prima di modificare la calibrazione")

    def reload_fields(self):
        state = self.store.snapshot()
        for key in ("name", "mines", "multiplier", "selection"):
            self.fields[key].set(state["config"][key])
        self.fields["multiplier"].set(str(state["config"]["multiplier"]).replace(".", ","))
        self.fields["stake"].set(display(state["config"]["stake"]))
        self.fields["first"].set(state["config"]["pair"][0])
        self.fields["second"].set(state["config"]["pair"][1])
        self.edit_revision = state["revision"]

    def save_profile(self):
        def save():
            profile = config({"name": self.fields["name"].get(), "stake": money(self.fields["stake"].get()),
                "mines": int(self.fields["mines"].get()), "multiplier": self.fields["multiplier"].get().replace(",", "."),
                "selection": self.fields["selection"].get(),
                "pair": [int(self.fields["first"].get()), int(self.fields["second"].get())]})
            state = self.store.snapshot()
            if state.get("unpair_requested"):
                raise ValueError("Dissociazione in corso: attendere prima di modificare la configurazione")
            if state["connection"]:
                self.store.command("device", {"revision": self.edit_revision, "config": profile})
                self.client.wake()
            else:
                self.store.update(config=profile)
                self.reload_fields()
            if any(profile[key] != state["config"][key] for key in ("mines", "multiplier")):
                self.profile_confirmed.set(False)
        self.guarded(save)

    def correct_balance(self):
        def correct():
            if self.store.snapshot().get("unpair_requested"):
                raise ValueError("Dissociazione in corso: completare la verifica dal master")
            self.client.disarm()
            if self.client.busy.is_set() or not self.client.jobs.empty():
                raise ValueError("Disarmo richiesto: attendere la fine della partita, poi riaprire la verifica")
            state = self.store.snapshot()
            if any(c["action"] in ("balance", "reconcile") for c in state["commands"]):
                raise ValueError("Una rettifica attende già la conferma del master: attendere il collegamento")
            result = BalanceDialog(self.root, state).result
            if result is None:
                return
            if self.client.busy.is_set() or not self.client.jobs.empty():
                raise ValueError("Attendere la fine della partita e verificare nuovamente il saldo")
            if not state["connection"]:
                self.store.update(balance=result["balance"], confirmed=True)
                self.balance_sync_var.set("Saldo iniziale confermato: " + euro(result["balance"]))
                self._render_status()
                return
            command = self.store.command("reconcile" if "outcome" in result else "balance", result)
            self.balance_command_id = command["id"]
            self.balance_sync_var.set("Rettifica inviata: attendo la conferma del master. Saldo non ancora aggiornato.")
            self.client.wake()
        self.guarded(correct)

    def reset_local(self):
        def reset():
            self.client.disarm()
            if self.pair_thread and self.pair_thread.is_alive():
                raise ValueError("Attendere la fine dell'associazione prima di ripartire da zero")
            if not messagebox.askyesno("Archivia e riparti da zero", "Verrà creato un backup completo dei dati locali.\n\n"
                    "Il laptop avrà una nuova identità e dovrà essere associato di nuovo. Dovrai reinserire il saldo effettivo del gioco. "
                    "Coordinate, colori e tempi di calibrazione saranno conservati.\n\n"
                    "Lo storico del master resta conservato: per ripartire da zero anche nel master usa Archivia e riparti da zero nel suo pannello.\n\n"
                    "Continuare?", parent=self.root):
                return
            archive = self.client.reset_local()
            if archive is None:
                self.balance_sync_var.set("Archiviazione richiesta: attendo la dissociazione e la conferma del master")
                self.log_message("Ripartenza da zero richiesta: attendo il master prima di archiviare i dati locali.")
            else:
                self._reset_complete(archive)
        self.guarded(reset)

    def _reset_complete(self, archive):
        self.last_reply, self.balance_command_id = None, None
        self.balance_sync_var.set("Nuovo avvio: verifica il saldo effettivo prima di associare il laptop")
        self.profile_confirmed.set(False)
        self.error_var.set("")
        self.pair_code.delete(0, "end")
        self.reload_fields()
        self.load_calibration()
        self._render_status()
        self.log_message(f"Dati precedenti archiviati in {archive}. Confermare il saldo e associare di nuovo il laptop.")

    def pair(self):
        code = self.pair_code.get()
        if self.pair_thread and self.pair_thread.is_alive():
            return
        state = self.store.snapshot()
        if not code.strip() and not state.get("pair_pending"):
            self.error_var.set("Nel master scegliere Associa laptop → Genera codice monouso, poi incollare il codice qui")
            self.pair_code.focus_set()
            return
        if not state["confirmed"]:
            self.correct_balance()
            if not self.store.snapshot()["confirmed"]:
                return
        self.error_var.set("")
        self.connection_var.set("Associazione al master in corso…")
        def work():
            try:
                asyncio.run(associate(self.store, code))
                self.ui_queue.put(("paired", None))
                self.client.wake()
            except Exception as exc:
                self.ui_queue.put(("error", str(exc)))
        self.pair_thread = threading.Thread(target=work, name="pairing", daemon=False)
        self.pair_thread.start()

    def change_address(self):
        def change():
            from urllib.parse import urlsplit
            self.idle_required()
            c = self.store.snapshot()["connection"]
            if not c:
                raise ValueError("Per la prima associazione usare il codice generato nel master; Indirizzo serve per un laptop già associato")
            address = simpledialog.askstring("Indirizzo master", "Nuovo indirizzo HTTPS (certificato e credenziale restano invariati):",
                                            initialvalue=c["url"], parent=self.root)
            if address is None:
                return
            parsed = urlsplit(address)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
                raise ValueError("Usare https://indirizzo:porta")
            c["url"] = address.rstrip("/")
            self.store.update(connection=c)
            self.client.reconnect.set()
            self.client.wake()
        self.guarded(change)

    def unpair(self):
        def request():
            state = self.store.snapshot()
            if not state["connection"]:
                raise ValueError("Questo laptop non è associato")
            if (state.get("master_round") or state["round"] or {}).get("status") == "uncertain":
                raise ValueError("Riconciliare la partita nel master prima di dissociare")
            self.client.disarm()
            if not state.get("unpair_requested"):
                self.store.command("unpair", {})
                self.store.update(unpair_requested=True)
            self.client.wake()
            self.log_message("Dissociazione richiesta: attendo il master e il completamento delle operazioni aperte")
        self.guarded(request)

    def load_calibration(self):
        c = self.store.snapshot()["calibration"]
        for key, point in c["tiles"].items():
            for var, value in zip(self.tile_vars[int(key)], point):
                var.set(value)
        for key in ("play", "raise", "lower", "difficulty_lower", "difficulty_raise"):
            for axis, value in zip(("x", "y"), c[key]):
                getattr(self, f"{key}_{axis}_var").set(value)
        self.bet_values_var.set("; ".join(display(v) for v in c["bet_values"]))
        self.step_list = c["steps"]
        self.render_steps()
        for key, value in c["delays"].items():
            self.delay_vars[key].set(str(value).replace(".", ","))
        self.blue_var.set(";".join(str(c["blue"][key]) for key in ("r", "g", "b")))
        self.red_var.set(";".join(str(c["red"][key]) for key in ("r", "g", "b")))
        self.tolerance_var.set(c["tolerance"])
        self.update_all_tiles()

    def update_all_tiles(self):
        self.coordinate_manager.populate_tile_vars(self.tile_vars, self.tile_vars[1][0].get(), self.tile_vars[1][1].get(),
            [self.tile_vars[i][0] for i in (2, 3, 4, 5)], [self.tile_vars[i][1] for i in (6, 11, 16, 21)])
        x0, y0 = self.tile_vars[1][0].get(), self.tile_vars[1][1].get()
        for i in (2, 3, 4, 5):
            self.tile_vars[i][1].set(y0)
        for i in (6, 11, 16, 21):
            self.tile_vars[i][0].set(x0)
        self.grid_preview.configure(state="normal")
        self.grid_preview.delete("1.0", "end")
        self.grid_preview.insert("1.0", self.coordinate_manager.build_preview_text(self.tile_vars))
        self.grid_preview.configure(state="disabled")

    def record_coordinates(self):
        def record():
            self.idle_required()
            CoordinateRecorder(self).start()
        self.guarded(record)

    def save_calibration(self):
        def save():
            self.idle_required()
            self.update_all_tiles()
            c = self.store.snapshot()["calibration"]
            c["tiles"] = {str(i): [x.get(), y.get()] for i, (x, y) in self.tile_vars.items()}
            for key in ("play", "raise", "lower", "difficulty_lower", "difficulty_raise"):
                c[key] = [getattr(self, f"{key}_{axis}_var").get() for axis in ("x", "y")]
            c["screen"] = list(pyautogui.size())
            validate_calibration(c, c["screen"], self.store.snapshot()["config"])
            self.store.update(calibration=c, applied_revision=0)
            self.profile_confirmed.set(False)
            self.log_message("Calibrazione salvata; confermare nuovamente il profilo")
        self.guarded(save)

    def save_advanced(self, section="bet"):
        def save():
            self.idle_required()
            c = self.store.snapshot()["calibration"]
            if section == "timing":
                c["delays"] = {key: float(var.get().replace(",", ".")) for key, var in self.delay_vars.items()}
            else:
                c["bet_values"] = [money(v.strip()) for v in self.bet_values_var.get().split(";")]
                c["steps"] = self.step_list
                for key, variable in (("blue", self.blue_var), ("red", self.red_var)):
                    channels = [int(v.strip()) for v in variable.get().split(";")]
                    if len(channels) != 3:
                        raise ValueError("Inserire i tre canali R;G;B")
                    c[key] = dict(zip(("r", "g", "b"), channels))
                c["tolerance"] = self.tolerance_var.get()
            validate_calibration(c, pyautogui.size(), self.store.snapshot()["config"])
            self.store.update(calibration=c, applied_revision=0)
            self.profile_confirmed.set(False)
            self.log_message("Tempi salvati; confermare nuovamente il profilo" if section == "timing" else "Sequenza puntata e colori salvati; confermare nuovamente il profilo")
        self.guarded(save)

    def import_settings(self):
        def load():
            self.idle_required()
            path = filedialog.askopenfilename(filetypes=[("Impostazioni JSON", "*.json")], parent=self.root)
            if path:
                self.store.import_legacy(path)
                self.load_calibration()
                self.profile_confirmed.set(False)
                self.log_message("Importate coordinate e pause; il file originale è invariato. Salvare la calibrazione.")
        self.guarded(load)

    def arm(self):
        def ready():
            if self.coordinate_recorder:
                raise ValueError("Chiudere prima il recorder")
            if not self.profile_confirmed.get():
                raise ValueError("Confermare prima profilo, coordinate e credito")
            state = self.store.snapshot()
            validate_calibration(state["calibration"], pyautogui.size(), state["config"])
            self.client.arm()
        self.guarded(ready)

    def disarm(self):
        self.client.disarm()
        self._render_status()

    def pause_local(self):
        self.client.disarm()
        self.ui_queue.put(("paused", None))

    def emergency(self):
        self.client.disarm(emergency=True)
        self.ui_queue.put(("error", "Emergenza: verificare la partita prima di riarmare"))

    def _key(self, key):
        if key == keyboard.Key.esc and (self.client.armed.is_set() or self.client.busy.is_set()):
            self.emergency()
        elif (getattr(key, "char", "") or "").lower() == "p":
            if not getattr(self, "pause_key_down", False) and (self.client.armed.is_set() or self.client.busy.is_set()):
                self.pause_local()
            self.pause_key_down = True

    def _key_release(self, key):
        if (getattr(key, "char", "") or "").lower() == "p":
            self.pause_key_down = False

    def log_message(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        if int(self.log.index("end-1c").split(".")[0]) > 300:
            self.log.delete("1.0", "50.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _render_status(self):
        state = self.store.snapshot()
        paired = bool(state["connection"])
        pairing = bool(self.pair_thread and self.pair_thread.is_alive())
        unpairing = state.get("unpair_requested", False)
        pending_balance = any(c["action"] in ("balance", "reconcile") for c in state["commands"])
        self.ready_button.configure(state="normal" if paired and not unpairing and not pending_balance and not self.client.armed.is_set() else "disabled")
        self.address_button.configure(state="normal" if paired else "disabled")
        self.unpair_button.configure(state="normal" if paired and not unpairing else "disabled")
        self.pair_button.configure(state="disabled" if paired or pairing else "normal")
        if not paired and not pairing:
            self.connection_var.set("Master non associato · completare Associazione qui sotto")
        self.balance_var.set("Saldo calcolato: " + euro(state["balance"]) + (" · da confermare sul gioco" if not state["confirmed"] else ""))
        phase = self.last_reply.get("session", {}).get("status") if self.last_reply and self.last_reply.get("session") else None
        self.status_var.set("Dissociazione in corso · attendo completamento e conferma del master" if unpairing else
                            "Partita / impostazione puntata in corso" if self.client.busy.is_set() else
                            "Disabilitato · verifica il gioco e premi Abilita questo laptop" if not self.client.armed.is_set() or self.client.emergency.is_set() else
                            "Abilitato · sessione in pausa: premi Riprendi sessione nel master" if phase == "paused_manual" else
                            "Abilitato · in attesa del minimo di laptop: ripresa automatica dal master" if phase == "paused_minimum" else
                            "Abilitato · sessione in esecuzione" if phase == "active" else
                            "Abilitato · il master sta completando la sessione" if phase == "draining" else
                            "Abilitato · premi Avvia nuova sessione nel master")
        if self.last_reply:
            session = self.last_reply.get("session")
            d = self.last_reply["device"]
            outcome = (d.get("last_result") or {}).get("outcome")
            result = {"win": "vinta", "loss": "persa", "cancel": "annullata", "unknown": "non noto"}.get(outcome, "—")
            self.session_var.set((f"Sessione {session['status']} · risultato gruppo {euro(session['progress'])}" if session else "Nessuna sessione") + f" · ultimo esito {result}")
            own = state.get("session_net")
            self.session_var.set(self.session_var.get() + (f"\nQuesto laptop: sessione {euro(own)}" if own is not None else "") +
                                 f" · netto registrato {euro(state.get('net', 0))} · vinte {state.get('wins', 0)} / perse {state.get('losses', 0)}")
        else:
            self.session_var.set("Nessuna sessione")
        if state["error"]:
            self.error_var.set(state["error"])

    def _poll(self):
        if self.closing:
            return
        while True:
            try:
                kind, value = self.ui_queue.get_nowait()
            except queue.Empty:
                break
            if kind == "reply":
                self.last_reply = value
                if value.get("command_id") == self.balance_command_id and self.balance_command_id:
                    self.balance_command_id = None
                    if value.get("command_error"):
                        self.balance_sync_var.set("Rettifica rifiutata dal master: " + value["command_error"])
                    else:
                        self.balance_sync_var.set("Saldo confermato dal master: " + euro(value["device"]["balance"]))
                connection = self.store.snapshot()["connection"]
                if connection:
                    self.connection_var.set("Master collegato · " + connection["url"])
            elif kind == "unpaired":
                self.last_reply = None
                self.profile_confirmed.set(False)
                self.error_var.set("")
                self.log_message("Laptop dissociato. Saldo e calibrazione conservati; lo storico rimane nel master.")
            elif kind == "paired":
                self.pair_code.delete(0, "end")
                self.error_var.set("")
                self.connection_var.set("Associato: collegamento al master in corso")
            elif kind == "reset":
                self._reset_complete(value)
            elif kind == "connection":
                self.connection_var.set(value)
            elif kind == "error":
                self.error_var.set(value)
                self.log_message(value)
            elif kind == "paused":
                self.log_message("Pausa laptop richiesta: completo la partita aperta, poi libero il mouse. Per riprendere usa Abilita questo laptop. Gli altri laptop restano sotto il controllo del master.")
            elif kind == "callback":
                value()
        self._render_status()
        try:
            self.mouse_var.set("Mouse: " + str(tuple(pyautogui.position())))
        except Exception:
            pass
        self.poll_id = self.root.after(100, self._poll)

    def on_closing(self):
        if self.closing:
            return
        self.closing = True
        self.root.after_cancel(self.poll_id)
        if self.coordinate_recorder:
            self.coordinate_recorder._cancel()
        if self.keyboard_listener:
            self.keyboard_listener.stop()
        self.client.disarm()
        def drain():
            if self.client.busy.is_set() or (self.pair_thread and self.pair_thread.is_alive()):
                self.root.after(100, drain)
                return
            if self.services_started:
                self.client.stop()
                if self.client.network.is_alive() or self.client.worker.is_alive():
                    self.root.after(100, drain)
                    return
            self.store.close()
            self.root.destroy()
        drain()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir")
    parser.add_argument("--self-test", help="Verifica GUI nascosta e scrive un JSON, senza click o collegamenti")
    args = parser.parse_args()
    directory = Path(args.data_dir) if args.data_dir else data_directory()
    directory.mkdir(exist_ok=True, parents=True)
    lock = InstanceLock(directory)
    try:
        root = tk.Tk()
        if args.self_test:
            root.withdraw()
        app = GrattaEVinciGUI(root, ClientStore(directory / "laptop.sqlite3"), start_services=not bool(args.self_test))
        if args.self_test:
            names = [app.notebook.tab(t, "text") for t in app.notebook.tabs()]
            assert names == ["Stato", "Calibrazione", "Cambio/reset puntata", "Tempi"]
            app.on_closing()
            Path(args.self_test).write_text(json.dumps({"ok": True, "tabs": names, "physical_clicks": 0}), encoding="utf-8")
        else:
            root.mainloop()
    finally:
        lock.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        messagebox.showerror("Mine · avvio non riuscito", str(exc))
        raise
