/*
Gridfinity 底板双头弹性插销

用途：
1. 对准两块底板侧面的连接孔。
2. 先将插销的一端压入第一块底板，再将第二块底板压上。
3. 默认会一次打印松、标准、紧三种公差，从下向上依次排列。
4. 先在两块小底板上试装，选出合适公差后再批量打印。

打印建议：
- PETG 优先，PLA 适合试装或一次性装配。
- 文件已将插销侧躺并削出小平底，无需支撑。
- 0.2 mm 层高，3~4 道墙，100% 填充。
- 如果太紧，选择 loose；如果易松脱，选择 tight。
*/

/* [输出设置] */
// test_set 同时生成松/标准/紧三根；其他选项只生成一根。
fit_mode = "test_set"; // [test_set,loose,standard,tight]

/* [底板孔尺寸] */
// 项目当前底板侧孔的标称直径。
hole_diameter = 3.35; // [3.00:0.05:4.00]
// 两块底板合拢后的插销总长度，留有少量孔底余量。
pin_length = 19.6; // [16.0:0.1:21.0]

/* [弹性和安装] */
// 插销中间杆径，小于孔径以便装配。
shaft_diameter = 3.10; // [2.60:0.05:3.50]
// 两端导向尖的直径。
tip_diameter = 2.40; // [1.80:0.05:3.00]
// 两端导向锥长度。
tip_length = 2.0; // [1.0:0.1:3.5]
// 最大卡紧段长度。
grip_length = 0.8; // [0.4:0.1:1.5]
// 卡紧段回到中间杆径的过渡长度。
shoulder_length = 0.8; // [0.4:0.1:1.5]
// 从每个端部向中间延伸的弹性槽长度。
slot_depth = 7.0; // [4.0:0.5:8.5]
// 弹性槽宽度。
slot_width = 0.65; // [0.40:0.05:1.00]
// 侧躺打印时削掉的底部高度，用于提高首层附着。
flat_cut = 0.25; // [0.10:0.05:0.50]

/* [试件排列] */
test_spacing = 7.0; // [5.0:0.5:12.0]

/* [渲染质量] */
$fn = 64;

// 三档最大卡紧直径：相对标称孔径的偏移量。
function grip_diameter(mode) =
    mode == "loose" ? hole_diameter - 0.05 :
    mode == "tight" ? hole_diameter + 0.15 :
    hole_diameter + 0.05;

// 围绕 Z 轴生成双头卡紧轮廓，再旋转成侧躺打印方向。
module pin_solid(grip_d) {
    half_length = pin_length / 2;
    tip_r = tip_diameter / 2;
    grip_r = grip_d / 2;
    shaft_r = shaft_diameter / 2;
    transition_end = half_length - tip_length - grip_length - shoulder_length;

    assert(transition_end > 0,
        "插销太短：请减小导向锥/卡紧段/过渡段长度");
    assert(slot_depth < half_length - 0.5,
        "弹性槽过深：中间必须保留至少 1 mm 连接段");
    assert(shaft_diameter < grip_d,
        "中间杆径必须小于卡紧直径");

    rotate_extrude(convexity = 10)
        polygon(points = [
            [0, -half_length],
            [tip_r, -half_length],
            [grip_r, -half_length + tip_length],
            [grip_r, -half_length + tip_length + grip_length],
            [shaft_r, -transition_end],
            [shaft_r, transition_end],
            [grip_r, half_length - tip_length - grip_length],
            [grip_r, half_length - tip_length],
            [tip_r, half_length],
            [0, half_length]
        ]);
}

// 从两端切出纵向槽，形成可压缩的双臂。
module slotted_pin(grip_d) {
    half_length = pin_length / 2;

    difference() {
        pin_solid(grip_d);

        translate([-slot_width / 2, -grip_d, -half_length - 0.1])
            cube([slot_width, 2 * grip_d, slot_depth + 0.1]);

        translate([-slot_width / 2, -grip_d, half_length - slot_depth])
            cube([slot_width, 2 * grip_d, slot_depth + 0.1]);
    }
}

// 将插销水平放置，并在下方生成一条窄平面。
module printable_pin(mode = "standard") {
    grip_d = grip_diameter(mode);
    axis_height = grip_d / 2 - flat_cut;

    intersection() {
        translate([0, 0, axis_height])
            rotate([0, 90, 0])
                slotted_pin(grip_d);

        translate([-pin_length, -grip_d, 0])
            cube([2 * pin_length, 2 * grip_d, 2 * grip_d]);
    }
}

if (fit_mode == "test_set") {
    // 从下向上（-Y 到 +Y）：loose、standard、tight。
    translate([0, -test_spacing, 0]) printable_pin("loose");
    printable_pin("standard");
    translate([0, test_spacing, 0]) printable_pin("tight");
} else {
    printable_pin(fit_mode);
}
