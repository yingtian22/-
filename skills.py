"""
skills.py — Skill Gomoku (技能五子棋)

改进版（兼容 dataclass GameContext 与 dict）：
- 统一访问器：ctx_get/ctx_set/ctx_setdefault + 玩家属性读写 p_get/p_set
- 完整实现六个技能与拦截/冷却/冻结窗口逻辑
- 与 rules 模块解耦，缺席时自动降级（仅返回基础概率）
"""
from __future__ import annotations
from typing import Any, Dict, Tuple, List, Optional, Union
import random

# 可选依赖（缺席时降级处理）
try:
    import rules  # type: ignore
except Exception:
    rules = None

# ------------------------------
# 常量（与 engine 对齐）
# ------------------------------
SKILL_FEISHA = 1
SKILL_JINGRU = 2
SKILL_SHUIDI = 3
SKILL_LIBA = 4
SKILL_QINNA = 5
SKILL_DSZQ = 6

SIDE_BLACK = 1
SIDE_WHITE = 2

Ctx = Union[Dict[str, Any], Any]  # 允许 dataclass

# ------------------------------
# 访问器：兼容 dict / dataclass 上下文 & 玩家
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
# 对外主入口
# ------------------------------

def can_cast(ctx: Ctx, skill_id: int) -> bool:
    side = ctx_get(ctx, "turn_side")
    p = get_player(ctx, side)
    cds = p_get(p, "cooldowns", {})
    if cds.get(skill_id, 0) > 0:
        return False

    sui = ctx_setdefault(ctx, "skill_ui_state", {})

    # 3 水滴石穿：仅在冻结窗口开启时可用
    if skill_id == SKILL_SHUIDI:
        return bool(sui.get("freeze_window_open"))

    # 4 力拔山兮：前置总落子 ≥ 20
    if skill_id == SKILL_LIBA:
        total_moves = len(ctx_get(ctx, "move_history") or [])
        if total_moves < ctx_cfg(ctx).get("LIBA_MIN_MOVES", 20):
            return False

    # 1 飞沙走石：需要有可选目标（任意敌方棋子）
    if skill_id == SKILL_FEISHA:
        return len(highlight_enemy_stones(ctx)) > 0

    return True


def try_cast(ctx: Ctx, skill_id: int) -> bool:
    if not can_cast(ctx, skill_id):
        push_message(ctx, "技能不可用或冷却中。")
        return False

    side = ctx_get(ctx, "turn_side")

    # 擒拿拦截（对手是否布有守势）
    if check_qinna_intercept(ctx, caster_side=side):
        set_cooldown(ctx, skill_id, ctx_cfg(ctx)["CDS"].get(skill_id, 1))
        push_message(ctx, "对手的擒拿发动：你的技能被拦截！")
        return False

    # 未被拦截 → 执行技能
    if skill_id == SKILL_FEISHA:
        cast_feisha(ctx)
    elif skill_id == SKILL_JINGRU:
        cast_jingru(ctx)
    elif skill_id == SKILL_SHUIDI:
        cast_shuidi(ctx)
    elif skill_id == SKILL_LIBA:
        cast_libashanxi(ctx)
    elif skill_id == SKILL_QINNA:
        cast_qinna(ctx)
    elif skill_id == SKILL_DSZQ:
        cast_dongshanzaoqi(ctx)
    else:
        return False

    # 入冷却（东山再起也在这里统一处理）
    set_cooldown(ctx, skill_id, ctx_cfg(ctx)["CDS"].get(skill_id, 1))
    return True


# ------------------------------
# 拦截：擒拿
# ------------------------------

def check_qinna_intercept(ctx: Ctx, caster_side: int) -> bool:
    opp = SIDE_WHITE if caster_side == SIDE_BLACK else SIDE_BLACK
    opp_state = get_player(ctx, opp)
    if p_get(opp_state, "qinna_stance"):
        p_set(opp_state, "qinna_stance", False)
        return True
    return False


def set_qinna_stance(ctx: Ctx) -> None:
    side = ctx_get(ctx, "turn_side")
    p = get_player(ctx, side)
    p_set(p, "qinna_stance", True)


def clear_qinna_stance(ctx: Ctx) -> None:
    side = ctx_get(ctx, "turn_side")
    p = get_player(ctx, side)
    p_set(p, "qinna_stance", False)


# ------------------------------
# 冷却 & 回合开始
# ------------------------------

def on_turn_begin_cooldowns(ctx: Ctx) -> None:
    """当前玩家所有技能 CD-1（不小于0）；清除自己上回合设置的擒拿守势。"""
    side = ctx_get(ctx, "turn_side")
    p = get_player(ctx, side)
    cds = p_get(p, "cooldowns", {})
    for k in list(cds.keys()):
        cds[k] = max(0, cds[k] - 1)
    p_set(p, "qinna_stance", False)


def set_cooldown(ctx: Ctx, skill_id: int, cd_val: int) -> None:
    side = ctx_get(ctx, "turn_side")
    p = get_player(ctx, side)
    cds = p_get(p, "cooldowns", {})
    cds[skill_id] = max(0, int(cd_val))
    p_set(p, "cooldowns", cds)


def consume_cooldown(ctx: Ctx, skill_id: int) -> None:
    side = ctx_get(ctx, "turn_side")
    p = get_player(ctx, side)
    cds = p_get(p, "cooldowns", {})
    cds[skill_id] = max(0, cds.get(skill_id, 0) - 1)
    p_set(p, "cooldowns", cds)


# ------------------------------
# 技能实现
# ------------------------------

def cast_feisha(ctx: Ctx) -> None:
    sui = ctx_setdefault(ctx, "skill_ui_state", {})
    if len(highlight_enemy_stones(ctx)) == 0:
        push_message(ctx, "飞沙走石：没有可选目标。")
        return
    sui["target_select_active"] = True
    push_message(ctx, "飞沙走石：请选择要移除的对方棋子。")


def cast_jingru(ctx: Ctx) -> None:
    mark_opponent_frozen_next_turn(ctx)
    push_message(ctx, "静如止水：对手下回合将被冻结。")


def cast_shuidi(ctx: Ctx) -> None:
    sui = ctx_setdefault(ctx, "skill_ui_state", {})
    if not sui.get("freeze_window_open"):
        push_message(ctx, "水滴石穿只能在被冻结回合开始时使用。")
        return
    clear_frozen_flag_if_consumed(ctx)
    sui["freeze_window_open"] = False
    push_message(ctx, "水滴石穿：已解除本次冻结，可正常落子。")


def cast_libashanxi(ctx: Ctx) -> None:
    total_moves = len(ctx_get(ctx, "move_history") or [])
    min_moves = ctx_cfg(ctx).get("LIBA_MIN_MOVES", 20)
    if total_moves < min_moves:
        push_message(ctx, f"力拔山兮前置未达成（总落子需 ≥ {min_moves}）。")
        return
    prob = compute_mighty_power_success(ctx)
    roll = random.random()
    if roll < prob:
        ctx_set(ctx, "winner", ctx_get(ctx, "turn_side"))
        ctx_set(ctx, "state", ctx_cfg(ctx).get("STATE_GAMEOVER"))
        push_message(ctx, f"力拔山兮成功！（成功率 {int(prob*100)}%）")
    else:
        push_message(ctx, f"力拔山兮未能成功（成功率 {int(prob*100)}%）。")


def cast_qinna(ctx: Ctx) -> None:
    set_qinna_stance(ctx)
    push_message(ctx, "擒拿：已架势，准备拦截对手下回合的首次技能。")


def cast_dongshanzaoqi(ctx: Ctx) -> None:
    sui = ctx_setdefault(ctx, "skill_ui_state", {})
    sui["rematch_dialog_open"] = True
    sui["rematch_request_from"] = ctx_get(ctx, "turn_side")
    push_message(ctx, "东山再起：已向对手发起重开请求。")


# ------------------------------
# 帮助函数：冻结、目标集、成功率
# ------------------------------

def mark_opponent_frozen_next_turn(ctx: Ctx) -> None:
    opp = SIDE_WHITE if ctx_get(ctx, "turn_side") == SIDE_BLACK else SIDE_BLACK
    p = get_player(ctx, opp)
    p_set(p, "frozen_once", True)


def clear_frozen_flag_if_consumed(ctx: Ctx) -> None:
    side = ctx_get(ctx, "turn_side")
    p = get_player(ctx, side)
    p_set(p, "frozen_once", False)


def highlight_enemy_stones(ctx: Ctx) -> List[Tuple[int, int]]:
    board = ctx_get(ctx, "board")
    size = ctx_cfg(ctx)["BOARD_SIZE"]
    me = ctx_get(ctx, "turn_side")
    enemy = SIDE_WHITE if me == SIDE_BLACK else SIDE_BLACK
    res: List[Tuple[int, int]] = []
    for y in range(size):
        for x in range(size):
            if board[y][x] == enemy:
                res.append((x, y))
    return res


def compute_mighty_power_success(ctx: Ctx) -> float:
    base = ctx_cfg(ctx).get("LIBA_BASE", 0.10)
    cap = ctx_cfg(ctx).get("LIBA_CAP", 0.18)
    bonus = 0.0
    if rules and hasattr(rules, "count_open_threes_fours"):
        try:
            me = ctx_get(ctx, "turn_side")
            stats = rules.count_open_threes_fours(ctx_get(ctx, "board"), me)  # type: ignore
            open_three = int(stats.get("open_three", 0))
            open_four = int(stats.get("open_four", 0))
            bonus = 0.02 * open_three + 0.03 * open_four
        except Exception:
            bonus = 0.0
    return max(0.0, min(cap, base + bonus))


# ------------------------------
# 消息工具
# ------------------------------

def push_message(ctx: Ctx, text: str) -> None:
    msgs = ctx_setdefault(ctx, "messages", [])
    msgs.append(text)
