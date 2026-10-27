package ai.motchi.companion

import android.Manifest
import android.app.Activity
import android.content.pm.PackageManager
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import android.webkit.JavascriptInterface
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.view.WindowManager
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.net.InetAddress
import java.net.URL
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.KeyStore
import java.security.MessageDigest
import java.security.SecureRandom
import java.security.cert.X509Certificate
import java.util.concurrent.Executors
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import javax.net.ssl.HttpsURLConnection
import javax.net.ssl.SSLContext
import javax.net.ssl.TrustManager
import javax.net.ssl.X509TrustManager

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
        // Only bundled assets can call the narrowly scoped native interface.
        web.loadUrl("file:///android_asset/" + if(BuildConfig.COMPATIBILITY) "compatibility.html" else "index.html")
    }

    private fun reply(id: String, value: JSONObject) {
        main.post { if (!isFinishing) web.evaluateJavascript("window.nativeReply(${JSONObject.quote(id)},${JSONObject.quote(value.toString())})", null) }
    }
    private fun event(name: String, value: JSONObject) {
        main.post { if (!isFinishing) web.evaluateJavascript("window.nativeEvent(${JSONObject.quote(name)},${JSONObject.quote(value.toString())})", null) }
    }
    private fun key(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore"); store.load(null)
        (store.getKey("motchi.connection", null) as? SecretKey)?.let { return it }
        val gen = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        gen.init(KeyGenParameterSpec.Builder("motchi.connection", KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build())
        return gen.generateKey()
    }
    @Synchronized private fun saveConnection(value: JSONObject?) {
        if (value == null) { prefs.edit().clear().apply(); return }
        val cipher = Cipher.getInstance("AES/GCM/NoPadding"); cipher.init(Cipher.ENCRYPT_MODE, key())
        val encrypted = cipher.iv + cipher.doFinal(value.toString().toByteArray(Charsets.UTF_8))
        prefs.edit().putString("connection", Base64.encodeToString(encrypted, Base64.NO_WRAP)).apply()
    }
    @Synchronized private fun connection(): JSONObject? {
        val value = prefs.getString("connection", null) ?: return null
        return try {
            val data = Base64.decode(value, Base64.NO_WRAP)
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, data.copyOfRange(0,12)))
            JSONObject(String(cipher.doFinal(data.copyOfRange(12,data.size)), Charsets.UTF_8))
        } catch (e: Exception) { null }
    }
    private fun validateEndpoint(endpoint: String): URL {
        val url = URL(endpoint)
        require(url.protocol == "https" && url.userInfo == null && url.query == null && url.ref == null && url.path in listOf("", "/")) { "Use a valid local Mac pairing code." }
        require(url.host.matches(Regex("[0-9.]+")) && InetAddress.getByName(url.host).isSiteLocalAddress) { "Pair with a Mac on your local Wi-Fi." }
        return url
    }
    private fun network(config: JSONObject, path: String, method: String = "GET", payload: ByteArray? = null, voice: Boolean = false, operation: String = ""): JSONObject {
        val base = validateEndpoint(config.getString("url"))
        require(path.matches(Regex("/v1/(projects|pair|operations|device|speech|operations/[a-zA-Z0-9-]{8,100})")))
        val pin = config.getString("pin").lowercase()
        require(pin.matches(Regex("[a-f0-9]{64}")))
        val trust = object : X509TrustManager {
            override fun getAcceptedIssuers(): Array<X509Certificate> = emptyArray()
            override fun checkClientTrusted(chain: Array<X509Certificate>, authType: String) { throw java.security.cert.CertificateException("Client certificates unsupported") }
            override fun checkServerTrusted(chain: Array<X509Certificate>, authType: String) {
                require(chain.isNotEmpty())
                val found = MessageDigest.getInstance("SHA-256").digest(chain[0].encoded).joinToString("") { "%02x".format(it.toInt() and 255) }
                if (!MessageDigest.isEqual(found.toByteArray(), pin.toByteArray())) throw java.security.cert.CertificateException("Mac certificate changed. Pair again on the Mac.")
                chain[0].checkValidity()
            }
        }
        val ssl = SSLContext.getInstance("TLS"); ssl.init(null,arrayOf<TrustManager>(trust),SecureRandom())
        val conn = URL(base.toString().trimEnd('/') + path).openConnection() as HttpsURLConnection
        conn.sslSocketFactory = ssl.socketFactory
        // Exact paired host plus SHA-256 leaf pin replaces public-CA DNS validation.
        conn.hostnameVerifier = javax.net.ssl.HostnameVerifier { hostname, _ -> hostname == base.host }
        conn.instanceFollowRedirects = false
        conn.connectTimeout = 10000; conn.readTimeout = 35000; conn.requestMethod = method
        conn.setRequestProperty("Accept", "application/json")
        if (config.has("token")) conn.setRequestProperty("Authorization", "Bearer " + config.getString("token"))
        if (payload != null) {
            conn.doOutput = true; conn.setRequestProperty("Content-Type", if (voice) "audio/wav" else "application/json")
            if (voice) conn.setRequestProperty("X-Operation-ID", operation)
            conn.setFixedLengthStreamingMode(payload.size)
        }
        try {
            if (payload != null) conn.outputStream.use { it.write(payload) }
            val code = conn.responseCode
            val stream = if (code in 200..299) conn.inputStream else conn.errorStream
            val data = stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() } ?: "{}"
            val result = JSONObject(data)
            if (code == 401) throw IllegalStateException("Pairing expired or revoked. Reconnect from Settings.")
            if (code !in 200..299) throw IllegalStateException(result.optString("error", "Mac request failed ($code)"))
            return result
        } finally { conn.disconnect() }
    }

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
                            validateEndpoint(config.getString("url"))
                            val response=network(config,"/v1/pair","POST",JSONObject().put("code",config.getString("code")).put("name","Motchi calendar · " + android.os.Build.MODEL).toString().toByteArray())
                            config.remove("code"); config.put("token",response.getString("token"));config.put("deviceId",response.getString("deviceId"));saveConnection(config)
                            JSONObject().put("paired",true)
                        }
                        "snapshot" -> network(connection() ?: error("Pair with your Mac first."), "/v1/projects")
                        "submit" -> network(connection() ?: error("Mac is disconnected."),"/v1/operations","POST",value.getJSONObject("request").toString().toByteArray(Charsets.UTF_8))
                        "job" -> network(connection() ?: error("Mac is disconnected."),"/v1/operations/"+value.getString("id"))
                        "forget" -> {
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
        if (requestCode==40) {
            val id=pendingPermission;pendingPermission=null
            if (id!=null) workers.execute {
                try {
                    require(grantResults.isNotEmpty()&&grantResults[0]==PackageManager.PERMISSION_GRANTED) { "Microphone access denied. You can still type." }
                    beginRecording();reply(id,JSONObject().put("ok",true).put("data",JSONObject().put("recording",true)))
                } catch(e:Exception) { reply(id,JSONObject().put("ok",false).put("error",e.message)) }
            }
        }
    }
    @Synchronized private fun beginRecording() {
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED) throw SecurityException("Microphone access denied. You can still type.")
        check(!recording) { "Already recording." }; recorded=null;audio=ByteArrayOutputStream()
        val minimum=AudioRecord.getMinBufferSize(16000,AudioFormat.CHANNEL_IN_MONO,AudioFormat.ENCODING_PCM_16BIT)
        require(minimum>0) { "16kHz microphone recording is unavailable." }
        val input=AudioRecord(MediaRecorder.AudioSource.MIC,16000,AudioFormat.CHANNEL_IN_MONO,AudioFormat.ENCODING_PCM_16BIT,maxOf(8192,minimum*2))
        check(input.state==AudioRecord.STATE_INITIALIZED) { "Microphone unavailable. You can still type." }
        recorder=input;input.startRecording();recording=true
        audioThread=Thread {
            val buffer=ByteArray(4096)
            while(recording && audio.size()<1920000) {
                val count=input.read(buffer,0,minOf(buffer.size,1920000-audio.size()))
                if(count<=0) break
                audio.write(buffer,0,count)
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
        if(cancel || pcm.isEmpty()) { recorded=null; return }
        val header=ByteBuffer.allocate(44).order(ByteOrder.LITTLE_ENDIAN)
        header.put("RIFF".toByteArray());header.putInt(pcm.size+36);header.put("WAVEfmt ".toByteArray());header.putInt(16)
        header.putShort(1);header.putShort(1);header.putInt(16000);header.putInt(32000);header.putShort(2);header.putShort(16)
        header.put("data".toByteArray());header.putInt(pcm.size)
        recorded=header.array()+pcm
    }
    override fun onStop() { val wasRecording=recording; finishRecording(true); if(wasRecording) event("recordingCancelled",JSONObject()); super.onStop() }
    override fun onDestroy() { finishRecording(true);workers.shutdownNow();web.removeJavascriptInterface("MotchiNative");web.destroy();super.onDestroy() }
    @Deprecated("Deprecated in Java") override fun onBackPressed() { web.evaluateJavascript("window.goHome && window.goHome()",null) }
}
