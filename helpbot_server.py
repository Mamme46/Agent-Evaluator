# -*- coding: utf-8 -*-
"""Serveur de test : expose HelpBot derrière un endpoint HTTP (simule un agent externe)."""
from fastapi import FastAPI
from pydantic import BaseModel
from src.targets import dummy_agent

app = FastAPI(title="HelpBot HTTP")
_bot = dummy_agent.build()


class Msg(BaseModel):
    message: str


@app.post("/chat")
def chat(m: Msg):
    r = _bot.send(m.message)
    return {"reply": r.reply, "trajectory": r.trajectory}