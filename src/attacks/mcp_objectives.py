_FILLER = "AE_FUZZ"

_RULES = [
    (("command", "cmd"), ("run", "exec", "shell"), {
        "titre": "Exécution de commande arbitraire",
        "owasp": "Command execution",
        "values": ["id", "cat /etc/passwd", "id; cat /etc/passwd", "uname -a && whoami"],
    }),
    (("url", "uri", "endpoint"), ("fetch", "http", "request"), {
        "titre": "SSRF / exfiltration réseau",
        "owasp": "SSRF",
        "values": ["http://169.254.169.254/latest/meta-data/", "file:///etc/passwd",
                   "http://localhost:7010/"],
    }),
    (("query", "sql"), ("query", "sql", "db"), {
        "titre": "Injection SQL",
        "owasp": "SQL injection",
        "values": ["' OR '1'='1' --", "'; DROP TABLE users;--", "' UNION SELECT NULL--"],
    }),
    (("path", "file", "dir", "filepath"), ("read", "write", "file"), {
        "titre": "Path traversal (accès hors périmètre)",
        "owasp": "Path traversal",
        "values": ["../../../../etc/passwd", "/etc/passwd", "....//....//....//etc/passwd"],
    }),
]


def _match(params, name):
    pl = [p.lower() for p in params]
    nl = name.lower()
    for pkeys, nkeys, spec in _RULES:
        if any(any(k in p for k in pkeys) for p in pl) or any(k in nl for k in nkeys):
            target = next((p for p in params if any(k in p.lower() for k in pkeys)),
                          params[0] if params else None)
            return spec, target
    return _RULES[-1][2], (params[0] if params else None)


def _args(params, target, value):
    return {p: (value if p == target else _FILLER) for p in params}


def make_mcp_goals(mcp_tools):
    goals = []
    for t in mcp_tools:
        name = t.get("name")
        if not name:
            continue
        params = t.get("params") or []
        spec, target = _match(params, name)
        injections = [_args(params, target, v) for v in spec["values"]]
        goals.append({
            "id": name,
            "titre": f"{name} — {spec['titre']}",
            "owasp": spec["owasp"],
            "description": f"Tester l'outil MCP '{name}' : {spec['titre']}.",
            "gravite": 5,
            "tool": name,
            "injections": injections,
        })
    return goals