import html
import json
from pathlib import Path

import markdown


def report(store, task_id):
    task = store.get(task_id)
    lines = [
        f"# QA LSF — {task['identifier']}: {task['title']}",
        f"Identificador: {task_id}",
        f"Status: {task['status']}",
        f"Conclusão humana: {task.get('result', 'Não avaliada')}",
        "\n## Requisito",
        task.get("description", ""),
        "\n## Critérios de aceite",
        task.get("acceptance", ""),
    ]
    for kind, title in [
        ("plan", "Plano e cobertura"),
        ("case", "Definição dos testes"),
        ("execution", "Execuções observadas"),
        ("attachment", "Evidências"),
        ("defect", "Defeitos"),
        ("exploration", "Sessões exploratórias"),
        ("knowledge", "Conhecimento"),
        ("knowledge-cycle", "Revisão de conhecimento"),
    ]:
        lines.append(f"\n## {title}")
        items = store.list(kind, task_id)
        if not items:
            lines.append("Sem registros.")
        for item in items:
            lines.extend(
                [
                    f"\n### {item['id']}",
                    "```json",
                    json.dumps(item, ensure_ascii=False, indent=2),
                    "```",
                ]
            )
    lines.append(
        "\nConclusões se referem exclusivamente ao escopo registrado. Encerrar uma atividade de IA não aprova testes."
    )
    return "\n\n".join(lines)


def as_html(text):
    body = markdown.markdown(html.escape(text), extensions=["fenced_code", "tables"])
    return (
        '<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>QA LSF</title><style>body{max-width:1000px;margin:40px auto;font:16px system-ui;padding:24px}pre{white-space:pre-wrap;background:#f1f5f9;padding:16px}</style>'
        + body
        + "</html>"
    )


def export(store, task_id, folder):
    folder = Path(folder) / task_id
    folder.mkdir(parents=True, exist_ok=True)
    text = report(store, task_id)
    for name, body in [("relatorio.md", text), ("relatorio.html", as_html(text))]:
        target = folder / name
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(body, encoding="utf-8")
        temporary.replace(target)
    return folder


def card_comment(store, task_id):
    t = store.get(task_id)
    runs = store.list("execution", task_id)
    return f"QA LSF | {t['identifier']}\nConclusão humana: {t.get('result', 'Não avaliada')}\nExecuções registradas: {len(runs)}\nRelatório: {task_id}/relatorio.md\nPendências: consultar relatório e defeitos relacionados."
