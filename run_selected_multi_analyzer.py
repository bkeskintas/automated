import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
import json
import matplotlib.pyplot as plt
from datetime import datetime
from tqdm import tqdm

# İsim eşlemesi
STRATEGY_NAME_MAP = {
    "strategy1": "TF-IDF Based",
    "strategy2": "Name-based Heuristic",
    "strategy3": "Module Diversity First",
    "strategy4": "Alternate Positive/Edge",
    "strategy5": "Even Distribution of Regression",
    "combined": "Combined Average"
}

def extract_covered_lines(xml_path):
    tree = ET.parse(xml_path)
    root = tree.getroot()
    total_covered = 0
    total_missed = 0
    for counter in root.findall(".//counter[@type='LINE']"):
        covered = int(counter.attrib["covered"])
        missed = int(counter.attrib["missed"])
        total_covered += covered
        total_missed += missed
    total = total_covered + total_missed
    percent = (total_covered / total) * 100 if total > 0 else 0.0
    return {
        "covered_lines": total_covered,
        "missed_lines": total_missed,
        "total_lines": total,
        "coverage_percent": round(percent, 2)
    }

def plot_coverage_curve(progress_dict, output_path, strategy_title):
    values = [info["coverage_percent"] for info in progress_dict.values()]
    plt.figure(figsize=(10, 6))
    plt.plot(range(len(values)), values, marker='o')
    plt.title(f"Cumulative Code Coverage Progress - {strategy_title}")
    plt.xlabel("Test Index (Step)")
    plt.ylabel("Coverage (%)")
    plt.grid(True)
    plt.xticks(range(len(values)))
    plt.tight_layout()
    plt.savefig(output_path)

def run_strategy(args):
    strat_file, strat_name, BASE_RUN_DIR = args
    strategy_title = STRATEGY_NAME_MAP.get(strat_name, strat_name)
    PROJECT_DIR = "./PasswordManagerAPI"
    MVNW = "mvnw.cmd"
    JACOCO_EXEC = os.path.join(PROJECT_DIR, "target", "jacoco.exec")
    JACOCO_XML = os.path.join(PROJECT_DIR, "target", "site", "jacoco", "jacoco.xml")

    STRAT_DIR = os.path.join(BASE_RUN_DIR, strat_name)
    EXEC_DIR = os.path.join(STRAT_DIR, "execs")
    XML_DIR = os.path.join(STRAT_DIR, "xmls")
    LOG_DIR = os.path.join(STRAT_DIR, "logs")
    os.makedirs(EXEC_DIR, exist_ok=True)
    os.makedirs(XML_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)

    shutil.copy(strat_file, os.path.join(STRAT_DIR, "used_test_order.txt"))
    with open(strat_file, "r", encoding="utf-8") as f:
        all_tests = [line.strip() for line in f if line.strip()]

    cumulative_tests = []
    coverage_progress = {}
    failed_steps = []

    for i, test in enumerate(tqdm(all_tests, desc=f"[{strategy_title}]")):
        cumulative_tests.append(test)
        test_arg = ",".join(cumulative_tests)

        success = False
        for attempt in range(1, 4):
            print(f"[{strategy_title}] Step {i} Attempt {attempt}")
            mvn_command = [MVNW]
            if i == 0 and attempt == 1:
                mvn_command.append("clean")
            mvn_command += ["test", "jacoco:report", f"-Dtest={test_arg}"]

            process = subprocess.Popen(
                mvn_command, cwd=PROJECT_DIR,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                shell=True, universal_newlines=True
            )

            log_path = os.path.join(LOG_DIR, f"step_{i}_attempt{attempt}.log")
            with open(log_path, "w", encoding="utf-8") as log_file:
                for line in process.stdout:
                    log_file.write(line)

            if process.wait() != 0:
                continue

            exec_dest = os.path.join(EXEC_DIR, f"step_{i}.exec")
            if os.path.exists(JACOCO_EXEC):
                shutil.copy(JACOCO_EXEC, exec_dest)
            else:
                continue

            subprocess.run(" ".join([MVNW, "jacoco:report"]), cwd=PROJECT_DIR, shell=True)

            xml_dest = os.path.join(XML_DIR, f"step_{i}.xml")
            if os.path.exists(JACOCO_XML):
                shutil.copy(JACOCO_XML, xml_dest)
                percent_data = extract_covered_lines(xml_dest)
                coverage_progress[f"Step_{i}"] = percent_data
                success = True
                break

        if not success:
            failed_steps.append(f"Step_{i}")
            print(f"❌ [{strategy_title}] Step {i} failed after 3 attempts.")

    with open(os.path.join(STRAT_DIR, "coverage_progress.json"), "w") as f:
        json.dump(coverage_progress, f, indent=2)
    with open(os.path.join(STRAT_DIR, "failed_steps.json"), "w") as f:
        json.dump(failed_steps, f, indent=2)

    result_path = os.path.join(STRAT_DIR, "result.txt")
    with open(result_path, "w", encoding="utf-8") as f:
        f.write("=== COVERAGE RESULTS ===\n")
        for step, data in coverage_progress.items():
            f.write(f"{step}: {data['coverage_percent']:.2f}% covered | "
                    f"Covered: {data['covered_lines']}, "
                    f"Missed: {data['missed_lines']}, "
                    f"Total: {data['total_lines']}\n")
        f.write("\n=== FAILED STEPS ===\n")
        for step in failed_steps:
            f.write(step + "\n")

    plot_coverage_curve(coverage_progress, os.path.join(STRAT_DIR, "coverage_curve.png"), strategy_title)
    return strat_name, coverage_progress

def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    BASE_RUN_DIR = os.path.join("runs", f"run_{timestamp}")
    os.makedirs(BASE_RUN_DIR, exist_ok=True)

    strategies = [
        "sorted_test_strategy1.txt",
        "sorted_test_strategy2.txt",
        "sorted_test_strategy3.txt",
        "sorted_test_strategy4.txt",
        "sorted_test_strategy5.txt",
        "sorted_test_combined.txt"
    ]

    args = [(file, file.replace("sorted_test_", "").replace(".txt", ""), BASE_RUN_DIR) for file in strategies]

    all_results = {}
    for arg in tqdm(args, desc="==> Sequential Strategy Execution"):
        strat_name, result = run_strategy(arg)
        all_results[strat_name] = result

    with open(os.path.join(BASE_RUN_DIR, "coverage_results.json"), "w") as f:
        json.dump(all_results, f, indent=2)

    # Individually draw each strategy again with readable titles
    for strat_name, progress in all_results.items():
        readable_name = STRATEGY_NAME_MAP.get(strat_name, strat_name)
        values = [progress[f"Step_{i}"]["coverage_percent"] for i in range(len(progress))]
        plt.figure(figsize=(10, 6))
        plt.plot(range(len(values)), values, marker='o')
        plt.title(f"Coverage Progress - {readable_name}")
        plt.xlabel("Test Index (Step)")
        plt.ylabel("Coverage (%)")
        plt.grid(True)
        plt.xticks(range(len(values)))
        plt.tight_layout()
        plt.savefig(os.path.join(BASE_RUN_DIR, strat_name, "coverage_curve.png"))
        plt.close()

    # Combined plot with readable names
    plt.figure(figsize=(12, 6))
    for strat_name, progress in all_results.items():
        readable_name = STRATEGY_NAME_MAP.get(strat_name, strat_name)
        values = [progress[f"Step_{i}"]["coverage_percent"] for i in range(len(progress))]
        plt.plot(range(len(values)), values, marker='o', label=readable_name)
    plt.title("Combined Coverage Comparison")
    plt.xlabel("Test Count")
    plt.ylabel("Coverage (%)")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(BASE_RUN_DIR, "coverage_comparison.png"))
    plt.close()

if __name__ == "__main__":
    main()
