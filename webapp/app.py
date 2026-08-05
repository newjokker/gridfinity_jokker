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
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, render_template, request, send_file

from planner import fit_for_kind, make_plan


ROOT = Path(__file__).resolve().parents[1]
OPENSCAD = os.environ.get("OPENSCAD_BIN") or shutil.which("openscad") or "/usr/bin/openscad"
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024
CACHE_DIR = Path("/tmp/gridfinity-stl-cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
RENDER_LOCK = threading.Lock()
PIN_SCAD_PATH = ROOT / "011_BOSL2原版双头弹性插销.scad"
ACTION_LOG_PATH = ROOT / "log" / "action.log"
ACTION_LOG_LOCK = threading.Lock()
ACTION_TIMEZONE = ZoneInfo("Asia/Shanghai")


def _log_text(value, maximum: int = 120) -> str:
    return str(value).replace("\n", " ").replace("\r", " ").replace("|", "/")[:maximum]


def write_action_log(action: str, details: dict | None = None, *, status: int | None = None) -> None:
    parts = [
        datetime.now(ACTION_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S"),
        f"IP {_log_text(request.remote_addr or 'unknown')}",
        _log_text(action, 160),
    ]
    if status is not None:
        parts.append(f"状态 {status}")
    if details:
        detail_text = " ".join(
            f"{_log_text(key, 40)}={_log_text(value)}"
            for key, value in list(details.items())[:15]
        )
        if detail_text:
            parts.append(detail_text)
    try:
        ACTION_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with ACTION_LOG_LOCK, ACTION_LOG_PATH.open("a", encoding="utf-8") as stream:
            stream.write(" | ".join(parts) + "\n")
    except OSError:
        # Logging must never make model generation unavailable.
        app.logger.exception("Unable to write action log: %s", ACTION_LOG_PATH)


@app.after_request
def record_request_action(response):
    action_names = {
        "/": "访问模型首页",
        "/baseplates": "访问底板生成器",
        "/bins": "访问盒子生成器",
        "/pins": "访问插销生成器",
        "/api/download": "生成并下载底板 ZIP",
        "/api/piece-stl": "生成底板 STL",
        "/api/bin-stl": "生成盒子 STL",
        "/api/pin-stl": "生成插销 STL",
    }
    action = action_names.get(request.path)
    if action:
        values = request_values() if request.path.startswith("/api/") else {}
        detail_keys = (
            "width", "depth", "printer_x_cells", "printer_y_cells", "piece_id", "download",
            "gridx", "gridy", "gridz", "divx", "divy", "cut_mode", "target_center_length",
        )
        details = {key: values[key] for key in detail_keys if key in values}
        write_action_log(action, details, status=response.status_code)
    return response


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
        "wall_thickness": number("wall_thickness", 1.2, 0.8, 6, "外壁厚度"),
        "divider_thickness": number("divider_thickness", 1, 0.6, 6, "分隔墙厚度"),
    }
    # Backward compatibility for links created before the shape selector existed.
    if params["cut_cylinders"]:
        params["cut_mode"] = "circles"
    if params["cut_mode"] not in ("compartments", "circles", "rectangles"):
        raise ValueError("开孔模式无效")
    if params["divx"] * params["divy"] > 64:
        raise ValueError("分仓总数不能超过 64")
    inner_x = params["gridx"] * 42 - 0.5 - 2 * params["wall_thickness"]
    inner_y = params["gridy"] * 42 - 0.5 - 2 * params["wall_thickness"]
    cell_x = inner_x / params["divx"] - params["divider_thickness"] / 2
    cell_y = inner_y / params["divy"] - params["divider_thickness"] / 2
    if cell_x <= 0 or cell_y <= 0:
        raise ValueError("壁厚或分隔墙厚度过大，当前盒子无法容纳这些分段")
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
// wall-parameter implementation v2: values are also passed with OpenSCAD -D.
d_wall = {params['wall_thickness']:.3f};
d_div = {params['divider_thickness']:.3f};
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


def parse_pin_payload():
    body = request_values()

    def number(name, default, minimum, maximum, label):
        try:
            value = float(body.get(name, default))
        except (TypeError, ValueError):
            raise ValueError(f"{label}请输入有效数字")
        if not minimum <= value <= maximum:
            raise ValueError(f"{label}需要在 {minimum:g} 到 {maximum:g} 之间")
        return value

    def boolean(name, default=False):
        raw = body.get(name, default)
        return raw if isinstance(raw, bool) else str(raw).lower() in ("1", "true", "yes", "on")

    params = {
        "head_diameter": number("head_diameter", 3.2, 2.5, 4.0, "销身直径"),
        "head_length": number("head_length", 6.0, 4.0, 8.0, "单侧头部长度"),
        "snap_projection": number("snap_projection", 0.5, 0.1, 0.6, "卡点凸出量"),
        "nub_depth": number("nub_depth", 1.2, 0.8, 1.8, "卡点位置"),
        "arm_thickness": number("arm_thickness", 1.0, 0.7, 1.3, "弹性臂壁厚"),
        "fit_clearance": number("fit_clearance", 0.2, 0.05, 0.35, "配合间隙"),
        "head_preload": number("head_preload", 0.16, 0.0, 0.3, "卡点预紧量"),
        "target_center_length": number("target_center_length", 4.34, 1.5, 10.0, "中央长度"),
        "pointed_head": boolean("pointed_head", True),
    }
    radius = params["head_diameter"] / 2
    elastic_space = radius - params["fit_clearance"] - params["arm_thickness"]
    if elastic_space <= 0.1:
        raise ValueError("弹性臂壁厚或配合间隙过大，中间没有足够弹性空间")
    if params["head_preload"] >= params["nub_depth"]:
        raise ValueError("卡点预紧量必须小于卡点位置")
    minimum_center = 2 * (params["nub_depth"] - params["head_preload"])
    if params["target_center_length"] < minimum_center:
        raise ValueError(f"当前头部参数下，中央长度不能小于 {minimum_center:.2f} mm")
    if params["head_length"] <= 2 ** 0.5 * radius + params["fit_clearance"] + 0.5:
        raise ValueError("头部长度过短，无法容纳当前直径和尖头")
    return params


def scad_define(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return f"{float(value):.4f}"


def render_stl(scad_path: Path, stl_path: Path, defines: dict[str, float | bool] | None = None) -> None:
    environment = os.environ.copy()
    environment.setdefault("QT_QPA_PLATFORM", "offscreen")
    arguments = []
    for name, value in (defines or {}).items():
        arguments.extend(["-D", f"{name}={scad_define(value)}"])
    arguments.extend(["-o", str(stl_path), str(scad_path)])

    # Nightly uses the faster Manifold backend. OpenSCAD 2021.01 does not know
    # this option, so retry once without it for local development compatibility.
    attempts = ([OPENSCAD, "--backend=Manifold"], [OPENSCAD])
    last_error = ""
    for prefix in attempts:
        stl_path.unlink(missing_ok=True)
        run = subprocess.run(
            [*prefix, *arguments],
            cwd=ROOT, env=environment, capture_output=True, text=True, timeout=300,
        )
        if not run.returncode and stl_path.exists():
            return
        last_error = run.stderr
    app.logger.error("OpenSCAD failed: %s", last_error[-2000:])
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


@app.get("/pins")
def pins():
    return render_template("pins.html")


@app.post("/api/action")
def browser_action():
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not str(body.get("action", "")).strip():
        return jsonify({"error": "action is required"}), 400
    details = body.get("details") if isinstance(body.get("details"), dict) else {}
    write_action_log(str(body["action"]), details, status=204)
    return ("", 204)


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
                render_stl(scad_path, stl_path, {
                    "d_wall": params["wall_thickness"],
                    "d_div": params["divider_thickness"],
                })
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        return jsonify({"error": str(exc)}), 500

    suffix = {"compartments": "divided", "circles": "circle_array", "rectangles": "rect_array"}[params["cut_mode"]]
    filename = f"gridfinity_{suffix}_{params['gridx']}x{params['gridy']}x{params['gridz']}U.stl"
    response = send_file(stl_path, mimetype="model/stl", as_attachment=as_download, download_name=filename)
    response.headers["Cache-Control"] = "private, max-age=3600"
    response.headers["X-Bin-Grid"] = f"{params['gridx']}x{params['gridy']}x{params['gridz']}"
    return response


@app.route("/api/pin-stl", methods=["GET", "POST"])
def pin_stl():
    try:
        params = parse_pin_payload()
        body = request_values()
        as_download = str(body.get("download", "0")).lower() in ("1", "true", "yes", "on")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if not Path(OPENSCAD).exists():
        return jsonify({"error": "服务器尚未安装 OpenSCAD"}), 503
    if not PIN_SCAD_PATH.exists():
        return jsonify({"error": "服务器缺少插销 SCAD 源文件"}), 503

    source_hash = hashlib.sha256(PIN_SCAD_PATH.read_bytes()).hexdigest()
    cache_input = json.dumps({"source": source_hash, "params": params}, sort_keys=True)
    cache_key = hashlib.sha256(cache_input.encode("utf-8")).hexdigest()
    stl_path = CACHE_DIR / f"pin-{cache_key}.stl"
    try:
        with RENDER_LOCK:
            if not stl_path.exists():
                render_stl(PIN_SCAD_PATH, stl_path, params)
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        return jsonify({"error": str(exc)}), 500

    maximum_width = params["head_diameter"] + 2 * params["snap_projection"] - params["fit_clearance"]
    filename = (
        f"gridfinity_snap_pin_w{maximum_width:.2f}_center{params['target_center_length']:.2f}.stl"
    )
    response = send_file(stl_path, mimetype="model/stl", as_attachment=as_download, download_name=filename)
    response.headers["Cache-Control"] = "private, max-age=3600"
    response.headers["X-Pin-Max-Width"] = f"{maximum_width:.3f}"
    response.headers["X-Pin-Center-Length"] = f"{params['target_center_length']:.3f}"
    return response


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=55504)
