import json
import random
from pathlib import Path

PATH = Path("evals/cases.jsonl")
cases = [json.loads(line) for line in PATH.read_text().splitlines() if line.strip()]

random.seed(42)  # fixed seed: same picks every time, no cherry-picking

groups = {}
for case in cases:
    prefix = case["id"].split("_")[0]  # "spam_03" -> "spam"
    groups.setdefault(prefix, []).append(case)

for prefix in ["clean", "messy", "spam", "ambiguous", "adversarial"]:
    for case in random.sample(groups[prefix], 2):
        if "holdout" not in case["tags"]:
            case["tags"].append("holdout")

PATH.write_text("\n".join(json.dumps(c, ensure_ascii=False) for c in cases) + "\n")
print(sum("holdout" in c["tags"] for c in cases), "holdout cases")