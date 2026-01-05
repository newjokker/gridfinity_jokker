import math
import matplotlib.pyplot as plt
from dataclasses import dataclass

@dataclass
class Piece:
    pid: int
    x: float
    y: float
    w: float
    h: float
    kind: str  # "grid" or "edge"

def split_cells(n_cells, max_cells):
    """Split integer number of cells into segments of integer cells <= max_cells, as evenly as possible."""
    if n_cells <= 0:
        return []
    n = math.ceil(n_cells / max_cells)
    base = n_cells // n
    rem = n_cells % n
    return [base + (1 if i < rem else 0) for i in range(n)]

def pack_aligned_segments(lengths, max_len):
    """
    把一串“对齐段”(lengths) 按顺序合并成若干块，
    每块长度 <= max_len，且只在对齐段边界处分割（接缝保持对齐）。
    """
    out = []
    cur = 0.0
    for L in lengths:
        if L <= 1e-9:
            continue
        if cur <= 1e-9:
            cur = L
        elif cur + L <= max_len + 1e-9:
            cur += L
        else:
            out.append(cur)
            cur = L
    if cur > 1e-9:
        out.append(cur)
    return out

def aligned_breaks_1d(total, start, used, K):
    """
    total: 全长 M 或 N
    start: mx 或 my
    used : used_x 或 used_y
    生成必须对齐的断点：[0, start, start+K, ..., start+used, total]
    """
    b = [0.0, float(start)]
    # n = gx 或 gy
    n = int(round(used / K)) if K > 0 else 0
    for i in range(1, n):
        b.append(float(start + i * K))
    b += [float(start + used), float(total)]

    # 去重 + 排序 + 夹紧
    b = sorted(set([max(0.0, min(float(total), x)) for x in b]))
    # 清理过近的点
    clean = [b[0]]
    for x in b[1:]:
        if x - clean[-1] > 1e-9:
            clean.append(x)
    return clean

def add_strip_aligned_x(pieces, x0, y0, W, H, a, pid_start, x_breaks):
    """
    沿 x 在 x_breaks 这些对齐断点处分割，再按 a 打包。
    """
    pid = pid_start
    if W <= 1e-9 or H <= 1e-9:
        return pid

    x1 = x0 + W

    # 取落在条带范围内的断点
    cuts = [x for x in x_breaks if x0 - 1e-9 <= x <= x1 + 1e-9]
    cuts = [x0] + [x for x in cuts if x0 < x < x1] + [x1]

    # 最小对齐段
    elems = [cuts[i + 1] - cuts[i] for i in range(len(cuts) - 1)]

    # 按打印尺寸打包（仍只在对齐边界处分割）
    packs = pack_aligned_segments(elems, a)

    x = x0
    for w in packs:
        if w > a + 1e-9 or H > 1e-9 and H > 1e18:  # 不可能分支，仅占位避免误改
            pass
        pieces.append(Piece(pid, x, y0, w, H, "edge"))
        pid += 1
        x += w

    return pid

def add_strip_aligned_y(pieces, x0, y0, W, H, b, pid_start, y_breaks):
    """
    沿 y 在 y_breaks 这些对齐断点处分割，再按 b 打包。
    """
    pid = pid_start
    if W <= 1e-9 or H <= 1e-9:
        return pid

    y1 = y0 + H

    cuts = [y for y in y_breaks if y0 - 1e-9 <= y <= y1 + 1e-9]
    cuts = [y0] + [y for y in cuts if y0 < y < y1] + [y1]

    elems = [cuts[i + 1] - cuts[i] for i in range(len(cuts) - 1)]
    packs = pack_aligned_segments(elems, b)

    y = y0
    for h in packs:
        pieces.append(Piece(pid, x0, y, W, h, "edge"))
        pid += 1
        y += h

    return pid

def generate_gridfinity_baseplate_plan(M, N, a, b, K=42, min_margin_cells=1):
    """
    方案：
      1) 四周边缘至少 min_margin_cells 个 K 的宽度（默认 1 格）
      2) 中间区域尽量多放 K 网格（在满足边缘约束下最大化 gx*gy）
      3) 边缘 pieces 的接缝必须对齐到网格线（mx+iK / my+jK）
      4) 每块 piece 尺寸需 <= a x b（不考虑旋转；需要旋转就交换 a,b）
    """
    if K <= 0:
        raise ValueError("K must be positive.")

    min_margin = min_margin_cells * K

    # 打印尺寸如果比一格还小，则无法保证“只在网格线处分割”
    if a + 1e-9 < K:
        raise ValueError(f"Printer size a={a} is smaller than K={K}; cannot keep edge seams aligned on K-grid.")
    if b + 1e-9 < K:
        raise ValueError(f"Printer size b={b} is smaller than K={K}; cannot keep edge seams aligned on K-grid.")

    # 抽屉太小则无法做到“四周至少一格 + 中间至少一格”
    if M < 2 * min_margin + K or N < 2 * min_margin + K:
        raise ValueError(
            f"Drawer too small for min margins: need M >= {2*min_margin+K}, N >= {2*min_margin+K}"
        )

    # 中间可用尺寸：扣掉两边至少一格
    avail_x = M - 2 * min_margin
    avail_y = N - 2 * min_margin

    gx = math.floor(avail_x / K)
    gy = math.floor(avail_y / K)

    used_x = gx * K
    used_y = gy * K

    # 对称边距（一定 >= min_margin）
    mx = (M - used_x) / 2.0
    my = (N - used_y) / 2.0

    # 每个网格 piece 最多包含多少格（受 a,b 限制）
    max_cx = max(1, math.floor(a / K))
    max_cy = max(1, math.floor(b / K))

    seg_x_cells = split_cells(gx, max_cx)
    seg_y_cells = split_cells(gy, max_cy)

    pieces = []
    pid = 1

    # Central grid origin
    x0_grid = mx
    y0_grid = my

    # 1) Central grid pieces (multiples of K)
    y = y0_grid
    for cy in seg_y_cells:
        h = cy * K
        x = x0_grid
        for cx in seg_x_cells:
            w = cx * K
            if w > a + 1e-9 or h > b + 1e-9:
                raise ValueError("Grid piece exceeds printer size; reduce a/b or adjust.")
            pieces.append(Piece(pid, x, y, w, h, "grid"))
            pid += 1
            x += w
        y += h

    # 2) Edge strips with seams aligned to grid lines
    x_breaks = aligned_breaks_1d(M, mx, used_x, K)
    y_breaks = aligned_breaks_1d(N, my, used_y, K)

    # Bottom and top strips: full width M, height my, split along x (aligned)
    pid = add_strip_aligned_x(pieces, 0, 0, M, my, a, pid, x_breaks)
    pid = add_strip_aligned_x(pieces, 0, my + used_y, M, my, a, pid, x_breaks)

    # Left and right strips: height used_y, width mx, split along y (aligned)
    pid = add_strip_aligned_y(pieces, 0, my, mx, used_y, b, pid, y_breaks)
    pid = add_strip_aligned_y(pieces, mx + used_x, my, mx, used_y, b, pid, y_breaks)

    info = dict(
        M=M, N=N, a=a, b=b, K=K,
        gx=gx, gy=gy, boxes=gx * gy,
        used_x=used_x, used_y=used_y,
        margin_left=mx, margin_right=mx, margin_bottom=my, margin_top=my,
        seg_x_cells=seg_x_cells, seg_y_cells=seg_y_cells,
        min_margin=min_margin,
        x_breaks=x_breaks, y_breaks=y_breaks
    )
    return info, pieces

def plot_plan(info, pieces, show_grid=True):
    M, N, K = info["M"], info["N"], info["K"]
    mx, my = info["margin_left"], info["margin_bottom"]
    used_x, used_y = info["used_x"], info["used_y"]

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.set_aspect("equal")
    ax.set_xlim(0, M)
    ax.set_ylim(0, N)

    ax.axis("off")

    # drawer outline
    ax.add_patch(plt.Rectangle((0, 0), M, N, fill=False, linewidth=2))

    # central grid region outline
    ax.add_patch(plt.Rectangle((mx, my), used_x, used_y, fill=False, linewidth=2, linestyle="--"))

    # optional: grid lines
    if show_grid:
        for i in range(info["gx"] + 1):
            x = mx + i * K
            ax.plot([x, x], [my, my + used_y], linewidth=0.6, alpha=0.6)
        for j in range(info["gy"] + 1):
            y = my + j * K
            ax.plot([mx, mx + used_x], [y, y], linewidth=0.6, alpha=0.6)

    # pieces
    for p in pieces:
        ls = "-" if p.kind == "grid" else ":"
        ax.add_patch(plt.Rectangle((p.x, p.y), p.w, p.h, fill=False, linewidth=2, linestyle=ls))

        cx = p.x + p.w / 2
        cy = p.y + p.h / 2
        ax.text(
            cx, cy, str(p.pid),
            ha="center", va="center",
            fontsize=14, fontweight="bold", color="red"
        )

    plt.tight_layout()
    plt.show()

# =======================
# Demo
# =======================
if __name__ == "__main__":
    info, pieces = generate_gridfinity_baseplate_plan(
        M=413, N=408,
        a=42 * 5, b=42 * 5,
        K=42, min_margin_cells=1
    )

    print("margins:", info["margin_left"], info["margin_bottom"], "min_margin:", info["min_margin"])
    print("boxes:", info["boxes"], "pieces:", len(pieces))

    plot_plan(info, pieces, show_grid=True)

    for each in pieces:
        print(each)
