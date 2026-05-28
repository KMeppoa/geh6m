#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
sat_lg_test_v4_parallel_cpu.py

SAT-эксперимент для идеи:
    L = локальное состояние ограничений
    G = глобальная согласованность всей формулы

Почему v3:
    v1/v2 смотрели в основном на локальное L:
        сколько клауз выполнено / сломано / неизвестно

    Но SAT может обманывать:
        локально хороший выбор может глобально ломать систему.

    Поэтому добавляем G-оценку:
        - сколько клауз стало опасными
        - сколько unit clauses появилось
        - сколько переменных стали вынужденными
        - сколько свободы выбора осталось
        - есть ли конфликт при unit propagation
        - насколько выбор сохраняет глобальную совместимость

Режимы:
    random
    greedy_L
    lookahead_L_2
    lookahead_L_3
    greedy_LG
    lookahead_LG_2
    lookahead_LG_3
    dpll_control

Простой запуск:
    python sat_lg_test_v4_parallel_cpu.py --formulas 50 --vars 20 --clauses 80 --k 3 --max-steps 80 --lookaheads 2,3

Средний запуск:
    python sat_lg_test_v4_parallel_cpu.py --formulas 100 --vars 30 --clauses 120 --k 3 --max-steps 120 --lookaheads 2,3

Файлы:
    sat_lg_v4_parallel_summary_by_mode.csv
    sat_lg_v4_parallel_summary_by_formula.csv
    sat_lg_v4_parallel_logs.jsonl
"""

import argparse
import csv
import json
import random
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
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
# SAT utilities
# -----------------------------

def generate_random_k_sat(n_vars, n_clauses, k, seed):
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
    var = abs(lit)
    if var not in assignment:
        return None
    val = assignment[var]
    return val if lit > 0 else (not val)


def clause_details(clause, assignment):
    """
    Возвращает:
        status:
            sat / unsat / unknown
        unknown_count:
            сколько литералов ещё не назначено
        false_count:
            сколько литералов уже false
    """
    unknown_count = 0
    false_count = 0

    for lit in clause:
        val = lit_value(lit, assignment)
        if val is True:
            return "sat", unknown_count, false_count
        elif val is None:
            unknown_count += 1
        else:
            false_count += 1

    if unknown_count == 0:
        return "unsat", unknown_count, false_count

    return "unknown", unknown_count, false_count


def clause_status(clause, assignment):
    return clause_details(clause, assignment)[0]


def formula_stats(formula, assignment):
    sat = 0
    unsat = 0
    unknown = 0
    unit = 0
    dangerous = 0

    for clause in formula:
        st, unknown_count, false_count = clause_details(clause, assignment)

        if st == "sat":
            sat += 1
        elif st == "unsat":
            unsat += 1
        else:
            unknown += 1
            if unknown_count == 1:
                unit += 1
            if unknown_count <= 1:
                dangerous += 1

    return {
        "sat": sat,
        "unsat": unsat,
        "unknown": unknown,
        "unit": unit,
        "dangerous": dangerous,
        "total": len(formula),
    }


def is_formula_satisfied(formula, assignment, n_vars):
    if len(assignment) < n_vars:
        # Для обычных агентов требуем полный assignment.
        return False
    return all(clause_status(c, assignment) == "sat" for c in formula)


def verify_assignment(formula, assignment, n_vars):
    logs = []
    logs.append(f"START verify: assigned={len(assignment)}/{n_vars}")
    stats = formula_stats(formula, assignment)
    logs.append(f"stats={stats}")
    success = is_formula_satisfied(formula, assignment, n_vars)
    logs.append(f"FINISH verify: success={success}")
    return success, logs


def complete_assignment(partial_assignment, n_vars):
    full = dict(partial_assignment)
    for v in range(1, n_vars + 1):
        if v not in full:
            full[v] = False
    return full


def unassigned_vars(n_vars, assignment):
    return [v for v in range(1, n_vars + 1) if v not in assignment]


def possible_actions(n_vars, assignment):
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
# Unit propagation: G-signal
# -----------------------------

def simplify_formula(formula, assignment):
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

        if satisfied:
            continue

        if not new_clause:
            return None

        simplified.append(new_clause)

    return simplified


def find_unit_clause(simplified):
    for clause in simplified:
        if len(clause) == 1:
            lit = clause[0]
            return abs(lit), lit > 0
    return None


def unit_propagate(formula, assignment, n_vars, max_forced=10000):
    """
    Глобальная проверка G:
        если текущий выбор создаёт вынужденные переменные,
        применяем их.

    Возвращает:
        conflict: True/False
        propagated_assignment
        forced_count
    """
    assignment = dict(assignment)
    forced_count = 0

    while forced_count < max_forced:
        simplified = simplify_formula(formula, assignment)

        if simplified is None:
            return True, assignment, forced_count

        if not simplified:
            return False, assignment, forced_count

        unit = find_unit_clause(simplified)
        if unit is None:
            return False, assignment, forced_count

        v, val = unit

        if v in assignment:
            if assignment[v] != val:
                return True, assignment, forced_count
            return False, assignment, forced_count

        assignment[v] = val
        forced_count += 1

    return False, assignment, forced_count


# -----------------------------
# L score and LG score
# -----------------------------

def score_L(formula, assignment, n_vars):
    """
    Локальная оценка L.
    Меньше = лучше.
    """
    st = formula_stats(formula, assignment)

    return (
        st["unsat"] * 100000
        + st["unknown"] * 10
        + st["dangerous"] * 5
        + st["unit"] * 3
        - st["sat"]
    )


def variable_freedom_score(formula, assignment, n_vars):
    """
    Оценка свободы:
        сколько переменных ещё не назначено и насколько они участвуют
        в неизвестных клаузах.

    Идея:
        если много неизвестных клауз зависят от малой группы переменных,
        система становится более зажатой.
    """
    unassigned = set(unassigned_vars(n_vars, assignment))
    if not unassigned:
        return 0

    appearances = {v: 0 for v in unassigned}

    for clause in formula:
        st = clause_status(clause, assignment)
        if st == "unknown":
            for lit in clause:
                v = abs(lit)
                if v in unassigned:
                    appearances[v] += 1

    if not appearances:
        return 0

    max_pressure = max(appearances.values())
    avg_pressure = sum(appearances.values()) / len(appearances)

    # Большое давление = меньше свободы = хуже.
    return max_pressure * 3 + avg_pressure


def score_LG(formula, assignment, n_vars):
    """
    Глобальная оценка LG.
    Меньше = лучше.

    Смотрим не только локальную статистику,
    но и глобальные последствия через unit propagation.
    """
    conflict, propagated, forced_count = unit_propagate(formula, assignment, n_vars)

    if conflict:
        return 10_000_000

    st_before = formula_stats(formula, assignment)
    st_after = formula_stats(formula, propagated)

    freedom = variable_freedom_score(formula, propagated, n_vars)

    # Идея:
    # - конфликт очень плохо
    # - опасные/forcing состояния могут быть как полезными, так и опасными,
    #   поэтому штрафуем их умеренно
    # - выполненные клаузы хорошо
    # - слишком большое давление на оставшиеся переменные плохо
    # - forced_count иногда хорошо, потому что раскрывает структуру,
    #   но если оно создаёт опасность, stats_after это покажет.
    return (
        st_after["unsat"] * 1_000_000
        + st_after["unknown"] * 10
        + st_after["dangerous"] * 8
        + st_after["unit"] * 4
        + freedom * 2
        - st_after["sat"] * 2
        - forced_count * 1
    )


# -----------------------------
# Search modes
# -----------------------------

def random_search_sat(formula, n_vars, formula_seed, max_steps, seed):
    rng = random.Random(seed)
    assignment = {}
    logs = [f"START random: n_vars={n_vars}"]

    for step in range(1, min(max_steps, n_vars) + 1):
        if is_formula_satisfied(formula, assignment, n_vars):
            logs.append(f"GOAL random: steps={step-1}")
            return RunResult(formula_seed, "random", True, step - 1, assignment, logs)

        actions = possible_actions(n_vars, assignment)
        if not actions:
            break

        action = rng.choice(actions)
        assignment = apply_action(assignment, action)
        logs.append(
            f"step={step}: choose x{action[0]}={action[1]} | "
            f"L_stats={formula_stats(formula, assignment)}"
        )

    success = is_formula_satisfied(formula, assignment, n_vars)
    logs.append(f"FINISH random: success={success}, assigned={len(assignment)}/{n_vars}, stats={formula_stats(formula, assignment)}")
    return RunResult(formula_seed, "random", success, len(assignment), assignment, logs)


def evaluate_future(formula, n_vars, assignment, depth, score_kind):
    if is_formula_satisfied(formula, complete_assignment(assignment, n_vars), n_vars):
        # Осторожно: partial может быть уже enough после completion.
        # Это хороший знак.
        return -1000000

    if score_kind == "L":
        base_score = score_L(formula, assignment, n_vars)
    else:
        base_score = score_LG(formula, assignment, n_vars)

    # Конфликт/очень плохое состояние
    if base_score >= 10_000_000:
        return base_score

    if depth <= 0:
        return base_score

    actions = possible_actions(n_vars, assignment)
    if not actions:
        return base_score

    ranked = []
    for action in actions:
        new_asg = apply_action(assignment, action)
        local_score = score_LG(formula, new_asg, n_vars) if score_kind == "LG" else score_L(formula, new_asg, n_vars)
        ranked.append((local_score, action, new_asg))

    ranked.sort(key=lambda x: (x[0], x[1][0], x[1][1]))

    # Ограничитель ветвления, чтобы скрипт не завис.
    BRANCH_CAP = 8
    ranked = ranked[:BRANCH_CAP]

    best = inf
    for local_score, action, new_asg in ranked:
        future = evaluate_future(formula, n_vars, new_asg, depth - 1, score_kind)
        if future < best:
            best = future

    return best


def search_sat(formula, n_vars, formula_seed, mode, score_kind, lookahead_depth, max_steps):
    assignment = {}
    logs = [f"START {mode}: score_kind={score_kind}, lookahead={lookahead_depth}"]

    for step in range(1, min(max_steps, n_vars) + 1):
        full_candidate = complete_assignment(assignment, n_vars)
        if is_formula_satisfied(formula, full_candidate, n_vars):
            logs.append(f"GOAL {mode}: partial assignment can be completed, steps={step-1}")
            return RunResult(formula_seed, mode, True, step - 1, full_candidate, logs)

        actions = possible_actions(n_vars, assignment)
        if not actions:
            break

        scored = []
        for action in actions:
            new_asg = apply_action(assignment, action)

            score = evaluate_future(
                formula,
                n_vars,
                new_asg,
                depth=lookahead_depth - 1,
                score_kind=score_kind,
            )

            scored.append((score, action, new_asg))

        scored.sort(key=lambda x: (x[0], x[1][0], x[1][1]))

        best_score, best_action, best_assignment = scored[0]

        # Для LG можно сразу применить вынужденные переменные.
        # Это делает G активным, а не только оценочным.
        if score_kind == "LG":
            conflict, propagated, forced_count = unit_propagate(formula, best_assignment, n_vars)
            if not conflict:
                best_assignment = propagated
            else:
                forced_count = 0
        else:
            forced_count = 0

        assignment = best_assignment

        top_preview = [(round(s, 2), f"x{a[0]}={a[1]}") for s, a, _ in scored[:5]]
        logs.append(
            f"step={step}: chosen=x{best_action[0]}={best_action[1]}, "
            f"score={round(best_score,2)}, forced={forced_count}, "
            f"top5={top_preview}, stats={formula_stats(formula, assignment)}"
        )

        stats = formula_stats(formula, assignment)
        if stats["unsat"] > 0:
            logs.append(f"dead_branch: unsat appeared at step={step}")
            break

    full_assignment = complete_assignment(assignment, n_vars)
    success = is_formula_satisfied(formula, full_assignment, n_vars)
    logs.append(f"FINISH {mode}: success={success}, assigned={len(assignment)}/{n_vars}, stats={formula_stats(formula, full_assignment)}")
    return RunResult(formula_seed, mode, success, len(assignment), full_assignment, logs)


# -----------------------------
# DPLL control
# -----------------------------

def choose_variable_dpll(simplified, assignment, n_vars):
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
    node_counter[0] += 1
    if node_counter[0] > max_nodes:
        return None

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
        return assignment

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

    full = complete_assignment(result, n_vars)
    success, verify_logs = verify_assignment(formula, full, n_vars)
    logs.extend(verify_logs)
    logs.append(
        f"FINISH dpll_control: SAT={success}, nodes={node_counter[0]}, "
        f"partial_assigned={len(result)}, full_assigned={len(full)}"
    )
    return RunResult(formula_seed, "dpll_control", success, node_counter[0], full, logs)




# -----------------------------
# Parallel worker
# -----------------------------

def solve_one_formula_task(task):
    """
    Решает одну SAT-формулу полностью.

    Важно:
    - параллельность идёт между формулами;
    - внутри каждой формулы L/G-логика не меняется;
    - G остаётся глобальной согласованностью всей конкретной формулы.
    """
    (
        formula_seed,
        n_vars,
        n_clauses,
        k,
        max_steps,
        max_dpll_nodes,
        base_seed,
        lookaheads,
        log_limit_per_formula,
    ) = task

    formula = generate_random_k_sat(
        n_vars=n_vars,
        n_clauses=n_clauses,
        k=k,
        seed=formula_seed,
    )

    results = []

    dpll_res = dpll_control(
        formula,
        n_vars=n_vars,
        formula_seed=formula_seed,
        max_nodes=max_dpll_nodes,
    )
    results.append(dpll_res)

    rnd = random_search_sat(
        formula,
        n_vars=n_vars,
        formula_seed=formula_seed,
        max_steps=max_steps,
        seed=base_seed * 1000000 + formula_seed,
    )
    results.append(rnd)

    greedy_l = search_sat(
        formula, n_vars, formula_seed,
        mode="greedy_L",
        score_kind="L",
        lookahead_depth=1,
        max_steps=max_steps,
    )
    results.append(greedy_l)

    greedy_lg = search_sat(
        formula, n_vars, formula_seed,
        mode="greedy_LG",
        score_kind="LG",
        lookahead_depth=1,
        max_steps=max_steps,
    )
    results.append(greedy_lg)

    for depth in lookaheads:
        l_res = search_sat(
            formula, n_vars, formula_seed,
            mode=f"lookahead_L_{depth}",
            score_kind="L",
            lookahead_depth=depth,
            max_steps=max_steps,
        )
        results.append(l_res)

        lg_res = search_sat(
            formula, n_vars, formula_seed,
            mode=f"lookahead_LG_{depth}",
            score_kind="LG",
            lookahead_depth=depth,
            max_steps=max_steps,
        )
        results.append(lg_res)

    selected_logs = results[:log_limit_per_formula]
    return formula_seed, results, selected_logs


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

    parser.add_argument("--formulas", type=int, default=50)
    parser.add_argument("--vars", type=int, default=20)
    parser.add_argument("--clauses", type=int, default=80)
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--max-steps", type=int, default=80)
    parser.add_argument("--max-dpll-nodes", type=int, default=200000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--lookaheads", type=str, default="2,3")
    parser.add_argument("--log-limit", type=int, default=20)
    parser.add_argument("--out-prefix", type=str, default="sat_lg_v4_parallel")
    parser.add_argument("--workers", type=int, default=max(1, min(2, (os.cpu_count() or 2))))

    args = parser.parse_args()

    lookaheads = [int(x.strip()) for x in args.lookaheads.split(",") if x.strip()]

    print("=== CONFIG SAT LG V4 PARALLEL CPU ===")
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

    tasks = []
    for i in range(args.formulas):
        formula_seed = args.seed + i
        tasks.append((
            formula_seed,
            args.vars,
            args.clauses,
            args.k,
            args.max_steps,
            args.max_dpll_nodes,
            args.seed,
            lookaheads,
            2,  # log_limit_per_formula
        ))

    print(f"parallel workers={args.workers}")
    print()

    completed = 0

    if args.workers <= 1:
        for task in tasks:
            formula_seed, results, logs = solve_one_formula_task(task)

            all_results.extend(results)

            for item in logs:
                if len(selected_logs) < args.log_limit:
                    selected_logs.append(item)

            completed += 1

            if completed == 1 or completed % 10 == 0 or completed == args.formulas:
                print(f"done {completed}/{args.formulas}, seed={formula_seed}")
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            future_to_seed = {
                executor.submit(solve_one_formula_task, task): task[0]
                for task in tasks
            }

            for future in as_completed(future_to_seed):
                formula_seed = future_to_seed[future]

                try:
                    seed, results, logs = future.result()
                except Exception as e:
                    print(f"ERROR seed={formula_seed}: {e}")
                    continue

                all_results.extend(results)

                for item in logs:
                    if len(selected_logs) < args.log_limit:
                        selected_logs.append(item)

                completed += 1

                if completed == 1 or completed % 10 == 0 or completed == args.formulas:
                    print(f"done {completed}/{args.formulas}, seed={seed}")

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
    print("L  = локальная оценка ограничений.")
    print("LG = локальная оценка + глобальная согласованность через unit propagation.")
    print()
    print("Главное сравнение:")
    print("greedy_L       vs greedy_LG")
    print("lookahead_L_2  vs lookahead_LG_2")
    print("lookahead_L_3  vs lookahead_LG_3")
    print()
    print("Если LG лучше L, это поддерживает твою идею:")
    print("нужна не только локальная L-логика, но и глобальная G-согласованность.")


if __name__ == "__main__":
    main()
