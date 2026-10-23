# Recuperação local

Antes de alterações extensas futuras, copie o código ou faça commit revisado. O repositório inicial estava vazio; o histórico local desta entrega serve como base de recuperação.

Use Configurações → Criar backup consistente do banco. Os backups SQLite ficam em `data/backups`. Eles não incluem os arquivos binários: copie também `data/evidence` para armazenamento autorizado. Proteja os backups como os dados originais.

Para restaurar, encerre o processo Streamlit, preserve uma cópia de toda a pasta `data`, restaure o backup como `data/qa-lsf.sqlite3` e as evidências correspondentes. Não copie um SQLite ativo diretamente sem seu WAL. Reinicie pelo inicializador. Os índices fazem parte do backup transacional.

Se a interface não abrir, consulte `app-error.log` e `app.log`. O inicializador reutiliza um servidor saudável na porta 8501; uma aplicação diferente usando a mesma porta exige encerrar o conflito. Não apague dados para corrigir inicialização.

Se `.venv` for perdida, recrie com Python 3.12: `python -m venv .venv` e `.venv\Scripts\python.exe -m pip install -r requirements-lock.txt`. No ambiente desta entrega também há Python em `C:\Users\lucas.faht\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`. Esses comandos são instruções de contingência; a instalação inicial já foi feita.

O código pode ser recuperado do Git local. Banco e anexos são ignorados por Git e precisam dos próprios backups. Não há push ou cópia remota automática.
