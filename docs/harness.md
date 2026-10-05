# 🛠️ Telegram Harness — Especificação & Guia

> Agente de desenvolvimento (Antigravity SDK) controlado pelo tópico **🛠️ Harness** do grupo do Oráculo.
> Trabalha num clone isolado, na branch fixa `telegram-dev`, e entrega via Pull Request para a `main`.

## 1. Requisitos

| ID | Requisito |
|---|---|
| R1 | Aceitar mensagens **somente** de `HARNESS_ALLOWED_USER_ID`, no chat `HARNESS_CHAT_ID` e tópico `HARNESS_TOPIC_ID` (ou chat privado com o bot, se `HARNESS_ALLOW_PRIVATE=true`). Todo o resto é ignorado e logado. |
| R2 | Cada texto vira um prompt para o agente. Uma sessão (agente vivo) persiste entre prompts até `/novo`, ociosidade (`HARNESS_IDLE_MINUTES`, padrão 120) ou erro. |
| R3 | Somente **uma tarefa por vez**. Prompts recebidos durante uma tarefa são recusados com aviso (use `/parar`). |
| R4 | Limite por tarefa: `HARNESS_TASK_TIMEOUT_MIN` (padrão 45) + orçamento de chamadas (`HARNESS_MAX_TOOL_CALLS`, padrão 200). |
| R5 | Workspace = clone em `HARNESS_WORKDIR` (padrão `/srv/harness/oraculo`), branch `HARNESS_BRANCH` (padrão `telegram-dev`). No `/novo`: `fetch` + `merge origin/main`; conflito → aborta merge e reporta. |
| R6 | **Guard** classifica toda chamada de ferramenta: `allow`, `confirm` (botões ✅/❌, timeout 10 min = recusado) ou `block`. |
| R7 | Ao fim de cada tarefa com alterações: commit, push para `telegram-dev`, cria PR `telegram-dev → main` se não existir, ou comenta no PR aberto com o resumo. |
| R8 | Progresso numa única mensagem editada (throttle ≥ 2 s, ≤ 4096 chars) + mensagem final com resumo, `git diff --stat`, commit e link do PR. |
| R9 | Segredos (`HARNESS_BOT_TOKEN`, `GITHUB_TOKEN_HARNESS`) são removidos de `os.environ` após o carregamento e mascarados em qualquer texto enviado ao Telegram. |

## 2. Regras do Guard

| Classe | Gatilhos |
|---|---|
| ✅ **confirm** (pede aprovação) | Apagar arquivos/pastas: `rm`, `rmdir`, `del`, `erase`, `rd`, `Remove-Item`, `unlink`, `shred`, `git rm`, `git clean`, `find … -delete`, `shutil.rmtree`, `os.remove`, `os.unlink`, `os.rmdir`, `Path.unlink/rmdir`, `git reset --hard`. SQL destrutivo: `DROP`, `DELETE FROM`, `TRUNCATE`. Vale para o comando **e** para scripts `.py/.sh/.sql` do workspace que o comando executar. |
| ⛔ **block** (nunca roda) | `git push` (o harness faz o push), `git checkout/switch main\|master`, `git branch -D/-d`, alterar `git remote`/`git config`; `cwd` ou arquivos fora do workspace; ler/expor segredos (`.env`, `credentials/`, `token.json`, `printenv`, `env`, `$GITHUB_TOKEN`, `/proc/*/environ`). |
| 🟢 **allow** | Todo o resto (editar/criar arquivos no workspace, rodar testes, instalar dependências, pesquisar na web…). |

## 3. Comandos

| Comando | Ação |
|---|---|
| texto livre | prompt para o agente |
| `/novo` | encerra sessão, sincroniza com `main`, nova sessão |
| `/parar` | cancela a tarefa em execução |
| `/status` | branch, último commit, PR, sessão, tarefa ativa |
| `/pr` | commit + push do pendente e link do PR |
| `/diff` | diff completo (`telegram-dev` vs `origin/main`) como `.patch` |
| `/ajuda` | lista os comandos |

## 4. Arquitetura (módulos em `harness/`)

| Módulo | Responsabilidade |
|---|---|
| `config.py` | `HarnessSettings` (env) + remoção/máscara de segredos |
| `guard.py` | `classify(tool, args, workspace) -> GuardDecision` (puro, testável) |
| `approvals.py` | `ApprovalBroker`: futures por pedido, timeout, auditoria |
| `progress.py` | `ProgressReporter`: eventos, renderização, throttle, truncamento |
| `workspace.py` | Operações git assíncronas (clone, sync, commit, push, diff) |
| `github_pr.py` | API REST do GitHub (stdlib `urllib`): achar/criar PR, comentar |
| `session.py` | Ciclo de vida do `Agent` + hooks (guard, progresso) |
| `bridge.py` | Bot Telethon: filtro, comandos, botões, orquestração |
| `__main__.py` | `python -m harness` |

## 5. Deploy (VM)

```bash
# 1) .env na VM (mesmo arquivo do Oráculo) — adicionar:
HARNESS_BOT_TOKEN=...            # bot "Oráculo Dev" (BotFather)
HARNESS_ALLOWED_USER_ID=...      # seu user id do Telegram
HARNESS_CHAT_ID=-100...          # id do grupo do Oráculo
HARNESS_TOPIC_ID=...             # id do tópico 🛠️ Harness
GITHUB_TOKEN_HARNESS=github_pat_...
HARNESS_REPO=RodrigoBettio/oraculo

# 2) subir
docker compose --profile harness up -d --build harness
docker compose logs -f harness
```

Descobrir IDs: envie `/whoami` no tópico Harness — o bot responde com `user_id`, `chat_id` e `topic_id` (este comando funciona mesmo antes de configurar os IDs, mas só responde e não executa nada).

## 6. Recuperação

| Sintoma | Ação |
|---|---|
| Bot não responde | `docker compose logs harness`; conferir IDs com `/whoami` |
| Merge com conflito no `/novo` | peça ao agente: "resolva o conflito com a main" |
| Tarefa travada | `/parar`; se persistir `docker compose restart harness` |
| PR não criado | conferir escopo do `GITHUB_TOKEN_HARNESS` (Contents + Pull requests: RW) |
