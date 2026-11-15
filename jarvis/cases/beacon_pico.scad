// BEACON - Pico 2 W light puck: 12-LED ring under a diffuser, buzzer, "on my way" button.
// Print "cup" and "plate" in a dark colour, "cap" in natural / white PETG (it is the diffuser).
// Parts: "cup", "plate", "cap", "assembly"
include <lib.scad>
$fn = 96;
part = "assembly";

D = 80;
H = 26;
wall = 2.4;
floor_t = 2.4;
Ri = D / 2 - wall;
stand = 4;
btn_d = 16.2;      // 16 mm momentary push button on the side
pico_x0 = Ri - 0.4 - 51;   // board runs along X, micro-USB end against the wall
usb_z = floor_t + stand + 1 + 1.4;
plate_z = H - 3;           // LED plate rests on the ribs

module pico_holes() { for (x = [2, 49], y = [-5.7, 5.7]) translate([pico_x0 + x, y, 0]) children(); }

module cup() {
    difference() {
        union() {
            difference() {
                cylinder(d = D, h = H);
                translate([0, 0, floor_t]) cylinder(r = Ri, h = H);
            }
            translate([0, 0, floor_t - 0.5]) pico_holes() cylinder(r = 2.3, h = stand + 0.5);
            // ribs that carry the LED plate
            for (a = [50, 130, 230, 310]) rotate(a) translate([Ri - 3, -2, floor_t - 0.5]) cube([3.5, 4, plate_z - floor_t + 0.5]);
        }
        translate([0, 0, floor_t + 0.6]) pico_holes() cylinder(d = 1.7, h = stand);   // M2 self-tap
        // micro-USB plug notch
        translate([Ri - 1, -6, usb_z - 4]) cube([wall + 2, 12, 8]);
        // side button
        rotate(180) translate([Ri - 1, 0, 15]) rotate([0, 90, 0]) cylinder(d = btn_d, h = wall + 2);
        // buzzer sound slots
        for (i = [-2 : 2]) rotate(90 + i * 9) translate([Ri - 1, -1, 6]) cube([wall + 2, 2, 10]);
    }
}

module plate() {
    difference() {
        cylinder(r = Ri - 0.3, h = 2);
        translate([0, 0, -1]) cylinder(d = 14, h = 4);                        // wiring
        for (a = [50, 130, 230, 310]) rotate(a) translate([Ri - 6, 0, -1]) cylinder(d = 3, h = 4);   // finger holes
    }
}

module cap() {   // modelled as installed: sits on the cup rim
    cap_h = 16;
    difference() {
        union() {
            cylinder(d = D, h = cap_h - 3);
            translate([0, 0, cap_h - 3]) cylinder(d1 = D, d2 = D - 5, h = 3);
            translate([0, 0, -2.5]) ring(Ri - 0.15, Ri - 1.8, 2.51);          // push-fit spigot
        }
        translate([0, 0, -0.01]) cylinder(r = Ri - 1.8, h = cap_h - 1.0);     // 1 mm top = diffuser
    }
}

if (part == "cup") cup();
if (part == "plate") plate();
if (part == "cap") translate([0, 0, 16]) rotate([180, 0, 0]) cap();   // print top down
if (part == "assembly") {
    color("#30343b") cup();
    color("#e0a526") translate([0, 0, H + 8]) plate();
    color("#f4f4f0", 0.85) translate([0, 0, H + 24]) cap();
    color("#2e7d4f") translate([pico_x0, -10.5, floor_t + stand]) cube([51, 21, 1]);
}
