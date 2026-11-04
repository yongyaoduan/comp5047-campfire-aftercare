import Foundation
import CoreGraphics

enum HandSide: String {
    case left = "Left hand"
    case right = "Right hand"
}

struct WaveSample {
    let time: TimeInterval
    let normalizedX: CGFloat
    let normalizedY: CGFloat
    let isRaised: Bool
}

struct WaveDetection {
    let hand: HandSide
    let horizontalRange: CGFloat
    let duration: TimeInterval
}

/// A deliberately transparent baseline detector. It looks for a sizeable horizontal
/// movement followed by a return movement, normalized by shoulder width.
final class WaveDetector {
    private var history: [HandSide: [WaveSample]] = [.left: [], .right: []]

    // Start here when tuning with your own camera position.
    var firstLegMinimum: CGFloat = 0.55
    var returnLegMinimum: CGFloat = 0.42
    var maximumVerticalRange: CGFloat = 0.65
    var historySeconds: TimeInterval = 2.4

    func reset() {
        history = [.left: [], .right: []]
    }

    func add(
        hand: HandSide,
        time: TimeInterval,
        wrist: CGPoint,
        elbow: CGPoint,
        shoulderCenter: CGPoint,
        shoulderWidth: CGFloat
    ) -> WaveDetection? {
        guard shoulderWidth > 0.04 else { return nil }

        let sample = WaveSample(
            time: time,
            normalizedX: (wrist.x - shoulderCenter.x) / shoulderWidth,
            normalizedY: (wrist.y - shoulderCenter.y) / shoulderWidth,
            isRaised: wrist.y > elbow.y - shoulderWidth * 0.12
        )

        var samples = history[hand, default: []]
        samples.append(sample)
        samples.removeAll { time - $0.time > historySeconds }
        history[hand] = samples

        guard samples.count >= 9,
              let result = detectRoundTrip(in: samples, hand: hand) else { return nil }

        history[hand] = []
        return result
    }

    private func detectRoundTrip(in samples: [WaveSample], hand: HandSide) -> WaveDetection? {
        let raisedRatio = CGFloat(samples.filter(\.isRaised).count) / CGFloat(samples.count)
        guard raisedRatio >= 0.70 else { return nil }

        let ys = samples.map(\.normalizedY)
        guard let minY = ys.min(), let maxY = ys.max(),
              maxY - minY <= maximumVerticalRange else { return nil }

        // Trying each interior point as the turn-around point makes this tolerant of
        // brief pauses at either end of the wave.
        for pivot in 3..<(samples.count - 3) {
            let before = Array(samples[0...pivot])
            let after = Array(samples[pivot...])
            guard let start = median(Array(before.prefix(3)).map(\.normalizedX)),
                  let turn = extremePoint(before.map(\.normalizedX), relativeTo: start),
                  let end = median(Array(after.suffix(3)).map(\.normalizedX)) else { continue }

            let outward = turn - start
            let returning = end - turn
            guard outward * returning < 0,
                  abs(outward) >= firstLegMinimum,
                  abs(returning) >= returnLegMinimum else { continue }

            let duration = samples.last!.time - samples.first!.time
            guard duration >= 0.45 else { continue }
            return WaveDetection(
                hand: hand,
                horizontalRange: max(abs(outward), abs(returning)),
                duration: duration
            )
        }
        return nil
    }

    private func extremePoint(_ values: [CGFloat], relativeTo start: CGFloat) -> CGFloat? {
        guard let low = values.min(), let high = values.max() else { return nil }
        return abs(high - start) >= abs(low - start) ? high : low
    }

    private func median(_ values: [CGFloat]) -> CGFloat? {
        guard !values.isEmpty else { return nil }
        let sorted = values.sorted()
        return sorted[sorted.count / 2]
    }
}
