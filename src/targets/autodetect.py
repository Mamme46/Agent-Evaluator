# -*- coding: utf-8 -*-
"""
Détection AUTOMATIQUE du format d'un agent HTTP inconnu.
"""
import requests
from .base import TargetResponse, TargetProfile
from .mcp_target import MCPTarget


def _req_openai(msg, model):
    return {"model": model or "gpt-4o", "messages": [{"role": "user", "content": msg}]}

def _req_messages(msg, model):
    return {"messages": [{"role": "user", "content": msg}]}

def _req_single(key):
    return lambda msg, model: {key: msg}

REQUEST_BUILDERS = [
    ("openai",   _req_openai),
    ("messages", _req_messages),
    ("message",  _req_single("message")),
    ("input",    _req_single("input")),
    ("prompt",   _req_single("prompt")),
    ("query",    _req_single("query")),
    ("text",     _req_single("text")),
    ("question", _req_single("question")),
    ("q",        _req_single("q")),
]


def _oa(d):        return d["choices"][0]["message"]["content"]
def _oa_text(d):   return d["choices"][0]["text"]
def _top(key):     return lambda d: d[key]
def _nested(a, b): return lambda d: d[a][b]

_JSON_EXTRACTORS = [
    ("choices[0].message.content", _oa),
    ("choices[0].text",            _oa_text),
    ("reply",                      _top("reply")),
    ("response",                   _top("response")),
    ("message",                    _top("message")),
    ("output",                     _top("output")),
    ("text",                       _top("text")),
    ("content",                    _top("content")),
    ("answer",                     _top("answer")),
    ("result",                     _top("result")),
    ("completion",                 _top("completion")),
    ("generation",                 _top("generation")),
    ("data.reply",                 _nested("data", "reply")),
    ("data.response",              _nested("data", "response")),
    ("data.message",               _nested("data", "message")),
    ("output.text",                _nested("output", "text")),
    ("message.content",            _nested("message", "content")),
]


def _extract(resp, fn):
    try:
        val = fn(resp.json())
    except Exception:
        return None
    if isinstance(val, str) and val.strip():
        return val.strip()
    return None


def _extract_plaintext(resp):
    ct = resp.headers.get("content-type", "")
    if "application/json" in ct:
        return None
    txt = (resp.text or "").strip()
    return txt or None


class AutoTarget:
    def __init__(self, url, req_builder, extractor_name, extractor_fn,
                 name, capabilities, model, send_timeout, headers=None):
        self.url = url
        self._build = req_builder
        self._extractor_name = extractor_name
        self._extractor_fn = extractor_fn
        self._name = name
        self._caps = capabilities or []
        self._model = model
        self._timeout = send_timeout
        self._headers = headers

    def describe(self) -> TargetProfile:
        return TargetProfile(name=self._name, role="Agent distant (format auto-détecté)",
                             capabilities=self._caps)

    def send(self, message: str) -> TargetResponse:
        try:
            r = requests.post(self.url, json=self._build(message, self._model),
                              headers=self._headers, timeout=self._timeout)
            if self._extractor_fn is None:
                reply = (r.text or "").strip() or "[réponse vide]"
            else:
                reply = _extract(r, self._extractor_fn) or "[réponse vide]"
        except Exception as e:
            reply = f"[ERREUR cible injoignable: {e}]"
        return TargetResponse(reply=reply, trajectory=[])


def build_auto_target(url, name="agent-externe", model=None, capabilities=None,
                      detect_timeout=60, send_timeout=300, headers=None,
                      probe="Bonjour, peux-tu confirmer que tu me reçois en une phrase ?"):
    _mcp_data = None
    try:
        r = requests.post(url, json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
                          headers=headers, timeout=detect_timeout)
        _mcp_data = r.json()
    except Exception:
        _mcp_data = None
    if (isinstance(_mcp_data, dict) and isinstance(_mcp_data.get("result"), dict)
            and "tools" in _mcp_data["result"]):
        print("[autodetect] format détecté : MCP (JSON-RPC, tools/list)")
        return MCPTarget(url, name=name, capabilities=capabilities,
                         timeout=send_timeout, headers=headers)

    last_err = "aucune réponse exploitable"
    for rb_name, rb in REQUEST_BUILDERS:
        try:
            r = requests.post(url, json=rb(probe, model), headers=headers,
                              timeout=detect_timeout)
        except Exception as e:
            last_err = f"requête '{rb_name}' -> {e}"
            continue
        if r.status_code != 200:
            last_err = f"requête '{rb_name}' -> HTTP {r.status_code}"
            continue
        for ex_name, ex_fn in _JSON_EXTRACTORS:
            if _extract(r, ex_fn):
                print(f"[autodetect] format détecté : requête='{rb_name}', réponse='{ex_name}'")
                return AutoTarget(url, rb, ex_name, ex_fn, name, capabilities,
                                  model, send_timeout, headers=headers)
        if _extract_plaintext(r):
            print(f"[autodetect] format détecté : requête='{rb_name}', réponse='texte brut'")
            return AutoTarget(url, rb, "texte brut", None, name, capabilities,
                              model, send_timeout, headers=headers)
        last_err = f"requête '{rb_name}' -> 200 mais réponse non reconnue"
    raise ValueError(f"Format non détecté pour {url} ({last_err}).")