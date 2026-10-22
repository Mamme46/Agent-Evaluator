# -*- coding: utf-8 -*-
"""
Interface COMMUNE de cible.

Tout agent qu'on veut tester doit respecter ce contrat. Le graphe ne parle
JAMAIS directement à un agent : il parle à un objet Target. C'est cette
abstraction qui permet de changer de cible sans toucher au cerveau du scanner.
"""
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class TargetResponse:
    """Ce qu'une cible renvoie après avoir reçu un message.

    - reply       : la réponse textuelle de l'agent (sens A)
    - trajectory  : la séquence d'outils appelés (rempli à l'étape 2). Vide ici.
    """
    reply: str
    trajectory: list[dict] = field(default_factory=list)


@dataclass
class TargetProfile:
    """Carte d'identité de la cible, utilisée par le nœud recon."""
    name: str
    role: str                 # ex. "assistant SAV"
    capabilities: list[str]   # ex. ["chat", "database"]


class Target(Protocol):
    """Contrat que toute cible doit implémenter."""

    def describe(self) -> TargetProfile:
        """Renvoie le profil de la cible (utilisé par recon)."""
        ...

    def send(self, message: str) -> TargetResponse:
        """Envoie un message à l'agent cible et renvoie sa réponse."""
        ...