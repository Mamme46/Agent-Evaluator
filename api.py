# -*- coding: utf-8 -*-
"""API : lancer des scans (par registre OU par URL) et récupérer les rapports."""
from uuid import uuid4
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from src.service import run_scan, run_hosted_scan
from src.targets.registry import list_targets, target_exists
from src.cancel import request_cancel, clear, ScanCancelled
import json
from pathlib import Path

REPORTS_DIR = Path(__file__).resolve().parent / "reports"

app = FastAPI(title="Mon API", version="0.1.0")

SCANS: dict[str, dict] = {}


class RegistryScan(BaseModel):
    target: str = "helpbot"
    max_attempts: int = 4


class FlatURLScan(BaseModel):
    url: str
    name: str = "agent-externe"
    request_field: str = "message"
    reply_field: str = "reply"
    max_attempts: int = 4
    auth_header: str | None = None
    auth_value: str | None = None


class OpenAIURLScan(BaseModel):
    url: str
    name: str = "agent-externe"
    model: str = "gpt-4o"
    max_attempts: int = 4
    auth_header: str | None = None
    auth_value: str | None = None


class AutoURLScan(BaseModel):
    url: str
    name: str = "agent-externe"
    model: str = "gpt-4o"
    max_attempts: int = 4
    auth_header: str | None = None
    auth_value: str | None = None


class HostedScan(BaseModel):
    image: str
    container_port: int
    env: dict = {}
    data_host_dir: str | None = None
    data_mount_path: str = "/data"
    ready_path: str | None = None
    api_path: str | None = None
    target_format: str = "auto"
    name: str = "agent-hébergé"
    model: str = "gpt-4o"
    max_attempts: int = 4
    auth_header: str | None = None
    auth_value: str | None = None


LAUNCHES: dict[str, dict] = {}


class HostedLaunch(BaseModel):
    image: str
    container_port: int
    env: dict = {}
    data_host_dir: str | None = None
    data_mount_path: str = "/data"
    ready_path: str | None = None


class HostedScanStep(BaseModel):
    launch_id: str | None = None
    url: str | None = None
    container_id: str | None = None
    api_path: str | None = None
    target_format: str = "auto"
    name: str = "agent-hébergé"
    model: str = "gpt-4o"
    max_attempts: int = 4
    auth_header: str | None = None
    auth_value: str | None = None
    keep_alive: bool = False


def _new_scan() -> str:
    scan_id = str(uuid4())
    SCANS[scan_id] = {"status": "pending", "report": None, "error": None}
    return scan_id


def _execute(scan_id: str, _runner=run_scan, **kwargs) -> None:
    SCANS[scan_id]["status"] = "running"
    try:
        SCANS[scan_id]["report"] = _runner(scan_id=scan_id, **kwargs)
        SCANS[scan_id]["status"] = "done"
    except ScanCancelled:
        SCANS[scan_id]["status"] = "cancelled"
        print(f"[scan {scan_id}] annulé")
    except Exception as e:
        SCANS[scan_id]["status"] = "error"
        SCANS[scan_id]["error"] = str(e)
        print(f"[ERREUR scan {scan_id}] {e}")
    finally:
        clear(scan_id)


def _do_launch(launch_id: str, req: HostedLaunch) -> None:
    from src.hosted.launcher import HostedSpec, launch
    LAUNCHES[launch_id]["status"] = "launching"
    try:
        spec = HostedSpec(
            image=req.image, container_port=req.container_port, env=req.env,
            data_host_dir=req.data_host_dir, data_mount_path=req.data_mount_path,
            ready_path=req.ready_path,
        )
        info = launch(spec)
        LAUNCHES[launch_id].update(status="ready", url=info["url"],
                                   port=info["port"], container_id=info["container_id"])
    except Exception as e:
        LAUNCHES[launch_id].update(status="error", detail=str(e))
        print(f"[ERREUR launch {launch_id}] {e}")


def _run_hosted_scan_step(scan_id: str, container_id: str, keep_alive: bool,
                          scan_kwargs: dict) -> None:
    from src.hosted.launcher import stop
    SCANS[scan_id]["status"] = "running"
    try:
        SCANS[scan_id]["report"] = run_scan(scan_id=scan_id, **scan_kwargs)
        SCANS[scan_id]["status"] = "done"
    except ScanCancelled:
        SCANS[scan_id]["status"] = "cancelled"
        print(f"[scan {scan_id}] annulé")
    except Exception as e:
        SCANS[scan_id]["status"] = "error"
        SCANS[scan_id]["error"] = str(e)
        print(f"[ERREUR scan {scan_id}] {e}")
    finally:
        clear(scan_id)
        if not keep_alive and container_id:
            stop(container_id)


@app.get("/targets")
def get_targets():
    return {"targets": list_targets()}


@app.post("/scan/registry")
def scan_registry(req: RegistryScan, background_tasks: BackgroundTasks):
    if not target_exists(req.target):
        raise HTTPException(status_code=404, detail=f"cible inconnue : {req.target}")
    scan_id = _new_scan()
    background_tasks.add_task(_execute, scan_id, target_name=req.target, max_attempts=req.max_attempts)
    return {"scan_id": scan_id, "status": "pending", "target": req.target}


@app.post("/scan/url/flat")
def scan_url_flat(req: FlatURLScan, background_tasks: BackgroundTasks):
    scan_id = _new_scan()
    background_tasks.add_task(
        _execute, scan_id,
        target_url=req.url, target_format="flat", name=req.name,
        request_field=req.request_field, reply_field=req.reply_field,
        max_attempts=req.max_attempts,
        auth_header=req.auth_header, auth_value=req.auth_value,
    )
    return {"scan_id": scan_id, "status": "pending", "url": req.url}


@app.post("/scan/url/openai")
def scan_url_openai(req: OpenAIURLScan, background_tasks: BackgroundTasks):
    scan_id = _new_scan()
    background_tasks.add_task(
        _execute, scan_id,
        target_url=req.url, target_format="openai", name=req.name,
        model=req.model, max_attempts=req.max_attempts,
        auth_header=req.auth_header, auth_value=req.auth_value,
    )
    return {"scan_id": scan_id, "status": "pending", "url": req.url}


@app.post("/scan/url/auto")
def scan_url_auto(req: AutoURLScan, background_tasks: BackgroundTasks):
    scan_id = _new_scan()
    background_tasks.add_task(
        _execute, scan_id,
        target_url=req.url, target_format="auto", name=req.name,
        model=req.model, max_attempts=req.max_attempts,
        auth_header=req.auth_header, auth_value=req.auth_value,
    )
    return {"scan_id": scan_id, "status": "pending", "url": req.url}


@app.post("/scan/hosted")
def scan_hosted(req: HostedScan, background_tasks: BackgroundTasks):
    scan_id = _new_scan()
    background_tasks.add_task(
        _execute, scan_id, _runner=run_hosted_scan,
        image=req.image, container_port=req.container_port, env=req.env,
        data_host_dir=req.data_host_dir, data_mount_path=req.data_mount_path,
        ready_path=req.ready_path, api_path=req.api_path, target_format=req.target_format,
        name=req.name, model=req.model, max_attempts=req.max_attempts,
        auth_header=req.auth_header, auth_value=req.auth_value,
    )
    return {"scan_id": scan_id, "status": "pending", "image": req.image}


@app.post("/hosted/launch")
def hosted_launch(req: HostedLaunch, background_tasks: BackgroundTasks):
    launch_id = str(uuid4())
    LAUNCHES[launch_id] = {"status": "pending", "url": None, "port": None,
                           "container_id": None, "detail": None}
    background_tasks.add_task(_do_launch, launch_id, req)
    return {"launch_id": launch_id, "status": "pending"}


@app.get("/hosted/launch/{launch_id}")
def hosted_launch_status(launch_id: str):
    if launch_id not in LAUNCHES:
        raise HTTPException(status_code=404, detail="lancement introuvable")
    return {"launch_id": launch_id, **LAUNCHES[launch_id]}


@app.post("/hosted/launch/{launch_id}/stop")
def hosted_launch_stop(launch_id: str):
    from src.hosted.launcher import stop
    lan = LAUNCHES.get(launch_id)
    if not lan:
        raise HTTPException(status_code=404, detail="lancement introuvable")
    if lan.get("container_id"):
        stop(lan["container_id"])
    lan["status"] = "stopped"
    return {"launch_id": launch_id, "status": "stopped"}


@app.post("/hosted/scan")
def hosted_scan_step(req: HostedScanStep, background_tasks: BackgroundTasks):
    lan = LAUNCHES.get(req.launch_id) if req.launch_id else None
    if lan and lan.get("status") == "ready":
        base, container_id = lan["url"], lan["container_id"]
    elif req.url:
        base, container_id = req.url, req.container_id
    else:
        raise HTTPException(status_code=409, detail="cible non prête (lance-la d'abord)")
    scan_url = (base.rstrip("/") + "/" + req.api_path.lstrip("/")) if req.api_path else base
    scan_id = _new_scan()
    scan_kwargs = dict(
        target_url=scan_url, target_format=req.target_format, name=req.name,
        model=req.model, max_attempts=req.max_attempts,
        auth_header=req.auth_header, auth_value=req.auth_value,
    )
    background_tasks.add_task(_run_hosted_scan_step, scan_id, container_id,
                             req.keep_alive, scan_kwargs)
    return {"scan_id": scan_id, "status": "pending"}


@app.post("/scan/{scan_id}/cancel")
def cancel_scan(scan_id: str):
    if scan_id not in SCANS:
        raise HTTPException(status_code=404, detail="scan introuvable")
    request_cancel(scan_id)
    SCANS[scan_id]["cancel"] = True
    if SCANS[scan_id]["status"] in ("pending", "running"):
        SCANS[scan_id]["status"] = "cancelled"
    return {"scan_id": scan_id, "status": SCANS[scan_id]["status"]}


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


@app.get("/history")
def history():
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
    safe = Path(file).name
    p = REPORTS_DIR / safe
    if p.suffix != ".json" or not p.exists():
        raise HTTPException(status_code=404, detail="rapport introuvable")
    return json.loads(p.read_text(encoding="utf-8"))


app.mount("/static", StaticFiles(directory="web"), name="static")


@app.get("/")
def dashboard():
    return FileResponse("web/index.html")