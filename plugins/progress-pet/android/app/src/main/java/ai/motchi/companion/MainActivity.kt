package ai.motchi.companion

import android.Manifest
import android.app.Activity
import android.content.pm.PackageManager
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Bundle
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.util.Base64
import android.webkit.JavascriptInterface
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.view.WindowManager
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.concurrent.Executors

class MainActivity : Activity() {
    private lateinit var web: WebView
    private val main = Handler(Looper.getMainLooper())
    private val workers = Executors.newFixedThreadPool(3)
    private val prefs by lazy { getSharedPreferences("motchi", MODE_PRIVATE) }
    @Volatile private var recording = false
    private var recorder: AudioRecord? = null
    private var audioThread: Thread? = null
    private var audio = ByteArrayOutputStream()
    @Volatile private var recorded: ByteArray? = null
    private var pendingPermission: String? = null
    private var pendingNotifications: String? = null
    private var pendingWake: String? = null
    @Volatile private var syncAvailable = false
    private val timeout = Runnable { finishRecording(false); event("recordingStopped", JSONObject().put("automatic", true)) }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        web = WebView(this)
        WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG)
        web.settings.javaScriptEnabled = true
        web.settings.domStorageEnabled = true
        web.settings.allowFileAccess = false
        web.settings.allowContentAccess = false
        web.settings.mediaPlaybackRequiresUserGesture = true
        web.settings.setSupportMultipleWindows(false)
        web.addJavascriptInterface(NativeBridge(), "MotchiNative")
        web.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean = true
        }
        setContentView(web)
        try { QuickAccess.show(this) } catch (_: Exception) { android.util.Log.w("MotchiAccess", "Quick access notification unavailable") }
        // Only bundled assets can call the narrowly scoped native interface.
        web.loadUrl("file:///android_asset/" + if(BuildConfig.COMPATIBILITY) "compatibility.html" else "index.html")
        if (!BuildConfig.COMPATIBILITY && VoiceService.enabled(this)) try { VoiceService.setEnabled(this, true) } catch (_: Exception) {}
    }

    private fun reply(id: String, value: JSONObject) {
        main.post { if (!isFinishing) web.evaluateJavascript("window.nativeReply(${JSONObject.quote(id)},${JSONObject.quote(value.toString())})", null) }
    }
    private fun event(name: String, value: JSONObject) {
        main.post { if (!isFinishing) web.evaluateJavascript("window.nativeEvent(${JSONObject.quote(name)},${JSONObject.quote(value.toString())})", null) }
    }
    private val mac by lazy { MacConnection(this) }
    private fun connection() = mac.load()
    private fun saveConnection(value: JSONObject?) = mac.save(value)
    private fun network(config: JSONObject, path: String, method: String = "GET", payload: ByteArray? = null, voice: Boolean = false, operation: String = "") = mac.request(config,path,method,payload,voice,operation)

    inner class NativeBridge {
        @JavascriptInterface fun request(id: String, raw: String) {
            if (!id.matches(Regex("[a-zA-Z0-9-]{1,100}"))) return
            workers.execute {
                try {
                    val value=JSONObject(raw); val action=value.getString("action")
                    val result = when(action) {
                        "info" -> JSONObject().put("paired", connection()!=null).put("microphone",checkSelfPermission(Manifest.permission.RECORD_AUDIO)==PackageManager.PERMISSION_GRANTED).put("android",android.os.Build.VERSION.RELEASE).put("model",android.os.Build.MODEL)
                        "pair" -> {
                            val ticket=value.getString("ticket").trim(); require(ticket.startsWith("MOTCHI1.")) { "Paste the pairing code shown on your Mac." }
                            val config=JSONObject(String(Base64.decode(ticket.substring(8), Base64.URL_SAFE or Base64.NO_WRAP or Base64.NO_PADDING), Charsets.UTF_8))
                            mac.validateEndpoint(config.getString("url"))
                            val response=network(config,"/v1/pair","POST",JSONObject().put("code",config.getString("code")).put("name","Motchi calendar · " + android.os.Build.MODEL).toString().toByteArray())
                            config.remove("code"); config.put("token",response.getString("token"));config.put("deviceId",response.getString("deviceId"));saveConnection(config)
                            JSONObject().put("paired",true)
                        }
                        "snapshot" -> {
                            try {
                                val snapshot = network(connection() ?: error("Pair with your Mac first."), "/v1/projects")
                                if (!syncAvailable) android.util.Log.i("MotchiConnection", "Project sync ready: ${snapshot.optJSONArray("projects")?.length() ?: 0} projects")
                                syncAvailable = true
                                snapshot
                            } catch (error: Exception) {
                                if (syncAvailable) android.util.Log.w("MotchiConnection", "Mac project sync disconnected")
                                syncAvailable = false
                                throw error
                            }
                        }
                        "quickAccessInfo" -> QuickAccess.info(this@MainActivity)
                        "voiceInfo" -> VoiceService.info(this@MainActivity)
                        "speechProvider" -> {
                            val config=connection() ?: error("Connect to your Mac first.")
                            if(value.has("provider")) network(config,"/v1/speech-provider","POST",JSONObject().put("provider",value.getString("provider")).toString().toByteArray())
                            else network(config,"/v1/speech-provider")
                        }
                        "voiceSource" -> { VoiceService.setSource(this@MainActivity, value.getString("source")); VoiceService.info(this@MainActivity) }
                        "voiceLanguage" -> { VoiceService.setLanguage(this@MainActivity, value.getString("language")); VoiceService.info(this@MainActivity) }
                        "finishVoice" -> { VoiceService.finishQuestion(); VoiceService.info(this@MainActivity) }
                        "listenNow" -> { VoiceService.listenNow(); VoiceService.info(this@MainActivity) }
                        "voiceEvents" -> JSONObject().put("events", VoiceService.drain())
                        "voiceContext" -> { VoiceService.context(value.optString("projectId").takeIf { it.isNotEmpty() }, value.optString("selection").takeIf { it.isNotEmpty() }); JSONObject().put("saved", true) }
                        "wakeListening" -> {
                            val enabled = value.getBoolean("enabled")
                            if (enabled) {
                                val ready = network(connection() ?: error("Connect to your Mac first."), "/v1/projects")
                                check(ready.optBoolean("wakeVoiceAvailable")) { "Wake voice is not ready on your Mac. Update or reconnect Motchi on the Mac first." }
                                if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
                                    main.post { pendingWake = id; requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), 42) }; return@execute
                                }
                            }
                            main.post {
                                try { VoiceService.setEnabled(this@MainActivity, enabled); reply(id, JSONObject().put("ok", true).put("data", VoiceService.info(this@MainActivity))) }
                                catch(error: Exception) { reply(id, JSONObject().put("ok", false).put("error", error.message)) }
                            }; return@execute
                        }
                        "pinShortcut" -> QuickAccess.requestShortcut(this@MainActivity)
                        "quickAccess" -> {
                            val enabled = value.getBoolean("enabled")
                            if (enabled && Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                                main.post { pendingNotifications=id;requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS),41) };return@execute
                            }
                            QuickAccess.setEnabled(this@MainActivity, enabled)
                            QuickAccess.info(this@MainActivity)
                        }
                        "submit" -> network(connection() ?: error("Mac is disconnected."),"/v1/operations","POST",value.getJSONObject("request").toString().toByteArray(Charsets.UTF_8))
                        "job" -> network(connection() ?: error("Mac is disconnected."),"/v1/operations/"+value.getString("id"))
                        "forget" -> {
                            VoiceService.setEnabled(this@MainActivity, false)
                            connection()?.let { network(it,"/v1/device","DELETE") }; saveConnection(null);JSONObject().put("forgotten",true)
                        }
                        "startRecording" -> {
                            if (checkSelfPermission(Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED) {
                                main.post { pendingPermission=id;requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO),40) };return@execute
                            }
                            beginRecording(); JSONObject().put("recording",true)
                        }
                        "stopRecording" -> { finishRecording(false);JSONObject().put("recorded",recorded!=null) }
                        "cancelRecording" -> { finishRecording(true);JSONObject().put("cancelled",true) }
                        "transcribe" -> {
                            val bytes=recorded ?: error("Record a question first."); recorded=null
                            network(connection() ?: error("Mac is disconnected."),"/v1/speech","POST",bytes,true,value.getString("operationId"))
                        }
                        else -> error("Unsupported app action.")
                    }
                    reply(id,JSONObject().put("ok",true).put("data",result))
                } catch(e: Exception) { reply(id,JSONObject().put("ok",false).put("error",e.message ?: "Connection failed. Your request was not automatically resent.")) }
            }
        }
    }
    override fun onRequestPermissionsResult(requestCode:Int,permissions:Array<out String>,grantResults:IntArray) {
        super.onRequestPermissionsResult(requestCode,permissions,grantResults)
        if (requestCode==41) {
            val id=pendingNotifications;pendingNotifications=null
            if (id!=null) {
                val granted=grantResults.isNotEmpty()&&grantResults[0]==PackageManager.PERMISSION_GRANTED
                QuickAccess.setEnabled(this,granted)
                reply(id,JSONObject().put("ok",true).put("data",QuickAccess.info(this)))
            }
        }
        if (requestCode==40) {
            val id=pendingPermission;pendingPermission=null
            if (id!=null) workers.execute {
                try {
                    require(grantResults.isNotEmpty()&&grantResults[0]==PackageManager.PERMISSION_GRANTED) { "Microphone access denied. You can still type." }
                    beginRecording();reply(id,JSONObject().put("ok",true).put("data",JSONObject().put("recording",true)))
                } catch(e:Exception) { reply(id,JSONObject().put("ok",false).put("error",e.message)) }
            }
        }
        if (requestCode == 42) {
            val id = pendingWake; pendingWake = null
            if (id != null) {
                val granted = grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED
                if (granted) try { VoiceService.setEnabled(this, true); reply(id, JSONObject().put("ok", true).put("data", VoiceService.info(this))) }
                catch (error: Exception) { reply(id, JSONObject().put("ok", false).put("error", error.message)) }
                else reply(id, JSONObject().put("ok", false).put("error", "Microphone permission denied. You can still type."))
            }
        }
    }
    @Synchronized private fun beginRecording() {
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED) throw SecurityException("Microphone access denied. You can still type.")
        check(!recording) { "Already recording." }; recorded=null;audio=ByteArrayOutputStream()
        val minimum=AudioRecord.getMinBufferSize(16000,AudioFormat.CHANNEL_IN_MONO,AudioFormat.ENCODING_PCM_16BIT)
        require(minimum>0) { "16kHz microphone recording is unavailable." }
        VoiceService.holdManual(true)
        val input: AudioRecord
        try {
            input=AudioRecord(MediaRecorder.AudioSource.VOICE_RECOGNITION,16000,AudioFormat.CHANNEL_IN_MONO,AudioFormat.ENCODING_PCM_16BIT,maxOf(8192,minimum*2))
            recorder=input
            check(input.state==AudioRecord.STATE_INITIALIZED) { "Microphone unavailable. You can still type." }
            input.startRecording();check(input.recordingState==AudioRecord.RECORDSTATE_RECORDING);recording=true
        } catch (error: Exception) { recorder?.release(); recorder=null; VoiceService.holdManual(false); throw error }
        audioThread=Thread {
            val buffer=ByteArray(4096)
            while(recording && audio.size()<1920000) {
                val count=input.read(buffer,0,minOf(buffer.size,1920000-audio.size()))
                if(count<=0) break
                audio.write(buffer,0,count)
                // Share only a normalized level with the bundled UI, while an
                // explicitly started recording is active. No extra recording.
                var squares = 0.0
                for (i in 0 until count - 1 step 2) {
                    val sample = ((buffer[i].toInt() and 0xff) or (buffer[i+1].toInt() shl 8)).toShort().toDouble()
                    squares += sample * sample
                }
                val rms = kotlin.math.sqrt(squares / maxOf(1, count / 2)) / 32768.0
                event("recordingLevel", JSONObject().put("level", minOf(1.0, rms * 12.0)))
            }
            if(recording) main.post { finishRecording(false);event("recordingStopped",JSONObject().put("automatic",true)) }
        }.also { it.start() }
        main.postDelayed(timeout,60000)
    }
    @Synchronized private fun finishRecording(cancel:Boolean) {
        main.removeCallbacks(timeout)
        recording=false
        try { recorder?.stop() } catch (_:Exception) {}
        try { audioThread?.join(1200) } catch (_:Exception) {}
        recorder?.release();recorder=null;audioThread=null
        val pcm=audio.toByteArray();audio.reset()
        if(cancel || pcm.isEmpty()) { recorded=null; VoiceService.holdManual(false); return }
        val header=ByteBuffer.allocate(44).order(ByteOrder.LITTLE_ENDIAN)
        header.put("RIFF".toByteArray());header.putInt(pcm.size+36);header.put("WAVEfmt ".toByteArray());header.putInt(16)
        header.putShort(1);header.putShort(1);header.putInt(16000);header.putInt(32000);header.putShort(2);header.putShort(16)
        header.put("data".toByteArray());header.putInt(pcm.size)
        recorded=header.array()+pcm
        VoiceService.holdManual(false)
    }
    override fun onStop() { val wasRecording=recording; finishRecording(true); if(wasRecording) event("recordingCancelled",JSONObject()); super.onStop() }
    override fun onDestroy() { finishRecording(true);workers.shutdownNow();web.removeJavascriptInterface("MotchiNative");web.destroy();super.onDestroy() }
    @Deprecated("Deprecated in Java") override fun onBackPressed() { web.evaluateJavascript("window.goHome && window.goHome()",null) }
}
