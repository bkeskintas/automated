import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
import json
import matplotlib.pyplot as plt
from datetime import datetime
from tqdm import tqdm
import sys
##Runner and Analyzer
PROJECT_DIR = "./PasswordManagerAPI" #"./spring-petclinic" 
MVNW = "mvnw.cmd"
JACOCO_EXEC = os.path.join(PROJECT_DIR, "target", "jacoco.exec")
JACOCO_XML = os.path.join(PROJECT_DIR, "target", "site", "jacoco", "jacoco.xml")

RUN_BASE_DIR = "./module_coverage_runs"
os.makedirs(RUN_BASE_DIR, exist_ok=True)

def extract_module_wise_coverage(xml_path):
    tree = ET.parse(xml_path)
    root = tree.getroot()
    module_coverage = {}

    for package in root.findall("package"):
        pkg_name = package.attrib["name"]
        for cls in package.findall("class"):
            class_name = cls.attrib["name"]
            fq_class_name = f"{pkg_name}/{class_name}".replace("/", ".")
            for counter in cls.findall("counter"):
                if counter.attrib["type"] == "LINE":
                    covered = int(counter.attrib["covered"])
                    missed = int(counter.attrib["missed"])
                    module_coverage[fq_class_name] = {
                        "covered": covered,
                        "missed": missed,
                        "total": covered + missed
                    }
    return module_coverage

def extract_total_coverage(xml_path):
    tree = ET.parse(xml_path)
    root = tree.getroot()
    total_covered = total_missed = 0
    for counter in root.findall(".//counter[@type='LINE']"):
        covered = int(counter.attrib["covered"])
        missed = int(counter.attrib["missed"])
        total_covered += covered
        total_missed += missed
    total = total_covered + total_missed
    percent = (total_covered / total) * 100 if total > 0 else 0.0
    return round(percent, 2)

def run_test_order(test_file, run_dir):
    strat_name = os.path.splitext(os.path.basename(test_file))[0]
    STRAT_DIR = os.path.join(run_dir, strat_name)
    XML_DIR = os.path.join(STRAT_DIR, "xmls")
    LOG_DIR = os.path.join(STRAT_DIR, "logs")
    os.makedirs(XML_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)

    with open(test_file, "r", encoding="utf-8") as f:
        all_tests = [line.strip() for line in f if line.strip()]

    cumulative_tests = []
    total_coverage = {}
    module_coverage_all = {}

    for i, test in enumerate(tqdm(all_tests, desc=f"[{strat_name}]")):
        cumulative_tests.append(test)
        test_arg = ",".join(cumulative_tests)

        mvn_command = [MVNW]
        if i == 0:
            mvn_command.append("clean")
        mvn_command += ["test", "jacoco:report", f"-Dtest={test_arg}"]

        log_path = os.path.join(LOG_DIR, f"step_{i}.log")
        with open(log_path, "w", encoding="utf-8") as log_file:
            process = subprocess.Popen(
                mvn_command, cwd=PROJECT_DIR,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                shell=True, universal_newlines=True
            )
            for line in process.stdout:
                log_file.write(line)
            process.wait()

        subprocess.run(" ".join([MVNW, "jacoco:report"]), cwd=PROJECT_DIR, shell=True)

        if os.path.exists(JACOCO_XML):
            shutil.copy(JACOCO_XML, os.path.join(XML_DIR, f"step_{i}.xml"))
            total_coverage[f"Step_{i}"] = extract_total_coverage(JACOCO_XML)
            module_coverage_all[f"Step_{i}"] = extract_module_wise_coverage(JACOCO_XML)

    with open(os.path.join(STRAT_DIR, "total_coverage.json"), "w") as f:
        json.dump(total_coverage, f, indent=2)
    with open(os.path.join(STRAT_DIR, "module_coverage.json"), "w") as f:
        json.dump(module_coverage_all, f, indent=2)

    plt.plot(range(len(total_coverage)), list(total_coverage.values()), marker='o')
    plt.title(f"Total Coverage Progress - {strat_name}")
    plt.xlabel("Test Step")
    plt.ylabel("Coverage %")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(STRAT_DIR, "coverage_curve.png"))
    plt.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_test_orders_from_folder.py <input_folder>")
        sys.exit(1)

    selected_folder = sys.argv[1]

    if not os.path.isdir(selected_folder):
        print(f"Error: Provided folder does not exist: {selected_folder}")
        sys.exit(1)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(RUN_BASE_DIR, f"{os.path.basename(selected_folder)}_{timestamp}")
    os.makedirs(output_dir, exist_ok=True)

    txt_files = [f for f in os.listdir(selected_folder)
                 if (f.startswith("tests_") or f == "combined_risk.txt") and f.endswith(".txt")]

    if not txt_files:
        print(f"No valid test files found in {selected_folder}")
        sys.exit(1)

    for file in txt_files:
        run_test_order(os.path.join(selected_folder, file), output_dir)
