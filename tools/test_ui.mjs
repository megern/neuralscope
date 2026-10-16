import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { parseCSV, numericColumn, payload } = require("../app/static/data.js");
const context = { window: {} };
vm.runInNewContext(
  fs.readFileSync(new URL("../app/static/config.js", import.meta.url), "utf8"),
  context,
);
const cfg = context.window.APP_CONFIG;
let checks = 0;
test("quoted-empty single-column record preserved then rejected as missing numeric", () => {
  const data = parseCSV('values\n1\n""\n2');
  assert.deepEqual(data.rows, [["1"], [""], ["2"]]);
  assert.throws(() => numericColumn(data, "values"), /Row 3.*missing values/);
});
test("trailing quoted-empty record at EOF preserved", () => {
  const data = parseCSV('values\r\n1\r\n""');
  assert.deepEqual(data.rows, [["1"], [""]]);
  assert.throws(() => numericColumn(data, "values"), /Row 3/);
});
test("whitespace-only field is data, not a blank physical line", () => {
  const data = parseCSV("values\n1\n   \n2");
  assert.equal(data.rows.length, 3);
  assert.throws(() => numericColumn(data, "values"), /Row 3/);
});
test("truly empty physical lines ignored while delimiter-empty rows retained", () => {
  assert.deepEqual(parseCSV("values\n\n1\n\n2\n").rows, [["1"], ["2"]]);
  assert.deepEqual(parseCSV("a,b\n,\n1,2").rows, [
    ["", ""],
    ["1", "2"],
  ]);
});
function test(name, callback) {
  callback();
  checks++;
  console.log("PASS " + name);
}
test("quoted comma, multiline, escaped quote and CRLF", () => {
  const data = parseCSV('name,value\r\n"a,b",1\r\n"line\n""two""",2\r\n');
  assert.deepEqual(data.rows, [
    ["a,b", "1"],
    ['line\n"two"', "2"],
  ]);
});
test("BOM header parsed", () =>
  assert.deepEqual(parseCSV("\uFEFFa,b\n1,2").headers, ["a", "b"]));
test("duplicate headers rejected", () =>
  assert.throws(() => parseCSV("a,a\n1,2"), /unique/));
test("ragged row actionable", () =>
  assert.throws(() => parseCSV("a,b\n1"), /row 2/));
test("unclosed quoted field rejected", () =>
  assert.throws(() => parseCSV('a,b\n"1,2'), /unclosed/));
test("empty matrix row not silently dropped", () =>
  assert.equal(parseCSV("a,b\n,\n1,2").rows.length, 2));
test("blank physical lines ignored", () =>
  assert.equal(parseCSV("a,b\n\n1,2\n").rows.length, 1));
test("missing numeric value is an error", () =>
  assert.throws(() => numericColumn(parseCSV("a,b\n,2"), "a"), /Row 2/));
test("nonfinite and oversized numbers rejected", () => {
  for (const value of ["1e400", "1e101", "NaN", "Infinity", "0x10"])
    assert.throws(() => numericColumn(parseCSV("a\n" + value), "a"));
});
test("scientific notation and decimal values", () =>
  assert.deepEqual(
    numericColumn(parseCSV("a\n-1.2e2\n+.5"), "a"),
    [-120, 0.5],
  ));
test("hostile text remains plain CSV text", () => {
  assert.equal(
    parseCSV("name,value\n<img src=x onerror=alert(1)>,2").rows[0][0],
    "<img src=x onerror=alert(1)>",
  );
});
test("synthetic CSV produces actual API request", () => {
  const data = parseCSV(cfg.sample),
    map = {};
  cfg.mapping.forEach(
    ([key], i) =>
      (map[key] = data.headers.includes(key) ? key : data.headers[i]),
  );
  if (cfg.multi)
    map[cfg.multi[0]] = data.headers.filter(
      (h) => !Object.values(map).includes(h),
    );
  const params = {};
  cfg.params.forEach(([key, , value]) => (params[key] = value));
  if (cfg.method) params.method = "drift";
  const request = payload(cfg.slug, data, map, params);
  assert.equal(Object.keys(request).length > 0, true);
  const roundtrip = JSON.parse(JSON.stringify(request));
  assert.deepEqual(roundtrip, request);
  if (cfg.slug === "quantforge") {
    assert.equal(request.prices.length, 48);
    assert.throws(
      () => payload(cfg.slug, data, { ...map, signals: "missing" }, params),
      /Select a column/,
    );
  }
  if (cfg.slug === "causallab") {
    assert.equal(request.confounders[0].length, 2);
    assert.throws(
      () =>
        payload(
          cfg.slug,
          data,
          { ...map, confounders: [map.treatment] },
          params,
        ),
      /cannot also/,
    );
  }
  if (cfg.slug === "neuralscope") {
    assert.equal(request.features.length, 100);
    assert.throws(
      () => payload(cfg.slug, data, { ...map, features: [map.target] }, params),
      /leakage/,
    );
  }
  if (cfg.slug === "timesense") {
    assert.equal(request.values.length, 48);
    assert.throws(
      () => payload(cfg.slug, data, map, { ...params, holdout: 46 }),
      /five training/,
    );
  }
});
console.log(`${checks} frontend checks passed for ${cfg.title}`);
