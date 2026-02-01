// bot.js
const TelegramBot = require('node-telegram-bot-api');
const { spawn } = require('child_process');

const bot = new TelegramBot(process.env.BOT_TOKEN, { polling: true });
const OWNER_ID = Number(process.env.OWNER_ID);

bot.on('message', (msg) => {
  if (msg.chat.id !== OWNER_ID) return;
});

bot.onText(/\/run/, (msg) => {
  bot.sendMessage(msg.chat.id, '🚀 Send logins now.\nFormat:\nemail|password (one per line)');
});

bot.on('message', (msg) => {
  if (!msg.text || msg.text.startsWith('/')) return;
  if (msg.chat.id !== OWNER_ID) return;

  const logins = msg.text.trim();
  bot.sendMessage(msg.chat.id, '⏳ Checking logins…');

  const proc = spawn('node', ['runner.js'], {
    env: { ...process.env, LOGINS: logins }
  });

  proc.stdout.on('data', (d) => {
    bot.sendMessage(msg.chat.id, d.toString());
  });

  proc.on('close', () => {
    bot.sendMessage(msg.chat.id, '✅ Done');
  });
});