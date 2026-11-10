# -*- coding: utf-8 -*-
"""Service de scan : lance une campagne et renvoie le rapport (dict)."""
from .core.graph import build_graph
from .targets.registry import get_target

MAX_ATTEMPTS = 4


def run_scan(target_name=None, target_url=None, target_format="auto",
             request_field="message", reply_field="reply",
             name="agent-externe", model="gpt-4o", capabilities=None,
             max_attempts=MAX_ATTEMPTS, auth_header=None, auth_value=None,
             scan_id=None) -> dict:
    headers = {auth_header: auth_value} if auth_header and auth_value else None
    if target_url:
        if target_format == "mcp":
            from .targets.mcp_target import MCPTarget
            target = MCPTarget(url=target_url, name=name, capabilities=capabilities,
                               headers=headers)
        elif target_format == "auto":
            from .targets.autodetect import build_auto_target
            target = build_auto_target(url=target_url, name=name, model=model,
                                       capabilities=capabilities, headers=headers)
        elif target_format == "openai":
            from .targets.openai_target import OpenAICompatibleTarget
            target = OpenAICompatibleTarget(url=target_url, model=model, name=name,
                                            capabilities=capabilities, headers=headers)
        else:
            from .targets.http_target import HTTPTarget
            target = HTTPTarget(url=target_url, name=name, capabilities=capabilities,
                                request_field=request_field, reply_field=reply_field,
                                headers=headers)
    else:
        target = get_target(target_name or "helpbot")
    graph = build_graph(target)
    final_state = graph.invoke({"max_attempts": max_attempts, "scan_id": scan_id},
                               config={"recursion_limit": 100})
    return final_state.get("report", {})


def run_hosted_scan(image, container_port, env=None, data_host_dir=None,
                    data_mount_path="/data", ready_path=None, api_path=None,
                    target_format="auto", name="agent-hébergé", model="gpt-4o",
                    capabilities=None, max_attempts=MAX_ATTEMPTS,
                    auth_header=None, auth_value=None, scan_id=None) -> dict:
    from .hosted.launcher import HostedSpec, launch, stop
    spec = HostedSpec(image=image, container_port=container_port, env=env or {},
                      data_host_dir=data_host_dir, data_mount_path=data_mount_path,
                      ready_path=ready_path)
    info = launch(spec)
    try:
        scan_url = info["url"]
        if api_path:
            scan_url = scan_url.rstrip("/") + "/" + api_path.lstrip("/")
        return run_scan(target_url=scan_url, target_format=target_format, name=name,
                        model=model, capabilities=capabilities, max_attempts=max_attempts,
                        auth_header=auth_header, auth_value=auth_value, scan_id=scan_id)
    finally:
        stop(info["container_id"])