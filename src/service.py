# -*- coding: utf-8 -*-
"""Service de scan : lance une campagne et renvoie le rapport (dict)."""
from .core.graph import build_graph
from .targets.registry import get_target

MAX_ATTEMPTS = 4


def run_scan(
    target_name: str | None = None,
    target_url: str | None = None,
    request_field: str = "message",
    reply_field: str = "reply",
    name: str = "agent-externe",
    max_attempts: int = MAX_ATTEMPTS,
) -> dict:
    """Scan par NOM (registre) ou par URL (agent arbitraire)."""
    if target_url:
        from .targets.http_target import HTTPTarget
        target = HTTPTarget(
            url=target_url, name=name,
            request_field=request_field, reply_field=reply_field,
        )
    else:
        target = get_target(target_name or "helpbot")

    graph = build_graph(target)
    final_state = graph.invoke({"max_attempts": max_attempts}, config={"recursion_limit": 100})
    return final_state.get("report", {})