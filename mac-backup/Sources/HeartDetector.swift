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

/// Two-hand heart with time filtering (laptop program, Nov 2026):
/// a heart must be seen for 2 s (up to two missed checks, 0.35 s, do not break the run)
/// before it counts, and must be gone for 1 s before it is released. The laptop
/// checks hands about 10 times a second, so this rejects one-frame false matches
/// and keeps the pump on through brief landmark dropouts.
final class HeartDetector {
    var confirmSeconds: TimeInterval = 2.0
    var releaseGraceSeconds: TimeInterval = 1.0
    var gapTolerance: TimeInterval = 0.35
    private var activeGesture: HeartGesture?
    private var candidateSince: TimeInterval?
    private var lastMatchAt: TimeInterval = -100

    func observe(_ hands: [HeartHand], at now: TimeInterval) -> HeartUpdate {
        guard let gesture = Self.classify(hands) else {
            if let activeGesture {
                if now - lastMatchAt < releaseGraceSeconds {
                    return HeartUpdate(active: activeGesture, started: nil, ended: false)
                }
                self.activeGesture = nil
                candidateSince = nil
                return HeartUpdate(active: nil, started: nil, ended: true)
            }
            if now - lastMatchAt > gapTolerance { candidateSince = nil }
            return HeartUpdate(active: nil, started: nil, ended: false)
        }
        if candidateSince == nil || (activeGesture == nil && now - lastMatchAt > gapTolerance) {
            candidateSince = now
        }
        lastMatchAt = now
        if let activeGesture { return HeartUpdate(active: activeGesture, started: nil, ended: false) }
        guard let since = candidateSince, now - since >= confirmSeconds else {
            return HeartUpdate(active: nil, started: nil, ended: false)
        }
        activeGesture = gesture
        return HeartUpdate(active: gesture, started: gesture, ended: false)
    }

    static func classify(_ hands: [HeartHand]) -> HeartGesture? {
        // Several people may be in view; any pair of hands forming a two-hand
        // heart counts (one person, or two people sharing one). Finger hearts are ignored.
        for i in hands.indices {
            for j in hands.indices where j > i {
                if matchesTwoHand([hands[i], hands[j]]) { return .twoHand }
            }
        }
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
              indexMid.y - thumbMid.y >= 0.45 * palm,
              indexMid.y - thumbMid.y <= 1.8 * palm,
              abs(indexMid.x - thumbMid.x) <= 1.2 * palm,
              abs(indexMid.x - wristMidX) <= 1.5 * palm,
              abs(thumbMid.x - wristMidX) <= 1.5 * palm else { return false }

        for hand in sorted {
            let opening = distance(hand.indexTip, hand.thumbTip)
            // Opening 0.45-1.8 palms, as in the Pi rule (gesture_core.py).
            guard opening >= 0.45 * palm, opening <= 1.8 * palm,
                  hand.indexTip.y - hand.thumbTip.y >= 0.45 * palm,
                  abs(hand.indexTip.x - hand.thumbTip.x) <= 0.8 * palm,
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

/// "Someone here" with the same kind of filter: people must be seen for 2 s
/// (misses up to 0.5 s tolerated) before presence is reported, and must be
/// gone for 2 s before absence is reported.
final class PresenceFilter {
    var confirmSeconds: TimeInterval = 2.0
    var releaseSeconds: TimeInterval = 2.0
    var gapTolerance: TimeInterval = 0.5
    private(set) var present = false
    private var since: TimeInterval?
    private var lastSeenAt: TimeInterval = -100

    /// Returns the new state when it changes, nil otherwise.
    func observe(_ seen: Bool, at now: TimeInterval) -> Bool? {
        if seen {
            if since == nil || (!present && now - lastSeenAt > gapTolerance) { since = now }
            lastSeenAt = now
            if !present, let since, now - since >= confirmSeconds { present = true; return true }
            return nil
        }
        if present, now - lastSeenAt >= releaseSeconds { present = false; since = nil; return false }
        if !present, now - lastSeenAt > gapTolerance { since = nil }
        return nil
    }
}
