# -*- coding: utf-8 -*-
"""
Assemblage du graphe LangGraph : les DEUX boucles.

    START → recon → planner → attacker → target → judge → [aiguillage]
                                  ▲                            │
                                  └──── (échec, retente) ◄──────┤   boucle INTERNE
                                  ▲                            │
                               next_goal ◄── (objectif suivant)┤   boucle EXTERNE
                                                               │
                                        report ◄── (campagne finie)
"""
from langgraph.graph import StateGraph, START, END

from .state import State
from .nodes.recon import make_recon
from .nodes.planner import planner
from .nodes.attacker import attacker
from .nodes.target_node import make_send_to_target
from .nodes.judge import judge
from .nodes.reporter import reporter
from ..targets.base import Target


def _route_after_judge(state: State) -> str:
    """Aiguillage après le juge : décide de la suite (gère les 2 boucles).

    - objectif atteint OU plafond de tentatives -> on CLÔT cet objectif
         -> reste-t-il des objectifs ? oui: next_goal / non: report
    - sinon -> on RETENTE (boucle interne) : retour à attacker
    """
    objectif_clos = state["current_success"] or state["attempt"] >= state["max_attempts"]

    if not objectif_clos:
        return "attacker"                               # boucle interne

    if state["goal_idx"] + 1 < len(state["goals"]):
        return "next_goal"                              # boucle externe
    return "report"                                     # fin de campagne


def next_goal(state: State) -> dict:
    """Passe à l'objectif suivant et réinitialise la boucle interne."""
    nouveau_idx = state["goal_idx"] + 1                 # ← ICI on fait avancer
    print(f"\n{'-'*60}\n[campagne] objectif suivant "
          f"({nouveau_idx + 1}/{len(state['goals'])})\n{'-'*60}")
    return {
        "goal_idx": nouveau_idx,
        "attempt": 0,            # on remet le compteur de tentatives à zéro
        "conversation": [],      # nouveau dialogue pour le nouvel objectif
        "current_success": False
    }


def build_graph(target: Target):
    """Construit et compile le graphe pour une cible donnée."""
    g = StateGraph(State)

    # 1. On déclare les nœuds
    g.add_node("recon", make_recon(target))
    g.add_node("planner", planner)
    g.add_node("attacker", attacker)
    g.add_node("target", make_send_to_target(target))
    g.add_node("judge", judge)
    g.add_node("next_goal", next_goal)
    g.add_node("report", reporter)

    # 2. Les transitions fixes (toujours A -> B)
    g.add_edge(START, "recon")
    g.add_edge("recon", "planner")
    g.add_edge("planner", "attacker")
    g.add_edge("attacker", "target")
    g.add_edge("target", "judge")

    # 3. LE CŒUR : l'aiguillage conditionnel après le juge
    g.add_conditional_edges("judge", _route_after_judge, {
        "attacker": "attacker",     # retenter (boucle interne)
        "next_goal": "next_goal",   # objectif suivant (boucle externe)
        "report": "report",         # fin
    })

    # 4. Après next_goal, on relance l'attaque sur le nouvel objectif
    g.add_edge("next_goal", "attacker")
    g.add_edge("report", END)

    return g.compile()