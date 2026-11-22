// Persistent bench settings (axis calibration, servo trims/directions, motor) in the last 4 KB sector of the
// Pico 2 W's own 4 MB flash. Never written in flight.
#pragma once
#include "../logic/servo_map.hpp"

namespace app {

kestrel::Settings settings_load(bool* was_valid);
bool settings_save(kestrel::Settings& s);   // seals + programs + verifies

}  // namespace app
