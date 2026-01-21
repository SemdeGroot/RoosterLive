import type { CapacitorConfig } from '@capacitor/cli';
import dotenv from 'dotenv';
import path from 'node:path';

dotenv.config({ path: path.resolve(__dirname, '../.env'), override: true });

const isDebug = String(process.env.DEBUG || '').toLowerCase() === 'true';

const DEV_URL = process.env.CAPACITOR_DEV_URL || 'https://app.apotheekjansen.com';
const PROD_URL = process.env.CAPACITOR_PROD_URL || 'https://app.apotheekjansen.com';
const TARGET_URL = isDebug ? DEV_URL : PROD_URL;

const config: CapacitorConfig = {
  appId: 'com.apotheekjansen.app',
  appName: 'Apotheek Jansen',
  webDir: 'www',
  bundledWebRuntime: false,
  server: {
    allowNavigation: [
      'app.apotheekjansen.com',
      '*.ngrok-free.dev',
      'localhost',
      '127.0.0.1',
    ],
  },
};

export default config;
