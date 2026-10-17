/* Actual-versus-predicted plot of the bounded held-out diagnostic sample. */
(function (global) {
  "use strict";
  function draw(canvas, records) {
    canvas.width = 900;
    canvas.height = 330;
    const context = canvas.getContext("2d");
    context.clearRect(0, 0, 900, 330);
    const values = records.flatMap((row) => [row.actual, row.predicted]);
    let minimum = values.reduce((a, b) => Math.min(a, b), Infinity),
      maximum = values.reduce((a, b) => Math.max(a, b), -Infinity);
    if (
      !Number.isFinite(minimum) ||
      !Number.isFinite(maximum) ||
      !records.length
    )
      throw Error("Diagnostic plot needs finite observations.");
    if (minimum === maximum) {
      minimum -= 1;
      maximum += 1;
    }
    const margin = (maximum - minimum) * 0.1;
    minimum -= margin;
    maximum += margin;
    const x = (value) => 90 + ((value - minimum) / (maximum - minimum)) * 720;
    const y = (value) => 260 - ((value - minimum) / (maximum - minimum)) * 220;
    context.font = "13px system-ui";
    context.fillStyle = "#27485d";
    context.strokeStyle = "#adbdc8";
    context.lineWidth = 1;
    context.beginPath();
    context.moveTo(90, 40);
    context.lineTo(90, 260);
    context.lineTo(810, 260);
    context.stroke();
    context.setLineDash([5, 5]);
    context.beginPath();
    context.moveTo(x(minimum), y(minimum));
    context.lineTo(x(maximum), y(maximum));
    context.stroke();
    context.setLineDash([]);
    const points = records.map((row) => ({
      x: x(row.predicted),
      y: y(row.actual),
      row_index: row.row_index,
    }));
    context.fillStyle = "#167665";
    points.forEach((point) => {
      context.beginPath();
      context.arc(point.x, point.y, 3, 0, 2 * Math.PI);
      context.fill();
    });
    const format = (value) => Number(value.toPrecision(4)).toString();
    context.fillStyle = "#27485d";
    context.fillText(format(minimum), 90, 282);
    context.fillText(format(maximum), 770, 282);
    context.fillText(format(maximum), 5, 45);
    context.fillText(format(minimum), 5, 260);
    context.fillText("Actual", 5, 20);
    context.textAlign = "center";
    context.fillText("Predicted · dashed line is perfect agreement", 450, 315);
    context.textAlign = "left";
    canvas.setAttribute(
      "aria-label",
      `Actual versus predicted values for ${records.length} held-out diagnostic observations. Dashed line shows perfect agreement. Exact worst-case values and source row indices are in the following table.`,
    );
    return points;
  }
  const api = { draw };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else global.LabDiagnosticChart = api;
})(typeof window === "undefined" ? globalThis : window);
