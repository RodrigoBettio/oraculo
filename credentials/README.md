# 🔐 Credenciais do Google Drive - Oráculo

Para acessar pastas privadas do Google Drive que foram **compartilhadas com a sua conta pessoal**, utilizamos autenticação **OAuth 2.0**.

Desta forma, o Oráculo enxerga automaticamente todas as pastas e arquivos de **"Compartilhados comigo"**, sem necessidade de tornar nada público nem de pedir permissão especial ao dono da pasta.

---

## 🚀 Passo a Passo: Gerando seu `credentials.json` (Leva 2 minutos)

1. Acesse o **[Google Cloud Console](https://console.cloud.google.com/)** (gratuito com qualquer conta Google/Gmail).
2. Se não tiver um projeto criado, clique no topo e crie um novo projeto (ex: `Oraculo-Drive`).
3. Vá no menu lateral em **APIs e Serviços** -> **Biblioteca** (Library):
   - Pesquise por **Google Drive API** e clique em **Ativar** (Enable).
4. Vá em **APIs e Serviços** -> **Tela de permissão OAuth** (OAuth Consent Screen):
   - Tipo de usuário: escolha **Externo** e clique em Criar.
   - Nome do app: digite `Oráculo`.
   - E-mail de suporte e Desenvolvedor: coloque o seu próprio e-mail do Gmail.
   - Clique em Salvar e Continuar.
   - Na etapa **Usuários de teste** (Test Users): clique em **+ ADD USERS** e digite o **seu e-mail do Gmail** (o mesmo com quem a pasta foi compartilhada).
   - Salve até o final.
5. Vá em **APIs e Serviços** -> **Credenciais**:
   - Clique em **+ Criar Credenciais** -> **ID do cliente OAuth** (OAuth client ID).
   - Tipo de aplicativo: selecione **App para computador** (Desktop app).
   - Nome: `Oráculo Desktop`.
   - Clique em **Criar**.
6. Uma janela abrirá com o seu ID do cliente. Clique no botão **Fazer o download do JSON** (ícone de download no final da linha da credencial criada).
7. Renomeie o arquivo baixado para **`credentials.json`** e salve-o nesta pasta:
   ```
   C:\Users\Rodrigo\.gemini\antigravity\scratch\oraculo\credentials\credentials.json
   ```

---

## 🔑 Como Conectar e Ativar

Depois de colocar o `credentials.json` aqui, basta rodar o comando no terminal:

```powershell
.\.venv\Scripts\python -m ingestion.drive_auth
```

O script irá:
1. Abrir seu navegador padrão para você autorizar com a sua conta Google com segurança (permissão somente leitura).
2. Gerar automaticamente o `token.json` nesta mesma pasta (com refresh token, nunca precisará logar de novo).
3. Listar todas as suas pastas de **"Compartilhados comigo"**.
4. Permitir você escolher a pasta do curso com um simples número e salvar direto no sistema!
