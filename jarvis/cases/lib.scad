// Shared helpers for the J.A.R.V.I.S. enclosures. All dimensions in mm.
$fn = 64;

// Box with rounded vertical edges, origin at the lower-left corner.
module rbox(size, r = 3) {
    hull()
        for (x = [r, size.x - r], y = [r, size.y - r])
            translate([x, y, 0]) cylinder(r = r, h = size.z);
}

// Raspberry Pi (3B / 5) mounting-hole pattern, board origin at the corner
// next to the SD card / USB power end. Board is 85 x 56.
PI_L = 85;
PI_W = 56;
module pi_holes() {
    for (p = [[3.5, 3.5], [61.5, 3.5], [3.5, 52.5], [61.5, 52.5]])
        translate(p) children();
}

// Field of hexagonal vent holes covering w x d, cut depth h.
module hexgrid(w, d, h, flat = 6, web = 2) {
    px = flat + web;
    py = px * 0.866;
    nx = floor(w / px);
    ny = floor(d / py);
    ox = (w - (nx - 0.5) * px) / 2;
    oy = (d - (ny - 1) * py) / 2;
    for (j = [0 : ny - 1], i = [0 : nx - 1 - (j % 2)])
        translate([ox + i * px + (j % 2) * px / 2, oy + j * py, 0])
            rotate(30) cylinder(d = flat / 0.866, h = h, $fn = 6);
}

// Ring (tube) helper.
module ring(ro, ri, h) {
    difference() {
        cylinder(r = ro, h = h);
        translate([0, 0, -0.01]) cylinder(r = ri, h = h + 0.02);
    }
}
