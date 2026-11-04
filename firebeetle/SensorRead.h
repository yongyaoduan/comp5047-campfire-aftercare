#pragma once
#include <Arduino.h>
#include <Wire.h>
static bool readWaterPart(uint8_t address, uint8_t *out, uint8_t length) {
  const size_t received = Wire.requestFrom(address, length);
  if (received != length) {
    while (Wire.available()) Wire.read();
    return false;
  }
  for (uint8_t i = 0; i < length; ++i) out[i] = Wire.read();
  return true;
}

// SMBus read-word with PEC: reject missing, corrupt and sensor-error readings.
static bool readTemperature(uint8_t reg, float &value) {
  constexpr uint8_t address = 0x5A;
  Wire.beginTransmission(address);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(address, uint8_t(3)) != 3) {
    while (Wire.available()) Wire.read();
    return false;
  }
  uint8_t lo = Wire.read(), hi = Wire.read(), pec = Wire.read();
  uint8_t bytes[] = {uint8_t(address << 1), reg, uint8_t((address << 1) | 1), lo, hi};
  uint8_t crc = 0;
  for (uint8_t b : bytes) {
    crc ^= b;
    for (int i = 0; i < 8; ++i) crc = (crc & 0x80) ? uint8_t((crc << 1) ^ 0x07) : uint8_t(crc << 1);
  }
  if (crc != pec || (hi & 0x80)) return false;
  value = (uint16_t(lo) | (uint16_t(hi) << 8)) * 0.02f - 273.15f;
  return true;
}

