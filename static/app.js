"use strict";

async function getJSON(url, options) {
  const res = await fetch(url, options);
  return { ok: res.ok, status: res.status, body: await res.json().catch(() => null) };
}

function renderIngestionStatus(auditResp) {
  const statusEl = document.getElementById("ingestion-status");
  const summaryEl = document.getElementById("audit-summary");
  const audits = Array.isArray(auditResp.body) ? auditResp.body : [];

  if (audits.length === 0) {
    statusEl.className = "status status-gap";
    statusEl.textContent = "No FHIR data ingested yet";
    summaryEl.textContent =
      "POST /api/ingest/fhir is not implemented in the initial state (returns 501). " +
      "Clinical data is entered manually until ingestion is wired up.";
    return;
  }

  const latest = audits[0];
  statusEl.className = "status status-ok";
  statusEl.textContent = "Last ingest: " + latest.outcome;
  summaryEl.textContent =
    `${latest.resource_type} from ${latest.source}: received ${latest.resources_received}, ` +
    `ingested ${latest.resources_ingested}, skipped ${latest.resources_skipped}. ${latest.detail || ""}`;
}

function diagnosisPills(diagnoses) {
  if (!diagnoses || diagnoses.length === 0) return '<span class="muted">none</span>';
  return diagnoses.map((d) => `<span class="pill">${d.category}</span>`).join("");
}

function measurePills(measures) {
  if (!measures || measures.length === 0) return '<span class="muted">none</span>';
  return measures.map((m) => `<span class="pill">${m.measure}=${m.value}</span>`).join("");
}

async function loadParticipants() {
  const list = await getJSON("/api/participants");
  const tbody = document.querySelector("#participants-table tbody");
  tbody.innerHTML = "";
  for (const p of list.body || []) {
    const detail = await getJSON(`/api/participants/${p.id}`);
    const d = detail.body || {};
    const row = document.createElement("tr");
    row.innerHTML =
      `<td>${p.mrn}</td><td>${p.display_name}</td><td>${p.birth_year}</td><td>${p.sex}</td>` +
      `<td>${diagnosisPills(d.diagnoses)}</td><td>${measurePills(d.measures)}</td>`;
    tbody.appendChild(row);
  }
}

async function loadTrials() {
  const trials = await getJSON("/api/trials");
  const select = document.getElementById("trial-select");
  select.innerHTML = "";
  for (const t of trials.body || []) {
    const opt = document.createElement("option");
    opt.value = t.id;
    opt.textContent = `${t.code} — ${t.title}`;
    opt.dataset.criteria = (t.criteria || []).map((c) => c.description).join("; ");
    select.appendChild(opt);
  }
  select.addEventListener("change", () => loadPrescreen(select.value));
  if (select.value) loadPrescreen(select.value);
}

async function loadPrescreen(trialId) {
  const select = document.getElementById("trial-select");
  const opt = select.options[select.selectedIndex];
  document.getElementById("trial-criteria").textContent =
    opt ? "Criteria: " + opt.dataset.criteria : "";

  const results = await getJSON(`/api/trials/${trialId}/prescreen`);
  const tbody = document.querySelector("#prescreen-table tbody");
  tbody.innerHTML = "";
  for (const r of results.body || []) {
    const match = r.status === "potential_match";
    const badge = match
      ? '<span class="badge badge-match">potential match</span>'
      : '<span class="badge badge-nomatch">not matched</span>';
    const row = document.createElement("tr");
    row.innerHTML = `<td>${badge}</td><td>${r.mrn}</td><td>${r.display_name}</td><td>${r.rationale}</td>`;
    tbody.appendChild(row);
  }
}

async function init() {
  renderIngestionStatus(await getJSON("/api/ingest/audit"));
  await loadParticipants();
  await loadTrials();
}

init();
