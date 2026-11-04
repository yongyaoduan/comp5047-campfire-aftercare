#pragma once
#include <Arduino.h>
#include <atomic>
#include <math.h>
#include <driver/i2s.h>
#include "ControlState.h"
#include "AudioSamples.h"

// DMA feeds only DAC1/GPIO25. DAC2/GPIO26 remains the digital pump output.
class AudioPlayer {
 public:
  bool begin() {
    i2s_config_t config = {};
    config.mode = i2s_mode_t(I2S_MODE_MASTER | I2S_MODE_TX | I2S_MODE_DAC_BUILT_IN);
    config.sample_rate = AUDIO_RATE;
    config.bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT;
    config.channel_format = I2S_CHANNEL_FMT_ONLY_RIGHT;
    config.communication_format = I2S_COMM_FORMAT_STAND_MSB;
    config.dma_buf_count = 4;
    config.dma_buf_len = 128;
    config.tx_desc_auto_clear = false;
    if (i2s_driver_install(I2S_NUM_0, &config, 0, nullptr) != ESP_OK) return false;
    if (i2s_set_dac_mode(I2S_DAC_CHANNEL_RIGHT_EN) != ESP_OK) return false;
    return xTaskCreate(task, "audio-dma", 4096, this, 1, nullptr) == pdPASS;
  }
  void alarm(bool on) { alarm_.store(on); }
  void speak(ControlState::Voice voice) {
    if (voice != ControlState::Voice::None) {
      pending_.store(int(voice));
      revision_.fetch_add(1);
    }
  }
  void stop() {
    alarm_.store(false);
    pending_.store(0);
    revision_.fetch_add(1);
  }
 private:
  std::atomic<bool> alarm_{false};
  std::atomic<int> pending_{0};
  std::atomic<unsigned> revision_{0};
  static void task(void *context) { static_cast<AudioPlayer *>(context)->run(); }
  void run() {
    const uint8_t *clip = nullptr;
    size_t count = 0, offset = 0;
    unsigned seenRevision = 0;
    uint32_t toneSample = 0;
    for (;;) {
      const unsigned rev = revision_.load();
      if (rev != seenRevision) {
        seenRevision = rev;
        offset = count = 0;
        clip = nullptr;
        switch (ControlState::Voice(pending_.exchange(0))) {
          case ControlState::Voice::Water: clip = AUDIO_WATER; count = sizeof(AUDIO_WATER); break;
          case ControlState::Voice::Fire: clip = AUDIO_FIRE; count = sizeof(AUDIO_FIRE); break;
          case ControlState::Voice::Love: clip = AUDIO_LOVE; count = sizeof(AUDIO_LOVE); break;
          case ControlState::Voice::Spray: clip = AUDIO_SPRAY; count = sizeof(AUDIO_SPRAY); break;
          default: break;
        }
      }
      uint16_t buffer[128];
      const bool alarmOn = alarm_.load();
      // Alarm interrupts speech; returning to attended state silences it immediately.
      if (alarmOn) { clip = nullptr; count = offset = 0; }
      for (auto &sample : buffer) {
        uint8_t value = 128;
        if (alarmOn)
          value = uint8_t(128 + 45 * sinf(2 * PI * 880 * (toneSample++ % AUDIO_RATE) / AUDIO_RATE));
        else if (clip && offset < count) value = clip[offset++];
        sample = uint16_t(value) << 8;
      }
      size_t written = 0;
      i2s_write(I2S_NUM_0, buffer, sizeof(buffer), &written, portMAX_DELAY);
    }
  }
};
