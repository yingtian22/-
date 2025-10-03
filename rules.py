"""
rules.py — Skill Gomoku (技能五子棋)

提供：
- check_five(board, last_pos)  五连判定
- is_draw(board)               平局（棋盘无空位）
- count_open_threes_fours(board, side)  统计活三/活四（用于“力拔山兮”）
- inside_board(x, y)
- is_empty(board, x, y)

说明：
- board 使用 2D 列表，0=空，1=黑，2=白。
- 方向向量：水平、垂直、两条对角线。
- 活四：行文本中出现模式 ".XXXX."（两端都空）。
- 活三：行文本中出现 ".XXX." 或 ".XX.X." 或 ".X.XX."（开放三，包括跳三）。
  为简化实现，采取基于正则的行扫描。可能存在少量重叠计数，不影响“力拔山兮”的小幅加成用途。
"""
from __future__ import annotations
from typing import List, Tuple, Dict
import re

EMPTY = 0
BLACK = 1
WHITE = 2

# ------------------------------
# 基础工具
# ------------------------------

def inside_board(x: int, y: int, size: int | None = None, board: List[List[int]] | None = None) -> bool:
    if board is not None:
        size = len(board)
    assert size is not None
    return 0 <= x < size and 0 <= y < size


def is_empty(board: List[List[int]], x: int, y: int) -> bool:
    if not inside_board(x, y, board=board):
        return False
    return board[y][x] == EMPTY


# ------------------------------
# 五连 & 平局
# ------------------------------

def check_five(board: List[List[int]], last_pos: Tuple[int, int]) -> bool:
    """从最后一步开始向四个方向统计连续相同棋子数，是否≥5。允许长连。"""
    if last_pos is None:
        return False
    x, y = last_pos
    side = board[y][x]
    if side not in (BLACK, WHITE):
        return False

    dirs = [(1, 0), (0, 1), (1, 1), (1, -1)]
    size = len(board)

    def count_dir(dx: int, dy: int) -> int:
        c = 1
        # 正向
        i, j = x + dx, y + dy
        while 0 <= i < size and 0 <= j < size and board[j][i] == side:
            c += 1
            i += dx
            j += dy
        # 反向
        i, j = x - dx, y - dy
        while 0 <= i < size and 0 <= j < size and board[j][i] == side:
            c += 1
            i -= dx
            j -= dy
        return c

    for dx, dy in dirs:
        if count_dir(dx, dy) >= 5:
            return True
    return False


def is_draw(board: List[List[int]]) -> bool:
    for row in board:
        for v in row:
            if v == EMPTY:
                return False
    return True


# ------------------------------
# 活三 / 活四 统计
# ------------------------------

def count_open_threes_fours(board: List[List[int]], side: int) -> Dict[str, int]:
    """返回 {'open_three': n1, 'open_four': n2}

    简化实现（基于行字符串与正则）：
    - 将棋盘映射为字符：side → 'X'，对手 → 'O'，空 → '.'
    - 分别扫描行、列、两条对角线；将每条线转换为字符串，统计模式出现次数。
    - 使用重叠匹配（lookahead）计数，避免遗漏相邻模式。
    注意：为避免跨行误判，按线逐条统计；可能存在少量重叠计数。
    """
    assert side in (BLACK, WHITE)
    size = len(board)
    enemy = BLACK if side == WHITE else WHITE

    def cell_to_char(v: int) -> str:
        if v == side:
            return 'X'
        if v == enemy:
            return 'O'
        return '.'

    lines: List[str] = []

    # 行
    for y in range(size):
        s = ''.join(cell_to_char(board[y][x]) for x in range(size))
        lines.append(s)
    # 列
    for x in range(size):
        s = ''.join(cell_to_char(board[y][x]) for y in range(size))
        lines.append(s)
    # 主对角线（左上→右下）
    for k in range(-(size - 5), size - 4):  # 保证至少有5长的对角线被覆盖
        seg = []
        for y in range(size):
            x = y - k
            if 0 <= x < size:
                seg.append(cell_to_char(board[y][x]))
        if len(seg) >= 5:
            lines.append(''.join(seg))
    # 反对角线（右上→左下）
    for k in range(4, size + size - 5):  # y + x = k
        seg = []
        for y in range(size):
            x = k - y
            if 0 <= x < size:
                seg.append(cell_to_char(board[y][x]))
        if len(seg) >= 5:
            lines.append(''.join(seg))

    # 正则模式
    # 活四：.XXXX.  （两端开放）
    pat_open_four = re.compile(r"(?=\.XXXX\.)")
    # 活三：.XXX. 或 .XX.X. 或 .X.XX.
    pat_open_three_1 = re.compile(r"(?=\.XXX\.)")
    pat_open_three_2 = re.compile(r"(?=\.XX\.X\.)")
    pat_open_three_3 = re.compile(r"(?=\.X\.XX\.)")

    open_four = 0
    open_three = 0

    for s in lines:
        # 阻断：对手子作为硬边界，无需额外处理；正则本身通过 '.' 定位空位
        open_four += len(pat_open_four.findall(s))
        open_three += len(pat_open_three_1.findall(s))
        open_three += len(pat_open_three_2.findall(s))
        open_three += len(pat_open_three_3.findall(s))

        # 额外：排除五连端内的伪命中（如 '.XXXXX.'），简单修正：
        # 若存在 'XXXXX'，则其内部不会被 '.XXXX.' 捕获（因为需要两端为 '.'），无需特别排除。

    return {"open_three": open_three, "open_four": open_four}
