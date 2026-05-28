#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
sat_l_test_v1.py

SAT-эксперимент для идеи P_L / NP_L.

Идея:
    SAT = задача про True/False переменные.
    Нужно подобрать значения так, чтобы все условия-клаузы стали True.

Связь с твоей L-идеей:
    assignment path = последовательность выборов переменных
    L = текущее состояние ограничений после уже сделанных выборов
    NP_L = готовый полный assignment быстро проверяется
    P_L-кандидат = алгоритм умеет выбирать переменные так, чтобы быстро прийти к решению

Сравниваем режимы:
    random        — случайно выбирает переменную и True/False
    greedy_1      — выбирает локально лучший следующий ход
    lookahead_2   — смотрит на 2 хода вперёд
    lookahead_3   — смотрит на 3 хода вперёд
    lookahead_5   — смотрит на 5 ходов вперёд
    dpll_control  — контрольный решатель с backtracking + unit propagation

Простой запуск:
    python sat_l_test_v1.py --formulas 100 --vars 30 --clauses 120 --k 3 --max-steps 100 --lookaheads 1,2,3,5

Более большой запуск:
    python sat_l_test_v1.py --formulas 500 --vars 50 --clauses 210 --k 3 --max-steps 200 --lookaheads 1,2,3,5

Файлы результата:
    sat_l_v1_summary_by_mode.csv
    sat_l_v1_summary_by_formula.csv
    sat_l_v1_logs.jsonl
"""

import argparse
import csv
import json
import random
from dataclasses import dataclass
from math import inf


# -----------------------------
# Result
# -----------------------------

@dataclass
class RunResult:
    formula_seed: int
    mode: str
    success: bool
    steps: int
    assignment: dict
    logs: list


# -----------------------------
# SAT formula utilities
# -----------------------------

def generate_random_k_sat(n_vars, n_clauses, k, seed):
    """
    Генерирует случайную k-SAT формулу.

    Переменная: число 1..n
    Литерал:
        +x значит x=True
        -x значит x=False

    Клауза:
        [1, -3, 5] значит:
        x1 OR not x3 OR x5
    """
    rng = random.Random(seed)
    formula = []

    for _ in range(n_clauses):
        vars_ = rng.sample(range(1, n_vars + 1), k)
        clause = []
        for v in vars_:
            sign = 1 if rng.random() < 0.5 else -1
            clause.append(sign * v)
        formula.append(clause)

    return formula


def lit_value(lit, assignment):
    """
    Возвращает:
        True  если литерал уже истинный
        False если литерал уже ложный
        None  если переменная ещё не назначена
    """
    var = abs(lit)
    if var not in assignment:
        return None
    val = assignment[var]
    return val if lit > 0 else (not val)


def clause_status(clause, assignment):
    """
    Возвращает:
        "sat"      если клауза уже True
        "unsat"    если все литералы False
        "unknown"  если пока неясно
    """
    has_unknown = False

    for lit in clause:
        v = lit_value(lit, assignment)
        if v is True:
            return "sat"
        if v is None:
            has_unknown = True

    return "unknown" if has_unknown else "unsat"


def formula_stats(formula, assignment):
    sat = 0
    unsat = 0
    unknown = 0

    for clause in formula:
        st = clause_status(clause, assignment)
        if st == "sat":
            sat += 1
        elif st == "unsat":
            unsat += 1
        else:
            unknown += 1

    return {
        "sat": sat,
        "unsat": unsat,
        "unknown": unknown,
        "total": len(formula),
    }


def is_formula_satisfied(formula, assignment, n_vars):
    if len(assignment) < n_vars:
        return False
    return all(clause_status(c, assignment) == "sat" for c in formula)


def verify_assignment(formula, assignment, n_vars):
    """
    NP_L-проверка:
        готовый assignment быстро проверяется подстановкой.
    """
    logs = []
    logs.append(f"START verify: assigned={len(assignment)}/{n_vars}")
    stats = formula_stats(formula, assignment)
    logs.append(f"stats={stats}")
    success = is_formula_satisfied(formula, assignment, n_vars)
    logs.append(f"FINISH verify: success={success}")
    return success, logs


# -----------------------------
# L-state interpretation for SAT
# -----------------------------

def score_assignment_state(formula, assignment, n_vars):
    """
    Score для текущего L-состояния.
    Меньше = лучше.

    Логика:
        unsat clauses = очень плохо
        unknown clauses = ещё не решено
        sat clauses = хорошо

    Это не доказательство, а эвристика.
    """
    st = formula_stats(formula, assignment)

    # Если уже есть ложная клауза, это почти тупик для текущей ветки.
    # В обычном SAT backtracking мог бы откатиться, но наши greedy/lookahead агенты
    # идут вперёд без полного отката.
    return st["unsat"] * 10000 + st["unknown"] * 10 - st["sat"]


def unassigned_vars(n_vars, assignment):
    return [v for v in range(1, n_vars + 1) if v not in assignment]


def possible_actions(n_vars, assignment):
    """
    Action = выбрать ещё не назначенную переменную и дать ей True/False.
    """
    actions = []
    for v in unassigned_vars(n_vars, assignment):
        actions.append((v, True))
        actions.append((v, False))
    return actions


def apply_action(assignment, action):
    v, val = action
    new_assignment = dict(assignment)
    new_assignment[v] = val
    return new_assignment


# -----------------------------
# Random SAT search
# -----------------------------

def random_search_sat(formula, n_vars, formula_seed, max_steps, seed):
    rng = random.Random(seed)
    assignment = {}
    logs = [f"START random: n_vars={n_vars}"]

    for step in range(1, max_steps + 1):
        if is_formula_satisfied(formula, assignment, n_vars):
            logs.append(f"GOAL random: steps={step-1}")
            return RunResult(formula_seed, "random", True, step - 1, assignment, logs)

        actions = possible_actions(n_vars, assignment)
        if not actions:
            break

        action = rng.choice(actions)
        assignment = apply_action(assignment, action)
        stats = formula_stats(formula, assignment)

        logs.append(
            f"step={step}: choose x{action[0]}={action[1]} | "
            f"L_stats={stats}"
        )

        # Если уже есть unsat, random всё равно продолжает, но это ветка уже обречена.
        # Это специально показывает разницу между простой проверкой и умным поиском.

    success = is_formula_satisfied(formula, assignment, n_vars)
    logs.append(f"FINISH random: success={success}, assigned={len(assignment)}/{n_vars}, stats={formula_stats(formula, assignment)}")
    return RunResult(formula_seed, "random", success, min(max_steps, len(assignment)), assignment, logs)


# -----------------------------
# Lookahead SAT search
# -----------------------------

def evaluate_future_sat(formula, n_vars, assignment, depth):
    """
    Оценка будущего.
    Меньше = лучше.

    Если depth=0, смотрим только текущее L-состояние.
    Если depth>0, пробуем будущие выборы.
    """
    if is_formula_satisfied(formula, assignment, n_vars):
        return -1000000

    stats = formula_stats(formula, assignment)
    if stats["unsat"] > 0:
        return 1000000 + stats["unsat"] * 10000 + stats["unknown"]

    if depth <= 0:
        return score_assignment_state(formula, assignment, n_vars)

    actions = possible_actions(n_vars, assignment)
    if not actions:
        return score_assignment_state(formula, assignment, n_vars)

    best = inf

    # Ограничение: чтобы lookahead не взрывался слишком сильно.
    # Мы сначала сортируем действия по локальной оценке и берём top-N.
    ranked = []
    for action in actions:
        new_asg = apply_action(assignment, action)
        local_score = score_assignment_state(formula, new_asg, n_vars)
        ranked.append((local_score, action, new_asg))

    ranked.sort(key=lambda x: x[0])

    # branching cap: ключевой ограничитель скорости
    # Чем больше, тем честнее, но медленнее.
    BRANCH_CAP = 8
    ranked = ranked[:BRANCH_CAP]

    for local_score, action, new_asg in ranked:
        future = evaluate_future_sat(formula, n_vars, new_asg, depth - 1)
        if future < best:
            best = future

    return best


def lookahead_search_sat(formula, n_vars, formula_seed, lookahead_depth, max_steps):
    mode = "greedy_1" if lookahead_depth == 1 else f"lookahead_{lookahead_depth}"
    assignment = {}
    logs = [f"START {mode}: n_vars={n_vars}, lookahead={lookahead_depth}"]

    for step in range(1, min(max_steps, n_vars) + 1):
        if is_formula_satisfied(formula, assignment, n_vars):
            logs.append(f"GOAL {mode}: steps={step-1}")
            return RunResult(formula_seed, mode, True, step - 1, assignment, logs)

        actions = possible_actions(n_vars, assignment)
        if not actions:
            break

        scored = []
        for action in actions:
            new_asg = apply_action(assignment, action)
            score = evaluate_future_sat(
                formula,
                n_vars,
                new_asg,
                depth=lookahead_depth - 1,
            )
            scored.append((score, action, new_asg))

        scored.sort(key=lambda x: (x[0], x[1][0], x[1][1]))

        best_score, best_action, best_assignment = scored[0]
        assignment = best_assignment
        stats = formula_stats(formula, assignment)

        # Логи не делаем слишком огромными: показываем top-5
        top_preview = [(s, f"x{a[0]}={a[1]}") for s, a, _ in scored[:5]]

        logs.append(
            f"step={step}: chosen=x{best_action[0]}={best_action[1]}, "
            f"score={best_score}, top5={top_preview}, L_stats={stats}"
        )

        if stats["unsat"] > 0:
            # Этот greedy/lookahead без backtracking.
            # Как только появилась ложная клауза, текущий путь обречён.
            logs.append(f"dead_branch: unsat clauses appeared at step={step}")
            break

    success = is_formula_satisfied(formula, assignment, n_vars)
    logs.append(f"FINISH {mode}: success={success}, assigned={len(assignment)}/{n_vars}, stats={formula_stats(formula, assignment)}")
    return RunResult(formula_seed, mode, success, len(assignment), assignment, logs)


# -----------------------------
# DPLL control solver
# -----------------------------

def simplify_formula(formula, assignment):
    """
    Возвращает статусы и упрощённые клаузы для DPLL.
    """
    simplified = []

    for clause in formula:
        new_clause = []
        satisfied = False

        for lit in clause:
            val = lit_value(lit, assignment)
            if val is True:
                satisfied = True
                break
            elif val is None:
                new_clause.append(lit)
            # False literal просто выбрасываем

        if satisfied:
            continue

        if not new_clause:
            return None  # конфликт

        simplified.append(new_clause)

    return simplified


def find_unit_clause(simplified):
    for clause in simplified:
        if len(clause) == 1:
            lit = clause[0]
            return abs(lit), lit > 0
    return None


def choose_variable_dpll(simplified, assignment, n_vars):
    """
    Простая эвристика: переменная, которая чаще всего встречается в оставшихся клаузах.
    """
    counts = {}
    polarity = {}

    for clause in simplified:
        for lit in clause:
            v = abs(lit)
            if v in assignment:
                continue
            counts[v] = counts.get(v, 0) + 1
            polarity[v] = polarity.get(v, 0) + (1 if lit > 0 else -1)

    if not counts:
        for v in range(1, n_vars + 1):
            if v not in assignment:
                return v, True
        return None

    v = max(counts, key=counts.get)
    preferred_val = polarity.get(v, 0) >= 0
    return v, preferred_val


def dpll(formula, n_vars, assignment, node_counter, max_nodes):
    """
    Контрольный backtracking SAT solver.
    Он не доказывает P/NP, но нужен как контроль:
        формула решаема или нет.
    """
    node_counter[0] += 1
    if node_counter[0] > max_nodes:
        return None  # timeout/unknown

    simplified = simplify_formula(formula, assignment)

    if simplified is None:
        return False

    if not simplified:
        return assignment

    # Unit propagation
    while True:
        unit = find_unit_clause(simplified)
        if unit is None:
            break

        v, val = unit
        if v in assignment and assignment[v] != val:
            return False

        assignment = dict(assignment)
        assignment[v] = val

        simplified = simplify_formula(formula, assignment)
        if simplified is None:
            return False
        if not simplified:
            return assignment

    choice = choose_variable_dpll(simplified, assignment, n_vars)
    if choice is None:
        return assignment if is_formula_satisfied(formula, assignment, n_vars) else False

    v, preferred_val = choice

    for val in (preferred_val, not preferred_val):
        new_assignment = dict(assignment)
        new_assignment[v] = val
        result = dpll(formula, n_vars, new_assignment, node_counter, max_nodes)
        if result is None:
            return None
        if result is not False:
            return result

    return False


def dpll_control(formula, n_vars, formula_seed, max_nodes):
    logs = [f"START dpll_control: n_vars={n_vars}, max_nodes={max_nodes}"]
    node_counter = [0]
    result = dpll(formula, n_vars, {}, node_counter, max_nodes=max_nodes)

    if result is None:
        logs.append(f"FINISH dpll_control: unknown/timeout, nodes={node_counter[0]}")
        return RunResult(formula_seed, "dpll_control", False, node_counter[0], {}, logs)

    if result is False:
        logs.append(f"FINISH dpll_control: UNSAT, nodes={node_counter[0]}")
        return RunResult(formula_seed, "dpll_control", False, node_counter[0], {}, logs)

    success, verify_logs = verify_assignment(formula, result, n_vars)
    logs.extend(verify_logs)
    logs.append(f"FINISH dpll_control: SAT={success}, nodes={node_counter[0]}")
    return RunResult(formula_seed, "dpll_control", success, node_counter[0], result, logs)


# -----------------------------
# Summaries
# -----------------------------

def summarize(results):
    total = len(results)
    successes = [r for r in results if r.success]
    fail = total - len(successes)

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
        "fail": fail,
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
        w = csv.writer(f)
        w.writerow([
            "mode", "total", "success", "fail", "success_rate",
            "avg_steps_success_only", "avg_steps_all",
            "min_steps_success", "max_steps_success",
        ])
        for mode, items in grouped.items():
            s = summarize(items)
            w.writerow([
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


def save_summary_by_formula(path, results):
    seeds = sorted(set(r.formula_seed for r in results))
    modes = sorted(set(r.mode for r in results))

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "formula_seed", "mode", "success", "steps", "assigned_count"
        ])
        for seed in seeds:
            for mode in modes:
                items = [r for r in results if r.formula_seed == seed and r.mode == mode]
                for r in items:
                    w.writerow([
                        seed,
                        mode,
                        r.success,
                        r.steps,
                        len(r.assignment),
                    ])


def save_logs(path, selected_results):
    with open(path, "w", encoding="utf-8") as f:
        for r in selected_results:
            item = {
                "formula_seed": r.formula_seed,
                "mode": r.mode,
                "success": r.success,
                "steps": r.steps,
                "assignment": r.assignment,
                "logs": r.logs,
            }
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


# -----------------------------
# Main
# -----------------------------

def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--formulas", type=int, default=100)
    parser.add_argument("--vars", type=int, default=30)
    parser.add_argument("--clauses", type=int, default=120)
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--max-steps", type=int, default=100)
    parser.add_argument("--max-dpll-nodes", type=int, default=200000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--lookaheads", type=str, default="1,2,3,5")
    parser.add_argument("--log-limit", type=int, default=20)
    parser.add_argument("--out-prefix", type=str, default="sat_l_v1")

    args = parser.parse_args()
    lookaheads = [int(x.strip()) for x in args.lookaheads.split(",") if x.strip()]

    print("=== CONFIG SAT L V1 ===")
    print(f"formulas={args.formulas}")
    print(f"vars={args.vars}")
    print(f"clauses={args.clauses}")
    print(f"k={args.k}")
    print(f"max_steps={args.max_steps}")
    print(f"max_dpll_nodes={args.max_dpll_nodes}")
    print(f"seed={args.seed}")
    print(f"lookaheads={lookaheads}")
    print()

    all_results = []
    selected_logs = []

    for i in range(args.formulas):
        formula_seed = args.seed + i
        formula = generate_random_k_sat(
            n_vars=args.vars,
            n_clauses=args.clauses,
            k=args.k,
            seed=formula_seed,
        )

        if (i + 1) % 10 == 0 or i == 0:
            print(f"formula {i+1}/{args.formulas}, seed={formula_seed}")

        # Control solver first
        dpll_res = dpll_control(
            formula,
            n_vars=args.vars,
            formula_seed=formula_seed,
            max_nodes=args.max_dpll_nodes,
        )
        all_results.append(dpll_res)
        if len(selected_logs) < args.log_limit:
            selected_logs.append(dpll_res)

        # Если DPLL не нашёл SAT, формула может быть UNSAT или timeout.
        # Для сравнения greedy/random с SAT-поиском полезнее оставлять все,
        # но success для них будет естественно False, если формула UNSAT.
        rnd = random_search_sat(
            formula,
            n_vars=args.vars,
            formula_seed=formula_seed,
            max_steps=args.max_steps,
            seed=args.seed * 1000000 + formula_seed,
        )
        all_results.append(rnd)
        if len(selected_logs) < args.log_limit:
            selected_logs.append(rnd)

        for depth in lookaheads:
            res = lookahead_search_sat(
                formula,
                n_vars=args.vars,
                formula_seed=formula_seed,
                lookahead_depth=depth,
                max_steps=args.max_steps,
            )
            all_results.append(res)
            if len(selected_logs) < args.log_limit:
                selected_logs.append(res)

    print()
    print("=== SUMMARY BY MODE ===")
    grouped = group_by_mode(all_results)
    for mode in sorted(grouped.keys()):
        s = summarize(grouped[mode])
        print(f"\n[{mode}]")
        for k, v in s.items():
            print(f"{k}: {v}")

    summary_mode_path = f"{args.out_prefix}_summary_by_mode.csv"
    summary_formula_path = f"{args.out_prefix}_summary_by_formula.csv"
    logs_path = f"{args.out_prefix}_logs.jsonl"

    save_summary_by_mode(summary_mode_path, all_results)
    save_summary_by_formula(summary_formula_path, all_results)
    save_logs(logs_path, selected_logs)

    print()
    print("=== FILES WRITTEN ===")
    print(summary_mode_path)
    print(summary_formula_path)
    print(logs_path)

    print()
    print("=== HOW TO READ ===")
    print("random = выбор переменных без понимания будущего L.")
    print("greedy_1 = локально лучший выбор.")
    print("lookahead_N = прогноз N шагов будущих изменений ограничений.")
    print("dpll_control = контрольный SAT solver с откатом.")
    print()
    print("Если lookahead_N растёт по success_rate относительно greedy_1,")
    print("это поддерживает идею: важна не просто локальная проверка L,")
    print("а прогноз цепочки будущих L-состояний.")
    print()
    print("Если greedy_1 хуже random, это важный знак:")
    print("локально хорошее решение может вести в плохое будущее L.")


if __name__ == "__main__":
    main()
