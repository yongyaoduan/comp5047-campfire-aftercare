import AppKit
import AVFoundation

final class CameraPreviewView: NSView {
    let previewLayer = AVCaptureVideoPreviewLayer()
    private let boxesLayer = CAShapeLayer()
    private let wristsLayer = CAShapeLayer()
    private let heartTipsLayer = CAShapeLayer()

    override init(frame frameRect: NSRect) {
        super.init(frame: frameRect)
        wantsLayer = true
        layer = CALayer()
        layer?.backgroundColor = NSColor.black.cgColor

        previewLayer.videoGravity = .resizeAspectFill
        layer?.addSublayer(previewLayer)

        boxesLayer.fillColor = NSColor.clear.cgColor
        boxesLayer.strokeColor = NSColor.systemGreen.cgColor
        boxesLayer.lineWidth = 3
        layer?.addSublayer(boxesLayer)

        wristsLayer.fillColor = NSColor.systemYellow.cgColor
        wristsLayer.strokeColor = NSColor.systemYellow.cgColor
        wristsLayer.lineWidth = 3
        layer?.addSublayer(wristsLayer)

        heartTipsLayer.fillColor = NSColor.systemPink.cgColor
        heartTipsLayer.strokeColor = NSColor.white.cgColor
        heartTipsLayer.lineWidth = 2
        layer?.addSublayer(heartTipsLayer)
    }

    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }

    override func layout() {
        super.layout()
        previewLayer.frame = bounds
        boxesLayer.frame = bounds
        wristsLayer.frame = bounds
        heartTipsLayer.frame = bounds
    }

    func show(humans: [CGRect], wrists: [CGPoint], heartTips: [CGPoint]) {
        let boxes = CGMutablePath()
        for visionRect in humans {
            let metadataRect = CGRect(
                x: visionRect.minX,
                y: 1 - visionRect.maxY,
                width: visionRect.width,
                height: visionRect.height
            )
            boxes.addRect(previewLayer.layerRectConverted(fromMetadataOutputRect: metadataRect))
        }
        boxesLayer.path = boxes

        let wristPath = CGMutablePath()
        for visionPoint in wrists {
            let capturePoint = CGPoint(x: visionPoint.x, y: 1 - visionPoint.y)
            let point = previewLayer.layerPointConverted(fromCaptureDevicePoint: capturePoint)
            wristPath.addEllipse(in: CGRect(x: point.x - 7, y: point.y - 7, width: 14, height: 14))
        }
        wristsLayer.path = wristPath

        let tipsPath = CGMutablePath()
        for visionPoint in heartTips {
            let capturePoint = CGPoint(x: visionPoint.x, y: 1 - visionPoint.y)
            let point = previewLayer.layerPointConverted(fromCaptureDevicePoint: capturePoint)
            tipsPath.addEllipse(in: CGRect(x: point.x - 6, y: point.y - 6, width: 12, height: 12))
        }
        heartTipsLayer.path = tipsPath
    }
}
