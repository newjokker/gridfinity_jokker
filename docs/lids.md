# Gridfinity 防尘盖

已经把 [ostat/gridfinity_extended_openscad](https://github.com/ostat/gridfinity_extended_openscad) 的原项目直接放入：

`third_party/gridfinity_extended_openscad/`

引用版本为提交 `335afadd151e6899ec1f28fd454b01bc3b177fc2`，上游许可证是 GPL-3.0，许可证原文随项目保留。

## 在线生成

远程服务已经增加独立页面：

`http://8.153.160.138:55504/lids`

页面支持选择 1–10 格的 X/Y 尺寸、标准/平整/半格/省料四种盖板样式、磁铁孔开关，并提供真实 STL 三维预览和下载。纯防尘用途默认关闭磁铁孔。

后端接口为 `GET/POST /api/lid-stl`，参数包括 `gridx`、`gridy`、`lid_style` 和 `magnets`。

## 普通盖/磁吸盖

打开：

`third_party/gridfinity_extended_openscad/gridfinity_lid.scad`

主要参数：

- `width = [2, 0]`：X 方向 2 格。
- `depth = [1, 0]`：Y 方向 1 格。
- `Lid_Options = "default"`：标准可堆叠盖。
- `Enable_Magnets`：是否在上部 Gridfinity 结构中生成磁铁位。
- `Lid_Include_Magnets`：是否保留盖子配合部分的磁铁结构。

只想挡灰时，尺寸改成与盒子相同，并关闭两组磁铁孔，避免孔洞成为落灰通道。比如 1 x 2 盒子：

```scad
width = [1, 0];
depth = [2, 0];
Enable_Magnets = false;
Lid_Include_Magnets = false;
```

盖子依靠盒子顶部的标准 Gridfinity 堆叠唇边定位，所以目标盒子的 `include_lip` 应设为 `true`。

## 滑盖

需要带滑轨的盒子和盖子时打开：

`third_party/gridfinity_extended_openscad/gridfinity_sliding_lid.scad`

它不是给现有普通盒子单独加一块滑盖，而是同时生成带滑轨结构的 cup。因此，已有普通盒子防尘优先使用 `gridfinity_lid.scad`。

## 当前仓库盒子的尺寸

| 盒子文件 | 盖子尺寸 | 当前 `include_lip` |
| --- | --- | --- |
| `007_磁铁收纳盒.scad`、`009_电动机盒子_2.scad` | 1 x 1 | `false`，使用盖子前改为 `true` |
| `003_盒子上面很多均匀的孔.scad`、`004_轴承.scad` | 1 x 2 | `true` |
| `006_电池盒子.scad`、`008_9v矩形电池.scad` | 1 x 2 | `false`，使用盖子前改为 `true` |
| `005_盒子上大小不一的矩形.scad` | 1 x 3 | `true` |
| `009_电动机盒子_3.scad` | 2 x 1 | `false`，使用盖子前改为 `true` |
| `009_电动机盒子_1.scad` | 2 x 2 | `false`，使用盖子前改为 `true` |
| `123.scad` | 2 x 2 | `true` |

## OpenSCAD 版本

本机图形版 `/Applications/OpenSCAD.app` 是 2026.01.02，可以运行该项目。终端 PATH 中还有一个旧的 2021.01，因此命令行渲染时应明确使用：

```bash
/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD \
  third_party/gridfinity_extended_openscad/gridfinity_lid.scad
```
