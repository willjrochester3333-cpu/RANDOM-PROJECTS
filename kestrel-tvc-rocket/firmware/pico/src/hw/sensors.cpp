#include "sensors.hpp"

#include <initializer_list>

#include "../board.hpp"
#include "hardware/gpio.h"
#include "hardware/spi.h"
#include "pico/stdlib.h"

namespace hw {

namespace {
inline void cs_low(uint cs) {
    asm volatile("nop \n nop \n nop");
    gpio_put(cs, 0);
    asm volatile("nop \n nop \n nop");
}
inline void cs_high(uint cs) {
    asm volatile("nop \n nop \n nop");
    gpio_put(cs, 1);
    asm volatile("nop \n nop \n nop");
}
}  // namespace

void spi_init_bus() {
    spi_init(spi0, board::SPI_HZ);
    spi_set_format(spi0, 8, SPI_CPOL_1, SPI_CPHA_1, SPI_MSB_FIRST);   // mode 3: fine for all three chips
    gpio_set_function(board::SPI_MISO, GPIO_FUNC_SPI);
    gpio_set_function(board::SPI_SCK, GPIO_FUNC_SPI);
    gpio_set_function(board::SPI_MOSI, GPIO_FUNC_SPI);
    for (uint cs : {board::CS_IMU, board::CS_BARO, board::CS_FLASH}) {
        gpio_init(cs);
        gpio_set_dir(cs, GPIO_OUT);
        gpio_put(cs, 1);
    }
}

void spi_read(uint cs, uint8_t reg, uint8_t* buf, size_t n) {
    const uint8_t a = reg | 0x80u;
    cs_low(cs);
    spi_write_blocking(spi0, &a, 1);
    spi_read_blocking(spi0, 0x00, buf, n);
    cs_high(cs);
}

void spi_write(uint cs, uint8_t reg, uint8_t val) {
    const uint8_t b[2] = {static_cast<uint8_t>(reg & 0x7Fu), val};
    cs_low(cs);
    spi_write_blocking(spi0, b, 2);
    cs_high(cs);
}

// ============================================================================ LSM6DSO
namespace lsm {
constexpr uint8_t WHO_AM_I = 0x0F, CTRL1_XL = 0x10, CTRL2_G = 0x11, CTRL3_C = 0x12, CTRL4_C = 0x13,
                  CTRL9_XL = 0x18, OUTX_L_G = 0x22;
constexpr float GYRO_RADS_PER_LSB = 0.070f * 3.14159265f / 180.0f;   // +/-2000 dps
constexpr float ACC_MS2_PER_LSB = 0.488e-3f * 9.80665f;              // +/-16 g
}  // namespace lsm

bool Lsm6dso::init() {
    const uint cs = board::CS_IMU;
    spi_read(cs, lsm::WHO_AM_I, &id_, 1);
    if (id_ != 0x6C) return ok_ = false;
    spi_write(cs, lsm::CTRL3_C, 0x01);        // software reset
    sleep_ms(20);
    spi_write(cs, lsm::CTRL3_C, 0x44);        // BDU + auto-increment
    spi_write(cs, lsm::CTRL4_C, 0x04);        // I2C interface off (SPI only)
    spi_write(cs, lsm::CTRL9_XL, 0xE2);       // I3C off (DEN bits at default)
    spi_write(cs, lsm::CTRL1_XL, 0x74);       // accel 833 Hz, +/-16 g
    spi_write(cs, lsm::CTRL2_G, 0x7C);        // gyro 833 Hz, +/-2000 dps
    uint8_t c[2] = {0, 0};
    spi_read(cs, lsm::CTRL1_XL, c, 2);
    ok_ = (c[0] == 0x74 && c[1] == 0x7C);
    sleep_ms(30);                             // first samples after power-up are discarded by the core's averaging
    return ok_;
}

bool Lsm6dso::read(float g[3], float a[3]) {
    uint8_t b[12];
    spi_read(board::CS_IMU, lsm::OUTX_L_G, b, 12);
    bool all_same = true;
    for (int i = 1; i < 12; ++i) all_same &= (b[i] == b[0]);
    if (all_same && (b[0] == 0x00 || b[0] == 0xFF)) {      // bus stuck / chip gone
        if (++bad_reads_ > 50) ok_ = false;
        return false;
    }
    bad_reads_ = 0;
    for (int i = 0; i < 3; ++i) {
        const int16_t rg = static_cast<int16_t>(b[2 * i] | (b[2 * i + 1] << 8));
        const int16_t ra = static_cast<int16_t>(b[6 + 2 * i] | (b[6 + 2 * i + 1] << 8));
        g[i] = rg * lsm::GYRO_RADS_PER_LSB;
        a[i] = ra * lsm::ACC_MS2_PER_LSB;
    }
    return true;
}

// ============================================================================ BMP580/581
namespace bmp {
constexpr uint8_t CHIP_ID = 0x01, INT_CONFIG = 0x14, INT_SOURCE = 0x15, TEMP_XLSB = 0x1D, INT_STATUS = 0x27,
                  STATUS = 0x28, OSR_CONFIG = 0x36, ODR_CONFIG = 0x37, OSR_EFF = 0x38, CMD = 0x7E;
}

bool Bmp58x::init() {
    const uint cs = board::CS_BARO;
    uint8_t v = 0;
    spi_read(cs, bmp::CHIP_ID, &v, 1);        // dummy read: first CSB edge switches the chip to SPI
    spi_write(cs, bmp::CMD, 0xB6);            // soft reset (returns to I2C mode...)
    sleep_ms(3);
    spi_read(cs, bmp::CHIP_ID, &v, 1);        // ...so do the dummy read again
    spi_read(cs, bmp::CHIP_ID, &id_, 1);
    if (id_ != 0x50 && id_ != 0x51) return ok_ = false;
    spi_read(cs, bmp::INT_STATUS, &v, 1);     // clear POR flag
    spi_read(cs, bmp::STATUS, &v, 1);
    if (!(v & 0x02) || (v & 0x04)) return ok_ = false;   // NVM not ready / NVM error
    spi_write(cs, bmp::ODR_CONFIG, 0x80);     // standby, deep standby disabled
    sleep_ms(3);
    spi_write(cs, bmp::OSR_CONFIG, 0x58);     // pressure on, OSR_P 8x, OSR_T 1x
    spi_write(cs, bmp::INT_SOURCE, 0x01);     // data-ready flag
    spi_read(cs, bmp::INT_CONFIG, &v, 1);
    spi_write(cs, bmp::INT_CONFIG, static_cast<uint8_t>((v & 0xF0u) | 0x0Au));   // INT pin: enabled, push-pull, active high
    spi_write(cs, bmp::ODR_CONFIG, static_cast<uint8_t>(0x80u | (0x0Fu << 2) | 0x01u));   // 50 Hz, normal mode
    sleep_ms(3);
    spi_read(cs, bmp::OSR_EFF, &v, 1);
    ok_ = (v & 0x80u) != 0;                   // odr_is_valid
    return ok_;
}

bool Bmp58x::poll(float& p, float& t) {
    uint8_t s = 0;
    spi_read(board::CS_BARO, bmp::INT_STATUS, &s, 1);
    if (!(s & 0x01u)) return false;
    uint8_t b[6];
    spi_read(board::CS_BARO, bmp::TEMP_XLSB, b, 6);
    const int32_t traw = static_cast<int32_t>((static_cast<uint32_t>(b[2]) << 24) | (static_cast<uint32_t>(b[1]) << 16) |
                                              (static_cast<uint32_t>(b[0]) << 8)) >> 8;
    const uint32_t praw = (static_cast<uint32_t>(b[5]) << 16) | (static_cast<uint32_t>(b[4]) << 8) | b[3];
    t = static_cast<float>(traw) / 65536.0f;
    p = static_cast<float>(praw) / 64.0f;
    if (p < 20000.0f || p > 120000.0f) return false;
    return true;
}

// ============================================================================ W25Q128JV
void W25q::write_enable() {
    const uint8_t c = 0x06;
    cs_low(board::CS_FLASH);
    spi_write_blocking(spi0, &c, 1);
    cs_high(board::CS_FLASH);
}

void W25q::cmd_addr(uint8_t cmd, uint32_t addr) {
    const uint8_t b[4] = {cmd, static_cast<uint8_t>(addr >> 16), static_cast<uint8_t>(addr >> 8), static_cast<uint8_t>(addr)};
    spi_write_blocking(spi0, b, 4);
}

bool W25q::init() {
    uint8_t c = 0xAB;                         // release from power-down
    cs_low(board::CS_FLASH);
    spi_write_blocking(spi0, &c, 1);
    cs_high(board::CS_FLASH);
    sleep_us(50);
    c = 0x9F;
    uint8_t id[3] = {0, 0, 0};
    cs_low(board::CS_FLASH);
    spi_write_blocking(spi0, &c, 1);
    spi_read_blocking(spi0, 0, id, 3);
    cs_high(board::CS_FLASH);
    jedec_ = (static_cast<uint32_t>(id[0]) << 16) | (static_cast<uint32_t>(id[1]) << 8) | id[2];
    ok_ = (id[0] == 0xEF && id[2] == 0x18);  // Winbond, 128 Mbit (W25Q128JV-IQ: EF 40 18)
    return ok_;
}

bool W25q::busy() {
    const uint8_t c = 0x05;
    uint8_t s = 0;
    cs_low(board::CS_FLASH);
    spi_write_blocking(spi0, &c, 1);
    spi_read_blocking(spi0, 0, &s, 1);
    cs_high(board::CS_FLASH);
    return s & 0x01u;
}

void W25q::read(uint32_t addr, uint8_t* buf, size_t n) {
    cs_low(board::CS_FLASH);
    cmd_addr(0x03, addr);
    spi_read_blocking(spi0, 0, buf, n);
    cs_high(board::CS_FLASH);
}

void W25q::program_page_start(uint32_t addr, const uint8_t* data, size_t n) {
    write_enable();
    cs_low(board::CS_FLASH);
    cmd_addr(0x02, addr);
    spi_write_blocking(spi0, data, n);
    cs_high(board::CS_FLASH);
}

void W25q::erase_sector_start(uint32_t addr) {
    write_enable();
    cs_low(board::CS_FLASH);
    cmd_addr(0x20, addr);
    cs_high(board::CS_FLASH);
}

void W25q::erase_block_start(uint32_t addr) {
    write_enable();
    cs_low(board::CS_FLASH);
    cmd_addr(0xD8, addr);
    cs_high(board::CS_FLASH);
}

void W25q::erase_chip_start() {
    write_enable();
    const uint8_t c = 0xC7;
    cs_low(board::CS_FLASH);
    spi_write_blocking(spi0, &c, 1);
    cs_high(board::CS_FLASH);
}

}  // namespace hw
