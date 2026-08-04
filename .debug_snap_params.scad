include <BOSL2/std.scad>
include <BOSL2/joiners.scad>
$fn=48;
translate([0,0,0]) snap_pin("small", anchor=CENTER, orient=UP);
translate([8,0,0]) snap_pin("small", d=3.2, anchor=CENTER, orient=UP);
translate([16,0,0]) snap_pin("small", l=6, anchor=CENTER, orient=UP);
translate([24,0,0]) snap_pin("small", snap=0.4, anchor=CENTER, orient=UP);
translate([32,0,0]) snap_pin("small", nub_depth=1.2, anchor=CENTER, orient=UP);
translate([40,0,0]) snap_pin("small", thickness=1.0, anchor=CENTER, orient=UP);
translate([48,0,0]) snap_pin("small", clearance=0.2, anchor=CENTER, orient=UP);
translate([56,0,0]) snap_pin("small", preload=0.16, anchor=CENTER, orient=UP);
