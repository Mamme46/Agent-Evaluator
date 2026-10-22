# -*- coding: utf-8 -*-
"""
Nœud PLANNER : choisit les objectifs d'attaque adaptés au profil de la cible,
et initialise la campagne (liste d'objectifs + marque-page à 0).

Il NE fait PAS avancer goal_idx ensuite : il pose juste le point de départ.
L'avancement est géré par l'aiguillage du graphe.
"""
from ...attacks.catalog import goals_for_caps


def planner(state) -> dict:
    caps = state.get("target_caps", [])
    goals = goals_for_caps(caps)   # <-- lit le CATALOGUE

    # On transforme les objectifs en dict pour qu'ils vivent dans l'état.
    goals_data = [
        {"id": g.id, "titre": g.titre, "owasp": g.owasp, "description": g.description}
        for g in goals
    ]

    print(f"[planner] {len(goals_data)} objectif(s) retenu(s) :")
    for g in goals_data:
        print(f"          - {g['id']} ({g['owasp']})")

    return {
        "goals": goals_data,     # la LISTE (le rail)
        "goal_idx": 0,           # le MARQUE-PAGE au départ (station 0)
        # On initialise aussi la première boucle interne :
        "attempt": 0,            # aucune tentative encore
        "conversation": [],      # dialogue vide
        "current_success": False # objectif pas encore atteint
    }