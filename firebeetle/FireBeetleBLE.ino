#include <Arduino.h>
#include <Wire.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <atomic>
#include "ControlState.h"
#include "WaterLevelState.h"
#include "TemperatureState.h"
#include "SensorRead.h"
#include "AudioPlayer.h"

constexpr uint8_t GREEN = 14, YELLOW = 13, RED = 27, BLUE = 4, PUMP = 26;
static const char *SERVICE_UUID = "A6E40001-B5A3-F393-E0A9-E50E24DCCA9E";
static const char *COMMAND_UUID = "A6E40002-B5A3-F393-E0A9-E50E24DCCA9E";
static QueueHandle_t events, samples;
static std::atomic<bool> disconnected{false};
static std::atomic<bool> connected{false};
static ControlState controller;
static WaterLevelState water;
static TemperatureState temperature;
static AudioPlayer audio;
static bool audioReady = false;
static bool person = false, heart = false, armed = false, transportSeen = false;
static bool lastWaterValid = false, lastTempValid = false;
static uint32_t lastCommand = 0, lastPerson = 0, lastHeart = 0, lastReport = 0;

struct SensorSample {
  uint8_t water[20];
  float ambient, object;
  bool waterValid, tempValid;
  uint32_t at;
};

static void sensorTask(void *) {
  Wire.begin(21, 22, 100000);
  Wire.setTimeOut(25);
  for (;;) {
    SensorSample sample = {};
    const bool ambientOK = readTemperature(0x06, sample.ambient);
    const bool objectOK = readTemperature(0x07, sample.object);
    sample.tempValid = ambientOK && objectOK;
    const bool lowOK = readWaterPart(0x77, sample.water, 8);
    const bool highOK = readWaterPart(0x78, sample.water + 8, 12);
    sample.waterValid = lowOK && highOK;
    sample.at = millis();
    xQueueOverwrite(samples, &sample);
    vTaskDelay(pdMS_TO_TICKS(250));
  }
}

static void receive(uint8_t command) {
  if (command != 0 && command != 1 && command != 4 && command != 5 && command != 6) return;
  if (xQueueSend(events, &command, 0) != pdTRUE) disconnected.store(true);
}

class ServerCallbacks : public BLEServerCallbacks {
  void onConnect(BLEServer *) override {
    connected.store(true);
    Serial.println("BLE connected; waiting for fresh presence command");
  }
  void onDisconnect(BLEServer *) override {
    connected.store(false);
    disconnected.store(true);
  }
};
class CommandCallbacks : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic *characteristic) override {
    auto value = characteristic->getValue();
    if (value.length() == 1) receive(uint8_t(value[0]));
  }
};

void setup() {
  digitalWrite(PUMP, LOW);
  pinMode(PUMP, OUTPUT);
  for (uint8_t pin : {GREEN, YELLOW, RED, BLUE}) {
    digitalWrite(pin, LOW);
    pinMode(pin, OUTPUT);
  }
  Serial.begin(115200);
  events = xQueueCreate(32, sizeof(uint8_t));
  samples = xQueueCreate(1, sizeof(SensorSample));
  configASSERT(events && samples);
  configASSERT(xTaskCreate(sensorTask, "sensors", 4096, nullptr, 1, nullptr) == pdPASS);
  audioReady = audio.begin();
  Serial.printf("Audio DMA on GPIO25: %s\n", audioReady ? "ready" : "FAILED (control still active)");
  BLEDevice::init("Campfire-FireBeetle");
  auto server = BLEDevice::createServer();
  server->setCallbacks(new ServerCallbacks());
  auto service = server->createService(SERVICE_UUID);
  auto command = service->createCharacteristic(COMMAND_UUID,
      BLECharacteristic::PROPERTY_WRITE | BLECharacteristic::PROPERTY_WRITE_NR);
  command->setCallbacks(new CommandCallbacks());
  service->start();
  auto advertising = BLEDevice::getAdvertising();
  advertising->addServiceUUID(SERVICE_UUID);
  advertising->setScanResponse(true);
  advertising->start();
  Serial.println("Four LEDs: green14 yellow13 red27 blue4; audio25 pump26 SDA21 SCL22");
  Serial.println("0/1=person absent/present, 4/5=heart held/released, 6=STOP");
  Serial.println("w/f/l=voice test; serial commands expire unless refreshed");
}

void loop() {
  const uint32_t now = millis();
  if (disconnected.exchange(false)) {
    digitalWrite(PUMP, LOW);
    xQueueReset(events);
    controller.reset();
    person = heart = armed = transportSeen = false;
    audio.stop();
    if (!connected.load()) BLEDevice::startAdvertising();
    Serial.println("Transport stopped; pump OFF");
  }
  while (Serial.available()) {
    const int c = Serial.read();
    if (c >= '0' && c <= '6') receive(c - '0');
    if (c == 'w') audio.speak(ControlState::Voice::Water);
    if (c == 'f') audio.speak(ControlState::Voice::Fire);
    if (c == 'l') audio.speak(ControlState::Voice::Love);
  }
  uint8_t cmd;
  while (xQueueReceive(events, &cmd, 0) == pdTRUE) {
    lastCommand = now;
    transportSeen = true;
    if (cmd == 6) {
      digitalWrite(PUMP, LOW);
      person = heart = armed = false;
      controller.reset();
      audio.stop();
      continue;
    }
    if (cmd == 0 || cmd == 1) {
      person = cmd == 1;
      lastPerson = now;
      armed = true;
    }
    if (cmd == 4) { heart = true; lastHeart = now; }
    if (cmd == 5) heart = false;
  }
  SensorSample sample;
  if (xQueueReceive(samples, &sample, 0) == pdTRUE) {
    water.update(sample.water, sample.waterValid, sample.at);
    temperature.update(sample.object, sample.ambient, sample.tempValid, sample.at);
    lastWaterValid = sample.waterValid;
    lastTempValid = sample.tempValid;
  }
  // All expiry checks run independently of I2C and audio playback.
  const bool link = armed && transportSeen && uint32_t(now - lastCommand) < 2000;
  if (!link && armed) {
    armed = person = heart = false;
    controller.reset();
    audio.stop();
  }
  ControlState::Input input;
  input.link = link;
  input.person = person && uint32_t(now - lastPerson) < 8000;
  input.heart = heart && uint32_t(now - lastHeart) < 800;
  input.temperatureKnown = lastTempValid && temperature.fresh(now);
  input.hot = temperature.hot(now);
  input.waterKnown = lastWaterValid && water.fresh(now);
  input.lowWater = water.dry(now);
  // Require two valid samples before allowing pumping (settled wet or dry).
  input.waterKnown = input.waterKnown && water.settled();
  const auto out = controller.tick(now, input);
  digitalWrite(PUMP, out.pump ? HIGH : LOW);
  digitalWrite(GREEN, out.green ? HIGH : LOW);
  digitalWrite(YELLOW, out.yellow ? HIGH : LOW);
  digitalWrite(RED, out.red ? HIGH : LOW);
  digitalWrite(BLUE, out.blue ? HIGH : LOW);
  if (audioReady) {
    audio.alarm(out.alarm);
    audio.speak(out.voice);
  }
  if (uint32_t(now - lastReport) >= 1000) {
    lastReport = now;
    Serial.printf("mode=%d link=%d person=%d heart=%d temp_ok=%d object_C=%.2f water_ok=%d level_mm=%u low=%d pump=%d GYRB=%d%d%d%d\n",
      int(out.mode), link, input.person, input.heart, input.temperatureKnown,
      temperature.object(), input.waterKnown, water.levelMM(), input.lowWater,
      out.pump, out.green, out.yellow, out.red, out.blue);
  }
  delay(5);
}
