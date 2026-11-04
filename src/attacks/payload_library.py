# -*- coding: utf-8 -*-
import json
import re
from pathlib import Path

_PATH = Path(__file__).resolve().parent / "payloads.json"

try:
    _RAW = json.loads(_PATH.read_text(encoding="utf-8"))
except Exception as e:
    print(f"[payload_library] payloads.json introuvable/illu ({e}) -> banque vide")
    _RAW = []

# Catégories dont l'exploit EST la structure -> VERBATIM obligatoire (le LLM les casserait)
_STRUCTURAL_CATS = {
    "fake-tool", "mcp-exploitation", "tool-shadow", "supply-chain",
    "persistent-agent", "parser-differential",
}

# Surface requise par catégorie structurelle (mot-clé cherché dans le profil recon)
_SURFACE_NEED = {
    "mcp-exploitation":    ("mcp", "tool", "function", "outil"),
    "fake-tool":           ("tool", "function", "execut", "outil", "command", "commande"),
    "tool-shadow":         ("tool", "function", "execut", "outil", "command", "commande"),
    "supply-chain":        ("package", "plugin", "skill", "install", "depend", "librair"),
    "persistent-agent":    ("memor", "persist", "session", "state", "mémoire"),
    "parser-differential": ("json", "parse", "structur", "api", "yaml"),
}

# Mots-clés d'un objectif -> catégories pertinentes (score de thème)
_THEME = {
    "data-exfiltration": ("secret", "clé", "cle", "key", "token", "password", "mot de passe",
                          "identifiant", "credential", "exfil", "donnée", "data", "config",
                          "pii", "personnel", "database", "base de données", "fuite"),
    "prompt-injection":  ("injection", "prompt", "instruction", "système", "system", "détourn",
                          "ignore", "override", "consigne"),
    "capability-abuse":  ("commande", "command", "exécut", "execut", "privil", "shell", "admin",
                          "outil", "tool", "action", "sudo"),
    "jailbreak":         ("jailbreak", "contourn", "bypass", "restriction", "filtre", "safety"),
    "context-manipulation": ("contexte", "context", "mémoire", "memory", "historique", "rag",
                             "poison", "manipul"),
}

_SEV_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def _is_structural(p: dict) -> bool:
    if p.get("category") in _STRUCTURAL_CATS:
        return True
    t = (p.get("payload") or "")
    ts = t.strip()
    if ts.startswith("{") or ts.startswith("anchor") or "_mcpTool" in t:
        return True
    if re.search(r"[​‌‍﻿]", t):   # caractères zéro-largeur
        return True
    return False


def _annotate(p: dict) -> dict:
    p = dict(p)
    p["mode"] = "verbatim" if _is_structural(p) else "adaptable"
    return p


_PAYLOADS = [_annotate(p) for p in _RAW]


def _surface_ok(p: dict, caps_text: str) -> bool:
    """Un payload structurel n'est pertinent que si la cible a la surface voulue."""
    if p["mode"] != "verbatim":
        return True                       # conversationnel : toujours applicable
    needs = _SURFACE_NEED.get(p.get("category"))
    if not needs:
        return True
    return any(k in caps_text for k in needs)


def _theme_score(p: dict, goal_text: str) -> int:
    kws = _THEME.get(p.get("category", ""), ())
    s = sum(1 for k in kws if k in goal_text)
    name = (p.get("name") or "").lower()
    s += sum(1 for w in name.split() if len(w) > 4 and w in goal_text)
    return s


def candidates(goal: dict, caps_text: str,
               intensities=("active", "aggressive")) -> list[dict]:
    """
    Payloads pertinents pour cet objectif + cette cible, du meilleur au moins bon.
    On ÉCARTE les passifs (trop triviaux pour la phase d'attaque) et les structurels
    sans surface correspondante.
    """
    goal_text = " ".join(str(goal.get(k, "")) for k in ("titre", "description", "owasp")).lower()
    caps_text = (caps_text or "").lower()
    pool = [p for p in _PAYLOADS
            if p.get("intensity") in intensities and _surface_ok(p, caps_text)]
    pool.sort(key=lambda p: (
        -_theme_score(p, goal_text),                       # plus proche du thème d'abord
        0 if p.get("intensity") == "active" else 1,        # active avant aggressive
        _SEV_RANK.get(p.get("severity"), 5),               # plus grave d'abord
    ))
    return pool


def pick(goal: dict, caps_text: str, attempt_no: int) -> dict | None:
    """Choisit le payload de cette tentative (rotation sur les plus pertinents),
    ou None si la banque est vide -> l'attaquant génère lui-même (comportement d'origine)."""
    pool = candidates(goal, caps_text)
    if not pool:
        return None
    return pool[(attempt_no - 1) % len(pool)]