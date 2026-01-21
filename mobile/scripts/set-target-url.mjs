import fs from 'node:fs';
import 'dotenv/config';

const isDebug = String(process.env.DJANGO_DEBUG || '').toLowerCase() === 'true';
const DEV_URL = process.env.CAPACITOR_DEV_URL || 'https://app.apotheekjansen.com';
const PROD_URL = process.env.CAPACITOR_PROD_URL || 'https://app.apotheekjansen.com';
const TARGET_URL = isDebug ? DEV_URL : PROD_URL;

const indexPath = new URL('../www/index.html', import.meta.url);
let html = fs.readFileSync(indexPath, 'utf8');

// Injecteer/refresh een window var bovenaan de redirect
const marker = '<head>';
if (!html.includes(marker)) {
  throw new Error('index.html mist <head>');
}

const injection = `<head>
    <script>window.__TARGET_URL__ = ${JSON.stringify(TARGET_URL)};</script>`;

html = html.replace(marker, injection);

fs.writeFileSync(indexPath, html, 'utf8');
console.log(`[mobile] TARGET_URL set to: ${TARGET_URL}`);
