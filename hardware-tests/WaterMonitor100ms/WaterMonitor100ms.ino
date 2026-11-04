#include <Arduino.h>
#include <Wire.h>

constexpr uint32_t PERIOD_US = 100000;
uint32_t nextSample;
uint32_t sequence = 0;

bool readPart(uint8_t address, uint8_t *out, uint8_t count) {
  if (Wire.requestFrom(address, count) != count) {
    while (Wire.available()) Wire.read();
    return false;
  }
  for (uint8_t i = 0; i < count; ++i) out[i] = Wire.read();
  return true;
}

void setup() {
  digitalWrite(26, LOW);
  pinMode(26, OUTPUT);
  for (uint8_t pin : {25, 14, 13, 27}) pinMode(pin, INPUT);
  Serial.begin(115200);
  Wire.begin(21, 22, 100000);
  Wire.setTimeOut(25);
  delay(500);
  Serial.println("seq,start_us,read_us,valid,level_mm,wet_segments,isolated_segments,r0,r1,r2,r3,r4,r5,r6,r7,r8,r9,r10,r11,r12,r13,r14,r15,r16,r17,r18,r19");
  nextSample = micros();
}

void loop() {
  // Monitoring firmware never enables the pump, regardless of serial input.
  digitalWrite(26, LOW);
  while (Serial.available()) Serial.read();
  if (int32_t(micros() - nextSample) < 0) { delay(1); return; }
  const uint32_t started = micros();
  nextSample += PERIOD_US;
  uint8_t data[20] = {};
  bool lowOK = readPart(0x77, data, 8);
  bool highOK = readPart(0x78, data + 8, 12);
  uint32_t duration = micros() - started;
  const bool valid = lowOK && highOK;
  unsigned contiguous = 0, wet = 0;
  if (valid) {
    while (contiguous < 20 && data[contiguous] > 100) ++contiguous;
    for (uint8_t value : data) if (value > 100) ++wet;
  }
  Serial.printf("%lu,%lu,%lu,%d,%d,%d,%d", (unsigned long)sequence++,
      (unsigned long)started, (unsigned long)duration, valid,
      valid ? int(contiguous * 5) : -1, valid ? int(wet) : -1,
      valid ? int(wet - contiguous) : -1);
  for (uint8_t value : data) Serial.printf(",%u", value);
  Serial.println();
  // Do not emit catch-up bursts after an overrun. Actual intervals are logged.
  if (int32_t(micros() - nextSample) >= 0) nextSample = micros() + PERIOD_US;
}
