"""
ui.py — Skill Gomoku (技能五子棋)

改进版（兼容 dataclass GameContext 与 dict + 中文字体方案B + 面板状态行）：
- 字体：优先使用 config["FONT_PATH"]，否则自动匹配系统中文字体（Windows/macOS/Linux 常见字体）。
- 兼容上下文：所有 ctx 访问改为 ctx_get/p_get，兼容 dict 与 dataclass。
- 面板新增“状态行”：
  * 冻结中 → “被冻结：可按3解除或跳过回合”
  * 擒拿守势中 → “擒拿：拦截对方下一技能”
  * 东山再起请求中 → “请求重开：等待对手回应”
- 绘制顺序：先右侧面板、再头像条，避免白方头像被面板遮挡；覆盖层始终最上。
"""
from __future__ import annotations
from typing import Any, Dict, List, Tuple, Optional, Union

import os
import pygame

try:
    import utils  # type: ignore
except Exception:
    utils = None  # 允许降级

# 常量对齐（与 engine/skills/models 一致）
SIDE_BLACK = 1
SIDE_WHITE = 2

SKILL_FEISHA = 1
SKILL_JINGRU = 2
SKILL_SHUIDI = 3
SKILL_LIBA = 4
SKILL_QINNA = 5
SKILL_DSZQ = 6

Ctx = Union[Dict[str, Any], Any]

# ==============================
# 字体系统（方案B：自动匹配系统中文字体）
# ==============================
_font_cache: Dict[tuple, pygame.font.Font] = {}
_FONT_FILE: Optional[str] = None  # 选中的中文字体文件（缓存路径）
config_global: Dict[str, Any] = {}  # 保存最近一次渲染时的 config，供字体选择使用


def _choose_cjk_font(config: Dict[str, Any]) -> Optional[str]:
    """选择可渲染中文的字体文件路径。
    优先：config["FONT_PATH"] → 系统常见中文字体（match_font）。
    """
    cand = config.get("FONT_PATH")
    if cand and os.path.isfile(cand):
        return cand

    candidates = [
        # Windows 常见
        "Microsoft YaHei UI", "Microsoft YaHei", "MSYH", "SimHei",
        # macOS 常见
        "PingFang SC", "Heiti SC", "STHeiti",
        # Linux / 跨平台常见
        "Noto Sans CJK SC", "Source Han Sans SC", "WenQuanYi Zen Hei",
    ]
    for name in candidates:
        path = pygame.font.match_font(name, bold=False, italic=False)
        if path:
            return path
    return None


def get_font(size: int, bold: bool = False) -> pygame.font.Font:
    global _FONT_FILE
    key = (size, bool(bold))
    f = _font_cache.get(key)
    if f:
        return f
    if _FONT_FILE is None:
        _FONT_FILE = _choose_cjk_font(config_global)
    if _FONT_FILE:
        f = pygame.font.Font(_FONT_FILE, size)
        if bold:
            f.set_bold(True)
    else:
        # 兜底（可能不含中文）
        f = pygame.font.SysFont(None, size, bold=bold)
    _font_cache[key] = f
    return f

# ==============================
# 兼容访问器（dict / dataclass）
# ==============================

def ctx_get(ctx: Ctx, key: str, default=None):
    if isinstance(ctx, dict):
        return ctx.get(key, default)
    return getattr(ctx, key, default)


def p_get(p: Any, name: str, default=None):
    if isinstance(p, dict):
        return p.get(name, default)
    return getattr(p, name, default)

# ==============================
# 入口
# ==============================

def render(ctx: Ctx, config: Dict[str, Any], assets: Dict[str, Any], screen: pygame.Surface) -> None:
    # 记录 config 供字体系统选择字体
    config_global.clear()
    config_global.update(config)

    draw_background(screen, config)
    draw_board_grid(screen, config)
    draw_star_points(screen, config)
    draw_pieces(screen, ctx, config)
    draw_last_move_highlight(screen, ctx, config)
    draw_right_panel(screen, ctx, assets, config)   # 先画面板
    draw_avatar_bar(screen, ctx, assets, config)    # 再画头像条，避免被面板遮挡
    draw_overlays(screen, ctx, config)              # 覆盖层最上

# ------------------------------
# 背景 & 棋盘
# ------------------------------

def draw_background(screen: pygame.Surface, config: Dict[str, Any]) -> None:
    screen.fill(config["COLOR_BG"])  # 木色背景


def draw_board_grid(screen: pygame.Surface, config: Dict[str, Any]) -> None:
    size, gap, margin = config["BOARD_SIZE"], config["CELL_SIZE"], config["MARGIN"]
    grid_w = gap * (size - 1)
    left, top = margin, margin
    # 边框加粗
    rect_outer = pygame.Rect(left, top, grid_w, grid_w)
    pygame.draw.rect(screen, config["COLOR_GRID"], rect_outer, width=3)
    # 网格线
    for i in range(size):
        y = top + i * gap
        x = left + i * gap
        pygame.draw.line(screen, config["COLOR_GRID"], (left, y), (left + grid_w, y), width=1)
        pygame.draw.line(screen, config["COLOR_GRID"], (x, top), (x, top + grid_w), width=1)


def draw_star_points(screen: pygame.Surface, config: Dict[str, Any]) -> None:
    size, gap, margin = config["BOARD_SIZE"], config["CELL_SIZE"], config["MARGIN"]
    star_idx = [3, 7, 11]
    r = 4
    for i in star_idx:
        for j in star_idx:
            cx = margin + j * gap
            cy = margin + i * gap
            pygame.draw.circle(screen, config["COLOR_GRID"], (cx, cy), r)

# ------------------------------
# 棋子 & 高亮
# ------------------------------

def draw_piece(screen: pygame.Surface, x: int, y: int, side: int, config: Dict[str, Any]) -> None:
    # 棋子带黑边
    border_col = (10, 10, 10)
    fill = config["COLOR_BLACK"] if side == SIDE_BLACK else config["COLOR_WHITE"]
    r = int(config["CELL_SIZE"] * 0.45)
    pygame.draw.circle(screen, border_col, (x, y), r)
    pygame.draw.circle(screen, fill, (x, y), r - 2)


def draw_pieces(screen: pygame.Surface, ctx: Ctx, config: Dict[str, Any]) -> None:
    board = ctx_get(ctx, "board")
    size = config["BOARD_SIZE"]
    for j in range(size):
        for i in range(size):
            side = board[j][i]
            if side in (SIDE_BLACK, SIDE_WHITE):
                px, py = (utils.grid_to_px(i, j, config) if utils else _grid_to_px(i, j, config))
                draw_piece(screen, px, py, side, config)


def draw_last_move_highlight(screen: pygame.Surface, ctx: Ctx, config: Dict[str, Any]) -> None:
    pos = ctx_get(ctx, "last_move_pos")
    if not pos:
        return
    i, j = pos
    x, y = (utils.grid_to_px(i, j, config) if utils else _grid_to_px(i, j, config))
    s = int(config["CELL_SIZE"] * 0.6)
    rect = pygame.Rect(0, 0, s, s)
    rect.center = (x, y)
    pygame.draw.rect(screen, config["COLOR_ACCENT"], rect, width=3)

# ------------------------------
# 顶部头像条
# ------------------------------

def draw_avatar_bar(screen: pygame.Surface, ctx: Ctx, assets: Dict[str, Any], config: Dict[str, Any]) -> None:
    h = int(config.get("AVATAR_BAR_H", 64))
    margin = config["MARGIN"]
    cell = config["CELL_SIZE"]
    width = margin * 2 + cell * (config["BOARD_SIZE"] - 1)

    bar_rect = pygame.Rect(margin, max(0, margin - h), width, h)
    overlay = pygame.Surface(bar_rect.size, pygame.SRCALPHA)
    overlay.fill((255, 255, 255, 30))
    screen.blit(overlay, bar_rect.topleft)

    # 左右头像
    av1 = assets.get("AVATAR1")
    av2 = assets.get("AVATAR2")
    diameter = h - 8

    # 占位（棋子风格圆点）
    def avatar_or_placeholder(surface, side):
        cx = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
        if surface:
            cx.blit(surface, (0, 0))
        else:
            col = config["COLOR_BLACK"] if side == SIDE_BLACK else config["COLOR_WHITE"]
            pygame.draw.circle(cx, (10, 10, 10), (diameter // 2, diameter // 2), diameter // 2)
            pygame.draw.circle(cx, col, (diameter // 2, diameter // 2), diameter // 2 - 2)
        return cx

    left_img = avatar_or_placeholder(av1, SIDE_BLACK)
    right_img = avatar_or_placeholder(av2, SIDE_WHITE)

    # 布局：左、右各一
    left_pos = (bar_rect.left + 8, bar_rect.centery - diameter // 2)
    right_pos = (bar_rect.right - diameter - 108, bar_rect.centery - diameter // 2)

    screen.blit(left_img, left_pos)
    screen.blit(right_img, right_pos)

    # 外圈高亮：当前执子
    turn = ctx_get(ctx, "turn_side") or SIDE_BLACK
    hl_col = config["COLOR_ACCENT"]
    if turn == SIDE_BLACK:
        cx = left_pos[0] + diameter // 2
        cy = left_pos[1] + diameter // 2
        pygame.draw.circle(screen, hl_col, (cx, cy), diameter // 2 + 2, width=3)
    else:
        cx = right_pos[0] + diameter // 2
        cy = right_pos[1] + diameter // 2
        pygame.draw.circle(screen, hl_col, (cx, cy), diameter // 2 + 2, width=3)

    # 名字
    font = get_font(20)
    name_left = config.get("NAME_BLACK", "技能五")
    name_right = config.get("NAME_WHITE", "子棋")
    text_l = font.render(name_left, True, config["COLOR_TEXT"])
    text_r = font.render(name_right, True, config["COLOR_TEXT"])
    screen.blit(text_l, (left_pos[0] + diameter + 8, bar_rect.top + 6))
    screen.blit(text_r, (right_pos[0] - text_r.get_width() - 8, bar_rect.top + 6))

# ------------------------------
# 右侧信息面板
# ------------------------------

def draw_right_panel(screen: pygame.Surface, ctx: Ctx, assets: Dict[str, Any], config: Dict[str, Any]) -> None:
    prect = (utils.panel_rect(config) if utils else _panel_rect(config))
    pygame.draw.rect(screen, config["COLOR_PANEL"], prect)

    # 内边距
    pad = 16
    x = prect.left + pad
    y = prect.top + pad

    y = draw_title_and_status(screen, ctx, config, x, y)
    y = draw_move_count(screen, ctx, config, x, y + 6)
    y = draw_skill_buttons(screen, ctx, assets, config, x, y + 10)
    y = draw_hotkey_hints(screen, config, x, y + 12)
    y = draw_status_line(screen, ctx, config, x, y + 8)  # 新增状态文字
    _ = draw_message_area(screen, ctx, config, x, prect.bottom - pad)  # 自底向上排版


def draw_title_and_status(screen, ctx: Ctx, config: Dict[str, Any], x: int, y: int) -> int:
    title_font = get_font(22)
    small = get_font(16)
    title = config.get("WINDOW_TITLE", "技能五子棋 | Skill Gomoku")
    screen.blit(title_font.render(title, True, (40, 40, 40)), (x, y))
    y += 28

    # 当前手（小圆棋子）
    turn = ctx_get(ctx, "turn_side") or SIDE_BLACK
    col = config["COLOR_BLACK"] if turn == SIDE_BLACK else config["COLOR_WHITE"]
    pygame.draw.circle(screen, (10, 10, 10), (x + 10, y + 10), 10)
    pygame.draw.circle(screen, col, (x + 10, y + 10), 8)
    txt = small.render("当前执子", True, (50, 50, 50))
    screen.blit(txt, (x + 26, y))
    return y + 20


def draw_move_count(screen, ctx: Ctx, config: Dict[str, Any], x: int, y: int) -> int:
    small = get_font(16)
    moves = len(ctx_get(ctx, "move_history") or [])
    text = small.render(f"已下手数：{moves}", True, (50, 50, 50))
    screen.blit(text, (x, y))
    return y + 20

# —— 技能按钮 ——
_SKILL_NAMES = {
    SKILL_FEISHA: "飞沙走石",
    SKILL_JINGRU: "静如止水",
    SKILL_SHUIDI: "水滴石穿",
    SKILL_LIBA: "力拔山兮",
    SKILL_QINNA: "擒拿",
    SKILL_DSZQ: "东山再起",
}

_skill_button_cache: List[Tuple[int, pygame.Rect]] = []  # (skill_id, rect)

def layout_skill_buttons(config: Dict[str, Any]) -> List[Tuple[int, pygame.Rect]]:
    global _skill_button_cache
    if _skill_button_cache:
        return _skill_button_cache

    prect = (utils.panel_rect(config) if utils else _panel_rect(config))
    pad = 16
    x = prect.left + pad
    y = prect.top + 90  # 标题+状态+手数预留

    btn_w = (prect.width - pad * 2 - 10) // 2
    btn_h = 56
    gap = 10

    order = [SKILL_FEISHA, SKILL_JINGRU, SKILL_SHUIDI, SKILL_LIBA, SKILL_QINNA, SKILL_DSZQ]
    rects: List[Tuple[int, pygame.Rect]] = []
    for idx, sid in enumerate(order):
        row = idx // 2
        col = idx % 2
        rx = x + col * (btn_w + gap)
        ry = y + row * (btn_h + gap)
        rects.append((sid, pygame.Rect(rx, ry, btn_w, btn_h)))

    _skill_button_cache = rects
    return rects


def draw_skill_buttons(screen, ctx: Ctx, assets: Dict[str, Any], config: Dict[str, Any], x: int, y: int) -> int:
    rects = layout_skill_buttons(config)
    for sid, rect in rects:
        draw_skill_button(screen, rect, sid, ctx, assets, config)
    last_rect = rects[-1][1]
    return last_rect.bottom + 4


def draw_skill_button(screen: pygame.Surface, rect: pygame.Rect, skill_id: int,
                      ctx: Ctx, assets: Dict[str, Any], config: Dict[str, Any]) -> None:
    # 背板
    pygame.draw.rect(screen, (255, 255, 255), rect, border_radius=10)
    pygame.draw.rect(screen, (200, 200, 200), rect, width=1, border_radius=10)

    # 图标
    icon = assets.get("ICONS", {}).get(skill_id)
    name = _SKILL_NAMES.get(skill_id, f"Skill {skill_id}")

    pad = 8
    icon_sz = rect.height - pad * 2
    if icon:
        try:
            scaled = pygame.transform.smoothscale(icon, (icon_sz, icon_sz))
            screen.blit(scaled, (rect.left + pad, rect.top + pad))
        except Exception:
            icon = None

    # 名称
    font = get_font(18)
    tx = rect.left + pad + (icon_sz + pad if icon else 0)
    ty = rect.centery - 10
    screen.blit(font.render(name, True, (40, 40, 40)), (tx, ty))

    # 冷却遮罩
    side = ctx_get(ctx, "turn_side") or SIDE_BLACK
    players = ctx_get(ctx, "players")
    p = players[side]
    cds = p_get(p, "cooldowns", {})
    cd = int(cds.get(skill_id, 0))
    if cd > 0:
        overlay = pygame.Surface(rect.size, pygame.SRCALPHA)
        overlay.fill((80, 80, 80, 140))
        screen.blit(overlay, rect.topleft)
        cd_font = get_font(20)
        cd_text = cd_font.render(str(cd), True, (255, 255, 255))
        screen.blit(cd_text, (rect.centerx - cd_text.get_width() // 2, rect.centery - cd_text.get_height() // 2))


def is_point_in_skill_button(pos: Tuple[int, int], config: Dict[str, Any]) -> Optional[int]:
    for sid, r in layout_skill_buttons(config):
        if r.collidepoint(pos):
            return sid
    return None


def draw_hotkey_hints(screen, config, x: int, y: int) -> int:
    small = get_font(14)
    lines = [
        "快捷键：1-6 技能",
        "U 悔棋 / R 重新开局 / Esc 重置",
    ]
    for s in lines:
        txt = small.render(s, True, (80, 80, 80))
        screen.blit(txt, (x, y))
        y += 18
    return y


def draw_status_line(screen, ctx: Ctx, config: Dict[str, Any], x: int, y: int) -> int:
    """信息面板中的小状态行。"""
    sui = ctx_get(ctx, "skill_ui_state") or {}
    players = ctx_get(ctx, "players") or {}
    side = ctx_get(ctx, "turn_side") or SIDE_BLACK
    p = players.get(side) if isinstance(players, dict) else None

    status_text = None
    if sui.get("freeze_window_open"):
        status_text = "被冻结：可按3解除或跳过回合"
    elif p_get(p, "qinna_stance", False):
        status_text = "擒拿：拦截对方下一技能"
    elif sui.get("rematch_dialog_open"):
        status_text = "请求重开：等待对手回应"

    if status_text:
        small = get_font(14)
        txt = small.render(status_text, True, (200, 60, 60))
        screen.blit(txt, (x, y))
        return y + 20
    return y


def draw_message_area(screen, ctx, config, x: int, bottom_y: int) -> None:
    """显示最近 3 条消息，靠底部对齐。"""
    msgs = (ctx_get(ctx, "messages") or [])[-3:]
    small = get_font(16)
    y = bottom_y
    for s in reversed(msgs):  # 从底往上
        txt = small.render(s, True, (60, 60, 60))
        y -= txt.get_height() + 6
        screen.blit(txt, (x, y))

# ------------------------------
# 覆盖层（冻结 / 目标选择 / 重开）
# ------------------------------

def draw_overlays(screen: pygame.Surface, ctx: Ctx, config: Dict[str, Any]) -> None:
    draw_freeze_overlay(screen, ctx, config)
    draw_target_select_hint(screen, ctx, config)
    draw_rematch_dialog(screen, ctx, config)


def draw_freeze_overlay(screen: pygame.Surface, ctx: Ctx, config: Dict[str, Any]) -> None:
    sui = ctx_get(ctx, "skill_ui_state") or {}
    if not sui.get("freeze_window_open"):
        return
    brect = (utils.board_rect(config) if utils else _board_rect(config))
    overlay = pygame.Surface(brect.size, pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 90))
    screen.blit(overlay, brect.topleft)

    # 文案
    hint = "按 3 使用水滴石穿解除，或点击屏幕跳过本回合"
    font = get_font(20)
    txt = font.render(hint, True, (255, 255, 255))
    cx = brect.left + brect.width // 2 - txt.get_width() // 2
    cy = brect.top + 12
    screen.blit(txt, (cx, cy))


def draw_target_select_hint(screen: pygame.Surface, ctx: Ctx, config: Dict[str, Any]) -> None:
    sui = ctx_get(ctx, "skill_ui_state") or {}
    if not sui.get("target_select_active"):
        return
    # 高亮对方所有可选棋子：黄框
    board = ctx_get(ctx, "board")
    size = config["BOARD_SIZE"]
    enemy = SIDE_WHITE if (ctx_get(ctx, "turn_side") or SIDE_BLACK) == SIDE_BLACK else SIDE_BLACK
    for j in range(size):
        for i in range(size):
            if board[j][i] == enemy:
                x, y = (utils.grid_to_px(i, j, config) if utils else _grid_to_px(i, j, config))
                s = int(config["CELL_SIZE"] * 0.6)
                rect = pygame.Rect(0, 0, s, s)
                rect.center = (x, y)
                pygame.draw.rect(screen, config["COLOR_ACCENT"], rect, width=3)


def draw_rematch_dialog(screen: pygame.Surface, ctx: Ctx, config: Dict[str, Any]) -> None:
    sui = ctx_get(ctx, "skill_ui_state") or {}
    if not sui.get("rematch_dialog_open"):
        return

    win_w, win_h = config.get("WINDOW_W"), config.get("WINDOW_H")
    dlg_w, dlg_h = 380, 160
    rect = pygame.Rect((win_w - dlg_w)//2, (win_h - dlg_h)//2, dlg_w, dlg_h)

    # 半透明背景
    overlay = pygame.Surface((win_w, win_h), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 100))
    screen.blit(overlay, (0, 0))

    # 窗体
    pygame.draw.rect(screen, (250, 250, 250), rect, border_radius=12)
    pygame.draw.rect(screen, (200, 200, 200), rect, width=1, border_radius=12)

    title = get_font(20).render("东山再起：是否同意重开？", True, (40, 40, 40))
    screen.blit(title, (rect.centerx - title.get_width()//2, rect.top + 18))

    # 两个按钮（仅绘制；事件处理由 engine 简化为任意点击=拒绝）
    btn_w, btn_h = 120, 40
    gap = 20
    btn_yes = pygame.Rect(rect.centerx - gap//2 - btn_w, rect.bottom - 20 - btn_h, btn_w, btn_h)
    btn_no  = pygame.Rect(rect.centerx + gap//2,           rect.bottom - 20 - btn_h, btn_w, btn_h)

    _draw_button(screen, btn_yes, "同意")
    _draw_button(screen, btn_no, "拒绝")

# ------------------------------
# 内部：简易按钮绘制 & 降级版几何函数
# ------------------------------

def _draw_button(screen: pygame.Surface, rect: pygame.Rect, text: str) -> None:
    pygame.draw.rect(screen, (255, 255, 255), rect, border_radius=10)
    pygame.draw.rect(screen, (180, 180, 180), rect, width=1, border_radius=10)
    label = get_font(18).render(text, True, (40, 40, 40))
    screen.blit(label, (rect.centerx - label.get_width()//2, rect.centery - label.get_height()//2))


def _grid_to_px(i: int, j: int, config: Dict[str, Any]) -> Tuple[int, int]:
    margin = int(config["MARGIN"])
    cell = int(config["CELL_SIZE"])
    return margin + i * cell, margin + j * cell


def _board_rect(config: Dict[str, Any]) -> pygame.Rect:
    size = int(config["BOARD_SIZE"])
    margin = int(config["MARGIN"])
    cell = int(config["CELL_SIZE"])
    grid_w = cell * (size - 1)
    return pygame.Rect(margin, margin, grid_w, grid_w)


def _panel_rect(config: Dict[str, Any]) -> pygame.Rect:
    margin = int(config["MARGIN"])
    cell = int(config["CELL_SIZE"])
    size = int(config["BOARD_SIZE"])
    panel_w = int(config["PANEL_W"])
    grid_w = cell * (size - 1)
    win_h = int(config.get("WINDOW_H", margin * 2 + grid_w))
    left = margin * 2 + grid_w
    return pygame.Rect(left, 0, panel_w, win_h)
