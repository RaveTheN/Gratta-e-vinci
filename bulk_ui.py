"""Three independent laptop configurations and a simple money comparison."""

from copy import deepcopy
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

from bulk_simulation import _validate_snapshot
from bulk_export import laptop_totals
from game_config import BETTING_MODES, MAX_PICKS


class LaptopPanel:
    def __init__(self, app, parent, number):
        self.app, self.number = app, number
        self.frame = ttk.LabelFrame(parent, text=f"Laptop {number}", padding=8)
        self.frame.grid(row=0, column=number - 1, sticky="nsew", padx=4)
        parent.columnconfigure(number - 1, weight=1, uniform="laptops")
        self.values = {}
        fields = (("starting_cash", "Capitale iniziale €", "500"),
                  ("target_profit", "Obiettivo guadagno €", "3"),
                  ("max_loss", "Limite perdita €", "20"),
                  ("max_rounds", "Massimo giocate", "1000"),
                  ("mode", "Modalità", "normal"),
                  ("difficulty", "Difficoltà", "medium"),
                  ("max_picks", "Caselle da trovare", "3"))
        self.mode_sequences = deepcopy(BETTING_MODES)
        self.custom_steps = [{"b": .1, "p": 2, "d": "medium"}]
        self.game_controls = []
        for row, (key, label, default) in enumerate(fields):
            self.values[key] = tk.StringVar(value=default)
            ttk.Label(self.frame, text=label).grid(row=row, column=0, sticky="w", pady=3)
            if key in ("mode", "difficulty", "max_picks"):
                choices = {"mode": [*BETTING_MODES, "custom"], "difficulty": ["low", "medium", "high"], "max_picks": list(range(1, MAX_PICKS + 1))}[key]
                widget = ttk.Combobox(self.frame, textvariable=self.values[key], values=choices, state="readonly", width=9)
            else:
                widget = ttk.Entry(self.frame, textvariable=self.values[key], width=10)
            widget.grid(row=row, column=1, sticky="ew", padx=(5, 0))
            if key in ("difficulty", "max_picks"):
                self.game_controls.append(widget)
        self.values["grinding_enabled"] = tk.BooleanVar(value=False)
        self.values["p_random"] = tk.BooleanVar(value=False)
        self.values["grinding_range"] = tk.StringVar(value="0.5")
        ttk.Checkbutton(self.frame, text="Grinding", variable=self.values["grinding_enabled"]).grid(row=7, column=0, columnspan=2, sticky="w", pady=3)
        ttk.Label(self.frame, text="Intervallo grinding €").grid(row=8, column=0, sticky="w")
        ttk.Entry(self.frame, textvariable=self.values["grinding_range"], width=10).grid(row=8, column=1, sticky="ew", padx=(5, 0))
        ttk.Checkbutton(self.frame, text="Caselle casuali nel grinding", variable=self.values["p_random"]).grid(row=9, column=0, columnspan=2, sticky="w")
        ttk.Button(self.frame, text="Modifica sequenza…", command=self.edit_sequence).grid(row=10, column=0, columnspan=2, sticky="ew", pady=(7, 3))
        self.preview = ttk.Label(self.frame, wraplength=230, justify="left")
        self.preview.grid(row=11, column=0, columnspan=2, sticky="w", pady=3)
        ttk.Button(self.frame, text="Copia da Settings", command=self.copy_current).grid(row=12, column=0, columnspan=2, sticky="ew", pady=(7, 0))
        self.values["mode"].trace_add("write", lambda *_: self.refresh())
        self.refresh()

    def refresh(self):
        mode = self.values["mode"].get()
        for widget in self.game_controls:
            widget.config(state="disabled" if mode == "custom" else "readonly")
        if mode == "custom":
            text = f"Custom: {len(self.custom_steps)} passi. Caselle e difficoltà sono indicate in ogni passo."
        else:
            text = "Puntate: " + " → ".join(f"{value:g}" for value in self.mode_sequences.get(mode, [])) + " €"
        self.preview.config(text=text)

    def copy_current(self):
        try:
            source = self.app.game_engine._build_bulk_snapshot()
            self.mode_sequences = deepcopy(self.app.betting_modes)
            self.custom_steps = deepcopy(source["custom_mode"])
            for key, variable in self.values.items():
                variable.set(source[key])
            self.refresh()
        except (KeyError, ValueError, tk.TclError) as error:
            messagebox.showerror(f"Laptop {self.number}", str(error))

    def state(self):
        return {"values": {key: var.get() for key, var in self.values.items()},
                "sequences": deepcopy(self.mode_sequences), "custom_steps": deepcopy(self.custom_steps)}

    def restore(self, state):
        self.mode_sequences = deepcopy(state["sequences"])
        self.custom_steps = deepcopy(state["custom_steps"])
        for key, var in self.values.items():
            if key in state["values"]:
                var.set(state["values"][key])
        self.refresh()

    def snapshot(self):
        # Read only shared game rules; all strategy/financial fields belong to this laptop.
        settings = {"bet_values": list(self.app.bulk_bet_values),
                    "mine_config": {d: v.get() for d, v in self.app.bulk_mine_config_vars.items()},
                    "win_multipliers": {d: {p: v.get() for p, v in values.items()}
                                        for d, values in self.app.bulk_win_multiplier_vars.items()},
                    "betting_modes": deepcopy(self.mode_sequences), "custom_mode": deepcopy(self.custom_steps)}
        try:
            settings.update({key: var.get() for key, var in self.values.items()})
            if settings["mode"] not in (*BETTING_MODES, "custom"):
                raise ValueError("Scegli una modalità disponibile")
            settings = _validate_snapshot(settings)
        except (KeyError, ValueError, TypeError, tk.TclError) as error:
            raise ValueError(f"Laptop {self.number}: {error}") from error
        settings["label"] = f"Laptop {self.number}"
        return settings

    def edit_sequence(self):
        mode = self.values["mode"].get()
        dialog = tk.Toplevel(self.app.root)
        dialog.title(f"Laptop {self.number} — sequenza {mode}")
        dialog.transient(self.app.root)
        dialog.grab_set()
        if mode != "custom":
            ttk.Label(dialog, text="Puntate in ordine, separate da ;. Usa il punto per i decimali.", padding=8).pack(anchor="w")
            text = scrolledtext.ScrolledText(dialog, height=4, width=65)
            text.insert("1.0", "; ".join(f"{v:g}" for v in self.mode_sequences[mode]))
            text.pack(fill="both", expand=True, padx=8)
            def collect():
                return [float(v.strip()) for v in text.get("1.0", "end").strip().split(";")]
        else:
            ttk.Label(dialog, text="Ogni riga è un passo della sequenza di questo laptop.\nDa 5 a 8 celle sono disponibili solo con medium.", padding=8).pack(anchor="w")
            canvas = tk.Canvas(dialog, width=430, height=360, highlightthickness=0)
            scroll = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
            canvas.configure(yscrollcommand=scroll.set)
            scroll.pack(side="right", fill="y")
            canvas.pack(fill="both", expand=True)
            rows_frame = ttk.Frame(canvas)
            canvas.create_window(0, 0, window=rows_frame, anchor="nw")
            rows_frame.bind("<Configure>", lambda _: canvas.configure(scrollregion=canvas.bbox("all")))
            for col, title in enumerate(("Passo", "Puntata €", "Caselle", "Difficoltà")):
                ttk.Label(rows_frame, text=title).grid(row=0, column=col, padx=6)
            rows = []
            def add(step=None):
                step = step or {"b": .1, "p": 2, "d": "medium"}
                variables = [tk.StringVar(value=step[key]) for key in ("b", "p", "d")]
                index = len(rows) + 1
                widgets = [ttk.Label(rows_frame, text=str(index)), ttk.Entry(rows_frame, textvariable=variables[0], width=10),
                           ttk.Combobox(rows_frame, textvariable=variables[1], values=list(range(1, MAX_PICKS + 1)), state="readonly", width=7),
                           ttk.Combobox(rows_frame, textvariable=variables[2], values=["low","medium","high"], state="readonly", width=10)]
                for col, widget in enumerate(widgets):
                    widget.grid(row=index, column=col, padx=6, pady=3)
                rows.append((variables, widgets))
            def remove():
                if len(rows) > 1:
                    for widget in rows.pop()[1]:
                        widget.destroy()
            for step in self.custom_steps:
                add(step)
            if not rows:
                add()
            controls = ttk.Frame(dialog)
            controls.pack(fill="x", padx=8)
            ttk.Button(controls, text="Aggiungi passo", command=add).pack(side="left")
            ttk.Button(controls, text="Rimuovi ultimo", command=remove).pack(side="left", padx=5)
            def collect():
                return [{"b": float(v[0].get()), "p": float(v[1].get()), "d": v[2].get()} for v, _ in rows]
        def save():
            previous = self.state()
            try:
                if mode == "custom":
                    self.custom_steps = collect()
                else:
                    self.mode_sequences[mode] = collect()
                self.snapshot()
            except (ValueError, TypeError, KeyError) as error:
                self.restore(previous)
                messagebox.showerror("Sequenza", str(error), parent=dialog)
                return
            self.refresh()
            dialog.destroy()
        ttk.Button(dialog, text="Salva per questo laptop", command=save).pack(pady=8)


def add_laptop_results(notebook, batch):
    page = ttk.Frame(notebook, padding=10)
    notebook.add(page, text="Confronto laptop")
    ttk.Label(page, text="Guadagni = somma dei profitti delle simulazioni positive.\n"
              "Perdite = somma delle perdite delle simulazioni negative. Netto = guadagni − perdite.",
              wraplength=900).pack(anchor="w", pady=(0, 8))
    if batch["status"] != "completed":
        ttk.Label(page, text="Test incompleto: i laptop possono avere un numero diverso di simulazioni. Le simulazioni interrotte sono escluse.",
                  foreground="#9a4916", wraplength=900).pack(anchor="w", pady=5)
    cards = ttk.Frame(page)
    cards.pack(fill="x")
    totals = []
    for index, config in enumerate(batch["configurations"]):
        s = laptop_totals(config)
        totals.append(s)
        frame = ttk.LabelFrame(cards, text=config["label"], padding=10)
        frame.grid(row=index//3, column=index%3, sticky="nsew", padx=5, pady=5)
        cards.columnconfigure(index%3, weight=1, uniform="results")
        ttk.Label(frame, text=f"Simulazioni complete: {s['completed']}").pack(anchor="w")
        ttk.Label(frame, text=f"Giocate totali: {s['rounds']}").pack(anchor="w")
        for label, key, color in (("Guadagni", "gains", "#19703a"), ("Perdite", "losses", "#b3261e"),
                                  ("Netto", "net", "#19703a" if (s["net"] or 0) >= 0 else "#b3261e")):
            value = "—" if s[key] is None else f"{s[key]:+.2f} €" if key == "net" else f"{s[key]:.2f} €"
            ttk.Label(frame, text=f"{label}: {value}", foreground=color, font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=5)
        avg = "—" if s["average"] is None else f"{s['average']:+.2f} €"
        ttk.Label(frame, text=f"Netto medio per simulazione: {avg}", wraplength=250).pack(anchor="w", pady=4)
        worst = "—" if s["worst"] is None else f"{s['worst']:+.2f} €"
        ttk.Label(frame, text=f"Peggiore simulazione: {worst}", wraplength=250).pack(anchor="w")
    if totals and batch["status"] == "completed" and all(t["completed"] for t in totals):
        total = sum(t["net"] for t in totals)
        ttk.Label(page, text=f"Risultato netto complessivo: {total:+.2f} €", font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=15)
    ttk.Label(page, text="Ogni simulazione riparte dal capitale impostato. Gli importi sono risultati simulati, non una previsione mensile; costi dei laptop esclusi.",
              wraplength=900).pack(anchor="w", pady=5)
    ttk.Label(page, text="Le giocate dei laptop sono indipendenti. Saldi finali uguali possono comunque capitare, soprattutto quando viene raggiunto lo stesso obiettivo.",
              wraplength=900).pack(anchor="w", pady=5)
