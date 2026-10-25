# -*- coding: utf-8 -*-
"""API : lancer des scans (par registre OU par URL) et récupérer les rapports."""
from uuid import uuid4
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from src.service import run_scan
from src.targets.registry import list_targets, target_exists

app = FastAPI(title="Mon API", version="0.1.0")

SCANS: dict[str, dict] = {}


# --- Deux formes de requête distinctes ---
class RegistryScan(BaseModel):
    target: str = "helpbot"
    max_attempts: int = 4


class URLScan(BaseModel):
    url: str
    name: str = "agent-externe"
    request_field: str = "message"
    reply_field: str = "reply"
    max_attempts: int = 4


def _new_scan() -> str:
    scan_id = str(uuid4())
    SCANS[scan_id] = {"status": "pending", "report": None, "error": None}
    return scan_id


def _execute(scan_id: str, **kwargs) -> None:
    SCANS[scan_id]["status"] = "running"
    try:
        SCANS[scan_id]["report"] = run_scan(**kwargs)
        SCANS[scan_id]["status"] = "done"
    except Exception as e:
        SCANS[scan_id]["status"] = "error"
        SCANS[scan_id]["error"] = str(e)


@app.get("/targets")
def get_targets():
    """Liste les cibles du catalogue (registre)."""
    return {"targets": list_targets()}


@app.post("/scan/registry")
def scan_registry(req: RegistryScan, background_tasks: BackgroundTasks):
    """Scanne une cible du catalogue, par son nom."""
    if not target_exists(req.target):
        raise HTTPException(status_code=404, detail=f"cible inconnue : {req.target}")
    scan_id = _new_scan()
    background_tasks.add_task(_execute, scan_id, target_name=req.target, max_attempts=req.max_attempts)
    return {"scan_id": scan_id, "status": "pending", "target": req.target}


@app.post("/scan/url")
def scan_url(req: URLScan, background_tasks: BackgroundTasks):
    """Scanne un agent arbitraire, par son endpoint HTTP."""
    scan_id = _new_scan()
    background_tasks.add_task(
        _execute, scan_id,
        target_url=req.url, name=req.name,
        request_field=req.request_field, reply_field=req.reply_field,
        max_attempts=req.max_attempts,
    )
    return {"scan_id": scan_id, "status": "pending", "url": req.url}


@app.get("/scan/{scan_id}")
def scan_status(scan_id: str):
    if scan_id not in SCANS:
        raise HTTPException(status_code=404, detail="scan introuvable")
    return {"scan_id": scan_id, "status": SCANS[scan_id]["status"]}


@app.get("/report/{scan_id}")
def get_report(scan_id: str):
    if scan_id not in SCANS:
        raise HTTPException(status_code=404, detail="scan introuvable")
    s = SCANS[scan_id]
    if s["status"] == "error":
        raise HTTPException(status_code=500, detail=f"scan en erreur : {s['error']}")
    if s["status"] != "done":
        raise HTTPException(status_code=409, detail=f"scan pas encore terminé (statut : {s['status']})")
    return s["report"]