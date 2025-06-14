import tkinter as tk
from tkinter import messagebox, scrolledtext, filedialog, ttk
import subprocess
import os
import threading
import json
import matplotlib.pyplot as plt
from PIL import Image, ImageTk

# === ANALYSIS UTILITY ===
def plot_combined_coverage_graph(base_run_dir):
    results_path = os.path.join(base_run_dir, "coverage_results.json")
    if not os.path.exists(results_path):
        raise FileNotFoundError("coverage_results.json not found.")

    with open(results_path, "r") as f:
        existing = json.load(f)

    plt.figure(figsize=(12, 6))
    for strat_name, progress in existing.items():
        values = [progress[f"Step_{i}"]["coverage_percent"] for i in range(len(progress))]
        plt.plot(range(len(values)), values, marker='o', label=strat_name)
    plt.title("Combined Coverage Comparison")
    plt.xlabel("Test Count")
    plt.ylabel("Coverage (%)")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()

    output_path = os.path.join(base_run_dir, "coverage_comparison_combined_only.png")
    plt.savefig(output_path)
    plt.close()

    return output_path

class SelectionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Risk & Coverage Based Runner")

        self.venv_python = os.path.join("venv", "Scripts", "python.exe")
        self.risk_path = "RiskBased"
        self.coverage_path = "CoverageBased"
        self.analysis_image = None

        self.process = None

        self.tab_control = ttk.Notebook(root)
        self.tab1 = ttk.Frame(self.tab_control)
        self.tab2 = ttk.Frame(self.tab_control)
        self.tab3 = ttk.Frame(self.tab_control)
        self.tab4 = ttk.Frame(self.tab_control)
        self.tab_control.add(self.tab1, text="Strategy Selection")
        self.tab_control.add(self.tab2, text="Run From Folder")
        self.tab_control.add(self.tab3, text="Coverage Analysis")
        self.tab_control.pack(expand=1, fill="both")
        self.tab_control.add(self.tab4, text="Risk Analysis")


        self.build_tab1()
        self.build_tab2()
        self.build_tab3()
        self.build_tab4()

    def build_tab1(self):
        self.risk_var = tk.BooleanVar()
        self.coverage_var = tk.BooleanVar()

        self.options_frame = tk.LabelFrame(self.tab1, text="Select Strategy Type", padx=10, pady=10)
        self.options_frame.pack(padx=10, pady=10, fill="x")

        self.risk_checkbox = tk.Checkbutton(self.options_frame, text="Risk Based", variable=self.risk_var)
        self.coverage_checkbox = tk.Checkbutton(self.options_frame, text="Coverage Based", variable=self.coverage_var)
        self.risk_checkbox.pack(anchor="w")
        self.coverage_checkbox.pack(anchor="w")

        self.run_button = tk.Button(self.tab1, text="Execute", command=self.run_selected_scripts, bg="green", fg="white")
        self.run_button.pack(pady=10)

        self.output_text = scrolledtext.ScrolledText(self.tab1, height=15, width=80)
        self.output_text.pack(padx=10, pady=10)

        self.input_entry = tk.Entry(self.tab1, width=60)
        self.input_entry.pack(padx=10, side=tk.LEFT, expand=True, fill="x")

        self.send_button = tk.Button(self.tab1, text="Send", command=self.send_input_to_process)
        self.send_button.pack(padx=5, pady=5, side=tk.RIGHT)

    def build_tab2(self):
        risk_frame = tk.LabelFrame(self.tab2, text="Run Risk-Based Folder", padx=10, pady=10)
        risk_frame.pack(padx=10, pady=10, fill="x")

        self.risk_folder_label = tk.Label(risk_frame, text="No folder selected")
        self.risk_folder_label.pack(anchor="w")

        tk.Button(risk_frame, text="Select Folder", command=self.select_risk_folder).pack(pady=5)
        tk.Button(risk_frame, text="Run Risk Script", command=self.run_risk_from_folder).pack(pady=5)

        coverage_frame = tk.LabelFrame(self.tab2, text="Run Coverage-Based Folder", padx=10, pady=10)
        coverage_frame.pack(padx=10, pady=10, fill="x")

        self.coverage_folder_label = tk.Label(coverage_frame, text="No folder selected")
        self.coverage_folder_label.pack(anchor="w")

        tk.Button(coverage_frame, text="Select Folder", command=self.select_coverage_folder).pack(pady=5)
        tk.Button(coverage_frame, text="Run Coverage Script", command=self.run_coverage_from_folder).pack(pady=5)

        self.output_tab2 = scrolledtext.ScrolledText(self.tab2, height=20, width=90)
        self.output_tab2.pack(padx=10, pady=10)

    def build_tab3(self):
        analysis_frame = tk.LabelFrame(self.tab3, text="Analyze Previous Run", padx=10, pady=10)
        analysis_frame.pack(padx=10, pady=10, fill="x")

        self.analysis_folder_label = tk.Label(analysis_frame, text="No folder selected")
        self.analysis_folder_label.pack(anchor="w")

        tk.Button(analysis_frame, text="Select Folder", command=self.select_analysis_folder).pack(pady=5)
        tk.Button(analysis_frame, text="Generate Graph", command=self.run_analysis).pack(pady=5)

        self.analysis_canvas = tk.Canvas(self.tab3, width=1500, height=800)
        self.analysis_canvas.pack(padx=10, pady=10)

    def build_tab4(self):
        analysis_frame = tk.LabelFrame(self.tab4, text="Analyze Risk-Based Graph", padx=10, pady=10)
        analysis_frame.pack(padx=10, pady=10, fill="x")

        self.risk_analysis_folder_label = tk.Label(analysis_frame, text="No folder selected")
        self.risk_analysis_folder_label.pack(anchor="w")

        tk.Button(analysis_frame, text="Select Folder", command=self.select_risk_analysis_folder).pack(pady=5)
        tk.Button(analysis_frame, text="Generate Risk Graph", command=self.run_risk_plot_analysis).pack(pady=5)

        # Figure 1 için canvas
        # Üst satır - Comparison ve CSV yan yana
        top_frame = tk.Frame(self.tab4)
        top_frame.pack(padx=10, pady=10, fill="x")
        
        self.risk_compare_image_canvas = tk.Canvas(top_frame, width=500, height=350)
        self.risk_compare_image_canvas.pack(side=tk.LEFT, padx=5)
        
        self.auc_table = scrolledtext.ScrolledText(top_frame, height=20, width=60)
        self.auc_table.pack(side=tk.RIGHT, padx=5)
        
        # Alt satır - Figure1 alta ortalanmış
        self.risk_final_image_canvas = tk.Canvas(self.tab4, width=1020, height=350)
        self.risk_final_image_canvas.pack(padx=10, pady=10)


    def select_risk_analysis_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.risk_analysis_folder = folder
            self.risk_analysis_folder_label.config(text=folder)

    def run_risk_plot_analysis(self):
        folder = getattr(self, 'risk_analysis_folder', '')
        if not os.path.exists(folder):
            messagebox.showerror("Error", "No valid folder selected.")
            return

        script_path = os.path.join(self.risk_path, "risk_plot_helper.py")
        if not os.path.exists(script_path):
            messagebox.showerror("Error", "risk_plot_helper.py not found in RiskBased.")
            return

        try:
            subprocess.run([self.venv_python, script_path, folder], check=True)

            # === FIGURE 1 ===
            fig1_path = os.path.join(folder, "Figure1.png")
            if os.path.exists(fig1_path):
                fig1 = Image.open(fig1_path).resize((500, 350), Image.Resampling.LANCZOS)
                self.risk_final_image = ImageTk.PhotoImage(fig1)
                self.risk_final_image_canvas.create_image(0, 0, anchor=tk.NW, image=self.risk_final_image)

            # === final_comparison.png ===
            compare_path = os.path.join(folder, "final_comparison.png")
            if os.path.exists(compare_path):
                cmp = Image.open(compare_path).resize((500, 350), Image.Resampling.LANCZOS)
                self.risk_comparison_image = ImageTk.PhotoImage(cmp)
                self.risk_compare_image_canvas.create_image(0, 0, anchor=tk.NW, image=self.risk_comparison_image)

            # === AUC TABLOSU ===
            auc_csv_path = os.path.join(folder, "auc_results.csv")
            if os.path.exists(auc_csv_path):
                with open(auc_csv_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    self.auc_table.delete("1.0", tk.END)
                    self.auc_table.insert(tk.END, content)
            else:
                self.auc_table.insert(tk.END, "auc_results.csv not found.")

        except subprocess.CalledProcessError as e:
            messagebox.showerror("Error", f"Script failed: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate outputs: {str(e)}")




     # === Folder Seçim Fonksiyonları ===
    def select_risk_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.risk_folder = folder
            self.risk_folder_label.config(text=folder)

    def select_coverage_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.coverage_folder = folder
            self.coverage_folder_label.config(text=folder)

    def select_analysis_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.analysis_folder = folder
            self.analysis_folder_label.config(text=folder)

    # === Script Çalıştıran Fonksiyonlar ===
    def run_risk_from_folder(self):
        folder = getattr(self, 'risk_folder', '')
        script = os.path.join(self.risk_path, "risk_analyzer.py")
        if os.path.exists(script) and os.path.isdir(folder):
            self.output_tab2.delete("1.0", tk.END)
            threading.Thread(target=self.run_script_with_args, args=(script, folder), daemon=True).start()
        else:
            messagebox.showerror("Error", "risk_analyzer.py not found or no folder selected.")

    def run_coverage_from_folder(self):
        folder = getattr(self, 'coverage_folder', '')
        script = os.path.join(self.coverage_path, "coverage_runner_analyzer.py")
        if os.path.exists(script) and os.path.isdir(folder):
            self.output_tab2.delete("1.0", tk.END)
            threading.Thread(target=self.run_script_with_args, args=(script, folder), daemon=True).start()
        else:
            messagebox.showerror("Error", "coverage_runner_analyzer.py not found or no folder selected.")

    def run_script_with_args(self, script_path, folder_arg):
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        process = subprocess.Popen(
            [self.venv_python, script_path, folder_arg],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
            encoding="utf-8",
            errors="replace"
        )
        for line in process.stdout:
            self.output_tab2.insert(tk.END, line)
            self.output_tab2.see(tk.END)

    def run_selected_scripts(self):
        if not self.risk_var.get() and not self.coverage_var.get():
            messagebox.showerror("Error", "Please select at least one strategy.")
            return

        self.output_text.delete("1.0", tk.END)
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        if self.risk_var.get():
            risk_script_path = os.path.join(self.risk_path, "risk_relation.py")
            if os.path.exists(risk_script_path):
                self.process = subprocess.Popen(
                    [self.venv_python, risk_script_path],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    env=env,
                    encoding="utf-8"
                )
                threading.Thread(target=self.read_output, daemon=True).start()
            else:
                messagebox.showerror("Error", "'risk_relation.py' not found in RiskBased folder.")

        if self.coverage_var.get():
            coverage_script_path = os.path.join(self.coverage_path, "coverage.py")
            if os.path.exists(coverage_script_path):
                self.process = subprocess.Popen(
                    [self.venv_python, coverage_script_path],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    env=env,
                    encoding="utf-8"
                )
                threading.Thread(target=self.read_output, daemon=True).start()
            else:
                messagebox.showerror("Error", "'coverage.py' not found in CoverageBased folder.")

    def read_output(self):
        for line in self.process.stdout:
            self.output_text.insert(tk.END, line)
            self.output_text.see(tk.END)

    def send_input_to_process(self):
        user_input = self.input_entry.get()
        if self.process and self.process.stdin:
            self.process.stdin.write(user_input + "\n")
            self.process.stdin.flush()
            self.input_entry.delete(0, tk.END)

    def run_analysis(self):
        folder = getattr(self, 'analysis_folder', '')
        if not os.path.exists(folder):
            messagebox.showerror("Error", "No valid folder selected.")
            return

        script_path = os.path.join(self.coverage_path, "coverage_analyzer.py")
        if not os.path.exists(script_path):
            messagebox.showerror("Error", "coverage_analyzer.py not found.")
            return

        try:
            subprocess.run([self.venv_python, script_path, folder], check=True)

            image_path = os.path.join(folder, "coverage_comparison.png")
            if not os.path.exists(image_path):
                messagebox.showerror("Error", "Graph image not found.")
                return

            image = Image.open(image_path)
            image = image.resize((1180, 780), Image.Resampling.LANCZOS)
            self.analysis_image = ImageTk.PhotoImage(image)
            self.analysis_canvas.create_image(0, 0, anchor=tk.NW, image=self.analysis_image)
        except subprocess.CalledProcessError as e:
            messagebox.showerror("Error", f"Script failed: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate graph: {str(e)}")


if __name__ == "__main__":
    root = tk.Tk()
    app = SelectionApp(root)
    root.mainloop()
