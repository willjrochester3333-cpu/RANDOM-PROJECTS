// SPI0 bus + drivers for the LSM6DSO IMU, BMP580 barometer and W25Q128JV log flash.
#pragma once
#include <cstddef>
#include <cstdint>

#include "pico/types.h"

namespace hw {

void spi_init_bus();
void spi_read(uint cs, uint8_t reg, uint8_t* buf, size_t n);   // register read (reg | 0x80)
void spi_write(uint cs, uint8_t reg, uint8_t val);

// ---------------------------------------------------------------- LSM6DSO (6-axis IMU)
class Lsm6dso {
public:
    bool init();                                   // false = not found / config did not stick
    bool read(float gyro_rads[3], float accel_ms2[3]);   // sensor axes, SI units
    bool ok() const { return ok_; }
    uint8_t who_am_i() const { return id_; }
private:
    bool ok_{false};
    uint8_t id_{0};
    uint32_t bad_reads_{0};
};

// ---------------------------------------------------------------- BMP580 / BMP581 (barometer)
class Bmp58x {
public:
    bool init();                                   // 50 Hz normal mode, OSR_P 8x
    bool poll(float& pressure_pa, float& temp_c);  // true when a new sample has been read
    bool ok() const { return ok_; }
    uint8_t chip_id() const { return id_; }
private:
    bool ok_{false};
    uint8_t id_{0};
};

// ---------------------------------------------------------------- W25Q128JV (16 MB SPI NOR flash)
class W25q {
public:
    static constexpr uint32_t kSize = 16u * 1024u * 1024u;
    static constexpr uint32_t kPage = 256;
    static constexpr uint32_t kSector = 4096;
    bool init();                                   // checks the JEDEC id (EF 40 18)
    uint32_t jedec() const { return jedec_; }
    bool busy();
    void read(uint32_t addr, uint8_t* buf, size_t n);
    void program_page_start(uint32_t addr, const uint8_t* data, size_t n);   // returns at once; poll busy()
    void erase_sector_start(uint32_t addr);        // 4 KB
    void erase_block_start(uint32_t addr);         // 64 KB
    void erase_chip_start();
    bool ok() const { return ok_; }
private:
    void cmd_addr(uint8_t cmd, uint32_t addr);
    void write_enable();
    bool ok_{false};
    uint32_t jedec_{0};
};

}  // namespace hw
