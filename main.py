# -*- coding: utf-8 -*-
"""
Point d'entrée : lance une campagne de scan contre une cible.

Usage (PowerShell) :
    .\.venv\Scripts\python.exe main.py

Prérequis : Ollama lancé avec le modèle qwen3:8b.
"""
from src.core.graph import build_graph
from src.targets import dummy_agent


# Plafond de tentatives PAR objectif (boucle interne).
# Un 8B est lent : commence à 2 pour aller vite, augmente ensuite.
MAX_ATTEMPTS = 3


def main() -> None:
    # 1. On choisit la cible. Demain : dummy_agent -> dvaa, même interface.
    target = dummy_agent.build()

    # 2. On construit le graphe pour cette cible.
    graph = build_graph(target)

    # 3. État initial. recon/planner rempliront le reste.
    etat_initial = {
        "max_attempts": MAX_ATTEMPTS
    }

    # 4. On lance la campagne.
    #    recursion_limit : garde-fou global (beaucoup de tours possibles avec
    #    plusieurs objectifs x plusieurs tentatives).
    graph.invoke(etat_initial, config={"recursion_limit": 100})


if __name__ == "__main__":
    main()