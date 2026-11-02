# -*- coding: utf-8 -*-
"""API : lancer des scans (par registre OU par URL) et récupérer les rapports."""
from uuid import uuid4
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from src.service import run_scan
from src.targets.registry import list_targets, target_exists
import json
from pathlib import Path

REPORTS_DIR = Path(__file__).resolve().parent / "reports"

app = FastAPI(title="Mon API", version="0.1.0")

SCANS: dict[str, dict] = {}


# --- Formes de requête ---
class RegistryScan(BaseModel):
    target: str = "helpbot"
    max_attempts: int = 4


class FlatURLScan(BaseModel):
    url: str
    name: str = "agent-externe"
    request_field: str = "message"
    reply_field: str = "reply"
    max_attempts: int = 4


class OpenAIURLScan(BaseModel):
    url: str
    name: str = "agent-externe"
    model: str = "gpt-4o"
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
        print(f"[ERREUR scan {scan_id}] {e}")   # visible dans le terminal


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


@app.post("/scan/url/flat")
def scan_url_flat(req: FlatURLScan, background_tasks: BackgroundTasks):
    """Scanne un agent à format PLAT ({champ} -> {champ})."""
    scan_id = _new_scan()
    background_tasks.add_task(
        _execute, scan_id,
        target_url=req.url, target_format="flat", name=req.name,
        request_field=req.request_field, reply_field=req.reply_field,
        max_attempts=req.max_attempts,
    )
    return {"scan_id": scan_id, "status": "pending", "url": req.url}


@app.post("/scan/url/openai")
def scan_url_openai(req: OpenAIURLScan, background_tasks: BackgroundTasks):
    """Scanne un agent compatible OpenAI (/v1/chat/completions)."""
    scan_id = _new_scan()
    background_tasks.add_task(
        _execute, scan_id,
        target_url=req.url, target_format="openai", name=req.name,
        model=req.model, max_attempts=req.max_attempts,
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


# ─── Dashboard web (doit venir APRÈS tous les endpoints) ───
app.mount("/static", StaticFiles(directory="web"), name="static")

@app.post("/scan/{scan_id}/cancel")
def cancel_scan(scan_id: str):
    if scan_id not in SCANS:
        raise HTTPException(status_code=404, detail="scan introuvable")
    SCANS[scan_id]["cancel"] = True
    if SCANS[scan_id]["status"] in ("pending", "running"):
        SCANS[scan_id]["status"] = "cancelled"
    return {"scan_id": scan_id, "status": SCANS[scan_id]["status"]}

class AutoURLScan(BaseModel):
    url: str
    name: str = "agent-externe"
    model: str = "gpt-4o"          # utilisé seulement si le format détecté est OpenAI
    max_attempts: int = 4


@app.post("/scan/url/auto")
def scan_url_auto(req: AutoURLScan, background_tasks: BackgroundTasks):
    """Scanne un agent dont le format est AUTO-DÉTECTÉ (aucun champ à préciser)."""
    scan_id = _new_scan()
    background_tasks.add_task(
        _execute, scan_id,
        target_url=req.url, target_format="auto", name=req.name,
        model=req.model, max_attempts=req.max_attempts,
    )
    return {"scan_id": scan_id, "status": "pending", "url": req.url}
@app.get("/history")
def history():
    """Liste les scans passés (lus depuis le dossier reports/)."""
    items = []
    if REPORTS_DIR.exists():
        for p in sorted(REPORTS_DIR.glob("scan_*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            items.append({
                "file": p.name,
                "nom": (data.get("cible") or {}).get("nom"),
                "role": (data.get("cible") or {}).get("role"),
                "date": data.get("date"),
                "synthese": data.get("synthese"),
                "nb_vulnerabilites": data.get("nb_vulnerabilites", 0),
                "objectifs_testes": data.get("objectifs_testes", []),
            })
    return {"scans": items}


@app.get("/history/{file}")
def history_report(file: str):
    """Renvoie le contenu d'un rapport archivé."""
    safe = Path(file).name          # empêche la traversée de dossier
    p = REPORTS_DIR / safe
    if p.suffix != ".json" or not p.exists():
        raise HTTPException(status_code=404, detail="rapport introuvable")
    return json.loads(p.read_text(encoding="utf-8"))
@app.get("/")
def dashboard():
    return FileResponse("web/index.html")