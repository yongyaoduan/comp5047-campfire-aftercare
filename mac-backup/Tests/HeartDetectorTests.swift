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
let firstStart = detector.observe(heart, at: 0)
check(firstStart.started == .twoHand && firstStart.active == .twoHand,
      "The first recognized heart frame requests the pump immediately")
for time in [0.2, 0.4, 0.6, 0.8, 1.0] {
    let update = detector.observe(heart, at: time)
    check(update.active == .twoHand && update.started == nil,
          "Holding a heart keeps its pump request active")
}
let briefMiss = detector.observe([], at: 1.1)
check(!briefMiss.ended && briefMiss.active == .twoHand,
      "One missed landmark frame must not interrupt the pump")
check(detector.observe(heart, at: 1.2).active == .twoHand,
      "A returning match keeps the same heart active")
let firstEnd = detector.observe([], at: 1.6)
check(firstEnd.ended && firstEnd.active == nil,
      "A sustained absence ends the heart request")

let nextStart = detector.observe(heart, at: 1.61)
check(nextStart.started == .twoHand && nextStart.active == .twoHand,
      "A new heart starts immediately without a cooldown")
check(detector.observe([finger], at: 1.8).active == .twoHand, "Grace covers one non-heart frame")
check(detector.observe([finger], at: 2.2).ended, "A finger heart does not keep the request alive")

let afterFailedAttempt = HeartDetector()
check(afterFailedAttempt.observe(heart, at: 0).started == .twoHand,
      "A short heart can start the pump")
check(!afterFailedAttempt.observe([], at: 0.1).ended,
      "A short miss is tolerated")
check(afterFailedAttempt.observe([], at: 0.4).ended,
      "A failed attempt ends after the release grace")
check(afterFailedAttempt.observe(heart, at: 0.41).started == .twoHand,
      "A failed attempt does not impose a cooldown")
print("HeartDetector tests passed")
}
}
