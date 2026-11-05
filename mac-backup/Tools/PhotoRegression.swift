import AppKit
import Foundation
import Vision

// Offline regression of the laptop vision program on the team's photo corpus.
// Uses the same VisionPipeline requests/thresholds and HeartDetector as the app.
// Each image is letterboxed to 640x480 and judged as five frames 0.1 s apart
// (person = two positive frames in a row, as in the app; heart = HeartDetector).
// Usage: PhotoRegression <corpus-dir-with-results.json> <output.json>

@main
struct PhotoRegression {
    static func letterbox(_ image: CGImage) -> CGImage? {
        let w = 640, h = 480
        guard let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: 0,
                                  space: CGColorSpaceCreateDeviceRGB(),
                                  bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue) else { return nil }
        ctx.setFillColor(CGColor(gray: 0, alpha: 1)); ctx.fill(CGRect(x: 0, y: 0, width: w, height: h))
        let scale = min(Double(w) / Double(image.width), Double(h) / Double(image.height))
        let dw = Double(image.width) * scale, dh = Double(image.height) * scale
        ctx.interpolationQuality = .high
        ctx.draw(image, in: CGRect(x: (Double(w) - dw) / 2, y: (Double(h) - dh) / 2, width: dw, height: dh))
        return ctx.makeImage()
    }

    static func main() throws {
        let args = CommandLine.arguments
        guard args.count == 3 else { print("usage: PhotoRegression <corpus> <out.json>"); exit(2) }
        let corpus = URL(fileURLWithPath: args[1]), output = URL(fileURLWithPath: args[2])
        let index = try JSONSerialization.jsonObject(with: Data(contentsOf: corpus.appendingPathComponent("results.json"))) as! [String: Any]
        let samples = index["samples"] as! [[String: Any]]
        var rows: [[String: Any]] = [], times: [Double] = []
        for sample in samples {
            let path = corpus.appendingPathComponent(sample["path"] as! String)
            guard let ns = NSImage(contentsOf: path),
                  let cg = ns.cgImage(forProposedRect: nil, context: nil, hints: nil),
                  let frame = letterbox(cg) else { print("skip", path.lastPathComponent); continue }
            // A still photo gives the same result on every frame, so it is analysed
            // twice (timing + a consistency check) and the result is replayed as a
            // live camera would see it for 3 s: hands every 0.1 s, people every 0.2 s,
            // through the same 2 s confirmation filters as the app.
            let heart = HeartDetector(), presence = PresenceFilter()
            var results: [VisionPipeline.Frame] = []
            for _ in 0..<2 {
                let start = Date()
                results.append(try VisionPipeline.analyze(VNImageRequestHandler(cgImage: frame, orientation: .up), people: true, hands: true))
                times.append(Date().timeIntervalSince(start))
            }
            var green = false, pump = false
            for step in 0...30 {
                let t = Double(step) * 0.1, r = results[step % 2]
                if heart.observe(r.hands, at: t).active != nil { pump = true }
                if step % 2 == 0, presence.observe(r.someoneHere, at: t) == true { green = true }
            }
            let row: [String: Any] = ["id": sample["id"]!, "expected_person": sample["expected_person"] ?? NSNull(),
                                      "expected_heart": sample["expected_heart"] ?? NSNull(), "green": green, "pump": pump]
            rows.append(row)
            print(sample["id"]!, green, pump)
        }
        func count(_ key: String, _ value: Bool, _ out: String?) -> Int {
            rows.filter { ($0[key] as? Bool) == value && (out == nil || ($0[out!] as? Bool) == true) }.count
        }
        let sorted = times.sorted()
        let summary: [String: Any] = [
            "samples": rows.count,
            "person_positives": count("expected_person", true, nil), "person_true_positive": count("expected_person", true, "green"),
            "person_negatives": count("expected_person", false, nil), "green_false_positive": count("expected_person", false, "green"),
            "heart_positives": count("expected_heart", true, nil), "heart_true_positive": count("expected_heart", true, "pump"),
            "heart_negatives": count("expected_heart", false, nil), "pump_false_positive": count("expected_heart", false, "pump"),
            "seconds_per_frame_median": sorted[sorted.count / 2], "seconds_per_frame_p90": sorted[Int(Double(sorted.count) * 0.9)],
        ]
        let host = ProcessInfo.processInfo
        let result: [String: Any] = ["program": "mac-backup (Apple Vision)", "os": host.operatingSystemVersionString,
            "policy": "640x480 letterbox, five frames per image (VisionPipeline.analyze run twice per photo, result replayed for 3 s through the app's 2 s confirmation filters), person = 2 positive frames, heart = HeartDetector; single thread",
            "summary": summary, "samples": rows]
        try JSONSerialization.data(withJSONObject: result, options: [.prettyPrinted, .sortedKeys]).write(to: output)
        print(summary)
    }
}
