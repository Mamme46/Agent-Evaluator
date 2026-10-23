# -*- coding: utf-8 -*-
"""
Nœud TARGET : envoie la dernière tentative de l'attaquant à la cible et récupère
sa réponse. Passe par l'interface Target -> marche pour n'importe quelle cible.
"""
from ..state import State
from ...targets.base import Target


def make_send_to_target(target: Target):
    def send_to_target(state: State) -> dict:
        dernier = state["conversation"][-1]["msg"]   # dernier msg = celui de l'attaquant
        response = target.send(dernier)              # <-- on parle à la cible
        apercu = response.reply[:400].replace("\n", " ")
        print(f"[target]   < {apercu}")
        return {
            "conversation": state["conversation"] + [
                {"role": "target", "msg": response.reply, "trajectory": response.trajectory}
            ],
        }
    return send_to_target