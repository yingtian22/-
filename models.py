"""
models.py — Skill Gomoku (技能五子棋)

数据结构与常量集中定义：
- PlayerState：玩家状态（冷却、冻结、擒拿、头像等）
- GameContext：对局上下文（棋盘、回合、历史、消息、技能 UI 状态等）
- 常量：状态机/阵营/技能 ID

与其他模块的耦合点：
- main.py 会优先使用这里的 PlayerState / GameContext 来构建 ctx
- engine.py / skills.py 直接读写 ctx 字段（保持字典风格也可用）

建议：尽量通过提供方法来修改状态，但为兼容现有调用，也保留对字段的直接访问。
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple
from collections import deque

# ------------------------------
# 常量（与 engine/skills/rules 对齐）
# ------------------------------
STATE_MENU = 0
STATE_PLAYING = 1
STATE_GAMEOVER = 2

SIDE_BLACK = 1
SIDE_WHITE = 2

SKILL_FEISHA = 1
SKILL_JINGRU = 2
SKILL_SHUIDI = 3
SKILL_LIBA = 4
SKILL_QINNA = 5
SKILL_DSZQ = 6

# ------------------------------
# 模型：玩家状态
# ------------------------------
@dataclass
class PlayerState:
    name: str
    cooldowns: Dict[int, int] = field(default_factory=dict)  # {skill_id: cd}
    frozen_once: bool = False
    qinna_stance: bool = False
    avatar_surface: Any | None = None  # pygame.Surface 或 None

    def reset_for_new_game(self, cds_template: Dict[int, int]) -> None:
        """清空临时状态并重置冷却。"""
        self.cooldowns = dict(cds_template)
        self.frozen_once = False
        self.qinna_stance = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # avatar_surface 不是可序列化对象，转为占位
        if d.get("avatar_surface") is not None:
            d["avatar_surface"] = "<Surface>"
        return d


# ------------------------------
# 模型：对局上下文
# ------------------------------
@dataclass
class GameContext:
    # 核心状态
    board: List[List[int]]
    turn_side: int = SIDE_BLACK
    move_history: List[Tuple[int, int, int]] = field(default_factory=list)  # (x,y,side)
    state: int = STATE_PLAYING
    winner: int = 0  # 0=无胜者, 1=黑, 2=白

    # 玩家
    players: Dict[int, PlayerState] = field(default_factory=dict)  # {SIDE_BLACK: PlayerState, SIDE_WHITE: PlayerState}

    # UI/技能/消息
    skill_ui_state: Dict[str, Any] = field(default_factory=dict)
    messages: List[str] = field(default_factory=list)  # UI 负责显示最近 3 条
    last_move_pos: Optional[Tuple[int, int]] = None

    # 外部资源/配置
    assets: Dict[str, Any] = field(default_factory=dict)
    config: Dict[str, Any] = field(default_factory=dict)

    # 运行时附加（可选）
    turn_stage: Optional[int] = None  # 由 engine 初始化为 BEGIN 常量

    # —— 基本方法 ——
    def reset(self) -> None:
        size = int(self.config.get("BOARD_SIZE", 15))
        self.board = [[0 for _ in range(size)] for _ in range(size)]
        self.move_history.clear()
        self.last_move_pos = None
        self.turn_side = SIDE_BLACK
        self.winner = 0
        self.state = STATE_PLAYING
        self.turn_stage = None
        # 重置玩家与 UI
        cds_template = self.config.get("CDS", {})
        for p in self.players.values():
            p.reset_for_new_game(cds_template)
        self.skill_ui_state.clear()
        self.log("已开始新对局。")

    def switch_turn(self) -> None:
        self.turn_side = SIDE_WHITE if self.turn_side == SIDE_BLACK else SIDE_BLACK
        self.turn_stage = None  # 由 engine 在下一帧置为 BEGIN

    def log(self, msg: str) -> None:
        self.messages.append(msg)

    # —— 数据导出 ——
    def to_dict(self) -> Dict[str, Any]:
        return {
            "board": [row[:] for row in self.board],
            "turn_side": self.turn_side,
            "move_history": self.move_history[:],
            "state": self.state,
            "winner": self.winner,
            "players": {k: v.to_dict() for k, v in self.players.items()},
            "skill_ui_state": dict(self.skill_ui_state),
            "messages": self.messages[:],
            "last_move_pos": tuple(self.last_move_pos) if self.last_move_pos else None,
            "assets": {k: str(type(v)) for k, v in self.assets.items()},
            "config": dict(self.config),
            "turn_stage": self.turn_stage,
        }


# ------------------------------
# 工厂：从 config/assets 快速构造上下文
# ------------------------------

def build_default_context(config: Dict[str, Any], assets: Dict[str, Any]) -> GameContext:
    size = int(config.get("BOARD_SIZE", 15))
    board = [[0 for _ in range(size)] for _ in range(size)]

    # 冷却模板
    cds_template = dict(config.get("CDS", {1: 6, 2: 8, 3: 3, 4: 20, 5: 5, 6: 12}))

    black = PlayerState(name=config.get("NAME_BLACK", "黑方"), cooldowns=dict(cds_template))
    white = PlayerState(name=config.get("NAME_WHITE", "白方"), cooldowns=dict(cds_template))

    # 可将头像 surface 挂到这里（由上层决定是否传入）
    if assets.get("AVATAR1") is not None:
        black.avatar_surface = assets.get("AVATAR1")
    if assets.get("AVATAR2") is not None:
        white.avatar_surface = assets.get("AVATAR2")

    ctx = GameContext(
        board=board,
        turn_side=SIDE_BLACK,
        move_history=[],
        state=STATE_PLAYING,
        players={SIDE_BLACK: black, SIDE_WHITE: white},
        messages=[],
        last_move_pos=None,
        winner=0,
        assets=assets,
        config=config,
        skill_ui_state={},
        turn_stage=None,
    )
    return ctx
