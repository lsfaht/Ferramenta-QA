import os
from pathlib import Path

import streamlit as st

from qa_lsf.agent import AIProvider
from qa_lsf.reports import as_html, card_comment, export, report
from qa_lsf.store import EDITORIAL, KNOWLEDGE_STATES, RESULTS, TASK_STATES, Store

ROOT = Path(__file__).parent
store = Store(os.getenv("QA_LSF_DATA", str(ROOT / "data")))
st.set_page_config(page_title="QA LSF", page_icon="🧭", layout="wide")
st.markdown(
    """<style>.stApp{background:#f7f9fc}h1,h2,h3{color:#142d50}[data-testid="stSidebar"]{background:#142d50}[data-testid="stSidebar"] *{color:#eff6ff}div[data-testid="stMetric"]{background:white;border:1px solid #e2e8f0;border-radius:12px;padding:16px}.stButton>button{border-radius:8px}</style>""",
    unsafe_allow_html=True,
)
st.sidebar.title("🧭 QA LSF")
st.sidebar.caption("Histórico • Testes • Conhecimento")
menu = [
    "Dashboard",
    "Gestão de tarefas",
    "Histórico de Tarefas",
    "Planejamento",
    "Casos de teste",
    "Execução de testes",
    "Base de conhecimento",
    "Relatórios",
    "Configurações",
]
page = st.sidebar.radio("Navegação", menu)
st.sidebar.caption("Local • SQLite • Revisão humana")
st.title(page)
st.caption("Homologação assistida e rastreável | QA LSF")


def save(kind, data, task_id=None, entity_id=None):
    try:
        ident = store.save(
            kind,
            data,
            task_id,
            entity_id,
            data.get("reviewer") or data.get("responsible") or "QA local",
        )
        st.success(f"Registro salvo: {ident}")
        return ident
    except (ValueError, OSError) as error:
        st.error(str(error))
        return None


def select_task(label="Tarefa", key=None):
    tasks = store.list("task")
    if not tasks:
        st.info("Cadastre uma tarefa para começar.")
        return None
    return st.selectbox(
        label, tasks, format_func=lambda t: f"{t['identifier']} · {t['title']}", key=key
    )


def details(task, context="task"):
    st.subheader(f"{task['identifier']} · {task['title']}")
    st.write(f"{task['system']} / {task.get('module', '')} · {task['status']}")
    st.write(task.get("description", ""))
    st.markdown("**Critérios de aceite**")
    st.write(task.get("acceptance", ""))
    if task.get("url"):
        st.link_button("Abrir card original", task["url"])
    for kind, title in [
        ("plan", "Plano de testes"),
        ("case", "Casos de teste"),
        ("execution", "Histórico de execuções"),
        ("attachment", "Documentos e evidências"),
        ("defect", "Defeitos"),
        ("knowledge", "Conhecimento produzido"),
    ]:
        with st.expander(title):
            items = store.list(kind, task["id"])
            if not items:
                st.caption("Sem registros.")
            for item in items:
                st.json(item, expanded=False)
                if kind == "attachment":
                    try:
                        st.download_button(
                            item["title"],
                            store.evidence(item),
                            file_name=item["title"],
                            key="dl-" + context + item["id"],
                        )
                    except (ValueError, OSError) as error:
                        st.error(str(error))
    with st.expander("Relatório de homologação e documentos exportados"):
        st.markdown(report(store, task["id"]))
        st.caption(
            f"Artefatos: artifacts/{task['id']}/relatorio.md e relatorio.html (após exportar em Relatórios)."
        )
    with st.expander("Histórico de alterações da tarefa"):
        st.json(store.history(task["id"]), expanded=False)
    with st.expander("Homologações relacionadas — busca determinística por palavras e módulo"):
        st.write(
            [
                {k: t.get(k) for k in ["id", "identifier", "title", "module"]}
                for t in store.similar(task)
            ]
        )


def search_ui(advanced=False):
    if st.button("Limpar pesquisa e filtros"):
        for key in list(st.session_state):
            if key.startswith("filter-"):
                del st.session_state[key]
        st.rerun()
    query = st.text_input("Pesquisar ID, título, regra, caso ou resultado", key="filter-query")
    filters = {}
    if advanced:
        tasks = store.list("task")
        with st.expander("Filtros avançados", expanded=True):
            cols = st.columns(3)
            fields = [
                ("system", "Sistema/projeto"),
                ("module", "Módulo"),
                ("status", "Status"),
                ("result", "Resultado da homologação"),
                ("priority", "Prioridade"),
                ("environment", "Ambiente"),
                ("responsible", "Responsável"),
            ]
            for n, (field, label) in enumerate(fields):
                filters[field] = cols[n % 3].selectbox(
                    label,
                    [""] + sorted({t.get(field, "") for t in tasks} - {""}),
                    key="filter-" + field,
                )
            filters["test_type"] = cols[1].selectbox(
                "Tipo de teste",
                [
                    "",
                    "Positivo",
                    "Negativo",
                    "Integração",
                    "Regressão",
                    "Limite",
                    "Exploratório",
                ],
                key="filter-type",
            )
            for key, label in [
                ("has_defects", "Defeitos"),
                ("has_evidence", "Evidências"),
                ("has_knowledge", "Conhecimento relacionado"),
            ]:
                value = cols[2].selectbox(label, ["Todos", "Sim", "Não"], key="filter-" + key)
                filters[key] = None if value == "Todos" else value == "Sim"
            filters["from"] = cols[0].date_input(
                "Execução a partir de", value=None, key="filter-from"
            )
            filters["to"] = cols[1].date_input("Execução até", value=None, key="filter-to")
    order = st.selectbox(
        "Ordenar por",
        ["updated", "title", "last_run"],
        format_func=lambda k: {
            "updated": "Atualização mais recente",
            "title": "Título",
            "last_run": "Última execução",
        }[k],
    )
    page_number = st.number_input("Página", min_value=1, value=1, step=1, key="filter-page")
    items, total = store.search(query, filters, order, page_number - 1)
    st.caption(f"{total} tarefas encontradas · 20 por página")
    for item in items:
        with st.expander(
            f"{item['identifier']} · {item['title']} | {item['system']} · {item['status']}"
        ):
            st.write(
                f"Módulo: {item.get('module', '')} | Casos: {item['cases']} | Aprovações: {item['passed']} | Reprovações: {item['failed']} | Última execução: {item['last_run']}"
            )
            if st.button("Abrir detalhes", key=item["id"]):
                st.session_state["detail"] = item["id"]
    if st.session_state.get("detail"):
        details(store.get(st.session_state["detail"]))


if page == "Dashboard":
    tasks, cases, runs, rules = [store.list(k) for k in ["task", "case", "execution", "knowledge"]]
    metrics = [
        ("Tarefas", len(tasks)),
        ("Em andamento", sum(t["status"] == "Em andamento" for t in tasks)),
        ("Homologações concluídas", sum(t["status"] == "Concluída" for t in tasks)),
        ("Casos de teste", len(cases)),
        ("Execuções aprovadas", sum(r["status"] == "Aprovado" for r in runs)),
        ("Execuções reprovadas", sum(r["status"] == "Reprovado" for r in runs)),
        ("Execuções bloqueadas", sum(r["status"] == "Bloqueado" for r in runs)),
        ("Regras aprovadas", sum(r["editorial"] == "Aprovado" for r in rules)),
        (
            "Propostas pendentes",
            sum(r["editorial"] in ["Proposto", "Em revisão"] for r in rules),
        ),
    ]
    cols = st.columns(3)
    for i, (label, value) in enumerate(metrics):
        cols[i % 3].metric(label, value)
    st.subheader("Busca rápida de tarefas")
    search_ui()

elif page == "Gestão de tarefas":
    mode = st.radio("Ação", ["Criar", "Editar"], horizontal=True)
    existing = select_task() if mode == "Editar" else None
    d = existing or {}
    with st.form("task"):
        cols = st.columns(2)
        data = {}
        for i, (key, label) in enumerate(
            [
                ("identifier", "ID da tarefa *"),
                ("title", "Título *"),
                ("system", "Sistema/projeto *"),
                ("module", "Módulo"),
                ("url", "URL do card"),
                ("responsible", "Responsável"),
                ("environment", "Ambiente"),
                ("keywords", "Palavras-chave"),
            ]
        ):
            data[key] = cols[i % 2].text_input(label, value=d.get(key, ""))
        data["description"] = st.text_area("Descrição", d.get("description", ""))
        data["acceptance"] = st.text_area("Critérios de aceite", d.get("acceptance", ""))
        data["priority"] = st.selectbox(
            "Prioridade",
            ["Alta", "Média", "Baixa"],
            index=["Alta", "Média", "Baixa"].index(d.get("priority", "Média")),
        )
        data["status"] = st.selectbox(
            "Status", TASK_STATES, index=TASK_STATES.index(d.get("status", "Nova"))
        )
        options = [
            "Não avaliada",
            "Aprovada",
            "Aprovada com ressalvas",
            "Reprovada",
            "Bloqueada",
        ]
        data["result"] = st.selectbox(
            "Resultado da homologação (avaliação humana)",
            options,
            index=options.index(d.get("result", "Não avaliada")),
        )
        if st.form_submit_button("Salvar tarefa"):
            save("task", data, entity_id=d.get("id"))
    task = select_task("Consultar / anexar", "attach-task")
    if task:
        uploaded = st.file_uploader(
            "Documentação autorizada — até 20 MB",
            type=["png", "jpg", "jpeg", "pdf", "txt", "md", "csv", "json", "log"],
        )
        st.caption("Arquivos ficam locais. Remova dados pessoais e credenciais antes de anexar.")
        if uploaded and st.button("Anexar documento"):
            try:
                store.attach(task["id"], uploaded.name, uploaded.getvalue())
                st.success("Documento anexado.")
            except ValueError as error:
                st.error(str(error))
        details(task)

elif page == "Histórico de Tarefas":
    search_ui(True)

elif page == "Planejamento":
    task = select_task()
    if task:
        st.info(
            "Planejamento manual disponível. Sugestões de IA exigem provedor configurado e revisão humana."
        )
        plans = store.list("plan", task["id"])
        d = plans[0] if plans else {}
        with st.form("plan"):
            plan = {
                key: st.text_area(label, d.get(key, ""))
                for key, label in [
                    ("requirements", "Análise dos requisitos e ambiguidades"),
                    ("risks", "Riscos e prioridades"),
                    ("scenarios", "Cenários propostos"),
                    ("coverage", "Matriz: critério → caso → lacuna"),
                    ("regression", "Regressão recomendada"),
                    ("reviewer", "Revisor e decisão humana"),
                ]
            }
            if st.form_submit_button("Salvar plano revisável"):
                save("plan", plan, task["id"], d.get("id"))
        st.write("Tarefas relacionadas:", [t["identifier"] for t in store.similar(task)])
        provider = AIProvider()
        allowed = st.checkbox(
            "Autorizar envio do contexto desta tarefa ao provedor configurado",
            disabled=not provider.available,
        )
        if st.button("Analisar requisitos com IA", disabled=not provider.available or not allowed):
            try:
                st.json(
                    provider.run(
                        "analyze-task",
                        {"task": task, "rules": store.list("knowledge", task["id"])},
                    )
                )
            except Exception:
                st.error(
                    "Falha na análise do provedor. Nenhum resultado foi persistido ou aprovado."
                )
        if not provider.available:
            st.caption("IA indisponível: nenhum mecanismo autenticado foi conectado.")

elif page == "Casos de teste":
    task = select_task()
    if task:
        cases = store.list("case", task["id"])
        selected = st.selectbox(
            "Criar ou editar",
            [None] + cases,
            format_func=lambda c: "Novo caso" if c is None else c["title"],
        )
        d = selected or {}
        with st.form("case"):
            data = {
                key: st.text_area(label, d.get(key, ""))
                for key, label in [
                    ("title", "Título *"),
                    ("preconditions", "Pré-condições"),
                    ("steps", "Passos *"),
                    ("expected", "Resultado esperado *"),
                    ("acceptance_ids", "Critérios cobertos"),
                ]
            }
            types = [
                "Positivo",
                "Negativo",
                "Integração",
                "Regressão",
                "Limite",
                "Exploratório",
            ]
            data["test_type"] = st.selectbox(
                "Categoria", types, index=types.index(d.get("test_type", "Positivo"))
            )
            data["priority"] = st.selectbox("Prioridade", ["Alta", "Média", "Baixa"])
            for key in ["original_case_id", "original_task_id"]:
                if key in d:
                    data[key] = d[key]
            if st.form_submit_button("Salvar caso"):
                save("case", data, task["id"], d.get("id"))
        if selected:
            with st.expander("Histórico de alterações"):
                st.json(store.history(selected["id"]), expanded=False)
        st.subheader("Reutilizar casos de teste")
        source = st.selectbox(
            "Tarefa de origem",
            [None] + [t for t in store.list("task") if t["id"] != task["id"]],
            format_func=lambda t: "Selecione" if t is None else t["identifier"],
        )
        if source:
            choices = st.multiselect(
                "Casos de origem",
                store.list("case", source["id"]),
                format_func=lambda c: c["title"],
            )
            if st.button("Reutilizar casos selecionados"):
                for case in choices:
                    store.reuse(case["id"], task["id"])
                st.success("Casos copiados com rastreabilidade. Execuções originais preservadas.")

elif page == "Execução de testes":
    task = select_task()
    if task:
        cases = store.list("case", task["id"])
        if cases:
            case = st.selectbox("Caso de teste", cases, format_func=lambda c: c["title"])
            st.write("Esperado:", case["expected"])
            with st.form("execution"):
                data = {
                    key: st.text_area(label)
                    for key, label in [
                        ("responsible", "Responsável *"),
                        ("build", "Versão/build"),
                        ("test_data", "Dados utilizados (sem segredos)"),
                        ("steps", "Passos executados"),
                        ("observed", "Resultado observado"),
                        ("defects", "IDs dos defeitos relacionados"),
                        ("notes", "Observações"),
                    ]
                }
                data["environment"] = st.text_input("Ambiente", task.get("environment", ""))
                data["status"] = st.selectbox("Status", RESULTS)
                data.update(case_id=case["id"], expected=case["expected"])
                if st.form_submit_button("Registrar execução imutável"):
                    save("execution", data, task["id"])
        else:
            st.info("Cadastre um caso de teste antes de executar.")
        runs = store.list("execution", task["id"])
        st.subheader("Evidência da execução")
        if runs:
            run = st.selectbox("Execução", runs, format_func=lambda r: f"{r['id']} · {r['status']}")
            upload = st.file_uploader(
                "Arquivo de evidência",
                type=["png", "jpg", "jpeg", "pdf", "txt", "md", "csv", "json", "log"],
            )
            if upload and st.button("Vincular evidência"):
                try:
                    store.attach(task["id"], upload.name, upload.getvalue(), run["id"])
                    st.success("Evidência vinculada.")
                except ValueError as error:
                    st.error(str(error))
        with st.expander("Registrar defeito / sessão exploratória"):
            kind = st.selectbox("Registro", ["defect", "exploration"])
            with st.form("discovery"):
                data = {
                    k: st.text_area(label)
                    for k, label in [
                        ("title", "Título"),
                        ("description", "Descrição / roteiro / reprodução"),
                        ("observed", "Observado e riscos"),
                        ("source", "IDs das fontes e execuções"),
                    ]
                }
                if st.form_submit_button("Salvar descoberta"):
                    save(kind, data, task["id"])
        for run in runs:
            with st.expander(f"{run['id']} · {run['status']} · {run['created']}"):
                st.json(run)

elif page == "Base de conhecimento":
    task = select_task("Tarefa de origem")
    if task:
        rules = store.list("knowledge", task["id"])
        selected = st.selectbox(
            "Criar ou revisar proposta",
            [None] + rules,
            format_func=lambda r: (
                "Nova proposta" if r is None else f"{r['title']} · {r['editorial']}"
            ),
        )
        d = selected or {}
        with st.form("knowledge"):
            data = {
                key: st.text_area(label, d.get(key, ""))
                for key, label in [
                    ("title", "Título *"),
                    ("description", "Descrição *"),
                    ("domain", "Domínio / módulo"),
                    ("category", "Categoria"),
                    ("source", "Origem / fontes *"),
                    ("evidence_ids", "IDs de evidências relacionadas"),
                    ("related_rule_id", "Regra em revisão / contradição"),
                    ("reviewer", "Revisor identificado"),
                    ("review_notes", "Decisão e justificativa da revisão"),
                ]
            }
            data["system"] = task["system"]
            data["state"] = st.selectbox(
                "Estado do conhecimento",
                KNOWLEDGE_STATES,
                index=KNOWLEDGE_STATES.index(d.get("state", "Hipótese")),
            )
            data["editorial"] = st.selectbox(
                "Estado editorial",
                EDITORIAL,
                index=EDITORIAL.index(d.get("editorial", "Proposto")),
            )
            if st.form_submit_button("Salvar proposta / revisão humana"):
                save("knowledge", data, task["id"], d.get("id"))
        cycle = store.list("knowledge-cycle", task["id"])[0]
        with st.form("cycle"):
            notes = st.text_area(
                "Conclusão da extração de conhecimento (inclusive sem descobertas)",
                cycle.get("notes", ""),
            )
            reviewer = st.text_input("Responsável pela revisão do ciclo", cycle.get("reviewer", ""))
            reviewed = st.checkbox(
                "Extração revisada por pessoa responsável", cycle.get("reviewed", False)
            )
            if st.form_submit_button("Registrar revisão do ciclo"):
                if reviewed and (not notes.strip() or not reviewer.strip()):
                    st.error("Informe conclusão e responsável.")
                else:
                    save(
                        "knowledge-cycle",
                        {"notes": notes, "reviewer": reviewer, "reviewed": reviewed},
                        task["id"],
                        cycle["id"],
                    )
    st.subheader("Pesquisar conhecimento de todos os sistemas")
    query = st.text_input("Buscar regra")
    system = st.text_input("Filtrar sistema")
    domain = st.text_input("Filtrar domínio/módulo")
    for rule in store.list("knowledge"):
        from qa_lsf.store import normalize

        if query and normalize(query) not in normalize(str(rule)):
            continue
        if system and normalize(system) not in normalize(rule.get("system", "")):
            continue
        if domain and normalize(domain) not in normalize(rule.get("domain", "")):
            continue
        with st.expander(f"{rule['title']} | {rule['state']} · {rule['editorial']}"):
            st.json(rule)
            if rule["task_id"]:
                details(store.get(rule["task_id"]), context=rule["id"])
            st.json(store.history(rule["id"]), expanded=False)

elif page == "Relatórios":
    task = select_task()
    if task:
        text = report(store, task["id"])
        st.download_button("Baixar Markdown", text, file_name=f"{task['id']}.md")
        st.download_button(
            "Baixar HTML",
            as_html(text),
            file_name=f"{task['id']}.html",
            mime="text/html",
        )
        if st.button("Exportar documentos para Git local"):
            folder = export(store, task["id"], ROOT / "artifacts")
            st.success(
                f"Documentos exportados: {folder}. Revise dados sensíveis antes de versionar."
            )
        st.code(card_comment(store, task["id"]), language=None)
        st.caption(
            "Use o botão de copiar no comentário. PDF: indisponível nesta versão; exportação HTML disponível."
        )
        st.markdown(text)

elif page == "Configurações":
    cfg = store.settings()
    st.write("Diretório do projeto:", str(ROOT))
    st.write("Dados operacionais:", str(store.root))
    st.write("Evidências:", str(store.root / "evidence"))
    st.caption(
        "Para isolar outro projeto, o inicializador aceita QA_LSF_DATA. Arquivos importados não executam comandos."
    )
    with st.form("settings"):
        data = {
            "environment": st.text_input("Ambiente padrão", cfg.get("environment", "Homologação")),
            "documentation": st.selectbox("Preferência de documentação", ["Concisa", "Detalhada"]),
            "export": st.selectbox("Exportação preferida", ["Markdown", "HTML"]),
            "search_size": st.selectbox("Resultados por página (preferência)", [20]),
            "safety": st.text_area(
                "Regras adicionais de segurança",
                cfg.get("safety", "Somente local; nenhuma publicação automática."),
            ),
        }
        if st.form_submit_button("Salvar preferências"):
            store.settings(data)
            st.success("Preferências salvas.")
    st.write(
        "Provedor de IA:",
        "Configurado por variáveis de ambiente" if AIProvider().available else "Indisponível",
    )
    st.caption(
        "Adaptador compatível com Chat Completions via HTTPS. Variáveis: QA_LSF_AI_URL, QA_LSF_AI_KEY e QA_LSF_AI_MODEL. Credenciais não são exibidas ou persistidas na interface."
    )
    st.info(
        "Azure DevOps/GitLab: URL e comentário locais disponíveis. Publicação remota não conectada. Verificações API/banco corporativas não habilitadas."
    )
    if st.button("Criar backup consistente do banco"):
        st.success(str(store.backup()))
