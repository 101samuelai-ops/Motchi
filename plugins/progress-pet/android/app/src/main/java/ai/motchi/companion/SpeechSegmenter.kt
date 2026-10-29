package ai.motchi.companion

import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.ArrayDeque
import kotlin.math.max
import kotlin.math.sqrt

/** Bounded 20 ms mono PCM frames; silence is never uploaded or saved. */
class SpeechSegmenter {
    @Volatile var rms = 0.0; private set
    @Volatile var peak = 0.0; private set
    private var noise = 25.0
    private var loud = 0
    private var voiced = 0
    private var quiet = 0
    private val before = ArrayDeque<ByteArray>()
    private var speech: ByteArrayOutputStream? = null

    @Synchronized fun reset() { before.clear(); speech = null; loud = 0; voiced = 0; quiet = 0 }
    @Synchronized fun push(frame: ByteArray, size: Int): ByteArray? {
        require(size > 0 && size <= frame.size && size % 2 == 0)
        var squares = 0.0; var maximum = 0.0
        for (i in 0 until size step 2) {
            val sample = ((frame[i].toInt() and 255) or (frame[i+1].toInt() shl 8)).toShort().toDouble()
            squares += sample * sample; maximum = max(maximum, kotlin.math.abs(sample))
        }
        rms = sqrt(squares / (size / 2)); peak = maximum / 32768.0
        val speaking = rms >= max(14.0, noise * 3.0)
        if (speech == null) {
            before.addLast(frame.copyOf(size)); if (before.size > 15) before.removeFirst()
            if (!speaking) noise = noise * .98 + rms * .02
            loud = if (speaking) loud + 1 else 0
            if (loud < 3) return null
            speech = ByteArrayOutputStream(); before.forEach { speech!!.write(it) }; before.clear()
            voiced = 3; quiet = 0
            return null
        }
        speech!!.write(frame, 0, size)
        if (speaking) { voiced++; quiet = 0 } else quiet++
        if (quiet < 42 && speech!!.size() < 640000) return null
        val pcm = speech!!.toByteArray().let { if(it.size > 640000) it.copyOf(640000) else it }; val valid = voiced >= 8
        reset()
        return if (valid) pcm else null
    }

    companion object {
        fun boost(pcm: ByteArray): ByteArray {
            val values = ByteBuffer.wrap(pcm).order(ByteOrder.LITTLE_ENDIAN).asShortBuffer()
            val samples = ShortArray(values.remaining()); values.get(samples)
            val rms = sqrt(samples.sumOf { it.toDouble() * it } / maxOf(1, samples.size))
            // Only VAD-selected speech is boosted. Noise below the gate is
            // never amplified or uploaded; this does not recover a dead mic.
            val gain = minOf(60.0, 1600.0 / maxOf(1.0, rms)).coerceAtLeast(1.0)
            return ByteBuffer.allocate(pcm.size).order(ByteOrder.LITTLE_ENDIAN).apply {
                samples.forEach { putShort((it * gain).toInt().coerceIn(-32768,32767).toShort()) }
            }.array()
        }
        fun wav(pcm: ByteArray): ByteArray {
            require(pcm.size <= 640000 && pcm.size % 2 == 0)
            val header = ByteBuffer.allocate(44).order(ByteOrder.LITTLE_ENDIAN)
            header.put("RIFF".toByteArray()); header.putInt(pcm.size + 36); header.put("WAVEfmt ".toByteArray()); header.putInt(16)
            header.putShort(1); header.putShort(1); header.putInt(16000); header.putInt(32000); header.putShort(2); header.putShort(16)
            header.put("data".toByteArray()); header.putInt(pcm.size)
            return header.array() + pcm
        }
    }
    @Synchronized fun partial(): ByteArray? = speech?.toByteArray()?.takeIf { it.size >= 48000 }?.let { if(it.size > 640000) it.copyOfRange(it.size-640000,it.size) else it }
    @Synchronized fun finish(): ByteArray? { val result=if(voiced>=8) speech?.toByteArray()?.take(640000)?.toByteArray() else null;reset();return result }
}
