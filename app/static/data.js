/* Local CSV parsing and validated analysis payloads. No external dependencies. */
(function (global) {
  "use strict";
  function parseCSV(text) {
    text = text.replace(/^\uFEFF/, "");
    const rows = [];
    let row = [],
      cell = "",
      quoted = false,
      closed = false,
      recordPresent = false;
    for (let i = 0; i < text.length; i++) {
      const c = text[i];
      if (c !== "\n" && c !== "\r") recordPresent = true;
      if (quoted) {
        if (c === '"') {
          if (text[i + 1] === '"') {
            cell += '"';
            i++;
          } else {
            quoted = false;
            closed = true;
          }
        } else cell += c;
        continue;
      }
      if (c === '"') {
        if (cell.length || closed)
          throw Error("Unexpected quote. Quote the entire CSV field.");
        quoted = true;
        continue;
      }
      if (c === "," || c === "\n" || c === "\r") {
        row.push(cell);
        cell = "";
        closed = false;
        if (c !== ",") {
          if (c === "\r" && text[i + 1] === "\n") i++;
          if (recordPresent) rows.push(row);
          row = [];
          recordPresent = false;
        }
        continue;
      }
      if (closed && !/\s/.test(c))
        throw Error("Unexpected text after a quoted field.");
      if (!closed) cell += c;
    }
    if (quoted) throw Error("CSV contains an unclosed quoted field.");
    row.push(cell);
    if (recordPresent) rows.push(row);
    if (rows.length < 2)
      throw Error("CSV needs a header and at least one data row.");
    const headers = rows.shift().map((v) => v.trim());
    if (headers.some((v) => !v) || new Set(headers).size !== headers.length)
      throw Error("Column headers must be nonempty and unique.");
    if (headers.length > 100)
      throw Error(
        "Import at most 100 columns, then select at most 50 numeric features.",
      );
    if (rows.length > 100000) throw Error("Import at most 100,000 rows.");
    rows.forEach((r, i) => {
      if (r.length !== headers.length)
        throw Error(
          `CSV row ${i + 2} has ${r.length} fields; expected ${headers.length}.`,
        );
    });
    return { headers, rows };
  }
  function numericColumn(data, name) {
    const index = data.headers.indexOf(name);
    if (index < 0) throw Error("Select a column for each required field.");
    return data.rows.map((row, i) => {
      const text = row[index].trim();
      if (!text || !/^[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?$/.test(text))
        throw Error(
          `Row ${i + 2}, column “${name}”: enter a number; missing values are not silently removed.`,
        );
      const value = Number(text);
      if (!Number.isFinite(value) || Math.abs(value) > 1e100)
        throw Error(
          `Row ${i + 2}, column “${name}”: number must be finite and at most 1e100 in magnitude.`,
        );
      return value;
    });
  }
  function payload(kind, data, map, parameters) {
    const out = { ...parameters };
    if (kind === "quantforge") {
      out.prices = numericColumn(data, map.prices);
      out.signals = numericColumn(data, map.signals);
      if (out.prices.some((v) => v <= 0))
        throw Error("Prices must all be positive.");
      if (out.signals.some((v) => Math.abs(v) > 1))
        throw Error("Exposure signals must be between −1 and 1.");
      if (out.prices.length < 4)
        throw Error("A backtest needs at least four price observations.");
    }
    if (kind === "causallab") {
      out.outcome = numericColumn(data, map.outcome);
      out.treatment = numericColumn(data, map.treatment);
      if (out.treatment.some((v) => v !== 0 && v !== 1))
        throw Error("Treatment must use 0 and 1 only.");
      if (
        out.treatment.filter((v) => v === 0).length < 3 ||
        out.treatment.filter((v) => v === 1).length < 3
      )
        throw Error(
          "Include at least three observations in each treatment group.",
        );
      out.confounders = matrix(data, map.confounders);
      if (out.outcome.length < 10)
        throw Error("Effect estimation needs at least ten observations.");
      if (
        map.confounders.includes(map.treatment) ||
        map.confounders.includes(map.outcome)
      )
        throw Error(
          "Treatment and outcome cannot also be selected as confounders.",
        );
    }
    if (kind === "neuralscope") {
      out.target = numericColumn(data, map.target);
      out.features = matrix(data, map.features);
      out.feature_names = map.features;
      if (map.features.includes(map.target))
        throw Error(
          "Remove the target column from features to avoid direct target leakage.",
        );
      if (out.target.length < 20)
        throw Error(
          "Training and evaluation need at least twenty observations.",
        );
    }
    if (kind === "timesense") {
      out.values = numericColumn(data, map.values);
      if (out.values.length < 10)
        throw Error("Forecast evaluation needs at least ten observations.");
      if (out.values.length - out.holdout < 5)
        throw Error(
          "Reduce holdout: at least five training observations must remain.",
        );
      if (
        out.method === "seasonal" &&
        out.values.length - out.holdout < 2 * out.season_length
      )
        throw Error(
          "Seasonal evaluation needs two complete training seasons. Reduce season length or holdout.",
        );
    }
    return out;
  }
  function matrix(data, names) {
    if (!names || !names.length)
      throw Error("Select at least one numeric input column.");
    if (names.length > 50) throw Error("Select at most 50 numeric columns.");
    const columns = names.map((n) => numericColumn(data, n));
    return data.rows.map((_, i) => columns.map((c) => c[i]));
  }
  const exported = { parseCSV, numericColumn, payload };
  if (typeof module !== "undefined" && module.exports)
    module.exports = exported;
  else global.LabData = exported;
})(typeof window === "undefined" ? globalThis : window);
