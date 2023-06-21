#!/usr/bin/env python3

import sys
from typing import Final
from itertools import permutations, product, pairwise

import networkx


def mod6(i: int) -> int:
    "Like %6 but 0 is 6"
    return i % 6 or 6


def connections(position: int):
    """From the center you can go anywhere, but the rest can only move to adjacent spaces."""
    if position == 0:
        return {1, 2, 3, 4, 5, 6}
    else:
        return {0, mod6(position - 1), mod6(position + 1)}


# Some weird crap with generators to generate every valid starting board
# (The rules are that 1,2,3 are shuffled onto the 4,5,6 spaces and vice versa)
starting_positions: Final = list(
    (0,) + i + j for i, j in (product(permutations([4, 5, 6]), permutations([1, 2, 3])))
)
goal: Final = (0, 1, 2, 3, 4, 5, 6)


def valid_moves(board: tuple[int]) -> set[int]:
    """Return all tiles that can be moved, based on where the empty space is"""
    i = board.index(0)
    return {board[i] for i in connections(i)}


def move(board: tuple[int], tile: int):
    """Return a board after moving the specified tile"""
    i = board.index(0)
    j = board.index(tile)
    li = list(board)
    li[i], li[j] = li[j], li[i]
    return tuple(li)


def all_moves(board):
    """Return a dict of tile_moved: new_board for all valid moves"""
    result = {}
    for valid_move in valid_moves(board):
        result[valid_move] = move(board, valid_move)
    return result


# Generate the complete state space for the board: every possible
# configuration of the board the moves that transition one board
# to the next.
g = networkx.Graph()
for board in permutations(goal):
    g.add_node(board)
    for m, b in all_moves(board).items():
        g.add_node(b)
        g.add_edge(board, b, data=str(m))


def solve(starting_position):
    """Return the shortest path from the staring position to the goal"""
    sp = networkx.shortest_path(g, starting_position, goal)
    solution = []
    for pair in pairwise(sp):
        solution.append(g.get_edge_data(*pair)["data"])
    return solution


def solve_argv():
    """Parse the first argument to the script and solve that board"""
    input_str = sys.argv[1]
    starting_position = tuple(int(i) for i in input_str if i.isdigit())
    print(f"{starting_position=}")
    solution = solve(starting_position)
    print(starting_position, f"solved in {len(solution)} moves", solution)


def solve_all_starting_positions():
    """Print the solutions to every valid starting board in the game"""
    for starting_position in starting_positions:
        solution = solve(starting_position)
        print(
            starting_position,
            f"solved in {len(solution)} moves:",
            "  ".join(solution),
            end=" ",
        )
        print()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        solve_argv()
    else:
        solve_all_starting_positions()
