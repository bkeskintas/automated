import openai
import os
import time
import tiktoken  # pip install tiktoken
from openai import OpenAI
from dotenv import load_dotenv
from collections import defaultdict
from tqdm import tqdm
from datetime import datetime
from typing import TypedDict, List
from langgraph.graph import StateGraph, END
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MODEL_AGENT1 = "gpt-4"
MODEL_AGENT2 = "gpt-4"

INPUT_FILE_ALL = "./Input/all_tests.txt"
INPUT_FILE_REG = "./Input/regression.txt"

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
RESULT_DIR = f"./CoverageBased/full_test_orders/run_{timestamp}"
os.makedirs(RESULT_DIR, exist_ok=True)
PROMPT_SNAPSHOT_FILE = os.path.join(RESULT_DIR, "final_prompt_used.txt")
LOG_FILE = os.path.join(RESULT_DIR, "process.txt")
TOTAL_TOKENS_LOG = os.path.join(RESULT_DIR, "total_tokens_used.txt")

class State(TypedDict):
    all_tests: List[str]
    regression_tests: List[str]
    allowed_tests: set
    strategies: List[str]
    prompts: List[str]
    results: List[tuple]

# === Token hesaplama ===
def estimate_tokens(text, model="gpt-4"):
    try:
        enc = tiktoken.encoding_for_model(model)
    except:
        enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))

# === Dosya okuma ===
def load_tests():
    with open(INPUT_FILE_ALL, "r", encoding="utf-8") as f:
        all_lines = [line.strip() for line in f if "#" in line and (" - " in line or "–" in line)]
    with open(INPUT_FILE_REG, "r", encoding="utf-8") as f:
        regression_lines = [line.strip() for line in f if line.strip()]

    all_names = set()
    for line in all_lines:
        if " - " in line:
            name = line.split(" - ")[0].strip()
        elif "–" in line:
            name = line.split("–")[0].strip()
        else:
            continue
        all_names.add(name)

    return all_lines, all_names, regression_lines


# === Base prompt ===
def get_base_prompt(test_count):
    return f"""
You are a test optimization assistant.

Now I will give you regression and unit test cases. Your job is to reorder the test names to maximize early cumulative code coverage.

Each test is in the format:
ClassName#testMethod - short description

⚙️ Input Parameters:
- Total number of tests: {test_count}
- You must return exactly {test_count} test names.
- All returned test names must come from the provided list.
- Do NOT add, remove, rename, or duplicate any tests.

⚠️ Important Instruction:
You must reorder exactly the test names I provide. Do not add anything. Do not change anything.
Just return the same test names in a better order to get higher line coverage.

🚫 Strict Format Rules:
- DO NOT include:
  • Descriptions
  • Explanations or comments
  • Markdown (e.g., **bold**, code)
  • Category headings
  • Numbering, bullets, or blank lines

✅ Output format:
AuthenticationServiceTest#testRegister_Success  
JwtServiceTest#testGenerateAccessToken
""".strip()

# === Strateji üretici ===
def generate_prompt_strategies(base_prompt):
    strategies = [
        "Prioritize tests with the most important terms based on TF-IDF scores.",
        "Focus on test cases that seem to cover large code regions based on naming.",
        "Maximize early diversity across different modules or classes.",
        "Alternate between positive/negative or edge/normal test cases.",
        "Distribute regression test cases evenly rather than grouping them."
    ]
    prompts = [base_prompt + "\n\n\U0001f9e0 Strategy: " + s for s in strategies]
    return strategies, prompts

# === Validation ===
def validate_output(output_lines, allowed_tests):
    errors = []
    seen = set()
    if len(output_lines) != len(allowed_tests):
        errors.append(f"Test count mismatch: expected {len(allowed_tests)}, got {len(output_lines)}")
    for test in output_lines:
        if test not in allowed_tests:
            errors.append(f"Unknown or malformed test name: {test}")
        if test in seen:
            errors.append(f"Duplicate test: {test}")
        if " " in test or "#" not in test:
            errors.append(f"Invalid format: {test}")
        seen.add(test)
    return errors

# === OpenAI çağrısı ===
def call_openai(system_prompt, user_prompt, model, temperature=0, top_p=1.0, n=1):
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=temperature,
        top_p=top_p,
        n=n
    )
    return response.choices[0].message.content

# === Agent düğümü ===
def agent2_node(state: State) -> State:
    idx = len(state["results"])
    strategy_prompt = state["prompts"][idx]
    strategy_name = state["strategies"][idx]
    print(f"\n▶️ Running strategy {idx+1}: {strategy_name}")

    user_prompt = (
        "Now I will give you the full test list.\n\n"
        "Here is the list of unit + integration tests:\n\n"
        + "\n".join(state["all_tests"])
        + "\n\nHere are the regression tests that must also be included:\n\n"
        + "\n".join(state["regression_tests"])
    )

    for attempt in range(5):
        response = call_openai(strategy_prompt, user_prompt, model=MODEL_AGENT2, temperature=0.7, top_p=0.9)
        parsed = [line.strip("\u2022*0123456789.- ").split(":")[0].strip() for line in response.splitlines() if line.strip()]
        errors = validate_output(parsed, state["allowed_tests"])
        if not errors:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"\n=== STRATEGY #{idx+1} - {strategy_name} ===\n\n")
                f.write("🔹 Prompt:\n" + strategy_prompt + "\n\n")
                f.write("🔹 User input:\n" + user_prompt + "\n\n")
                f.write("🔹 Response:\n" + response + "\n\n")
            state["results"].append((parsed, strategy_prompt, user_prompt, response))
            return state
        else:
            print(f"  ❌ Attempt {attempt+1} failed: {errors[0]}")

    print(f"  ❌ Strategy {idx+1} failed after 5 attempts.")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n❌ Strategy #{idx+1} - {strategy_name} failed after 5 attempts.\n")
    state["results"].append(([], strategy_prompt, user_prompt, ""))
    return state

# === Ortalama sıralama ===
def combine_test_orderings(orderings):
    rank_sum = defaultdict(int)
    count = defaultdict(int)
    for order in orderings:
        for i, test in enumerate(order):
            rank_sum[test] += i
            count[test] += 1
    averaged = sorted(rank_sum.items(), key=lambda x: x[1] / count[x[0]])
    return [test for test, _ in averaged]

# === Final adım ===
def finalize(state: State) -> State:
    parsed_orders = [entry[0] for entry in state["results"] if entry[0]]
    final_order = combine_test_orderings(parsed_orders)

    for i, order in enumerate(parsed_orders):
        strategy_file = os.path.join(RESULT_DIR, f"sorted_test_strategy{i+1}.txt")
        with open(strategy_file, "w", encoding="utf-8") as f:
            f.write("\n".join(order))
        print(f"✅ Strategy #{i+1} result saved to {strategy_file}")

    with open(os.path.join(RESULT_DIR, "sorted_test_combined.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(final_order))
    print("✅ Combined result saved to sorted_test_combined.txt")

    with open(PROMPT_SNAPSHOT_FILE, "w", encoding="utf-8") as pf:
        for _, sys_prompt, user_prompt, _ in state["results"]:
            pf.write("=== SYSTEM PROMPT ===\n" + sys_prompt + "\n\n")
            pf.write("=== USER PROMPT ===\n" + user_prompt + "\n\n")

    return state

# === Ana işlem ===
def main():
    all_tests, allowed_test_names, regression_tests = load_tests()
    base_prompt = get_base_prompt(len(allowed_test_names))
    strategies, prompts = generate_prompt_strategies(base_prompt)

    state = State(
        all_tests=all_tests,
        regression_tests=regression_tests,
        allowed_tests=allowed_test_names,
        strategies=strategies,
        prompts=prompts,
        results=[]
    )

    graph = StateGraph(State)
    for i in range(len(prompts)):
        graph.add_node(f"strategy_{i+1}", agent2_node)
    for i in range(len(prompts) - 1):
        graph.add_edge(f"strategy_{i+1}", f"strategy_{i+2}")

    # ✅ Final adımı ayrı düğüm olarak ekliyoruz
    graph.add_node("finalize", finalize)
    graph.add_edge(f"strategy_{len(prompts)}", "finalize")

    graph.set_entry_point("strategy_1")
    graph.set_finish_point("finalize")

    runnable = graph.compile()
    runnable.invoke(state)

if __name__ == "__main__":
    main()
