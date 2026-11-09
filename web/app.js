/* ============================================================
   Agent-Evaluator — logique du dashboard (vanilla JS)
   La page est servie par FastAPI (même origine) → pas de CORS.

   ⚙️  TOUTES LES HYPOTHÈSES SUR TON API SONT ICI (bloc CONFIG).
   ============================================================ */

const CONFIG = {
  endpoints: {
    targets:      "/targets",
    scanRegistry: "/scan/registry",
    scanAuto:     "/scan/url/auto",
    scanFlat:     "/scan/url/flat",
    scanOpenai:   "/scan/url/openai",
    scanMcp:      "/scan/url/mcp",
    scanStatus:   (id) => `/scan/${id}`,
    scanCancel:   (id) => `/scan/${id}/cancel`,
    report:       (id) => `/report/${id}`,
    history:      "/history",
    historyFile:  (f) => `/history/${encodeURIComponent(f)}`,
    scanHosted:   "/scan/hosted",
    hostedLaunch:       "/hosted/launch",
    hostedLaunchStatus: (id) => `/hosted/launch/${id}`,
    hostedLaunchStop:   (id) => `/hosted/launch/${id}/stop`,
    hostedScan:         "/hosted/scan",
  },
  doneStatuses:  ["done", "terminé", "termine", "completed", "finished", "ok"],
  errorStatuses: ["error", "erreur", "failed", "échec", "echec"],
  pollMs: 15000,
};

const SEVERITY = {
  5: { label: "Critique", color: "var(--sev-5)" },
  4: { label: "Élevée",   color: "var(--sev-4)" },
  3: { label: "Moyenne",  color: "var(--sev-3)" },
  2: { label: "Faible",   color: "var(--sev-2)" },
  1: { label: "Info",     color: "var(--sev-1)" },
};

/* ---------- helpers ---------- */
const $  = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}
async function postJSON(url, body) {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    let detail = `${r.status} ${r.statusText}`;
    try { const j = await r.json(); if (j.detail) detail = JSON.stringify(j.detail); } catch {}
    throw new Error(detail);
  }
  return r.json();
}

/* ---------- navigation entre vues ---------- */
function setView(view) {
  $$(".nav-item").forEach((t) => t.classList.toggle("active", t.dataset.view === view));
  $("#view-scan").classList.toggle("hidden", view !== "scan");
  $("#view-history").classList.toggle("hidden", view !== "history");
  $("#head-scan").classList.toggle("hidden", view !== "scan");
  $("#head-history").classList.toggle("hidden", view !== "history");
  if (view === "history") {
    $("#history-report-panel").classList.add("hidden");
    $("#history-grid-panel").classList.remove("hidden");
    loadHistory();
  }
}

/* ---------- état & mode du formulaire ---------- */
let currentMode = "registry";
let pollTimer = null;
let currentScanId = null;
let targetsCache = [];
let currentLaunchId = null;
let launchPollTimer = null;
let currentLaunchUrl = null;
let currentContainerId = null;

function setMode(mode) {
  currentMode = mode;
  $$(".mode-btn").forEach((b) => b.classList.toggle("active", b.dataset.mode === mode));
  $$(".group-registry").forEach((e) => e.classList.toggle("hidden", mode !== "registry"));
  $$(".group-url").forEach((e) => e.classList.toggle("hidden", mode !== "url"));
  $$(".group-hosted").forEach((e) => e.classList.toggle("hidden", mode !== "hosted"));
  $$(".group-auth").forEach((e) => e.classList.toggle("hidden", mode !== "url"));
  if (mode === "url") syncFlatFields();
}

function syncFlatFields() {
  const flat = $("#format-select").value === "flat";
  $$(".group-flat").forEach((e) => e.classList.toggle("hidden", !flat));
}

/* ---------- cibles du registre ---------- */
function normalizeTargets(data) {
  let list = Array.isArray(data) ? data : (data.targets || data.cibles || null);
  if (!list && typeof data === "object") {
    list = Object.entries(data).map(([k, v]) => ({ name: k, description: v?.description }));
  }
  if (!list) return [];
  return list.map((t) =>
    typeof t === "string" ? { name: t, description: "" }
      : { name: t.name || t.id || t.nom, description: t.description || t.desc || "" });
}

async function loadTargets() {
  const status = $("#api-status");
  try {
    const data = await getJSON(CONFIG.endpoints.targets);
    targetsCache = normalizeTargets(data);
    const sel = $("#target-select");
    sel.innerHTML = targetsCache.map((t) => `<option value="${esc(t.name)}">${esc(t.name)}</option>`).join("");
    updateTargetDesc();
    status.classList.add("ok"); status.classList.remove("down");
    status.querySelector(".label").textContent = "API connectée";
  } catch {
    status.classList.add("down"); status.classList.remove("ok");
    status.querySelector(".label").textContent = "API injoignable";
    $("#target-select").innerHTML = `<option>— API hors ligne —</option>`;
  }
}

function updateTargetDesc() {
  const t = targetsCache.find((x) => x.name === $("#target-select").value);
  $("#target-desc").textContent = t?.description || "";
}

/* ---------- lancement ---------- */
function parseEnv(text) {
  const env = {};
  text.split("\n").forEach((line) => {
    const l = line.trim();
    if (!l || l.startsWith("#")) return;
    const i = l.indexOf("=");
    if (i > 0) env[l.slice(0, i).trim()] = l.slice(i + 1).trim();
  });
  return env;
}

function withAuth(body) {
  const h = $("#auth-header").value.trim();
  const v = $("#auth-value").value.trim();
  if (h && v) { body.auth_header = h; body.auth_value = v; }
  return body;
}

function buildPayload() {
  const name = $("#name-input").value.trim();
  const max_attempts = parseInt($("#attempts-input").value, 10) || 3;
  const model = $("#model-input").value.trim();
  const common = { max_attempts };
  if (name) common.name = name;
  if (model) common.model = model;

  if (currentMode === "registry") {
    return { url: CONFIG.endpoints.scanRegistry,
             body: { target: $("#target-select").value, max_attempts } };
  }

  const url = $("#url-input").value.trim();
  if (!url) throw new Error("Renseigne l'URL de l'agent.");
  const fmt = $("#format-select").value;
  if (fmt === "auto")   return { url: CONFIG.endpoints.scanAuto,   body: withAuth({ ...common, url }) };
  if (fmt === "mcp")    return { url: CONFIG.endpoints.scanMcp,    body: withAuth({ ...common, url }) };
  if (fmt === "openai") return { url: CONFIG.endpoints.scanOpenai, body: withAuth({ ...common, url }) };
  return { url: CONFIG.endpoints.scanFlat, body: withAuth({
    ...common, url,
    request_field: $("#request-field").value.trim() || "message",
    reply_field: $("#reply-field").value.trim() || "reply",
  }) };
}

function extractScanId(data) {
  return data.scan_id || data.id || data.scanId || data.scan || null;
}

async function launchScan(e) {
  e.preventDefault();
  const errBox = $("#form-error");
  errBox.classList.add("hidden");
  const btn = $("#launch-btn");
  if (currentMode === "hosted") { launchHostedContainer(errBox, btn); return; }

  let req;
  try { req = buildPayload(); }
  catch (err) { errBox.textContent = err.message; errBox.classList.remove("hidden"); return; }

  btn.disabled = true;
  try {
    const data = await postJSON(req.url, req.body);
    const id = extractScanId(data);
    if (!id) throw new Error("Réponse sans identifiant de scan.");
    showRunning(req.body.target || req.body.name || req.body.image || req.body.url);
    startPolling(id);
  } catch (err) {
    errBox.textContent = "Échec du lancement : " + err.message;
    errBox.classList.remove("hidden");
    btn.disabled = false;
  }
}

function launchHostedContainer(errBox, btn) {
  const image = $("#image-input").value.trim();
  if (!image) { errBox.textContent = "Renseigne l'image Docker."; errBox.classList.remove("hidden"); return; }
  const port = parseInt($("#port-input").value, 10);
  if (!port) { errBox.textContent = "Renseigne le port interne."; errBox.classList.remove("hidden"); return; }

  const body = { image, container_port: port, env: parseEnv($("#env-input").value) };
  const dataDir = $("#data-input").value.trim();
  if (dataDir) { body.data_host_dir = dataDir; body.data_mount_path = $("#mount-input").value.trim() || "/data"; }
  const ready = $("#ready-input").value.trim();
  if (ready) body.ready_path = ready;

  btn.disabled = true;
  showHostedLaunching();
  postJSON(CONFIG.endpoints.hostedLaunch, body)
    .then((data) => { currentLaunchId = data.launch_id; pollLaunch(currentLaunchId); })
    .catch((err) => { showError("Échec du lancement : " + err.message); btn.disabled = false; });
}

function pollLaunch(id) {
  clearInterval(launchPollTimer);
  const tick = async () => {
    try {
      const st = await getJSON(CONFIG.endpoints.hostedLaunchStatus(id));
      if (st.status === "ready") {
        clearInterval(launchPollTimer);
        currentLaunchUrl = st.url;
        currentContainerId = st.container_id;
        showHostedConfig(st.url);
      } else if (st.status === "error") {
        clearInterval(launchPollTimer);
        showError("Lancement échoué : " + (st.detail || ""));
        $("#launch-btn").disabled = false;
      } else {
        $("#running-sub").textContent = "Démarrage du conteneur… (" + st.status + ")";
      }
    } catch (err) {
      clearInterval(launchPollTimer);
      showError("Perte de contact : " + err.message);
    }
  };
  tick();
  launchPollTimer = setInterval(tick, 3000);
}

function showHostedLaunching() {
  $("#empty-state").classList.add("hidden");
  $("#report-state").classList.add("hidden");
  $("#hosted-config-state").classList.add("hidden");
  $("#running-state").classList.remove("hidden");
  $("#stop-btn").classList.add("hidden");
  $("#running-title").textContent = "Lancement de la cible…";
  $("#running-sub").textContent = "Démarrage du conteneur";
}

function showHostedConfig(url) {
  $("#running-state").classList.add("hidden");
  const link = $("#hosted-open-link");
  link.href = url;
  link.textContent = "Ouvrir la cible : " + url + " ↗";
  $("#hosted-config-state").classList.remove("hidden");
}

async function launchHostedScan() {
  if (!currentLaunchId) return;
  const btn = $("#cfg-scan-btn");
  const status = $("#cfg-status");
  status.classList.add("hidden");
  const body = {
    launch_id: currentLaunchId,
    target_format: $("#cfg-format").value,
    url: currentLaunchUrl,
    container_id: currentContainerId,
    keep_alive: $("#cfg-keep").checked,
    max_attempts: parseInt($("#attempts-input").value, 10) || 3,
  };
  const ap = $("#cfg-apipath").value.trim();
  if (ap) body.api_path = ap;
  const h = $("#cfg-auth-header").value.trim(), v = $("#cfg-auth-value").value.trim();
  if (h && v) { body.auth_header = h; body.auth_value = v; }
  const name = $("#name-input").value.trim(); if (name) body.name = name;
  const model = $("#model-input").value.trim(); if (model) body.model = model;

  btn.disabled = true;
  try {
    const data = await postJSON(CONFIG.endpoints.hostedScan, body);
    const sid = extractScanId(data);
    if (!sid) throw new Error("Réponse sans identifiant de scan.");
    $("#hosted-config-state").classList.add("hidden");
    showRunning("cible hébergée");
    startPolling(sid);
  } catch (err) {
    status.textContent = "Échec : " + err.message;
    status.classList.remove("hidden");
    btn.disabled = false;
  }
}

async function stopHostedLaunch() {
  if (currentLaunchId) {
    try { await postJSON(CONFIG.endpoints.hostedLaunchStop(currentLaunchId), {}); } catch {}
  }
  clearInterval(launchPollTimer);
  currentLaunchId = null;
  $("#hosted-config-state").classList.add("hidden");
  $("#empty-state").classList.remove("hidden");
  $("#launch-btn").disabled = false;
}

/* ---------- polling ---------- */
function startPolling(id) {
  clearInterval(pollTimer);
  currentScanId = id;
  let ticks = 0;
  const tick = async () => {
    ticks++;
    try {
      const st = await getJSON(CONFIG.endpoints.scanStatus(id));
      const status = String(st.status ?? st.state ?? "").toLowerCase();
      $("#running-sub").textContent =
        (st.detail || st.message || status || "en cours") + `  ·  ${ticks * CONFIG.pollMs / 1000}s`;

      if (CONFIG.doneStatuses.includes(status)) {
        clearInterval(pollTimer);
        await showReport(id, st);
      } else if (CONFIG.errorStatuses.includes(status)) {
        clearInterval(pollTimer);
        showError(st.detail || st.error || "Le scan a échoué.");
      }
    } catch (err) {
      clearInterval(pollTimer);
      showError("Perte de contact avec l'API : " + err.message);
    }
  };
  tick();
  pollTimer = setInterval(tick, CONFIG.pollMs);
}

/* ---------- historique ---------- */
async function loadHistory() {
  try {
    const data = await getJSON(CONFIG.endpoints.history);
    renderHistory(data.scans || []);
  } catch {
    $("#history-grid").innerHTML = `<p class="hist-empty">Historique indisponible (API injoignable).</p>`;
  }
}

function renderHistory(items) {
  const box = $("#history-grid");
  if (!items.length) { box.innerHTML = `<p class="hist-empty">Aucun scan enregistré pour l'instant.</p>`; return; }
  box.innerHTML = items.map((it) => {
    const s = it.synthese || {};
    const ex = s.exploites ?? it.nb_vulnerabilites ?? 0;
    const ax = s.axes ?? (it.objectifs_testes || []).length ?? 0;
    const cls = ex > 0 ? "hit" : "safe";
    const date = (it.date || "").replace("T", " ");
    return `<button class="hist-card" type="button" data-file="${esc(it.file)}">
      <div class="hc-top">
        <span class="hc-name">${esc(it.nom || "cible")}</span>
        <span class="hc-score ${cls}">${ex}/${ax}</span>
      </div>
      <div class="hc-role">${esc(it.role || "")}</div>
      <div class="hc-date">${esc(date)}</div>
    </button>`;
  }).join("");
  box.querySelectorAll(".hist-card").forEach((b) =>
    b.addEventListener("click", () => openHistory(b.dataset.file)));
}

async function openHistory(file) {
  try {
    const data = await getJSON(CONFIG.endpoints.historyFile(file));
    $("#history-report").innerHTML = buildReportHTML(data.report || data.rapport || data);
    $("#history-grid-panel").classList.add("hidden");
    $("#history-report-panel").classList.remove("hidden");
    window.scrollTo({ top: 0, behavior: "smooth" });
  } catch (e) {
    $("#history-report").innerHTML = `<div class="notice">Impossible de charger ce rapport : ${esc(e.message)}</div>`;
    $("#history-grid-panel").classList.add("hidden");
    $("#history-report-panel").classList.remove("hidden");
  }
}

/* ---------- arrêt ---------- */
async function stopScan() {
  clearInterval(pollTimer);
  const id = currentScanId;
  $("#stop-btn").disabled = true;
  if (id) {
    try { await postJSON(CONFIG.endpoints.scanCancel(id), {}); } catch {}
  }
  $("#running-state").classList.add("hidden");
  const box = $("#report-state");
  box.classList.remove("hidden");
  box.innerHTML = `<div class="notice">⏹ Scan arrêté.</div>`;
  $("#stop-btn").disabled = false;
  $("#launch-btn").disabled = false;
}

/* ---------- affichage (vue scan) ---------- */
function showRunning(label) {
  $("#stop-btn").classList.remove("hidden");
  $("#empty-state").classList.add("hidden");
  $("#report-state").classList.add("hidden");
  $("#running-state").classList.remove("hidden");
  $("#running-title").textContent = `Scan de ${label}…`;
  $("#running-sub").textContent = "initialisation";
}

function showError(msg) {
  $("#running-state").classList.add("hidden");
  const box = $("#report-state");
  box.classList.remove("hidden");
  box.innerHTML = `<div class="verdict hit"><span class="big hit">!</span>
    <span class="v-text">${esc(msg)}</span></div>`;
  $("#launch-btn").disabled = false;
}

async function showReport(id, statusObj) {
  let report = statusObj.report || statusObj.rapport;
  if (!report) {
    try { report = await getJSON(CONFIG.endpoints.report(id)); }
    catch (e) { return showError("Scan terminé mais rapport introuvable : " + e.message); }
  }
  $("#running-state").classList.add("hidden");
  $("#empty-state").classList.add("hidden");
  const box = $("#report-state");
  box.classList.remove("hidden");
  box.innerHTML = buildReportHTML(report.report || report.rapport || report);
  $("#launch-btn").disabled = false;
  loadHistory();   // le nouveau scan vient d'être archivé
}

/* ---------- construction du rapport (partagée scan + historique) ---------- */
function buildReportHTML(r) {
  const cible = r.cible || {};
  const findings = r.findings || r.achieved_goals || [];
  const tested = r.objectifs_testes || (r.goals ? r.goals.map((g) => g.id || g) : []);
  const objectifs = r.objectifs || [];
  const hit = findings.length > 0;
  const hitIds = new Set(findings.map((f) => f.owasp || f.goal_id || f.id));
  const sevSort = (a, b) => (b.gravite || 0) - (a.gravite || 0);

  const synth = r.synthese || {
    axes: tested.length,
    exploites: tested.filter((id) => hitIds.has(id)).length,
    resistes: tested.filter((id) => !hitIds.has(id)).length,
  };

  const coverage = tested.map((id) => {
    const isHit = hitIds.has(id);
    return `<span class="cov-chip ${isHit ? "hit" : "safe"}">
      <span class="cov-dot"></span>${esc(id)} · ${isHit ? "ATTEINT" : "résisté"}</span>`;
  }).join("");

  const axes = objectifs.map((o) => {
    const sev = SEVERITY[o.gravite] || SEVERITY[3];
    const tries = (o.tentatives || []).map((t) => `
      <div class="attempt">
        <div class="att-head">Tentative ${esc(t.tentative)} ·
          <span class="att-verdict ${t.reussi ? "v-hit" : "v-safe"}">${t.reussi ? "cédé" : "résisté"}</span></div>
        <div class="att-block"><span class="att-label">Attaque</span><pre>${esc(t.attaque || "")}</pre></div>
        <div class="att-block"><span class="att-label">Réponse</span><pre>${esc(t.reponse || "")}</pre></div>
        ${t.raison ? `<div class="att-reason">Juge · ${esc(t.raison)}</div>` : ""}
      </div>`).join("");
    return `<div class="axis ${o.atteint ? "hit" : "safe"}"
         style="border-left-color:${o.atteint ? sev.color : "var(--accent-dim)"}">
      <div class="axis-top">
        <span class="asi-badge">${esc(o.owasp || o.id)}</span>
        <span class="axis-title">${esc(o.titre || "")}</span>
        <span class="axis-outcome ${o.atteint ? "hit" : "safe"}">${o.atteint ? "ATTEINT" : "résisté"}</span>
      </div>
      ${tries ? `<details class="axis-details"><summary>${(o.tentatives || []).length} tentative(s)</summary>${tries}</details>`
        : `<p class="axis-empty">aucune tentative enregistrée</p>`}
    </div>`;
  }).join("");

  const cards = [...findings].sort(sevSort).map((f) => {
    const sev = SEVERITY[f.gravite] || SEVERITY[3];
    const payload = f.payload ? `<details class="payload"><summary>Payload gagnant</summary>
        <pre>${esc(f.payload)}</pre></details>` : "";
    const secrets = (f.secrets_reveles && f.secrets_reveles.length)
      ? `<div class="finding-meta">secrets révélés : ${esc(f.secrets_reveles.join(", "))}</div>` : "";
    return `<div class="finding" style="border-left-color:${sev.color}">
      <div class="finding-top">
        <span class="asi-badge">${esc(f.owasp || f.goal_id || "ASI")}</span>
        <span class="finding-title">${esc(f.titre || "Vulnérabilité")}</span>
        <span class="sev-pill" style="background:${sev.color}">${sev.label}</span>
      </div>
      <p class="finding-reason">${esc(f.raison || "")}</p>
      <div class="finding-meta">${f.tentatives ? `atteint en ${esc(f.tentatives)} tentative(s)` : ""}</div>
      ${secrets}
      ${payload}
    </div>`;
  }).join("");

  return `
    <div class="report-head">
      <span class="r-name">${esc(cible.nom || cible.name || "Cible")}</span>
      <span class="r-role">${esc(cible.role || "")}</span>
      <span class="r-date">${esc(r.date || "")}</span>
    </div>

    <div class="verdict ${hit ? "hit" : "clean"}">
      <span class="big ${hit ? "hit" : "clean"}">${findings.length}/${tested.length || "?"}</span>
      <span class="v-text">${esc(r.verdict_global || (hit
        ? `${findings.length} vulnérabilité(s) sur ${tested.length} axe(s).`
        : "Aucune vulnérabilité détectée."))}</span>
    </div>

    <div class="synthese">
      <div class="syn-cell"><span class="syn-num">${synth.axes}</span><span class="syn-lab">axes testés</span></div>
      <div class="syn-cell"><span class="syn-num hit">${synth.exploites}</span><span class="syn-lab">exploités</span></div>
      <div class="syn-cell"><span class="syn-num safe">${synth.resistes}</span><span class="syn-lab">résistés</span></div>
    </div>

    ${tested.length ? `<div class="coverage"><h4>Couverture</h4><div class="cov-grid">${coverage}</div></div>` : ""}

    ${findings.length ? `<div class="findings-wrap"><h4>Vulnérabilités</h4>${cards}</div>`
      : `<div class="findings-wrap"><h4>Vulnérabilités</h4>
          <p class="finding-reason">La cible a résisté à tous les axes testés. 🛡️</p></div>`}

    ${axes ? `<div class="axes-wrap"><h4>Détail par axe</h4>${axes}</div>` : ""}
  `;
}

/* ---------- init ---------- */
document.addEventListener("DOMContentLoaded", () => {
  $$(".nav-item").forEach((t) => t.addEventListener("click", (e) => { e.preventDefault(); setView(t.dataset.view); }));
  $$(".mode-btn").forEach((b) => b.addEventListener("click", () => setMode(b.dataset.mode)));
  $("#format-select").addEventListener("change", syncFlatFields);
  $("#target-select").addEventListener("change", updateTargetDesc);
  $("#scan-form").addEventListener("submit", launchScan);
  $("#stop-btn").addEventListener("click", stopScan);
  $("#hist-back").addEventListener("click", () => {
    $("#history-report-panel").classList.add("hidden");
    $("#history-grid-panel").classList.remove("hidden");
  });
  $("#cfg-scan-btn").addEventListener("click", launchHostedScan);
  $("#cfg-stop-btn").addEventListener("click", stopHostedLaunch);
  setMode("registry");
  setView("scan");
  loadTargets();
});