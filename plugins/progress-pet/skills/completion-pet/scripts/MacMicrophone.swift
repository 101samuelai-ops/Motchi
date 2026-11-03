import AVFoundation
import Foundation

// Private child of the desktop companion. Raw PCM goes only to the parent
// process, never a file, socket or cloud service. Termination closes capture.
func fail(_ message: String) -> Never {
    FileHandle.standardError.write(Data(message.utf8)); exit(1)
}
let startup = Date()
func phase(_ value: String) {
    let value: [String: Any] = ["phase": value, "elapsedMs": Int(Date().timeIntervalSince(startup) * 1000)]
    if let data = try? JSONSerialization.data(withJSONObject: value) {
        FileHandle.standardError.write(data); FileHandle.standardError.write(Data([10]))
    }
}
let permission = AVCaptureDevice.authorizationStatus(for: .audio)
if permission == .notDetermined {
    let lock = NSLock()
    var result: Bool?
    AVCaptureDevice.requestAccess(for: .audio) { allowed in
        lock.lock(); result = allowed; lock.unlock()
    }
    // Authorization can need the main run loop. Blocking it on a semaphore
    // left the helper alive without audio while macOS resolved consent.
    let deadline = Date().addingTimeInterval(25)
    while Date() < deadline {
        lock.lock(); let resolved = result; lock.unlock()
        if let allowed = resolved {
            if !allowed { fail("Allow Motchi microphone access in macOS System Settings → Privacy & Security → Microphone.") }
            break
        }
        RunLoop.current.run(until: Date().addingTimeInterval(0.05))
    }
    lock.lock(); let allowed = result; lock.unlock()
    if allowed != true { fail("Mac microphone authorization is waiting. Unlock the Mac, then tap Talk again.") }
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
converter.primeMethod = .none
var firstInput = true
var firstPCM = true
input.installTap(onBus: 0, bufferSize: 1024, format: source) { buffer, _ in
    if firstInput { firstInput = false; phase("inputCallback") }
    let capacity = AVAudioFrameCount(Double(buffer.frameLength) * 16000 / source.sampleRate + 32)
    guard let converted = AVAudioPCMBuffer(pcmFormat: output, frameCapacity: capacity) else { return }
    var supplied = false
    var error: NSError?
    converter.convert(to: converted, error: &error) { _, status in
        if supplied { status.pointee = .noDataNow; return nil }
        supplied = true; status.pointee = .haveData; return buffer
    }
    if error == nil, let samples = converted.int16ChannelData?[0], converted.frameLength > 0 {
        if firstPCM { firstPCM = false; phase("pcmReady") }
        FileHandle.standardOutput.write(Data(bytes: samples, count: Int(converted.frameLength) * 2))
    }
}
engine.prepare()
do { try engine.start() } catch { fail("Mac microphone could not start: \(error.localizedDescription)") }
phase("engineStarted")
RunLoop.main.run()
