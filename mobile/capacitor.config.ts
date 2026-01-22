import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.apotheekjansen.app',
  appName: 'Apo Jansen',
  webDir: 'www',
  server: {
    url: 'https://treasonably-noncerebral-samir.ngrok-free.dev',
    cleartext: false
  },
    plugins: {
    SystemBars: {
        insetsHandling: 'css', // injecteert --safe-area-inset-* in de WebView
    },
    StatusBar: {
        // mag blijven, maar overlays heeft geen effect op Android 15+
        overlaysWebView: true,
    }
    }
};

export default config;
