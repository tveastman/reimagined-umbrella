#!/usr/bin/env python3

import enum
from typing import Final
from itertools import permutations, product, pairwise

from rich import print
import networkx


def mod6(i: int) -> int:
    return i % 6 or 6


def connections(position: int):
    if position == 0:
        return {1, 2, 3, 4, 5, 6}
    else:
        return {0, mod6(position - 1), mod6(position + 1)}


starting_positions: Final = list(
    (0,) + i + j for i, j in (product(permutations([4, 5, 6]), permutations([1, 2, 3])))
)
goal: Final = (0, 1, 2, 3, 4, 5, 6)


def valid_moves(board: tuple[int]) -> set[int]:
    i = board.index(0)
    return {board[i] for i in connections(i)}


def move(board: tuple[int], tile: int):
    i = board.index(0)
    j = board.index(tile)
    li = list(board)
    li[i], li[j] = li[j], li[i]
    return tuple(li)


def all_moves(board):
    result = {}
    for valid_move in valid_moves(board):
        result[valid_move] = move(board, valid_move)
    return result


g = networkx.Graph()
for board in permutations(goal):
    g.add_node(board)
    for m, b in all_moves(board).items():
        g.add_node(b)
        g.add_edge(board, b, data=str(m))


def solve(starting_position):
    sp = networkx.shortest_path(g, starting_position, goal)
    for pair in pairwise(sp):
        print(g.get_edge_data(*pair))


print(g)
input_str = input("enter the tiles: ")
starting_position = tuple(int(i) for i in input_str.strip().split())
print(f"{starting_position=}")
solve(starting_position)
# print(valid_moves(starting_position))
# print(all_moves(starting_position))
