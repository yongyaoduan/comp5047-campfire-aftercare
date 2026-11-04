#include <Arduino.h>
#include <Wire.h>

constexpr uint8_t PUMP = 26;
uint32_t lastReport = 0;

bool readWater(uint8_t address, uint8_t *data, uint8_t count) {
  if (Wire.requestFrom(address, count) != count) {
    while (Wire.available()) Wire.read();
    return false;
  }
  for (uint8_t i = 0; i < count; ++i) data[i] = Wire.read();
  return true;
}

bool readTemperature(uint8_t reg, float &value) {
  constexpr uint8_t address = 0x5A;
  Wire.beginTransmission(address);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(address, uint8_t(3)) != 3) {
    while (Wire.available()) Wire.read();
    return false;
  }
  uint8_t lo = Wire.read(), hi = Wire.read(), pec = Wire.read();
  uint8_t bytes[] = {uint8_t(address << 1), reg,
                     uint8_t((address << 1) | 1), lo, hi};
  uint8_t crc = 0;
  for (uint8_t b : bytes) {
    crc ^= b;
    for (int i = 0; i < 8; ++i)
      crc = (crc & 0x80) ? uint8_t((crc << 1) ^ 0x07) : uint8_t(crc << 1);
  }
  if (crc != pec || (hi & 0x80)) return false;
  value = (uint16_t(lo) | (uint16_t(hi) << 8)) * 0.02f - 273.15f;
  return true;
}

void scanBus() {
  Serial.println("I2C scan: expected temperature=0x5A, water=0x77 and 0x78");
  unsigned found = 0;
  // Include 0x78: the water sensor uses this address.
  for (uint8_t address = 1; address <= 0x7E; ++address) {
    Wire.beginTransmission(address);
    if (Wire.endTransmission() == 0) {
      Serial.printf("  Found 0x%02X\n", address);
      ++found;
    }
  }
  Serial.printf("Scan complete: %u address(es)\n", found);
}

void reportSensors() {
  float ambient = 0, object = 0;
  bool ambientOK = readTemperature(0x06, ambient);
  bool objectOK = readTemperature(0x07, object);
  if (ambientOK && objectOK)
    Serial.printf("TEMP OK ambient=%.2f C object=%.2f C\n", ambient, object);
  else Serial.printf("TEMP ERROR ambient_ok=%d object_ok=%d (includes CRC check)\n", ambientOK, objectOK);

  uint8_t data[20] = {};
  bool lowOK = readWater(0x77, data, 8);
  bool highOK = readWater(0x78, data + 8, 12);
  if (!lowOK || !highOK) {
    Serial.printf("WATER ERROR 0x77_ok=%d 0x78_ok=%d; not a dry reading\n", lowOK, highOK);
    return;
  }
  unsigned sections = 0;
  while (sections < 20 && data[sections] > 100) ++sections;
  Serial.printf("WATER OK approximate_level=%u mm raw=", sections * 5);
  for (unsigned i = 0; i < 20; ++i)
    Serial.printf("%u%s", data[i], i == 19 ? "\n" : ",");
}

void setup() {
  digitalWrite(PUMP, LOW);
  pinMode(PUMP, OUTPUT);
  // LEDs are unused. Keep these pins as inputs with no pull-ups.
  for (uint8_t pin : {25, 14, 13, 27}) pinMode(pin, INPUT);
  Serial.begin(115200);
  Wire.begin(21, 22, 100000);
  Wire.setTimeOut(25);
  delay(500);
  Serial.println("Wiring check: SDA=21 SCL=22 pump=26. Pump starts OFF.");
  Serial.println("s=scan, p=ONE 1-second pump pulse (water required), 0=OFF");
  scanBus();
}

void loop() {
  while (Serial.available()) {
    int c = Serial.read();
    if (c == 'p') {
      // No I2C or serial operations while the pump is on.
      Serial.println("PUMP: one 1000 ms pulse requested");
      Serial.flush();
      digitalWrite(PUMP, HIGH);
      delay(1000);
      digitalWrite(PUMP, LOW);
      Serial.println("PUMP: OFF (GPIO command only; confirm actual flow visually)");
      // Discard queued characters so one send cannot queue multiple pulses.
      while (Serial.available()) Serial.read();
      break;
    }
    if (c == '0') {
      digitalWrite(PUMP, LOW);
      Serial.println("PUMP: OFF");
    }
    if (c == 's') scanBus();
  }
  if (uint32_t(millis() - lastReport) >= 1000) {
    lastReport = millis();
    reportSensors();
  }
  delay(5);
}
