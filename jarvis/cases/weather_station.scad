// OUTPOST - outdoor weather station for Raspberry Pi 3 + Sense HAT.
// Two chambers on three M4 threaded rods:
//   * sealed drum (Pi 3, O-ring lid, cable gland, pressure vent)
//   * louvred radiation shield underneath (Sense HAT in free air, out of sun and rain)
// Print in white ASA or PETG. PLA will warp and go brittle outdoors.
// Parts: "base", "louvre" (x6), "spider", "drum", "lid", "sunshade", "assembly", "section"
include <lib.scad>
$fn = 96;
part = "assembly";

R_o = 79;          // drum / louvre outer radius
wall = 5;
R_i = R_o - wall;
floor_t = 4;
drum_h = 46;
rod_r = 86;        // rod circle radius (rods stay OUTSIDE the sealed volume)
rod_d = 4.5;       // M4 clearance
col_r = 7;

base_t = 6;
pitch = 14;        // louvre spacing
louvre_h = 22;     // louvre height (overlaps the next one: no line of sight)
louvre_t = 2.4;
n_louvres = 6;
spider_h = 12;
lid_t = 4;
lid_r = 96;
shade_gap = 10;
shade_r = 100;

gland_d = 12.5;    // PG7 cable gland / M12 vent plug
boss_angles = [180, 300];   // 180 = vent, 300 = cable gland

module rods() { for (a = [0, 120, 240]) rotate(a) translate([rod_r, 0, 0]) children(); }
module rod_holes(h) { rods() translate([0, 0, -1]) cylinder(d = rod_d, h = h + 2); }

// --- base plate with wall / pole arm ---
module base() {
    arm_x = -112;
    difference() {
        union() {
            hull() { cylinder(r = R_o, h = base_t); rods() cylinder(r = col_r, h = base_t); }
            translate([arm_x, -22, 0]) cube([-arm_x - 60, 44, base_t]);
            // wall plate
            translate([arm_x, -32, 0]) rbox([6, 64, 70], 2);
            // gussets
            for (y = [-22, 18])
                translate([arm_x + 5, y, base_t - 0.01]) rotate([90, 0, 180]) translate([0, 0, -4])
                    mirror([1, 0, 0]) linear_extrude(4) polygon([[0, 0], [38, 0], [0, 56]]);
        }
        rod_holes(base_t);
        // drain / air holes
        for (a = [0 : 45 : 359]) rotate(a + 22.5) translate([40, 0, -1]) cylinder(d = 8, h = base_t + 2);
        cylinder(d = 24, h = 3 * base_t, center = true);
        // wall screws (5 mm) and hose-clamp slots for a pole
        for (z = [22, 56]) translate([arm_x - 1, 0, z]) rotate([0, 90, 0]) cylinder(d = 5.2, h = 8);
        for (y = [-26, 20], z = [30, 44]) translate([arm_x - 1, y, z]) cube([8, 6, 10]);
    }
}

// --- one louvre: sloped ring, prints wide side down with no supports ---
module louvre() {
    k = louvre_t * 1.414;
    difference() {
        union() {
            difference() {
                cylinder(r1 = R_o, r2 = R_o - louvre_h, h = louvre_h);
                translate([0, 0, -0.01]) cylinder(r1 = R_o - k, r2 = R_o - louvre_h - k, h = louvre_h + 0.02);
            }
            rods() { cylinder(r = col_r, h = pitch); translate([-12, -7, 0]) cube([12, 14, 5]); }
        }
        rod_holes(pitch);
    }
}

// --- spider: carries the Sense HAT under the drum, keeps an air gap ---
module spider() {
    hat = [58, 49];   // HAT mounting-hole rectangle
    difference() {
        union() {
            rods() cylinder(r = col_r, h = spider_h);
            translate([0, 0, spider_h - 3]) {
                for (a = [0, 120, 240]) rotate(a) translate([20, -5, 0]) cube([rod_r - 20, 10, 3]);
                translate([-35, -31, 0]) rbox([70, 62, 3], 4);
            }
        }
        rod_holes(spider_h);
        translate([-24, -19.5, 0]) rbox([48, 39, spider_h + 1], 4);
        for (x = [-1, 1], y = [-1, 1])
            translate([x * hat.x / 2, y * hat.y / 2, 0]) cylinder(d = 2.8, h = spider_h + 1);
    }
}

// --- sealed drum for the Pi 3 ---
module drum() {
    difference() {
        union() {
            difference() {
                union() { cylinder(r = R_o, h = drum_h); rods() { cylinder(r = col_r, h = drum_h); translate([-10, -7, 0]) cube([10, 14, drum_h]); } }
                translate([0, 0, floor_t]) cylinder(r = R_i, h = drum_h);
            }
            // flat bosses for the gland and the vent
            for (a = boss_angles) rotate(a) translate([R_i - 4, -11, 0]) cube([wall + 8, 22, 34]);
            // Pi standoffs (Pi rotated 180 so the GPIO header faces the ribbon slot)
            rotate(180) translate([-PI_L / 2, -PI_W / 2, floor_t - 0.5]) pi_holes() cylinder(r = 3.2, h = 6.5);
        }
        rod_holes(drum_h);
        rotate(180) translate([-PI_L / 2, -PI_W / 2, floor_t + 1]) pi_holes() cylinder(d = 2.1, h = 6);
        for (a = boss_angles) rotate(a) translate([R_i - 8, 0, 21]) rotate([0, 90, 0]) cylinder(d = gland_d, h = 24);
        // O-ring groove (2.5 mm silicone cord)
        translate([0, 0, drum_h - 1.9]) ring(R_i + 3.8, R_i + 1.2, 2);
        // GPIO ribbon slot to the sensor chamber (seal with silicone after fitting)
        translate([-12, -40.5, -1]) rbox([56, 5, floor_t + 2], 2);
    }
}

// --- lid: modelled as installed, underside at z = 0 ---
module lid() {
    difference() {
        union() {
            cylinder(r = lid_r, h = lid_t - 1.5);
            translate([0, 0, lid_t - 1.5]) cylinder(r1 = lid_r, r2 = lid_r - 1.5, h = 1.5);
            translate([0, 0, -4]) ring(R_i - 0.4, R_i - 3, 4.01);       // locating ring
            translate([0, 0, -5]) ring(lid_r, lid_r - 2.5, 5.01);       // drip edge
        }
        rod_holes(lid_t);
    }
}

module sunshade() {
    difference() {
        union() {
            translate([0, 0, shade_gap]) cylinder(r = shade_r, h = 2.4);
            rods() cylinder(r = col_r, h = shade_gap);
        }
        rod_holes(shade_gap + 3);
    }
}

z_spider = base_t + n_louvres * pitch;
z_drum = z_spider + spider_h;
z_lid = z_drum + drum_h;

module assembly() {
    color("#8d949e") base();
    for (i = [0 : n_louvres - 1]) color("#f2f2ee") translate([0, 0, base_t + i * pitch]) louvre();
    color("#e0a526") translate([0, 0, z_spider]) spider();
    color("#f2f2ee") translate([0, 0, z_drum]) drum();
    color("#f2f2ee") translate([0, 0, z_lid]) lid();
    color("#ffffff") translate([0, 0, z_lid + lid_t]) sunshade();
    color("#b0b0b0") rods() cylinder(d = 4, h = z_lid + lid_t + shade_gap + 10);
    // Sense HAT ghost (hangs under the spider) and Pi ghost
    color("#2e7d4f") translate([-32.5, -28.25, z_spider - 12]) cube([65, 56.5, 1.6]);
    color("#2e7d4f") translate([-PI_L / 2, -PI_W / 2, z_drum + floor_t + 6]) cube([PI_L, PI_W, 1.6]);
}

if (part == "base") base();
if (part == "louvre") louvre();
if (part == "spider") translate([0, 0, spider_h]) rotate([180, 0, 0]) spider();
if (part == "drum") drum();
if (part == "lid") translate([0, 0, lid_t]) rotate([180, 0, 0]) lid();
if (part == "sunshade") translate([0, 0, shade_gap + 2.4]) rotate([180, 0, 0]) sunshade();
if (part == "assembly") assembly();
if (part == "section") difference() { assembly(); translate([-200, -400, -10]) cube([400, 400, 400]); }
