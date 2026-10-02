"""Recompila todas as skills com o padrão oficial do Oráculo Engine."""
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from web.app import load_all_agents, compile_agent_rich_skill
from config import settings

agents = load_all_agents()
print(f"Total de agentes encontrados: {len(agents)}")

for ag in agents:
    aid = ag.get("id")
    name = ag.get("name")
    atype = ag.get("agent_type")
    compiled = compile_agent_rich_skill(aid)
    if compiled:
        skill_dir = settings.DATA_DIR / "skills" / aid
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(compiled, encoding="utf-8")
        print(f"✅ {name} ({atype}): {len(compiled)} bytes gravados em {skill_file.relative_to(BASE_DIR)}")

print("\n🎉 Todas as skills foram reprocessadas e alinhadas ao padrão oficial!")
