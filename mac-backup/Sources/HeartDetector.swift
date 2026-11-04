import CoreGraphics
import Foundation

struct HeartHand {
    let wrist: CGPoint
    let middleMCP: CGPoint
    let indexTip: CGPoint
    let thumbTip: CGPoint
    var indexPIP: CGPoint? = nil
    var thumbIP: CGPoint? = nil
    var middleTip: CGPoint? = nil
}

enum HeartGesture: String {
    case twoHand = "two-hand heart"
    case finger = "finger heart"
}

struct HeartUpdate {
    let active: HeartGesture?
    let started: HeartGesture?
    let ended: Bool
}

/// Geometric prototypes calibrated against the two supplied example photos.
/// Vision reports hand landmarks, not a built-in heart-gesture classification.
final class HeartDetector {
    // Ignore a brief landmark miss while a real heart is being held.
    // This is release hysteresis, not a cooldown before the next gesture.
    var releaseGraceSeconds: TimeInterval = 0.30
    private var activeGesture: HeartGesture?
    private var lastMatchAt: TimeInterval = -100

    func observe(_ hands: [HeartHand], at now: TimeInterval) -> HeartUpdate {
        guard let gesture = Self.classify(hands) else {
            if let activeGesture, now - lastMatchAt < releaseGraceSeconds {
                return HeartUpdate(active: activeGesture, started: nil, ended: false)
            }
            let ended = activeGesture != nil
            activeGesture = nil
            return HeartUpdate(active: nil, started: nil, ended: ended)
        }

        let started = activeGesture == nil ? gesture : nil
        activeGesture = gesture
        lastMatchAt = now
        return HeartUpdate(active: gesture, started: started, ended: false)
    }

    static func classify(_ hands: [HeartHand]) -> HeartGesture? {
        if matchesTwoHand(hands) { return .twoHand }
        // Final design accepts only the two-hand heart (finger hearts are ignored).
        return nil
    }

    private static func matchesTwoHand(_ hands: [HeartHand]) -> Bool {
        guard hands.count == 2 else { return false }
        let sorted = hands.sorted { $0.wrist.x < $1.wrist.x }
        let left = sorted[0], right = sorted[1]
        let palm = (distance(left.wrist, left.middleMCP) +
                    distance(right.wrist, right.middleMCP)) / 2
        guard palm >= 0.012 else { return false }

        let wristGap = right.wrist.x - left.wrist.x
        guard wristGap >= 1.5 * palm, wristGap <= 6 * palm else { return false }

        let indexMid = midpoint(left.indexTip, right.indexTip)
        let thumbMid = midpoint(left.thumbTip, right.thumbTip)
        let wristMidX = (left.wrist.x + right.wrist.x) / 2

        // Two fingertip pairs meet at the centre, with a visible opening
        // between the upper index tips and lower thumb tips.
        guard distance(left.indexTip, right.indexTip) <= 0.6 * palm,
              distance(left.thumbTip, right.thumbTip) <= 0.6 * palm,
              indexMid.y - thumbMid.y >= 0.65 * palm,
              indexMid.y - thumbMid.y <= 1.8 * palm,
              abs(indexMid.x - thumbMid.x) <= 1.2 * palm,
              abs(indexMid.x - wristMidX) <= 1.5 * palm,
              abs(thumbMid.x - wristMidX) <= 1.5 * palm else { return false }

        for hand in sorted {
            let opening = distance(hand.indexTip, hand.thumbTip)
            guard opening >= 0.65 * palm, opening <= 1.8 * palm,
                  hand.indexTip.y - hand.thumbTip.y >= 0.6 * palm,
                  abs(hand.indexTip.x - hand.thumbTip.x) <= 0.8 * palm,
                  hand.indexTip.y > hand.wrist.y,
                  hand.thumbTip.x >= left.wrist.x - 0.5 * palm,
                  hand.thumbTip.x <= right.wrist.x + 0.5 * palm else { return false }
        }
        return true
    }

    private static func matchesFingerHeart(_ hand: HeartHand) -> Bool {
        guard let thumbIP = hand.thumbIP,
              let indexPIP = hand.indexPIP,
              let middleTip = hand.middleTip else { return false }
        let palm = distance(hand.wrist, hand.middleMCP)
        guard palm >= 0.012 else { return false }

        // In the supplied example, the thumb and index finger rise together,
        // their inner joints nearly meet, and their tips open into a small V.
        // The folded middle finger is visibly lower than both raised tips.
        let tipGap = distance(hand.thumbTip, hand.indexTip) / palm
        let innerGap = distance(thumbIP, indexPIP) / palm
        guard tipGap >= 0.45, tipGap <= 1.8,
              innerGap <= 0.8,
              hand.thumbTip.y - middleTip.y >= 0.6 * palm,
              hand.indexTip.y - middleTip.y >= 0.6 * palm,
              hand.thumbTip.y - thumbIP.y >= 0.55 * palm,
              hand.indexTip.y - indexPIP.y >= 0.55 * palm,
              distance(hand.thumbTip, hand.wrist) >= 1.6 * palm,
              distance(hand.indexTip, hand.wrist) >= 1.6 * palm else { return false }
        return true
    }

    private static func distance(_ a: CGPoint, _ b: CGPoint) -> CGFloat {
        hypot(a.x - b.x, a.y - b.y)
    }

    private static func midpoint(_ a: CGPoint, _ b: CGPoint) -> CGPoint {
        CGPoint(x: (a.x + b.x) / 2, y: (a.y + b.y) / 2)
    }
}
