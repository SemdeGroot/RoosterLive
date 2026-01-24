import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.apotheekjansen.app',
  appName: 'Apo Jansen',
  webDir: 'www',
  // Zet de containerkleur op een donkere kleur zodat er geen witte flits is
  backgroundColor: '#0d131b', 
  server: {
    url: 'https://treasonably-noncerebral-samir.ngrok-free.dev',
    cleartext: false
  },
  plugins: {
    StatusBar: {
      overlaysWebView: true, // Cruciaal voor Android
    }
  }
};

export default config;