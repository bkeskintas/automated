import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
import json
import matplotlib.pyplot as plt
from tqdm import tqdm
from datetime import datetime

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

def plot_coverage_curve(progress_dict, output_path):
    values = [info["coverage_percent"] for info in progress_dict.values()]
    plt.figure(figsize=(10, 6))
    plt.plot(range(len(values)), values, marker='o')
    plt.title("Cumulative Code Coverage Progress")
    plt.xlabel("Test Index (Step)")
    plt.ylabel("Coverage (%)")
    plt.grid(True)
    plt.xticks(range(len(values)))
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()

def run_strategy(args):
    strat_file, strat_name, BASE_RUN_DIR = args
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

    for i, test in enumerate(tqdm(all_tests, desc=f"[{strat_name}]")):
        cumulative_tests.append(test)
        test_arg = ",".join(cumulative_tests)

        success = False
        for attempt in range(1, 4):  # max 3 attempts
            print(f"[{strat_name}] Step {i} Attempt {attempt}")
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
            print(f"❌ [{strat_name}] Step {i} failed after 3 attempts.")

    # JSON kaydet
    with open(os.path.join(STRAT_DIR, "coverage_progress.json"), "w") as f:
        json.dump(coverage_progress, f, indent=2)
    with open(os.path.join(STRAT_DIR, "failed_steps.json"), "w") as f:
        json.dump(failed_steps, f, indent=2)

    # result.txt oluştur
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

    plot_coverage_curve(coverage_progress, os.path.join(STRAT_DIR, "coverage_curve.png"))
    return strat_name, coverage_progress

def resume_specific_strategies():
    # Buraya önceki run klasörünü yaz
    BASE_RUN_DIR = "runs/run_20250517_220118"  # örnek klasör, güncellemen gerekebilir

    strategies = [
        "sorted_test_strategy5.txt",
        "sorted_test_combined.txt"
    ]

    args = [(file, file.replace("sorted_test_", "").replace(".txt", ""), BASE_RUN_DIR) for file in strategies]

    all_results = {}
    for arg in tqdm(args, desc="==> RESUMING Selected Strategies"):
        strat_name, result = run_strategy(arg)
        all_results[strat_name] = result

    # Mevcut sonuçlarla birleştir
    results_path = os.path.join(BASE_RUN_DIR, "coverage_results.json")
    if os.path.exists(results_path):
        with open(results_path, "r") as f:
            existing = json.load(f)
    else:
        existing = {}

    existing.update(all_results)
    with open(results_path, "w") as f:
        json.dump(existing, f, indent=2)

    # Combined grafiği yeniden çiz
    plt.figure(figsize=(12, 6))
    for strat_name, progress in existing.items():
        values = [progress[f"Step_{i}"]["coverage_percent"] for i in range(len(progress))]
        plt.plot(range(len(values)), values, marker='o', label=strat_name)
    plt.title("Combined Coverage Comparison (Resumed)")
    plt.xlabel("Test Count")
    plt.ylabel("Coverage (%)")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(BASE_RUN_DIR, "coverage_comparison.png"))
    plt.close()

if __name__ == "__main__":
    resume_specific_strategies()
