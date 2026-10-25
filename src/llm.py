# -*- coding: utf-8 -*-
"""
Configuration du LLM (Qwen via Ollama).
Un seul endroit pour choisir le modèle -> tout le reste du projet importe d'ici.
"""
from langchain_ollama import ChatOllama

# Modèle local. On le nomme ici une seule fois.
SCANNER_MODEL = "qwen3:8b"   
TARGET_MODEL = "llama3.1:8b"  


def get_llm(temperature: float = 0.0, model: str | None = None) -> ChatOllama:
    return ChatOllama(model=model or SCANNER_MODEL, temperature=temperature)