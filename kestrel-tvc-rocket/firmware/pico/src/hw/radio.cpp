#include "radio.hpp"

#include "../board.hpp"
#include "hardware/gpio.h"
#include "hardware/uart.h"

namespace hw {

void RadioUart::init(uint32_t baud) {
    baud_ = uart_init(uart1, baud);
    gpio_set_function(board::RADIO_TX, GPIO_FUNC_UART);
    gpio_set_function(board::RADIO_RX, GPIO_FUNC_UART);
    gpio_pull_up(board::RADIO_RX);            // idle-high when no radio is plugged in (no garbage bytes)
    uart_set_format(uart1, 8, 1, UART_PARITY_NONE);
    uart_set_hw_flow(uart1, false, false);    // CTS / RTS are not wired (SiK RTSCTS=0, its default)
    uart_set_fifo_enabled(uart1, true);
}

void RadioUart::service(kestrel::RadioLink& link, uint32_t now_ms) {
    for (int k = 0; k < 64 && uart_is_readable(uart1); ++k) link.rx_byte(static_cast<uint8_t>(uart_getc(uart1)), now_ms);
    // at 57600 baud the FIFO empties 11.5 bytes per 2 ms loop; 32 bytes of FIFO keep the line busy between loops
    while (link.tx_pending() > 0 && uart_is_writable(uart1)) {
        uint8_t b;
        link.tx_pop(&b, 1);
        uart_putc_raw(uart1, static_cast<char>(b));
    }
}

}  // namespace hw
