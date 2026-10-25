# -*- coding: utf-8 -*-
"""
Cible HTTP générique : teste un agent externe via son endpoint.
Configurable (noms des champs, en-têtes) pour s'adapter à différents agents.
"""
import requests
from .base import Target, TargetProfile, TargetResponse


class HTTPTarget:
    def __init__(
        self,
        url: str,
        name: str = "agent-externe",
        role: str = "inconnu",
        capabilities: list[str] | None = None,
        request_field: str = "message",       # champ d'entrée attendu par l'agent
        reply_field: str = "reply",            # champ de sortie de l'agent
        trajectory_field: str = "trajectory",  # champ trajectoire (si exposé)
        headers: dict | None = None,           # ex. {"Authorization": "Bearer ..."}
        timeout: int = 60,
    ):
        self.url = url
        self._name = name
        self._role = role
        self._caps = capabilities or ["chat"]
        self.request_field = request_field
        self.reply_field = reply_field
        self.trajectory_field = trajectory_field
        self.headers = headers or {}
        self.timeout = timeout

    def describe(self) -> TargetProfile:
        return TargetProfile(name=self._name, role=self._role, capabilities=self._caps)

    def send(self, message: str) -> TargetResponse:
        try:
            resp = requests.post(
                self.url,
                json={self.request_field: message},
                headers=self.headers,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            # Agent injoignable ou erreur HTTP : on ne plante pas la campagne.
            return TargetResponse(reply=f"[ERREUR cible injoignable : {e}]", trajectory=[])

        reply = data.get(self.reply_field, "")
        trajectory = data.get(self.trajectory_field, []) or []
        return TargetResponse(reply=str(reply), trajectory=trajectory)