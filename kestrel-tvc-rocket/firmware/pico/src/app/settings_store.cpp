#include "settings_store.hpp"

#include <cstring>

#include "hardware/flash.h"
#include "hardware/sync.h"
#include "pico/stdlib.h"

namespace app {

namespace {
constexpr uint32_t kOffset = PICO_FLASH_SIZE_BYTES - FLASH_SECTOR_SIZE;
static_assert(sizeof(kestrel::Settings) <= FLASH_PAGE_SIZE, "settings must fit one flash page");
}  // namespace

kestrel::Settings settings_load(bool* was_valid) {
    kestrel::Settings s;
    std::memcpy(&s, reinterpret_cast<const void*>(XIP_BASE + kOffset), sizeof s);
    const bool ok = kestrel::settings_valid(s);
    if (was_valid) *was_valid = ok;
    if (!ok) s = kestrel::Settings{};
    return s;
}

bool settings_save(kestrel::Settings& s) {
    kestrel::settings_seal(s);
    uint8_t page[FLASH_PAGE_SIZE];
    std::memset(page, 0xFF, sizeof page);
    std::memcpy(page, &s, sizeof s);
    const uint32_t irq = save_and_disable_interrupts();
    flash_range_erase(kOffset, FLASH_SECTOR_SIZE);
    flash_range_program(kOffset, page, FLASH_PAGE_SIZE);
    restore_interrupts(irq);
    return std::memcmp(reinterpret_cast<const void*>(XIP_BASE + kOffset), &s, sizeof s) == 0;
}

}  // namespace app
