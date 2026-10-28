#pragma once

#include "esphome.h"
#include <SPI.h>
#include <PN5180.h>
#include <PN5180ISO14443.h>

namespace esphome {
namespace pn5180 {

class PN5180Component;

class TagTrigger : public Trigger<std::string> {
 public:
  explicit TagTrigger(PN5180Component *parent) {}
};

class TagRemovedTrigger : public Trigger<> {
 public:
  explicit TagRemovedTrigger(PN5180Component *parent) {}
};

class PN5180Component : public PollingComponent {
 protected:
  uint8_t pin_cs_;
  uint8_t pin_busy_;
  uint8_t pin_rst_;
  PN5180ISO14443 *nfc_{nullptr};

  bool is_present_{false};
  std::string active_uid_{""};
  uint8_t missed_reads_{0};

  std::vector<TagTrigger *> tag_triggers_;
  std::vector<TagRemovedTrigger *> tag_removed_triggers_;

 public:
  // 350ms Abfrageintervall: Entlastet SPI-Bus und CPU spürbar
  PN5180Component(uint8_t pin_cs, uint8_t pin_busy, uint8_t pin_rst)
      : PollingComponent(350), pin_cs_(pin_cs), pin_busy_(pin_busy), pin_rst_(pin_rst) {}

  void register_tag_trigger(TagTrigger *trigger) { tag_triggers_.push_back(trigger); }
  void register_tag_removed_trigger(TagRemovedTrigger *trigger) { tag_removed_triggers_.push_back(trigger); }

  void setup() override {
    ESP_LOGI("pn5180", "Initialisiere PN5180 SPI...");
    nfc_ = new PN5180ISO14443(pin_cs_, pin_busy_, pin_rst_);
    nfc_->begin();
    nfc_->reset();
    nfc_->setupRF();
    ESP_LOGI("pn5180", "PN5180 betriebsbereit.");
  }

  void update() override {
    if (!nfc_) return;

    if (digitalRead(pin_busy_) == HIGH) {
      ESP_LOGW("pn5180", "BUSY klemmt -> Reset");
      nfc_->reset();
      nfc_->setupRF();
      return;
    }

    uint8_t uid[10];
    uint8_t uidLength = nfc_->readCardSerial(uid);
    yield(); // Dem ESP32 Netzwerk-Stack kurz Rechenzeit geben

    if (uidLength > 0) {
      missed_reads_ = 0;

      char hex_str[30];
      int pos = 0;
      for (int i = 0; i < uidLength; i++) {
        pos += sprintf(hex_str + pos, (i == uidLength - 1) ? "%02X" : "%02X-", uid[i]);
      }
      std::string current_uid(hex_str);

      // Nur triggern, wenn die Figur wirklich neu aufgelegt oder gewechselt wurde
      if (!is_present_ || current_uid != active_uid_) {
        is_present_ = true;
        active_uid_ = current_uid;

        ESP_LOGI("pn5180", "Figur erkannt: %s", active_uid_.c_str());
        for (auto *trig : tag_triggers_) {
          trig->trigger(active_uid_);
        }
      }
    } else {
      if (is_present_) {
        missed_reads_++;
        // Erst nach 5 aufeinanderfolgenden Fehlmessungen (~1.75 Sekunden)
        // als "abgehoben" werten. Das filtert Zwischen-Timeouts komplett heraus.
        if (missed_reads_ >= 5) {
          is_present_ = false;
          ESP_LOGI("pn5180", "Figur abgehoben (vorher: %s)", active_uid_.c_str());
          active_uid_ = "";
          missed_reads_ = 0;
          for (auto *trig : tag_removed_triggers_) {
            trig->trigger();
          }
        }
      }
    }
  }
};

}  // namespace pn5180
}  // namespace esphome