include <src/core/standard.scad>
include <src/core/gridfinity-baseplate.scad>
use <src/core/gridfinity-rebuilt-utility.scad>
use <src/core/gridfinity-rebuilt-holes.scad>
use <src/helpers/generic-helpers.scad>
use <src/helpers/grid.scad>
use <gridfinity-rebuilt-baseplate.scad>


// ===== PARAMETERS ===== //

/* [Setup Parameters] */
$fa = 8;
$fs = 0.25;

/* [General Settings] */
// number of bases along x-axis
gridx = 9;
// number of bases along y-axis
gridy = 9;

/* [Screw Together Settings - Defaults work for M3 and 4-40] */
// screw diameter
d_screw = 3.35;
// screw head diameter
d_screw_head = 5;
// screw spacing distance
screw_spacing = .5;
// number of screws per grid block
n_screws = 1; // [1:3]


// /* [Fit to Drawer] */
// // minimum length of baseplate along x (leave zero to ignore, will automatically fill area if gridx is zero)
// distancex = 408 ;
// // minimum length of baseplate along y (leave zero to ignore, will automatically fill area if gridy is zero)
// distancey = 413 ;

// where to align extra space along x
fitx = 0; // [-1:0.1:1]
// where to align extra space along y
fity = 0; // [-1:0.1:1]


/* [Styles] */

// baseplate styles
style_plate = 3; // [0: thin, 1:weighted, 2:skeletonized, 3: screw together, 4: screw together minimal]


// hole styles
style_hole = 0; // [0:none, 1:countersink, 2:counterbore]

/* [Magnet Hole] */
// Baseplate will have holes for 6mm Diameter x 2mm high magnets.
enable_magnet = true;
// Magnet holes will have crush ribs to hold the magnet.
crush_ribs = false;
// Magnet holes will have a chamfer to ease insertion.
chamfer_holes = true;

hole_options = bundle_hole_options(refined_hole=false, magnet_hole=enable_magnet, screw_hole=false, crush_ribs=crush_ribs, chamfer=chamfer_holes, supportless=false);

// ===== IMPLEMENTATION ===== //

drawer_x = 408;
drawer_y = 413;
middle_x = 5;
middle_y = 5;
length = 42;

// 中间部分
distancex = length * middle_x;
distancey = length * middle_y ;
gridfinityBaseplate([0, 0], l_grid, [distancex, distancey], style_plate, hole_options, style_hole, [fitx, fity]);

// 右上角 
distancex_1 = 42 * floor(drawer_x/42/2) + (drawer_x - floor(drawer_x/42)*42)/2;
distancey_1 = 42 * floor((floor(drawer_y/42)- middle_y)/2) + (drawer_y - floor(drawer_y/42)*42)/2;
translate([distancex_1/2, length * middle_y/2 + distancey_1/2, 0])
    gridfinityBaseplate([0, 0], l_grid, [distancex_1, distancey_1], style_plate, hole_options, style_hole, [1, 1]);

// 左上角 
distancex_2 = drawer_x - distancex_1;
translate([- distancex_2/2, length * middle_y/2 + distancey_1/2, 0])
    gridfinityBaseplate([0, 0], l_grid, [distancex_2, distancey_1], style_plate, hole_options, style_hole, [-1, 1]);

// 右下角
distancey_5 = drawer_y - distancey_1 - length * middle_y;
translate([distancex_1/2, -(length * middle_y/2 + distancey_1/2), 0])
    gridfinityBaseplate([0, 0], l_grid, [distancex_1, distancey_5], style_plate, hole_options, style_hole, [1, -1]);

// 左下角
translate([-distancex_2/2, -(length * middle_y/2 + distancey_1/2), 0])
    gridfinityBaseplate([0, 0], l_grid, [distancex_2, distancey_5], style_plate, hole_options, style_hole, [-1, -1]);

// 右边
distancex_3 = 42 * floor((floor(drawer_x/42)- middle_x)/2) + (drawer_x - floor(drawer_x/42)*42)/2;
distancey_3 = length * middle_y;
translate([distancex/2 + distancex_4/2 + length , 0, 0])
    gridfinityBaseplate([0, 0], l_grid, [distancex_3, distancey_3], style_plate, hole_options, style_hole, [1, 1]);

// 左边
distancex_4 = drawer_x - distancex_3 - middle_x * length;
distancey_4 = length * middle_y;
translate([-(distancex/2 + distancex_4/2 + length), 0, 0])
    gridfinityBaseplate([0, 0], l_grid, [distancex_4, distancey_4], style_plate, hole_options, style_hole, [-1, -1]);

