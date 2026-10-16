"use strict";
const cfg = window.APP_CONFIG;
let data = null,
  lastInput = null,
  lastResult = null,
  analysisSnapshot = null,
  revision = 0;
const $ = (id) => document.getElementById(id);
function element(tag, text) {
  const e = document.createElement(tag);
  if (text !== undefined) e.textContent = text;
  return e;
}
function status(message, error = false) {
  $("status").textContent = message;
  $("status").classList.toggle("error", error);
}
function table(target, headers, rows) {
  target.replaceChildren();
  const t = element("table"),
    head = element("thead"),
    hr = element("tr");
  headers.forEach((h) => hr.append(element("th", h)));
  head.append(hr);
  t.append(head);
  const body = element("tbody");
  rows.forEach((r) => {
    const tr = element("tr");
    r.forEach((v) => tr.append(element("td", v === null ? "Not defined" : v)));
    body.append(tr);
  });
  t.append(body);
  target.append(t);
}
function invalidate() {
  revision++;
  lastInput = null;
  lastResult = null;
  analysisSnapshot = null;
  $("results").hidden = true;
  $("export-result").disabled = true;
  $("export-config").disabled = true;
}
function loadCSV(text, label) {
  invalidate();
  try {
    data = LabData.parseCSV(text);
    $("results").hidden = true;
    lastInput = null;
    lastResult = null;
    $("export-result").disabled = true;
    $("export-config").disabled = true;
    $("source-label").textContent = label;
    table(
      $("preview"),
      ["Row", ...data.headers],
      data.rows.slice(0, 8).map((row, i) => [i + 1, ...row])
    );
    $("preview-note").textContent =
      `${data.rows.length} rows × ${data.headers.length} columns. Preview shows first eight. Row order is preserved.`;
    buildMappings();
    status("Map columns, check settings, then run analysis.");
  } catch (error) {
    data = null;
    status(error.message, true);
  }
}
function buildMappings() {
  $("mapping").replaceChildren();
  cfg.mapping.forEach(([key, label]) => {
    const l = element("label", label),
      select = element("select");
    select.id = "map-" + key;
    data.headers.forEach((h) => {
      const option = element("option", h);
      option.value = h;
      select.append(option);
    });
    if (data.headers.includes(key)) select.value = key;
    else if (key === "outcome" || key === "target") select.selectedIndex = 0;
    else if (key === "treatment" || key === "signals")
      select.selectedIndex = Math.min(1, data.headers.length - 1);
    l.htmlFor = select.id;
    $("mapping").append(l, select);
  });
  if (cfg.multi) {
    const [key, label] = cfg.multi;
    $("mapping").append(element("h3", label));
    const choices = element("div");
    choices.className = "choices";
    data.headers.forEach((h) => {
      const l = element("label"),
        input = element("input");
      input.type = "checkbox";
      input.name = key;
      input.value = h;
      input.checked = !cfg.mapping.some(([k]) => $("map-" + k).value === h);
      l.append(input, element("span", h));
      choices.append(l);
    });
    $("mapping").append(choices);
  }
}
function parameters() {
  const values = {};
  cfg.params.forEach(([key]) => {
    const input = $("param-" + key);
    if (!input.checkValidity())
      throw Error(
        `Check ${input.labels[0].textContent}: use a value between ${input.min} and ${input.max}.`
      );
    values[key] = Number(input.value);
  });
  if (cfg.method) values.method = $("param-method").value;
  return values;
}
function mapping() {
  const map = {};
  cfg.mapping.forEach(([key]) => (map[key] = $("map-" + key).value));
  if (cfg.multi)
    map[cfg.multi[0]] = Array.from(
      document.querySelectorAll(`input[name="${cfg.multi[0]}"]:checked`)
    ).map((i) => i.value);
  return map;
}
function format(v, digits = 4) {
  return v === null
    ? "Not defined"
    : typeof v === "number"
      ? Number(v.toFixed(digits)).toLocaleString()
      : String(v);
}
function percent(v) {
  return format(v * 100, 2) + "%";
}
function metrics(items) {
  $("metrics").replaceChildren();
  items.forEach(([label, value]) => {
    const box = element("div");
    box.className = "metric";
    box.append(element("strong", value), element("span", label));
    $("metrics").append(box);
  });
}
function plot(title, series, labels = []) {
  $("chart-title").textContent = title;
  const canvas = $("chart"),
    w = 900,
    h = 300;
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, w, h);
  const colors = ["#177866", "#447bb8", "#d86a41"];
  let values = series.flatMap((s) => s.values).filter(Number.isFinite);
  if (!values.length) return;
  let low = Math.min(...values),
    high = Math.max(...values);
  if (low === high) {
    low -= 1;
    high += 1;
  }
  const padding = (high - low) * 0.08;
  low -= padding;
  high += padding;
  ctx.font = "12px system-ui";
  ctx.fillStyle = "#526b7d";
  ctx.strokeStyle = "#dce5eb";
  for (let i = 0; i < 5; i++) {
    const y = 25 + i * 52;
    ctx.beginPath();
    ctx.moveTo(85, y);
    ctx.lineTo(870, y);
    ctx.stroke();
    ctx.fillText(format(high - ((high - low) * i) / 4, 2), 8, y + 4);
  }
  const count = Math.max(...series.map((s) => s.values.length));
  const point = (index, value) => [
    85 + (index / Math.max(1, count - 1)) * 785,
    25 + ((high - value) / (high - low)) * 208
  ];
  series.forEach((s, j) => {
    ctx.strokeStyle = colors[j % 3];
    ctx.lineWidth = 2;
    ctx.beginPath();
    s.values.forEach((v, i) => {
      const [x, y] = point(i, v);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
    ctx.fillStyle = colors[j % 3];
    ctx.fillText(s.name, 85 + j * 220, 286);
  });
  ctx.fillStyle = "#526b7d";
  ctx.fillText(labels[0] || "First observation", 85, 255);
  ctx.textAlign = "right";
  ctx.fillText(labels[1] || "Last observation", 870, 255);
  ctx.textAlign = "left";
  canvas.setAttribute(
    "aria-label",
    title +
      ". " +
      series.map((s) => s.name).join(", ") +
      ". Exact values are in the results table and exported report."
  );
}
function bars(title, rows) {
  $("chart-title").textContent = title;
  const canvas = $("chart");
  canvas.width = 900;
  canvas.height = 300;
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, 900, 300);
  const shown = rows.slice(0, 8);
  const max = Math.max(1e-12, ...shown.map((r) => Math.abs(r[1])));
  ctx.font = "13px system-ui";
  shown.forEach(([label, value], i) => {
    const y = 15 + i * 33;
    ctx.fillStyle = "#27485d";
    ctx.fillText(label.slice(0, 20), 8, y + 18);
    ctx.fillStyle = value >= 0 ? "#167665" : "#d86a41";
    ctx.fillRect(210, y, (Math.abs(value) / max) * 520, 22);
    ctx.fillStyle = "#27485d";
    ctx.fillText(format(value), 750, y + 18);
  });
  canvas.setAttribute(
    "aria-label",
    title + ". Exact values are in the table below."
  );
}
function render(result, input) {
  $("results").hidden = false;
  $("raw").textContent = JSON.stringify(result, null, 2);
  $("assumptions").textContent = result.assumptions || result.limitations;
  let headers, rows, interpretation;
  if (cfg.slug === "quantforge") {
    metrics([
      ["Total net return", percent(result.total_return)],
      ["Maximum drawdown", percent(result.max_drawdown)],
      ["Sharpe", format(result.sharpe)],
      ["Position turnover", format(result.turnover)]
    ]);
    plot("Compounded strategy equity", [
      { name: "Net equity (starts at 1)", values: result.equity }
    ]);
    headers = ["Period", "Lagged exposure", "Net return", "Equity"];
    rows = result.net_returns.map((r, i) => [
      i + 1,
      format(result.positions[i]),
      percent(r),
      format(result.equity[i + 1])
    ]);
    interpretation = `The supplied rule ${result.total_return >= 0 ? "gained" : "lost"} ${percent(Math.abs(result.total_return))} after stated turnover costs. The largest decline from a previous equity peak was ${percent(result.max_drawdown)}. Compare against an appropriate benchmark before drawing an investment conclusion. Costs summed across periods: ${percent(result.total_cost_fraction)} of period capital; this is not a compounded return deduction.`;
  }
  if (cfg.slug === "causallab") {
    metrics([
      ["Adjusted treatment coefficient", format(result.treatment_effect)],
      ["HC1 standard error", format(result.robust_standard_error)],
      ["Poor overlap observations", percent(result.poor_overlap_fraction)]
    ]);
    bars("Treatment coefficient and approximate interval", [
      ["Lower interval", result.approximate_95_percent_interval[0]],
      ["Coefficient", result.treatment_effect],
      ["Upper interval", result.approximate_95_percent_interval[1]]
    ]);
    headers = ["Diagnostic", "Value"];
    rows = [
      [
        "Approximate 95% interval",
        result.approximate_95_percent_interval
          .map((v) => format(v))
          .join(" to ")
      ],
      ["Propensity min", format(result.propensity_range[0])],
      ["Propensity max", format(result.propensity_range[1])],
      [
        "Overlap warning",
        result.warnings.join("; ") ||
          "No threshold warning (does not prove positivity)"
      ]
    ];
    interpretation = `The additive outcome model estimates a treatment coefficient of ${format(result.treatment_effect)} in outcome units, after adjustment for selected columns. The approximate interval ${result.approximate_95_percent_interval[0] <= 0 && result.approximate_95_percent_interval[1] >= 0 ? "includes" : "excludes"} zero. ${result.warnings.length ? result.warnings.join(". ") : "Observed propensity scores do not trigger the configured extreme-score warning."} This is an observational model result, not proof of a causal effect.`;
  }
  if (cfg.slug === "neuralscope") {
    metrics([
      ["Held-out MSE", format(result.held_out_mse)],
      ["Held-out R²", format(result.held_out_r2)],
      ["Training rows", result.train_rows],
      ["Held-out rows", result.test_rows]
    ]);
    bars(
      "Held-out permutation importance (MSE increase)",
      result.importance.map((r) => [r.feature, r.mse_increase])
    );
    headers = [
      "Feature",
      "MSE increase",
      "Repeat spread (SD)",
      "Linear coefficient"
    ];
    rows = result.importance.map((r) => [
      r.feature,
      format(r.mse_increase),
      format(r.std),
      format(r.coefficient)
    ]);
    const first = result.importance[0];
    interpretation = `${first.feature} has the largest mean held-out permutation MSE increase (${format(first.mse_increase)}). Positive importance means shuffling degraded this model’s predictions; near-zero or negative values can reflect weak signal, redundancy, or sampling noise. Coefficients describe this local linear fit. R² ${result.held_out_r2 === null ? "is undefined for a constant held-out target" : format(result.held_out_r2) + " can be negative when prediction is worse than the held-out target mean"}.`;
  }
  if (cfg.slug === "timesense") {
    metrics([
      ["Holdout MAE", format(result.mae)],
      ["Holdout RMSE", format(result.rmse)],
      ["Flagged holdout values", result.anomalies.length],
      ["Training residual scale", format(result.training_residual_scale)]
    ]);
    plot("Holdout: unseen actual values versus fixed-origin forecast", [
      { name: "Holdout actual", values: result.holdout_actual },
      { name: "Holdout forecast", values: result.holdout_prediction }
    ]);
    headers = ["Holdout row", "Actual", "Forecast", "Residual", "Flag"];
    const offset = input.values.length - input.holdout;
    rows = result.holdout_actual.map((v, i) => [
      offset + i + 1,
      format(v),
      format(result.holdout_prediction[i]),
      format(v - result.holdout_prediction[i]),
      result.anomalies.some((a) => a.index === offset + i) ? "Inspect" : "—"
    ]);
    rows.push(
      ...result.future_forecast.map((v, i) => [
        "Future " + (i + 1),
        "Unavailable",
        format(v),
        "Unavailable",
        "Not evaluated"
      ])
    );
    interpretation = `${input.method} produced an average absolute holdout error of ${format(result.mae)} value units. ${result.anomalies.length} holdout residuals exceed the training-calibrated threshold. Inspect flagged rows for data issues or regime changes; long-horizon uncertainty can also create flags. Future values are projections from all supplied observations and have not been evaluated.`;
  }
  $("interpretation").textContent = interpretation;
  table($("result-table"), headers, rows.slice(0, 300));
  $("table-note").textContent =
    rows.length > 300
      ? `Showing first 300 of ${rows.length} rows. Export the full JSON report for all values.`
      : "All table rows shown.";
  $("export-result").disabled = false;
  $("export-config").disabled = false;
}
function download(name, value, type = "application/json") {
  const blob = new Blob(
    [typeof value === "string" ? value : JSON.stringify(value, null, 2)],
    { type }
  );
  const url = URL.createObjectURL(blob),
    link = element("a");
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
$("load-example").onclick = () =>
  loadCSV(cfg.sample, "Synthetic demonstration dataset");
$("sample-csv").onclick = () =>
  download(cfg.slug + "-synthetic.csv", cfg.sample, "text/csv;charset=utf-8");
$("csv-file").onchange = async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  invalidate();
  data = null;
  if (file.size > 2097152) {
    invalidate();
    data = null;
    status("CSV exceeds 2 MiB. Import a smaller subset.", true);
    return;
  }
  const importRevision = revision;
  try {
    const text = await file.text();
    if (importRevision !== revision) return;
    loadCSV(text, "Imported file: " + file.name + " (provenance not verified)");
  } catch (error) {
    if (importRevision === revision)
      status("Could not read CSV: " + error.message, true);
  }
};
$("run").onclick = async () => {
  const button = $("run");
  try {
    if (!data) throw Error("Load the synthetic example or import a CSV first.");
    invalidate();
    const selected = mapping(),
      settings = parameters(),
      requestRevision = revision;
    const input = LabData.payload(cfg.slug, data, selected, settings);
    if (new TextEncoder().encode(JSON.stringify(input)).length > 2097152)
      throw Error(
        "Analysis request exceeds 2 MiB. Reduce rows or selected columns."
      );
    button.disabled = true;
    status("Running local analysis…");
    const response = await fetch("/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input)
    });
    const result = await response.json();
    if (requestRevision !== revision)
      throw Error(
        "Inputs changed during analysis. Run again with the current settings."
      );
    if (!response.ok) {
      const detail = Array.isArray(result.detail)
        ? result.detail
            .map((d) => d.loc.slice(1).join(".") + ": " + d.msg)
            .join("\n")
        : result.detail;
      throw Error(detail || "Analysis failed. Check the input.");
    }
    lastInput = input;
    lastResult = result;
    analysisSnapshot = { columns: selected, parameters: settings };
    render(result, input);
    status(
      "Analysis finished. Review method assumptions before interpreting these results."
    );
    $("results").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    $("results").hidden = true;
    lastResult = null;
    $("export-result").disabled = true;
    status(error.message, true);
  } finally {
    button.disabled = false;
  }
};
$("export-result").onclick = () => {
  if (lastResult)
    download(cfg.slug + "-report.json", {
      application: cfg.title,
      version: "0.2.0",
      data_source: $("source-label").textContent,
      created_at: new Date().toISOString(),
      configuration: analysisSnapshot,
      result: lastResult
    });
};
$("export-config").onclick = () => {
  if (lastInput) download(cfg.slug + "-analysis-input.json", lastInput);
};
document.querySelectorAll("#mapping,.fields").forEach((container) =>
  container.addEventListener("input", () => {
    invalidate();
    status("Settings changed. Run analysis again to refresh results.");
  })
);
loadCSV(cfg.sample, "Synthetic demonstration dataset");
