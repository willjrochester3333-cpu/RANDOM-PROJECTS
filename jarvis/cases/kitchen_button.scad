// DINNER BELL - kitchen button puck for the XIAO ESP32-S3 Sense + LED arcade button.
// Parts: "body", "base", "assembly"
include <lib.scad>
$fn = 96;
part = "assembly";

D = 84;
H = 58;
wall = 2.4;
top_t = 3;
base_t = 2.4;
btn_hole = 28;     // 30 mm LED arcade button. Use 24 for the 24 mm type. Check yours.
Ri = D / 2 - wall;
boss_r = Ri - 3.2;
boss_a = [90, 210, 330];

xiao = [21.3, 18.1];          // board pocket (board is 21 x 17.8)
shelf = 2.6;                  // board height above the base plate
usb_z = base_t + shelf + 1.2 + 1.6;

module body() {
    difference() {
        union() {
            difference() {
                union() {
                    cylinder(d = D, h = H - 4);
                    translate([0, 0, H - 4]) cylinder(d1 = D, d2 = D - 6, h = 4);
                }
                translate([0, 0, -0.01]) cylinder(r = Ri, h = H - top_t);
            }
            // full-height screw ribs (so the body prints top-down without supports)
            for (a = boss_a) rotate(a) translate([boss_r, 0, base_t + 0.2]) cylinder(r = 3.4, h = H - base_t - 1);
        }
        translate([0, 0, H - top_t - 1]) cylinder(d = btn_hole, h = top_t + 2);
        for (a = boss_a) rotate(a) translate([boss_r, 0, 0]) cylinder(d = 2.6, h = 14);
        // USB-C plug notch
        translate([Ri - 2, -6.5, -0.01]) cube([wall + 4, 13, usb_z + 4]);
        // microphone holes (the Sense board's mic, for voice later)
        for (i = [-1 : 1]) rotate(180 + i * 8) translate([Ri - 1, 0, 22]) rotate([0, 90, 0]) cylinder(d = 1.6, h = wall + 2);
    }
}

module base() {
    difference() {
        union() {
            cylinder(r = Ri - 0.25, h = base_t);
            // XIAO cradle, USB-C end against the wall
            translate([Ri - 0.6 - xiao.x - 1.5, -xiao.y / 2 - 1.8, base_t - 0.01])
                cube([xiao.x + 1.5, xiao.y + 3.6, shelf + 1.4]);
        }
        translate([Ri - 0.6 - xiao.x, -xiao.y / 2, base_t + shelf]) cube([xiao.x + 5, xiao.y, 5]);
        // relief under the board for solder joints
        translate([Ri - 0.6 - xiao.x + 2, -xiao.y / 2 + 2.5, base_t + 0.6]) cube([xiao.x + 5, xiao.y - 5, 5]);
        for (a = boss_a) rotate(a) translate([boss_r, 0, -1]) {
            cylinder(d = 3.4, h = base_t + 2);
            cylinder(d1 = 6.6, d2 = 3.4, h = 2.6);
        }
    }
}

if (part == "body") translate([0, 0, H]) rotate([180, 0, 0]) body();   // print top down
if (part == "base") base();
if (part == "assembly") {
    color("#30343b") body();
    color("#e0a526") translate([0, 0, -18]) base();
    color("#d6402b") translate([0, 0, H]) cylinder(d = 33, h = 9);
}
