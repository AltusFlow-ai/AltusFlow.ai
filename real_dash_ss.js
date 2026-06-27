const puppeteer = require("puppeteer");
(async () => {
  const browser = await puppeteer.launch({ args: ["--no-sandbox", "--disable-setuid-sandbox"] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });
  await page.goto("file:///C:/Users/ghhoc/Projects/AltusFlow/outbound-hunter/dashboard/index.html", { waitUntil: "load", timeout: 30000 });
  await new Promise(r => setTimeout(r, 3000));
  await page.screenshot({ path: "C:/Users/ghhoc/Projects/AltusFlow/real_dash.png", fullPage: false });
  await browser.close();
  console.log("done");
})().catch(e => { console.error(e.message); process.exit(1); });
