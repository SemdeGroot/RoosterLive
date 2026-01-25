package com.apotheekjansen.app;

import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.content.Context;
import android.graphics.Color;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.view.Window;

import androidx.core.view.WindowCompat;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {

    private void ensureNotificationChannels() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationManager nm = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);

            // High importance channel -> heads-up mogelijk
            NotificationChannel high = new NotificationChannel(
                    "GENERAL_HIGH",
                    "General notifications",
                    NotificationManager.IMPORTANCE_HIGH
            );
            high.enableVibration(true);
            high.setShowBadge(true);

            nm.createNotificationChannel(high);

            // (optioneel) low channel als je later stille meldingen wil
            NotificationChannel low = new NotificationChannel(
                    "GENERAL_LOW",
                    "Silent notifications",
                    NotificationManager.IMPORTANCE_LOW
            );
            nm.createNotificationChannel(low);
        }
    }

    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // Ensure channels early
        ensureNotificationChannels();

        Window window = getWindow();

        // 1) Edge-to-edge
        WindowCompat.setDecorFitsSystemWindows(window, false);

        // 2) Transparante system bars
        window.setStatusBarColor(Color.TRANSPARENT);
        window.setNavigationBarColor(Color.TRANSPARENT);

        // 3) WebView full bleed, insets doorgeven
        View decorView = window.getDecorView();
        decorView.setOnApplyWindowInsetsListener((v, insets) -> {
            v.setPadding(0, 0, 0, 0);
            return insets;
        });
    }
}
