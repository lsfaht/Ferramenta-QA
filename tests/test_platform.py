import sqlite3

import pytest

from qa_lsf.agent import AIProvider
from qa_lsf.reports import as_html, export, report
from qa_lsf.store import Store


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path)


def task(s, identifier="TESTE-001", **extra):
    return s.save(
        "task",
        dict(
            identifier=identifier,
            title="TESTE FICTÍCIO Shipment",
            system="OMS Varejo",
            module="Shipment",
            status="Nova",
            priority="Alta",
            environment="QA",
            responsible="QA Teste",
            description="Cancelamento assíncrono",
            acceptance="Pedido cancelado",
            **extra,
        ),
    )


def case(s, tid):
    return s.save(
        "case",
        dict(
            title="Cancelar pedido",
            steps="Enviar solicitação",
            expected="Cancelado",
            test_type="Integração",
        ),
        tid,
    )


def run(s, tid, cid):
    return s.save(
        "execution",
        dict(
            case_id=cid,
            responsible="QA Teste",
            status="Aprovado",
            observed="Evento consumido",
            environment="QA",
        ),
        tid,
    )


def test_persistence_and_knowledge_cycle(store):
    tid = task(store)
    assert Store(store.root).get(tid)["identifier"] == "TESTE-001"
    assert store.list("knowledge-cycle", tid)[0]["reviewed"] is False
    assert len(store.history(tid)) == 1


def test_duplicates_and_invalid_fields(store):
    task(store)
    with pytest.raises(ValueError, match="já cadastrado"):
        task(store)
    with pytest.raises(ValueError):
        store.save("task", {"title": "sem campos"})


def test_execution_snapshot_and_immutability(store):
    tid = task(store)
    cid = case(store, tid)
    rid = run(store, tid, cid)
    store.save(
        "case",
        dict(title="Novo título", steps="Outro passo", expected="Outro resultado"),
        tid,
        cid,
    )
    assert store.get(rid)["case_snapshot"]["expected"] == "Cancelado"
    with pytest.raises(ValueError, match="imutáveis"):
        store.save("execution", store.get(rid), tid, rid)


def test_cross_task_execution_rejected(store):
    a, b = task(store), task(store, "TESTE-002")
    with pytest.raises(ValueError, match="não pertence"):
        run(store, b, case(store, a))


def test_execution_requires_observation(store):
    tid = task(store)
    with pytest.raises(ValueError, match="observado"):
        store.save(
            "execution",
            dict(case_id=case(store, tid), responsible="QA", status="Aprovado"),
            tid,
        )


def test_reuse_preserves_history(store):
    a, b = task(store), task(store, "TESTE-002")
    cid = case(store, a)
    rid = run(store, a, cid)
    clone = store.reuse(cid, b)
    assert clone != cid
    assert store.get(clone)["original_case_id"] == cid
    assert store.get(clone)["original_task_id"] == a
    assert store.get(rid)["task_id"] == a
    assert not store.list("execution", b)


@pytest.mark.parametrize("query", ["teste-001", "fict", "SHIP", "assincrono", "cancelad", "01"])
def test_partial_case_insensitive_search(store, query):
    task(store)
    assert store.search(query)[1] == 1


def test_search_related_and_index_update(store):
    tid = task(store)
    cid = case(store, tid)
    run(store, tid, cid)
    assert store.search("consumido")[1] == 1
    store.save(
        "case",
        dict(title="Faturamento exclusivo", steps="Passo", expected="OK"),
        tid,
        cid,
    )
    assert store.search("exclusivo")[1] == 1
    assert store.search('" OR * ; --')[1] == 0


def test_combined_filters_and_pagination(store):
    tid = task(store)
    run(store, tid, case(store, tid))
    assert (
        store.search(
            filters={
                "system": "OMS Varejo",
                "status": "Nova",
                "from": "2020-01-01",
                "to": "2099-01-01",
                "test_type": "Integração",
                "has_evidence": False,
            }
        )[1]
        == 1
    )
    assert store.search(filters={"has_defects": True})[1] == 0
    assert store.search(filters={"from": "2099-01-01"})[1] == 0
    task(store, "TESTE-002")
    assert len(store.search(size=1, page=1)[0]) == 1


def test_knowledge_review_and_protection(store):
    tid = task(store)
    data = dict(
        title="Regra observada",
        description="Cancelar antes da nota",
        source="manual autorizado",
        state="Observado",
        editorial="Proposto",
        system="OMS",
    )
    kid = store.save("knowledge", data, tid)
    with pytest.raises(ValueError, match="duplicada"):
        store.save("knowledge", data, tid)
    with pytest.raises(ValueError, match="revisor"):
        store.save("knowledge", {**data, "editorial": "Aprovado"}, tid, kid)
    approved = {
        **data,
        "editorial": "Aprovado",
        "state": "Confirmado",
        "reviewer": "QA Teste",
    }
    store.save("knowledge", approved, tid, kid)
    with pytest.raises(ValueError, match="protegida"):
        store.save("knowledge", {**approved, "description": "Conflito"}, tid, kid)
    assert len(store.history(kid)) == 2
    assert store.search("manual autorizado")[1] == 1


def test_conclusion_requires_knowledge_review(store):
    tid = task(store)
    data = {
        k: v
        for k, v in store.get(tid).items()
        if k not in ["kind", "id", "created", "updated", "task_id"]
    }
    with pytest.raises(ValueError, match="conhecimento"):
        store.save("task", {**data, "status": "Concluída"}, entity_id=tid)
    cycle = store.list("knowledge-cycle", tid)[0]
    store.save(
        "knowledge-cycle",
        dict(reviewed=True, notes="Sem descobertas", reviewer="QA"),
        tid,
        cycle["id"],
    )
    store.save("task", {**data, "status": "Concluída"}, entity_id=tid)
    assert store.get(tid)["status"] == "Concluída"


def test_evidence_integrity_and_no_overwrite(store):
    tid = task(store)
    aid = store.attach(tid, "../../evidence.txt", b"TESTE FICTICIO")
    attachment = store.get(aid)
    assert store.evidence(attachment) == b"TESTE FICTICIO"
    with pytest.raises(ValueError, match="já anexado"):
        store.attach(tid, "other.txt", b"TESTE FICTICIO")
    with pytest.raises(ValueError):
        store.attach(tid, "code.exe", b"x")
    (store.root / "evidence" / attachment["file"]).write_bytes(b"alterado")
    with pytest.raises(ValueError, match="Integridade"):
        store.evidence(attachment)


def test_report_escape_export_backup(store, tmp_path):
    tid = task(store)
    run(store, tid, case(store, tid))
    text = report(store, tid)
    assert "QA LSF" in text and "Evento consumido" in text
    assert "<script>" not in as_html("<script>alert(1)</script>")
    assert (export(store, tid, tmp_path / "artifacts") / "relatorio.md").exists()
    backup = store.backup()
    with sqlite3.connect(backup) as c:
        assert c.execute("SELECT count(*) FROM entities").fetchone()[0] == 4


def test_unavailable_ai(store, monkeypatch):
    monkeypatch.delenv("QA_LSF_AI_KEY", raising=False)
    with pytest.raises(ValueError, match="indisponível"):
        AIProvider().run("analyze-task", {})


def test_secret_redaction(store):
    tid = task(store)
    store.save("plan", {"notes": "token=abc123 Bearer xyz456"}, tid)
    assert "abc123" not in str(store.list("plan"))
    assert "xyz456" not in str(store.list("plan"))
    store.save("plan", {"notes": "senha=finalSecret"}, tid)
    assert "finalSecret" not in str(store.list("plan"))
