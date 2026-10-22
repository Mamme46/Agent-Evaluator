# -*- coding: utf-8 -*-
"""
Configuration du LLM (Qwen via Ollama).
Un seul endroit pour choisir le modèle -> tout le reste du projet importe d'ici.
"""
from langchain_ollama import ChatOllama

# Modèle local. On le nomme ici une seule fois.
MODEL_NAME = "qwen3:8b"


def get_llm(temperature: float = 0.0) -> ChatOllama:
    """Retourne une instance du LLM local.

    temperature : 0.0 = réponses stables (pour le juge) ;
                  plus haut = plus de créativité (pour l'attaquant).
    """
    return ChatOllama(model=MODEL_NAME, temperature=temperature)