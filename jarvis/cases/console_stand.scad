// CONSOLE - desk stand for a 7" touchscreen with the Pi 5 mounted on its back.
// Defaults are for the Raspberry Pi Touch Display 2 (7", landscape).
// MEASURE YOUR SCREEN and set disp_w / disp_h / disp_t before printing.
// Parts: "frame", "shroud", "assembly"
include <lib.scad>
part = "assembly";

disp_w = 189.32;   // glass width
disp_h = 120.24;   // glass height
disp_t = 9.0;      // glass + panel thickness at the edge
fit    = 0.5;

lip     = 4;       // how much bezel the front lip covers
front_t = 2.4;
back_t  = 4;
side    = 4;
ledge   = 8;       // back ledge that holds the screen in
tilt    = 20;      // lean-back angle from vertical
foot_d  = 95;      // depth of the rear shroud (= stability)
sh_wall = 3;

T  = front_t + disp_t + fit + back_t;   // frame thickness
Ws = disp_w + 2 * side;                 // overall width
tn = tan(tilt);

// tongues on the frame back that the shroud screws onto (sideways M3 screws)
tongue = [8, 18, 10];
tongue_y = [22, 82];
tongue_x = Ws / 2 - sh_wall - 0.3 - tongue.x;

// ---- frame: x across, y up the screen, z = 0 at the front face ----
module frame() {
    difference() {
        union() {
            difference() {
                translate([-Ws / 2, -side, 0]) rbox([Ws, disp_h + side, T], 3);
                // screen pocket, open at the top so the screen slides in
                translate([-(disp_w + fit) / 2, 0, front_t]) cube([disp_w + fit, disp_h + 1, disp_t + fit]);
                // front window
                translate([-disp_w / 2 + lip, lip, -1]) cube([disp_w - 2 * lip, disp_h + 1, front_t + 2]);
                // back window (open to the top for the Pi and its standoffs)
                translate([-disp_w / 2 + ledge, ledge, front_t + disp_t]) cube([disp_w - 2 * ledge, disp_h + 1, back_t + 2]);
            }
            for (s = [-1, 1], y = tongue_y)
                translate([s > 0 ? tongue_x : -tongue_x - tongue.x, y, T - 0.01]) cube(tongue);
        }
        // M3 self-tap pilots, sideways into the tongues
        for (s = [-1, 1], y = tongue_y)
            translate([s * (tongue_x - 1), y + tongue.y / 2, T + tongue.z / 2])
                rotate([0, s * 90, 0]) cylinder(d = 2.6, h = tongue.x + 2);
    }
}

// ---- rear shroud: wedge that covers the Pi and is the foot of the stand ----
// profile in (y, depth-behind-frame); the long lower edge lies flat on the desk
function prof(e) = [[-e * tn - side, -e], [foot_d * tn - side, foot_d],
                    [disp_h - 2 + e * (disp_h - 2 - foot_d * tn + side) / foot_d, -e]];

module wedge(w, inset) {
    rotate([90, 0, 90]) linear_extrude(w)
        if (inset > 0) intersection() {
            offset(delta = -inset) polygon(prof(20));
            translate([-50, -1]) square([400, 400]);
        } else polygon(prof(0));
}

module shroud() {
    difference() {
        translate([-Ws / 2, 0, T]) wedge(Ws, 0);
        translate([-Ws / 2 + sh_wall, 0, T]) wedge(Ws - 2 * sh_wall, sh_wall);
        // side screw holes (M3 clearance)
        for (s = [-1, 1], y = tongue_y)
            translate([s * (Ws / 2 + 1), y + tongue.y / 2, T + tongue.z / 2])
                rotate([0, -s * 90, 0]) cylinder(d = 3.4, h = sh_wall + 2);
        // cable ports, both sides (USB-C power, USB mic/speaker)
        for (s = [-1, 1])
            translate([s * (Ws / 2 + 1), 42, T + 36]) rotate([0, -s * 90, 0])
                hull() for (dz = [0, 22]) translate([-dz, 0, 0]) cylinder(d = 16, h = sh_wall + 2);
        // exhaust slots through the upper face
        for (i = [-5 : 5])
            translate([i * 14 - 2, 45, T + 18]) cube([4, 100, 34]);
    }
}

module upright() {   // rotate so the desk is the XY plane
    rotate([90 + tilt, 0, 0]) children();
}

if (part == "frame") frame();                                  // print front face down
if (part == "shroud") translate([0, 0, -T]) shroud();          // print open face down
if (part == "assembly") upright() {
    color("#30343b") frame();
    color("#e0a526") shroud();
    color("#0b0d10") translate([-disp_w / 2, 0, front_t]) cube([disp_w, disp_h, disp_t]);
}
