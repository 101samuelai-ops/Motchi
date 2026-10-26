import AppKit
import QuartzCore
import WebKit
import Darwin

struct Task: Decodable { let id: String; let title: String; let done: Bool }
struct Project: Decodable { let name: String; let tasks: [Task] }
struct Receipt: Codable { let taskIDs: [String]? }
enum AnnouncementTiming {
    static let lifetime: TimeInterval = 1.5
    static let fade: TimeInterval = 0.2
    static func fadeStart(lifetime: TimeInterval) -> TimeInterval { max(0, lifetime - fade) }
}
func trackingFrame(in area: NSRect) -> NSRect {
    let size = NSSize(width: min(440, area.width), height: min(195, area.height))
    return NSRect(x: area.maxX - size.width, y: area.maxY - size.height, width: size.width, height: size.height)
}
struct AnswerDelivery {
    struct Request { let selection: String; var dismissed = false }
    var requests: [String: Request] = [:]
    mutating func begin(id: String, selection: String) { requests[id] = Request(selection: selection) }
    mutating func dismiss() { for id in Array(requests.keys) { requests[id]?.dismissed = true } }
    mutating func finish(id: String, selection: String) -> Bool {
        guard let request = requests[id], request.selection == selection else { return false }
        requests.removeValue(forKey: id)
        return request.dismissed
    }
}
let launchConfiguration: [String: Any] = {
    guard let url = Bundle.main.url(forResource: "launch", withExtension: "json"), let data = try? Data(contentsOf: url),
          let values = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return [:] }
    return values
}()
func option(_ name: String, fallback: String = "") -> String {
    if let index = CommandLine.arguments.firstIndex(of: name), index + 1 < CommandLine.arguments.count { return CommandLine.arguments[index + 1] }
    return launchConfiguration[name] as? String ?? fallback
}
func flag(_ name: String) -> Bool { CommandLine.arguments.contains(name) || launchConfiguration[name] as? Bool == true }
func output(_ message: String) {
    print(message); fflush(stdout)
    let log = option("--log")
    if !log.isEmpty, let data = (message + "\n").data(using: .utf8) {
        try? FileManager.default.createDirectory(at: URL(fileURLWithPath: log).deletingLastPathComponent(), withIntermediateDirectories: true)
        if !FileManager.default.fileExists(atPath: log) { FileManager.default.createFile(atPath: log, contents: nil) }
        if let file = FileHandle(forWritingAtPath: log) { file.seekToEndOfFile(); file.write(data); try? file.close() }
    }
}

// Vector artwork is shared by the live animation and exported previews.
enum Puppy {
    static let ink = NSColor(calibratedRed: 0.31, green: 0.23, blue: 0.18, alpha: 1)
    static let cream = NSColor(calibratedRed: 1, green: 0.93, blue: 0.77, alpha: 1)
    static let gold = NSColor(calibratedRed: 0.76, green: 0.51, blue: 0.29, alpha: 1)
    static let pink = NSColor(calibratedRed: 0.97, green: 0.69, blue: 0.67, alpha: 1)
    static let green = NSColor(calibratedRed: 0.30, green: 0.58, blue: 0.45, alpha: 1)
    static func oval(_ rect: NSRect, _ color: NSColor, outline: Bool = false) {
        let path = NSBezierPath(ovalIn: rect); color.setFill(); path.fill()
        if outline { ink.setStroke(); path.lineWidth = 2.3; path.stroke() }
    }
    static func rounded(_ rect: NSRect, _ color: NSColor, radius: CGFloat = 8) {
        color.setFill(); NSBezierPath(roundedRect: rect, xRadius: radius, yRadius: radius).fill()
    }
    static func paw(_ x: CGFloat, _ y: CGFloat) {
        oval(NSRect(x: x, y: y, width: 27, height: 18), cream, outline: true)
        ink.withAlphaComponent(0.45).setStroke()
        let toes = NSBezierPath()
        for offset in [CGFloat(9), CGFloat(17)] { toes.move(to: NSPoint(x: x + offset, y: y + 3)); toes.line(to: NSPoint(x: x + offset, y: y + 8)) }
        toes.lineWidth = 1.3; toes.stroke()
    }
    static func draw() {
        oval(NSRect(x: 99, y: 28, width: 25, height: 51), gold, outline: true)
        oval(NSRect(x: 39, y: 15, width: 67, height: 79), cream, outline: true)
        oval(NSRect(x: 43, y: 27, width: 38, height: 46), .white.withAlphaComponent(0.4))
        paw(33, 10); paw(82, 10)
        oval(NSRect(x: 20, y: 62, width: 103, height: 83), cream, outline: true)
        oval(NSRect(x: 10, y: 87, width: 28, height: 58), gold, outline: true)
        oval(NSRect(x: 105, y: 87, width: 28, height: 58), gold, outline: true)
        oval(NSRect(x: 17, y: 96, width: 11, height: 37), pink.withAlphaComponent(0.45))
        oval(NSRect(x: 114, y: 96, width: 11, height: 37), pink.withAlphaComponent(0.45))
        oval(NSRect(x: 47, y: 69, width: 49, height: 28), .white.withAlphaComponent(0.65))
        // Large, bright eyes give the puppy an anime expression.
        for x in [CGFloat(43), CGFloat(85)] {
            oval(NSRect(x: x, y: 94, width: 17, height: 24), ink)
            oval(NSRect(x: x + 3, y: 106, width: 7, height: 8), .white)
            oval(NSRect(x: x + 10, y: 98, width: 3.5, height: 3.5), .white)
            oval(NSRect(x: x + 4, y: 95, width: 8, height: 4), gold.withAlphaComponent(0.8))
        }
        oval(NSRect(x: 28, y: 83, width: 18, height: 8), pink.withAlphaComponent(0.8))
        oval(NSRect(x: 99, y: 83, width: 18, height: 8), pink.withAlphaComponent(0.8))
        oval(NSRect(x: 65, y: 87, width: 14, height: 9), ink)
        oval(NSRect(x: 65, y: 72, width: 14, height: 14), pink)
        let smile = NSBezierPath()
        smile.move(to: NSPoint(x: 72, y: 86))
        smile.curve(to: NSPoint(x: 57, y: 81), controlPoint1: NSPoint(x: 68, y: 77), controlPoint2: NSPoint(x: 61, y: 77))
        smile.move(to: NSPoint(x: 72, y: 86))
        smile.curve(to: NSPoint(x: 87, y: 81), controlPoint1: NSPoint(x: 76, y: 77), controlPoint2: NSPoint(x: 83, y: 77))
        ink.setStroke(); smile.lineWidth = 2.4; smile.lineCapStyle = .round; smile.stroke()
        rounded(NSRect(x: 38, y: 56, width: 70, height: 12), green, radius: 6)
        rounded(NSRect(x: 91, y: 34, width: 12, height: 28), green, radius: 4)
    }
}

final class CompletionScene: NSView {
    var progress: CGFloat = 0
    var title: String
    var preview: Bool
    var anchor: NSPoint
    var upward: Bool
    init(frame: NSRect, title: String, preview: Bool, anchor: NSPoint, upward: Bool = true) {
        self.title = title; self.preview = preview; self.anchor = anchor; self.upward = upward
        super.init(frame: frame)
        setAccessibilityElement(true); setAccessibilityRole(.staticText)
        setAccessibilityLabel("\(preview ? "Preview: " : "")\(title) is done!")
    }
    required init?(coder: NSCoder) { fatalError("Not supported") }
    override func draw(_ dirtyRect: NSRect) {
        let p = min(max(progress, 0), 1)
        let baseY = upward ? anchor.y + 5 : anchor.y - 160
        let dogX = min(max(anchor.x - 71, 0), bounds.width - 143)
        let stage = NSRect(x: dogX, y: baseY, width: 143, height: 160)
        let context = NSGraphicsContext.current!.cgContext
        // A small opening stays at the real cursor position, anchoring the reveal.
        let portal = NSRect(x: anchor.x - 24, y: anchor.y - 3, width: 48, height: 9)
        Puppy.oval(portal, Puppy.green.withAlphaComponent(0.18 + 0.12 * (1 - p)))
        // Pause slightly at the head/paws before the body is pulled through.
        let reveal: CGFloat
        if p < 0.38 { reveal = p / 0.38 * 0.43 }
        else if p < 0.58 { reveal = 0.43 + (p - 0.38) / 0.20 * 0.07 }
        else { let t = (p - 0.58) / 0.42; reveal = 0.50 + (1 - pow(1 - t, 2)) * 0.50 }
        context.saveGState()
        context.clip(to: stage)
        context.translateBy(x: dogX, y: baseY + (upward ? -160 : 160) * (1 - reveal))
        Puppy.draw()
        context.restoreGState()
        if p > 0.25 && p < 0.94 {
            context.saveGState()
            context.setAlpha(min(1, (p - 0.25) / 0.10) * min(1, (0.94 - p) / 0.13))
            Puppy.paw(anchor.x - 33, anchor.y - 1)
            Puppy.paw(anchor.x + 7, anchor.y - 1)
            context.restoreGState()
        }
        let alpha = min(max((p - 0.84) / 0.16, 0), 1)
        guard alpha > 0 else { return }
        context.saveGState(); context.setAlpha(alpha)
        let bubbleWidth = min(CGFloat(268), bounds.width - 162)
        let right = dogX + 150 + bubbleWidth <= bounds.width
        let bubbleX = right ? dogX + 150 : max(0, dogX - bubbleWidth - 7)
        let bubbleY = min(max(baseY + 45, 12), bounds.height - 120)
        let bubble = NSRect(x: bubbleX, y: bubbleY, width: bubbleWidth, height: 112)
        let path = NSBezierPath(roundedRect: bubble, xRadius: 18, yRadius: 18)
        NSColor(calibratedRed: 1, green: 0.99, blue: 0.95, alpha: 1).setFill(); path.fill()
        Puppy.green.withAlphaComponent(0.25).setStroke(); path.lineWidth = 1; path.stroke()
        let tag = preview ? "PREVIEW · PROJECT COMPLETE" : "PROJECT COMPLETE"
        (tag as NSString).draw(at: NSPoint(x: bubbleX + 16, y: bubbleY + 85), withAttributes: [.font: NSFont.systemFont(ofSize: 9, weight: .semibold), .foregroundColor: Puppy.green])
        let paragraph = NSMutableParagraphStyle(); paragraph.lineBreakMode = .byWordWrapping
        ("“\(title)” is done!" as NSString).draw(in: NSRect(x: bubbleX + 16, y: bubbleY + 15, width: bubbleWidth - 32, height: 61), withAttributes: [.font: NSFont.systemFont(ofSize: 17, weight: .semibold), .foregroundColor: NSColor(calibratedRed: 0.17, green: 0.28, blue: 0.22, alpha: 1), .paragraphStyle: paragraph])
        context.restoreGState()
    }
}

// A pair must be close in time and space; consume each pair to avoid triple-click repeats.
struct RightClickGesture {
    var lastTime: TimeInterval?
    var lastPoint = NSPoint.zero
    mutating func receive(time: TimeInterval, point: NSPoint, interval: TimeInterval) -> Bool {
        if let previous = lastTime, time >= previous, time - previous <= interval,
           hypot(point.x - lastPoint.x, point.y - lastPoint.y) <= 14 {
            lastTime = nil; return true
        }
        lastTime = time; lastPoint = point; return false
    }
    mutating func reset() { lastTime = nil }
}

final class DogDialogPanel: NSPanel {
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { false }
}

final class Companion: NSObject, NSApplicationDelegate, WKScriptMessageHandler, WKNavigationDelegate {
    var projectURL: URL
    let initialProjectURL: URL
    var receiptURL: URL { projectURL.appendingPathComponent(".progress-pet-completion.json") }
    let preview = flag("--preview")
    let once = flag("--once")
    let duration = Double(option("--duration", fallback: "1.5")) ?? AnnouncementTiming.lifetime
    let emergence = 0.35
    var previousIDs: [String]?
    var timer: Timer?
    var animationTimer: Timer?
    var panel: NSPanel?
    var generation = 0
    var lastError: String?
    var statusItem: NSStatusItem?
    var reportPanel: DogDialogPanel?
    var dialogWeb: WKWebView?
    var dialogReady = false
    var entrance: [String: Any]?
    var catalog: [[String: Any]] = []
    var selectedID = ""
    var autoFollow = true
    var isEditing = false
    var conversationAnchor = ""
    var trackingQueue: [String] = []
    var seenTracking = Set(UserDefaults.standard.stringArray(forKey: "mochi.seenTracking") ?? [])
    var presentationToken = 0
    var trackingVisible = false
    var isDismissing = false
    var answerDelivery = AnswerDelivery()
    var answerQueue: [String] = []
    var latestSnapshot: [String: Any]?
    var seenApprovals = Set<String>()
    var seenManagedReplies = Set<String>()
    var globalRightClickMonitor: Any?
    var localRightClickMonitor: Any?
    var globalDismissMonitor: Any?
    var localDismissMonitor: Any?
    var rightClickGesture = RightClickGesture()
    var shortcutItem: NSMenuItem?
    var shortcutEnabled = true
    let shortcutPreference = "dogHub.doubleRightClick"
    var bridge: Process?
    var bridgeInput: FileHandle?
    var bridgeOutput: FileHandle?
    var bridgeBuffer = Data()
    var lastSnapshotTime: TimeInterval = 0

    init(project: URL) {
        projectURL = project; initialProjectURL = project
        super.init(); loadReceipt()
    }
    func loadReceipt() {
        previousIDs = nil
        if let data = try? Data(contentsOf: receiptURL), let receipt = try? JSONDecoder().decode(Receipt.self, from: data) { previousIDs = receipt.taskIDs }
    }
    func readProject() throws -> Project {
        let state = try JSONDecoder().decode(Project.self, from: Data(contentsOf: projectURL.appendingPathComponent(".progress-pet.json")))
        guard !state.name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty, state.name.count <= 100,
              state.tasks.count <= 1000, Set(state.tasks.map(\.id)).count == state.tasks.count,
              state.tasks.allSatisfy({ !$0.id.isEmpty && !$0.title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }) else {
            throw NSError(domain: "ProgressDog", code: 1, userInfo: [NSLocalizedDescriptionKey: "Invalid checklist"])
        }
        return state
    }
    func applicationDidFinishLaunching(_ notification: Notification) {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
        statusItem?.button?.title = "🐶"; statusItem?.button?.toolTip = "Motchi · Project companion"
        let menu = NSMenu()
        let report = menu.addItem(withTitle: "Chat with Motchi / show projects", action: #selector(toggleReport), keyEquivalent: ""); report.target = self
        shortcutEnabled = UserDefaults.standard.object(forKey: shortcutPreference) as? Bool ?? true
        shortcutItem = menu.addItem(withTitle: "Double right-click for Motchi", action: #selector(toggleShortcut), keyEquivalent: "")
        shortcutItem?.target = self; shortcutItem?.state = shortcutEnabled ? .on : .off
        let item = menu.addItem(withTitle: "Preview completion celebration", action: #selector(showPreview), keyEquivalent: ""); item.target = self
        menu.addItem(.separator())
        let quit = menu.addItem(withTitle: "Quit Progress Dog", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q"); quit.target = NSApp
        statusItem?.menu = menu
        output("Motchi 0.10.0 active: primary screen top-right; announcements \(duration)s total.")
        output("Progress Dog hub watching: \(initialProjectURL.path)")
        configureShortcut(); configureDismissal(); startBridge()
        if preview { showPreview() }
        else {
            poll()
            if flag("--preview-on-start") && panel == nil { showPreview() }
            if flag("--report-on-start") { showReport() }
            timer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in self?.poll() }
            RunLoop.main.add(timer!, forMode: .common)
        }
    }
    func startBridge() {
        guard bridge?.isRunning != true else { return }
        let script = Bundle.main.path(forResource: "dog_bridge", ofType: "py") ?? option("--bridge")
        guard !script.isEmpty else { output("Project/chat bridge is missing."); return }
        bridgeBuffer.removeAll(); bridgeOutput?.readabilityHandler = nil
        let process = Process(); process.executableURL = URL(fileURLWithPath: option("--python", fallback: "/usr/bin/python3"))
        process.arguments = [script, "--project", initialProjectURL.path]
        let input = Pipe(), outputPipe = Pipe(); process.standardInput = input; process.standardOutput = outputPipe; process.standardError = FileHandle.nullDevice
        bridgeInput = input.fileHandleForWriting; bridgeOutput = outputPipe.fileHandleForReading
        bridgeOutput?.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            DispatchQueue.main.async { self?.readBridge(data) }
        }
        do { try process.run(); bridge = process; output("Local project and chat bridge started.") }
        catch { output("Cannot start project bridge: \(error.localizedDescription)") }
    }
    func readBridge(_ data: Data) {
        guard !data.isEmpty else {
            bridgeOutput?.readabilityHandler = nil
            sendToDialog(["type": "error", "error": "Project connection closed. Reopen Motchi to reconnect."]); return
        }
        bridgeBuffer.append(data)
        while let end = bridgeBuffer.firstIndex(of: 10) {
            let line = bridgeBuffer[..<end]; bridgeBuffer.removeSubrange(...end)
            guard var value = (try? JSONSerialization.jsonObject(with: line)) as? [String: Any] else { continue }
            if value["type"] as? String == "snapshot" {
                catalog = value["items"] as? [[String: Any]] ?? []
                if !catalog.contains(where: { $0["id"] as? String == selectedID }) {
                    let match = catalog.first(where: { $0["cwd"] as? String == initialProjectURL.path }) ?? catalog.first
                    selectedID = match?["id"] as? String ?? ""
                }
                let answering = (catalog.first(where: { $0["id"] as? String == selectedID })?["questions"] as? [[String: Any]] ?? []).contains(where: { $0["canReply"] as? Bool == true })
                let recommended = value["autoSelection"] as? String ?? ""
                let hasNewTask = catalog.contains { item in
                    guard let key = item["trackingKey"] as? String else { return false }
                    return !seenTracking.contains(key)
                }
                if hasNewTask { conversationAnchor = "" }
                if autoFollow && !isEditing && !answering && conversationAnchor.isEmpty && !recommended.isEmpty { selectedID = recommended }
                var attention: String?
                var activeApprovalKeys = Set<String>()
                for item in catalog {
                    let requests = (item["approvals"] as? [[String: Any]] ?? []) + (item["questions"] as? [[String: Any]] ?? [])
                    for approval in requests {
                        let key = (item["id"] as? String ?? "") + ":" + (approval["id"] as? String ?? "")
                        activeApprovalKeys.insert(key)
                        if !seenApprovals.contains(key) {
                            seenApprovals.insert(key)
                            if attention == nil { attention = item["id"] as? String }
                        }
                    }
                }
                seenApprovals = activeApprovalKeys
                for item in catalog {
                    if let key = item["managedReplyKey"] as? String, !seenManagedReplies.contains(key), let id = item["id"] as? String {
                        seenManagedReplies.insert(key)
                        if !answerQueue.contains(id) { answerQueue.append(id) }
                    }
                }
                // New requests must surface even while a draft or another question exists.
                // The page keeps each project's draft and in-flight reply separately.
                if let attention = attention { selectedID = attention }
                adoptSelection(); value["selection"] = selectedID; value["autoFollow"] = autoFollow
                if let attention = attention { value["attentionSelection"] = attention }
                latestSnapshot = value
                sendToDialog(value)
                if attention != nil {
                    output("Codex question or approval attention popup for a connected project.")
                    showDialog()
                }
                for item in catalog where item["status"] as? String == "active" {
                    if let key = item["trackingKey"] as? String, !seenTracking.contains(key), let id = item["id"] as? String {
                        seenTracking.insert(key); trackingQueue.append(id)
                    }
                }
                UserDefaults.standard.set(Array(seenTracking.suffix(1000)), forKey: "mochi.seenTracking")
                showNextAnswer()
                showNextTracking()
                checkAllCompletions()
            } else {
                sendToDialog(value)
                if value["type"] as? String == "answer", let id = value["requestId"] as? String,
                   let selection = value["selection"] as? String,
                   answerDelivery.finish(id: id, selection: selection) {
                    let target = value["routedSelection"] as? String ?? selection
                    if value["action"] as? String == "askApproval" {
                        selectedID = target; adoptSelection(); showDialog()
                        sendToDialog(["type": "showAnswer", "selection": target]); continue
                    }
                    let alreadyReading = reportPanel?.isVisible == true && !trackingVisible && !isDismissing && selectedID == target
                    if !alreadyReading && !answerQueue.contains(target) { answerQueue.append(target) }
                    showNextAnswer()
                }
            }
        }
    }
    func requestBridge(_ value: [String: Any]) {
        guard let bridge = bridge, bridge.isRunning,
              var data = try? JSONSerialization.data(withJSONObject: value) else { return }
        data.append(10)
        do { try bridgeInput?.write(contentsOf: data) }
        catch { output("Project bridge disconnected.") }
    }
    func sendToDialog(_ value: [String: Any]) {
        guard dialogReady, let data = try? JSONSerialization.data(withJSONObject: value), let json = String(data: data, encoding: .utf8) else { return }
        dialogWeb?.evaluateJavaScript("window.receive(\(json))", completionHandler: nil)
    }
    func adoptSelection() {
        if let cwd = catalog.first(where: { $0["id"] as? String == selectedID })?["cwd"] as? String, cwd != projectURL.path {
            projectURL = URL(fileURLWithPath: cwd, isDirectory: true); loadReceipt()
        }
    }
    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.frameInfo.isMainFrame, let value = message.body as? [String: Any] else { return }
        switch value["action"] as? String {
        case "ready":
            dialogReady = true
            if let latestSnapshot = latestSnapshot { sendToDialog(latestSnapshot) }
            presentEntrance()
            refreshReport(force: true)
        case "dismiss": hideReport()
        case "select":
            if let selected = value["selection"] as? String, catalog.contains(where: { $0["id"] as? String == selected }) {
                selectedID = selected; autoFollow = value["autoFollow"] as? Bool ?? false; adoptSelection()
                if value["keepConversation"] as? Bool == true, let recommended = latestSnapshot?["autoSelection"] as? String {
                    conversationAnchor = catalog.first(where: { $0["id"] as? String == recommended })?["trackingKey"] as? String ?? recommended
                } else { conversationAnchor = "" }
            }
        case "follow": autoFollow = value["autoFollow"] as? Bool ?? true; conversationAnchor = ""; refreshReport(force: true)
        case "editing": isEditing = value["editing"] as? Bool ?? false
        case "ask", "replyQuestion", "askApproval", "decideApproval", "startTask", "sendTurn", "stopTask", "addWork", "addChecklist", "setChecklistDone", "undoChecklistChange", "retryWork":
            if let selected = value["selection"] as? String, catalog.contains(where: { $0["id"] as? String == selected }) {
                if ["ask", "askApproval"].contains(value["action"] as? String ?? ""), let id = value["requestId"] as? String {
                    answerDelivery.begin(id: id, selection: selected)
                }
                requestBridge(value)
            }
        case "refresh": requestBridge(["action": "refresh"])
        case "openThread":
            if let tid = value["threadId"] as? String, UUID(uuidString: tid) != nil,
               catalog.contains(where: { $0["threadId"] as? String == tid }), let url = URL(string: "codex://threads/\(tid)") {
                NSWorkspace.shared.open(url)
            }
        default: break
        }
    }
    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        let scheme = navigationAction.request.url?.scheme
        decisionHandler(scheme == "file" || scheme == "about" ? .allow : .cancel)
    }
    func configureShortcut() {
        if let monitor = globalRightClickMonitor { NSEvent.removeMonitor(monitor) }
        if let monitor = localRightClickMonitor { NSEvent.removeMonitor(monitor) }
        globalRightClickMonitor = nil; localRightClickMonitor = nil; rightClickGesture.reset()
        guard shortcutEnabled else { return }
        globalRightClickMonitor = NSEvent.addGlobalMonitorForEvents(matching: .rightMouseUp) { [weak self] event in self?.receiveRightClick(event) }
        localRightClickMonitor = NSEvent.addLocalMonitorForEvents(matching: .rightMouseUp) { [weak self] event in self?.receiveRightClick(event); return event }
        output(globalRightClickMonitor == nil ? "Cursor shortcut unavailable; use the dog menu." : "Double right-click shortcut enabled.")
    }
    func configureDismissal() {
        let mask: NSEvent.EventTypeMask = [.leftMouseDown, .rightMouseDown, .otherMouseDown]
        globalDismissMonitor = NSEvent.addGlobalMonitorForEvents(matching: mask) { [weak self] _ in self?.hideReport() }
        localDismissMonitor = NSEvent.addLocalMonitorForEvents(matching: mask) { [weak self] event in
            if event.window !== self?.reportPanel { self?.hideReport() }; return event
        }
    }
    func receiveRightClick(_ event: NSEvent) {
        if rightClickGesture.receive(time: event.timestamp, point: NSEvent.mouseLocation, interval: NSEvent.doubleClickInterval) { showReport() }
    }
    @objc func toggleReport() { if reportPanel?.isVisible == true && !isDismissing { hideReport() } else { showReport() } }
    @objc func toggleShortcut() {
        shortcutEnabled.toggle(); shortcutItem?.state = shortcutEnabled ? .on : .off
        UserDefaults.standard.set(shortcutEnabled, forKey: shortcutPreference); configureShortcut()
    }
    func hideReport(animated: Bool = true) {
        guard !isDismissing || !animated else { return }
        answerDelivery.dismiss()
        presentationToken += 1; trackingVisible = false
        guard let window = reportPanel, window.isVisible else { return }
        guard animated, dialogReady, !NSWorkspace.shared.accessibilityDisplayShouldReduceMotion else {
            isDismissing = false; window.orderOut(nil); return
        }
        isDismissing = true
        let token = presentationToken
        // Outside clicks, Escape, close and the menu share the same return leap.
        dialogWeb?.evaluateJavaScript("window.departMochi()", completionHandler: nil)
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.78) { [weak self] in
            guard let self = self, self.presentationToken == token, self.isDismissing else { return }
            self.isDismissing = false; self.reportPanel?.orderOut(nil)
            self.outputDismissal()
        }
    }
    func outputDismissal() { output("Motchi dismissal finished: return leap, then close.") }
    func showNextAnswer() {
        guard !answerQueue.isEmpty, !hasPendingAttention,
              reportPanel?.isVisible != true || trackingVisible || isDismissing else { return }
        let target = answerQueue.removeFirst()
        guard catalog.contains(where: { $0["id"] as? String == target }) else { return }
        selectedID = target; adoptSelection()
        conversationAnchor = catalog.first(where: { $0["id"] as? String == target })?["trackingKey"] as? String ?? target
        showDialog()
        sendToDialog(["type": "showAnswer", "selection": target])
        output("Motchi returned at top right with the requested answer.")
    }
    func showNextTracking() {
        guard reportPanel?.isVisible != true, panel?.isVisible != true, !trackingQueue.isEmpty,
              !hasPendingAttention else { return }
        let id = trackingQueue.removeFirst()
        guard let item = catalog.first(where: { $0["id"] as? String == id }), item["status"] as? String == "active",
              (item["questions"] as? [[String: Any]] ?? []).isEmpty, (item["approvals"] as? [[String: Any]] ?? []).isEmpty else { return }
        showDialog(trackingTitle: item["title"] as? String ?? "this project")
        output("Tracking task automatically: \(item["title"] as? String ?? "project")")
    }
    func scheduleTrackingDismissal(token: Int) {
        let reduced = NSWorkspace.shared.accessibilityDisplayShouldReduceMotion
        DispatchQueue.main.asyncAfter(deadline: .now() + (reduced ? duration : AnnouncementTiming.fadeStart(lifetime: duration))) { [weak self] in
            guard let self = self, self.presentationToken == token, self.trackingVisible else { return }
            if reduced { self.hideReport(animated: false); self.showNextTracking(); return }
            self.dialogWeb?.evaluateJavaScript("window.departMochi()", completionHandler: nil)
            DispatchQueue.main.asyncAfter(deadline: .now() + AnnouncementTiming.fade) { [weak self] in
                guard let self = self, self.presentationToken == token, self.trackingVisible else { return }
                self.hideReport(animated: false)
                self.showNextTracking()
            }
        }
    }
    func checkAllCompletions() {
        var visited = Set<String>()
        for item in catalog {
            guard let cwd = item["cwd"] as? String, !visited.contains(cwd) else { continue }
            visited.insert(cwd)
            let base = URL(fileURLWithPath: cwd, isDirectory: true)
            guard let data = try? Data(contentsOf: base.appendingPathComponent(".progress-pet.json")),
                  let state = try? JSONDecoder().decode(Project.self, from: data), !state.tasks.isEmpty,
                  !state.name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty, state.name.count <= 100,
                  state.tasks.count <= 1000, Set(state.tasks.map(\.id)).count == state.tasks.count,
                  state.tasks.allSatisfy({ !$0.id.isEmpty && !$0.title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }) else { continue }
            let receipt = base.appendingPathComponent(".progress-pet-completion.json")
            let saved = (try? Data(contentsOf: receipt)).flatMap { try? JSONDecoder().decode(Receipt.self, from: $0) }
            let ids = state.tasks.map(\.id).sorted()
            if state.tasks.allSatisfy(\.done) {
                if ids != saved?.taskIDs && canCelebrate {
                    try? JSONEncoder().encode(Receipt(taskIDs: ids)).write(to: receipt, options: .atomic)
                    if cwd == projectURL.path { previousIDs = ids }
                    show(name: state.name, isPreview: false)
                    break
                }
            } else if saved?.taskIDs != nil {
                try? JSONEncoder().encode(Receipt(taskIDs: nil)).write(to: receipt, options: .atomic)
                if cwd == projectURL.path { previousIDs = nil }
            }
        }
    }
    var hasPendingAttention: Bool {
        catalog.contains { !(($0["questions"] as? [[String: Any]] ?? []) + ($0["approvals"] as? [[String: Any]] ?? [])).isEmpty }
    }
    var canCelebrate: Bool { !hasPendingAttention && reportPanel?.isVisible != true && panel?.isVisible != true }
    func presentEntrance() {
        guard dialogReady, let entrance = entrance,
              let data = try? JSONSerialization.data(withJSONObject: entrance),
              let json = String(data: data, encoding: .utf8) else { return }
        let token = presentationToken
        dialogWeb?.evaluateJavaScript("window.presentMochi(\(json))") { [weak self] _, error in
            guard let self = self, self.presentationToken == token, !self.isDismissing, error == nil else { return }
            self.reportPanel?.alphaValue = 1
            if self.trackingVisible { self.scheduleTrackingDismissal(token: token) }
        }
    }
    @objc func showReport() {
        showDialog()
    }
    func showDialog(trackingTitle: String? = nil) {
        presentationToken += 1; trackingVisible = trackingTitle != nil; isDismissing = false
        startBridge()
        guard let screen = NSScreen.screens.first ?? NSScreen.main else { return }
        let area = screen.visibleFrame.insetBy(dx: 7, dy: 7)
        let frame: NSRect
        if trackingTitle != nil { frame = trackingFrame(in: area) }
        else {
            let size = NSSize(width: min(570, area.width), height: min(590, area.height))
            frame = NSRect(x: area.maxX - size.width, y: area.maxY - size.height, width: size.width, height: size.height)
        }
        let size = frame.size, x = frame.minX, y = frame.minY
        entrance = ["x": 65, "y": 158,
                    "mode": trackingTitle == nil ? "chat" : "tracking",
                    "placement": "topRight",
                    "projectTitle": trackingTitle ?? "",
                    "reduceMotion": NSWorkspace.shared.accessibilityDisplayShouldReduceMotion]
        if reportPanel == nil {
            let window = DogDialogPanel(contentRect: NSRect(origin: NSPoint(x: x, y: y), size: size), styleMask: [.borderless, .nonactivatingPanel], backing: .buffered, defer: false)
            window.isOpaque = false; window.backgroundColor = .clear; window.hasShadow = false; window.level = .statusBar
            window.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .ignoresCycle, .stationary]
            window.ignoresMouseEvents = false; window.hidesOnDeactivate = false; window.isReleasedWhenClosed = false
            let config = WKWebViewConfiguration(); config.userContentController.add(self, name: "dog")
            let web = WKWebView(frame: NSRect(origin: .zero, size: size), configuration: config)
            web.navigationDelegate = self; web.autoresizingMask = [.width, .height]; web.setValue(false, forKey: "drawsBackground")
            web.underPageBackgroundColor = .clear
            window.contentView = web; reportPanel = window; dialogWeb = web
            let path = Bundle.main.path(forResource: "dialog", ofType: "html") ?? option("--dialog")
            if !path.isEmpty { let url = URL(fileURLWithPath: path); web.loadFileURL(url, allowingReadAccessTo: url.deletingLastPathComponent()) }
        }
        guard let window = reportPanel else { return }
        if trackingTitle == nil { generation += 1; animationTimer?.invalidate(); panel?.orderOut(nil) }
        window.ignoresMouseEvents = trackingTitle != nil
        window.alphaValue = 0
        window.setFrame(NSRect(origin: NSPoint(x: x, y: y), size: size), display: false)
        presentEntrance()
        window.orderFrontRegardless(); refreshReport(force: true)
        output("Motchi 0.10.0 opened at primary screen top right: \(trackingTitle != nil ? "1.5-second tracking announcement" : "Codex dialog").")
    }
    func refreshReport(force: Bool = false) {
        let now = ProcessInfo.processInfo.systemUptime
        if force || now - lastSnapshotTime >= 2 { lastSnapshotTime = now; requestBridge(["action": "snapshot"]) }
    }
    func applicationWillTerminate(_ notification: Notification) {
        for monitor in [globalRightClickMonitor, localRightClickMonitor, globalDismissMonitor, localDismissMonitor] { if let monitor = monitor { NSEvent.removeMonitor(monitor) } }
        bridgeOutput?.readabilityHandler = nil; try? bridgeInput?.close(); bridge?.terminate()
    }
    @objc func showPreview() { show(name: (try? readProject().name) ?? "My project", isPreview: true) }
    func saveReceipt(_ ids: [String]?) {
        do { try JSONEncoder().encode(Receipt(taskIDs: ids)).write(to: receiptURL, options: .atomic) }
        catch { output("Could not persist completion receipt: \(error.localizedDescription)") }
    }
    func poll() {
        startBridge()
        refreshReport()
        let lock = option("--lock")
        if FileManager.default.fileExists(atPath: lock + ".stop") {
            try? FileManager.default.removeItem(atPath: lock + ".stop")
            output("Progress Dog stopped."); NSApp.terminate(nil); return
        }
        if FileManager.default.fileExists(atPath: lock + ".report") {
            try? FileManager.default.removeItem(atPath: lock + ".report"); showReport()
        }
        guard FileManager.default.fileExists(atPath: projectURL.appendingPathComponent(".progress-pet.json").path) else { return }
        do {
            let state = try readProject(); lastError = nil
            let complete = !state.tasks.isEmpty && state.tasks.allSatisfy(\.done)
            if !complete {
                if previousIDs != nil { previousIDs = nil; saveReceipt(nil); generation += 1; animationTimer?.invalidate(); panel?.orderOut(nil) }
                return
            }
            let ids = state.tasks.map(\.id).sorted()
            guard ids != previousIDs, canCelebrate else { return }
            previousIDs = ids; saveReceipt(ids); show(name: state.name, isPreview: false)
        } catch {
            let message = error.localizedDescription
            if lastError != message { output("Waiting for a valid checklist: \(message)"); lastError = message }
        }
    }
    func show(name: String, isPreview: Bool) {
        hideReport(animated: false)
        generation += 1; let current = generation
        animationTimer?.invalidate(); panel?.orderOut(nil)
        guard let screen = NSScreen.screens.first ?? NSScreen.main else { output("No desktop screen available"); return }
        let area = screen.visibleFrame.insetBy(dx: 8, dy: 8)
        let size = NSSize(width: min(440, area.width), height: min(210, area.height))
        let upward = true
        let x = area.maxX - size.width
        let y = area.maxY - size.height
        let window = NSPanel(contentRect: NSRect(origin: NSPoint(x: x, y: y), size: size), styleMask: [.borderless, .nonactivatingPanel], backing: .buffered, defer: false)
        window.isOpaque = false; window.backgroundColor = .clear; window.hasShadow = false; window.level = .statusBar
        window.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .ignoresCycle, .stationary]
        window.ignoresMouseEvents = true; window.hidesOnDeactivate = false; window.isReleasedWhenClosed = false
        window.setAccessibilityLabel("\(isPreview ? "Preview: " : "")Project completion: \(name) is done")
        let scene = CompletionScene(frame: NSRect(origin: .zero, size: size), title: name, preview: isPreview, anchor: NSPoint(x: 72, y: 12), upward: upward)
        window.contentView = scene; panel = window
        let reduced = NSWorkspace.shared.accessibilityDisplayShouldReduceMotion
        scene.progress = reduced ? 1 : 0
        window.orderFrontRegardless()
        if !reduced {
            let start = ProcessInfo.processInfo.systemUptime
            animationTimer = Timer.scheduledTimer(withTimeInterval: 1.0 / 60, repeats: true) { [weak self, weak scene] animation in
                guard let self = self, let scene = scene, self.generation == current else { animation.invalidate(); return }
                scene.progress = min(1, (ProcessInfo.processInfo.systemUptime - start) / self.emergence)
                scene.needsDisplay = true
                if scene.progress >= 1 { animation.invalidate() }
            }
        }
        output("\(isPreview ? "Preview" : "Celebration"): \(name) is done!")
        DispatchQueue.main.asyncAfter(deadline: .now() + (reduced ? duration : AnnouncementTiming.fadeStart(lifetime: duration))) { [weak self] in
            guard let self = self, self.generation == current else { return }
            NSAnimationContext.runAnimationGroup({ context in context.duration = reduced ? 0 : AnnouncementTiming.fade; window.animator().alphaValue = 0 }, completionHandler: {
                window.orderOut(nil)
                if self.preview || (self.once && !isPreview) { NSApp.terminate(nil) }
            })
        }
    }
}

if flag("--self-test") {
    var gesture = RightClickGesture()
    func check(_ condition: Bool, _ label: String) { if !condition { fatalError(label) } }
    let p = NSPoint(x: 100, y: 100)
    check(!gesture.receive(time: 1, point: p, interval: 0.5), "single click")
    check(gesture.receive(time: 1.2, point: p, interval: 0.5), "double click")
    check(!gesture.receive(time: 1.3, point: p, interval: 0.5), "triple click must not repeat")
    gesture.reset()
    check(!gesture.receive(time: 2, point: p, interval: 0.5), "first slow click")
    check(!gesture.receive(time: 2.8, point: p, interval: 0.5), "slow clicks do not trigger")
    check(!gesture.receive(time: 3, point: NSPoint(x: 180, y: 100), interval: 0.5), "distant clicks do not trigger")
    check(gesture.receive(time: 3.1, point: NSPoint(x: 181, y: 100), interval: 0.5), "nearby pair triggers")
    gesture.reset()
    check(!gesture.receive(time: 4, point: p, interval: 0.5), "reset clears prior click")
    let screenArea = NSRect(x: -1440, y: 25, width: 1440, height: 875)
    let frame = trackingFrame(in: screenArea)
    check(frame.maxX == screenArea.maxX && frame.maxY == screenArea.maxY, "tracking pins to the selected display's top right")
    check(frame.width == 440 && frame.height == 195, "tracking is compact")
    check(screenArea.contains(frame), "tracking stays inside usable screen bounds")
    check(trackingFrame(in: NSRect(x: 0, y: 0, width: 320, height: 180)).size == NSSize(width: 320, height: 180), "small displays clamp the toast")
    var delivery = AnswerDelivery()
    delivery.begin(id: "one", selection: "project-a")
    check(!delivery.finish(id: "one", selection: "project-a"), "visible answers do not create a return popup")
    delivery.begin(id: "two", selection: "project-a"); delivery.dismiss()
    check(!delivery.finish(id: "two", selection: "project-b"), "a mismatched project cannot consume an answer notification")
    check(delivery.finish(id: "two", selection: "project-a"), "a dismissed question returns when its answer arrives")
    check(!delivery.finish(id: "two", selection: "project-a"), "duplicate answers do not reopen Motchi")
    delivery.begin(id: "three", selection: "project-a"); delivery.begin(id: "four", selection: "project-b"); delivery.dismiss()
    check(delivery.finish(id: "four", selection: "project-b") && delivery.finish(id: "three", selection: "project-a"), "concurrent replies retain their project routing")
    check(AnnouncementTiming.fadeStart(lifetime: AnnouncementTiming.lifetime) == 1.3, "announcement fade begins at 1.3 seconds")
    check(AnnouncementTiming.fadeStart(lifetime: AnnouncementTiming.lifetime) + AnnouncementTiming.fade == 1.5, "announcement lifetime includes fade and totals 1.5 seconds")
    output("19 shortcut, placement, answer delivery and announcement timing checks passed"); exit(0)
}
// Rendering our own scene provides deterministic visual QA without recording the desktop.
let renderPath = option("--render-preview")
if !renderPath.isEmpty {
    let folder = URL(fileURLWithPath: renderPath, isDirectory: true)
    try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
    let scene = CompletionScene(frame: NSRect(x: 0, y: 0, width: 440, height: 210), title: "Website launch", preview: false, anchor: NSPoint(x: 72, y: 12))
    for step in 0...56 {
        let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: 880, pixelsHigh: 420, bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
        NSGraphicsContext.saveGraphicsState(); NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: bitmap)
        let context = NSGraphicsContext.current!.cgContext; context.scaleBy(x: 2, y: 2)
        NSColor(calibratedRed: 0.96, green: 0.97, blue: 0.93, alpha: 1).setFill(); NSBezierPath(rect: scene.bounds).fill()
        scene.progress = CGFloat(step) / 56; scene.draw(scene.bounds)
        NSGraphicsContext.restoreGraphicsState()
        try bitmap.representation(using: .png, properties: [:])!.write(to: folder.appendingPathComponent(String(format: "frame-%02d.png", step)))
    }
    output("Rendered 57 slow-reveal frames: \(renderPath)"); exit(0)
}

let projectPath = option("--project")
guard !projectPath.isEmpty else { output("Missing --project"); exit(1) }
// Replacement is scoped to this project's own Progress Pet/Progress Dog processes.
if flag("--replace") {
    let _ = NSApplication.shared
    let prefix = option("--replace-prefix")
    if prefix == "local.progress-pet.hub" {
        let previous = NSWorkspace.shared.runningApplications.filter { app in
            guard app.processIdentifier != getpid(), let id = app.bundleIdentifier else { return false }
            return id.hasPrefix("local.progress-pet.hub.") || id.hasPrefix("local.progress-pet.completion.p")
        }
        previous.forEach { _ = $0.terminate() }
        let deadline = Date().addingTimeInterval(5)
        while previous.contains(where: { !$0.isTerminated }) && Date() < deadline { RunLoop.current.run(until: Date().addingTimeInterval(0.1)) }
    }
}
var lockDescriptor: Int32 = -1
if !flag("--preview") {
    let lockPath = option("--lock")
    try? FileManager.default.createDirectory(at: URL(fileURLWithPath: lockPath).deletingLastPathComponent(), withIntermediateDirectories: true)
    lockDescriptor = open(lockPath, O_CREAT | O_RDWR, S_IRUSR | S_IWUSR)
    guard lockDescriptor >= 0, flock(lockDescriptor, LOCK_EX | LOCK_NB) == 0 else { output("A Completion Pet watcher is already running for this project."); exit(0) }
    try? FileManager.default.removeItem(atPath: lockPath + ".stop")
}
signal(SIGPIPE, SIG_IGN)
let app = NSApplication.shared; app.setActivationPolicy(.accessory)
let companion = Companion(project: URL(fileURLWithPath: projectPath, isDirectory: true))
app.delegate = companion; app.run()
