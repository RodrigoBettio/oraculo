"""Guard do Harness — classifica cada chamada de ferramenta do agente.

Três decisões possíveis:
- ``allow``   → executa normalmente.
- ``confirm`` → pede aprovação no Telegram (apagar arquivos / SQL destrutivo).
- ``block``   → nunca executa (proteções estruturais: push, sair do workspace, segredos).

Módulo puro (sem I/O de rede) para ser 100% testável.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Literal, Mapping

Action = Literal["allow", "confirm", "block"]


@dataclass(frozen=True)
class GuardDecision:
    action: Action
    reason: str = ""
    category: str = ""

    @property
    def allowed(self) -> bool:
        return self.action == "allow"


ALLOW = GuardDecision("allow")

_I = re.IGNORECASE

# ---------------------------------------------------------------------------
# Padrões — CONFIRM
# ---------------------------------------------------------------------------
# Comandos de shell que apagam arquivos (bash + PowerShell + cmd).
_SHELL_DELETE = re.compile(
    r"(?<![\w\-./\\])(rm|rmdir|del|erase|rd|shred|unlink|remove-item|ri)(?![\w\-])", _I
)
_FIND_DELETE = re.compile(r"\bfind\b.*\s-delete\b", _I)
_GIT_DELETE = re.compile(r"\bgit\s+(?:-\S+\s+)*(rm|clean)\b", _I)
_GIT_RESET_HARD = re.compile(r"\bgit\s+reset\b[^;&|]*--hard\b", _I)
# Código Python que apaga arquivos.
_PY_DELETE = re.compile(
    r"shutil\.rmtree|os\.(?:remove|unlink|rmdir|removedirs)\s*\(|\.unlink\s*\(|\.rmdir\s*\(|send2trash", _I
)
# SQL destrutivo.
_SQL_DESTRUCTIVE = re.compile(
    r"\bDROP\s+(?:TABLE|INDEX|VIEW|TRIGGER|DATABASE|SCHEMA)\b|\bDELETE\s+FROM\b|\bTRUNCATE\b", _I
)

# ---------------------------------------------------------------------------
# Padrões — BLOCK
# ---------------------------------------------------------------------------
_GIT_PUSH = re.compile(r"\bgit\s+(?:-\S+\s+)*push\b", _I)
_GIT_SWITCH_MAIN = re.compile(r"\bgit\s+(?:checkout|switch)\s+(?:-\S+\s+)*(?:main|master)(?![\w/\-.])", _I)
_GIT_BRANCH_DELETE = re.compile(r"\bgit\s+branch\s+(?:\S+\s+)*-(?:d|D|-delete)\b")
_GIT_REMOTE_EDIT = re.compile(r"\bgit\s+remote\s+(?:add|set-url|remove|rm|rename)\b", _I)
_GIT_CONFIG_WRITE = re.compile(r"\bgit\s+config\b(?![^;&|]*--(?:get|list|get-all|get-regexp)\b)", _I)

_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?<![\w])\.env(?![\w.\-])", _I),          # .env (mas não .env.example)
    re.compile(r"credentials[/\\]", _I),
    re.compile(r"\btoken\.json\b", _I),
    re.compile(r"\bprintenv\b", _I),
    re.compile(r"(?:^|[;&|]\s*)env\s*(?:$|[|;&>])", _I),     # `env` sem argumentos
    re.compile(r"\$\{?\w*(?:TOKEN|SECRET|API_KEY|PASSWORD|API_HASH)\w*\}?", _I),
    re.compile(r"\$env:\w*(?:TOKEN|SECRET|KEY|PASSWORD|HASH)", _I),
    re.compile(r"/proc/[^\s]*environ", _I),
    re.compile(r"\b(?:Get-ChildItem|gci|ls|dir)\s+env:", _I),
    re.compile(r"os\.environ|getenv\s*\(", _I),
)

_SECRET_PATH_PARTS = {".env", "token.json"}
_SECRET_DIRS = {"credentials"}

_SCRIPT_TOKEN = re.compile(r"[\w./\\\-]+\.(?:py|sh|sql|ps1)\b", _I)
_PYTEST = re.compile(r"\bpytest\b|-m\s+pytest\b", _I)
_GIT_COMMIT = re.compile(r"^\s*git\s+commit\b", _I)

_MAX_SCRIPT_BYTES = 256_000

# Chaves de argumentos de ferramentas que representam caminhos.
_PATH_KEY_HINTS = ("path", "file", "directory", "cwd", "dir")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _resolve(p: str, base: Path) -> Path:
    path = Path(p)
    if not path.is_absolute():
        path = base / path
    try:
        return path.resolve()
    except OSError:
        return path.absolute()


def is_inside(path: Path, workspace: Path) -> bool:
    try:
        path.resolve().relative_to(workspace.resolve())
        return True
    except (ValueError, OSError):
        return False


def _is_secret_path(path: Path) -> bool:
    name = path.name.lower()
    if name in _SECRET_PATH_PARTS:
        return True
    return any(part.lower() in _SECRET_DIRS for part in path.parts[:-1])


def _short(text: str, limit: int = 160) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _path_args(args: Mapping[str, Any]) -> Iterable[tuple[str, str]]:
    for key, value in args.items():
        if isinstance(value, str) and value and any(h in key.lower() for h in _PATH_KEY_HINTS):
            yield key, value


# ---------------------------------------------------------------------------
# Classificação de comandos
# ---------------------------------------------------------------------------
def classify_command(command: str, cwd: Path, workspace: Path) -> GuardDecision:
    """Classifica uma linha de comando de shell."""
    cmd = command or ""

    # ---- BLOCK -----------------------------------------------------------
    if _GIT_PUSH.search(cmd):
        return GuardDecision("block", "O push é feito pelo próprio harness ao final da tarefa (ou com /pr).", "git_push")
    if _GIT_SWITCH_MAIN.search(cmd):
        return GuardDecision("block", "Trocar para a main é proibido; trabalhe na branch do harness.", "git_branch")
    if _GIT_BRANCH_DELETE.search(cmd):
        return GuardDecision("block", "Apagar branches é proibido no harness.", "git_branch")
    if _GIT_REMOTE_EDIT.search(cmd) or _GIT_CONFIG_WRITE.search(cmd):
        return GuardDecision("block", "Alterar remote/config do git é proibido no harness.", "git_config")
    for pat in _SECRET_PATTERNS:
        if pat.search(cmd):
            return GuardDecision("block", "Acesso a segredos/variáveis de ambiente é proibido.", "secrets")

    # ---- CONFIRM ---------------------------------------------------------
    is_commit = bool(_GIT_COMMIT.search(cmd))  # mensagens de commit podem conter "rm", "delete"…
    if not is_commit:
        if _GIT_DELETE.search(cmd) or _GIT_RESET_HARD.search(cmd):
            return GuardDecision("confirm", f"🗑️ Apagar/descartar arquivos via git: `{_short(cmd)}`", "delete")
        if _SHELL_DELETE.search(cmd) or _FIND_DELETE.search(cmd) or _PY_DELETE.search(cmd):
            return GuardDecision("confirm", f"🗑️ Apagar arquivos/pastas: `{_short(cmd)}`", "delete")
        if _SQL_DESTRUCTIVE.search(cmd):
            return GuardDecision("confirm", f"🗄️ SQL destrutivo (DROP/DELETE/TRUNCATE): `{_short(cmd)}`", "sql")

        # Scripts do workspace executados pelo comando (exceto pytest).
        if not _PYTEST.search(cmd):
            decision = _scan_scripts(cmd, cwd, workspace)
            if decision is not None:
                return decision

    return ALLOW


def _scan_scripts(cmd: str, cwd: Path, workspace: Path) -> GuardDecision | None:
    for token in _SCRIPT_TOKEN.findall(cmd):
        script = _resolve(token.strip("'\""), cwd)
        if not is_inside(script, workspace) or not script.is_file():
            continue
        try:
            content = script.read_bytes()[:_MAX_SCRIPT_BYTES].decode("utf-8", errors="ignore")
        except OSError:
            continue
        suffix = script.suffix.lower()
        rel = script.relative_to(workspace.resolve()) if is_inside(script, workspace) else script
        if _SQL_DESTRUCTIVE.search(content):
            return GuardDecision("confirm", f"🗄️ O script `{rel}` contém SQL destrutivo (DROP/DELETE/TRUNCATE).", "sql")
        if suffix == ".py" and _PY_DELETE.search(content):
            return GuardDecision("confirm", f"🗑️ O script `{rel}` apaga arquivos (rmtree/remove/unlink).", "delete")
        if suffix in (".sh", ".ps1") and (_SHELL_DELETE.search(content) or _FIND_DELETE.search(content)):
            return GuardDecision("confirm", f"🗑️ O script `{rel}` apaga arquivos.", "delete")
    return None


# ---------------------------------------------------------------------------
# API principal
# ---------------------------------------------------------------------------
def classify(tool_name: str, args: Mapping[str, Any] | None, workspace: Path | str) -> GuardDecision:
    """Classifica uma chamada de ferramenta do agente."""
    ws = Path(workspace).resolve()
    args = dict(args or {})
    name = (tool_name or "").lower()

    if name == "run_command":
        cwd_raw = args.get("Cwd") or args.get("cwd") or str(ws)
        cwd = _resolve(str(cwd_raw), ws)
        if not is_inside(cwd, ws):
            return GuardDecision("block", f"Diretório fora do workspace: `{_short(str(cwd_raw))}`", "outside_workspace")
        command = str(args.get("CommandLine") or args.get("command") or "")
        return classify_command(command, cwd, ws)

    # Ferramentas de arquivo (view/create/edit/list/search/find…)
    for key, raw in _path_args(args):
        path = _resolve(raw, ws)
        if not is_inside(path, ws):
            return GuardDecision("block", f"Caminho fora do workspace ({key}): `{_short(raw)}`", "outside_workspace")
        if _is_secret_path(path):
            return GuardDecision("block", f"Arquivo de segredos protegido: `{_short(raw)}`", "secrets")

    return ALLOW
