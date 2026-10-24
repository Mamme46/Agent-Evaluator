# -*- coding: utf-8 -*-
"""API FastAPI pour lancer des scans et récupérer les rapports (asynchrone)."""
from uuid import uuid4
from fastapi import FastAPI, BackgroundTasks, HTTPException
from src.service import run_scan

app = FastAPI(title="Agent-Evaluator API", version="0.1.0")

# Stockage en mémoire des scans : scan_id -> {status, report, error}
# (simple pour l'instant ; une vraie base viendra plus tard)
SCANS: dict[str, dict] = {}


def _execute(scan_id: str, max_attempts: int) -> None:
    """Exécuté en arrière-plan : lance le scan et range le résultat."""
    SCANS[scan_id]["status"] = "running"
    try:
        report = run_scan(max_attempts=max_attempts)
        SCANS[scan_id]["report"] = report
        SCANS[scan_id]["status"] = "done"
    except Exception as e:
        SCANS[scan_id]["status"] = "error"
        SCANS[scan_id]["error"] = str(e)


@app.post("/scan")
def start_scan(background_tasks: BackgroundTasks, max_attempts: int = 4):
    """Lance un scan en arrière-plan et renvoie immédiatement un scan_id."""
    scan_id = str(uuid4())
    SCANS[scan_id] = {"status": "pending", "report": None, "error": None}
    background_tasks.add_task(_execute, scan_id, max_attempts)
    return {"scan_id": scan_id, "status": "pending"}


@app.get("/scan/{scan_id}")
def scan_status(scan_id: str):
    """Renvoie le statut d'un scan."""
    if scan_id not in SCANS:
        raise HTTPException(status_code=404, detail="scan introuvable")
    return {"scan_id": scan_id, "status": SCANS[scan_id]["status"]}


@app.get("/report/{scan_id}")
def get_report(scan_id: str):
    """Renvoie le rapport une fois le scan terminé."""
    if scan_id not in SCANS:
        raise HTTPException(status_code=404, detail="scan introuvable")
    s = SCANS[scan_id]
    if s["status"] == "error":
        raise HTTPException(status_code=500, detail=f"scan en erreur : {s['error']}")
    if s["status"] != "done":
        raise HTTPException(status_code=409, detail=f"scan pas encore terminé (statut : {s['status']})")
    return s["report"]