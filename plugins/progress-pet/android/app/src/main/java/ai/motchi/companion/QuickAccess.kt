package ai.motchi.companion

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ShortcutInfo
import android.content.pm.ShortcutManager
import android.graphics.drawable.Icon
import android.os.Build
import android.util.Log
import org.json.JSONObject

/** A local launch button only: no foreground service, overlay or project data. */
object QuickAccess {
    private const val CHANNEL = "motchi.quick-access"
    private const val NOTIFICATION = 1302
    private const val PREFERENCE = "quickAccessEnabled"

    private fun preferences(context: Context) = context.getSharedPreferences("motchi.access", Context.MODE_PRIVATE)
    fun enabled(context: Context) = preferences(context).getBoolean(PREFERENCE, true)
    private fun manager(context: Context) = context.getSystemService(NotificationManager::class.java)
    fun notificationsAllowed(context: Context): Boolean {
        val service = manager(context)
        return service.areNotificationsEnabled() &&
            (service.getNotificationChannel(CHANNEL)?.importance ?: NotificationManager.IMPORTANCE_LOW) != NotificationManager.IMPORTANCE_NONE &&
            (Build.VERSION.SDK_INT < 33 || context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED)
    }

    fun show(context: Context): Boolean {
        if (!enabled(context)) return false
        val service = manager(context)
        val channel = NotificationChannel(CHANNEL, "Open Motchi", NotificationManager.IMPORTANCE_LOW).apply {
            description = "A quiet button to open your project companion."
            setShowBadge(false)
            setSound(null, null)
        }
        service.createNotificationChannel(channel)
        if (!notificationsAllowed(context)) return false
        val intent = Intent(context, MainActivity::class.java).apply {
            action = Intent.ACTION_MAIN
            addCategory(Intent.CATEGORY_LAUNCHER)
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val launch = PendingIntent.getActivity(context, 1302, intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val notification = Notification.Builder(context, CHANNEL)
            .setSmallIcon(R.drawable.motchi_notification)
            .setContentTitle("Motchi")
            .setContentText("Tap to open your projects")
            .setContentIntent(launch)
            .addAction(Notification.Action.Builder(Icon.createWithResource(context, R.drawable.motchi_notification), "Open Motchi", launch).build())
            .setOngoing(true)
            .setAutoCancel(false)
            .setOnlyAlertOnce(true)
            .setVisibility(Notification.VISIBILITY_PUBLIC)
            .setCategory(Notification.CATEGORY_STATUS)
            .build()
        service.notify(NOTIFICATION, notification)
        return true
    }

    fun setEnabled(context: Context, enabled: Boolean): Boolean {
        preferences(context).edit().putBoolean(PREFERENCE, enabled).apply()
        if (!enabled) {
            manager(context).cancel(NOTIFICATION)
            return false
        }
        return show(context)
    }

    fun info(context: Context): JSONObject {
        val shortcuts = context.getSystemService(ShortcutManager::class.java)
        val visible = manager(context).activeNotifications.any { it.id == NOTIFICATION }
        return JSONObject().put("enabled", enabled(context)).put("visible", visible)
            .put("notificationsAllowed", notificationsAllowed(context))
            .put("canPinShortcut", shortcuts.isRequestPinShortcutSupported)
            .put("shortcutPinned", shortcuts.pinnedShortcuts.any { it.id == "motchi.open" })
    }

    fun requestShortcut(context: Context): JSONObject {
        val shortcuts = context.getSystemService(ShortcutManager::class.java)
        require(shortcuts.isRequestPinShortcutSupported) { "This calendar home screen does not support pinned shortcuts. Swipe down and use Open Motchi instead." }
        if (shortcuts.pinnedShortcuts.any { it.id == "motchi.open" }) return JSONObject().put("alreadyPinned", true)
        val shortcut = ShortcutInfo.Builder(context, "motchi.open")
            .setShortLabel("Motchi")
            .setLongLabel("Open Motchi projects")
            .setIcon(Icon.createWithResource(context, R.drawable.motchi_icon))
            .setIntent(Intent(context, MainActivity::class.java).setAction(Intent.ACTION_MAIN))
            .build()
        val accepted = shortcuts.requestPinShortcut(shortcut, null)
        require(accepted) { "The home screen could not show the shortcut request. Use Open Motchi in the notification panel." }
        return JSONObject().put("requested", true)
    }
}

class QuickAccessReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_MY_PACKAGE_REPLACED && intent.action != Intent.ACTION_BOOT_COMPLETED) return
        try {
            val visible = QuickAccess.show(context)
            Log.i("MotchiAccess", if (visible) "Open Motchi button ready" else "Open Motchi button disabled or notifications unavailable")
        } catch (error: Exception) {
            Log.w("MotchiAccess", "Open Motchi button unavailable: ${error.javaClass.simpleName}")
        }
    }
}
