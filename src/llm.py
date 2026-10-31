# -*- coding: utf-8 -*-
"""
Configuration du LLM (Qwen via Ollama).
Un seul endroit pour choisir le modèle -> tout le reste du projet importe d'ici.
"""
import os
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

# Modèle local. On le nomme ici une seule fois.
SCANNER_MODEL = "qwen2.5:7b-instruct"
ATTACKER_MODEL="llama3.1:8b"   
TARGET_MODEL = "llama3.1:8b"  


def get_llm(temperature: float = 0.0, model: str | None = None):
    model = model or SCANNER_MODEL
    if model.startswith("gpt-"):                    # ← LE branchement clé
        return ChatOpenAI(model=model, temperature=temperature,
                          api_key=os.environ["OPENAI_API_KEY"])
    return ChatOllama(model=model, temperature=temperature)