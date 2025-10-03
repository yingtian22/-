"""
config.py — Skill Gomoku (技能五子棋)

职责：集中定义本项目可调参数与资源路径，提供 `get_config()` 返回统一的配置 dict。
- 资源路径（头像、技能图标）
- 棋盘/窗口尺寸
- 颜色与文案
- 状态/热键/技能 CD 与“力拔山兮”参数

注：若与 models/engine 的常量重复时，以运行时的模块导入优先；这里的常量仅用于配置装配。
"""
from __future__ import annotations
from typing import Dict, Any, Tuple
import os

# =====================
# 资源路径
# =====================
ASSET_DIR = "assets/"

AVATAR1_PATH = os.path.join(ASSET_DIR, "avatar_skillwu.png")  # 黑方“技能五”
AVATAR2_PATH = os.path.join(ASSET_DIR, "avatar_ziqi.png")    # 白方“子棋”

ICON_PATHS: Dict[int, str] = {
    1: os.path.join(ASSET_DIR, "icon_fly_sand.png"),      # 飞沙走石
    2: os.path.join(ASSET_DIR, "icon_still_water.png"),   # 静如止水
    3: os.path.join(ASSET_DIR, "icon_drip_stone.png"),    # 水滴石穿
    4: os.path.join(ASSET_DIR, "icon_mighty_power.png"),  # 力拔山兮
    5: os.path.join(ASSET_DIR, "icon_qinna.png"),         # 擒拿
    6: os.path.join(ASSET_DIR, "icon_comeback.png"),      # 东山再起
}

# =====================
# 棋盘 / 窗口
# =====================
BOARD_SIZE = 15
CELL_SIZE = 40
MARGIN = 60
PANEL_W = 300
FPS = 60
AVATAR_BAR_H = 64  # 顶部头像条高度

# =====================
# 颜色（RGBA）
# =====================
COLOR_BG = (222, 184, 135)     # 背景木色
COLOR_GRID = (90, 60, 30)      # 棋盘线
COLOR_BLACK = (20, 20, 20)     # 黑棋
COLOR_WHITE = (240, 240, 240)  # 白棋
COLOR_PANEL = (245, 236, 220)  # 面板底色
COLOR_ACCENT = (255, 204, 0)   # 强调高亮
COLOR_TEXT = (30, 30, 30)

# =====================
# 文案
# =====================
WINDOW_TITLE = "技能五子棋 | Skill Gomoku"
NAME_BLACK = "技能五"
NAME_WHITE = "子棋"

# =====================
# 状态机（保留以备扩展）
# =====================
STATE_MENU = 0
STATE_PLAYING = 1
STATE_GAMEOVER = 2

# =====================
# 技能与热键
# =====================
SKILL_IDS = {
    "FEISHA": 1,
    "JINGRU": 2,
    "SHUIDI": 3,
    "LIBA": 4,
    "QINNA": 5,
    "DSZQ": 6,
}

# 默认冷却（使用者自己的回合数）
CDS: Dict[int, int] = {1: 6, 2: 8, 3: 3, 4: 20, 5: 5, 6: 12}

# 力拔山兮参数
LIBA_MIN_MOVES = 20   # 前置：总落子≥20
LIBA_BASE = 0.10      # 基础成功率 10%
LIBA_CAP = 0.18       # 上限 18%

# 快捷键映射（仅作为声明；在 engine 中直接读 pygame 的 key 常量）
KEY_HINTS = {
    "skills": "1–6",
    "undo": "U",
    "reset": "R",
    "esc": "Esc",
}

# =====================
# 装配函数：返回完整配置 dict
# =====================

def _compute_window_size() -> Tuple[int, int]:
    board_px = MARGIN * 2 + CELL_SIZE * (BOARD_SIZE - 1)
    win_w = board_px + PANEL_W
    win_h = board_px
    return win_w, win_h


def get_config() -> Dict[str, Any]:
    win_w, win_h = _compute_window_size()
    return {
        # 路径
        "ASSET_DIR": ASSET_DIR,
        "AVATAR1_PATH": AVATAR1_PATH,
        "AVATAR2_PATH": AVATAR2_PATH,
        "ICON_PATHS": dict(ICON_PATHS),
        # 棋盘 & 窗口
        "BOARD_SIZE": BOARD_SIZE,
        "CELL_SIZE": CELL_SIZE,
        "MARGIN": MARGIN,
        "PANEL_W": PANEL_W,
        "FPS": FPS,
        "AVATAR_BAR_H": AVATAR_BAR_H,
        "WINDOW_W": win_w,
        "WINDOW_H": win_h,
        # 颜色
        "COLOR_BG": COLOR_BG,
        "COLOR_GRID": COLOR_GRID,
        "COLOR_BLACK": COLOR_BLACK,
        "COLOR_WHITE": COLOR_WHITE,
        "COLOR_PANEL": COLOR_PANEL,
        "COLOR_ACCENT": COLOR_ACCENT,
        "COLOR_TEXT": COLOR_TEXT,
        # 文案
        "WINDOW_TITLE": WINDOW_TITLE,
        "NAME_BLACK": NAME_BLACK,
        "NAME_WHITE": NAME_WHITE,
        # 状态
        "STATE_MENU": STATE_MENU,
        "STATE_PLAYING": STATE_PLAYING,
        "STATE_GAMEOVER": STATE_GAMEOVER,
        # 技能
        "CDS": dict(CDS),
        "LIBA_MIN_MOVES": LIBA_MIN_MOVES,
        "LIBA_BASE": LIBA_BASE,
        "LIBA_CAP": LIBA_CAP,
        # 快捷键信息（用于 UI 展示）
        "KEY_HINTS": dict(KEY_HINTS),
    }
