# -*- coding: utf-8 -*-
"""
Nœud RECON : profile la cible (rôle + capacités) et l'écrit dans l'état.
Pour l'instant le profil vient de target.describe(). Plus tard, recon pourra
sonder activement un agent inconnu.
"""
from ...targets.base import Target


def make_recon(target: Target):
    def recon(state) -> dict:
        profile = target.describe()
        print(f"[recon] cible = {profile.name} | rôle = {profile.role}")
        print(f"[recon] capacités = {profile.capabilities}")
        return {
            "target_name": profile.name,
            "target_role": profile.role,
            "target_caps": profile.capabilities,
        }
    return recon