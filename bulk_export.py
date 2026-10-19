"""Portable bulk-test snapshots and Excel reports (no GUI dependencies)."""

import json
import math
import os
from pathlib import Path
import tempfile
import csv

from openpyxl import Workbook
from openpyxl.cell import Cell
from openpyxl.chart import BarChart, Reference
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo
from bulk_simulation import economic_summary


PERCENT_FORMAT = '0.00"%"'
STOP_LABELS = {
    "target": "Target raggiunto",
    "max_loss": "Perdita massima raggiunta",
    "max_rounds": "Limite di round",
    "insufficient_funds": "Saldo insufficiente",
    "interrupted": "Interrotta dall'utente",
    "time_limit": "Tempo disponibile terminato",
    "preventive_stop": "Puntata fermata prima di superare il limite",
    "total_loss": "Limite di perdita complessiva",
    "period_end": "Periodo completato",
}
METRICS = [
    ("completed_runs", "Simulazioni completate"),
    ("interrupted_runs", "Simulazioni interrotte"),
    ("target_rate", "Target raggiunto (%)"),
    ("target_ci_low", "Target: IC 95% inferiore (%)"),
    ("target_ci_high", "Target: IC 95% superiore (%)"),
    ("positive_rate", "Sessioni in profitto (%)"),
    ("positive_ci_low", "In profitto: IC 95% inferiore (%)"),
    ("positive_ci_high", "In profitto: IC 95% superiore (%)"),
    ("avg_profit", "Profitto medio"),
    ("median_profit", "Profitto mediano"),
    ("min_profit", "Profitto peggiore"),
    ("max_profit", "Profitto migliore"),
    ("p05_profit", "Profitto: percentile 5"),
    ("p95_profit", "Profitto: percentile 95"),
    ("avg_rounds", "Round medi"),
    ("max_drawdown", "Massimo drawdown osservato"),

]
PERCENT_METRICS = {
    "target_rate", "target_ci_low", "target_ci_high", "positive_rate",
    "positive_ci_low", "positive_ci_high",
    "negative_rate", "large_loss_rate", "funds_stop_rate",
}
SETTINGS_LABELS = {
    "starting_cash": "Saldo iniziale",
    "target_profit": "Profitto obiettivo",
    "max_loss": "Stop: perdita massima dal picco",
    "max_rounds": "Massimo numero di round",
    "mode": "Modalità di puntata",
    "betting_sequence": "Sequenza delle puntate",
    "max_picks": "Picks",
    "difficulty": "Difficoltà",
    "grinding_enabled": "Grinding abilitato",
    "grinding_range": "Intervallo grinding",
    "p_random": "Picks casuali",
    "win_multipliers": "Moltiplicatori per difficoltà / picks",
    "mine_config": "Numero mine per difficoltà",
    "custom_mode": "Step custom: puntata, picks, difficoltà",
    "betting_modes": "Sequenze delle modalità",
    "bet_values": "Valori delle puntate",
    "label": "Nome configurazione",
    "activity": "Attività: PC, giorni, costi e regole di ripartenza",
    "loss_basis": "Base del limite di perdita: peak=picco, initial=inizio giornata/sessione",
    "prevent_overrun": "Ferma prima della puntata che potrebbe superare il limite",
    "seconds_per_round": "Secondi stimati per giocata (pause comprese)",
    "time_limit_hours": "Ore disponibili (0=solo limite round)",
    "risk_threshold": "Soglia della perdita da monitorare",
    "model_source": "Provenienza delle regole del modello",
    "model_verified": "Regole dichiarate verificate dall'utente",
}


def enriched_config(config):
    complete = [r for r in config["runs"] if r["status"] != "interrupted"]
    return {**config, "summary": {**config["summary"], **economic_summary(
        complete, config["settings"].get("risk_threshold", 100))}}


def laptop_totals(config):
    """Session gains and losses must add up to the net, excluding unfinished work."""
    profits = [run["profit"] for run in config["runs"] if run["status"] != "interrupted"]
    gains = math.fsum(p for p in profits if p > 0)
    losses = -math.fsum(p for p in profits if p < 0)
    return {"completed": len(profits), "rounds": sum(r.get("rounds", 0) for r in config["runs"] if r["status"] != "interrupted"),
            "gains": gains if profits else None,
            "losses": losses if profits else None, "net": gains - losses if profits else None,
            "average": (gains - losses) / len(profits) if profits else None,
            "worst": min(profits) if profits else None}


def _write_laptops(sheet, batch, configurations):
    _append(sheet, ["CONFRONTO LAPTOP — Guadagni, perdite e risultato netto"], header=True)
    _append(sheet, ["Guadagni = profitti delle simulazioni positive. Perdite = perdite delle simulazioni negative. Netto = guadagni − perdite."])
    _append(sheet, ["Ogni simulazione riparte dal capitale impostato. Costi dei laptop esclusi; non è una previsione mensile."])
    _append(sheet, ["Test completo" if batch["status"] == "completed" else "Test incompleto: confrontare anche il numero di simulazioni completate. Interrotte escluse."])
    _append(sheet, ["Laptop", "Simulazioni completate", "Guadagni €", "Perdite €", "Netto €", "Netto medio per simulazione €", "Peggiore simulazione €", "Giocate totali"], header=True)
    for config in configurations:
        totals = laptop_totals(config)
        cells = _append(sheet, [config["label"], *[totals[k] for k in ("completed", "gains", "losses", "net", "average", "worst", "rounds")]])
        for cell in cells[2:7]:
            cell.number_format = '#,##0.00" €";[Red]-#,##0.00" €"'
        cells[2].font = Font(color="19703A")
        cells[3].font = Font(color="B3261E")
        cells[4].font = Font(bold=True, color="19703A" if (totals["net"] or 0) >= 0 else "B3261E")
    if configurations:
        chart = BarChart()
        chart.title = "Guadagni e perdite per laptop"
        chart.y_axis.title = "Euro"
        chart.add_data(Reference(sheet, min_col=3, max_col=4, min_row=5, max_row=5 + len(configurations)), titles_from_data=True)
        chart.set_categories(Reference(sheet, min_col=1, min_row=6, max_row=5 + len(configurations)))
        chart.series[0].graphicalProperties.solidFill = "19703A"
        chart.series[1].graphicalProperties.solidFill = "B3261E"
        sheet.add_chart(chart, f"A{9 + len(configurations)}")
    for col in range(1, 9):
        sheet.column_dimensions[get_column_letter(col)].width = 26 if col != 1 else 38
    sheet.freeze_panes = "C6"
    for cell in sheet[5]:
        cell.alignment = Alignment(wrap_text=True)
    sheet.row_dimensions[5].height = 32


def load_bulk_json(filepath):
    path = Path(filepath)
    batch = json.loads(path.read_text(encoding="utf-8"))
    if batch.get("schema_version") not in (1, 2, 3) or not isinstance(batch.get("configurations"), list):
        raise ValueError("Formato risultati non riconosciuto")
    # Read-only compatibility for archives created by the previous app version.
    # New reports are self-contained JSON; this path never creates a database.
    if batch.get("details_file"):
        import sqlite3
        from contextlib import closing
        name = batch["details_file"]
        if Path(name).name != name or not name.endswith(".sqlite"):
            raise ValueError("Riferimento ai vecchi dettagli non valido")
        database = path.parent / name
        if not database.is_file():
            raise ValueError("Questo vecchio report richiede il file dei dettagli originale accanto al JSON.")
        try:
            with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
                for config in batch["configurations"]:
                    count = config.pop("recorded_runs")
                    config["runs"] = [json.loads(row[0]) for row in connection.execute(
                        "SELECT data FROM runs WHERE config=? AND idx<=? ORDER BY idx", (config["id"], count))]
                    if len(config["runs"]) != count:
                        raise ValueError("Dettagli del vecchio report incompleti")
            batch.pop("details_file")
        except sqlite3.Error as error:
            raise ValueError(f"Impossibile leggere il vecchio report: {error}") from error
    return batch


def save_bulk_json(filepath, batch):
    """Replace a snapshot atomically, retaining the old file on write failure."""
    destination = Path(filepath)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=destination.parent,
            prefix=".bulk-", suffix=".json", delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(batch, handle, ensure_ascii=False, allow_nan=False, indent=2)
            handle.write("\n")
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return destination


def _append(sheet, values, header=False):
    cells = [Cell(sheet, value=value) for value in values]
    for cell in cells:
        # These reports contain data only; labels must never become formulas.
        if isinstance(cell.value, str):
            cell.data_type = "s"
        if header:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="245A81")
    sheet.append(cells)
    return cells


def _metric_format(key):
    if key in PERCENT_METRICS:
        return PERCENT_FORMAT
    return "0" if key.endswith("_runs") else "0.00"


def _write_grids(sheet, configurations):
    _append(sheet, ["Frequenza di raggiungimento del profitto entro il drawdown osservato (%)"])
    _append(sheet, ["Ogni sessione termina allo stop configurato: le righe non simulano stop loss alternativi."])
    _append(sheet, ["Drawdown = calo dal picco; conta il massimo osservato fino al primo raggiungimento del profitto. "
                    "Denominatore: sole sessioni completate; nessun dato = cella vuota."])
    for config in configurations:
        completed = config["summary"]["completed_runs"]
        _append(sheet, [f"#{config['id']} — {config['label']} | completate: {completed} | "
                        f"stop drawdown: {config['settings']['max_loss']}"])
        _append(sheet, ["Drawdown osservato / Profitto", *config["profit_thresholds"]], header=True)
        first_row = sheet.max_row + 1
        for loss, counts in zip(config["loss_thresholds"], config["success_counts"]):
            cells = _append(sheet, [loss, *[count / completed * 100 if completed else None for count in counts]])
            for cell in cells[1:]:
                cell.number_format = PERCENT_FORMAT
                cell.alignment = Alignment(horizontal="center")
        if config["loss_thresholds"] and config["profit_thresholds"]:
            last_column = get_column_letter(len(config["profit_thresholds"]) + 1)
            sheet.conditional_formatting.add(
                f"B{first_row}:{last_column}{sheet.max_row}",
                ColorScaleRule(
                    start_type="num", start_value=0, start_color="F8696B",
                    mid_type="num", mid_value=50, mid_color="FFEB84",
                    end_type="num", end_value=100, end_color="63BE7B",
                ),
            )
        _append(sheet, [])
    sheet.freeze_panes = "B6"
    sheet.column_dimensions["A"].width = 38
    for column in range(2, sheet.max_column + 1):
        sheet.column_dimensions[get_column_letter(column)].width = 14


def _write_settings(sheet, batch):
    _append(sheet, ["Test", "Valore"], header=True)
    metadata = [
        ("Data creazione UTC", batch["created_at"]),
        ("Versione schema risultati", batch["schema_version"]),
        ("Versione simulatore", batch.get("simulator_version", "Non registrata")),
        ("Stato", batch["status"]),
        ("Ripetizioni richieste per configurazione", batch["requested_runs"]),
        ("Configurazioni", len(batch["configurations"])),
        ("Tempo trascorso (secondi)", batch["elapsed_seconds"]),
    ]
    for item in metadata:
        _append(sheet, item)
    for config in batch["configurations"]:
        _append(sheet, [])
        _append(sheet, [f"Configurazione #{config['id']}", config["label"]], header=True)
        _append(sheet, ["Simulazioni registrate (incluse interrotte)", len(config["runs"])])
        _append(sheet, ["Simulazioni completate", config["summary"]["completed_runs"]])
        _append(sheet, ["Simulazioni interrotte", config["summary"]["interrupted_runs"]])
        for key, value in config["settings"].items():
            if isinstance(value, (dict, list, tuple)):
                value = json.dumps(value, ensure_ascii=False)
            _append(sheet, [SETTINGS_LABELS.get(key, key), value])
        _append(sheet, ["Soglie profitto", json.dumps(config["profit_thresholds"])])
        _append(sheet, ["Soglie drawdown", json.dumps(config["loss_thresholds"])])
    sheet.freeze_panes = "B2"
    sheet.column_dimensions["A"].width = 53
    sheet.column_dimensions["B"].width = 105
    for row in sheet.iter_rows(min_col=2, max_col=2):
        row[0].alignment = Alignment(wrap_text=True, vertical="top")


def _write_summary(sheet, configurations):
    _append(sheet, ["Statistiche sulle sole sessioni completate; le interruzioni sono conteggiate separatamente."])
    _append(sheet, ["Intervalli di confidenza al 95%: Wilson. Campione vuoto: valori lasciati vuoti."])
    _append(sheet, ["Il drawdown massimo e il profitto peggiore descrivono il campione osservato."])
    for config in configurations:
        _append(sheet, [f"#{config['id']} — {config['label']}", "Valore"], header=True)
        for key, label in METRICS:
            cells = _append(sheet, [label, config["summary"].get(key)])
            cells[1].number_format = _metric_format(key)
        _append(sheet, ["Motivo di arresto", "Numero di sessioni"], header=True)
        for status, label in STOP_LABELS.items():
            _append(sheet, [label, config["summary"]["stop_counts"].get(status, 0)])
        _append(sheet, [])
    sheet.freeze_panes = "B5"
    sheet.column_dimensions["A"].width = 58
    sheet.column_dimensions["B"].width = 24


def _write_comparison(sheet, configurations):
    setting_columns = ["mode", "max_picks", "difficulty", "grinding_enabled"]
    _append(sheet, ["ID", "Configurazione", *[SETTINGS_LABELS[key] for key in setting_columns],
                    *[label for _, label in METRICS], *STOP_LABELS.values()], header=True)
    for config in configurations:
        summary = config["summary"]
        cells = _append(sheet, [config["id"], config["label"],
                        *[config["settings"].get(key) for key in setting_columns],
                        *[summary.get(key) for key, _ in METRICS],
                        *[summary["stop_counts"].get(status, 0) for status in STOP_LABELS]])
        for column, (key, _) in enumerate(METRICS, start=6):
            cells[column].number_format = _metric_format(key)
    if configurations:
        table = Table(displayName="ConfrontoConfigurazioni", ref=sheet.dimensions)
        table.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
        sheet.add_table(table)
    sheet.freeze_panes = "C2"
    for column in range(1, sheet.max_column + 1):
        sheet.column_dimensions[get_column_letter(column)].width = 24
    sheet.column_dimensions["B"].width = 48


def _write_runs(sheet, configurations):
    _append(sheet, ["ID configurazione", "Configurazione", "Simulazione", "Esito",
                    "Round", "Saldo finale", "Profitto finale", "Picco saldo", "Massimo drawdown"], header=True)
    for config in configurations:
        for run in config["runs"]:
            cells = _append(sheet, [config["id"], config["label"], run["index"],
                            STOP_LABELS[run["status"]], run["rounds"], run["final_cash"],
                            run["profit"], run["peak_cash"], run["max_drawdown"]])
            for cell in cells[5:]:
                cell.number_format = "0.00"
    sheet.auto_filter.ref = sheet.dimensions
    sheet.freeze_panes = "C2"
    for column in range(1, 10):
        sheet.column_dimensions[get_column_letter(column)].width = 23
    sheet.column_dimensions["B"].width = 48
    sheet.column_dimensions["D"].width = 32


def _write_histograms(sheet, configurations):
    _append(sheet, ["Distribuzione dei profitti finali: sole sessioni completate; intervalli comuni a tutte le configurazioni."])
    profits = [run["profit"] for config in configurations for run in config["runs"] if run["status"] != "interrupted"]
    if not profits:
        _append(sheet, ["Nessuna sessione completata: nessun istogramma disponibile."])
        return
    low, high = min(profits), max(profits)
    bins = min(20, max(1, math.ceil(math.sqrt(len(profits))))) if low != high else 1
    width = (high - low) / bins if low != high else 0
    edges = [low + width * index for index in range(bins)] + [high]
    for config in configurations:
        values = [run["profit"] for run in config["runs"] if run["status"] != "interrupted"]
        start_row = sheet.max_row + 2
        sheet.cell(start_row, 1, f"#{config['id']} — {config['label']}").data_type = "s"
        if not values:
            _append(sheet, ["Nessuna sessione completata."])
            continue
        frequencies = [0] * bins
        for value in values:
            index = min(bins - 1, max(0, int((value - low) / width))) if width else 0
            frequencies[index] += 1
        _append(sheet, ["Intervallo profitto", "Da (incluso)", "A (ultima classe inclusa)", "Sessioni"], header=True)
        header_row = sheet.max_row
        for index, count in enumerate(frequencies):
            end = "]" if index == bins - 1 else ")"
            _append(sheet, [f"[{edges[index]:.6g}, {edges[index + 1]:.6g}{end}", edges[index], edges[index + 1], count])
        chart = BarChart()
        chart.title = f"#{config['id']} — {config['label']}"
        chart.y_axis.title = "Sessioni"
        chart.x_axis.title = "Profitto finale"
        chart.legend = None
        chart.add_data(Reference(sheet, min_col=4, min_row=header_row, max_row=header_row + bins), titles_from_data=True)
        chart.set_categories(Reference(sheet, min_col=1, min_row=header_row + 1, max_row=header_row + bins))
        sheet.add_chart(chart, f"F{start_row}")
        # Leave room for the chart before the next configuration's block.
        sheet.cell(max(start_row + 16, sheet.max_row + 1), 1, " ")
    sheet.freeze_panes = "B4"
    for column in ("A", "B", "C", "D"):
        sheet.column_dimensions[column].width = 28


def write_bulk_excel(filepath, batch, include_details=None):
    """Write the complete batch, including partial runs and comparison data."""
    workbook = Workbook()
    first = workbook.active
    first.title = "Confronto laptop"
    configurations = [enriched_config(c) for c in batch["configurations"]]
    _write_laptops(first, batch, configurations)
    grid = workbook.create_sheet("Griglia Win Rate")
    _write_grids(grid, configurations)
    _write_settings(workbook.create_sheet("Impostazioni"), batch)
    _write_summary(workbook.create_sheet("Sommario"), configurations)
    _write_comparison(workbook.create_sheet("Confronto"), configurations)
    details = workbook.create_sheet("Dettaglio simulazioni")
    count = sum(len(c["runs"]) for c in configurations)
    if include_details is None:
        include_details = count <= 10000
    if include_details and count < 1048576:
        _write_runs(details, configurations)
    else:
        _append(details, [f"{count} simulazioni: dettaglio completo nell'file JSON. Usa ESPORTA DETTAGLI CSV nell'app."])
    _write_histograms(workbook.create_sheet("Distribuzione profitti"), configurations)
    destination = Path(filepath)
    destination.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(destination)
    workbook.close()
    return destination


def write_bulk_csv(filepath, batch):
    """Stream full details; no spreadsheet row limit or formula interpretation."""
    keys = ("index", "status", "rounds", "final_cash", "profit", "max_drawdown",
            "wagered", "costs", "topups", "funds_stops", "simulated_seconds")
    with open(filepath, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(["Configurazione ID", *keys, "Dettagli PC (JSON)"])
        for config in batch["configurations"]:
            for run in config["runs"]:
                writer.writerow([config["id"], *[run.get(key, "") for key in keys], json.dumps(run.get("per_pc", []))])
    return Path(filepath)
