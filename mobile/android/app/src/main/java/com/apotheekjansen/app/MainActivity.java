package com.apotheekjansen.app;

import android.graphics.Color;
import android.os.Bundle;
import android.view.View;
import android.view.Window;
import androidx.core.view.WindowCompat;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        Window window = getWindow();
        
        // 1. Schakel Edge-to-Edge in: dit vertelt Android dat de app 
        // achter de statusbalk en navigatiebalk mag tekenen.
        WindowCompat.setDecorFitsSystemWindows(window, false);

        // 2. Maak de systeem-balken transparant zodat je webview-content zichtbaar is.
        window.setStatusBarColor(Color.TRANSPARENT);
        window.setNavigationBarColor(Color.TRANSPARENT);

        // 3. Zorg dat de WebView de volledige ruimte inneemt zonder native padding,
        // maar stuur de insets door zodat CSS env(safe-area-inset-top) werkt.
        View decorView = window.getDecorView();
        decorView.setOnApplyWindowInsetsListener((v, insets) -> {
            v.setPadding(0, 0, 0, 0);
            return insets; 
        });
    }
}