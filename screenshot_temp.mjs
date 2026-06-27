const puppeteer = require("puppeteer");
(async () => {
  const browser = await puppeteer.launch({ args: ["--no-sandbox", "--disable-setuid-sandbox"] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });
  await page.goto("file:///C:/Users/ghhoc/Projects/AltusFlow/index.html", { waitUntil: "domcontentloaded", timeout: 15000 });
  await new Promise(r => setTimeout(r, 2000));
  await page.screenshot({ path: "C:/Users/ghhoc/Projects/AltusFlow/landing_full3.png", fullPage: true });
  await browser.close();
  console.log("done");
})().catch(e => { console.error(e.message); process.exit(1); });
