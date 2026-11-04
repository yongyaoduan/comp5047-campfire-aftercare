import Foundation
import CoreBluetooth

/// Connects the Mac app to the FireBeetle BLE service and writes one-byte events.
/// 0 = no human, 1 = human present, 2 = wave LED + three-second pump,
/// 4 = heart LED/pump ON or keepalive, 5 = heart OFF, 6 = stop all.
final class BluetoothBridge: NSObject, CBCentralManagerDelegate, CBPeripheralDelegate {
    static let serviceUUID = CBUUID(string: "A6E40001-B5A3-F393-E0A9-E50E24DCCA9E")
    static let commandUUID = CBUUID(string: "A6E40002-B5A3-F393-E0A9-E50E24DCCA9E")

    var onStatusChange: ((String) -> Void)?
    var onLog: ((String) -> Void)?

    private var central: CBCentralManager!
    private var peripheral: CBPeripheral?
    private var commandCharacteristic: CBCharacteristic?
    private var pendingPresence: UInt8 = 0
    private let dryRun = ProcessInfo.processInfo.arguments.contains("--dry-run")

    override init() {
        super.init()
        central = CBCentralManager(delegate: self, queue: .main)
    }

    func sendPresence(_ present: Bool) {
        pendingPresence = present ? 1 : 0
        write(pendingPresence)
    }

    func sendWave() {
        write(2)
    }

    @discardableResult
    func sendHeartOn() -> Bool {
        write(4)
    }

    func sendHeartOff() {
        write(5)
    }

    func sendStopAll() {
        write(6)
    }

    func centralManagerDidUpdateState(_ central: CBCentralManager) {
        switch central.state {
        case .poweredOn:
            updateStatus("Bluetooth: searching for FireBeetle…")
            startScanning()
        case .poweredOff:
            updateStatus("Bluetooth: turned off")
        case .unauthorized:
            updateStatus("Bluetooth: permission denied")
        case .unsupported:
            updateStatus("Bluetooth: unsupported")
        default:
            updateStatus("Bluetooth: unavailable")
        }
    }

    private func startScanning() {
        guard central.state == .poweredOn, peripheral == nil else { return }
        central.scanForPeripherals(
            withServices: [Self.serviceUUID],
            options: [CBCentralManagerScanOptionAllowDuplicatesKey: false]
        )
    }

    func centralManager(
        _ central: CBCentralManager,
        didDiscover peripheral: CBPeripheral,
        advertisementData: [String: Any],
        rssi RSSI: NSNumber
    ) {
        self.peripheral = peripheral
        central.stopScan()
        updateStatus("Bluetooth: connecting…")
        central.connect(peripheral)
    }

    func centralManager(_ central: CBCentralManager, didConnect peripheral: CBPeripheral) {
        peripheral.delegate = self
        updateStatus("Bluetooth: discovering service…")
        peripheral.discoverServices([Self.serviceUUID])
    }

    func centralManager(
        _ central: CBCentralManager,
        didFailToConnect peripheral: CBPeripheral,
        error: Error?
    ) {
        onLog?("Bluetooth connection failed: \(error?.localizedDescription ?? "unknown error")")
        clearConnectionAndRetry()
    }

    func centralManager(
        _ central: CBCentralManager,
        didDisconnectPeripheral peripheral: CBPeripheral,
        error: Error?
    ) {
        onLog?("FireBeetle disconnected")
        clearConnectionAndRetry()
    }

    func peripheral(_ peripheral: CBPeripheral, didDiscoverServices error: Error?) {
        if let error {
            onLog?("BLE service discovery failed: \(error.localizedDescription)")
            return
        }
        guard let service = peripheral.services?.first(where: { $0.uuid == Self.serviceUUID }) else {
            onLog?("FireBeetle service was not found")
            return
        }
        peripheral.discoverCharacteristics([Self.commandUUID], for: service)
    }

    func peripheral(
        _ peripheral: CBPeripheral,
        didDiscoverCharacteristicsFor service: CBService,
        error: Error?
    ) {
        if let error {
            onLog?("BLE characteristic discovery failed: \(error.localizedDescription)")
            return
        }
        guard let characteristic = service.characteristics?.first(where: { $0.uuid == Self.commandUUID }) else {
            onLog?("FireBeetle command characteristic was not found")
            return
        }
        commandCharacteristic = characteristic
        updateStatus("Bluetooth: FireBeetle connected")
        onLog?("FireBeetle BLE link ready")
        write(6)
        write(pendingPresence)
    }

    @discardableResult
    private func write(_ command: UInt8) -> Bool {
        guard let peripheral, let characteristic = commandCharacteristic else { return false }
        if dryRun && command != 6 { return true }
        peripheral.writeValue(Data([command]), for: characteristic, type: .withResponse)
        return true
    }

    private func clearConnectionAndRetry() {
        peripheral = nil
        commandCharacteristic = nil
        updateStatus("Bluetooth: reconnecting…")
        DispatchQueue.main.asyncAfter(deadline: .now() + 1) { [weak self] in
            self?.startScanning()
        }
    }

    private func updateStatus(_ status: String) {
        onStatusChange?(status)
    }
}
