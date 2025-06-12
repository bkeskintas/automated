import openai
import os
import time
import tiktoken  # pip install tiktoken
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv() 
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MODEL_AGENT1 = "gpt-4"
MODEL_AGENT2 = "gpt-4"

INPUT_FILE_ALL = "./all_tests.txt"
INPUT_FILE_REG = "./regressiontext.txt"
PROMPT_SNAPSHOT_FILE = "./final_prompt_used.txt"
LOG_FILE = "./process.txt"
TOTAL_TOKENS_LOG = "./total_tokens_used.txt"

import os
import time
import tiktoken
from collections import defaultdict
from tqdm import tqdm

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
        all_lines = [line.strip() for line in f if " - " in line]
    with open(INPUT_FILE_REG, "r", encoding="utf-8") as f:
        regression_lines = [line.strip() for line in f if line.strip()]
    all_names = {line.split(" - ")[0].strip() for line in all_lines}
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

# === Agent1: 5 farklı strateji üretici ===
def generate_prompt_strategies(base_prompt):
    strategies = [
        "Prioritize tests with the most important terms based on TF-IDF scores.",
        "Focus on test cases that seem to cover large code regions based on naming.",
        "Maximize early diversity across different modules or classes.",
        "Alternate between positive/negative or edge/normal test cases.",
        "Distribute regression test cases evenly rather than grouping them."
    ]
    prompts = []
    for strategy in strategies:
        full_prompt = base_prompt + "\n\n\U0001f9e0 Strategy: " + strategy
        prompts.append(full_prompt)
    return prompts

# === Agent1: Validation hatası sonrası yeni prompt üretici ===
def generate_fixed_prompt_from_errors(previous_errors):
    error_summary = "\n".join(previous_errors)
    user_prompt = (
        "The following output was invalid:\n\n"
        + error_summary +
        "\n\nGenerate a stricter system prompt to guide the model to:\n"
        "- Reorder ONLY the provided test names\n"
        "- Match the test count exactly\n"
        "- Avoid descriptions, markdown, explanations, or any extra content\n"
        "- Output only one test name per line, no blank lines, nothing else\n"
        "- End with: 'Only return test names. No other text.'"
    )
    return call_openai("", user_prompt, MODEL_AGENT1, temperature=0)

# === Output validation ===
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

# === Agent2: Çoklu prompta göre sıralama üretici ===
def agent2_generate_multiple_orders(system_prompts, all_tests, regression_tests, allowed_tests):
    results = []
    max_attempts = 5
    for idx, original_prompt in enumerate(tqdm(system_prompts, desc="Generating test orderings")):
        sys_prompt = original_prompt
        attempt = 0
        while attempt < max_attempts:
            user_prompt = (
                "Now I will give you the full test list.\n\n"
                "Here is the list of unit + integration tests:\n\n"
                + "\n".join(all_tests)
                + "\n\nHere are the regression tests that must also be included:\n\n"
                + "\n".join(regression_tests)
            )
            response = call_openai(sys_prompt, user_prompt, model=MODEL_AGENT2, temperature=0.7, top_p=0.9, n=1)
            parsed = [line.strip("\u2022*0123456789.- ").split(":")[0].strip()
                      for line in response.splitlines() if line.strip()]
            errors = validate_output(parsed, allowed_tests)
            if not errors:
                results.append((parsed, sys_prompt, user_prompt, response))
                break
            else:
                print(f"❌ Strategy #{idx+1} - Attempt {attempt+1} failed validation:")
                for err in errors:
                    print(" -", err)
                sys_prompt = generate_fixed_prompt_from_errors(errors)
                attempt += 1
    return results

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

# === Çıktıları ortalama ile birleştir ===
def combine_test_orderings(orderings):
    rank_sum = defaultdict(int)
    count = defaultdict(int)
    for order in orderings:
        for i, test in enumerate(order):
            rank_sum[test] += i
            count[test] += 1
    averaged = sorted(rank_sum.items(), key=lambda x: x[1] / count[x[0]])
    return [test for test, _ in averaged]

# === Ana işlem ===
def main():
    all_tests, allowed_test_names, regression_tests = load_tests()
    base_prompt = get_base_prompt(len(allowed_test_names))
    strategy_prompts = generate_prompt_strategies(base_prompt)

    all_orderings = agent2_generate_multiple_orders(strategy_prompts, all_tests, regression_tests, allowed_test_names)
    parsed_orders = [entry[0] for entry in all_orderings]
    final_order = combine_test_orderings(parsed_orders)

    # Her strateji çıktısını ayrı dosyaya yaz
    for i, order in enumerate(parsed_orders):
        strategy_file = f"sorted_test_strategy{i+1}.txt"
        with open(strategy_file, "w", encoding="utf-8") as f:
            f.write("\n".join(order))
        print(f"✅ Strategy #{i+1} result saved to {strategy_file}")

    # Birleştirilmiş sonucu yaz
    with open("sorted_test_combined.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(final_order))
    print("✅ Combined result saved to sorted_test_combined.txt")

    # Prompt snapshotları
    with open(PROMPT_SNAPSHOT_FILE, "w", encoding="utf-8") as pf:
        for _, sys_prompt, user_prompt, _ in all_orderings:
            pf.write("=== SYSTEM PROMPT ===\n" + sys_prompt + "\n\n")
            pf.write("=== USER PROMPT ===\n" + user_prompt + "\n\n")

    # Log dosyası
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        for i, (_, sys_prompt, user_prompt, response) in enumerate(all_orderings):
            f.write(f"\n=== STRATEGY #{i+1} ===\n\n")
            f.write("🔹 Prompt sent to Agent 2:\n" + sys_prompt + "\n\n")
            f.write("🔹 User input to Agent 2:\n" + user_prompt + "\n\n")
            f.write("🔹 Response from Agent 2:\n" + response + "\n\n")
        f.write("\n✅ Final combined test order saved to sorted_test_combined.txt\n")

if __name__ == "__main__":
    main()