import asyncio
import shutil
from pathlib import Path
from orchestration.sandbox import extract_code_files, write_workspace_files, execute_in_sandbox

raw = """
Vou criar a calculadora solicitada e seu teste unitario.

```code:calc.py
def add(a: int, b: int) -> int:
    return a + b

if __name__ == "__main__":
    print(f"Resultado: {add(10, 20)}")
```

```code:test_calc.py
import unittest
from calc import add

class TestCalc(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(2, 3), 5)
        self.assertEqual(add(-1, 1), 0)

if __name__ == "__main__":
    unittest.main()
```
"""

files = extract_code_files(raw)
print("Extracted files:", list(files.keys()))

ws = Path("data/temp/test_ws")
if ws.exists():
    shutil.rmtree(ws)

created = write_workspace_files(ws, files)
print("Created files:", created)

async def run():
    res = await execute_in_sandbox(ws)
    print("Success:", res.success)
    print("Exit code:", res.exit_code)
    print("Command:", res.executed_command)
    print("Stdout:", res.stdout)
    print("Stderr:", res.stderr)
    print("Error summary:", res.error_summary)

asyncio.run(run())
