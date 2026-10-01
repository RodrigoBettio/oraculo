import json
import glob

for p in sorted(glob.glob("data/agents/*.json")):
    with open(p, "r", encoding="utf-8") as f:
        d = json.load(f)
        role = d.get("role") or d.get("system_prompt", "")[:60]
        print(f"{d.get('id')} | {d.get('name')} | Area: {d.get('area_id')} | Type: {d.get('agent_type')}")
