# -*- coding: utf-8 -*-
"""Service de scan : lance une campagne et renvoie le rapport (dict)."""
from .core.graph import build_graph
from .targets.registry import get_target

MAX_ATTEMPTS = 4


def run_scan(target_name=None, target_url=None, target_format="flat",
             request_field="message", reply_field="reply",
             name="agent-externe", model="gpt-4o", capabilities=None,
             max_attempts=MAX_ATTEMPTS) -> dict:
    if target_url:
        if target_format == "openai":
            from .targets.openai_target import OpenAICompatibleTarget
            target = OpenAICompatibleTarget(url=target_url, model=model,
                                            name=name, capabilities=capabilities)
        else:
            from .targets.http_target import HTTPTarget
            target = HTTPTarget(url=target_url, name=name, capabilities=capabilities,
                                request_field=request_field, reply_field=reply_field)
    else:
        target = get_target(target_name or "helpbot")
    graph = build_graph(target)
    final_state = graph.invoke({"max_attempts": max_attempts}, config={"recursion_limit": 100})
    return final_state.get("report", {})