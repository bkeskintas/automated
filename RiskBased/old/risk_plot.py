import os
import sys
import json
import re
import matplotlib.pyplot as plt

# === Yardımcı Fonksiyonlar ===

def extract_base_services(risk_file_path):
    with open(risk_file_path, "r", encoding="utf-8") as f:
        for line in f:
            if "risk order of" in line.lower():
                match = re.search(r"risk order of (.+?)(?:,|\.)", line, flags=re.IGNORECASE)
                if match:
                    # Sonu "Test" ile biten ifadeleri kes
                    services = [re.sub(r'Test$', '', s.strip()) for s in match.group(1).split(">")]
                    return services[:3]
    return []

def _get_class_name(path):
    # Sınıf adını alıp sonundaki Test'i kes
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

def _get_all_jsons():
    return [f for f in os.listdir() if f.startswith("module_coverage") and f.endswith(".json")]

def get_best_auc_per_group(paths, target_services):
    best_per_service = {s: (None, 0) for s in target_services}
    all_group_data = {}

    for path in paths:
        with open(path, "r") as f:
            formatted_data = _format_data(json.load(f))

        auc_info = {}
        for service in target_services:
            if service in formatted_data:
                auc = _get_auc(formatted_data[service]["data"], formatted_data[service]["total_line"])
                auc_info[service] = auc
                if auc > best_per_service[service][1]:
                    best_per_service[service] = (path, auc)

        all_group_data[path] = auc_info

    return best_per_service, all_group_data

def draw_final_plot(best_per_service, services, save_dir):
    plt.figure(figsize=(10, 6))
    for service in services:
        path = best_per_service[service][0]
        if not path:
            print(f"Warning: No data for service {service}")
            continue
        with open(path, "r") as f:
            formatted_data = _format_data(json.load(f))
        points = [v / formatted_data[service]["total_line"] for v in formatted_data[service]["data"]]
        plt.plot(range(len(points)), points, label=service)
    plt.title("Best AUC per Service")
    plt.legend()
    plt.grid(True)
    output_path = os.path.join(save_dir, "risk_auc_best.png")
    plt.savefig(output_path)
    plt.close()

def print_auc_table(all_group_data, target_services):
    print("\nAUC Table:")
    print("{:50s} | {:20s} | {:8s}".format("File", "Service", "AUC"))
    print("="*85)
    for path, values in all_group_data.items():
        for s in target_services:
            auc = values.get(s, 0)
            print("{:50s} | {:20s} | {:.4f}".format(path, s, auc))

# === Ana Program ===
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python risk_plot.py <folder_path>")
        sys.exit(1)

    base_dir = sys.argv[1]
    risk_order_path = os.path.join(base_dir, "all_risk_orders.txt")

    if not os.path.exists(risk_order_path):
        print(f"Error: '{risk_order_path}' not found.")
        sys.exit(1)

    services = extract_base_services(risk_order_path)
    if not services:
        print("Could not extract base services from risk order.")
        sys.exit(1)

    os.chdir(base_dir)
    all_jsons = _get_all_jsons()
    best_per_service, all_group_data = get_best_auc_per_group(all_jsons, services)

    draw_final_plot(best_per_service, services, save_dir=base_dir)
    print_auc_table(all_group_data, services)

    print("\nFinal best parameters:")
    for s in services:
        print(f"{s}: {best_per_service[s][0]} with AUC = {best_per_service[s][1]:.4f}")
