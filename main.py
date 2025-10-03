"""
main.py — Skill Gomoku (技能五子棋)

职责：
- 初始化窗口与资源
- 构造 GameContext
- 主循环：事件收集 → 事件路由(engine) → 状态推进(engine.update) → 渲染(ui.render)
- 降级策略：若 engine/ui/models 未就绪，提供最小可运行占位以便逐步联调

依赖：pygame（请先 pip install pygame）
"""
from __future__ import annotations
import os
import sys
from typing import Dict, Any, List, Optional, Tuple

# ---- 第三方 ----
try:
    import pygame
except Exception as e:  # pragma: no cover
    raise SystemExit("需要安装 pygame：pip install pygame") from e

# ---- 业务模块（允许缺席，便于分步实现） ----
try:
    import engine  # type: ignore
except Exception:
    engine = None  # 占位

try:
    import ui  # type: ignore
except Exception:
    ui = None  # 占位

try:
    import models  # type: ignore
except Exception:
    models = None  # 占位


# =====================
# Config & 常量装载
# =====================

def load_config() -> Dict[str, Any]:
    """集中管理本局所需的常量配置。
    注：正式实现中可迁移到 config.py；这里先内联，确保 main.py 可独立运行。
    """
    # 资源路径
    ASSET_DIR = "assets/"
    cfg: Dict[str, Any] = {
        # 路径
        "ASSET_DIR": ASSET_DIR,
        "AVATAR1_PATH": os.path.join(ASSET_DIR, "avatar_skillwu.png"),  # 黑方“技能五”
        "AVATAR2_PATH": os.path.join(ASSET_DIR, "avatar_ziqi.png"),     # 白方“子棋”
        # 图标
        "ICON_PATHS": {
            1: os.path.join(ASSET_DIR, "icon_fly_sand.png"),      # 飞沙走石
            2: os.path.join(ASSET_DIR, "icon_still_water.png"),   # 静如止水
            3: os.path.join(ASSET_DIR, "icon_drip_stone.png"),    # 水滴石穿
            4: os.path.join(ASSET_DIR, "icon_mighty_power.png"),  # 力拔山兮
            5: os.path.join(ASSET_DIR, "icon_qinna.png"),         # 擒拿
            6: os.path.join(ASSET_DIR, "icon_comeback.png"),      # 东山再起
        },
        # 棋盘 & 窗口
        "BOARD_SIZE": 15,
        "CELL_SIZE": 40,
        "MARGIN": 60,
        "PANEL_W": 300,
        "FPS": 60,
        # 颜色（RGBA）
        "COLOR_BG": (222, 184, 135),       # 背景木色
        "COLOR_GRID": (90, 60, 30),        # 棋盘线
        "COLOR_BLACK": (20, 20, 20),       # 黑棋
        "COLOR_WHITE": (240, 240, 240),    # 白棋
        "COLOR_PANEL": (245, 236, 220),    # 右侧面板底色
        "COLOR_ACCENT": (255, 204, 0),     # 强调色（高亮）
        "COLOR_TEXT": (30, 30, 30),
        # 文案
        "WINDOW_TITLE": "技能五子棋 | Skill Gomoku",
        "NAME_BLACK": "技能五",
        "NAME_WHITE": "子棋",
        # 状态常量（占位，models 若未提供）
        "STATE_PLAYING": 1,
        "STATE_MENU": 0,
        "STATE_GAMEOVER": 2,
        # 技能 CD
        "CDS": {1: 6, 2: 8, 3: 3, 4: 20, 5: 5, 6: 12},
        # 力拔山兮参数
        "LIBA_MIN_MOVES": 20,
        "LIBA_BASE": 0.10,
        "LIBA_CAP": 0.18,
        # 顶部头像条高度（覆盖棋盘上方区域视觉留白）
        "AVATAR_BAR_H": 64,
    }
    # 计算窗口尺寸
    board_px = cfg["MARGIN"] * 2 + cfg["CELL_SIZE"] * (cfg["BOARD_SIZE"] - 1)
    win_w = board_px + cfg["PANEL_W"]
    win_h = board_px
    cfg["WINDOW_W"], cfg["WINDOW_H"] = win_w, win_h
    return cfg


# =====================
# 初始化 & 资源加载
# =====================

def init_pygame() -> Tuple[pygame.Surface, pygame.time.Clock]:
    pygame.init()
    pygame.display.set_allow_screensaver(True)
    cfg = load_config()  # 局部生成用于窗口尺寸
    screen = pygame.display.set_mode((cfg["WINDOW_W"], cfg["WINDOW_H"]))
    pygame.display.set_caption(cfg["WINDOW_TITLE"])
    clock = pygame.time.Clock()
    return screen, clock


def file_exists(path: str) -> bool:
    return os.path.exists(path) and os.path.isfile(path)


def load_image_or_none(path: str) -> Optional[pygame.Surface]:
    if not file_exists(path):
        return None
    try:
        img = pygame.image.load(path).convert_alpha()
        return img
    except Exception:
        return None


def circle_crop(surface: pygame.Surface, diameter: int) -> pygame.Surface:
    """圆形裁剪：用于头像显示（缺省降级为原图缩放）。"""
    if surface is None:
        # 返回透明占位
        return pygame.Surface((diameter, diameter), pygame.SRCALPHA)
    surf = pygame.transform.smoothscale(surface, (diameter, diameter))
    mask = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
    pygame.draw.circle(mask, (255, 255, 255, 255), (diameter // 2, diameter // 2), diameter // 2)
    out = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
    out.blit(surf, (0, 0))
    out.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return out


def load_assets(config: Dict[str, Any]) -> Dict[str, Any]:
    """加载头像与技能图标；缺失资源以 None 占位，由 UI 决定占位绘制。"""
    assets: Dict[str, Any] = {}
    # 头像
    av1 = load_image_or_none(config["AVATAR1_PATH"])  # 黑方
    av2 = load_image_or_none(config["AVATAR2_PATH"])  # 白方
    # 预裁剪（圆形）
    diameter = config.get("AVATAR_BAR_H", 64)
    assets["AVATAR1"] = circle_crop(av1, diameter)
    assets["AVATAR2"] = circle_crop(av2, diameter)

    # 技能图标
    icon_paths = config["ICON_PATHS"]
    icons: Dict[int, Optional[pygame.Surface]] = {}
    for sid, p in icon_paths.items():
        icons[sid] = load_image_or_none(p)
    assets["ICONS"] = icons
    return assets


# =====================
# 上下文构建
# =====================

def create_game_context(config: Dict[str, Any], assets: Dict[str, Any]):
    """构建 GameContext。若 models 模块已就绪，则按其类型实例化；否则提供简易占位。"""
    board_size = config["BOARD_SIZE"]
    # 基本棋盘数据
    board = [[0 for _ in range(board_size)] for _ in range(board_size)]

    if models and hasattr(models, "GameContext") and hasattr(models, "PlayerState"):
        # 使用正式模型
        black = models.PlayerState(name=config["NAME_BLACK"], cooldowns=dict(config["CDS"]))
        white = models.PlayerState(name=config["NAME_WHITE"], cooldowns=dict(config["CDS"]))
        ctx = models.GameContext(
            board=board,
            turn_side=1,  # 1=黑, 2=白（建议在 models 里定义 SIDE_* 常量；此处先用数字）
            move_history=[],
            state=config["STATE_PLAYING"],
            players={1: black, 2: white},
            messages=[],
            last_move_pos=None,
            winner=0,
            assets=assets,
            config=config,
            skill_ui_state={},
        )
        return ctx

    # 占位上下文（dict 版本），仅用于渲染空棋盘与退出键
    ctx: Dict[str, Any] = {
        "board": board,
        "turn_side": 1,
        "move_history": [],
        "state": config["STATE_PLAYING"],
        "players": {
            1: {
                "name": config["NAME_BLACK"],
                "cooldowns": dict(config["CDS"]),
                "frozen_once": False,
                "qinna_stance": False,
            },
            2: {
                "name": config["NAME_WHITE"],
                "cooldowns": dict(config["CDS"]),
                "frozen_once": False,
                "qinna_stance": False,
            },
        },
        "messages": [],
        "last_move_pos": None,
        "winner": 0,
        "assets": assets,
        "config": config,
        "skill_ui_state": {},
    }
    return ctx


# =====================
# 事件与主循环
# =====================

def poll_events() -> List[pygame.event.Event]:
    return list(pygame.event.get())


def tick_fps(clock: pygame.time.Clock, config: Dict[str, Any]) -> None:
    clock.tick(config["FPS"])


def _fallback_draw_when_ui_missing(screen: pygame.Surface, ctx: Dict[str, Any], config: Dict[str, Any]):
    """在 ui 模块尚未就绪时，绘制最小可视内容（木色背景 + 基本网格）。"""
    screen.fill(config["COLOR_BG"])  # 背景
    # 棋盘网格（15x15 交点 → 14 格）
    size, gap, margin = config["BOARD_SIZE"], config["CELL_SIZE"], config["MARGIN"]
    grid_w = gap * (size - 1)
    left = margin
    top = margin
    # 边框
    rect_outer = pygame.Rect(left, top, grid_w, grid_w)
    pygame.draw.rect(screen, config["COLOR_GRID"], rect_outer, width=3)
    # 网格线
    for i in range(size):
        y = top + i * gap
        x = left + i * gap
        pygame.draw.line(screen, config["COLOR_GRID"], (left, y), (left + grid_w, y), width=1)
        pygame.draw.line(screen, config["COLOR_GRID"], (x, top), (x, top + grid_w), width=1)
    # 星位与天元
    star_idx = [3, 7, 11]
    r = 4
    for i in star_idx:
        for j in star_idx:
            cx = left + j * gap
            cy = top + i * gap
            pygame.draw.circle(screen, config["COLOR_GRID"], (cx, cy), r)
    # 简单标题
    font = pygame.font.SysFont(None, 24)
    txt = font.render("UI 模块未就绪：显示占位棋盘", True, config["COLOR_GRID"])
    screen.blit(txt, (left, max(0, top - 30)))


def game_loop(ctx, config: Dict[str, Any], assets: Dict[str, Any], screen: pygame.Surface, clock: pygame.time.Clock) -> None:
    running = True
    while running:
        for event in poll_events():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                # 约定：Esc 重置/返回；此处先实现为退出，后续在 engine 中完善
                running = False
            # 交给引擎路由（若已就绪）
            if engine and hasattr(engine, "route_event"):
                engine.route_event(ctx, event)

        # 帧推进（状态机）
        if engine and hasattr(engine, "update"):
            engine.update(ctx)

        # 渲染
        if ui and hasattr(ui, "render"):
            ui.render(ctx, config, assets, screen)
        else:
            _fallback_draw_when_ui_missing(screen, ctx, config)

        pygame.display.flip()
        tick_fps(clock, config)

    pygame.quit()


# =====================
# 入口
# =====================

def main() -> None:
    screen, clock = init_pygame()
    config = load_config()
    assets = load_assets(config)
    ctx = create_game_context(config, assets)
    game_loop(ctx, config, assets, screen, clock)


if __name__ == "__main__":
    main()
