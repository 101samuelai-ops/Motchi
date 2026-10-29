package ai.motchi.companion

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaPlayer
import android.media.MediaRecorder
import android.media.AudioManager
import android.media.ToneGenerator
import android.media.audiofx.AutomaticGainControl
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import android.util.Base64
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.UUID
import java.util.concurrent.Executors
import kotlin.math.min

/** Opt-in visible capture. The Mac applies local wake and selected ASR policy; no work delivery. */
class VoiceService : Service() {
    private val main = Handler(Looper.getMainLooper())
    private val worker = Executors.newSingleThreadExecutor()
    private val mac by lazy { MacConnection(this) }
    private val segmenter = SpeechSegmenter()
    @Volatile private var alive = false
    @Volatile private var capturing = false
    @Volatile private var manual = false
    @Volatile private var busy = false
    @Volatile private var finalBusy = false
    @Volatile private var previewPending = false
    @Volatile private var activatedUntil = 0L
    @Volatile private var speechAt = 0L
    @Volatile private var recentRms = 0.0
    @Volatile private var speaking = false
    @Volatile private var generation = UUID.randomUUID().toString()
    @Volatile private var session: String? = null
    @Volatile private var projectId: String? = null
    @Volatile private var selection: String? = null
    @Volatile private var status = "Starting microphone…"
    @Volatile private var issue: String? = null
    @Volatile private var lastWake = 0L
    @Volatile private var captureTicket = 0L
    @Volatile private var macCapture = false
    @Volatile private var macActivate = false
    @Volatile private var macFinish = false
    @Volatile private var macState = JSONObject()
    private var input: AudioRecord? = null
    private var gainControl: AutomaticGainControl? = null
    private var captureThread: Thread? = null
    private var player: MediaPlayer? = null
    private var playbackFile: File? = null
    private var wakeLock: PowerManager.WakeLock? = null

    override fun onBind(intent: Intent?): IBinder? = null
    override fun dump(fd: java.io.FileDescriptor, writer: java.io.PrintWriter, args: Array<out String>) {
        // Authorized ADB diagnostics expose levels/state, never audio, tokens or questions.
        writer.println(info(this).toString())
    }
    override fun onCreate() {
        super.onCreate(); instance = this; alive = true
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel(CHANNEL, "Motchi microphone", NotificationManager.IMPORTANCE_LOW).apply {
            description = "Visible wake-name listening with a Pause button"; setShowBadge(false)
        })
    }
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == STOP) { setEnabled(this, false); stopSelf(); return START_NOT_STICKY }
        if (!enabled(this) || checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            issue = "Microphone permission is required. Open Motchi to enable it."; stopSelf(); return START_NOT_STICKY
        }
        try {
            startForeground(NOTIFICATION, notification())
            if (wakeLock == null) wakeLock = getSystemService(PowerManager::class.java).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "Motchi:WakeListening").apply { acquire() }
            if (!capturing && !manual) startCapture()
        } catch (error: Exception) { issue = error.message ?: "Open Motchi to resume microphone access."; stopSelf() }
        return START_STICKY
    }
    private fun notification(): Notification {
        val open = PendingIntent.getActivity(this, 1501, Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val pause = PendingIntent.getService(this, 1502, Intent(this, VoiceService::class.java).setAction(STOP), PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        return Notification.Builder(this, CHANNEL).setSmallIcon(R.drawable.motchi_notification)
            .setContentTitle(if (source(this) == "mac") "Motchi uses your Mac microphone" else "Motchi microphone is on").setContentText("Say Hey Motchi · $status")
            .setContentIntent(open).addAction(Notification.Action.Builder(null, "Pause microphone", pause).build())
            .setOngoing(true).setOnlyAlertOnce(true).setVisibility(Notification.VISIBILITY_PRIVATE).setCategory(Notification.CATEGORY_SERVICE).build()
    }
    private fun updateStatus(value: String) {
        status = value
        main.post { if (alive) getSystemService(NotificationManager::class.java).notify(NOTIFICATION, notification()) }
    }
    @Synchronized private fun startCapture() {
        if (!alive || manual || capturing) return
        if (source(this) == "mac") { startMacCapture(); return }
        check(checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED)
        val minimum = AudioRecord.getMinBufferSize(16000, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        require(minimum > 0) { "This microphone cannot record at 16 kHz." }
        val record = AudioRecord(MediaRecorder.AudioSource.MIC, 16000, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, maxOf(8192, minimum * 2))
        if (record.state != AudioRecord.STATE_INITIALIZED) { record.release(); error("Calendar microphone is unavailable. Check Voice settings.") }
        try { record.startRecording(); check(record.recordingState == AudioRecord.RECORDSTATE_RECORDING) }
        catch (error: Exception) { record.release(); throw error }
        input = record; capturing = true; val ticket = ++captureTicket; issue = null; updateStatus("Listening for Hey Motchi")
        try { if (AutomaticGainControl.isAvailable()) gainControl = AutomaticGainControl.create(record.audioSessionId)?.apply { enabled = true } } catch (_: Exception) {}
        captureThread = Thread({
            val buffer = ByteArray(640)
            var lastPreview = 0L
            try {
                while (alive && capturing && captureTicket == ticket) {
                    val count = record.read(buffer, 0, buffer.size)
                    if (count <= 0) { if (capturing) error("Microphone stopped supplying audio."); break }
                    if (finalBusy || speaking || manual) { segmenter.reset(); continue }
                    val pcm = segmenter.push(buffer, count - count % 2)
                    recentRms = maxOf(segmenter.rms, recentRms * .996)
                    if (segmenter.rms >= 14) speechAt = System.currentTimeMillis()
                    if (pcm != null && !finalBusy) {
                        finalBusy = true; busy = true; val epoch = generation
                        worker.execute { process(pcm, epoch, false) }
                    } else if (!previewPending && System.currentTimeMillis()-lastPreview>1800) {
                        val partial = segmenter.partial()
                        if (partial != null) {
                            previewPending = true; busy = true; lastPreview = System.currentTimeMillis(); val epoch = generation
                            worker.execute { process(partial, epoch, true) }
                        }
                    }
                }
            } catch (error: Exception) { issue = error.message; updateStatus("Microphone needs attention") }
            finally { if (captureTicket == ticket) capturing = false }
        }, "motchi-calendar-microphone").also { it.start() }
    }
    private fun startMacCapture() {
        macCapture = true; capturing = true; val ticket = ++captureTicket
        updateStatus("Connecting to your Mac microphone…")
        captureThread = Thread({
            while (alive && capturing && captureTicket == ticket) {
                try {
                    val config = mac.load() ?: error("Connect this calendar to your Mac first.")
                    val epoch = generation
                    val activate = macActivate; macActivate = false
                    val finish = macFinish; macFinish = false
                    val body = JSONObject().put("enabled", true).put("activate", activate).put("speaking", speaking)
                        .put("finish", finish).put("language", language(this))
                        .put("projectId", projectId).put("selection", selection)
                    val value = mac.request(config, "/v1/mac-voice", "POST", body.toString().toByteArray())
                    if (captureTicket != ticket) break
                    macState = value; issue = value.optString("issue").takeIf { it.isNotEmpty() && it != "null" }
                    updateStatus(value.optString("status", "Listening on your Mac"))
                    val ready = value.optJSONArray("events") ?: JSONArray()
                    for (i in 0 until ready.length()) deliver(ready.getJSONObject(i), epoch)
                } catch (error: Exception) {
                    if (captureTicket == ticket) {
                        issue = error.message; macState = JSONObject().put("running",false)
                        updateStatus("Reconnecting to your Mac microphone…")
                    }
                }
                try { Thread.sleep(if (issue == null) 700 else 2500) } catch (_: InterruptedException) { break }
            }
            if (captureTicket == ticket) capturing = false
        }, "motchi-mac-microphone").also { it.start() }
    }
    private fun deliver(result: JSONObject, epoch: String) {
        if (!alive || epoch != generation || !result.optBoolean("wake")) return
        val firstWake = System.currentTimeMillis() - lastWake > 30000
        lastWake = System.currentTimeMillis(); session = result.optString("session").takeIf { it.isNotEmpty() }
        result.optString("projectId").takeIf { it.isNotEmpty() && it != "null" }?.let { projectId = it; selection = result.optString("selection") }
        synchronized(events) { events.addLast(result); while(events.size > 8) events.removeFirst() }
        if (result.optBoolean("partial")) { updateStatus("I'm listening · live transcript"); if (firstWake) beep() }
        if (result.optBoolean("spokenReply")) {
            val config = mac.load() ?: return
            val wav = mac.request(config, "/v1/voice-audio/${result.getString("operationId")}").optString("wav")
            if (wav.isNotEmpty() && wav != "null" && epoch == generation) {
                speaking = true
                main.post { if (alive && epoch == generation) play(Base64.decode(wav, Base64.DEFAULT)) else speaking = false }
            }
        }
    }
    private fun process(pcm: ByteArray, epoch: String, preview: Boolean) {
        try {
            if (!alive || epoch != generation) return
            val config = mac.load() ?: error("Connect this calendar to your Mac in Settings.")
            updateStatus("Checking speech locally on your Mac…")
            val id = UUID.randomUUID().toString()
            val payload = JSONObject().put("operationId", id).put("generation", epoch).put("session", session)
                .put("projectId", projectId).put("selection", selection).put("preview", preview)
                .put("activated", System.currentTimeMillis() < activatedUntil)
                .put("language", language(this))
                .put("audio", Base64.encodeToString(SpeechSegmenter.wav(SpeechSegmenter.boost(pcm)), Base64.NO_WRAP))
            var job = mac.request(config, "/v1/voice", "POST", payload.toString().toByteArray())
            val deadline = System.currentTimeMillis() + 240000
            while (alive && epoch == generation && job.optString("status") in listOf("queued", "running") && System.currentTimeMillis() < deadline) {
                Thread.sleep(500); job = mac.request(config, "/v1/operations/$id")
            }
            if (!alive || epoch != generation) return
            val result = job.optJSONObject("result") ?: JSONObject()
            check(job.optString("status") == "done") { result.optString("error", "Voice processing did not finish. Please ask again.") }
            issue = null
            result.put("operationId", id); deliver(result, epoch)
        } catch (error: Exception) {
            if (alive && epoch == generation) issue = error.message ?: "Reconnect to your Mac for voice."
        } finally {
            if (preview) previewPending = false else finalBusy = false
            busy = previewPending || finalBusy
            if (alive && !speaking && !manual) updateStatus(when {
                issue != null -> "Voice needs attention · open Motchi"
                finalBusy -> "Preparing your answer…"
                System.currentTimeMillis() - lastWake < 30000 || System.currentTimeMillis() < activatedUntil -> "I'm listening · speak your question"
                else -> "Listening for Hey Motchi"
            })
        }
    }
    private fun beep() { main.post {
        try { val tone = ToneGenerator(AudioManager.STREAM_MUSIC, 55); tone.startTone(ToneGenerator.TONE_PROP_BEEP, 120); main.postDelayed({ tone.release() }, 250) } catch (_: Exception) {}
    } }
    private fun play(bytes: ByteArray) {
        stopPlayback()
        speaking = true; updateStatus("Motchi is replying")
        try {
            val file = File.createTempFile("motchi-reply-", ".wav", cacheDir); playbackFile = file; file.writeBytes(bytes)
            player = MediaPlayer().apply {
                setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ASSISTANT).setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build())
                setDataSource(file.absolutePath)
                setOnCompletionListener { finishPlayback() }
                setOnErrorListener { _, _, _ -> issue = "The reply is on screen; speaker playback failed."; finishPlayback(); true }
                prepare(); start()
            }
        } catch (_: Exception) { issue = "The reply is on screen; speaker playback is unavailable."; finishPlayback() }
    }
    private fun finishPlayback() {
        stopPlayback()
        // Discard the loudspeaker tail before accepting another utterance.
        main.postDelayed({ speaking = false; if (alive) updateStatus("Listening for your next question") }, 800)
    }
    private fun stopPlayback() {
        try { player?.stop() } catch (_: Exception) {}
        player?.release(); player = null; playbackFile?.delete(); playbackFile = null
    }
    @Synchronized private fun stopCapture() {
        capturing = false; captureTicket++
        if (macCapture) {
            macCapture = false
            Thread { try { mac.load()?.let { mac.request(it, "/v1/mac-voice", "POST", JSONObject().put("enabled", false).toString().toByteArray()) } } catch (_: Exception) {} }.start()
        }
        try { input?.stop() } catch (_: Exception) {}
        try { captureThread?.join(1200) } catch (_: Exception) {}
        gainControl?.release(); gainControl = null
        input?.release(); input = null; captureThread = null; segmenter.reset()
    }
    private fun invalidateSession() {
        val old = generation; generation = UUID.randomUUID().toString(); session = null; activatedUntil = 0; segmenter.reset()
        synchronized(events) { events.clear() }
        Thread {
            try { mac.load()?.let { mac.request(it, "/v1/voice", "POST", JSONObject().put("cancel", true).put("generation", old).toString().toByteArray()) } } catch (_: Exception) {}
        }.start()
    }
    override fun onDestroy() {
        alive = false; invalidateSession(); stopCapture(); stopPlayback(); speaking = false
        wakeLock?.let { if(it.isHeld) it.release() }; wakeLock = null
        worker.shutdownNow(); if (instance === this) instance = null
        super.onDestroy()
    }
    companion object {
        private const val CHANNEL = "motchi.wake-microphone"
        private const val NOTIFICATION = 1500
        private const val STOP = "ai.motchi.PAUSE_MICROPHONE"
        @Volatile private var instance: VoiceService? = null
        private val events = java.util.ArrayDeque<JSONObject>()
        private fun preferences(context: Context) = context.getSharedPreferences("motchi.voice", Context.MODE_PRIVATE)
        fun enabled(context: Context) = preferences(context).getBoolean("enabled", false)
        // The calendar enumerates an input but supplies no usable speech.
        // This release defaults to the user's requested computer fallback.
        fun source(context: Context) = preferences(context).getString("source", "mac") ?: "mac"
        fun language(context: Context) = preferences(context).getString("language", "en") ?: "en"
        fun setLanguage(context: Context, value: String) {
            require(value in listOf("en","zh","auto"))
            preferences(context).edit().putString("language",value).apply()
        }
        fun setSource(context: Context, value: String) {
            require(value in listOf("calendar", "mac"))
            if (source(context) == value) return
            preferences(context).edit().putString("source", value).apply()
            instance?.let { service ->
                service.invalidateSession(); service.stopCapture()
                service.main.post { service.stopPlayback(); service.speaking = false }
                if (service.alive && !service.manual) service.startCapture()
            }
        }
        fun setEnabled(context: Context, enabled: Boolean) {
            preferences(context).edit().putBoolean("enabled", enabled).apply()
            if (enabled) context.startForegroundService(Intent(context, VoiceService::class.java))
            else { synchronized(events) { events.clear() }; context.stopService(Intent(context, VoiceService::class.java)) }
        }
        fun info(context: Context): JSONObject {
            val service = instance
            val result = JSONObject().put("enabled", enabled(context)).put("running", service?.capturing == true)
                .put("status", service?.status ?: if (enabled(context)) "Open Motchi to resume listening" else "Microphone paused")
                .put("issue", service?.issue).put("level", min(1.0, (service?.segmenter?.rms ?: 0.0) / 2200.0))
                .put("rms", service?.segmenter?.rms ?: 0.0).put("peak", service?.segmenter?.peak ?: 0.0)
                .put("recentRms", service?.recentRms ?: 0.0).put("speechAt", service?.speechAt ?: 0)
                .put("source", source(context)).put("inputSource", if (source(context) == "mac") "Mac microphone" else "Calendar microphone").put("gainControl", service?.gainControl?.enabled == true)
                .put("language", language(context))
                .put("busy", service?.busy == true).put("speaking", service?.speaking == true).put("lastWakeAt", service?.lastWake ?: 0)
                .put("microphoneGranted", context.checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED)
            if (source(context) == "mac" && service != null) {
                for (key in listOf("rms", "recentRms", "busy", "status", "issue", "lastWakeAt", "utteranceSeconds", "detector", "provider", "providerLabel", "providerReady", "providerIssue", "cloudSpeech")) {
                    if (service.macState.has(key)) result.put(key, service.macState.opt(key))
                }
                result.put("running", service.capturing && service.macState.optBoolean("running"))
                if (service.issue != null) result.put("issue", service.issue)
            }
            return result
        }
        fun context(project: String?, selection: String?) { instance?.let {
            // An explicit UI project/chat change clears an older ambiguity or
            // follow-up lease. Displaying the current voice answer is a no-op.
            if (it.projectId != project || it.selection != selection) it.invalidateSession()
            it.projectId = project; it.selection = selection
        } }
        fun drain(): JSONArray = synchronized(events) { val result = JSONArray(); while(events.isNotEmpty()) result.put(events.removeFirst()); result }
        fun listenNow() {
            val service = instance ?: error("Enable the microphone first.")
            service.activatedUntil = System.currentTimeMillis() + 30000
            if (source(service) == "mac") service.macActivate = true
            service.updateStatus("I'm listening · speak now")
            synchronized(events) { events.addLast(JSONObject().put("wake", true).put("partial", true).put("text", "I'm listening. Go ahead.").put("heard", "")) }
            service.beep()
        }
        fun finishQuestion() {
            val service=instance ?: error("Tap Listen now first.")
            service.activatedUntil=System.currentTimeMillis()+30000
            if(source(service)=="mac") { service.macFinish=true;service.updateStatus("Finishing your question…");return }
            if(service.finalBusy)return
            val data=service.segmenter.finish() ?: error("No speech captured. Tap Listen now and speak close to the microphone.")
            service.finalBusy=true;service.busy=true;val epoch=service.generation
            service.worker.execute { service.process(data,epoch,false) }
        }
        fun holdManual(hold: Boolean) {
            instance?.let {
                it.manual = hold
                if (hold) { it.invalidateSession(); it.stopCapture(); it.main.post { it.stopPlayback(); it.speaking = false }; it.updateStatus("Push-to-talk in use") }
                else if (it.alive && !it.capturing) try { it.startCapture() } catch (error: Exception) { it.issue = error.message }
            }
        }
    }
}
