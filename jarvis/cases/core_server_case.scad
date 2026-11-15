// CORE - Raspberry Pi 5 server case (room for Active Cooler + M.2 HAT+ NVMe)
// Parts: "base", "lid", "assembly"
include <lib.scad>
part = "assembly";

wall   = 2.4;
floor_t = 2.4;
lid_t  = 2.4;
stand  = 5;      // standoff height under the Pi
inner_h = 34;    // floor to underside of lid (Pi + cooler + NVMe HAT)
m_xlo = 7;       // margin, SD-card end (PCIe ribbon + screw bosses)
m_xhi = 0.5;     // USB / Ethernet end (connectors sit flush in the wall)
m_ylo = 0.5;     // USB-C / HDMI side
m_yhi = 7;       // GPIO side (screw bosses + airflow)

L = wall + m_xlo + PI_L + m_xhi + wall;
W = wall + m_ylo + PI_W + m_yhi + wall;
H = floor_t + inner_h;
X0 = wall + m_xlo;           // board origin inside the case
Y0 = wall + m_ylo;
board_top = floor_t + stand + 1.6;

boss_pos = [[wall + 2.9, wall + 2.9], [wall + 2.9, W - wall - 2.9], [L - wall - 2.9, W - wall - 2.9]];
usb_notch_y0 = Y0 + 1.5;
usb_notch_w  = 53.5;
usb_notch_h  = 17.5;         // opening height above the board top

module base() {
    difference() {
        union() {
            difference() {
                rbox([L, W, H], 4);
                translate([wall, wall, floor_t]) rbox([L - 2 * wall, W - 2 * wall, H], 2);
            }
            // Pi standoffs
            translate([X0, Y0, floor_t - 0.5]) pi_holes() cylinder(r = 3, h = stand + 0.5);
            // lid screw bosses
            for (p = boss_pos) translate([p.x, p.y, floor_t - 0.5]) cylinder(r = 3.4, h = inner_h + 0.5);
        }
        // Pi screws: M2.5 self-tap pilots
        translate([X0, Y0, floor_t - 1]) pi_holes() cylinder(d = 2.1, h = stand + 2);
        // lid screws: M3 self-tap pilots
        for (p = boss_pos) translate([p.x, p.y, H - 14]) cylinder(d = 2.6, h = 15);
        // USB-C power
        translate([X0 + 11.2 - 6.5, -1, board_top + 1.6 - 3.75]) cube([13, wall + 2, 7.5]);
        // 2x micro-HDMI
        for (x = [25.8, 39.2])
            translate([X0 + x - 5.5, -1, board_top + 1.5 - 4]) cube([11, wall + 2, 8]);
        // USB + Ethernet bay (open to the top so the board drops in; lid tab closes it)
        translate([L - wall - 1, usb_notch_y0, board_top - 0.5]) cube([wall + 2, usb_notch_w, H]);
        // intake slots, GPIO side
        for (i = [0 : 9])
            translate([X0 + 8 + i * 7, W - wall - 1, floor_t + 8]) cube([3, wall + 2, 18]);
        // rubber-foot recesses (8 mm bumpers)
        for (x = [10, L - 10], y = [10, W - 10])
            translate([x, y, -0.01]) cylinder(d = 8.5, h = 0.8);
    }
}

module lid() {
    difference() {
        union() {
            rbox([L, W, lid_t], 4);
            // tab that closes the top of the USB / Ethernet bay
            translate([L - wall, usb_notch_y0 + 0.2, -(H - board_top - usb_notch_h)])
                cube([wall, usb_notch_w - 0.4, H - board_top - usb_notch_h]);
        }
        // hex vent field over the board
        translate([X0 + 4, Y0 + 4, -1]) hexgrid(PI_L - 12, PI_W - 8, lid_t + 2);
        // countersunk M3 holes
        for (p = boss_pos) translate([p.x, p.y, -1]) {
            cylinder(d = 3.4, h = lid_t + 2);
            translate([0, 0, lid_t - 0.6]) cylinder(d1 = 3.4, d2 = 6.4, h = 1.7);
        }
    }
}

if (part == "base") base();
if (part == "lid") rotate([180, 0, 0]) lid();      // print flat side down
if (part == "assembly") {
    color("#30343b") base();
    color("#e0a526") translate([0, 0, H + 12]) lid();
    // board ghost
    color("#2e7d4f", 0.7) translate([X0, Y0, floor_t + stand]) cube([PI_L, PI_W, 1.6]);
}
