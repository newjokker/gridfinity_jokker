// 示例3：多种字体展示
fonts = [
    ["华文宋体", "STSong:style=Regular", -120],
    ["黑体-简", "Heiti SC:style=Regular", -200]
];

for (f = fonts) {
    translate([0, f[2], 0]) {
        linear_extrude(height = 4) {
            text(f[0], size = 15, font = f[1]);
        }
    }
}