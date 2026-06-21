import { chromium } from 'playwright-core';

const users = [
  { role: 'patient', email: 'patient@healthai.test', pass: 'Password123!' },
  { role: 'doctor', email: 'alice.smith@hospital.com', pass: 'Password123!' },
  { role: 'admin', email: 'admin@healthai.test', pass: 'Password123!' }
];

async function runTest(user) {
  console.log(`\n========================================`);
  console.log(`Testing dashboard for role: ${user.role.toUpperCase()} (${user.email})`);
  console.log(`========================================`);
  
  let browser;
  try {
    browser = await chromium.launch({
      headless: true,
      channel: 'chrome'
    });
  } catch (err) {
    try {
      browser = await chromium.launch({ headless: true });
    } catch (err2) {
      console.error("Failed to launch any browser:", err2.message);
      return false;
    }
  }

  const page = await browser.newPage();
  let errors = [];
  
  page.on('console', msg => {
    if (msg.type() === 'error') {
      console.log(`[BROWSER CONSOLE ERROR]: ${msg.text()}`);
      errors.push(msg.text());
    } else {
      console.log(`[BROWSER CONSOLE ${msg.type().toUpperCase()}]: ${msg.text()}`);
    }
  });

  page.on('pageerror', err => {
    console.error(`[BROWSER UNCAUGHT EXCEPTION]: ${err.message}`);
    console.error(err.stack);
    errors.push(err.message);
  });

  try {
    await page.goto('http://localhost:5173/login', { timeout: 15000, waitUntil: 'domcontentloaded' });
    await page.fill('input[type="email"]', user.email);
    await page.fill('input[type="password"]', user.pass);
    
    await Promise.all([
      page.waitForNavigation({ waitUntil: 'load', timeout: 15000 }),
      page.click('button[type="submit"]')
    ]);
    
    console.log(`Logged in successfully. Current URL: ${page.url()}`);
    console.log("Waiting 5 seconds for dashboard elements to render...");
    await page.waitForTimeout(5000);
    
    const html = await page.content();
    console.log(`Rendered HTML length: ${html.length}`);
    
    if (errors.length > 0) {
      console.log(`FAIL: Found ${errors.length} error(s) during dashboard render.`);
      return false;
    } else {
      console.log(`SUCCESS: Dashboard for ${user.role} loaded with 0 exceptions/errors.`);
      return true;
    }
  } catch (err) {
    console.error(`Test execution failed for ${user.role}:`, err.message);
    return false;
  } finally {
    await browser.close();
  }
}

async function main() {
  let overallSuccess = true;
  for (const u of users) {
    const success = await runTest(u);
    if (!success) {
      overallSuccess = false;
    }
  }
  console.log(`\n========================================`);
  if (overallSuccess) {
    console.log("OVERALL RESULT: ALL DASHBOARDS RENDERED SUCCESSFUL!");
    process.exit(0);
  } else {
    console.log("OVERALL RESULT: SOME DASHBOARDS HAD RENDERING ERRORS!");
    process.exit(1);
  }
}

main();
