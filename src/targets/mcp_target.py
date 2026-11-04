# -*- coding: utf-8 -*-
"""
Adaptateur MCP : parle le protocole JSON-RPC d'un serveur MCP (ex. DVAA ToolBot).

Contrairement à un agent de chat (où on social-engineer un LLM), un serveur MCP
expose des OUTILS. On l'attaque donc en appelant ses outils avec des arguments
malveillants (path traversal, SQLi, SSRF, injection de commande).

Transport DVAA : POST JSON-RPC sur l'URL racine.
  - tools/list -> { result: { tools: [{name, description, inputSchema}] } }
  - tools/call -> { result: { content: [{type:'text', text:'...'}] } }  (ou { error })

send() accepte deux formes de message :
  1. un appel d'outil STRUCTURÉ (le payload) :
       {"_mcpTool":"read_file","path":"../../etc/passwd"}         (format HackMyAgent)
       {"name":"read_file","arguments":{"path":"..."}}            (format MCP direct)
     -> traduit en vrai tools/call, renvoie le résultat + remplit la trajectory.
  2. du TEXTE (sonde de recon) -> renvoie le catalogue des outils, pour que le
     recon découvre la surface réelle.
"""
import json
import requests
from .base import TargetResponse, TargetProfile


class MCPTarget:
    def __init__(self, url, name="mcp-agent", capabilities=None, timeout=60):
        self.url = url.rstrip("/") + "/"       # JSON-RPC sur la racine
        self._name = name
        self._caps = capabilities or []
        self._timeout = timeout
        self._tools_cache = None

    # ---- JSON-RPC ----
    def _rpc(self, method, params=None):
        body = {"jsonrpc": "2.0", "method": method, "id": 1}
        if params is not None:
            body["params"] = params
        r = requests.post(self.url, json=body, timeout=self._timeout)
        return r.json()

    def list_tools(self):
        if self._tools_cache is not None:
            return self._tools_cache
        try:
            res = self._rpc("tools/list")
            self._tools_cache = res.get("result", {}).get("tools", []) or []
        except Exception:
            self._tools_cache = []
        return self._tools_cache

    # ---- interface Target ----
    def describe(self) -> TargetProfile:
        tools = self.list_tools()
        names = [t.get("name") for t in tools if t.get("name")]
        caps = names or self._caps
        return TargetProfile(
            name=self._name,
            role="Serveur MCP (expose des outils)",
            capabilities=[f"MCP tool: {n}" for n in names] or self._caps,
        )

    def _parse_tool_call(self, message: str):
        """Renvoie (name, arguments) si le message est un appel d'outil, sinon None."""
        try:
            d = json.loads(message)
        except Exception:
            return None
        if not isinstance(d, dict):
            return None
        if "_mcpTool" in d:
            name = d["_mcpTool"]
            args = {k: v for k, v in d.items() if k != "_mcpTool"}
            return name, args
        if "name" in d and "arguments" in d:
            return d["name"], d.get("arguments") or {}
        if d.get("method") == "tools/call":
            p = d.get("params", {})
            return p.get("name"), p.get("arguments") or {}
        return None

    def send(self, message: str) -> TargetResponse:
        spec = self._parse_tool_call(message)

        # Cas 1 : message texte (recon) -> on renvoie le catalogue d'outils
        if spec is None:
            tools = self.list_tools()
            desc = "; ".join(
                f"{t.get('name')}({', '.join((t.get('inputSchema', {}).get('properties') or {}).keys())})"
                for t in tools
            )
            return TargetResponse(
                reply=f"Serveur MCP. Outils disponibles : {desc or '(aucun)'}",
                trajectory=[],
            )

        # Cas 2 : appel d'outil réel
        name, args = spec
        try:
            res = self._rpc("tools/call", {"name": name, "arguments": args})
        except Exception as e:
            return TargetResponse(reply=f"[MCP injoignable: {e}]", trajectory=[])

        if "error" in res:
            text = f"[MCP error] {res['error'].get('message')}"
        else:
            content = res.get("result", {}).get("content", [])
            text = content[0].get("text", "") if content else json.dumps(res.get("result", {}))

        return TargetResponse(
            reply=text,
            trajectory=[{"tool": name, "args": args, "result": str(text)[:300]}],
        )