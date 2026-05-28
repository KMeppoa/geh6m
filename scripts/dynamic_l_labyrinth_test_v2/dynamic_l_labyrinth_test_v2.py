#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
dynamic_l_labyrinth_test_v2.py

V2 эксперимент для твоей идеи P_L / NP_L.

Главная проверка:
    L-проверка      = можно проверить разрешённость шага
    L-навигация     = можно выбрать "лучший" шаг
    L-lookahead     = можно смотреть на несколько будущих изменений L

Мы сравниваем:
    random      — только L-проверка, без направления
    guided_1    — смотрит на 1 шаг вперёд
    guided_2    — смотрит на 2 шага вперёд
    guided_3    — смотрит на 3 шага вперёд
    guided_5    — смотрит на 5 шагов вперёд
    guided_10   — смотрит на 10 шагов вперёд
    bfs_control — контрольный полный поиск по состояниям (cell, L)

Простой запуск:
    python dynamic_l_labyrinth_test_v2.py --maps 50 --trials-per-map 50 --size 20 --max-steps 1000 --wall-density 0.25

Большой запуск:
    python dynamic_l_labyrinth_test_v2.py --maps 200 --trials-per-map 100 --size 25 --max-steps 1500 --wall-density 0.25

Файлы результата:
    l_labyrinth_v2_summary_by_mode.csv
    l_labyrinth_v2_summary_by_map.csv
    l_labyrinth_v2_logs.jsonl
"""

import argparse
import csv
import json
import random
from collections import deque
from dataclasses import dataclass
from math import inf


# -----------------------------
# Result
# -----------------------------

@dataclass
class RunResult:
    map_seed: int
    mode: str
    success: bool
    steps: int
    path: list
    l_chain: list
    logs: list


# -----------------------------
# Dynamic L Labyrinth
# -----------------------------

class DynamicLLabyrinth:
    DIRECTIONS = {
        "R": (1, 0),
        "L": (-1, 0),
        "D": (0, 1),
        "U": (0, -1),
    }

    L_STATES = ("L0", "L1", "L2", "L3")

    def __init__(self, size=20, seed=42, wall_density=0.25):
        self.size = size
        self.seed = seed
        self.wall_density = wall_density
        self.start = (0, 0)
        self.goal = (size - 1, size - 1)

        rng = random.Random(seed)

        self.blocked = set()
        for y in range(size):
            for x in range(size):
                if (x, y) in (self.start, self.goal):
                    continue
                if rng.random() < wall_density:
                    self.blocked.add((x, y))

        # Гарантируем грубый физический коридор, чтобы карта не была совсем невозможной.
        # Но L-правила всё равно могут делать путь сложным.
        for x in range(size):
            self.blocked.discard((x, 0))
        for y in range(size):
            self.blocked.discard((size - 1, y))

    def inside(self, cell):
        x, y = cell
        return 0 <= x < self.size and 0 <= y < self.size and cell not in self.blocked

    def move(self, cell, direction):
        dx, dy = self.DIRECTIONS[direction]
        return (cell[0] + dx, cell[1] + dy)

    def allowed_dirs_by_L(self, cell, current_L):
        x, y = cell

        # Искусственная L-логика:
        # один и тот же переход может быть разрешён или запрещён в зависимости от L.
        if current_L == "L0":
            dirs = ["R", "D"]
            if (x + y) % 3 == 0:
                dirs.append("U")

        elif current_L == "L1":
            dirs = ["D", "L"]
            if x % 2 == 0:
                dirs.append("R")

        elif current_L == "L2":
            dirs = ["R", "U"]
            if y % 2 == 1:
                dirs.append("D")

        else:  # L3
            dirs = ["R", "D", "L", "U"]
            if (x * 7 + y * 3) % 4 == 0 and "L" in dirs:
                dirs.remove("L")

        result = []
        for d in dirs:
            nxt = self.move(cell, d)
            if self.inside(nxt):
                result.append(d)
        return result

    def update_L(self, cell, direction, current_L):
        x, y = cell
        idx = self.L_STATES.index(current_L)

        delta_by_dir = {
            "R": 1,
            "D": 2,
            "L": 3,
            "U": 1,
        }

        local_shift = (x + 2 * y) % 2
        new_idx = (idx + delta_by_dir[direction] + local_shift) % len(self.L_STATES)
        return self.L_STATES[new_idx]

    def heuristic_distance(self, cell):
        return abs(self.goal[0] - cell[0]) + abs(self.goal[1] - cell[1])


# -----------------------------
# Verify path: NP_L
# -----------------------------

def verify_given_path(lab, directions, map_seed, start_L="L0"):
    cell = lab.start
    current_L = start_L
    logs = [f"START verify: cell={cell}, L={current_L}"]
    path = [cell]
    l_chain = [current_L]

    for step, d in enumerate(directions, start=1):
        allowed = lab.allowed_dirs_by_L(cell, current_L)
        if d not in allowed:
            logs.append(f"step={step}: {cell} --{d}--> запрещено при L={current_L}, allowed={allowed}")
            return RunResult(map_seed, "verify", False, step - 1, path, l_chain, logs)

        next_cell = lab.move(cell, d)
        old_L = current_L
        current_L = lab.update_L(cell, d, current_L)

        logs.append(f"step={step}: {cell} --{d}--> {next_cell} | L: {old_L}->{current_L}")

        cell = next_cell
        path.append(cell)
        l_chain.append(current_L)

    success = cell == lab.goal
    logs.append(f"FINISH verify: cell={cell}, L={current_L}, success={success}")
    return RunResult(map_seed, "verify", success, len(directions), path, l_chain, logs)


# -----------------------------
# Random search: only L-check
# -----------------------------

def random_search(lab, map_seed, max_steps=1000, seed=0, start_L="L0"):
    rng = random.Random(seed)
    cell = lab.start
    current_L = start_L

    logs = [f"START random: cell={cell}, L={current_L}"]
    path = [cell]
    l_chain = [current_L]

    for step in range(1, max_steps + 1):
        candidates = lab.allowed_dirs_by_L(cell, current_L)

        if not candidates:
            logs.append(f"step={step}: тупик | cell={cell}, L={current_L}")
            return RunResult(map_seed, "random", False, step - 1, path, l_chain, logs)

        d = rng.choice(candidates)
        next_cell = lab.move(cell, d)
        old_L = current_L
        current_L = lab.update_L(cell, d, current_L)

        logs.append(
            f"step={step}: candidates={candidates}, chosen={d}, "
            f"{cell}->{next_cell} | L: {old_L}->{current_L}"
        )

        cell = next_cell
        path.append(cell)
        l_chain.append(current_L)

        if cell == lab.goal:
            logs.append(f"GOAL random: steps={step}, L={current_L}")
            return RunResult(map_seed, "random", True, step, path, l_chain, logs)

    logs.append(f"FAIL random: max_steps={max_steps}, final_cell={cell}, L={current_L}")
    return RunResult(map_seed, "random", False, max_steps, path, l_chain, logs)


# -----------------------------
# Lookahead scoring
# -----------------------------

def evaluate_future(lab, cell, current_L, depth, visited):
    """
    Возвращает score: чем меньше, тем лучше.

    Идея:
    - depth=0: просто расстояние до цели
    - depth>0: пробуем будущие шаги и берём лучший прогноз
    - если тупик: большой штраф
    - если цель: очень хороший score

    Это не полный BFS. Это локальный прогноз глубиной N.
    """

    if cell == lab.goal:
        return -100000

    if depth <= 0:
        repeat_penalty = visited.get((cell, current_L), 0) * 5
        return lab.heuristic_distance(cell) + repeat_penalty

    candidates = lab.allowed_dirs_by_L(cell, current_L)

    if not candidates:
        return 100000 + lab.heuristic_distance(cell)

    best = inf

    for d in candidates:
        nxt = lab.move(cell, d)
        next_L = lab.update_L(cell, d, current_L)

        repeat_penalty = visited.get((nxt, next_L), 0) * 5

        # Небольшая цена за шаг + прогноз будущего
        future_score = 1 + repeat_penalty + evaluate_future(
            lab, nxt, next_L, depth - 1, visited
        )

        if future_score < best:
            best = future_score

    return best


# -----------------------------
# Guided lookahead search
# -----------------------------

def guided_lookahead_search(lab, map_seed, lookahead_depth=1, max_steps=1000, start_L="L0"):
    mode = f"guided_{lookahead_depth}"

    cell = lab.start
    current_L = start_L

    logs = [f"START {mode}: cell={cell}, L={current_L}"]
    path = [cell]
    l_chain = [current_L]
    visited = {(cell, current_L): 1}

    for step in range(1, max_steps + 1):
        candidates = lab.allowed_dirs_by_L(cell, current_L)

        if not candidates:
            logs.append(f"step={step}: тупик | cell={cell}, L={current_L}")
            return RunResult(map_seed, mode, False, step - 1, path, l_chain, logs)

        scored = []
        for d in candidates:
            nxt = lab.move(cell, d)
            next_L = lab.update_L(cell, d, current_L)

            score = evaluate_future(
                lab,
                nxt,
                next_L,
                depth=lookahead_depth - 1,
                visited=visited,
            )

            scored.append((score, d, nxt, next_L))

        scored.sort(key=lambda x: (x[0], x[1]))
        score, d, next_cell, next_L = scored[0]

        old_L = current_L
        logs.append(
            f"step={step}: lookahead={lookahead_depth}, "
            f"scored={[(round(s,2), dd) for s, dd, _, _ in scored]}, "
            f"chosen={d}, {cell}->{next_cell} | L: {old_L}->{next_L}"
        )

        cell = next_cell
        current_L = next_L
        path.append(cell)
        l_chain.append(current_L)
        visited[(cell, current_L)] = visited.get((cell, current_L), 0) + 1

        if cell == lab.goal:
            logs.append(f"GOAL {mode}: steps={step}, L={current_L}")
            return RunResult(map_seed, mode, True, step, path, l_chain, logs)

    logs.append(f"FAIL {mode}: max_steps={max_steps}, final_cell={cell}, L={current_L}")
    return RunResult(map_seed, mode, False, max_steps, path, l_chain, logs)


# -----------------------------
# BFS control over (cell, L)
# -----------------------------

def bfs_state_search(lab, start_L="L0"):
    start_state = (lab.start, start_L)
    queue = deque([start_state])
    parent = {start_state: None}
    parent_action = {}

    while queue:
        cell, current_L = queue.popleft()

        if cell == lab.goal:
            dirs = []
            state = (cell, current_L)
            while parent[state] is not None:
                dirs.append(parent_action[state])
                state = parent[state]
            dirs.reverse()
            return dirs

        for d in lab.allowed_dirs_by_L(cell, current_L):
            nxt = lab.move(cell, d)
            next_L = lab.update_L(cell, d, current_L)
            next_state = (nxt, next_L)

            if next_state not in parent:
                parent[next_state] = (cell, current_L)
                parent_action[next_state] = d
                queue.append(next_state)

    return None


# -----------------------------
# Summary helpers
# -----------------------------

def summarize(results):
    total = len(results)
    successes = [r for r in results if r.success]
    fails = total - len(successes)

    if successes:
        avg_steps_success = sum(r.steps for r in successes) / len(successes)
        min_steps_success = min(r.steps for r in successes)
        max_steps_success = max(r.steps for r in successes)
    else:
        avg_steps_success = None
        min_steps_success = None
        max_steps_success = None

    avg_steps_all = sum(r.steps for r in results) / total if total else None

    return {
        "total": total,
        "success": len(successes),
        "fail": fails,
        "success_rate": len(successes) / total if total else 0,
        "avg_steps_success_only": avg_steps_success,
        "avg_steps_all": avg_steps_all,
        "min_steps_success": min_steps_success,
        "max_steps_success": max_steps_success,
    }


def group_by_mode(results):
    modes = sorted(set(r.mode for r in results))
    return {m: [r for r in results if r.mode == m] for m in modes}


def save_summary_by_mode(path, results):
    grouped = group_by_mode(results)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "mode",
            "total",
            "success",
            "fail",
            "success_rate",
            "avg_steps_success_only",
            "avg_steps_all",
            "min_steps_success",
            "max_steps_success",
        ])

        for mode, items in grouped.items():
            s = summarize(items)
            writer.writerow([
                mode,
                s["total"],
                s["success"],
                s["fail"],
                s["success_rate"],
                s["avg_steps_success_only"],
                s["avg_steps_all"],
                s["min_steps_success"],
                s["max_steps_success"],
            ])


def save_summary_by_map(path, results, bfs_info_by_seed):
    # summary: per map_seed + mode
    seeds = sorted(set(r.map_seed for r in results))
    modes = sorted(set(r.mode for r in results))

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "map_seed",
            "bfs_exists",
            "bfs_length",
            "mode",
            "total",
            "success",
            "fail",
            "success_rate",
            "avg_steps_success_only",
            "avg_steps_all",
        ])

        for seed in seeds:
            for mode in modes:
                items = [r for r in results if r.map_seed == seed and r.mode == mode]
                if not items:
                    continue
                s = summarize(items)
                bfs_exists, bfs_length = bfs_info_by_seed.get(seed, (False, None))
                writer.writerow([
                    seed,
                    bfs_exists,
                    bfs_length,
                    mode,
                    s["total"],
                    s["success"],
                    s["fail"],
                    s["success_rate"],
                    s["avg_steps_success_only"],
                    s["avg_steps_all"],
                ])


def save_logs(path, selected_results):
    with open(path, "w", encoding="utf-8") as f:
        for r in selected_results:
            item = {
                "map_seed": r.map_seed,
                "mode": r.mode,
                "success": r.success,
                "steps": r.steps,
                "path": r.path,
                "l_chain": r.l_chain,
                "logs": r.logs,
            }
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


# -----------------------------
# Main
# -----------------------------

def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--maps", type=int, default=50)
    parser.add_argument("--trials-per-map", type=int, default=50)
    parser.add_argument("--size", type=int, default=20)
    parser.add_argument("--max-steps", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--wall-density", type=float, default=0.25)
    parser.add_argument("--lookaheads", type=str, default="1,2,3,5,10")
    parser.add_argument("--log-limit", type=int, default=20)
    parser.add_argument("--out-prefix", type=str, default="l_labyrinth_v2")

    args = parser.parse_args()

    lookaheads = [int(x.strip()) for x in args.lookaheads.split(",") if x.strip()]

    print("=== CONFIG V2 ===")
    print(f"maps={args.maps}")
    print(f"trials_per_map={args.trials_per_map}")
    print(f"size={args.size}")
    print(f"max_steps={args.max_steps}")
    print(f"seed={args.seed}")
    print(f"wall_density={args.wall_density}")
    print(f"lookaheads={lookaheads}")
    print()

    all_results = []
    selected_logs = []
    bfs_info_by_seed = {}

    for map_index in range(args.maps):
        map_seed = args.seed + map_index
        lab = DynamicLLabyrinth(
            size=args.size,
            seed=map_seed,
            wall_density=args.wall_density,
        )

        bfs_dirs = bfs_state_search(lab)
        bfs_exists = bfs_dirs is not None
        bfs_length = len(bfs_dirs) if bfs_dirs is not None else None
        bfs_info_by_seed[map_seed] = (bfs_exists, bfs_length)

        if not bfs_exists:
            # Если даже BFS не нашёл путь, карта не подходит для сравнения.
            print(f"map {map_index+1}/{args.maps}, seed={map_seed}: BFS no path, skipped")
            continue

        verify_result = verify_given_path(lab, bfs_dirs, map_seed)
        if len(selected_logs) < args.log_limit:
            selected_logs.append(verify_result)

        if (map_index + 1) % 10 == 0 or map_index == 0:
            print(
                f"map {map_index+1}/{args.maps}, seed={map_seed}: "
                f"BFS length={bfs_length}"
            )

        for trial in range(args.trials_per_map):
            trial_seed = args.seed * 1000000 + map_seed * 1000 + trial

            r = random_search(
                lab,
                map_seed=map_seed,
                max_steps=args.max_steps,
                seed=trial_seed,
            )
            all_results.append(r)

            if len(selected_logs) < args.log_limit:
                selected_logs.append(r)

            # guided lookahead deterministic, но мы всё равно записываем по trial,
            # чтобы статистически сравнение было в одинаковом формате.
            # Важно: из-за deterministic будет одинаково на одной карте.
            for depth in lookaheads:
                g = guided_lookahead_search(
                    lab,
                    map_seed=map_seed,
                    lookahead_depth=depth,
                    max_steps=args.max_steps,
                )
                all_results.append(g)

                if len(selected_logs) < args.log_limit:
                    selected_logs.append(g)

    print()
    print("=== SUMMARY BY MODE ===")
    grouped = group_by_mode(all_results)

    for mode in sorted(grouped.keys()):
        s = summarize(grouped[mode])
        print(f"\n[{mode}]")
        for k, v in s.items():
            print(f"{k}: {v}")

    summary_mode_path = f"{args.out_prefix}_summary_by_mode.csv"
    summary_map_path = f"{args.out_prefix}_summary_by_map.csv"
    logs_path = f"{args.out_prefix}_logs.jsonl"

    save_summary_by_mode(summary_mode_path, all_results)
    save_summary_by_map(summary_map_path, all_results, bfs_info_by_seed)
    save_logs(logs_path, selected_logs)

    print()
    print("=== FILES WRITTEN ===")
    print(summary_mode_path)
    print(summary_map_path)
    print(logs_path)

    print()
    print("=== HOW TO READ ===")
    print("1) random = L только проверяет шаги.")
    print("2) guided_1 = L смотрит на 1 шаг.")
    print("3) guided_10 = L смотрит на 10 шагов.")
    print("4) Если success_rate растёт с глубиной lookahead,")
    print("   это поддерживает идею: важна не просто L-навигация,")
    print("   а способность учитывать будущие изменения L.")
    print("5) Если guided_1 хуже random, это тоже важно:")
    print("   локальная подсказка может вредить без памяти будущего.")


if __name__ == "__main__":
    main()
