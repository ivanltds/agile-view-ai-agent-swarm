# Comece aqui 👋

Este programa gera um **relatório de eficiência do time** a partir do Azure DevOps Boards.
Você não precisa saber programar. Siga os 3 passos abaixo.

---

## O que você precisa ter em mãos

Antes de começar, tenha estas informações (peça ao time técnico se não souber):

| Informação | Onde encontrar |
|---|---|
| **Chave de IA** (veja opções abaixo) | Depende do provedor escolhido |
| **Organização do Azure DevOps** | No endereço: `dev.azure.com/SUA-ORGANIZACAO` |
| **Nome do projeto** | No menu do Azure DevOps |
| **Nome do time** | Em Configurações do Projeto → Times |
| **Token do Azure (PAT)** | Veja o passo "Criar o token" abaixo |

### Chave de IA — escolha um dos provedores

Você pode usar **qualquer um** dos provedores abaixo:

| Provedor | Como a chave começa | Onde obter |
|---|---|---|
| **Anthropic (Claude)** | `sk-ant-` | console.anthropic.com → API Keys |
| **OpenAI (GPT)** | `sk-` | platform.openai.com → API Keys |
| **DeepSeek** | qualquer | platform.deepseek.com → API Keys |
| **Google Gemini** | `AIza` | aistudio.google.com → Get API Key |

> O programa detecta o provedor automaticamente pela chave. Não é necessário configurar nada além de colar a chave.

---

## Passo 1 — Instalar o Python (só na primeira vez)

1. Acesse https://www.python.org/downloads/
2. Clique no botão grande de download e abra o instalador.
3. **MUITO IMPORTANTE:** na primeira tela, marque a caixinha
   **"Add Python to PATH"** antes de clicar em *Install Now*.
4. Quando terminar, feche o instalador.

Se o Python já estiver instalado, pule este passo.

---

## Passo 2 — Gerar o relatório

1. Abra a pasta do programa.
2. Dê **dois cliques** no arquivo **`GERAR-RELATORIO.bat`**.
3. Uma janela preta vai abrir. Na primeira vez ela leva 1–2 minutos
   se preparando — isso é normal.
4. O programa vai te fazer algumas perguntas. Digite cada resposta
   e aperte **Enter**.
   - Ao digitar a chave e o token, **os caracteres ficam invisíveis**
     (por segurança). Pode digitar normalmente e apertar Enter.
5. Pronto! O relatório abre sozinho no seu navegador.

> Da segunda vez em diante, o programa lembra das suas respostas e é mais rápido.

---

## Passo 3 — Ver o resultado

O relatório abre automaticamente no navegador. Ele também fica salvo como um
arquivo `report_...html` dentro da pasta — você pode enviá-lo por e-mail ou
abrir de novo quando quiser, é só dar dois cliques.

---

## Criar o token do Azure (PAT)

1. Entre em `https://dev.azure.com/SUA-ORGANIZACAO`.
2. Clique no ícone do seu perfil (canto superior direito) →
   **Personal access tokens**.
3. Clique em **New Token**.
4. Dê um nome (ex.: `relatorio`).
5. Em **Scopes**, escolha **Custom defined** e marque:
   - **Work Items** → Read
   - **Project and Team** → Read
6. Clique em **Create** e **copie o token na hora** — ele não aparece de novo.

---

## Deu algum problema?

| O que apareceu | O que fazer |
|---|---|
| "Python nao foi encontrado" | Faça o Passo 1 e marque "Add Python to PATH". |
| "401" ou "Unauthorized" | O token do Azure expirou ou está errado. Crie um novo. |
| "404 — not found" | Confira se o nome do projeto/time está exatamente igual ao do Azure. |
| O relatório abriu sem gráficos | Abra o arquivo com a internet conectada. |
| "Unknown AI provider" | A chave de IA não foi reconhecida. Verifique se colou corretamente. |
| Quero só testar se o acesso funciona | Dê dois cliques em **`TESTAR-CONEXAO.bat`**. |

Se travar, chame alguém do time técnico e mostre a mensagem da janela preta.
