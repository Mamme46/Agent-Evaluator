# -*- coding: utf-8 -*-
"""
Cible compatible OpenAI (/v1/chat/completions).
Format IMBRIQUÉ et FIXE : messages[] en entrée, choices[0].message.content en sortie.
"""
import requests
from .base import Target, TargetProfile, TargetResponse


class OpenAICompatibleTarget:
    def __init__(self, url: str, model: str = "gpt-4o", name: str = "agent-openai",
                 role: str = "inconnu", capabilities: list[str] | None = None,
                 headers: dict | None = None, timeout: int = 120):
        self.url = url
        self.model = model
        self._name = name
        self._role = role
        self._caps = capabilities or ["chat"]
        self.headers = headers or {}
        self.timeout = timeout

    def describe(self) -> TargetProfile:
        return TargetProfile(name=self._name, role=self._role, capabilities=self._caps)

    def send(self, message: str) -> TargetResponse:
        body = {"model": self.model, "messages": [{"role": "user", "content": message}]}
        try:
            resp = requests.post(self.url, json=body, headers=self.headers, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            return TargetResponse(reply=f"[ERREUR cible injoignable : {e}]", trajectory=[])
        try:
            reply = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            reply = str(data)
        return TargetResponse(reply=str(reply), trajectory=[])