import os
import json
import re
import matplotlib.pyplot as plt
import csv

def extract_base_services(risk_file_path):
    with open(risk_file_path, "r", encoding="utf-8") as f:
        for line in f:
            if "risk order of" in line.lower():
                match = re.search(r"risk order of (.+?)(?:,|\.)", line, flags=re.IGNORECASE)
                if match:
                    services = [re.sub(r'Test$', '', s.strip()) for s in match.group(1).split(">")]
                    return services[:3]
    return []

def _get_class_name(path):
    return re.sub(r'Test$', '', path.split(".")[-1])

def _get_auc(data, total):
    return sum(data) / total if total else 0

def _format_data(raw_data):
    data_list = [0] * len(raw_data)
    for key, value in raw_data.items():
        index = int(key.lstrip("Step_"))
        data_list[index] = value

    formatted = {}
    for step in data_list:
        for class_path, value in step.items():
            class_name = _get_class_name(class_path)
            if class_name in formatted:
                formatted[class_name]["data"].append(value["covered"])
            else:
                formatted[class_name] = {
                    "total_line": value["total"],
                    "data": [value["covered"]]
                }
    return formatted

def find_best_folder(folder_group, services):
    best_avg_auc = 0
    best_folder = None
    folder_auc_data = {}

    print("Folders to evaluate:", folder_group)

    for folder in folder_group:
        print(f"\n--- Evaluating folder: {folder} ---")
        json_candidates = [f for f in os.listdir(folder) if f.startswith("module_coverage") and f.endswith(".json")]
        print(f"Found JSON files in {folder}:", json_candidates)

        if not json_candidates:
            print(f"Warning: No coverage file found in {folder}")
            continue

        path = os.path.join(folder, json_candidates[0])
        print(f"Reading JSON from: {path}")

        try:
            with open(path, "r") as f:
                raw_data = json.load(f)
        except Exception as e:
            print(f"Error reading {path}: {e}")
            continue

        formatted_data = _format_data(raw_data)
        print(f"Formatted data keys for {folder}:", list(formatted_data.keys()))

        aucs = []
        for service in services:
            if service in formatted_data:
                try:
                    auc = _get_auc(formatted_data[service]["data"], formatted_data[service]["total_line"])
                    aucs.append(auc)
                    print(f"AUC for {service} in {folder}: {auc}")
                except Exception as e:
                    print(f"Error computing AUC for {service} in {folder}: {e}")
            else:
                print(f"Service '{service}' not found in formatted data for {folder}")

        if aucs:
            avg_auc = sum(aucs) / len(services)
        else:
            avg_auc = 0

        print(f"Average AUC for {folder}: {avg_auc}")
        folder_auc_data[folder] = aucs

        if avg_auc > best_avg_auc:
            best_avg_auc = avg_auc
            best_folder = folder
            print(f"New best folder found: {best_folder} with AUC {best_avg_auc}")

    print("\n=== Final Selection ===")
    print("Best folder:", best_folder)
    print("All AUC data:", folder_auc_data)

    return best_folder, folder_auc_data


def plot_services_from_folders(folders, target_services, save_dir):
    plt.figure(figsize=(10, 6))
    for folder in folders:
        json_file = os.path.join(folder, "module_coverage.json")
        if not os.path.exists(json_file):
            print(f"Warning: No 'module_coverage.json' found in folder '{folder}'. Skipping.")
            continue

        with open(json_file, "r") as f:
            formatted_data = _format_data(json.load(f))

        for service in target_services:
            if service not in formatted_data:
                print(f"Warning: {service} not found in {json_file}")
                continue
            points = [v / formatted_data[service]["total_line"] for v in formatted_data[service]["data"]]
            label = f"{service} ({os.path.basename(folder)})"
            auc_value = sum(formatted_data[service]["data"]) / formatted_data[service]["total_line"]
            label_with_auc = f"{label} - AUC={auc_value:.4f}"
            plt.plot(range(len(points)), points, label=label_with_auc)

    plt.title("AUC Comparison Across Strategies")
    plt.legend()
    plt.grid(True)
    output_path = os.path.join(save_dir, "final_comparison.png")
    plt.savefig(output_path)
    plt.close()


def plot_best_folder(folder, services):
    json_file = os.path.join(folder, "module_coverage.json")
    if not os.path.exists(json_file):
        candidates = [f for f in os.listdir(folder) if f.startswith("module_coverage") and f.endswith(".json")]
        if not candidates:
            print(f"No coverage file found in {folder}")
            return
        json_file = os.path.join(folder, candidates[0])

    with open(json_file, "r") as f:
        formatted_data = _format_data(json.load(f))

    plt.figure(figsize=(10, 6))
    for service in services:
        if service in formatted_data:
            points = [v / formatted_data[service]["total_line"] for v in formatted_data[service]["data"]]
            plt.plot(range(len(points)), points, label=service)

    plt.title(f"Best Folder: {os.path.basename(folder)}")
    plt.legend()
    plt.grid(True)
    plt.savefig("Figure1.png")  # 👈 Burada PNG olarak kaydediyoruz


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python risk_plot_helper.py <base_folder>")
        sys.exit(1)

    base_dir = sys.argv[1]
    os.chdir(base_dir)

    services = extract_base_services("all_risk_orders.txt")
    if not services:
        print("Service extraction failed.")
        sys.exit(1)

    all_folders = [f for f in os.listdir(".") if os.path.isdir(f)]
    input_folders = [f for f in all_folders if f.startswith("tests_input")]
    relation_folders = [f for f in all_folders if f.startswith("tests_relation")]
    combined_folders = [f for f in all_folders if f.startswith("combined")]
    
    best_input, input_auc_data = find_best_folder(input_folders, services)
    best_relation, relation_auc_data = find_best_folder(relation_folders, services)
    best_combined, combined_auc_data = find_best_folder(combined_folders, services)

    print(f"Best Input Folder: {best_input}")
    print(f"Best Relation Folder: {best_relation}")
    print(f"Best Combined Folder: {best_combined}")
    plot_services_from_folders([best_input, best_relation, best_combined], services, ".")

    # AUC tablosunu yazdır ve CSV olarak kaydet
    print("\nAUC Table:")
    print("{:25s} | {:20s} | {:8s}".format("Folder", "Service", "AUC"))
    print("="*60)

    all_data = {
        best_input: input_auc_data.get(best_input, []),
        best_relation: relation_auc_data.get(best_relation, []),
        best_combined: combined_auc_data.get(best_combined, [])
    }

    with open("auc_results.csv", "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Folder", "Service", "AUC"])
        for folder, aucs in all_data.items():
            for i, service in enumerate(services):
                auc_val = aucs[i] if i < len(aucs) else 0
                print("{:25s} | {:20s} | {:.4f}".format(folder, service, auc_val))
                writer.writerow([folder, service, f"{auc_val:.4f}"])

    avg_aucs = {folder: sum(aucs) / len(aucs) if aucs else 0 for folder, aucs in all_data.items()}
    best_overall = max(avg_aucs, key=avg_aucs.get)

    print(f"\nBest Overall Folder: {best_overall} (avg AUC = {avg_aucs[best_overall]:.4f})")

    # Son olarak en iyi klasörün grafiğini göster
    plot_best_folder(best_overall, services)
