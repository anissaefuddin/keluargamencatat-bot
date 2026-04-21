// Keluarga Mencatat — Monthly Summary (Small 2x2)
const API_URL = "https://script.google.com/macros/s/YOUR_DEPLOYMENT_ID/exec";

// --- helpers ------------------------------------------------------------

function formatRupiah(n) {
  const s = Math.round(Number(n) || 0).toString();
  return "Rp" + s.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

function shortNumber(n) {
  n = Number(n) || 0;
  if (n >= 1_000_000_000) {
    const v = n / 1_000_000_000;
    return (v % 1 === 0 ? v.toFixed(0) : v.toFixed(1)) + "M";
  }
  if (n >= 1_000_000) {
    const v = n / 1_000_000;
    return (v % 1 === 0 ? v.toFixed(0) : v.toFixed(1)) + "jt";
  }
  if (n >= 1000) return Math.round(n / 1000) + "k";
  return n.toString();
}

async function fetchSummary() {
  const req = new Request(API_URL);
  req.timeoutInterval = 10;
  const data = await req.loadJSON();
  if (!data || typeof data.total !== "number") throw new Error("bad payload");
  return data;
}

// --- widget -------------------------------------------------------------

function buildWidget(data) {
  const w = new ListWidget();
  w.setPadding(12, 14, 12, 14);
  w.backgroundColor = Color.dynamic(new Color("#ffffff"), new Color("#1c1c1e"));

  const primary = Color.dynamic(Color.black(), Color.white());
  const secondary = Color.dynamic(new Color("#555"), new Color("#a0a0a0"));

  // Title
  const title = w.addText("📊 Bulan Ini");
  title.font = Font.mediumSystemFont(12);
  title.textColor = secondary;
  title.lineLimit = 1;

  w.addSpacer(6);

  // Total
  const total = w.addText("💸 " + formatRupiah(data.total));
  total.font = Font.boldSystemFont(18);
  total.textColor = primary;
  total.lineLimit = 1;
  total.minimumScaleFactor = 0.5;

  w.addSpacer();

  // Top 2 categories (desc)
  const top = Object.entries(data.kategori || {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, 2);

  if (top.length === 0) {
    const empty = w.addText("Belum ada kategori");
    empty.font = Font.regularSystemFont(11);
    empty.textColor = secondary;
    empty.lineLimit = 1;
  } else {
    for (const [name, amount] of top) {
      const row = w.addText(`${name}: ${shortNumber(amount)}`);
      row.font = Font.regularSystemFont(11);
      row.textColor = secondary;
      row.lineLimit = 1;
      row.minimumScaleFactor = 0.8;
    }
  }

  return w;
}

function buildErrorWidget() {
  const w = new ListWidget();
  w.setPadding(12, 14, 12, 14);
  w.backgroundColor = Color.dynamic(new Color("#ffffff"), new Color("#1c1c1e"));

  const title = w.addText("📊 Bulan Ini");
  title.font = Font.mediumSystemFont(12);
  title.textColor = Color.dynamic(new Color("#555"), new Color("#a0a0a0"));

  w.addSpacer();

  const err = w.addText("Data error");
  err.font = Font.semiboldSystemFont(16);
  err.textColor = Color.red();
  err.lineLimit = 1;

  w.addSpacer();
  return w;
}

// --- run ----------------------------------------------------------------

let widget;
try {
  const data = await fetchSummary();
  widget = buildWidget(data);
} catch (e) {
  widget = buildErrorWidget();
}

if (config.runsInWidget) {
  Script.setWidget(widget);
} else {
  widget.presentSmall();
}
Script.complete();
