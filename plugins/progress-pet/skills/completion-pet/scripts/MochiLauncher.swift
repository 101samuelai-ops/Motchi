// Per-user app lifecycle listener. No approval hooks or UI automation are used.
import AppKit
import Foundation
import Darwin

struct LauncherConfig: Codable {
    let codexBundleIDs: [String]
    let mochiAppPath: String
    let statusPath: String
    let logPath: String
}

enum LaunchGate {
    case idle, alreadyRunning, launch
    static func action(codexRunning: Bool, previouslyRunning: Bool, mochiRunning: Bool) -> LaunchGate {
        guard codexRunning, !previouslyRunning else { return .idle }
        return mochiRunning ? .alreadyRunning : .launch
    }
}

final class MochiLauncher {
    let config: LauncherConfig
    var previouslyRunning = false
    var lastState: [String: Any] = [:]
    var observers: [NSObjectProtocol] = []
    var timer: Timer?
    var generation = 0
    var launching = false
    var attempts = 0

    init(_ config: LauncherConfig) { self.config = config }

    static func isMochi(_ app: NSRunningApplication) -> Bool {
        guard !app.isTerminated, let id = app.bundleIdentifier else { return false }
        return id.hasPrefix("local.progress-pet.hub.") || id.hasPrefix("local.progress-pet.completion.")
    }
    func codexRunning() -> Bool {
        NSWorkspace.shared.runningApplications.contains {
            !$0.isTerminated && config.codexBundleIDs.contains($0.bundleIdentifier ?? "")
        }
    }
    func mochiRunning() -> Bool { NSWorkspace.shared.runningApplications.contains(where: Self.isMochi) }

    func record(_ event: String, _ message: String) {
        let state: [String: Any] = ["event": event, "message": message,
            "updatedAt": ISO8601DateFormatter().string(from: Date()), "pid": getpid(),
            "codexRunning": codexRunning(), "mochiRunning": mochiRunning(), "mochiAppPath": config.mochiAppPath]
        lastState = state
        if let data = try? JSONSerialization.data(withJSONObject: state, options: [.prettyPrinted, .sortedKeys]) {
            try? data.write(to: URL(fileURLWithPath: config.statusPath), options: .atomic)
        }
        let line = "\(ISO8601DateFormatter().string(from: Date())) [\(event)] \(message)\n"
        guard let data = line.data(using: .utf8) else { return }
        let path = config.logPath
        if let size = try? FileManager.default.attributesOfItem(atPath: path)[.size] as? NSNumber,
           size.intValue > 262144 {
            try? FileManager.default.removeItem(atPath: path + ".previous")
            try? FileManager.default.moveItem(atPath: path, toPath: path + ".previous")
        }
        if !FileManager.default.fileExists(atPath: path) { FileManager.default.createFile(atPath: path, contents: nil) }
        if let file = FileHandle(forWritingAtPath: path) {
            file.seekToEndOfFile(); file.write(data); try? file.close()
        }
    }

    func start() {
        let center = NSWorkspace.shared.notificationCenter
        for name in [NSWorkspace.didLaunchApplicationNotification, NSWorkspace.didTerminateApplicationNotification] {
            observers.append(center.addObserver(forName: name, object: nil, queue: .main) { [weak self] _ in self?.check() })
        }
        record("watching", "Watching Codex desktop launches.")
        check()
        // Also recover a missed workspace notification without a tight polling loop.
        timer = Timer.scheduledTimer(withTimeInterval: 15, repeats: true) { [weak self] _ in self?.check() }
    }

    func check() {
        let running = codexRunning()
        let action = LaunchGate.action(codexRunning: running, previouslyRunning: previouslyRunning, mochiRunning: mochiRunning())
        if !running && previouslyRunning {
            generation += 1
            record("codex-closed", "Codex closed. Mochi is left running to preserve its tasks.")
        }
        previouslyRunning = running
        switch action {
        case .idle: break
        case .alreadyRunning:
            record("already-running", "Codex is open; Mochi is already running. No duplicate started.")
        case .launch:
            generation += 1; attempts = 0
            launch(generation: generation)
        }
    }

    func launch(generation expected: Int) {
        guard expected == generation, codexRunning(), !launching else { return }
        guard !mochiRunning() else { record("already-running", "Mochi started before launch; no duplicate needed."); return }
        let url = URL(fileURLWithPath: config.mochiAppPath, isDirectory: true)
        guard FileManager.default.fileExists(atPath: url.appendingPathComponent("Contents/Info.plist").path) else {
            record("missing-app", "Mochi app is missing at \(url.path). Reinstall the launcher."); return
        }
        attempts += 1; launching = true
        record("launching", "Codex opened. Launching Mochi quietly (attempt \(attempts)).")
        let options = NSWorkspace.OpenConfiguration()
        options.activates = false
        options.addsToRecentItems = false
        var environment = ProcessInfo.processInfo.environment
        environment["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
        options.environment = environment
        NSWorkspace.shared.openApplication(at: url, configuration: options) { [weak self] app, error in
            DispatchQueue.main.async {
                guard let self = self else { return }
                self.launching = false
                if let error = error {
                    self.record("launch-failed", error.localizedDescription)
                    if self.attempts < 3, expected == self.generation {
                        DispatchQueue.main.asyncAfter(deadline: .now() + 5) { self.launch(generation: expected) }
                    }
                } else {
                    self.record("launched", "Mochi launched for Codex (pid \(app?.processIdentifier ?? 0)).")
                }
            }
        }
    }
}

if CommandLine.arguments.contains("--self-test") {
    let checks: [(Bool, String)] = [
        (LaunchGate.action(codexRunning: false, previouslyRunning: false, mochiRunning: false) == .idle, "No launch without Codex"),
        (LaunchGate.action(codexRunning: true, previouslyRunning: false, mochiRunning: false) == .launch, "Codex opening launches absent Mochi"),
        (LaunchGate.action(codexRunning: true, previouslyRunning: false, mochiRunning: true) == .alreadyRunning, "Existing Mochi is preserved"),
        (LaunchGate.action(codexRunning: true, previouslyRunning: true, mochiRunning: false) == .idle, "Manual Mochi quit is respected until Codex reopens"),
        (LaunchGate.action(codexRunning: false, previouslyRunning: true, mochiRunning: true) == .idle, "Closing Codex does not stop Mochi")
    ]
    for (ok, name) in checks { guard ok else { fputs("FAIL: \(name)\n", stderr); exit(1) }; print("PASS: \(name)") }
    exit(0)
}
let configURL: URL? = {
    if let index = CommandLine.arguments.firstIndex(of: "--config"), index + 1 < CommandLine.arguments.count {
        return URL(fileURLWithPath: CommandLine.arguments[index + 1])
    }
    return Bundle.main.url(forResource: "launcher", withExtension: "json")
}()
guard let configURL = configURL,
      let data = try? Data(contentsOf: configURL),
      let config = try? JSONDecoder().decode(LauncherConfig.self, from: data) else {
    fputs("Usage: MochiLauncher --config /absolute/launcher.json [--probe]\n", stderr); exit(2)
}
let launcher = MochiLauncher(config)
if CommandLine.arguments.contains("--probe") {
    let result: [String: Any] = ["codexRunning": launcher.codexRunning(), "mochiRunning": launcher.mochiRunning(),
        "codexBundleIDs": config.codexBundleIDs, "mochiAppPath": config.mochiAppPath,
        "apps": NSWorkspace.shared.runningApplications.filter { config.codexBundleIDs.contains($0.bundleIdentifier ?? "") || MochiLauncher.isMochi($0) }
            .map { ["bundleID": $0.bundleIdentifier ?? "", "pid": $0.processIdentifier, "path": $0.bundleURL?.path ?? ""] as [String: Any] }]
    let encoded = try JSONSerialization.data(withJSONObject: result, options: [.prettyPrinted, .sortedKeys])
    print(String(data: encoded, encoding: .utf8)!); exit(0)
}
// Keep one watcher even when both login and a manual app launch occur.
let lockPath = URL(fileURLWithPath: config.statusPath).deletingLastPathComponent().appendingPathComponent("launcher.lock").path
let lockFD = Darwin.open(lockPath, O_CREAT | O_RDWR, S_IRUSR | S_IWUSR)
guard lockFD >= 0 else { fputs("Cannot open launcher lock.\n", stderr); exit(3) }
guard flock(lockFD, LOCK_EX | LOCK_NB) == 0 else { exit(0) }
let app = NSApplication.shared
app.setActivationPolicy(.prohibited)
launcher.start()
app.run()
