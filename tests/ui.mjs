import { chromium } from "playwright";
import assert from "node:assert/strict";
import { readFile, mkdir } from "node:fs/promises";
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1050 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
page.on("dialog", (d) => d.accept());
async function text(id, expected) {
  await page.waitForFunction(
    ([id, value]) => document.getElementById(id).textContent.trim() === value,
    [id, expected],
  );
}
async function download(selector) {
  const pending = page.waitForEvent("download");
  await page.click(selector);
  const d = await pending;
  return readFile(await d.path(), "utf8");
}
try {
  await page.goto(process.env.BASE_URL || "http://127.0.0.1:7421");
  await text("placed", "11");
  await page.fill("#stock-count", "3");
  await page.locator("#stock-count").blur();
  await page.click("#plan");
  await text("placed", "11");
  await page.locator('#drawing [role="button"]').first().focus();
  await page.keyboard.press("Enter");
  await page.fill("#x", "9999");
  await page.click("#move");
  await page.locator("#error:not([hidden])").waitFor();
  assert.match(await page.textContent("#error"), /outside|bounds|fit|beyond/i);
  await page.fill("#x", "0");
  await page.fill("#y", "0");
  await page.selectOption("#piece-sheet", "2");
  await page.click("#move");
  await page.waitForFunction(() => !document.getElementById("undo").disabled);
  await page.click("#undo");
  await page.click("#redo");
  const exported = JSON.parse(await download("#export-json"));
  assert.equal(exported.layout.placements.length, 11);
  assert(exported.layout.placements.some((p) => p.sheet === 2));
  assert.match(await download("#export-svg"), /<svg/);
  await page.click("#save");
  await text("revision", "Saved revision 1");
  await page.waitForFunction(() => !document.getElementById("save").disabled);
  const key = await page.inputValue("#library");
  assert(key);
  await page.reload();
  await text("placed", "11");
  await page.selectOption("#library", key);
  await page.click("#open");
  await text("revision", "Saved revision 1");
  assert.equal(
    JSON.parse(await download("#export-json")).layout.placements.filter(
      (p) => p.sheet === 2,
    ).length,
    exported.layout.placements.filter((p) => p.sheet === 2).length,
  );

  const stale = await page.evaluate(
    async ({ key, app }) => {
      const r = await (await fetch("/api/projects/" + key)).json();
      const payload = { id: r.id, revision: 0, document: r.document };
      if (r.layout) payload.layout = r.layout;
      return (
        await fetch("/api/save", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Requested-With": app,
          },
          body: JSON.stringify(payload),
        })
      ).status;
    },
    { key, app: "SheetNest" },
  );
  assert.equal(stale, 409, "Stale writes must be rejected");
  const blocked = await page.evaluate(
    async () =>
      (
        await fetch("/api/save", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: "{}",
        })
      ).status,
  );
  assert.equal(blocked, 403, "Mutations require the workspace header");
  await page.setInputFiles("#import", "examples/sample.json");
  await page.waitForFunction(() =>
    document.getElementById("revision").textContent.includes("Imported"),
  );
  await page.waitForFunction(() => !document.getElementById("save").disabled);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(200);
  assert(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
    "Page must fit a narrow viewport",
  );
  if (process.env.UI_SCREENSHOTS) {
    await mkdir(process.env.UI_SCREENSHOTS, { recursive: true });
    await page.screenshot({
      path: process.env.UI_SCREENSHOTS + "/mobile.png",
      fullPage: true,
    });
    await page.setViewportSize({ width: 1440, height: 1050 });
    await page.screenshot({
      path: process.env.UI_SCREENSHOTS + "/desktop.png",
      fullPage: true,
    });
  }
  assert.deepEqual(errors, []);
  console.log(
    "Browser workflows, persistence, exports and responsive layout passed",
  );
} finally {
  await browser.close();
}
