
import os
import subprocess
import json
from scripts.baseplate_tools import split_rect
from PIL import Image, ImageDraw, ImageFont

"""

gridfinity 风格的盒子需要放在底板上，底板是一个个的边长为 42 的正方形，为了适配各种形状，底板还可以在上下左右延伸出不同长度的边缘，我现在有一个 长宽为 M N 的抽屉

我想将抽屉底部都铺满底板，现在要 （1）出现的边缘部分要左右 上下 对称 （2）有尽可能多的 42 边长的盒子 

我的底板是使用 3D 打印制作的，因为 3D 打印有大小的限制，一次性只能打印出 a b 长宽的长方形，

给我一个好的风格方案，给我完整的 python 代码，代码要能生成风格示意图


给我完整的代码
"""

def create_scad_from_template(params):
    """使用模板生成 SCAD 文件"""
    
    template = '''
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
$fa = {fa};
$fs = {fs}; // .01

/* [General Settings] */
// number of bases along x-axis
gridx = {gridx};
// number of bases along y-axis
gridy = {gridy};
// bin height. See bin height information and "gridz_define" below.
gridz = 5; //.1

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

/* [Cylindrical Compartments] */
// Use this instead of bins
cut_cylinders = false;
// diameter of cylindrical cut outs
cd = 10; // .1
// chamfer around the top rim of the holes
c_chamfer = 0.5; // .1

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

bin1 = new_bin(
    grid_size = [gridx, gridy],
    height_mm = height(gridz, gridz_define, enable_zsnap),
    fill_height = height_internal,
    include_lip = include_lip,
    hole_options = hole_options,
    only_corners = only_corners || half_grid,
    thumbscrew = enable_thumbscrew,
    grid_dimensions = GRID_DIMENSIONS_MM / (half_grid ? 2 : 1)
);

bin_render(bin1) {{
    bin_subdivide(bin1, [divx, divy]) {{
        depth_real = cgs(height=depth).z;
        if (cut_cylinders) {{
            cut_chamfered_cylinder(cd/2, depth_real, c_chamfer);
        }} else {{
            cut_compartment_auto(
                cgs(height=depth),
                style_tab,
                place_tab != 0,
                scoop
            );
        }}
    }}
}}

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
    
def save_to_png(save_path, scad_code, img_path, w, h):
    # 生成文件
    with open(save_path, "w") as f:
        f.write(scad_code)

    # 渲染为 STL
    subprocess.run([
        '/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD', 
        "--projection", "ortho",
        "--imgsize", f"{w},{h}",
        "--camera", "0,0,0,0,0,0,100",
        "--autocenter",
        "--viewall",
        '-o', img_path,
        save_path
    ])


# 定义参数
my_params = {
    'fa': 8,
    'fs': 0.25,
    'gridx': 1,
    'gridy': 1
}

# FIXME: 现在的合并方案是有问题的，可能会出现很多个只包含一个格子的斑块，但是旁白就是包含五六个格子的斑块，这很显然是不合理的，所以需要重新优化合并的逻辑

# --------------------------- 超参 -------------------------------------
scad_path = "./__temp_code.scad"
drawer_x = 408              # 抽屉的宽
drawer_y = 413              # 抽屉的高
K = 42                      # 每一个小方块的边长
a = K * 5                   # 打印机可以打印的最大长度
b = K * 5                   # 打印机可以打印的最大宽度
min_margin_cells = 2        # 边缘宽度至少包含多少个小正方形的边长
scale = 5                   # 示意图缩放尺寸
# ---------------------------------------------------------------------

# # 创建保存文件夹
# save_dir = f"./stls/drawer_{drawer_x}_{drawer_y}_K{K}_{int(a/K)}-{int(b/K)}_Min{min_margin_cells}"
# os.makedirs(save_dir, exist_ok=True)

scad_code = create_scad_from_template(my_params)
save_to_stl(save_path="123.scad", scad_code=scad_code, stl_path="123.stl")

