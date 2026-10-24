# -*- coding: utf-8 -*-
"""Service de scan : lance une campagne et renvoie le rapport (dict)."""
from .core.graph import build_graph
from .targets import dummy_agent

MAX_ATTEMPTS = 4


def run_scan(max_attempts: int = MAX_ATTEMPTS) -> dict:
    """Exécute un scan complet contre la cible et renvoie le rapport."""
    target = dummy_agent.build()
    graph = build_graph(target)
    final_state = graph.invoke(
        {"max_attempts": max_attempts},
        config={"recursion_limit": 100},
    )
    return final_state.get("report", {})