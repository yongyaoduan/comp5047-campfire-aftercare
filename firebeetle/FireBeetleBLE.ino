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

// Two LEDs on the short header row (easy to solder): green person, red fire.
// Tank low is spoken ("I need some more water"); a held heart is answered by voice and water.
constexpr uint8_t GREEN = 16, RED = 17, PUMP = 26;
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
static uint8_t lastWaterRaw[20] = {};
static bool printRaw = false;
// Start-up standby: the first 10 s of IR readings give the room temperature; after about 30 s,
// once the IR thermometer is calibrated and the water sensor answers on I2C, both LEDs blink
// twice and the station starts. Until then the pump stays off and nothing is spoken.
// The water sensor must be dry during standby (it calibrates at power-up); put it in the tank
// after the double blink. If it is still not ready after 30 s, the red LED flickers fast.
constexpr uint32_t STANDBY_MS = 30000, READY_BLINK_MS = 300;
static bool ready = false;
static uint32_t readyAt = 0;

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
  for (uint8_t pin : {GREEN, RED}) {
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
  Serial.println("Standby about 30 s (room temperature from the first 10 s; keep the water sensor dry), then both LEDs blink twice");
  Serial.println("Two LEDs: green16 person, red17 fire (room + 10 C); audio25 (amp on 5 V VCC) pump26 SDA21 SCL22");
  Serial.println("0/1=person absent/present, 4/5=heart held/released, 6=STOP");
  Serial.println("w/f/l/p/e=voice test (water/fire/love/spray/enough); r=toggle raw water pads; serial commands expire unless refreshed");
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
    if (c == 'p') audio.speak(ControlState::Voice::Spray);
    if (c == 'e') audio.speak(ControlState::Voice::Full);
    if (c == 'r') printRaw = !printRaw;   // toggle raw water-pad values in the status line
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
    memcpy(lastWaterRaw, sample.water, sizeof(lastWaterRaw));
    temperature.update(sample.object, sample.ambient, sample.tempValid, sample.at);
    lastWaterValid = sample.waterValid;
    lastTempValid = sample.tempValid;
  }
  if (!ready) {
    const bool waterSensorOK = lastWaterValid && water.fresh(now);
    const bool tempOK = lastTempValid && temperature.fresh(now) && temperature.calibrated();
    if (now >= STANDBY_MS && waterSensorOK && tempOK) {
      ready = true;
      readyAt = now;
      controller.reset();
      Serial.printf("STANDBY DONE: room_C=%.2f (window restarts %u), water sensor OK -> put the water sensor in the tank now\n",
        temperature.room(), temperature.calibrationRestarts());
    } else {
      digitalWrite(PUMP, LOW);
      digitalWrite(GREEN, LOW);
      digitalWrite(RED, (now >= STANDBY_MS && (now / 100) % 2) ? HIGH : LOW);   // fast flicker = fault
      if (uint32_t(now - lastReport) >= 1000) {
        lastReport = now;
        Serial.printf("standby %lus: temp_ok=%d calibrated=%d room_C=%.2f object_C=%.2f water_i2c=%d\n",
          (unsigned long)(now / 1000), tempOK, temperature.calibrated(), temperature.room(),
          temperature.object(), waterSensorOK);
      }
      delay(5);
      return;
    }
  }
  if (uint32_t(now - readyAt) < 4 * READY_BLINK_MS) {           // double blink: ready
    const bool on = (uint32_t(now - readyAt) / READY_BLINK_MS) % 2 == 0;
    digitalWrite(PUMP, LOW);
    digitalWrite(GREEN, on ? HIGH : LOW);
    digitalWrite(RED, on ? HIGH : LOW);
    delay(5);
    return;
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
  input.fullWater = water.full(now);
  // Require two valid samples before allowing pumping (settled wet or dry).
  input.waterKnown = input.waterKnown && water.settled() && !water.suspect();  // film suspected: unknown
  const auto out = controller.tick(now, input);
  digitalWrite(PUMP, out.pump ? HIGH : LOW);
  digitalWrite(GREEN, out.green ? HIGH : LOW);
  digitalWrite(RED, out.red ? HIGH : LOW);
  if (audioReady) {
    audio.alarm(out.alarm);
    audio.speak(out.voice);
  }
  if (uint32_t(now - lastReport) >= 1000) {
    lastReport = now;
    Serial.printf("mode=%d link=%d person=%d heart=%d temp_ok=%d object_C=%.2f room_C=%.2f water_ok=%d level_mm=%u low=%d full=%d suspect=%d pump=%d GR=%d%d\n",
      int(out.mode), link, input.person, input.heart, input.temperatureKnown,
      temperature.object(), temperature.room(), input.waterKnown, water.levelMM(), input.lowWater, input.fullWater, water.suspect(),
      out.pump, out.green, out.red);
    if (printRaw) {
      Serial.print("water_raw (bottom->top):");
      for (uint8_t v : lastWaterRaw) Serial.printf(" %u", v);
      Serial.println();
    }
  }
  delay(5);
}
