import os
import json
import matplotlib.pyplot as plt
from tqdm import tqdm

# 👇 Klasör adını buraya yaz (örnek: "runs/run_20240517_225000")
BASE_RUN_DIR = "runs/run_20250517_220118"

def plot_coverage_curve(progress_dict, output_path, title):
    values = [info["coverage_percent"] for info in progress_dict.values()]
    plt.figure(figsize=(10, 6))
    plt.plot(range(len(values)), values, marker='o')
    plt.title(title)
    plt.xlabel("Test Index (Step)")
    plt.ylabel("Coverage (%)")
    plt.grid(True)
    plt.xticks(range(len(values)))
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()

def analyze_run(base_run_dir):
    print(f"\n📂 Analyzing folder: {base_run_dir}")
    all_results = {}

    # 👇 Optional: Strategy folder name → readable name
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

            # Per-strategy plot
            plot_path = os.path.join(base_run_dir, strat, "coverage_curve.png")
            display_name = name_map.get(strat, strat)
            plot_coverage_curve(progress, plot_path, f"Coverage Progress - {display_name}")
        else:
            print(f"⚠️ Skipping {strat} (no coverage_progress.json found)")

    # Combined plot
    # Combined plot with readable names and better legend layout
    plt.figure(figsize=(14, 7))  # genişliği biraz artır
    for strat_name, progress in all_results.items():
        readable_name = STRATEGY_NAME_MAP.get(strat_name, strat_name)
        values = [progress[f"Step_{i}"]["coverage_percent"] for i in range(len(progress))]
        plt.plot(range(len(values)), values, marker='o', label=readable_name)

    plt.title("Combined Coverage Comparison")
    plt.xlabel("Test Count")
    plt.ylabel("Coverage (%)")
    plt.grid(True)
    plt.xticks(range(max(len(progress) for progress in all_results.values())))
    
    # Legend sağa taşındı, dikey yerleşim verildi
    plt.legend(loc='center left', bbox_to_anchor=(1, 0.5))
    plt.tight_layout(rect=[0, 0, 0.8, 1])  # sağdan boşluk bırak
    plt.savefig(os.path.join(BASE_RUN_DIR, "coverage_comparison.png"))
    plt.close()


if __name__ == "__main__":
    if not os.path.isdir(BASE_RUN_DIR):
        print(f"❌ Folder not found: {BASE_RUN_DIR}")
    else:
        analyze_run(BASE_RUN_DIR)
