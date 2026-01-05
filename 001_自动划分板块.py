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

def split_len(L, max_len):
    """Split length L into segments <= max_len, as evenly as possible."""
    if L <= 1e-9:
        return []
    n = math.ceil(L / max_len)
    base = L / n
    segs = [base] * n
    # adjust to keep exact sum by distributing rounding later (float safe)
    return segs

def split_cells(n_cells, max_cells):
    """Split integer number of cells into segments of integer cells <= max_cells, as evenly as possible."""
    if n_cells <= 0:
        return []
    n = math.ceil(n_cells / max_cells)
    base = n_cells // n
    rem = n_cells % n
    return [base + (1 if i < rem else 0) for i in range(n)]

def generate_gridfinity_baseplate_plan(M, N, a, b, K=42):
    """
    Returns:
      info: dict with grid counts + symmetric margins
      pieces: list of printable rectangles (pieces) that tile the drawer bottom
    Constraints:
      - Margins are symmetric (left=right, top=bottom)
      - Max number of KxK squares is achieved: floor(M/K)*floor(N/K)
      - Each printed piece fits within a x b (rotating allowed by user in slicer; we still ensure w<=a and h<=b
        for one orientation; you can swap a,b if you want rotation).
    """
    gx = math.floor(M / K)
    gy = math.floor(N / K)
    used_x = gx * K
    used_y = gy * K
    mx = (M - used_x) / 2.0
    my = (N - used_y) / 2.0

    # Choose max grid-cells per printable piece within a,b
    max_cx = max(1, math.floor(a / K))
    max_cy = max(1, math.floor(b / K))

    seg_x_cells = split_cells(gx, max_cx)  # each *K width
    seg_y_cells = split_cells(gy, max_cy)

    pieces = []
    pid = 1

    # Coordinate system: drawer lower-left at (0,0)
    # Central grid region starts at (mx, my)
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

    # Helper to add edge strip pieces by splitting along one axis to respect a/b
    def add_strip(x0, y0, W, H, split_along="x"):
        nonlocal pid
        if W <= 1e-9 or H <= 1e-9:
            return
        if W <= a + 1e-9 and H <= b + 1e-9:
            pieces.append(Piece(pid, x0, y0, W, H, "edge"))
            pid += 1
            return
        if split_along == "x":
            segs = split_len(W, a)
            x = x0
            for s in segs:
                pieces.append(Piece(pid, x, y0, s, H, "edge"))
                pid += 1
                x += s
        else:
            segs = split_len(H, b)
            y = y0
            for s in segs:
                pieces.append(Piece(pid, x0, y, W, s, "edge"))
                pid += 1
                y += s

    # 2) Bottom and top margin strips (full width M, height my)
    add_strip(0, 0, M, my, split_along="x")
    add_strip(0, my + used_y, M, my, split_along="x")

    # 3) Left and right margin strips (height used_y, width mx)
    add_strip(0, my, mx, used_y, split_along="y")
    add_strip(mx + used_x, my, mx, used_y, split_along="y")

    info = dict(
        M=M, N=N, a=a, b=b, K=K,
        gx=gx, gy=gy, boxes=gx*gy,
        used_x=used_x, used_y=used_y,
        margin_left=mx, margin_right=mx, margin_bottom=my, margin_top=my,
        seg_x_cells=seg_x_cells, seg_y_cells=seg_y_cells
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

    # ===== 关键优化 1：关闭坐标轴（刻度 + 边框）=====
    ax.axis("off")

    # drawer outline
    ax.add_patch(
        plt.Rectangle((0, 0), M, N, fill=False, linewidth=2)
    )

    # central grid region outline
    ax.add_patch(
        plt.Rectangle(
            (mx, my), used_x, used_y,
            fill=False, linewidth=2, linestyle="--"
        )
    )

    # optional: grid lines（42 网格）
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
        ax.add_patch(
            plt.Rectangle(
                (p.x, p.y), p.w, p.h,
                fill=False, linewidth=2, linestyle=ls
            )
        )

        # ===== 关键优化 2 + 3：只画编号，字体更大更醒目 =====
        cx = p.x + p.w / 2
        cy = p.y + p.h / 2
        ax.text(
            cx, cy, str(p.pid),
            ha="center",
            va="center",
            fontsize=14,          # 比原来 8 大很多
            fontweight="bold",
            color="red"
        )

    plt.tight_layout()
    plt.show()



# Demo with plausible numbers
info, pieces = generate_gridfinity_baseplate_plan(M=608, N=613, a=42*5, b=42*5, K=42)
info, len(pieces), pieces[:3], info["boxes"]


plot_plan(info, pieces, show_grid=True)


for each in pieces:
    print(each)
