package ai.motchi.companion

import org.junit.Assert.*
import org.junit.Test
import java.nio.ByteBuffer
import java.nio.ByteOrder

class SpeechSegmenterTest {
    private fun frame(value: Int): ByteArray = ByteBuffer.allocate(640).order(ByteOrder.LITTLE_ENDIAN).apply { repeat(320) { putShort(value.toShort()) } }.array()
    @Test fun silenceIsNotUploaded() {
        val voice = SpeechSegmenter()
        repeat(3000) { assertNull(voice.push(frame(12), 640)) }
        assertTrue(voice.rms < 20)
    }
    @Test fun shortClicksDoNotBecomeSpeech() {
        val voice = SpeechSegmenter()
        repeat(30) { assertNull(voice.push(frame(0), 640)) }
        repeat(2) { assertNull(voice.push(frame(6000), 640)) }
        repeat(60) { assertNull(voice.push(frame(0), 640)) }
    }
    @Test fun speechEndsAfterSilenceAndPreservesPreRoll() {
        val voice = SpeechSegmenter()
        repeat(20) { voice.push(frame(10), 640) }
        repeat(30) { assertNull(voice.push(frame(1800), 640)) }
        var pcm: ByteArray? = null
        repeat(42) { voice.push(frame(10), 640)?.let { pcm = it } }
        assertNotNull(pcm); assertTrue(pcm!!.size > (30+42)*640)
        val wav = SpeechSegmenter.wav(pcm!!)
        assertEquals("RIFF", String(wav.copyOfRange(0,4)))
        val header = ByteBuffer.wrap(wav).order(ByteOrder.LITTLE_ENDIAN)
        assertEquals(16000, header.getInt(24)); assertEquals(pcm!!.size, header.getInt(40))
    }
    @Test fun continuousInputIsBounded() {
        val voice = SpeechSegmenter(); val chunks = mutableListOf<ByteArray>()
        repeat(2100) { voice.push(frame(1000), 640)?.let { chunks.add(it) } }
        assertTrue(chunks.size >= 2); assertTrue(chunks.all { it.size <= 640000 })
    }
    @Test fun pauseDiscardsPartialSpeech() {
        val voice = SpeechSegmenter()
        repeat(20) { voice.push(frame(1000), 640) }; voice.reset()
        repeat(60) { assertNull(voice.push(frame(0), 640)) }
    }
    @Test fun waveformUsesMeasuredMicrophoneLevel() {
        val voice = SpeechSegmenter(); voice.push(frame(100), 640); val quiet = voice.rms
        voice.push(frame(2000), 640); assertTrue(voice.rms > quiet * 10); assertTrue(voice.peak > 0)
    }
    @Test fun weakSpeechGetsLiveUpdatesAndAFinalSegment() {
        val voice = SpeechSegmenter()
        repeat(200) { assertNull(voice.push(frame(4), 640)) }
        assertNull(voice.partial())
        repeat(90) { assertNull(voice.push(frame(30), 640)) }
        val partial = voice.partial(); assertNotNull(partial)
        var final: ByteArray? = null
        repeat(42) { voice.push(frame(4), 640)?.let { final = it } }
        assertNotNull(final); assertTrue(final!!.size > partial!!.size)
        assertNull(voice.partial())
    }
    @Test fun quietSegmentsAreBoostedWithoutClippingLoudInput() {
        val weak = SpeechSegmenter.boost(frame(30))
        val meter = SpeechSegmenter(); meter.push(weak, weak.size)
        assertTrue(meter.rms > 1000)
        val loud = SpeechSegmenter.boost(frame(32000)); meter.push(loud, loud.size)
        assertEquals(32000.0, meter.rms, 1.0)
    }
}
