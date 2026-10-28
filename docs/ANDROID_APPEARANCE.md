# Calendar reference appearance — 0.14.1

The calendar was showing a saved light Bubble lounge layout. The user's pictured reference was dark Companion canvas. Lounge places Primary and Secondary beside one another on tablet widths; canvas places Primary above Secondary. The older canvas also relied on the platform's serif fallback and used smaller project cards.

Android 0.14.1 (versionCode 5) uses the pictured dark green canvas, a large dog, a serif speech bubble, a compact composer, larger progress circles and two cards per row on tablets. The groups remain stacked, including in landscape. Below 520 CSS pixels, cards use one column. Status colours still come from real project state: amber input, blue active, green checklist complete, red failure and neutral unknown/recent.

The requested appearance applies once when upgrading an older saved preference. Its previous layout, mode and custom colours are retained as a restorable backup. Primary pins and greeting preferences are preserved. Subsequent launches respect the chosen appearance. Settings → Appearance provides **Use pictured design** and **Restore previous look**, alongside all three approved designs and existing colour controls. No app data or Mac pairing is cleared.

## Verification — 2026-10-28

- All 24 appearance/status/isolation checks and 22 Android routing/review/offline checks passed. New cases exercise fresh installs, one-time upgrade, backup/restoration, saved personalization after restart, exact project pins and unchanged input data.
- Browser checks verified restoration, all three choices, returning to the reference, persisted selection on reload and draft retention. A question typed into the compact home composer opened the correct project's editable draft without submitting work.
- At the browser's 494 CSS-pixel viewport, the canvas uses one card column, stacked groups, the requested serif font and a 45-pixel composer. The document does not overflow horizontally. The calendar supplies the physical tablet check.
- Signed release build, Android lint and JavaScript syntax checks passed. The signed APK installed in place through the authorized WLAN connection. Android reports versionCode 5 / 0.14.1; Calendar Mirror visibly confirms dark canvas, stacked Primary/Secondary groups, seven retained projects and **Mac connected**.

This changes presentation. Automatic review remains asynchronous, actual project percentages are not the preview's sample percentages, and existing firmware/microphone/field limits in [the rollout record](ANDROID_VERIFICATION.md) remain open.
