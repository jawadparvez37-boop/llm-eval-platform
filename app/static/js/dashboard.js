const state = {
  datasets: [],
  evaluations: [],
};

const $ = (sel) => document.querySelector(sel);

function fmtPct(value) {
  return `${Math.round((value || 0) * 100)}%`;
}

function fmtDate(value) {
  if (!value) return "—";
  return new Date(value).toLocaleString();
}

function passClass(rate) {
  if (rate >= 0.75) return "pass-high";
  if (rate >= 0.45) return "pass-mid";
  return "pass-low";
}

function showToast(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.remove("hidden");
  setTimeout(() => toast.classList.add("hidden"), 2800);
}

async function api(path, options) {
  const res = await fetch(path, options);
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || res.statusText);
  }
  return res.json();
}

function setActivePanel(name) {
  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.panel === name);
  });
  document.querySelectorAll(".panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === `panel-${name}`);
  });
  const titles = {
    overview: "Overview",
    evaluations: "Evaluations",
    datasets: "Datasets",
    traces: "Traces",
  };
  $("#page-title").textContent = titles[name] || "Overview";
}

function renderOverview(overview, latestRun) {
  const passRate = latestRun?.summary?.pass_rate ?? overview.latest_runs?.[0]?.pass_rate ?? 0;
  $("#metric-pass-rate").textContent = fmtPct(passRate);
  $("#bar-pass-rate").style.width = `${Math.round(passRate * 100)}%`;
  $("#metric-runs").textContent = overview.evaluation_runs ?? 0;
  $("#metric-traces").textContent = overview.trace_count ?? 0;
  $("#metric-latency").textContent = `${overview.avg_trace_latency_ms ?? 0} ms`;

  const runsPreview = $("#runs-preview");
  runsPreview.innerHTML = "";
  (overview.latest_runs || []).slice(0, 5).forEach((run) => {
    const el = document.createElement("div");
    el.className = "run-item";
    el.innerHTML = `
      <div>
        <strong>${run.name}</strong>
        <div class="run-meta">${run.id.slice(0, 8)} · ${run.status}</div>
      </div>
      <span class="pass-pill ${passClass(run.pass_rate || 0)}">${fmtPct(run.pass_rate || 0)}</span>
    `;
    runsPreview.appendChild(el);
  });

  const chart = $("#quality-chart");
  chart.innerHTML = "";
  const metrics = [
    ["Faithfulness", latestRun?.summary?.avg_faithfulness ?? 0],
    ["Answer Relevance", latestRun?.summary?.avg_answer_relevance ?? 0],
    ["Context Precision", latestRun?.summary?.avg_context_precision ?? 0],
  ];
  metrics.forEach(([label, value]) => {
    const row = document.createElement("div");
    row.className = "quality-row";
    row.innerHTML = `
      <span>${label}</span>
      <div class="quality-track"><div class="quality-fill" style="width:${Math.round(value * 100)}%"></div></div>
      <strong>${fmtPct(value)}</strong>
    `;
    chart.appendChild(row);
  });
}

function renderEvaluations(runs) {
  const body = $("#eval-table-body");
  body.innerHTML = "";
  runs.forEach((run) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><strong>${run.run_name}</strong><div class="run-meta">${fmtDate(run.created_at)}</div></td>
      <td><span class="badge badge-success">${run.status}</span></td>
      <td>${fmtPct(run.summary?.pass_rate || 0)}</td>
      <td>${fmtPct(run.summary?.avg_faithfulness || 0)}</td>
      <td>${fmtPct(run.summary?.avg_answer_relevance || 0)}</td>
      <td>${fmtPct(run.summary?.avg_context_precision || 0)}</td>
      <td><button class="btn btn-ghost" data-run="${run.id}">View</button></td>
    `;
    body.appendChild(tr);
  });

  body.querySelectorAll("button[data-run]").forEach((btn) => {
    btn.addEventListener("click", () => openRunDetail(btn.dataset.run));
  });
}

async function openRunDetail(runId) {
  const run = await api(`/evaluations/${runId}`);
  $("#eval-detail").classList.remove("hidden");
  $("#eval-detail-title").textContent = `${run.run_name} · ${fmtPct(run.summary?.pass_rate || 0)} pass rate`;
  const container = $("#eval-detail-body");
  container.innerHTML = "";

  run.results.forEach((item) => {
    const card = document.createElement("article");
    card.className = "question-card";
    card.innerHTML = `
      <h4>${item.question}</h4>
      <p class="run-meta">${item.generated_answer}</p>
      <div class="q-grid">
        <div class="q-stat">Faithfulness<strong>${fmtPct(item.faithfulness)}</strong></div>
        <div class="q-stat">Relevance<strong>${fmtPct(item.answer_relevance)}</strong></div>
        <div class="q-stat">Precision<strong>${fmtPct(item.context_precision)}</strong></div>
        <div class="q-stat">Latency<strong>${item.latency_ms} ms</strong></div>
      </div>
    `;
    container.appendChild(card);
  });

  setActivePanel("evaluations");
}

function renderDatasets(datasets) {
  const grid = $("#datasets-grid");
  grid.innerHTML = "";
  datasets.forEach((ds) => {
    const card = document.createElement("article");
    card.className = "dataset-card";
    card.innerHTML = `
      <h3>${ds.name}</h3>
      <p>${ds.description || "Golden Q&A regression set"}</p>
      <div class="dataset-meta"><span>${ds.item_count} items</span><span>${fmtDate(ds.created_at)}</span></div>
    `;
    grid.appendChild(card);
  });

  const select = $("#dataset-select");
  select.innerHTML = "";
  datasets.forEach((ds) => {
    const opt = document.createElement("option");
    opt.value = ds.id;
    opt.textContent = ds.name;
    select.appendChild(opt);
  });
}

function renderTraces(traces) {
  const body = $("#trace-table-body");
  body.innerHTML = "";
  traces.forEach((trace) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${fmtDate(trace.created_at)}</td>
      <td>${trace.service}</td>
      <td>${trace.operation}</td>
      <td>${trace.model}</td>
      <td>${trace.latency_ms} ms</td>
      <td>${trace.prompt_tokens + trace.completion_tokens}</td>
      <td><span class="badge badge-success">${trace.status}</span></td>
    `;
    body.appendChild(tr);
  });
}

async function refresh() {
  const [overview, evaluations, datasets, traces] = await Promise.all([
    api("/metrics/overview"),
    api("/evaluations"),
    api("/datasets"),
    api("/traces?limit=25"),
  ]);

  state.datasets = datasets;
  state.evaluations = evaluations;

  const latestRun = evaluations[0] || null;
  renderOverview(overview, latestRun);
  renderEvaluations(evaluations);
  renderDatasets(datasets);
  renderTraces(traces);
}

async function runEvaluation() {
  const datasetId = $("#dataset-select").value;
  if (!datasetId) {
    showToast("No dataset available");
    return;
  }

  $("#run-eval-btn").disabled = true;
  try {
    await api("/evaluations/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        dataset_id: datasetId,
        run_name: `ui-run-${new Date().toISOString().slice(11, 19).replace(/:/g, "")}`,
        use_llm_judge: false,
      }),
    });
    showToast("Evaluation completed");
    await refresh();
    setActivePanel("evaluations");
  } catch (err) {
    showToast("Evaluation failed");
  } finally {
    $("#run-eval-btn").disabled = false;
  }
}

function bindEvents() {
  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.addEventListener("click", () => setActivePanel(btn.dataset.panel));
  });
  $("#run-eval-btn").addEventListener("click", runEvaluation);
  $("#close-detail").addEventListener("click", () => $("#eval-detail").classList.add("hidden"));
}

async function init() {
  bindEvents();
  try {
    await api("/health");
    await refresh();
  } catch {
    $("#system-status").textContent = "System offline";
    showToast("Unable to reach API");
  }
}

init();
