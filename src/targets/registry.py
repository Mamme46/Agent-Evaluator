# -*- coding: utf-8 -*-
"""
Registre des cibles PUBLIQUES de la plateforme (catalogue de favoris).

Pour un agent ponctuel d'un utilisateur, pas besoin d'y toucher : on passe
l'URL directement dans la requête de scan. Le registre ne sert QU'aux cibles
permanentes qu'on veut proposer en catalogue (GET /targets).
"""
from . import dummy_agent
from .http_target import HTTPTarget

# Chaque cible : un nom -> { fabrique, description }
_REGISTRY: dict[str, dict] = {
    "helpbot": {
        "build": dummy_agent.build,                    # agent EN-PROCESS (Python)
        "description": "Agent SAV jouet (ACME), volontairement vulnérable. Cible d'entraînement.",
    },
    "helpbot_http": {
        "build": lambda: HTTPTarget(                   # même agent, servi en HTTP
            url="http://localhost:7001/chat",
            name="HelpBot-HTTP",
            role="assistant service client",
            capabilities=["chat", "database"],
            timeout=300,                     
        ),
        "description": "HelpBot servi en HTTP (valide l'adaptateur HTTPTarget).",
    },
    # "dvaa": {
    #     "build": lambda: HTTPTarget(
    #         url="http://localhost:7000/chat",
    #         name="DVAA",
    #         role="agent vulnérable multi-rôles",
    #         capabilities=["chat", "database", "tools"],
    #     ),
    #     "description": "Damn Vulnerable AI Agent (OWASP), lancé via Docker.",
    # },
}


def list_targets() -> list[dict]:
    """Liste les cibles du catalogue (pour GET /targets)."""
    return [{"name": nom, "description": info["description"]} for nom, info in _REGISTRY.items()]


def target_exists(name: str) -> bool:
    return name in _REGISTRY


def get_target(name: str):
    """Instancie une cible du registre par son nom. Lève ValueError si inconnue."""
    info = _REGISTRY.get(name)
    if info is None:
        raise ValueError(f"cible inconnue : {name}. Disponibles : {list(_REGISTRY)}")
    return info["build"]()