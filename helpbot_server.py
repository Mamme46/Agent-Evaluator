# -*- coding: utf-8 -*-
"""Serveur de test : expose HelpBot derrière un endpoint HTTP (simule un agent externe).

Variante INPUT/OUTPUT : sert à vérifier l'auto-détection de format.
- lit le message dans le champ "input"
- renvoie la réponse dans le champ "output"
- si "input" est absent -> 422 automatique (Pydantic) -> les autres formats échouent
"""
from fastapi import FastAPI
from pydantic import BaseModel
from src.targets import dummy_agent

app = FastAPI(title="HelpBot HTTP (input/output)")
_bot = dummy_agent.build()


class Msg(BaseModel):
    input: str


@app.post("/chat")
def chat(m: Msg):
    r = _bot.send(m.input)
    return {"output": r.reply, "trajectory": r.trajectory}