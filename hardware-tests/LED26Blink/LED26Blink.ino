// FireBeetle 2 ESP32-E: external LED on GPIO26 (D3).
// Wiring: GPIO26 -> 220-330 ohm resistor -> LED anode (+), cathode (-) -> GND.
constexpr int LED_PIN = 26;

void setup() {
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
}

void loop() {
  digitalWrite(LED_PIN, HIGH);
  delay(1000);
  digitalWrite(LED_PIN, LOW);
  delay(1000);
}
