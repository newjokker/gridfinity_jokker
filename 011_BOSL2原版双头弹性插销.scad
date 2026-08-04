/*
BOSL2 small 双头弹性插销——保留试打组第 2 号

本文件的变化规则：
- 两端使用同一组可调参数，初始尺寸参考 BOSL2 `snap_pin("small")`。
- 只把两个原版半销向外分开，在正中央增加与原版断面一致的直连接段。
- 只保留试打组第 2 号的中央长度 3.64 mm；调整头部参数后总长会随之变化。

中央长度基准：
- BOSL2 small: nub_depth = 1.2 mm, preload = 0.16 mm。
- 原版两侧卡点中央距离约为 2 * (1.2 - 0.16) = 2.08 mm。
- 第 2 号为原版中央长度的 1.75 倍：2.08 * 1.75 = 3.64 mm。

打印建议：
- 模型已平放，不需要支撑。
- 建议在切片软件中加 4–6 mm 外侧 Brim。

上游代码：
https://github.com/BelfrySCAD/BOSL2/blob/master/joiners.scad
*/

include <BOSL2/std.scad>
include <BOSL2/joiners.scad>

/* [左右两个头（同时调整）] */
// 头部和销身的标称直径。
head_diameter = 3.20;       // [2.50:0.05:4.00]
// 每一侧从中央到尖端的 BOSL2 长度参数。
head_length = 6.00;         // [4.00:0.10:8.00]
// 卡点向外凸出量；越大越紧，也越难插入。
snap_projection = 0.50;    // [0.10:0.05:0.60]
// 卡点距离中央连接处的位置。
nub_depth = 1.20;          // [0.80:0.05:1.80]
// 弹性臂壁厚；越大越硬。
arm_thickness = 1.00;      // [0.70:0.05:1.30]
// 销体相对于配套孔的收缩间隙；越大越松。
fit_clearance = 0.20;      // [0.05:0.05:0.35]
// 卡点预紧量；越大卡紧力越高。
head_preload = 0.16;       // [0.00:0.02:0.30]
// true 为尖头，false 为圆头。
pointed_head = false;

/* [中央连接颈] */
target_center_length = 4.34; // 中央卡点间距（mm）

// 根据当前头部参数计算原始中央卡点间距。
original_center_length = 2 * (nub_depth - head_preload); // 默认 2.08 mm

/* [渲染质量] */
$fn = 48;

// 使用 BOSL2 small 结构，但把所有需要调整的头部参数显式传入。
module original_pin_up() {
    snap_pin(
        "small",
        d = head_diameter,
        l = head_length,
        snap = snap_projection,
        nub_depth = nub_depth,
        thickness = arm_thickness,
        clearance = fit_clearance,
        preload = head_preload,
        pointed = pointed_head,
        anchor = CENTER,
        orient = UP
    );
}

// 取原版插销在正中央的真实断面，拉伸成新的中央连接颈。
module center_bridge(extra_length, overlap = 0.03) {
    if (extra_length > 0)
        // 向两端各重叠 overlap，避免共面接触被 STL 视为分离体。
        linear_extrude(height = extra_length + 2 * overlap, center = true)
            projection(cut = true)
                original_pin_up();
}

// 只增加中央连接颈；两端依然是原版 BOSL2 small 几何。
module selected_pin() {
    extra_length = target_center_length - original_center_length;
    assert(
        extra_length >= 0,
        "target_center_length 不能小于 2 * (nub_depth - head_preload)"
    );
    // 20 mm 足以包住 BOSL2 small 的单侧几何，同时避免预览相机被过大裁切体拉远。
    cut_size = 20;

    // 在 UP 方向拆分上下两半、向外平移，再补上中央直段。
    // 最后绕 X 轴旋转 90°，使 BOSL2 的原生平面贴在打印平台上。
    rotate([90, 0, 0])
        union() {
            translate([0, 0, extra_length / 2])
                intersection() {
                    original_pin_up();
                    translate([-cut_size / 2, -cut_size / 2, 0])
                        cube([cut_size, cut_size, cut_size]);
                }

            translate([0, 0, -extra_length / 2])
                intersection() {
                    original_pin_up();
                    translate([-cut_size / 2, -cut_size / 2, -cut_size])
                        cube([cut_size, cut_size, cut_size]);
                }

            center_bridge(extra_length);
        }
}

selected_pin();
