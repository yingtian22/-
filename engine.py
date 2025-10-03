"""
engine.py — Skill Gomoku (技能五子棋)

改进版 v3：
- 同时兼容 dict 上下文与 models.GameContext（dataclass）
- 新增玩家访问器 get_player / p_get / p_set，修复 PlayerState 无 .get/.[] 的错误
- 接入 UI 技能按钮点击触发
- 放宽：在 TURN_STAGE_PLACE 且“尚未在本回合落子”时也允许释放技能（落子前）
- 完整的回合阶段：BEGIN → SKILL → PLACE → POST
"""
from __future__ import annotations
from typing import Any, Dict, Optional, Tuple, List, Union

import pygame

# 可选业务模块
try:
    import skills  # type: ignore
except Exception:
    skills = None

try:
    import rules  # type: ignore
except Exception:
    rules = None

try:
    import utils  # type: ignore
except Exception:
    utils = None

try:
    import ui  # type: ignore
except Exception:
    ui = None

# ------------------------------
# 常量
# ------------------------------
SKILL_FEISHA = 1
SKILL_JINGRU = 2
SKILL_SHUIDI = 3
SKILL_LIBA = 4
SKILL_QINNA = 5
SKILL_DSZQ = 6

SIDE_BLACK = 1
SIDE_WHITE = 2

TURN_STAGE_BEGIN = 0
TURN_STAGE_SKILL = 1
TURN_STAGE_PLACE = 2
TURN_STAGE_POST = 3

Ctx = Union[Dict[str, Any], Any]  # 允许 dataclass

# ------------------------------
# 兼容访问器（支持 dict 与 dataclass）
# ------------------------------

def ctx_get(ctx: Ctx, key: str, default=None):
    if isinstance(ctx, dict):
        return ctx.get(key, default)
    return getattr(ctx, key, default)


def ctx_set(ctx: Ctx, key: str, value: Any) -> None:
    if isinstance(ctx, dict):
        ctx[key] = value
    else:
        setattr(ctx, key, value)


def ctx_setdefault(ctx: Ctx, key: str, default):
    cur = ctx_get(ctx, key, None)
    if cur is None:
        ctx_set(ctx, key, default)
        return default
    return cur


def ctx_cfg(ctx: Ctx) -> Dict[str, Any]:
    return ctx_get(ctx, "config", {})

# —— 玩家访问器 ——

def get_player(ctx: Ctx, side: int) -> Any:
    players = ctx_get(ctx, "players")
    return players[side]


def p_get(p: Any, name: str, default=None):
    if isinstance(p, dict):
        return p.get(name, default)
    return getattr(p, name, default)


def p_set(p: Any, name: str, value: Any) -> None:
    if isinstance(p, dict):
        p[name] = value
    else:
        setattr(p, name, value)


# ------------------------------
# 对外 API（main 调用）
# ------------------------------

def route_event(ctx: Ctx, event: pygame.event.Event) -> None:
    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        pos = event.pos
        handle_mouse_on_board(ctx, pos)
        handle_mouse_on_panel(ctx, pos)
    elif event.type == pygame.KEYDOWN:
        handle_keydown(ctx, event.key)


def update(ctx: Ctx) -> None:
    if ctx_get(ctx, "state") != ctx_cfg(ctx).get("STATE_PLAYING"):
        return

    if ctx_get(ctx, "turn_stage") is None:
        ctx_set(ctx, "turn_stage", TURN_STAGE_BEGIN)

    stage = ctx_get(ctx, "turn_stage")
    if stage == TURN_STAGE_BEGIN:
        maybe_start_turn(ctx)
        return
    if stage == TURN_STAGE_SKILL:
        handle_freeze_reaction_window(ctx)
        handle_skill_phase(ctx)
        return
    if stage == TURN_STAGE_PLACE:
        handle_place_phase(ctx)
        return
    if stage == TURN_STAGE_POST:
        post_move_judgement(ctx)
        return


# ------------------------------
# 事件细分
# ------------------------------

def handle_mouse_on_board(ctx: Ctx, pos: Tuple[int, int]) -> None:
    sui = ctx_setdefault(ctx, "skill_ui_state", {})

    # 重开对话框：此处简化为任意点击=拒绝
    if sui.get("rematch_dialog_open"):
        handle_rematch_response(ctx, agree=False)
        return

    # 冻结窗口：点击任意位置 = 跳过回合
    if sui.get("freeze_window_open"):
        consume_freeze_skip_turn(ctx)
        return

    # 目标选择（飞沙走石）
    if sui.get("target_select_active"):
        grid = px_to_grid(ctx, pos)
        if grid is not None:
            confirm_remove_target(ctx, grid)
        return

    # 正常落子
    if ctx_get(ctx, "turn_stage") == TURN_STAGE_PLACE:
        grid = px_to_grid(ctx, pos)
        if grid is None:
            return
        if try_place_stone(ctx, grid):
            ctx_set(ctx, "turn_stage", TURN_STAGE_POST)


def handle_mouse_on_panel(ctx: Ctx, pos: Tuple[int, int]) -> None:
    """允许在 SKILL 阶段直接放；或在 PLACE 阶段且本回合尚未落子时放。
       冻结窗口开启时允许 3 号（水滴石穿）。"""
    if ui is None or not hasattr(ui, "is_point_in_skill_button"):
        return
    sid = ui.is_point_in_skill_button(pos, ctx_cfg(ctx))
    if not sid:
        return

    stage = ctx_get(ctx, "turn_stage")
    sui = ctx_setdefault(ctx, "skill_ui_state", {})

    # 是否尚未在本回合落子：历史为空，或最后一手不是当前方
    hist = ctx_get(ctx, "move_history") or []
    cur_side = ctx_get(ctx, "turn_side")
    not_moved_this_turn = (not hist) or (hist[-1][2] != cur_side)

    # 技能阶段直接放；冻结窗口允许3；或在PLACE阶段但还没落子也允许放
    if stage == TURN_STAGE_SKILL or (stage == TURN_STAGE_PLACE and not_moved_this_turn):
        try_cast_skill(ctx, sid)
    elif sid == SKILL_SHUIDI and sui.get("freeze_window_open"):
        try_cast_skill(ctx, sid)


def handle_keydown(ctx: Ctx, key: int) -> None:
    key_to_skill = {
        pygame.K_1: SKILL_FEISHA,
        pygame.K_2: SKILL_JINGRU,
        pygame.K_3: SKILL_SHUIDI,
        pygame.K_4: SKILL_LIBA,
        pygame.K_5: SKILL_QINNA,
        pygame.K_6: SKILL_DSZQ,
    }
    if key in key_to_skill:
        stage = ctx_get(ctx, "turn_stage")
        sui = ctx_setdefault(ctx, "skill_ui_state", {})
        # 是否尚未落子（用于 PLACE 阶段）
        hist = ctx_get(ctx, "move_history") or []
        cur_side = ctx_get(ctx, "turn_side")
        not_moved_this_turn = (not hist) or (hist[-1][2] != cur_side)

        if stage == TURN_STAGE_SKILL or (stage == TURN_STAGE_PLACE and not_moved_this_turn):
            try_cast_skill(ctx, key_to_skill[key])
        elif key == pygame.K_3 and sui.get("freeze_window_open"):
            try_cast_skill(ctx, SKILL_SHUIDI)
        return

    # U/Z 悔棋
    if key in (pygame.K_u, pygame.K_z):
        undo_last_move(ctx)
        return
    # R 重开
    if key == pygame.K_r:
        reset_game(ctx)
        return


# ------------------------------
# 回合与阶段
# ------------------------------

def maybe_start_turn(ctx: Ctx) -> None:
    if ctx_get(ctx, "turn_stage") != TURN_STAGE_BEGIN:
        return

    sui = ctx_setdefault(ctx, "skill_ui_state", {})

    # 冷却与擒拿清理
    if skills and hasattr(skills, "on_turn_begin_cooldowns"):
        skills.on_turn_begin_cooldowns(ctx)
    else:
        side = ctx_get(ctx, "turn_side")
        p = get_player(ctx, side)
        cds = p_get(p, "cooldowns", {})
        for k in list(cds.keys()):
            cds[k] = max(0, cds[k] - 1)
        p_set(p, "cooldowns", cds)
        p_set(p, "qinna_stance", False)

    # 冻结检查
    side = ctx_get(ctx, "turn_side")
    p = get_player(ctx, side)
    sui["freeze_window_open"] = bool(p_get(p, "frozen_once", False))

    # 关闭其余窗口
    sui["rematch_dialog_open"] = False
    sui.setdefault("target_select_active", False)

    ctx_set(ctx, "turn_stage", TURN_STAGE_SKILL)


def handle_freeze_reaction_window(ctx: Ctx) -> None:
    return


def handle_skill_phase(ctx: Ctx) -> None:
    sui = ctx_setdefault(ctx, "skill_ui_state", {})
    if sui.get("freeze_window_open"):
        return
    if not sui.get("target_select_active") and not sui.get("rematch_dialog_open"):
        ctx_set(ctx, "turn_stage", TURN_STAGE_PLACE)


def handle_place_phase(ctx: Ctx) -> None:
    return


def post_move_judgement(ctx: Ctx) -> None:
    last = ctx_get(ctx, "last_move_pos")
    board = ctx_get(ctx, "board")
    win = False
    draw = False

    if rules and hasattr(rules, "check_five") and last is not None:
        try:
            win = rules.check_five(board, last)  # type: ignore
        except Exception:
            win = False
    if not win and (rules and hasattr(rules, "is_draw")):
        try:
            draw = rules.is_draw(board)  # type: ignore
        except Exception:
            draw = False

    if win:
        ctx_set(ctx, "winner", ctx_get(ctx, "turn_side"))
        push_message(ctx, f"{current_player_name(ctx)} 胜利！")
        ctx_set(ctx, "state", ctx_cfg(ctx).get("STATE_GAMEOVER"))
        return

    if draw:
        ctx_set(ctx, "winner", 0)
        push_message(ctx, "平局！")
        ctx_set(ctx, "state", ctx_cfg(ctx).get("STATE_GAMEOVER"))
        return

    maybe_switch_turn(ctx)


def maybe_switch_turn(ctx: Ctx) -> None:
    side = ctx_get(ctx, "turn_side")
    ctx_set(ctx, "turn_side", SIDE_WHITE if side == SIDE_BLACK else SIDE_BLACK)
    ctx_set(ctx, "turn_stage", TURN_STAGE_BEGIN)


# ------------------------------
# 通用操作
# ------------------------------

def try_place_stone(ctx: Ctx, grid_pos: Tuple[int, int]) -> bool:
    x, y = grid_pos
    board = ctx_get(ctx, "board")
    size = ctx_cfg(ctx)["BOARD_SIZE"]
    if not (0 <= x < size and 0 <= y < size):
        return False
    if board[y][x] != 0:
        return False

    side = ctx_get(ctx, "turn_side")
    board[y][x] = side
    ctx_set(ctx, "last_move_pos", (x, y))
    hist = ctx_setdefault(ctx, "move_history", [])
    hist.append((x, y, side))
    return True


def undo_last_move(ctx: Ctx) -> bool:
    hist = ctx_get(ctx, "move_history") or []
    if not hist:
        return False
    x, y, _side = hist.pop()
    board = ctx_get(ctx, "board")
    board[y][x] = 0
    ctx_set(ctx, "last_move_pos", hist[-1][:2] if hist else None)
    push_message(ctx, "已悔棋一步。")
    return True


def reset_game(ctx: Ctx) -> None:
    size = ctx_cfg(ctx)["BOARD_SIZE"]
    ctx_set(ctx, "board", [[0 for _ in range(size)] for _ in range(size)])
    ctx_set(ctx, "move_history", [])
    ctx_set(ctx, "last_move_pos", None)
    ctx_set(ctx, "turn_side", SIDE_BLACK)
    ctx_set(ctx, "winner", 0)
    ctx_set(ctx, "state", ctx_cfg(ctx)["STATE_PLAYING"])
    ctx_set(ctx, "turn_stage", TURN_STAGE_BEGIN)

    players = ctx_get(ctx, "players")
    cds_template = ctx_cfg(ctx)["CDS"]
    for s in (SIDE_BLACK, SIDE_WHITE):
        p = players[s]
        p_set(p, "frozen_once", False)
        p_set(p, "qinna_stance", False)
        p_set(p, "cooldowns", dict(cds_template))

    sui = ctx_setdefault(ctx, "skill_ui_state", {})
    sui.clear()
    push_message(ctx, "已开始新对局。")


def push_message(ctx: Ctx, text: str) -> None:
    msgs = ctx_setdefault(ctx, "messages", [])
    msgs.append(text)


# ------------------------------
# 技能交互 & 冻结/重开
# ------------------------------

def try_cast_skill(ctx: Ctx, skill_id: int) -> bool:
    if skills and hasattr(skills, "try_cast"):
        try:
            ok = skills.try_cast(ctx, skill_id)  # type: ignore
        except Exception:
            ok = False
        return ok

    # 降级占位
    side = ctx_get(ctx, "turn_side")
    p = get_player(ctx, side)
    cds = p_get(p, "cooldowns", {})
    cd = cds.get(skill_id, 0)
    if cd == 0:
        cds[skill_id] = 1
        p_set(p, "cooldowns", cds)
        push_message(ctx, f"已发动技能 #{skill_id}（占位）。")
        return True
    else:
        push_message(ctx, f"技能 #{skill_id} 冷却中（{cd}）。")
        return False


def confirm_remove_target(ctx: Ctx, grid_pos: Tuple[int, int]) -> bool:
    sui = ctx_setdefault(ctx, "skill_ui_state", {})
    if not sui.get("target_select_active"):
        return False
    x, y = grid_pos
    if not inside_board_ctx(ctx, x, y):
        return False
    enemy = SIDE_WHITE if ctx_get(ctx, "turn_side") == SIDE_BLACK else SIDE_BLACK
    board = ctx_get(ctx, "board")
    if board[y][x] != enemy:
        return False
    board[y][x] = 0
    hist = ctx_get(ctx, "move_history") or []
    for i in range(len(hist) - 1, -1, -1):
        hx, hy, hs = hist[i]
        if (hx, hy, hs) == (x, y, enemy):
            hist.pop(i)
            break
    sui["target_select_active"] = False
    push_message(ctx, "飞沙走石：已移除对方一枚棋子。")
    return True


def consume_freeze_skip_turn(ctx: Ctx) -> None:
    sui = ctx_setdefault(ctx, "skill_ui_state", {})
    if not sui.get("freeze_window_open"):
        return
    side = ctx_get(ctx, "turn_side")
    p = get_player(ctx, side)
    p_set(p, "frozen_once", False)
    sui["freeze_window_open"] = False
    push_message(ctx, "被冻结：已跳过本回合。")
    maybe_switch_turn(ctx)


def handle_rematch_response(ctx: Ctx, agree: bool) -> None:
    sui = ctx_setdefault(ctx, "skill_ui_state", {})
    if not sui.get("rematch_dialog_open"):
        return
    sui["rematch_dialog_open"] = False
    if agree:
        reset_game(ctx)
    else:
        push_message(ctx, "对方拒绝了重开请求。")


# ------------------------------
# 工具：坐标换算
# ------------------------------

def px_to_grid(ctx: Ctx, pos: Tuple[int, int]) -> Optional[Tuple[int, int]]:
    if utils and hasattr(utils, "px_to_grid"):
        try:
            return utils.px_to_grid(pos[0], pos[1], ctx_cfg(ctx))  # type: ignore
        except Exception:
            pass
    x, y = pos
    cfg = ctx_cfg(ctx)
    margin = cfg["MARGIN"]
    cell = cfg["CELL_SIZE"]
    size = cfg["BOARD_SIZE"]
    left = margin
    top = margin
    grid_w = cell * (size - 1)
    if not (left - cell//2 <= x <= left + grid_w + cell//2 and top - cell//2 <= y <= top + grid_w + cell//2):
        return None
    gx = int(round((x - left) / cell))
    gy = int(round((y - top) / cell))
    if 0 <= gx < size and 0 <= gy < size:
        return (gx, gy)
    return None


def inside_board_ctx(ctx: Ctx, x: int, y: int) -> bool:
    size = ctx_cfg(ctx)["BOARD_SIZE"]
    return 0 <= x < size and 0 <= y < size


# ------------------------------
# 提供给 UI 的小工具
# ------------------------------

def current_player_name(ctx: Ctx) -> str:
    side = ctx_get(ctx, "turn_side")
    p = get_player(ctx, side)
    name = p_get(p, "name", None)
    return name or "玩家"
