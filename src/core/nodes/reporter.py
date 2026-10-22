# -*- coding: utf-8 -*-
"""
Nœud REPORTER : agrège tous les findings de la campagne en un rapport.
Écrit un JSON horodaté dans reports/ et affiche un résumé lisible.
"""
import json
from datetime import datetime
from pathlib import Path
from ..state import State


# reports/ est à la racine du projet : on remonte depuis ce fichier.
# Ce fichier = src/core/nodes/reporter.py -> parents : [nodes, core, src, RACINE]
REPORTS_DIR = Path(__file__).resolve().parents[3] / "reports"


def reporter(state: State) -> dict:
    findings = state.get("findings", [])
    goals = state.get("goals", [])

    rapport = {
        "date": datetime.now().isoformat(timespec="seconds"),
        "cible": {
            "nom": state.get("target_name"),
            "role": state.get("target_role"),
            "capacites": state.get("target_caps", []),
        },
        "objectifs_testes": [g["id"] for g in goals],
        "nb_vulnerabilites": len(findings),
        "findings": findings,
        "verdict_global": (
            "Aucune vulnérabilité détectée sur les axes testés."
            if not findings else
            f"{len(findings)} vulnérabilité(s) sur {len(goals)} axe(s) testé(s)."
        ),
    }

    # Écriture du fichier JSON
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    nom = f"scan_{state.get('target_name', 'cible')}_{datetime.now():%Y%m%d_%H%M%S}.json"
    chemin = REPORTS_DIR / nom
    chemin.write_text(json.dumps(rapport, ensure_ascii=False, indent=2), encoding="utf-8")

    # Affichage console
    print("\n" + "=" * 60)
    print("RAPPORT DE SÉCURITÉ")
    print("=" * 60)
    print(f"Cible   : {rapport['cible']['nom']} ({rapport['cible']['role']})")
    print(f"Verdict : {rapport['verdict_global']}")
    if findings:
        print("\nVulnérabilités trouvées :")
        for f in findings:
            print(f"  • [{f['owasp']}] {f['titre']} "
                  f"(gravité {f['gravite']}, en {f['tentatives']} tentative(s))")
            print(f"      → {f['raison']}")
    print(f"\nRapport écrit : {chemin}")
    print("=" * 60)

    return {}