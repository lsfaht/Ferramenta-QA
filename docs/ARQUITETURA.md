# Decisões técnicas — QA LSF

O workspace tinha somente `.git`, sem commit, código ou ZIP anterior acessível nas pastas consultadas (workspace, Documents/ChatGPT, Documents, Desktop e Downloads). Não foi presumido conteúdo do OMS QA Copilot.

Python 3.12, Streamlit e SQLite atendem ao uso local sem serviço externo. O ambiente é isolado em `.venv`; dependências diretas fixadas e transitivas registradas no lock. A porta escuta somente 127.0.0.1.

SQLite mantém entidades com IDs estáveis, payloads JSON e índice por tarefa/tipo. O serviço valida campos, estados, duplicidades e vínculos críticos. Registros de execução guardam snapshot do caso. Auditoria armazena antes/depois, responsável e horário UTC. A interface apresenta horários ISO com fuso explícito.

FTS5 com tokenizador trigram permite correspondência parcial em termos a partir de três caracteres. Termos menores usam varredura de texto normalizado. Acentos e caixa são normalizados. O índice agregado de cada tarefa é atualizado na mesma transação das alterações. Filtros combinam dados da tarefa e relações. Resultados são paginados na interface; filtros relacionais ainda são avaliados em Python, uma limitação para bases muito grandes.

O banco é canônico. Relatórios Markdown/HTML são snapshots derivados e exportados atomicamente, preparados para revisão e Git. Não há sincronização bidirecional. Evidências têm nomes aleatórios e SHA-256; downloads verificam integridade. Conteúdo binário não é indexado nem analisado automaticamente.

Não existem subprocessos disparados por documentos, ferramentas de shell na IA ou publicação automática. Conteúdo remoto é dado não confiável. HTML exportado escapa texto antes de renderizar. Credenciais de IA vêm somente do ambiente. A redação de segredos é heurística e não cobre todos os formatos.

Cada tarefa inicia um ciclo de conhecimento pendente. Conclusão exige revisão do ciclo. Estado epistemológico e editorial são independentes. Regra confirmada e aprovada é protegida contra sobrescrita; uma descoberta conflitante precisa de nova proposta com ID da regra relacionada.

Limites atuais: não há autenticação multiusuário, detecção semântica de contradições, leitura automática de PDF/imagem, execução de SQL/REST corporativos ou mecanismo completo de agentes. As skills documentam procedimentos invocáveis no Codex; a UI oferece análise de requisitos pelo adaptador, quando configurado. Preferências de documentação e exportação são armazenadas; ainda não alteram todos os formulários. Diretórios operacionais são escolhidos por QA_LSF_DATA ao iniciar, mantendo banco e evidências juntos.

Evoluções: extrair serviços por domínio e migrações versionadas, melhorar desempenho dos filtros SQL, adicionar contratos de IA por skill com fontes verificáveis, links de cobertura estruturados, testes E2E completos e integrações corporativas autorizadas somente leitura.
