from __future__ import annotations

import io
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import threading
import zipfile
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

from planner import fit_for_kind, make_plan


ROOT = Path(__file__).resolve().parents[1]
OPENSCAD = os.environ.get("OPENSCAD_BIN") or shutil.which("openscad") or "/usr/bin/openscad"
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024
CACHE_DIR = Path("/tmp/gridfinity-stl-cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
RENDER_LOCK = threading.Lock()


def request_values():
    if request.method == "GET":
        return request.args.to_dict()
    json_body = request.get_json(silent=True)
    return json_body if isinstance(json_body, dict) else request.form.to_dict()


def parse_payload():
    body = request_values()
    try:
        if "printer_x_cells" in body:
            printer_x_cells_raw = float(body["printer_x_cells"])
        else:
            printer_x_cells_raw = float(body.get("printer_x", 126)) / 42.0
        if "printer_y_cells" in body:
            printer_y_cells_raw = float(body["printer_y_cells"])
        else:
            printer_y_cells_raw = float(body.get("printer_y", 126)) / 42.0
        values = {
            "width": float(body.get("width", 413)),
            "depth": float(body.get("depth", 308)),
            "printer_x": printer_x_cells_raw * 42.0,
            "printer_y": printer_y_cells_raw * 42.0,
            "grid": 42.0,
            "min_margin_cells": int(body.get("min_margin_cells", 1)),
            "style": int(body.get("style", 4)),
            "magnets": body.get("magnets", True) if isinstance(body.get("magnets", True), bool)
            else str(body.get("magnets", True)).lower() in ("1", "true", "yes", "on"),
        }
    except (TypeError, ValueError):
        raise ValueError("请输入有效的数字")
    if not 0 <= values["style"] <= 4:
        raise ValueError("底板样式无效")
    if any(values[name] > 3000 for name in ("width", "depth", "printer_x", "printer_y")):
        raise ValueError("尺寸不能超过 3000 mm")
    for raw_cells, label, value_name in (
        (printer_x_cells_raw, "X", "printer_x"),
        (printer_y_cells_raw, "Y", "printer_y"),
    ):
        if abs(raw_cells - round(raw_cells)) > 1e-8:
            raise ValueError(f"打印机 {label} 最大格数必须是整数")
        cells = int(round(raw_cells))
        if cells < 1 or cells > 71:
            raise ValueError(f"打印机 {label} 最大格数必须是 1 到 71 之间的整数")
        values[value_name] = cells * 42.0
    return values


def scad_code(piece: dict, grid: float, style: int, magnets: bool) -> str:
    fit_x, fit_y = fit_for_kind(piece["kind"])
    magnet = "true" if magnets else "false"
    root = ROOT.as_posix()
    return f'''include <{root}/src/core/standard.scad>
include <{root}/src/core/gridfinity-baseplate.scad>
use <{root}/src/core/gridfinity-rebuilt-utility.scad>
use <{root}/src/core/gridfinity-rebuilt-holes.scad>
use <{root}/src/helpers/generic-helpers.scad>
use <{root}/src/helpers/grid.scad>
use <{root}/gridfinity-rebuilt-baseplate.scad>
$fa = 16;
$fs = 0.5;
distancex = {piece['w']:.4f};
distancey = {piece['h']:.4f};
style_plate = {style};
enable_magnet = {magnet};
hole_options = bundle_hole_options(refined_hole=false, magnet_hole=enable_magnet,
    screw_hole=false, crush_ribs=false, chamfer_holes=true, supportless=false);
gridfinityBaseplate([0, 0], {grid:.4f}, [distancex, distancey], style_plate,
    hole_options, 0, [{fit_x}, {fit_y}]);
'''


def parse_bin_payload():
    body = request_values()

    def integer(name, default, minimum, maximum, label):
        try:
            raw = float(body.get(name, default))
        except (TypeError, ValueError):
            raise ValueError(f"{label}请输入整数")
        if abs(raw - round(raw)) > 1e-8:
            raise ValueError(f"{label}请输入整数")
        value = int(round(raw))
        if value < minimum or value > maximum:
            raise ValueError(f"{label}需要在 {minimum} 到 {maximum} 之间")
        return value

    def number(name, default, minimum, maximum, label):
        try:
            value = float(body.get(name, default))
        except (TypeError, ValueError):
            raise ValueError(f"{label}请输入有效数字")
        if value < minimum or value > maximum:
            raise ValueError(f"{label}需要在 {minimum} 到 {maximum} 之间")
        return value

    def boolean(name, default=False):
        raw = body.get(name, default)
        return raw if isinstance(raw, bool) else str(raw).lower() in ("1", "true", "yes", "on")

    params = {
        "gridx": integer("gridx", 2, 1, 10, "X 网格数"),
        "gridy": integer("gridy", 1, 1, 10, "Y 网格数"),
        "gridz": integer("gridz", 4, 1, 20, "高度单位"),
        "divx": integer("divx", 2, 1, 12, "X 分仓数"),
        "divy": integer("divy", 1, 1, 12, "Y 分仓数"),
        "style_tab": integer("style_tab", 5, 0, 5, "标签挡板样式"),
        "hole_style": integer("hole_style", 0, 0, 2, "底孔样式"),
        "scoop": number("scoop", 0.5, 0, 1, "底部圆弧"),
        "cylinder_diameter": number("cylinder_diameter", 12, 2, 40, "圆柱孔直径"),
        "include_lip": boolean("include_lip", True),
        "only_corners": boolean("only_corners", False),
        "cut_cylinders": boolean("cut_cylinders", False),
        "cut_mode": str(body.get("cut_mode", "compartments")),
        "rectangle_length": number("rectangle_length", 20, 3, 200, "矩形长度"),
        "rectangle_width": number("rectangle_width", 15, 3, 200, "矩形宽度"),
        "rectangle_radius": number("rectangle_radius", 0.5, 0, 20, "矩形圆角半径"),
    }
    # Backward compatibility for links created before the shape selector existed.
    if params["cut_cylinders"]:
        params["cut_mode"] = "circles"
    if params["cut_mode"] not in ("compartments", "circles", "rectangles"):
        raise ValueError("开孔模式无效")
    if params["divx"] * params["divy"] > 64:
        raise ValueError("分仓总数不能超过 64")
    cell_x = (params["gridx"] * 42 - 2.5) / params["divx"] - 1.2
    cell_y = (params["gridy"] * 42 - 2.5) / params["divy"] - 1.2
    if params["cut_mode"] == "circles" and params["cylinder_diameter"] > min(cell_x, cell_y):
        raise ValueError(f"圆孔放不下：当前单格最多约 {min(cell_x, cell_y):.1f} mm")
    if params["cut_mode"] == "rectangles":
        if params["rectangle_length"] > cell_x or params["rectangle_width"] > cell_y:
            raise ValueError(f"矩形放不下：当前单格约可用 {cell_x:.1f} × {cell_y:.1f} mm")
        if params["rectangle_radius"] >= min(params["rectangle_length"], params["rectangle_width"]) / 2:
            maximum = min(params["rectangle_length"], params["rectangle_width"]) / 2
            raise ValueError(f"矩形圆角半径必须小于 {maximum:.1f} mm；设为 0 可生成直角矩形")
    return params


def bin_scad_code(params: dict) -> str:
    root = ROOT.as_posix()
    boolean = lambda value: "true" if value else "false"
    magnet_holes = params["hole_style"] in (1, 2)
    screw_holes = params["hole_style"] == 2
    return f'''include <{root}/src/core/standard.scad>
use <{root}/src/core/gridfinity-rebuilt-utility.scad>
use <{root}/src/core/gridfinity-rebuilt-holes.scad>
use <{root}/src/core/bin.scad>
use <{root}/src/core/cutouts.scad>
use <{root}/src/helpers/generic-helpers.scad>
use <{root}/src/helpers/grid.scad>
use <{root}/src/helpers/grid_element.scad>
use <{root}/src/helpers/shapes.scad>
$fa = 8;
$fs = 0.5;
gridx = {params['gridx']};
gridy = {params['gridy']};
gridz = {params['gridz']};
include_lip = {boolean(params['include_lip'])};
divx = {params['divx']};
divy = {params['divy']};
scoop = {params['scoop']:.3f};
cut_cylinders = {boolean(params['cut_cylinders'])};
cut_mode = "{params['cut_mode']}";
cd = {params['cylinder_diameter']:.3f};
rectangle_length = {params['rectangle_length']:.3f};
rectangle_width = {params['rectangle_width']:.3f};
rectangle_radius = {params['rectangle_radius']:.3f};
only_corners = {boolean(params['only_corners'])};
magnet_holes = {boolean(magnet_holes)};
screw_holes = {boolean(screw_holes)};
hole_options = bundle_hole_options(false, magnet_holes, screw_holes, true, true, true);
bin1 = new_bin(
    grid_size = [gridx, gridy],
    height_mm = height(gridz, 0, false),
    fill_height = 0,
    include_lip = include_lip,
    hole_options = hole_options,
    only_corners = only_corners,
    thumbscrew = false,
    grid_dimensions = GRID_DIMENSIONS_MM
);
module rectangle_cutter(size_mm, corner_radius) {{
    difference() {{
        rounded_cube([size_mm.x, size_mm.y, size_mm.z*2], corner_radius, center=true);
        translate([0, 0, size_mm.z/2])
            cube(size_mm + [TOLLERANCE, TOLLERANCE, TOLLERANCE], center=true);
    }}
}}
bin_render(bin1) {{
    bin_subdivide(bin1, [divx, divy]) {{
        if (cut_mode == "circles")
            cut_chamfered_cylinder(cd/2, cgs().z, 0.5);
        else if (cut_mode == "rectangles")
            rectangle_cutter([rectangle_length, rectangle_width, cgs().z], rectangle_radius);
        else
            // Use a clean compartment cutter without the legacy floating label tab.
            // The tab creates a thin overhang that looks like a patch in STL viewers.
            compartment_cutter(cgs(), scoop);
    }}
}}
'''


def render_stl(scad_path: Path, stl_path: Path) -> None:
    environment = os.environ.copy()
    environment.setdefault("QT_QPA_PLATFORM", "offscreen")
    run = subprocess.run(
        [OPENSCAD, "--backend=Manifold", "-o", str(stl_path), str(scad_path)],
        cwd=ROOT, env=environment, capture_output=True, text=True, timeout=300,
    )
    if run.returncode or not stl_path.exists():
        app.logger.error("OpenSCAD failed: %s", run.stderr[-2000:])
        raise RuntimeError("STL 生成失败，请稍后重试")


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/baseplates")
def baseplates():
    return render_template("baseplates.html")


@app.get("/bins")
def bins():
    return render_template("bins.html")


@app.post("/api/plan")
def plan():
    try:
        values = parse_payload()
        result = make_plan(**{key: values[key] for key in (
            "width", "depth", "printer_x", "printer_y", "grid", "min_margin_cells"
        )})
        return jsonify(result)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/api/download")
def download():
    try:
        values = parse_payload()
        plan_data = make_plan(**{key: values[key] for key in (
            "width", "depth", "printer_x", "printer_y", "grid", "min_margin_cells"
        )})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if not Path(OPENSCAD).exists():
        return jsonify({"error": "服务器尚未安装 OpenSCAD"}), 503

    archive = io.BytesIO()
    try:
        with RENDER_LOCK, tempfile.TemporaryDirectory(prefix="gridfinity-") as temp_name:
            temp = Path(temp_name)
            for piece in plan_data["pieces"]:
                stem = f"{piece['pid']:02d}_{piece['w']:g}x{piece['h']:g}mm"
                scad_path = temp / f"{stem}.scad"
                stl_path = temp / f"{stem}.stl"
                scad_path.write_text(scad_code(piece, values["grid"], values["style"], values["magnets"]), encoding="utf-8")
                render_stl(scad_path, stl_path)

            with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
                bundle.writestr("assembly_plan.json", json.dumps(plan_data, ensure_ascii=False, indent=2))
                bundle.writestr("使用说明.txt", "文件编号对应网页预览中的编号。单位：毫米。打印前请在切片软件中复核尺寸。\n")
                for stl_path in sorted(temp.glob("*.stl")):
                    bundle.write(stl_path, stl_path.name)
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        return jsonify({"error": str(exc)}), 500
    archive.seek(0)
    filename = f"gridfinity_{values['width']:g}x{values['depth']:g}mm.zip"
    return send_file(archive, mimetype="application/zip", as_attachment=True, download_name=filename)


@app.route("/api/piece-stl", methods=["GET", "POST"])
def piece_stl():
    try:
        values = parse_payload()
        body = request_values()
        piece_id = int(body.get("piece_id", 0))
        as_download = str(body.get("download", "0")).lower() in ("1", "true", "yes", "on")
        plan_data = make_plan(**{key: values[key] for key in (
            "width", "depth", "printer_x", "printer_y", "grid", "min_margin_cells"
        )})
        if piece_id < 1 or piece_id > len(plan_data["pieces"]):
            raise ValueError("请选择有效的底板编号")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if not Path(OPENSCAD).exists():
        return jsonify({"error": "服务器尚未安装 OpenSCAD"}), 503

    piece = plan_data["pieces"][piece_id - 1]
    code = scad_code(piece, values["grid"], values["style"], values["magnets"])
    cache_key = hashlib.sha256(code.encode("utf-8")).hexdigest()
    scad_path = CACHE_DIR / f"{cache_key}.scad"
    stl_path = CACHE_DIR / f"{cache_key}.stl"
    try:
        with RENDER_LOCK:
            if not stl_path.exists():
                scad_path.write_text(code, encoding="utf-8")
                render_stl(scad_path, stl_path)
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        return jsonify({"error": str(exc)}), 500

    response = send_file(
        stl_path, mimetype="model/stl", as_attachment=as_download,
        download_name=f"{piece_id:02d}_{piece['w']:g}x{piece['h']:g}mm.stl",
    )
    response.headers["Cache-Control"] = "private, max-age=3600"
    response.headers["X-Piece-Width"] = str(piece["w"])
    response.headers["X-Piece-Height"] = str(piece["h"])
    return response


@app.route("/api/bin-stl", methods=["GET", "POST"])
def bin_stl():
    try:
        params = parse_bin_payload()
        body = request_values()
        as_download = str(body.get("download", "0")).lower() in ("1", "true", "yes", "on")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if not Path(OPENSCAD).exists():
        return jsonify({"error": "服务器尚未安装 OpenSCAD"}), 503

    code = bin_scad_code(params)
    cache_key = hashlib.sha256(code.encode("utf-8")).hexdigest()
    scad_path = CACHE_DIR / f"bin-{cache_key}.scad"
    stl_path = CACHE_DIR / f"bin-{cache_key}.stl"
    try:
        with RENDER_LOCK:
            if not stl_path.exists():
                scad_path.write_text(code, encoding="utf-8")
                render_stl(scad_path, stl_path)
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        return jsonify({"error": str(exc)}), 500

    suffix = {"compartments": "divided", "circles": "circle_array", "rectangles": "rect_array"}[params["cut_mode"]]
    filename = f"gridfinity_{suffix}_{params['gridx']}x{params['gridy']}x{params['gridz']}U.stl"
    response = send_file(stl_path, mimetype="model/stl", as_attachment=as_download, download_name=filename)
    response.headers["Cache-Control"] = "private, max-age=3600"
    response.headers["X-Bin-Grid"] = f"{params['gridx']}x{params['gridy']}x{params['gridz']}"
    return response


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=55504)
