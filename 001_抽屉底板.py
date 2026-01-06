
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

def stitch_pieces_png(
    pieces,
    png_dir,
    out_path,
    canvas_W, canvas_H,
    scale=5,
    draw_border=True,
    draw_id=True,
    bg=(255, 255, 255, 0),
    flip_y=False,
):
    """
    把每个 pid.png 按 pieces 的 (x,y,w,h) 拼回一张大图。

    参数:
      - pieces: 你 split_rect 返回的列表，元素有 pid,x,y,w,h
      - png_dir: 保存 pid.png 的目录
      - out_path: 输出大图路径（.png）
      - canvas_W, canvas_H: 大图对应的尺寸（跟 split.jpg 的坐标系一致），单位=mm 或者你 split 用的单位
      - scale: 1 个单位对应多少像素（你现在每块用 w*5,h*5，所以默认 5）
      - flip_y: 如果你发现 y 方向上下颠倒，就设为 True

    约定:
      - 坐标原点默认认为在左下（很多几何/建模习惯这样）
      - PIL 贴图原点在左上，所以需要换算 y
    """
    # 1) 建画布
    canvas_px = (int(round(canvas_W * scale)), int(round(canvas_H * scale)))
    big = Image.new("RGBA", canvas_px, bg)
    draw = ImageDraw.Draw(big)

    # 字体（可选）
    font = None
    if draw_id:
        try:
            font = ImageFont.truetype("Arial.ttf", size=max(55, int(10 * scale / 5)))
        except Exception:
            print("使用默认字体")
            font = ImageFont.load_default()

    # 2) 逐块贴回去
    for p in pieces:
        pid = p.pid
        x, y, w, h = float(p.x), float(p.y), float(p.w), float(p.h)

        png_path = os.path.join(png_dir, f"{pid}.png")
        if not os.path.exists(png_path):
            raise FileNotFoundError(f"找不到 {png_path}")

        tile = Image.open(png_path).convert("RGBA")

        # 目标尺寸（像素）
        tw = max(1, int(round(w * scale)))
        th = max(1, int(round(h * scale)))

        # 如果每块 png 尺寸不是恰好 w*scale/h*scale，就强制 resize（更鲁棒）
        if tile.size != (tw, th):
            tile = tile.resize((tw, th), Image.Resampling.LANCZOS)

        # 坐标换算：几何坐标(左下) -> 图像坐标(左上)
        px = int(round(x * scale))
        if flip_y:
            # 如果 pieces.y 本身就是“从上往下”的坐标，就用这个
            py = int(round(y * scale))
        else:
            # 默认 y 是从下往上：贴图需要用 (H - (y+h))
            py = int(round((canvas_H - (y + h)) * scale))

        big.alpha_composite(tile, (px, py))

        # 3) 画边框 / 编号（可选）
        if draw_border:
            draw.rectangle([px, py, px + tw, py + th], outline=(0, 0, 0, 255), width=max(1, scale // 5))

        if draw_id:
            text = str(pid)
            # 放左上角一点 padding
            draw.text((px + 3, py + 3), text, fill=(255, 0, 0, 255), font=font)

    # 4) 保存
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    big.save(out_path)
    return out_path


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

# 创建保存文件夹
save_dir = f"./stls/drawer_{drawer_x}_{drawer_y}_{K}_{int(a/K)}-{int(b/K)}_{min_margin_cells}"
os.makedirs(save_dir, exist_ok=True)

pieces = split_rect(M=drawer_x, N=drawer_y, a=a, b=a, K=K, min_margin_cells=min_margin_cells, img_path=os.path.join(save_dir, "split.jpg"))

for each in pieces:
    
    my_params["distancex"] = each.w    # 矩形的的宽度
    my_params["distancey"] = each.h    # 矩形的高度
    
    if each.kind in ["corner_lt"]:
        my_params["fitx"] = -1           # -1 全在左边
        my_params["fity"] = 1           # -1 全在下边
    elif each.kind in ["corner_rt"]:
        my_params["fitx"] = 1           # -1 全在左边
        my_params["fity"] = 1           # -1 全在下边
    elif each.kind in ["corner_lb"]:
        my_params["fitx"] = -1           # -1 全在左边
        my_params["fity"] = -1           # -1 全在下边
    elif each.kind in ["corner_rb"]:
        my_params["fitx"] = 1           # -1 全在左边
        my_params["fity"] = -1           # -1 全在下边
    elif each.kind in ["edge_top"]:
        my_params["fitx"] = 0           # -1 全在左边
        my_params["fity"] = 1           # -1 全在下边
    elif each.kind in ["edge_bottom"]:
        my_params["fitx"] = 0           # -1 全在左边
        my_params["fity"] = -1           # -1 全在下边
    elif each.kind in ["edge_left"]:
        my_params["fitx"] = -1           # -1 全在左边
        my_params["fity"] = 0           # -1 全在下边
    elif each.kind in ["edge_right"]:
        my_params["fitx"] = 1           # -1 全在左边
        my_params["fity"] = 0           # -1 全在下边
    elif each.kind in ["center"]:
        my_params["fitx"] = 0           # -1 全在左边
        my_params["fity"] = 0           # -1 全在下边
    else:
        raise ValueError(f"斑块类型:{each.kind} 未定义")
        
    scad_code = create_scad_from_template(my_params)

    each_stl_path = os.path.join(save_dir, f"{each.pid}.stl")
    save_to_stl(scad_path, scad_code, each_stl_path)
    
    each_png_path = os.path.join(save_dir, f"{each.pid}.png")
    save_to_png(scad_path, scad_code, each_png_path, w=int(each.w) * 5, h=int(each.h) * 5)

    os.remove(scad_path)

# 生成打印核对图像
out = stitch_pieces_png(
    pieces=pieces,
    png_dir=save_dir,
    out_path=os.path.join(save_dir, "stitched.png"),
    canvas_W=drawer_x,
    canvas_H=drawer_y,
    scale=5,
    draw_border=True,
    draw_id=True,
    flip_y=False,  
)
