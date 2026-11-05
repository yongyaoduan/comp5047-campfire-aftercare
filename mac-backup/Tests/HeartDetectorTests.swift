import CoreGraphics
import Foundation

func check(_ condition: @autoclosure () -> Bool, _ message: String) {
    if !condition() { fatalError(message) }
}

@main
struct HeartDetectorTests {
static func main() {
let heart = [
    HeartHand(wrist: CGPoint(x: 0.25, y: 0.40), middleMCP: CGPoint(x: 0.32, y: 0.48),
              indexTip: CGPoint(x: 0.47, y: 0.64), thumbTip: CGPoint(x: 0.48, y: 0.53)),
    HeartHand(wrist: CGPoint(x: 0.75, y: 0.40), middleMCP: CGPoint(x: 0.68, y: 0.48),
              indexTip: CGPoint(x: 0.53, y: 0.64), thumbTip: CGPoint(x: 0.52, y: 0.53))
]
let detector = HeartDetector()
check(HeartDetector.classify(heart) == .twoHand, "The two-hand heart should match")
check(HeartDetector.classify([heart[0]]) == nil, "One half-heart must not match")
let flat = [
    HeartHand(wrist: heart[0].wrist, middleMCP: heart[0].middleMCP,
              indexTip: CGPoint(x: 0.47, y: 0.55), thumbTip: heart[0].thumbTip),
    HeartHand(wrist: heart[1].wrist, middleMCP: heart[1].middleMCP,
              indexTip: CGPoint(x: 0.53, y: 0.55), thumbTip: heart[1].thumbTip)
]
check(HeartDetector.classify(flat) == nil, "Touching hands without a heart opening must not match")

// Landmarks measured with Vision on the supplied two-hand photo.
let photographedTwoHand = [
    HeartHand(wrist: CGPoint(x: 0.337, y: 0.401), middleMCP: CGPoint(x: 0.420, y: 0.460),
              indexTip: CGPoint(x: 0.507, y: 0.428), thumbTip: CGPoint(x: 0.506, y: 0.344)),
    HeartHand(wrist: CGPoint(x: 0.674, y: 0.384), middleMCP: CGPoint(x: 0.604, y: 0.463),
              indexTip: CGPoint(x: 0.528, y: 0.422), thumbTip: CGPoint(x: 0.508, y: 0.340))
]
check(HeartDetector.classify(photographedTwoHand) == .twoHand,
      "The supplied two-hand heart should match")
check(HeartDetector.classify([photographedTwoHand[0]]) == nil,
      "One visible half of the supplied two-hand heart should not trigger")

// Finger hearts are not part of the final interaction.
let finger = HeartHand(
    wrist: CGPoint(x: 0.355, y: 0.415), middleMCP: CGPoint(x: 0.304, y: 0.456),
    indexTip: CGPoint(x: 0.397, y: 0.613), thumbTip: CGPoint(x: 0.320, y: 0.627),
    indexPIP: CGPoint(x: 0.313, y: 0.552), thumbIP: CGPoint(x: 0.327, y: 0.572),
    middleTip: CGPoint(x: 0.355, y: 0.502))
check(HeartDetector.classify([finger]) == nil, "A finger heart must not trigger")

// Two people in view: four hands, one pair forms the heart.
let bystander = [
    HeartHand(wrist: CGPoint(x: 0.05, y: 0.20), middleMCP: CGPoint(x: 0.08, y: 0.25),
              indexTip: CGPoint(x: 0.10, y: 0.35), thumbTip: CGPoint(x: 0.04, y: 0.30)),
    HeartHand(wrist: CGPoint(x: 0.95, y: 0.20), middleMCP: CGPoint(x: 0.92, y: 0.25),
              indexTip: CGPoint(x: 0.90, y: 0.35), thumbTip: CGPoint(x: 0.96, y: 0.30))
]
check(HeartDetector.classify(bystander + heart) == .twoHand, "A heart among four hands should match")
check(HeartDetector.classify(bystander) == nil, "Four random hands must not match")
let loweredThumb = HeartHand(
    wrist: finger.wrist,
    middleMCP: finger.middleMCP,
    indexTip: finger.indexTip,
    thumbTip: CGPoint(x: 0.320, y: 0.515),
    indexPIP: finger.indexPIP,
    thumbIP: finger.thumbIP,
    middleTip: finger.middleTip
)
check(HeartDetector.classify([loweredThumb]) == nil, "A folded thumb must not match")
// Timing: 2 s of hearts to start, 1 s without to stop (checks every 0.1 s).
func run(_ d: HeartDetector, _ frames: [HeartHand]?, from t0: Double, to t1: Double) -> [HeartUpdate] {
    let n0 = Int((t0 * 10).rounded()), n1 = Int((t1 * 10).rounded())
    return (n0...n1).map { d.observe(frames ?? [], at: Double($0) / 10) }
}
let d1 = HeartDetector()
check(run(d1, heart, from: 0, to: 1.9).allSatisfy { $0.active == nil }, "No pump before 2 s of heart")
let s1 = d1.observe(heart, at: 2.0)
check(s1.started == .twoHand, "Heart counts after 2 s")
check(d1.observe([], at: 2.1).active == .twoHand, "One missed frame keeps the heart")
check(run(d1, nil, from: 2.2, to: 2.9).allSatisfy { $0.active == .twoHand && !$0.ended }, "Under 1 s without a heart keeps it")
check(d1.observe([], at: 3.0).ended, "1 s without a heart releases it")

let d2 = HeartDetector()
_ = run(d2, heart, from: 0, to: 1.5)
_ = d2.observe([], at: 1.6); _ = d2.observe([], at: 1.7)   // 0.2 s miss: tolerated
_ = d2.observe(heart, at: 1.8); _ = d2.observe(heart, at: 1.9)
check(d2.observe(heart, at: 2.0).started == .twoHand, "A short miss does not restart the 2 s count")
let d3 = HeartDetector()
_ = run(d3, heart, from: 0, to: 1.5)
_ = run(d3, nil, from: 1.6, to: 2.1)                       // 0.6 s miss: run broken
check(d3.observe(heart, at: 2.2).active == nil, "A long miss restarts the count")
check(run(d3, heart, from: 2.3, to: 4.1).contains { $0.started != nil } == false, "Not yet 2 s since restart")
check(d3.observe(heart, at: 4.2).started == .twoHand, "Counts 2 s after the restart")

let p = PresenceFilter()
var changes: [(Double, Bool)] = []
for i in 0...30 { let t = Double(i) * 0.2; if let c = p.observe(i < 15, at: t) { changes.append((t, c)) } }
check(changes.count == 2 && abs(changes[0].0 - 2.0) < 1e-6 && changes[0].1, "Person after 2 s")
check(abs(changes[1].0 - 4.8) < 1e-6 && !changes[1].1, "Nobody 2 s after the last detection")
let flicker = PresenceFilter()
check((0..<20).allSatisfy { flicker.observe($0 % 4 == 0, at: Double($0) * 0.2) == nil }, "A flickering false detection never becomes a person")
print("HeartDetector tests passed")
}
}
