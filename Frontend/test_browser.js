import { chromium } from 'playwright-core';

async function main() {
  console.log("Launching browser...");
  let browser;
  try {
    browser = await chromium.launch({
      headless: true,
      channel: 'chrome'
    });
  } catch (err) {
    console.log("Failed to launch system Chrome, trying default chromium launch:", err.message);
    try {
      browser = await chromium.launch({ headless: true });
    } catch (err2) {
      console.error("Failed to launch any browser:", err2.message);
      process.exit(1);
    }
  }

  const page = await browser.newPage();
  
  page.on('console', msg => {
    console.log(`[BROWSER CONSOLE] ${msg.type().toUpperCase()}: ${msg.text()}`);
  });

  page.on('pageerror', err => {
    console.error(`[BROWSER ERROR] ${err.message}`);
    console.error(err.stack);
  });

  try {
    console.log("Navigating to http://localhost:5173/login ...");
    await page.goto('http://localhost:5173/login', { timeout: 15000, waitUntil: 'domcontentloaded' });
    console.log("Page loaded. Waiting for form elements...");
    
    // Fill in credentials
    await page.fill('input[type="email"]', 'patient@healthai.test');
    await page.fill('input[type="password"]', 'Password123!');
    console.log("Credentials entered. Clicking login...");
    
    // Submit form and wait for navigation
    await Promise.all([
      page.waitForNavigation({ waitUntil: 'load', timeout: 15000 }),
      page.click('button[type="submit"]')
    ]);
    
    console.log(`Navigated to: ${page.url()}`);
    console.log("Waiting 5 seconds for dashboard to load and render...");
    await page.waitForTimeout(5000);
    
    const html = await page.content();
    console.log(`Dashboard body HTML length: ${html.length}`);
    
  } catch (err) {
    console.error("Test flow failed:", err.message);
  } finally {
    await browser.close();
  }
}

main();
