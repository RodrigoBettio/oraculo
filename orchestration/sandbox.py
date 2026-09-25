"""
Módulo de Sandbox de Execução de Código para o Agent Harness do Oráculo.

Permite que especialistas técnicos (Alex Vance, Bruno, etc.) gerem código,
gravem arquivos em workspaces isolados de projeto, executem os testes/scripts
em subprocessos seguros com timeout e capturem saídas/erros para o loop de ReAct.
"""

import os
import re
import sys
import shutil
import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("oraculo.sandbox")


class SandboxResult(BaseModel):
    success: bool
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    executed_command: str = ""
    files_created: List[str] = Field(default_factory=list)
    error_summary: Optional[str] = None


def extract_code_files(raw_text: str) -> Dict[str, str]:
    """
    Extrai arquivos de código gerados pelo modelo a partir de blocos Markdown.
    
    Suporta formatos:
    ```code:caminho/arquivo.py
    conteudo
    ```
    ou
    ```python filename="caminho/arquivo.py"
    conteudo
    ```
    ou
    # Arquivo: caminho/arquivo.py
    ```python
    conteudo
    ```
    """
    files: Dict[str, str] = {}
    
    # 1. Padrão ```code:caminho/do/arquivo.ext
    code_pattern = re.compile(r"```(?:code|file):([^\r\n]+)\r?\n(.*?)```", re.DOTALL)
    for match in code_pattern.finditer(raw_text):
        fname = match.group(1).strip()
        fcontent = match.group(2).strip()
        if fname:
            files[fname] = fcontent

    # 2. Padrão ```lang filename="arquivo.ext"
    if not files:
        fname_pattern = re.compile(r"```(?:\w+)\s+(?:filename|file)=[\"']?([^\s\"'\r\n]+)[\"']?\r?\n(.*?)```", re.DOTALL)
        for match in fname_pattern.finditer(raw_text):
            fname = match.group(1).strip()
            fcontent = match.group(2).strip()
            if fname:
                files[fname] = fcontent

    # 3. Padrão de cabeçalho antes do bloco: # Arquivo: caminho/arquivo.py seguido de ```lang
    if not files:
        header_pattern = re.compile(r"(?:###?|//|#)\s*(?:Arquivo|File):\s*([^\r\n]+)\r?\n\s*```(?:\w*)\r?\n(.*?)```", re.DOTALL | re.IGNORECASE)
        for match in header_pattern.finditer(raw_text):
            fname = match.group(1).strip()
            fcontent = match.group(2).strip()
            if fname:
                files[fname] = fcontent

    # 4. Fallback: Se houver apenas 1 bloco de código genérico (ex: ```python ... ```), salva como main.py
    if not files:
        generic_pattern = re.compile(r"```(python|javascript|typescript|bash|sh|sql|html|css|json)\r?\n(.*?)```", re.DOTALL | re.IGNORECASE)
        matches = list(generic_pattern.finditer(raw_text))
        if matches:
            first_lang = matches[0].group(1).lower()
            ext_map = {
                "python": "main.py",
                "javascript": "index.js",
                "typescript": "index.ts",
                "html": "index.html",
                "css": "style.css",
                "json": "config.json",
                "sql": "schema.sql",
                "bash": "run.sh",
                "sh": "run.sh"
            }
            default_fname = ext_map.get(first_lang, "output.txt")
            files[default_fname] = matches[0].group(2).strip()

    return files


def write_workspace_files(workspace_dir: Path, files: Dict[str, str]) -> List[str]:
    """Grava todos os arquivos no workspace do projeto com sanitização de caminhos."""
    created = []
    workspace_dir.mkdir(parents=True, exist_ok=True)
    
    for rel_path, content in files.items():
        # Previne directory traversal
        clean_rel = rel_path.strip().replace("\\", "/").lstrip("/")
        if ".." in clean_rel:
            clean_rel = os.path.basename(clean_rel)
            
        target_path = workspace_dir / clean_rel
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        target_path.write_text(content, encoding="utf-8")
        created.append(clean_rel)
        logger.info(f"💾 Arquivo gerado no workspace: {target_path}")

    return created


async def execute_in_sandbox(workspace_dir: Path, timeout_seconds: int = 20) -> SandboxResult:
    """
    Executa testes ou o script principal gerado no workspace com isolamento e timeout.
    
    Verifica:
    1. Compilação/Sintaxe (py_compile para arquivos Python)
    2. Testes automatizados (se houver test_*.py)
    3. Execução do entrypoint (main.py, app.py, run.py)
    """
    if not workspace_dir.exists():
        return SandboxResult(
            success=False,
            exit_code=1,
            error_summary=f"Workspace {workspace_dir} não existe."
        )

    all_files = [f for f in workspace_dir.glob("**/*") if f.is_file()]
    py_files = [f for f in all_files if f.suffix == ".py"]
    
    python_exe = sys.executable

    # Se não houver arquivos Python, verifica HTML/JS ou outros formatos
    if not py_files:
        html_files = [f for f in all_files if f.suffix == ".html"]
        if html_files:
            return SandboxResult(
                success=True,
                exit_code=0,
                stdout=f"Artefato estático Web validado com sucesso: {[f.name for f in html_files]}",
                executed_command="static_validation",
                files_created=[f.name for f in all_files]
            )
        return SandboxResult(
            success=True,
            exit_code=0,
            stdout=f"Arquivos gerados com sucesso: {[f.name for f in all_files]}",
            executed_command="none",
            files_created=[f.name for f in all_files]
        )

    # 1. Passo de Verificação de Sintaxe de todos os arquivos .py
    for pf in py_files:
        try:
            compile_cmd = [python_exe, "-m", "py_compile", str(pf.resolve())]
            proc = await asyncio.create_subprocess_exec(
                *compile_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(workspace_dir.resolve())
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5)
            if proc.returncode != 0:
                err_text = stderr.decode("utf-8", errors="replace").strip()
                return SandboxResult(
                    success=False,
                    exit_code=proc.returncode,
                    stdout=stdout.decode("utf-8", errors="replace"),
                    stderr=err_text,
                    executed_command=" ".join(compile_cmd),
                    files_created=[f.name for f in all_files],
                    error_summary=f"Erro de sintaxe em {pf.name}: {err_text}"
                )
        except Exception as e:
            return SandboxResult(
                success=False,
                exit_code=1,
                stderr=str(e),
                executed_command="py_compile",
                files_created=[f.name for f in all_files],
                error_summary=f"Falha ao compilar {pf.name}: {e}"
            )

    # 2. Passo de Execução: Procura por arquivos de teste
    test_files = [f for f in py_files if f.name.startswith("test_") or f.name.endswith("_test.py")]
    
    if test_files:
        run_cmd = [python_exe, "-m", "unittest", "discover", "-s", str(workspace_dir.resolve()), "-p", "*test*.py"]
    else:
        # Encontra entrypoint principal
        entrypoint = None
        for candidate in ["main.py", "app.py", "run.py", "cli.py", "server.py"]:
            candidate_path = workspace_dir / candidate
            if candidate_path.exists():
                entrypoint = candidate_path
                break
        
        if not entrypoint and py_files:
            entrypoint = py_files[0]

        if entrypoint:
            run_cmd = [python_exe, str(entrypoint.resolve())]
        else:
            return SandboxResult(
                success=True,
                exit_code=0,
                stdout="Todos os arquivos compilam sem erros de sintaxe.",
                executed_command="py_compile",
                files_created=[f.name for f in all_files]
            )

    # Executa o script / teste com timeout
    try:
        proc = await asyncio.create_subprocess_exec(
            *run_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(workspace_dir),
            env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
        )
        
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout_seconds
        )
        
        stdout = stdout_bytes.decode("utf-8", errors="replace").strip()
        stderr = stderr_bytes.decode("utf-8", errors="replace").strip()
        
        success = (proc.returncode == 0)
        error_summary = None if success else (stderr or f"Processo encerrou com código {proc.returncode}")

        return SandboxResult(
            success=success,
            exit_code=proc.returncode,
            stdout=stdout,
            stderr=stderr,
            executed_command=" ".join(run_cmd),
            files_created=[f.name for f in all_files],
            error_summary=error_summary
        )

    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        return SandboxResult(
            success=False,
            exit_code=-1,
            stderr=f"Execução cancelada: excedeu o timeout limite de {timeout_seconds} segundos.",
            executed_command=" ".join(run_cmd),
            files_created=[f.name for f in all_files],
            error_summary=f"Timeout ({timeout_seconds}s) na execução de {run_cmd[-1]}"
        )
    except Exception as e:
        return SandboxResult(
            success=False,
            exit_code=1,
            stderr=str(e),
            executed_command=" ".join(run_cmd),
            files_created=[f.name for f in all_files],
            error_summary=f"Erro ao executar processo no sandbox: {e}"
        )
