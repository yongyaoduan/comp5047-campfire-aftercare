import AppKit
import AVFoundation
import Vision

final class CameraViewController: NSViewController, AVCaptureVideoDataOutputSampleBufferDelegate {
    private let captureSession = AVCaptureSession()
    private let processingQueue = DispatchQueue(label: "campfire.vision.processing")
    private let preview = CameraPreviewView()
    private let statusLabel = NSTextField(labelWithString: "Waiting for camera permission…")
    private let detailLabel = NSTextField(labelWithString: "Detecting people, waves and both heart gestures")
    private let bluetoothLabel = NSTextField(labelWithString: "Bluetooth: starting…")
    private let gestureLabel = NSTextField(labelWithString: "")
    private let logView = NSTextView()
    private let waveDetector = WaveDetector()
    private let heartDetector = HeartDetector()
    private let presenceFilter = PresenceFilter()
    private let bluetooth = BluetoothBridge()
    private let dryRun = ProcessInfo.processInfo.arguments.contains("--dry-run")

    private var frameNumber = 0
    private var lastHumanBoxes: [CGRect] = []
    private var lastHumanSeenAt: TimeInterval = -100
    private var humanPositiveFrames = 0
    private var presence = false
    private var waveCount = 0
    private var heartCount = 0
    private var lastHeartStatusSentAt: TimeInterval = -100
    private var announcementTimer: Timer?
    private var lastHumanAnnouncementAt: TimeInterval = -100
    private var announcedPresence = false
    private var didStart = false
    // Written on the vision queue, read by the main-thread timer (a Double is fine for a watchdog).
    private var lastFrameAt: TimeInterval = -100
    private var visionStale = false

    override func loadView() {
        view = NSView()
        buildInterface()
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        startIfNeeded()
    }

    override func viewDidAppear() {
        super.viewDidAppear()
        startIfNeeded()
    }

    private func startIfNeeded() {
        guard !didStart else { return }
        didStart = true
        configureBluetoothCallbacks()
        startAnnouncementTimer()
        requestCameraAndStart()
    }

    override func viewWillDisappear() {
        captureSession.stopRunning()
        bluetooth.sendStopAll()
        announcementTimer?.invalidate()
        announcementTimer = nil
        super.viewWillDisappear()
    }

    private func buildInterface() {
        preview.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(preview)

        let sidePanel = NSStackView()
        sidePanel.orientation = .vertical
        sidePanel.alignment = .leading
        sidePanel.spacing = 14
        sidePanel.edgeInsets = NSEdgeInsets(top: 20, left: 18, bottom: 20, right: 18)
        sidePanel.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(sidePanel)

        statusLabel.font = .systemFont(ofSize: 25, weight: .bold)
        statusLabel.textColor = .secondaryLabelColor
        statusLabel.maximumNumberOfLines = 2
        statusLabel.lineBreakMode = .byWordWrapping
        statusLabel.translatesAutoresizingMaskIntoConstraints = false

        detailLabel.font = .systemFont(ofSize: 13)
        detailLabel.textColor = .secondaryLabelColor
        detailLabel.maximumNumberOfLines = 0
        detailLabel.lineBreakMode = .byWordWrapping

        bluetoothLabel.font = .systemFont(ofSize: 13, weight: .medium)
        bluetoothLabel.textColor = .secondaryLabelColor
        bluetoothLabel.maximumNumberOfLines = 2
        bluetoothLabel.lineBreakMode = .byWordWrapping

        gestureLabel.font = .systemFont(ofSize: 20, weight: .semibold)
        gestureLabel.textColor = .systemBlue
        gestureLabel.maximumNumberOfLines = 2
        gestureLabel.lineBreakMode = .byWordWrapping

        let explanation = NSTextField(wrappingLabelWithString:
            (dryRun ? "DRY RUN: hardware outputs are disabled. " : "") +
            "Person visible: green ON. Two-hand heart: \"I love you too\", and the pump runs while the heart is held and the bowl is hot. Release takes about 0.3 seconds; the Mac continuously confirms a held heart."
        )
        explanation.textColor = .secondaryLabelColor

        let divider = NSBox()
        divider.boxType = .separator

        let logTitle = NSTextField(labelWithString: "Event Log")
        logTitle.font = .systemFont(ofSize: 14, weight: .semibold)

        logView.isEditable = false
        logView.font = .monospacedSystemFont(ofSize: 11, weight: .regular)
        logView.backgroundColor = NSColor.textBackgroundColor
        let scrollView = NSScrollView()
        scrollView.documentView = logView
        scrollView.hasVerticalScroller = true
        scrollView.borderType = .bezelBorder
        scrollView.translatesAutoresizingMaskIntoConstraints = false

        for item in [statusLabel, detailLabel, bluetoothLabel, gestureLabel, explanation, divider, logTitle, scrollView] {
            sidePanel.addArrangedSubview(item)
        }

        NSLayoutConstraint.activate([
            preview.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            preview.topAnchor.constraint(equalTo: view.topAnchor),
            preview.bottomAnchor.constraint(equalTo: view.bottomAnchor),
            preview.widthAnchor.constraint(equalTo: view.widthAnchor, multiplier: 0.70),

            sidePanel.leadingAnchor.constraint(equalTo: preview.trailingAnchor),
            sidePanel.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            sidePanel.topAnchor.constraint(equalTo: view.topAnchor),
            sidePanel.bottomAnchor.constraint(equalTo: view.bottomAnchor),

            statusLabel.widthAnchor.constraint(equalTo: sidePanel.widthAnchor, constant: -36),
            detailLabel.widthAnchor.constraint(equalTo: statusLabel.widthAnchor),
            bluetoothLabel.widthAnchor.constraint(equalTo: statusLabel.widthAnchor),
            gestureLabel.widthAnchor.constraint(equalTo: statusLabel.widthAnchor),
            explanation.widthAnchor.constraint(equalTo: statusLabel.widthAnchor),
            divider.widthAnchor.constraint(equalTo: statusLabel.widthAnchor),
            scrollView.widthAnchor.constraint(equalTo: statusLabel.widthAnchor),
            scrollView.heightAnchor.constraint(greaterThanOrEqualToConstant: 260)
        ])
    }

    private func configureBluetoothCallbacks() {
        bluetooth.onStatusChange = { [weak self] status in
            self?.bluetoothLabel.stringValue = status
            self?.bluetoothLabel.textColor = status.contains("connected") ? .systemGreen : .secondaryLabelColor
        }
        bluetooth.onLog = { [weak self] message in
            self?.appendLog(message)
        }
    }

    private func startAnnouncementTimer() {
        announcementTimer?.invalidate()
        announcementTimer = Timer.scheduledTimer(withTimeInterval: 0.25, repeats: true) { [weak self] _ in
            self?.announceHumanIfNeeded()
        }
    }

    private func announceHumanIfNeeded() {
        // Final FireBeetle firmware treats the link as lost after 2 s of silence,
        // so the current presence (present OR absent) is refreshed every second.
        let now = ProcessInfo.processInfo.systemUptime
        // Frozen camera or vision: like the Pi, send STOP instead of repeating an
        // old "person present", so the firmware never trusts a stale picture.
        if now - lastFrameAt > 2 {
            if !visionStale { appendLog("Camera/vision stalled for 2 s — sending STOP") }
            visionStale = true
            if now - lastHumanAnnouncementAt >= 0.3 {
                lastHumanAnnouncementAt = now
                bluetooth.sendStopAll()
            }
            return
        }
        if visionStale { visionStale = false; appendLog("Camera/vision resumed") }
        guard now - lastHumanAnnouncementAt >= 1 else { return }
        lastHumanAnnouncementAt = now
        bluetooth.sendPresence(announcedPresence)
    }

    private func requestCameraAndStart() {
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized:
            configureCaptureSession()
        case .notDetermined:
            AVCaptureDevice.requestAccess(for: .video) { [weak self] granted in
                DispatchQueue.main.async {
                    granted ? self?.configureCaptureSession() : self?.showCameraDenied()
                }
            }
        default:
            showCameraDenied()
        }
    }

    /// The Brio 100 (or any external USB camera) is preferred over the built-in
    /// FaceTime camera, because the webcam is mounted on the station.
    static func preferredCamera() -> AVCaptureDevice? {
        let session = AVCaptureDevice.DiscoverySession(
            deviceTypes: [.external, .builtInWideAngleCamera], mediaType: .video, position: .unspecified)
        return session.devices.first { $0.deviceType == .external } ?? session.devices.first
            ?? AVCaptureDevice.default(for: .video)
    }

    private func showCameraDenied() {
        statusLabel.stringValue = "Camera Access Denied"
        detailLabel.stringValue = "Open System Settings → Privacy & Security → Camera, enable Campfire LED Demo, and then reopen the app."
        statusLabel.textColor = .systemRed
    }

    private func configureCaptureSession() {
        guard !captureSession.isRunning else { return }
        captureSession.beginConfiguration()
        captureSession.sessionPreset = .high

        guard let camera = Self.preferredCamera(),
              let input = try? AVCaptureDeviceInput(device: camera),
              captureSession.canAddInput(input) else {
            captureSession.commitConfiguration()
            statusLabel.stringValue = "No Camera Available"
            return
        }
        captureSession.addInput(input)

        let output = AVCaptureVideoDataOutput()
        output.alwaysDiscardsLateVideoFrames = true
        output.videoSettings = [
            kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA
        ]
        output.setSampleBufferDelegate(self, queue: processingQueue)
        guard captureSession.canAddOutput(output) else {
            captureSession.commitConfiguration()
            statusLabel.stringValue = "Unable to Read Camera Video"
            return
        }
        captureSession.addOutput(output)
        captureSession.commitConfiguration()

        preview.previewLayer.session = captureSession
        appendLog("Camera started; human detection is active")
        statusLabel.stringValue = "No Human Detected"
        statusLabel.textColor = .systemOrange
        processingQueue.async { [weak self] in self?.captureSession.startRunning() }
    }

    func captureOutput(
        _ output: AVCaptureOutput,
        didOutput sampleBuffer: CMSampleBuffer,
        from connection: AVCaptureConnection
    ) {
        guard let pixelBuffer = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }
        let now = ProcessInfo.processInfo.systemUptime
        frameNumber += 1
        lastFrameAt = now

        // People every 5th frame, hands every 3rd (and on every people frame, so
        // a visible hand also counts as presence). Pose runs for the on-screen
        // wave log only.
        let shouldDetectHumans = frameNumber % 5 == 0
        let shouldDetectHands = frameNumber % 3 == 0 || shouldDetectHumans
        let handler = VNImageRequestHandler(cvPixelBuffer: pixelBuffer, orientation: .up, options: [:])
        let poseRequest = VNDetectHumanBodyPoseRequest()
        let result: VisionPipeline.Frame
        do {
            result = try VisionPipeline.analyze(handler, people: shouldDetectHumans, hands: shouldDetectHands)
            try handler.perform([poseRequest])
        } catch {
            DispatchQueue.main.async { [weak self] in
                self?.appendLog("Vision processing error: \(error.localizedDescription)")
            }
            return
        }

        if shouldDetectHumans {
            updatePresence(boxes: result.personBoxes, handSeen: result.handSeen, now: now)
        }

        var wrists: [CGPoint] = []
        if let observation = poseRequest.results?.max(by: { $0.confidence < $1.confidence }) {
            wrists = processPose(observation, now: now)
        }

        var heartTips: [CGPoint] = []
        if shouldDetectHands {
            let hands = result.hands
            for hand in hands { heartTips.append(contentsOf: [hand.indexTip, hand.thumbTip]) }
            let heartUpdate = heartDetector.observe(hands, at: now)
            if let gesture = heartUpdate.started {
                lastHeartStatusSentAt = now
                DispatchQueue.main.async { [weak self] in
                    self?.handleHeartStarted(gesture)
                }
            } else if heartUpdate.active != nil, now - lastHeartStatusSentAt >= 0.2 {
                lastHeartStatusSentAt = now
                DispatchQueue.main.async { [weak self] in _ = self?.bluetooth.sendHeartOn() }
            }
            if heartUpdate.ended {
                lastHeartStatusSentAt = now
                DispatchQueue.main.async { [weak self] in self?.handleHeartEnded() }
            } else if heartUpdate.active == nil, now - lastHeartStatusSentAt >= 0.3 {
                lastHeartStatusSentAt = now
                DispatchQueue.main.async { [weak self] in self?.bluetooth.sendHeartOff() }
            }
        }

        let boxesForDisplay = lastHumanBoxes
        DispatchQueue.main.async { [weak self] in
            self?.preview.show(humans: boxesForDisplay, wrists: wrists, heartTips: heartTips)
        }
    }

    private func updatePresence(boxes: [CGRect], handSeen: Bool, now: TimeInterval) {
        lastHumanBoxes = boxes
        // 2 s of continuous detection to report a person, 2 s without to report nobody.
        if let change = presenceFilter.observe(!boxes.isEmpty || handSeen, at: now) {
            presence = change
            publishPresence(change)
        }
    }

    private func publishPresence(_ isPresent: Bool) {
        DispatchQueue.main.async { [weak self] in
            guard let self else { return }
            self.announcedPresence = isPresent
            self.statusLabel.stringValue = isPresent ? "Human Detected" : "No Human Detected"
            self.statusLabel.textColor = isPresent ? .systemGreen : .systemOrange
            self.appendLog(isPresent ? "Human detected" : "Human left the camera view")
            if isPresent {
                self.lastHumanAnnouncementAt = -100
                self.announceHumanIfNeeded()
            } else {
                self.bluetooth.sendPresence(false)
            }
        }
    }

    private func processPose(_ observation: VNHumanBodyPoseObservation, now: TimeInterval) -> [CGPoint] {
        guard let points = try? observation.recognizedPoints(.all),
              let leftShoulder = validPoint(points[.leftShoulder]),
              let rightShoulder = validPoint(points[.rightShoulder]) else { return [] }

        let shoulderCenter = CGPoint(
            x: (leftShoulder.x + rightShoulder.x) / 2,
            y: (leftShoulder.y + rightShoulder.y) / 2
        )
        let shoulderWidth = hypot(leftShoulder.x - rightShoulder.x, leftShoulder.y - rightShoulder.y)
        var visibleWrists: [CGPoint] = []

        let candidates: [(HandSide, VNHumanBodyPoseObservation.JointName, VNHumanBodyPoseObservation.JointName)] = [
            (.left, .leftWrist, .leftElbow),
            (.right, .rightWrist, .rightElbow)
        ]
        for (side, wristName, elbowName) in candidates {
            guard let wrist = validPoint(points[wristName]),
                  let elbow = validPoint(points[elbowName]) else { continue }
            visibleWrists.append(wrist)
            if let detection = waveDetector.add(
                hand: side,
                time: now,
                wrist: wrist,
                elbow: elbow,
                shoulderCenter: shoulderCenter,
                shoulderWidth: shoulderWidth
            ) {
                DispatchQueue.main.async { [weak self] in
                    self?.handleWave(detection)
                }
            }
        }
        return visibleWrists
    }

    private func validPoint(_ point: VNRecognizedPoint?, minimumConfidence: VNConfidence = 0.25) -> CGPoint? {
        guard let point, point.confidence >= minimumConfidence else { return nil }
        return point.location
    }

    private func handleHeartStarted(_ gesture: HeartGesture) {
        heartCount += 1
        gestureLabel.stringValue = "\(gesture.rawValue.capitalized) Held (Event \(heartCount))"
        if bluetooth.sendHeartOn() {
            appendLog("\(gesture.rawValue) recognized — \(dryRun ? "DRY RUN, outputs disabled" : "heart held sent to FireBeetle (voice, pump only if the bowl is hot)").")
        } else {
            appendLog("\(gesture.rawValue) recognized, but FireBeetle is not connected; command not sent.")
        }
    }

    private func handleHeartEnded() {
        bluetooth.sendHeartOff()
        gestureLabel.stringValue = "Heart Released"
        appendLog("Heart released — \(dryRun ? "DRY RUN" : "heart released sent to FireBeetle").")
    }

    private func handleWave(_ detection: WaveDetection) {
        waveCount += 1
        // The LED firmware refreshes an existing presence lease on a wave.
        // Send the next presence heartbeat five seconds after this event.
        lastHumanAnnouncementAt = ProcessInfo.processInfo.systemUptime
        // Waves are not part of the final interaction; the final firmware ignores command 2.
        appendLog("Wave detected (logged only; not sent to FireBeetle).")
        let event = String(
            format: "Horizontal back-and-forth wave detected: %@, amplitude %.2f× shoulder width, duration %.2f seconds",
            detection.hand.rawValue,
            detection.horizontalRange,
            detection.duration
        )
        gestureLabel.stringValue = "Horizontal Wave Detected (Event \(waveCount))"
        appendLog(event)
    }

    private func appendLog(_ message: String) {
        let formatter = DateFormatter()
        formatter.dateFormat = "HH:mm:ss"
        let line = "[\(formatter.string(from: Date()))] \(message)\n"
        logView.textStorage?.append(NSAttributedString(string: line))
        logView.scrollToEndOfDocument(nil)
    }
}
