import CoreGraphics
import Vision

/// Shared Apple Vision steps used by the live camera app and by the offline
/// photo regression (`Tools/PhotoRegression.swift`), so both judge a frame
/// with exactly the same requests and thresholds.
///
/// Tuned on the team's 264-photo corpus (a regression check, not an
/// independent accuracy test): full-body rectangles OR a face OR a visible
/// hand count as "someone here"; hand landmarks are accepted from confidence
/// 0.2; if no heart is found in the full frame, hands are searched again in
/// each person's region and in three overlapping tiles.
enum VisionPipeline {
    static let personConfidence: VNConfidence = 0.55
    static let faceConfidence: VNConfidence = 0.6
    static let handPresenceConfidence: VNConfidence = 0.5
    static let landmarkConfidence: VNConfidence = 0.2
    // Any number of people counts as "someone here"; up to 8 hands (four people)
    // are checked, and any pair forming a heart counts, whoever's hands they are.
    static let maximumHands = 8
    static let tiles = [CGRect(x: 0, y: 0, width: 0.6, height: 1),
                        CGRect(x: 0.4, y: 0, width: 0.6, height: 1),
                        CGRect(x: 0.2, y: 0.2, width: 0.6, height: 0.6)]

    struct Frame {
        var personBoxes: [CGRect] = []   // people (after removing animals)
        var hands: [HeartHand] = []      // hands to judge for a heart
        var handSeen = false
        var someoneHere: Bool { !personBoxes.isEmpty || handSeen }
    }

    static func humanRequest() -> VNDetectHumanRectanglesRequest {
        let request = VNDetectHumanRectanglesRequest()
        // Full-body rectangles: on the corpus upper-body-only found 69/139
        // people, full-body 101/139.
        request.upperBodyOnly = false
        return request
    }

    static func handRequest(region: CGRect? = nil) -> VNDetectHumanHandPoseRequest {
        let request = VNDetectHumanHandPoseRequest()
        request.maximumHandCount = maximumHands
        if let region { request.regionOfInterest = region }
        return request
    }

    /// One frame. `people` and `hands` select which parts run (the live app
    /// staggers them over frames; the photo regression runs both).
    static func analyze(_ handler: VNImageRequestHandler, people: Bool, hands: Bool) throws -> Frame {
        var frame = Frame()
        let human = humanRequest(), face = VNDetectFaceRectanglesRequest(),
            animal = VNRecognizeAnimalsRequest(), hand = handRequest()
        var requests: [VNRequest] = []
        if people { requests += [human, face, animal] }
        if hands { requests.append(hand) }
        guard !requests.isEmpty else { return frame }
        try handler.perform(requests)

        if people {
            let animals = (animal.results ?? []).filter { $0.confidence >= 0.5 }.map(\.boundingBox)
            func notAnimal(_ box: CGRect) -> Bool { !animals.contains { overlap(box, $0) > 0.5 } }
            frame.personBoxes = (human.results ?? []).filter { $0.confidence >= personConfidence }
                .map(\.boundingBox).filter(notAnimal)
            if frame.personBoxes.isEmpty {
                frame.personBoxes = (face.results ?? []).filter { $0.confidence >= faceConfidence }
                    .map(\.boundingBox).filter(notAnimal)
            }
        }
        if hands {
            frame.handSeen = (hand.results ?? []).contains { $0.confidence >= handPresenceConfidence }
            frame.hands = heartHands(hand)
            if HeartDetector.classify(frame.hands) == nil {
                // Second look: each person's region, then three tiles (smaller hands).
                let regions = (people ? (human.results ?? []).filter { $0.confidence >= 0.3 }.map {
                    $0.boundingBox.insetBy(dx: -$0.boundingBox.width * 0.15, dy: -$0.boundingBox.height * 0.1)
                        .intersection(CGRect(x: 0, y: 0, width: 1, height: 1)) } : []) + tiles
                for region in regions where !region.isNull && region.width > 0.05 {
                    let zoomed = handRequest(region: region)
                    try handler.perform([zoomed])
                    let found = heartHands(zoomed)
                    if HeartDetector.classify(found) != nil { frame.hands = found; break }
                }
            }
        }
        return frame
    }

    static func heartHands(_ request: VNDetectHumanHandPoseRequest) -> [HeartHand] {
        (request.results ?? []).compactMap { observation in
            guard let points = try? observation.recognizedPoints(.all) else { return nil }
            func point(_ name: VNHumanHandPoseObservation.JointName) -> CGPoint? {
                guard let p = points[name], p.confidence >= landmarkConfidence else { return nil }
                return p.location
            }
            guard let wrist = point(.wrist), let middleMCP = point(.middleMCP),
                  let indexTip = point(.indexTip), let thumbTip = point(.thumbTip) else { return nil }
            return HeartHand(wrist: wrist, middleMCP: middleMCP, indexTip: indexTip, thumbTip: thumbTip,
                             indexPIP: point(.indexPIP), thumbIP: point(.thumbIP), middleTip: point(.middleTip))
        }
    }

    /// Intersection over the smaller box.
    static func overlap(_ a: CGRect, _ b: CGRect) -> CGFloat {
        let i = a.intersection(b)
        guard !i.isNull, a.width * a.height > 0, b.width * b.height > 0 else { return 0 }
        return (i.width * i.height) / min(a.width * a.height, b.width * b.height)
    }
}
