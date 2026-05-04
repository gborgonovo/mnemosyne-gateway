#!/usr/bin/env python3
"""
Visualizza le curve di decay per i parametri attuali di settings.yaml.
Uso: python3 scripts/simulate_decay.py
"""
import sys
import os
import math
import yaml

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.yaml')

def load_config():
    with open(CONFIG_PATH, 'r') as f:
        return yaml.safe_load(f)

def half_life_days(rate):
    return -0.693 / (math.log(1 - rate) * 24)

def simulate(rate, total_days=180, step_days=7):
    activation = 1.0
    points = [(0, activation)]
    hours_per_step = step_days * 24
    steps = total_days // step_days
    for _ in range(steps):
        activation *= (1 - rate) ** hours_per_step
        points.append((points[-1][0] + step_days, activation))
    return points

def bar(value, width=30):
    filled = int(round(value * width))
    return "█" * filled + "░" * (width - filled)

def main():
    config = load_config()
    attn = config.get("attention", {})
    decay_rates = attn.get("decay_rates", {
        "Node": 0.0025, "Goal": 0.00026, "Task": 0.00045, "Observation": 0.004,
    })
    dormant_cfg = attn.get("dormant", {})
    dormant_threshold = 0.2
    dormant_ceiling   = dormant_cfg.get("ceiling", 0.25)

    boost_weights = attn.get("boost_weights", {
        "file_edit": 0.6, "mcp_query": 0.2, "proximity": 0.05,
    })

    print("=" * 62)
    print("  MNEMOSYNE — Simulazione Decay")
    print("=" * 62)
    print(f"\n  Boost per interazione:")
    for itype, w in boost_weights.items():
        print(f"    {itype:<12} +{w}")

    print(f"\n  Soglie: dormante < {dormant_threshold}  |  resurface ceiling = {dormant_ceiling}")

    for node_type, rate in decay_rates.items():
        hl = half_life_days(rate)
        print(f"\n{'─'*62}")
        print(f"  {node_type}  (rate/h={rate}, mezza vita={hl:.1f} giorni)")
        print(f"{'─'*62}")

        curve = simulate(rate)
        dormant_marked = False
        for day, val in curve:
            marker = ""
            if val < dormant_threshold and not dormant_marked:
                marker = " ← soglia DORMIENTE"
                dormant_marked = True
            print(f"  Giorno {day:4d}  [{bar(val)}]  {val:.3f}{marker}")

    print("\n" + "=" * 62)
    print("  Per modificare i parametri: config/settings.yaml → attention.decay_rates")
    print("=" * 62)

if __name__ == "__main__":
    main()
