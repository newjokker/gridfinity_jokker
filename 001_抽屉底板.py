
import os
import subprocess
import json


def create_scad_from_template(params):
    """使用模板生成 SCAD 文件"""
    
    template = '''
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
// minimum length of baseplate along x (leave zero to ignore, will automatically fill area if gridx is zero)
distancex = {distancex};
// minimum length of baseplate along y (leave zero to ignore, will automatically fill area if gridy is zero)
distancey = {distancey};

// where to align extra space along x
fitx = {fitx}; // [-1:0.1:1]
// where to align extra space along y
fity = {fity}; // [-1:0.1:1]


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

gridfinityBaseplate([0, 0], l_grid, [distancex, distancey], style_plate, hole_options, style_hole, [fitx, fity]);

'''
    
    # 转换布尔值为 OpenSCAD 格式
    for key in params:
        if isinstance(params[key], bool):
            params[key] = "true" if params[key] else "false"
    
    return template.format(**params)

def save_to_stl(save_path, scad_code, stl_path):
    # 生成文件
    with open(save_path, "w") as f:
        f.write(scad_code)

    # 渲染为 STL
    subprocess.run([
        '/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD', '-o', stl_path,
        save_path
    ])

# 定义参数
my_params = {
    'fa': 8,
    'fs': 0.25,
    'gridx': 0,
    'gridy': 0,
    'd_screw': 3.35,
    'd_screw_head': 5.0,
    'screw_spacing': 0.5,
    'n_screws': 1,
    'distancex': 50,
    'distancey': 100,
    'fitx': 0,
    'fity': 0,
    'style_plate': 3,
    'style_hole': 0,
    'enable_magnet': True,
    'crush_ribs': False,
    'chamfer_holes': True
}


# --------------------------- 超参 -------------------------------------
scad_path = "./__temp_code.scad"
stl_path = "./stls/111.stl"
# ---------------------------------------------------------------------

my_params["distancex"] = 300    # 矩形的的宽度
my_params["distancey"] = 100    # 矩形的高度
my_params["fitx"] = 1           # -1 全在左边
my_params["fity"] = 1           # -1 全在下边

scad_code = create_scad_from_template(my_params)

save_to_stl(scad_path, scad_code, stl_path)

os.remove(scad_path)


