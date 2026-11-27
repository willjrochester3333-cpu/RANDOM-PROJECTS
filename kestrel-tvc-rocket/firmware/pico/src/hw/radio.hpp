// Telemetry radio on the board's radio socket J7 (Pixhawk TELEM pinout): UART1, GP4 = TX to the radio, GP5 = RX from it.
// SiK radios talk 57600 baud 8N1 by default (SERIAL_SPEED=57); nothing here changes the radio's own settings.
#pragma once
#include <cstdint>

#include "../logic/radio_link.hpp"

namespace hw {

class RadioUart {
public:
    void init(uint32_t baud = 57600);
    // Call every loop: hands received bytes to the link and tops up the 32-byte hardware TX FIFO (never blocks).
    void service(kestrel::RadioLink& link, uint32_t now_ms);
    uint32_t baud() const { return baud_; }
private:
    uint32_t baud_{57600};
};

}  // namespace hw
