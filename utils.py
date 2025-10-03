"""
utils.py — Skill Gomoku (技能五子棋)

提供：
- 坐标换算：grid_to_px, px_to_grid
- 区域矩形：board_rect, panel_rect
- 图片加载与圆形裁剪：load_image, load_circle_avatar
- 杂项：file_exists, clamp

依赖：pygame
"""
from __future__ import annotations
from typing import Tuple, Optional, Dict, Any
import os

try:
    import pygame
except Exception as e:  # pragma: no cover
    raise SystemExit("需要安装 pygame：pip install pygame") from e


# ------------------------------
# 公共小工具
# ------------------------------

def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def file_exists(path: str) -> bool:
    return os.path.exists(path) and os.path.isfile(path)


# ------------------------------
# 坐标换算（棋盘交点 ↔ 屏幕像素）
# ------------------------------

def grid_to_px(i: int, j: int, config: Dict[str, Any]) -> Tuple[int, int]:
    """将棋盘网格坐标 (i,j) → 屏幕像素坐标 (x,y)。
    约定：i 为列（x 轴，从左到右），j 为行（y 轴，从上到下），
    返回的是**交点中心**像素坐标。
    """
    margin = int(config["MARGIN"])
    cell = int(config["CELL_SIZE"])
    x = margin + i * cell
    y = margin + j * cell
    return x, y


def px_to_grid(x: int, y: int, config: Dict[str, Any]) -> Optional[Tuple[int, int]]:
    """将像素坐标 (x,y) 映射到最近的网格交点 (i,j)。
    若超出棋盘容差范围（半格）返回 None。
    """
    size = int(config["BOARD_SIZE"])
    margin = int(config["MARGIN"])
    cell = int(config["CELL_SIZE"])

    left = margin
    top = margin
    grid_w = cell * (size - 1)

    # 允许点击区域比网格框再外扩半格，便于玩家点在交点附近
    if not (left - cell // 2 <= x <= left + grid_w + cell // 2):
        return None
    if not (top - cell // 2 <= y <= top + grid_w + cell // 2):
        return None

    # 四舍五入到最近交点
    gi = int(round((x - left) / cell))
    gj = int(round((y - top) / cell))
    if 0 <= gi < size and 0 <= gj < size:
        return gi, gj
    return None


# ------------------------------
# 区域矩形（用于 UI 布局与点击判定）
# ------------------------------

def board_rect(config: Dict[str, Any]) -> pygame.Rect:
    """返回棋盘绘制区域的外接矩形（不含右侧信息面板）。"""
    size = int(config["BOARD_SIZE"])
    margin = int(config["MARGIN"])
    cell = int(config["CELL_SIZE"])
    grid_w = cell * (size - 1)
    return pygame.Rect(margin, margin, grid_w, grid_w)


def panel_rect(config: Dict[str, Any]) -> pygame.Rect:
    """返回右侧信息/技能面板矩形。
    面板位于棋盘区域右侧，宽度为 PANEL_W，高度与窗口同高。
    如果 config 未包含 WINDOW_H，则按棋盘高度计算（MARGIN*2 + grid_w）。
    """
    margin = int(config["MARGIN"])
    cell = int(config["CELL_SIZE"])
    size = int(config["BOARD_SIZE"])
    panel_w = int(config["PANEL_W"])
    grid_w = cell * (size - 1)

    win_h = int(config.get("WINDOW_H", margin * 2 + grid_w))
    left = margin * 2 + grid_w  # 棋盘右侧再留一格 margin 的视觉缓冲
    return pygame.Rect(left, 0, panel_w, win_h)


# ------------------------------
# 图片加载与圆形裁剪
# ------------------------------

def load_image(path: str) -> pygame.Surface:
    """加载图片并保持 alpha 通道；不存在时抛出 FileNotFoundError。"""
    if not file_exists(path):
        raise FileNotFoundError(path)
    surf = pygame.image.load(path)
    # 尽量保留透明度
    try:
        surf = surf.convert_alpha()
    except Exception:
        surf = surf.convert()
    return surf


def _circle_mask(diameter: int) -> pygame.Surface:
    mask = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
    pygame.draw.circle(mask, (255, 255, 255, 255), (diameter // 2, diameter // 2), diameter // 2)
    return mask


def load_circle_avatar(path: str, diameter: int) -> pygame.Surface:
    """加载并裁剪为圆形头像；若加载失败，返回透明占位。"""
    try:
        src = load_image(path)
    except Exception:
        return pygame.Surface((diameter, diameter), pygame.SRCALPHA)

    img = pygame.transform.smoothscale(src, (diameter, diameter))
    mask = _circle_mask(diameter)
    out = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
    out.blit(img, (0, 0))
    out.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return out
