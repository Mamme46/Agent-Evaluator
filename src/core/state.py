# -*- coding: utf-8 -*-
"""
État partagé du graphe LangGraph. Porte les DEUX boucles :
- boucle externe (campagne) : on parcourt `goals`, index `goal_idx`
- boucle interne (attaque)   : tentatives sur le goal courant, compteur `attempt`

Les résultats finaux s'accumulent dans `findings`.
"""
from typing import TypedDict, Annotated
import operator


class State(TypedDict, total=False):
    # --- Cible (rempli par recon) ---
    target_name: str
    target_role: str
    target_caps: list[str]

    # --- Plan de campagne (boucle externe) ---
    goals: list[dict]          # objectifs choisis par le planner
    goal_idx: int              # index de l'objectif en cours

    # --- Attaque adaptative en cours (boucle interne) ---
    attempt: int               # n° de tentative sur l'objectif courant
    max_attempts: int          # plafond de tentatives par objectif
    conversation: list[dict]   # dialogue attacker<->target pour CE goal
    current_success: bool      # l'objectif courant a-t-il été atteint ?

    # --- Résultats (accumulés sur toute la campagne) ---
    achieved_goals: Annotated[list[dict], operator.add]  # objectifs atteints
    leak_events: Annotated[list[dict], operator.add]     # toutes les occurrences de fuite