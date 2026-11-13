# Agent-Evaluator

**Plateforme de test de sécurité pour agents IA.** Un agent *red-team* attaque automatiquement un agent cible, et un agent *juge* (« AI-as-judge ») évalue ses réponses, le tout cartographié sur l'**OWASP Top 10 pour les applications agentiques**.

L'objectif : donner à un développeur ou un auditeur un verdict clair, axe par axe, sur la robustesse d'un agent face aux attaques courantes (injection de prompt, fuite de secrets, exécution d'outils non prévue, contournement de rôle…).

---

## Sommaire

- [Concept](#concept)
- [Fonctionnalités](#fonctionnalités)
- [Architecture](#architecture)
- [Prérequis](#prérequis)
- [Installation & lancement (Docker)](#installation--lancement-docker)
- [Lancement en local (dev)](#lancement-en-local-dev)
- [Les trois modes de scan](#les-trois-modes-de-scan)
- [Rapports & historique](#rapports--historique)
- [Usage responsable](#usage-responsable)
- [Feuille de route](#feuille-de-route)

---

## Concept

Agent-Evaluator fonctionne en deux boucles :

1. **Campagne** : pour chaque objectif de sécurité (un axe : fuite de secret, exécution d'outil, contournement de rôle…), la plateforme planifie une série de tentatives.
2. **Tentatives adaptatives** : l'agent attaquant forge une charge utile, l'envoie à la cible, lit la réponse, et adapte sa tentative suivante en fonction de ce qu'il a observé.

À la fin, l'agent **juge** évalue le comportement de la cible (il juge *le comportement*, pas l'authenticité d'une valeur renvoyée) et produit un verdict par axe avec les preuves (charges utiles envoyées, réponses obtenues, sévérité).

---

## Fonctionnalités

- **Trois modes de scan** : cible du registre, agent par URL, ou agent **hébergé** (la plateforme lance la cible en Docker pour toi).
- **Adaptateurs multiples** : JSON plat (champ requête → champ réponse), OpenAI-compatible (`/v1/chat/completions`), auto-détection du format, et MCP (serveur d'outils JSON-RPC).
- **Tableau de bord web** : lancement des scans, suivi en direct, lecture du verdict et historique des rapports.
- **Rapports persistants** : chaque scan est archivé en JSON et consultable depuis l'historique.

---

## Architecture

```
Agent-Evaluator/
├── api.py              # Backend FastAPI : endpoints + le dashboard
├── web/                # Interface utilisateur
├── src/
│   ├── service.py      # Orchestration du lancement des scans
│   ├── llm.py          # Modèles : Ollama (llama3.1 pour l'agent attaquant et qwen2.5 pour l'orchestrateur et le juge)
│   ├── cancel.py       # Annulation coopérative des scans
│   ├── core/
│   │   ├── graph.py    # Graphe LangGraph : Construction des boucles internes et externes 
│   │   ├── state.py    # État partagé du graphe
│   │   └── nodes/      # Les 4 pilliers de base : recon, planner, attacker, judge
│   ├── targets/        # Adaptateurs (HTTP plat, OpenAI, auto et MCP)
│   └── hosted/         # Lanceur Docker (scan hébergé)
└── reports/            # Rapports des scans éffectués
```

Le moteur de scan est construit avec **LangGraph** (graphe à états). Le backend **FastAPI** expose les endpoints et sert le dashboard.

---

## Prérequis

- **Docker** (Docker Desktop sous Windows/macOS).
- **[Ollama](https://ollama.com/)** installé sur la machine hôte, avec les modèles utilisés par la plateforme :
  ```bash
  ollama pull qwen2.5:7b-instruct
  ollama pull llama3.1:8b
  ```
- *(Optionnel)* Une clé **OpenAI** à configurer uniquement si tu choisis un modèle OpenAI, la plateforme fonctionne entièrement en local avec Ollama.

---

## Installation & lancement (Docker)

Depuis la racine du projet :

```powershell
docker build -t agent-evaluator .

docker run -d --name agent-evaluator -p 8000:8000 `
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 `
  -v /var/run/docker.sock:/var/run/docker.sock `
  -v ${PWD}\reports:/app/reports `
  --add-host host.docker.internal:host-gateway `
  agent-evaluator
```

Puis ouvre **http://localhost:8000**.

Ce que font les options :

| Option | Rôle |
|---|---|
| `-e OLLAMA_BASE_URL=http://host.docker.internal:11434` | Pointe le client vers l'Ollama de l'hôte. |
| `-v /var/run/docker.sock:/var/run/docker.sock` | Permet au **scan hébergé** de lancer des conteneurs cibles. |
| `-v ${PWD}\reports:/app/reports` | Garde tes rapports sur ta machine, hors de l'image. |
| `--add-host host.docker.internal:host-gateway` | Rend l'hôte joignable depuis le conteneur. |

Note (scan hébergé conteneurisé) : quand la plateforme tourne elle-même dans un conteneur et lance des conteneurs cibles, ceux-ci sont des frères sur l'hôte. Le mode URL fonctionnent tel quel; le mode hébergé nécessite un ajustement réseau (joindre la cible via host.docker.internal:<port> au lieu de 127.0.0.1).
---

## Lancement en local (dev)

Sans Docker, directement sur ta machine (Ollama sur `localhost:11434`) :

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
uvicorn api:app --reload
```

> En test de scan hébergé, lance **sans** `--reload` : le rechargement automatique efface l'état en mémoire (cibles lancées / scans en cours) entre le lancement et le scan.

---

## Les trois modes de scan

### 1. Registre
Choisis une cible pré-configurée dans la liste et lance le scan.

### 2. Agent par URL
Indique l'endpoint d'un agent que tu héberges déjà ou celui d'un agent public si tu as l'autorisation de le scanner, choisis le format (auto recommandé), ajoute un en-tête d'auth si besoin, puis lance.

### 3. Hébergé
La plateforme lance la cible en Docker pour toi, en deux temps :
1. **Lancement** : tu donnes l'image Docker, le port interne, les variables d'env et un éventuel dossier de données à monter. La plateforme démarre le conteneur et t'affiche un lien.
2. **Configuration & scan** : tu ouvres la cible, tu la configures (modèle, données, clé API), puis tu renseignes le chemin de l'API + l'auth et tu lances le scan. Le conteneur est arrêté en fin de scan.

---

## Rapports & historique

Chaque scan produit un rapport JSON dans `reports/`, monté sur ta machine via le volume Docker. L'onglet **Historique** liste tous les rapports archivés, du plus récent au plus ancien.

Les rapports **ne sont pas versionnés** (`.gitignore`) ni embarqués dans l'image (`.dockerignore`) : chaque personne qui lance la plateforme ne voit que **ses** scans.

---

## Usage responsable

⚠️ **Cet outil ne doit cibler que des agents que tu possèdes, que tu contrôles, ou pour lesquels tu as une autorisation explicite** (cibles d'entraînement volontairement vulnérables, CTF, périmètre de bug bounty).

- Les cibles délibérément vulnérables ne doivent **jamais** être exposées sur Internet : elles tournent uniquement en local, en Docker.
- **Ne committe jamais** de clé API (OpenAI ou autre). Les clés se passent au runtime via les variables d'environnement, jamais dans le code ou l'image.
- Scanner un agent tiers sans autorisation peut être illégal.

---
