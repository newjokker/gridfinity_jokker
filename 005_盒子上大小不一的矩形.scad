// ===== INFORMATION ===== //
/*
 修改说明：将圆形改为矩形，添加矩形参数控制
*/

include <src/core/standard.scad>
use <src/core/gridfinity-rebuilt-utility.scad>
use <src/core/gridfinity-rebuilt-holes.scad>
use <src/core/bin.scad>
use <src/core/cutouts.scad>
use <src/helpers/generic-helpers.scad>
use <src/helpers/grid.scad>
use <src/helpers/grid_element.scad>
use <src/helpers/generic-helpers.scad>

// ===== PARAMETERS ===== //

/* [Setup Parameters] */
$fa = 4;
$fs = 0.25; // .01

/* [General Settings] */
// number of bases along x-axis
gridx = 1;
// number of bases along y-axis
gridy = 3;
// bin height. See bin height information and "gridz_define" below.
gridz = 3; //.1

// Half grid sized bins.  Implies "only corners".
half_grid = false;

/* [Height] */
// How "gridz" is used to calculate height.  Some exclude 7mm/1U base, others exclude ~3.5mm (4.4mm nominal) stacking lip.
gridz_define = 0; // [0:7mm increments - Excludes Stacking Lip, 1:Internal mm - Excludes Base & Stacking Lip, 2:External mm - Excludes Stacking Lip, 3:External mm]
// Overrides internal block height of bin (for solid containers). Leave zero for default height. Units: mm
height_internal = 0;
// snap gridz height to nearest 7mm increment
enable_zsnap = false;
// If the top lip should exist.  Not included in height calculations.
include_lip = true;

/* [Compartments] */
// number of X Divisions (set to zero to have solid bin)
divx = 1;
// number of Y Divisions (set to zero to have solid bin)
divy = 1;
// Leave zero for default. Units: mm
depth = 0;  //.1

/* [矩形参数] */
// 矩形长度 (X轴方向)
rectangle_length = 20; // .1
// 矩形宽度 (Y轴方向)  
rectangle_width = 15; // .1
// 矩形高度 (Z轴方向) - 如果为0则使用bin深度
rectangle_height = 0; // .1
// 圆角半径
corner_radius = 2; // .1
// 旋转角度 (度)
rotation_angle = 0; // [-45:45]

/* [Compartment Features] */
// the type of tabs
style_tab = 3; //[0:Full,1:Auto,2:Left,3:Center,4:Right,5:None]
// which divisions have tabs
place_tab = 0; // [0:Everywhere-Normal,1:Top-Left Division]
// scoop weight percentage. 0 disables scoop, 1 is regular scoop. Any real number will scale the scoop.
scoop = 1; //[0:0.1:1]

/* [Base Hole Options] */
// only cut magnet/screw holes at the corners of the bin to save uneccesary print time
only_corners = false;
//Use gridfinity refined hole style. Not compatible with magnet_holes!
refined_holes = false;
// Base will have holes for 6mm Diameter x 2mm high magnets.
magnet_holes = true;
// Base will have holes for M3 screws.
screw_holes = true;
// Magnet holes will have crush ribs to hold the magnet.
crush_ribs = true;
// Magnet/Screw holes will have a chamfer to ease insertion.
chamfer_holes = true;
// Magnet/Screw holes will be printed so supports are not needed.
printable_hole_top = true;
// Enable "gridfinity-refined" thumbscrew hole in the center of each base: https://www.printables.com/model/413761-gridfinity-refined
enable_thumbscrew = false;

hole_options = bundle_hole_options(refined_holes, magnet_holes, screw_holes, crush_ribs, chamfer_holes, printable_hole_top);


// ===== 模块定义 ===== //

bin_11 = new_bin(
    grid_size = [gridx, gridy],
    height_mm = height(gridz, gridz_define, enable_zsnap),
    fill_height = height_internal,
    include_lip = include_lip,
    hole_options = hole_options,
    only_corners = only_corners || half_grid,
    thumbscrew = enable_thumbscrew,
    grid_dimensions = GRID_DIMENSIONS_MM / (half_grid ? 2 : 1)
);

// 矩形模块（带圆角）
module rounded_rectangle(size = [20, 15], r = 2, center = false) {
    x = size[0];
    y = size[1];
    
    if (r <= 0) {
        // 如果没有圆角，使用简单矩形
        square([x, y], center = center);
    } else {
        // 限制圆角半径不超过矩形尺寸的一半
        r_limited = min(r, min(x, y)/2);
        
        // 创建带圆角的矩形
        hull() {
            // 四个角的圆形
            translate([-x/2 + r_limited, -y/2 + r_limited]) circle(r = r_limited);
            translate([x/2 - r_limited, -y/2 + r_limited]) circle(r = r_limited);
            translate([-x/2 + r_limited, y/2 - r_limited]) circle(r = r_limited);
            translate([x/2 - r_limited, y/2 - r_limited]) circle(r = r_limited);
        }
    }
}

// 圆柱形矩形模块（拉伸矩形形成柱体）
module rectangular_pillar(length = 20, width = 15, height = 10, corner_radius = 2) {
    linear_extrude(height = height)
    rounded_rectangle(size = [length, width], r = corner_radius, center = true);
}

// 旋转矩形模块
module rotated_rectangular_pillar(length = 20, width = 15, height = 10, corner_radius = 2, angle = 0) {
    rotate([0, 0, angle])
    rectangular_pillar(length, width, height, corner_radius);
}


// ===== 主渲染部分 ===== //

bin_render(bin_11) {
    depth = bin_get_infill_size_mm(bin_11).z;
    actual_rect_height = (rectangle_height > 0) ? rectangle_height : depth;
    
    bin_subdivide(bin_11, [1, 2]) {
        translate([0, 0, -actual_rect_height/2])  // 居中放置
        
        child_per_element() {
            
            // 每个子元素创建一个矩形柱
            rotated_rectangular_pillar(
                length = 35.5,
                width = 80.1,
                height = 21.5/2,
                corner_radius = corner_radius,
                angle = 0
            );
            
            // 重复相同的矩形（根据你的原始代码有4个子元素）
            rotated_rectangular_pillar(
                length = 10,
                width = 26,
                height = 10.5,
                corner_radius = corner_radius,
                angle = rotation_angle
            );
            
            rotated_rectangular_pillar(
                length = rectangle_length,
                width = rectangle_width,
                height = actual_rect_height,
                corner_radius = corner_radius,
                angle = rotation_angle
            );
            
            rotated_rectangular_pillar(
                length = rectangle_length,
                width = rectangle_width,
                height = actual_rect_height,
                corner_radius = corner_radius,
                angle = rotation_angle
            );
        }
    }
}