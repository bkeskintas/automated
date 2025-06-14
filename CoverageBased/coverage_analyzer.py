import os
import json
import matplotlib.pyplot as plt
from tqdm import tqdm
import sys

def plot_coverage_curve(progress_dict, output_path, title):
    # Step isimlerini sıralayıp verileri hazırla
    steps = sorted(progress_dict.keys(), key=lambda x: int(x.split("_")[1]))
    values = [progress_dict[step]["coverage_percent"] for step in steps]
    x_values = list(range(len(values)))  # 0, 1, 2, ...

    plt.figure(figsize=(14, 7))
    plt.plot(x_values, values, marker='o')
    plt.title(title)
    plt.xlabel("Test Index (Step)")
    plt.ylabel("Coverage (%)")
    plt.grid(True)

    # Sadece 3 adımda bir x etiketi göster
    xtick_positions = list(range(0, len(x_values), 3))
    plt.xticks(xtick_positions)

    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()

def compute_auc(progress_dict):
    steps = sorted(progress_dict.keys(), key=lambda x: int(x.split("_")[1]))
    values = [progress_dict[step]["coverage_percent"] for step in steps]
    return sum(values) / len(values) if values else 0.0, values

def analyze_run(base_run_dir):
    print(f"\n📂 Analyzing folder: {base_run_dir}")
    all_results = {}
    auc_scores = {}

    name_map = {
        "strategy1": "TF-IDF Based",
        "strategy2": "Class Diversity",
        "strategy3": "Cross-Class Alternation",
        "strategy4": "Edge-Normal Alternation",
        "strategy5": "Regression Spread",
        "combined": "Combined Strategy"
    }

    strategy_dirs = [d for d in os.listdir(base_run_dir)
                     if os.path.isdir(os.path.join(base_run_dir, d))]

    for strat in tqdm(strategy_dirs, desc="📊 Loading strategies"):
        path = os.path.join(base_run_dir, strat, "coverage_progress.json")
        if os.path.exists(path):
            with open(path, "r") as f:
                progress = json.load(f)
            all_results[strat] = progress

            auc, values = compute_auc(progress)
            auc_scores[strat] = (auc, values)

            display_name = name_map.get(strat, strat)
            plot_path = os.path.join(base_run_dir, strat, "coverage_curve.png")
            plot_coverage_curve(progress, plot_path, f"Coverage Progress - {display_name}")
        else:
            print(f"⚠️ Skipping {strat} (no coverage_progress.json found)")

    if not all_results:
        print("❌ No strategies found with valid coverage data.")
        return

    # Combined plot with AUCs
    sorted_strats = sorted(auc_scores.items(), key=lambda x: x[1][0], reverse=True)

    plt.figure(figsize=(18, 10))
    for strat_name, (auc, values) in sorted_strats:
        readable_name = name_map.get(strat_name, strat_name)
        label = f"{readable_name} (AUC: {auc:.2f})"
        plt.plot(range(len(values)), values, marker='o', label=label)

    plt.title("Combined Coverage Comparison")
    plt.xlabel("Test Count")
    plt.ylabel("Coverage (%)")
    plt.grid(True)
    plt.xticks(range(0, max(len(v[1]) for v in auc_scores.values()), 3))
    plt.legend(loc='center left', bbox_to_anchor=(1, 0.5))
    plt.tight_layout(rect=[0, 0, 0.85, 1])
    plt.savefig(os.path.join(base_run_dir, "coverage_comparison.png"))
    plt.close()

    # Console output
    print("\n📊 AUC Scores (Higher is Better):")
    for strat_name, (auc, _) in sorted_strats:
        print(f"  {name_map.get(strat_name, strat_name):<30} → AUC: {auc:.2f}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_dir = sys.argv[1]
    else:
        run_dir = input("Enter run folder path (e.g., runs/run_20250613_213000): ").strip()

    if not os.path.isdir(run_dir):
        print(f"❌ Folder not found: {run_dir}")
    else:
        analyze_run(run_dir)
