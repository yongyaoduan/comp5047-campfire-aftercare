import AppKit

final class AppDelegate: NSObject, NSApplicationDelegate {
    private var window: NSWindow?

    func applicationDidFinishLaunching(_ notification: Notification) {
        let controller = CameraViewController()
        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 1120, height: 760),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        window.title = CommandLine.arguments.contains("--dry-run") ? "Campfire LED + Pump Demo (Dry Run)" : "Campfire LED + Pump Demo"
        window.center()
        window.contentViewController = controller
        window.makeKeyAndOrderFront(nil)
        window.minSize = NSSize(width: 900, height: 620)
        self.window = window
        NSApp.activate(ignoringOtherApps: true)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }
}
