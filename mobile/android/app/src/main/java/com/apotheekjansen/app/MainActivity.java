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
import androidx.core.view.WindowInsetsControllerCompat;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {

    private void ensureNotificationChannels() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationManager nm = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);

            NotificationChannel high = new NotificationChannel(
                    "GENERAL_HIGH",
                    "General notifications",
                    NotificationManager.IMPORTANCE_HIGH
            );
            high.enableVibration(true);
            high.setShowBadge(true);
            nm.createNotificationChannel(high);

            NotificationChannel low = new NotificationChannel(
                    "GENERAL_LOW",
                    "Silent notifications",
                    NotificationManager.IMPORTANCE_LOW
            );
            nm.createNotificationChannel(low);
        }
    }

    private void applySystemBarAppearance(Window window) {
        View decorView = window.getDecorView();
        WindowInsetsControllerCompat controller = WindowCompat.getInsetsController(window, decorView);
        if (controller != null) {
            // false = NOT light -> dus witte icons
            controller.setAppearanceLightStatusBars(false);
            controller.setAppearanceLightNavigationBars(false);
        }
    }

    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // Ensure channels early
        ensureNotificationChannels();

        Window window = getWindow();

        // 1) Edge-to-edge (jouw huidige gedrag)
        WindowCompat.setDecorFitsSystemWindows(window, false);

        // 2) Transparante system bars (jouw huidige gedrag)
        window.setStatusBarColor(Color.TRANSPARENT);
        window.setNavigationBarColor(Color.TRANSPARENT);

        // 2b) FIX: forceer bij launch lichte (witte) icons op status/navigation bar.
        // 1) Direct
        applySystemBarAppearance(window);
        // 2) Nog een keer na eerste draw (pakt 1-frame toggles tijdens splash/theme switch)
        window.getDecorView().post(() -> applySystemBarAppearance(window));

        // 2c) Extra: zorg dat WebView nooit "transparant" lijkt tijdens first paint
        try {
            if (getBridge() != null && getBridge().getWebView() != null) {
                getBridge().getWebView().setBackgroundColor(Color.parseColor("#0d131b"));
            }
        } catch (Exception ignored) {}

        // 3) WebView full bleed, insets doorgeven (jouw huidige gedrag)
        View decorView = window.getDecorView();
        decorView.setOnApplyWindowInsetsListener((v, insets) -> {
            v.setPadding(0, 0, 0, 0);
            return insets;
        });
    }
}
