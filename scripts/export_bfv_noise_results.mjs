import fs from "node:fs/promises";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { SpreadsheetFile, Workbook } = require("@oai/artifact-tool");

const [csvPath, outputPath] = process.argv.slice(2);

if (!csvPath || !outputPath) {
  throw new Error("usage: export_bfv_noise_results.mjs input.csv output.xlsx");
}

const csvText = await fs.readFile(csvPath, "utf8");
const rows = csvText.trim().split(/\r?\n/).filter(Boolean).map((line) => line.split(","));
if (rows.length < 2) {
  throw new Error("CSV must contain a header and at least one result row");
}

const headers = rows[0];
const percentIndex = headers.indexOf("difference_percent_of_initial_budget");
const numericHeaders = new Set(headers.filter((header) => header !== "benchmark"));
const values = rows.slice(1).map((row) => row.map((value, index) => {
  if (!numericHeaders.has(headers[index])) {
    return value;
  }
  const number = Number(value);
  if (!Number.isFinite(number)) {
    throw new Error(`invalid numeric CSV value: ${value}`);
  }
  return index === percentIndex ? number / 100 : number;
}));

const workbook = Workbook.create();
const sheet = workbook.worksheets.add("Results");
sheet.showGridLines = false;
sheet.getRange("A1:K1").merge();
sheet.getRange("A1").values = [["BFV Noise Bound Benchmark Results"]];
sheet.getRange("A1").format = {
  font: { name: "Arial", size: 14, bold: true, color: "#1F2937" },
  horizontalAlignment: "left",
  verticalAlignment: "center"
};
sheet.getRange("A1:K1").format.rowHeight = 24;
sheet.getRange("A3").write([headers, ...values]);
const tableEndRow = values.length + 3;
const table = sheet.tables.add(`A3:K${tableEndRow}`, true, "BFVNoiseResults");
table.style = "TableStyleMedium2";
sheet.getRange(`A4:A${tableEndRow}`).format.font = { name: "Arial", size: 10 };
sheet.getRange(`B4:K${tableEndRow}`).format = {
  font: { name: "Arial", size: 10 },
  horizontalAlignment: "right",
  verticalAlignment: "center"
};
sheet.getRange("A3:K3").format = {
  fill: "#1F4E78",
  font: { name: "Arial", size: 9, bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true
};
sheet.getRange(`B4:I${tableEndRow}`).format.numberFormat = "#,##0";
sheet.getRange(`J4:J${tableEndRow}`).format.numberFormat = "0.00E+00";
if (percentIndex >= 0) {
  const percentColumn = String.fromCharCode("A".charCodeAt(0) + percentIndex);
  sheet.getRange(`${percentColumn}4:${percentColumn}${tableEndRow}`).format.numberFormat = "0.0%";
}
sheet.getRange(`A4:K${tableEndRow}`).format.borders = { preset: "inside", style: "thin", color: "#D9E2F3" };
sheet.getRange("A:A").format.columnWidth = 26;
sheet.getRange("B:D").format.columnWidth = 14;
sheet.getRange("E:H").format.columnWidth = 19;
sheet.getRange("I:I").format.columnWidth = 22;
sheet.getRange("J:J").format.columnWidth = 18;
sheet.getRange("K:K").format.columnWidth = 16;
sheet.getRange("A3:K3").format.rowHeight = 54;
sheet.freezePanes.freezeRows(3);
workbook.recalculate();
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
