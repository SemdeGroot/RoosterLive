package com.apotheekjansen.app;

import android.os.Bundle; // Belangrijk: voeg deze import toe
import androidx.core.view.WindowCompat; // Belangrijk: voeg deze import toe
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        
        // Dit forceert de webview om 'edge-to-edge' te gaan
        WindowCompat.setDecorFitsSystemWindows(getWindow(), false);
    }
}