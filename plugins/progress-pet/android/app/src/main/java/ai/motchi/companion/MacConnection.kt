package ai.motchi.companion

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import org.json.JSONObject
import java.net.InetAddress
import java.net.URL
import java.security.KeyStore
import java.security.MessageDigest
import java.security.SecureRandom
import java.security.cert.X509Certificate
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import javax.net.ssl.HttpsURLConnection
import javax.net.ssl.SSLContext
import javax.net.ssl.TrustManager
import javax.net.ssl.X509TrustManager

/** The same Keystore credential and certificate pin for UI and microphone service. */
class MacConnection(context: Context) {
    private val prefs = context.applicationContext.getSharedPreferences("motchi", Context.MODE_PRIVATE)
    private fun key(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore"); store.load(null)
        (store.getKey("motchi.connection", null) as? SecretKey)?.let { return it }
        val gen = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        gen.init(KeyGenParameterSpec.Builder("motchi.connection", KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build())
        return gen.generateKey()
    }
    @Synchronized fun save(value: JSONObject?) {
        if (value == null) { prefs.edit().clear().apply(); return }
        val cipher = Cipher.getInstance("AES/GCM/NoPadding"); cipher.init(Cipher.ENCRYPT_MODE, key())
        val encrypted = cipher.iv + cipher.doFinal(value.toString().toByteArray(Charsets.UTF_8))
        prefs.edit().putString("connection", Base64.encodeToString(encrypted, Base64.NO_WRAP)).apply()
    }
    @Synchronized fun load(): JSONObject? {
        val value = prefs.getString("connection", null) ?: return null
        return try {
            val data = Base64.decode(value, Base64.NO_WRAP)
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, data.copyOfRange(0,12)))
            JSONObject(String(cipher.doFinal(data.copyOfRange(12,data.size)), Charsets.UTF_8))
        } catch (e: Exception) { null }
    }
    fun validateEndpoint(endpoint: String): URL {
        val url = URL(endpoint)
        require(url.protocol == "https" && url.userInfo == null && url.query == null && url.ref == null && url.path in listOf("", "/")) { "Use a valid local Mac pairing code." }
        require(url.host.matches(Regex("[0-9.]+")) && InetAddress.getByName(url.host).isSiteLocalAddress) { "Pair with a Mac on your local Wi-Fi." }
        return url
    }
    fun request(config: JSONObject, path: String, method: String = "GET", payload: ByteArray? = null, voice: Boolean = false, operation: String = ""): JSONObject {
        val base = validateEndpoint(config.getString("url"))
        require(path.matches(Regex("/v1/(projects|pair|operations|device|speech|speech-provider|voice|mac-voice|voice-audio/[a-zA-Z0-9-]{8,100}|operations/[a-zA-Z0-9-]{8,100})")))
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

}
