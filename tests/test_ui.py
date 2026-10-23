from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from qa_lsf.store import Store
from tests.test_platform import case, run, task


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_LSF_DATA", str(tmp_path))
    return AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=20)


def test_empty_dashboard(app):
    app.run()
    assert not app.exception
    assert all(m.value == "0" for m in app.metric)


@pytest.mark.parametrize(
    "page",
    [
        "Gestão de tarefas",
        "Histórico de Tarefas",
        "Planejamento",
        "Casos de teste",
        "Execução de testes",
        "Base de conhecimento",
        "Relatórios",
        "Configurações",
    ],
)
def test_pages_with_persisted_records(app, page, tmp_path):
    s = Store(tmp_path)
    tid = task(s)
    run(s, tid, case(s, tid))
    app.run()
    app.sidebar.radio[0].set_value(page).run()
    assert not app.exception


def test_create_task_through_ui_and_restart(app):
    app.run()
    app.sidebar.radio[0].set_value("Gestão de tarefas").run()
    for label, value in [
        ("ID da tarefa *", "TESTE-UI-001"),
        ("Título *", "TESTE FICTÍCIO UI"),
        ("Sistema/projeto *", "OMS"),
    ]:
        next(i for i in app.text_input if i.label == label).set_value(value)
    next(b for b in app.button if b.label == "Salvar tarefa").click().run()
    assert not app.exception
    assert app.success
    restarted = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run()
    assert restarted.metric[0].value == "1"


def test_full_ui_workflow(app, tmp_path):
    def field(label, value, widgets=None):
        next(i for i in (widgets or app.text_area) if i.label == label).set_value(value)

    def button(label):
        next(b for b in app.button if b.label == label).click().run()
        assert not app.exception

    def navigate(label):
        app.sidebar.radio[0].set_value(label).run()
        assert not app.exception

    s = Store(tmp_path)
    tid = task(s)
    task(s, "TESTE-DESTINO")
    app.run()
    navigate("Casos de teste")
    # Explicitly choose the source, as tasks are ordered by update.
    app.selectbox[0].select_index(1).run()
    field("Título *", "TESTE FICTÍCIO cancelar")
    field("Passos *", "Solicitar cancelamento")
    field("Resultado esperado *", "Cancelado")
    button("Salvar caso")
    cid = s.list("case", tid)[0]["id"]
    navigate("Execução de testes")
    app.selectbox[0].select_index(1).run()
    field("Responsável *", "QA Teste")
    field("Resultado observado", "Cancelado conforme evento")
    next(i for i in app.selectbox if i.label == "Status").set_value("Aprovado")
    button("Registrar execução imutável")
    assert s.list("execution", tid)[0]["status"] == "Aprovado"
    navigate("Base de conhecimento")
    app.selectbox[0].select_index(1).run()
    field("Título *", "TESTE FICTÍCIO regra")
    field("Descrição *", "Cancelamento emite evento")
    field("Origem / fontes *", "Execução sintética autorizada")
    button("Salvar proposta / revisão humana")
    app.run()
    next(i for i in app.selectbox if i.label == "Criar ou revisar proposta").select_index(1).run()
    field("Revisor identificado", "QA Teste")
    next(i for i in app.selectbox if i.label == "Estado editorial").set_value("Aprovado")
    button("Salvar proposta / revisão humana")
    assert s.list("knowledge", tid)[0]["editorial"] == "Aprovado"
    field(
        "Conclusão da extração de conhecimento (inclusive sem descobertas)", "Descoberta revisada"
    )
    field("Responsável pela revisão do ciclo", "QA Teste", app.text_input)
    app.checkbox[0].check()
    button("Registrar revisão do ciclo")
    navigate("Histórico de Tarefas")
    field("Pesquisar ID, título, regra, caso ou resultado", "TESTE-001", app.text_input)
    app.run()
    next(i for i in app.selectbox if i.label == "Sistema/projeto").set_value("OMS Varejo")
    next(i for i in app.selectbox if i.label == "Status").set_value("Nova")
    app.run()
    button("Abrir detalhes")
    assert any("TESTE-001" in item.value for item in app.subheader)
    navigate("Relatórios")
    app.selectbox[0].select_index(1).run()
    assert len(app.get("download_button")) == 2
    navigate("Casos de teste")
    app.selectbox[0].select_index(0).run()
    next(i for i in app.selectbox if i.label == "Tarefa de origem").select_index(1).run()
    app.multiselect[0].set_value([s.get(cid)])
    button("Reutilizar casos selecionados")
    assert len(s.list("execution", tid)) == 1
    assert any(c.get("original_case_id") == cid for c in s.list("case"))
