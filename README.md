# QA LSF

Aplicação local de homologação com tarefas, histórico pesquisável, casos reutilizáveis, execuções imutáveis, evidências, relatórios e conhecimento revisado por pessoas.

## Abrir

Clique duas vezes em **Iniciar QA LSF.cmd**. A aplicação abre em http://127.0.0.1:8501 e aceita conexões somente locais. O ambiente Python já foi instalado em `.venv`.

## Operação

1. Cadastre uma tarefa em Gestão de tarefas, informando sistema/projeto e critérios de aceite.
2. Registre análise de riscos e cobertura em Planejamento.
3. Crie casos ou reutilize casos de outra tarefa. A cópia mantém IDs de origem e não copia execuções.
4. Registre cada execução com responsável, ambiente, build e resultado observado. Registre defeitos e anexe evidências.
5. Proponha conhecimento, indique fontes e submeta à revisão humana. Revise também o ciclo da tarefa, inclusive quando não houver descoberta.
6. Consolide o resultado humano na tarefa e exporte relatórios Markdown/HTML.
7. Use Histórico de Tarefas para buscar IDs, termos parciais, casos, observações, execuções e regras, combinando filtros.

Não existem dados demonstrativos no banco operacional. Testes usam diretórios temporários separados.

## Estrutura

- `app.py`: interface Streamlit, navegação e formulários.
- `qa_lsf/store.py`: serviço de domínio, SQLite, FTS5 trigram, auditoria, evidências, reutilização e backup.
- `qa_lsf/reports.py`: exportação Markdown/HTML e comentário de card.
- `qa_lsf/agent.py`: adaptador HTTP de IA, sem ferramentas ou execução de comandos.
- `qa_lsf/integrations.py`: contrato para publicação futura em cards.
- `.agents/skills/`: nove procedimentos especializados.
- `templates/`: dez modelos de documentação.
- `tests/`: testes de regras de negócio e interface Streamlit.
- `docs/`: decisões, referências, validação e recuperação.
- `data/`: banco, evidências e backups locais, ignorados por Git.
- `artifacts/`: documentos exportados; ignorados por padrão para evitar inclusão acidental de dados corporativos. Após revisão, pode-se adicioná-los explicitamente ao Git.

## IA e integrações

Nenhum modelo autenticado está conectado por padrão. O uso desta aplicação dentro do Codex não concede acesso ao modelo. O fluxo manual funciona independentemente de IA.

O adaptador aceita um endpoint HTTPS compatível com Chat Completions usando `QA_LSF_AI_URL`, `QA_LSF_AI_KEY` e `QA_LSF_AI_MODEL`. O botão de análise exige autorização explícita de envio do contexto. A resposta deve ser JSON com `summary`, `findings` e `sources`; só é apresentada como proposta. O adaptador não foi validado com um serviço autenticado neste ambiente.

Azure DevOps e GitLab: URL, abertura do card e comentário copiável disponíveis; publicação autenticada não implementada. Não há conexão a bancos, Kafka ou APIs corporativas, nem automação de navegador dos sistemas homologados. Similaridade é determinística, por palavras e módulo. PDF não habilitado.

## Desenvolvimento e recuperação

Consulte `docs/RECUPERACAO.md`. Verificações: `.venv\Scripts\python.exe -m pytest -q`, `.venv\Scripts\ruff.exe check .`.

O escopo inicial é local e de um usuário. Não exponha a aplicação na rede. Há redação básica de padrões de credenciais em campos de texto; ela não substitui revisão humana, especialmente em arquivos anexados. Não anexe dados pessoais ou segredos.
