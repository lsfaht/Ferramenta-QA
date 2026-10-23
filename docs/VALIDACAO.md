# Validação — 23/10/2026

Foram executados `pytest -q`, `ruff check .` e `python -m compileall -q app.py qa_lsf`. Resultado: **31 testes aprovados**, Ruff sem problemas e compilação bem-sucedida.

Cobertura executada:

- Cadastro, identificadores duplicados, campos obrigatórios, SQLite reaberto e auditoria.
- Criação e edição de casos, snapshot imutável da definição na execução, vínculo da execução à tarefa e exigência de observação para resultados finais.
- Estados válidos, conclusão da tarefa condicionada à revisão de conhecimento, propostas duplicadas, aprovação com revisor e proteção da regra confirmada.
- Busca por ID, título, caixa, acentos, termos parciais, texto de execuções e regras; sincronização após edição; entradas especiais sem execução SQL; paginação.
- Filtros combinados de sistema, status, tipo de teste, período e existência de registros relacionados.
- Reutilização com IDs próprios e preservação da origem e do histórico de execução.
- Evidências com SHA-256, duplicidade, restrição de extensão e detecção de alteração; exportação Markdown/HTML, escape de HTML e backup SQLite legível.
- Redação básica de credenciais e IA indisponível sem autenticação.
- AppTest: dashboard vazio, todas as nove áreas com registros persistidos, cadastro via formulário e nova instância do aplicativo.
- AppTest: fluxo completo com criação de caso, execução aprovada por registro humano, proposta, aprovação editorial, revisão do ciclo, pesquisa com filtros, abertura de detalhes, controles de download e reutilização de caso.

Dados sintéticos explicitamente identificados como TESTE FICTÍCIO foram criados em diretórios temporários independentes do banco operacional. O banco operacional inicia sem tarefas, execuções ou regras fictícias.

Servidor real iniciado em 127.0.0.1:8501, encerrado e reiniciado pelo inicializador Windows; endpoint de saúde respondeu `ok` após o reinício. O banco operacional continuou com zero tarefas e `PRAGMA integrity_check` retornou `ok`. Navegador Playwright abriu QA LSF e verificou a página Histórico de Tarefas, o campo de pesquisa e os filtros avançados. Tentativas posteriores de navegação foram interrompidas pelo encerramento da sessão do navegador; não se afirma validação visual completa de todas as telas. Essas telas foram verificadas com AppTest.

Não foram executadas homologações corporativas, requisições de IA autenticadas, publicação em cards, processamento automático de evidências ou exportação PDF. Resultados dos testes da plataforma não representam aprovação de OMS, VTEX, ERP ou outro sistema.
