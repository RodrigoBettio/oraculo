# Automação com Hooks no Claude Code

## Resumo
Nesta aula é apresentado o conceito de **Hooks** no Claude Code, que permite associar eventos de execução do agente a comandos de terminal ou scripts personalizados. Os Hooks garantem que automações essenciais (como testes, linting, regras de segurança e notificação) sejam executadas de forma transparente e obrigatória.

---

## Principais Conceitos
- **PreToolUse:** Executa ações antes que o agente utilize uma ferramenta (ex: bloquear leitura de arquivo `.env`).
- **PostToolUse:** Executa ações imediatamente após o agente utilizar uma ferramenta (ex: formatar código com `npm run lint -- --fix`).
- **Stop:** Executa um script ao finalizar a tarefa (ex: enviar notificação via webhook).
- **UserPromptSubmit:** Permite intercetar ou tratar prompts antes do envio.

---

## Exemplo de Configuração (`.claude/settings.json`)

```json
// .claude/settings.json - hooks
{
  "hooks": {
    "PostToolUse": [{
      "matcher": "Edit|Write",
      "hooks": [
        { "command": "npm run lint -- --fix" },
        { "command": "npm run typecheck" }
      ]
    }],
    "Stop": [{
      "hooks": [
        { "command": "./scripts/notify-discord.sh" }
      ]
    }]
  }
}
```

---

## Timestamps & Conteúdo Detalhado
- **00:00 - 00:40**: O que são Hooks e tipos de eventos (`PreToolUse`, `PostToolUse`).
- **00:40 - 01:43**: Casos práticos (segurança, linters, 'Doc as Code').
- **01:43 - 02:25**: Configurando scripts `.sh` e `JavaScript` no `settings.json`.