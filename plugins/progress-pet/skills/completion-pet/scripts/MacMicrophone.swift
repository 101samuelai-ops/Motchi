import AVFoundation
import Foundation

// Private child of the desktop companion. Raw PCM goes only to the parent
// process, never a file, socket or cloud service. Termination closes capture.
func fail(_ message: String) -> Never {
    FileHandle.standardError.write(Data(message.utf8)); exit(1)
}
let permission = AVCaptureDevice.authorizationStatus(for: .audio)
if permission == .notDetermined {
    let ready = DispatchSemaphore(value: 0)
    var granted = false
    AVCaptureDevice.requestAccess(for: .audio) { granted = $0; ready.signal() }
    ready.wait()
    if !granted { fail("Allow Motchi microphone access in macOS System Settings → Privacy & Security → Microphone.") }
} else if permission != .authorized {
    fail("Allow Motchi microphone access in macOS System Settings → Privacy & Security → Microphone.")
}
let engine = AVAudioEngine()
let input = engine.inputNode
// Keep the default physical input unprocessed. Voice-processing I/O suppressed
// this Mac's signal during the calendar test. Segment speech in the parent;
// mute capture during replies instead of applying an opaque input noise gate.
let source = input.outputFormat(forBus: 0)
guard source.sampleRate > 0, source.channelCount > 0,
      let output = AVAudioFormat(commonFormat: .pcmFormatInt16, sampleRate: 16000, channels: 1, interleaved: true),
      let converter = AVAudioConverter(from: source, to: output) else { fail("The Mac has no available microphone input.") }
input.installTap(onBus: 0, bufferSize: 1024, format: source) { buffer, _ in
    let capacity = AVAudioFrameCount(Double(buffer.frameLength) * 16000 / source.sampleRate + 32)
    guard let converted = AVAudioPCMBuffer(pcmFormat: output, frameCapacity: capacity) else { return }
    var supplied = false
    var error: NSError?
    converter.convert(to: converted, error: &error) { _, status in
        if supplied { status.pointee = .noDataNow; return nil }
        supplied = true; status.pointee = .haveData; return buffer
    }
    if error == nil, let samples = converted.int16ChannelData?[0], converted.frameLength > 0 {
        FileHandle.standardOutput.write(Data(bytes: samples, count: Int(converted.frameLength) * 2))
    }
}
do { try engine.start() } catch { fail("Mac microphone could not start: \(error.localizedDescription)") }
RunLoop.main.run()
