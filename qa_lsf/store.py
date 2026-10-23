import hashlib
import json
import re
import sqlite3
import unicodedata
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

TASK_STATES = ["Nova", "Em andamento", "Concluída", "Bloqueada"]
RESULTS = [
    "Não executado",
    "Em execução",
    "Aprovado",
    "Reprovado",
    "Bloqueado",
    "Não aplicável",
]
KNOWLEDGE_STATES = ["Hipótese", "Observado", "Confirmado", "Contraditório", "Obsoleto"]
EDITORIAL = ["Proposto", "Em revisão", "Aprovado", "Rejeitado"]


def now():
    return datetime.now(UTC).isoformat()


def normalize(value):
    return "".join(
        c
        for c in unicodedata.normalize("NFKD", str(value)).casefold()
        if not unicodedata.combining(c)
    )


def redact(value):
    value = re.sub(r"(?i)(bearer\s+)[\w.\-]+", r"\1[REDACTED]", str(value))
    return re.sub(
        r"(?i)((?:password|senha|token|api[_-]?key|secret)\s*[:=]\s*)[^\s,;]+",
        r"\1[REDACTED]",
        value,
    )


def clean(value):
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean(v) for v in value]
    return redact(value) if isinstance(value, str) else value


class Store:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = self.root / "qa-lsf.sqlite3"
        with self.connect() as c:
            c.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS entities (
                id TEXT PRIMARY KEY, kind TEXT NOT NULL, task_id TEXT,
                data TEXT NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS by_task ON entities(task_id,kind);
            CREATE TABLE IF NOT EXISTS audit (
                seq INTEGER PRIMARY KEY, entity_id TEXT, action TEXT, actor TEXT,
                timestamp TEXT, before_data TEXT, after_data TEXT);
            CREATE VIRTUAL TABLE IF NOT EXISTS search USING fts5(id UNINDEXED, body, tokenize='trigram');
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY,value TEXT NOT NULL);
            """)

    @contextmanager
    def connect(self):
        c = sqlite3.connect(self.db, timeout=20)
        c.row_factory = sqlite3.Row
        try:
            with c:
                yield c
        finally:
            c.close()

    def get(self, entity_id, c=None):
        if c is None:
            with self.connect() as conn:
                return self.get(entity_id, conn)
        row = c.execute("SELECT * FROM entities WHERE id=?", (entity_id,)).fetchone()
        if not row:
            raise ValueError("Registro não encontrado")
        return {
            **json.loads(row["data"]),
            "id": row["id"],
            "kind": row["kind"],
            "task_id": row["task_id"],
            "created": row["created"],
            "updated": row["updated"],
        }

    def list(self, kind, task_id=None, c=None):
        if c is None:
            with self.connect() as conn:
                return self.list(kind, task_id, conn)
        sql, args = "SELECT id FROM entities WHERE kind=?", [kind]
        if task_id is not None:
            sql += " AND task_id=?"
            args.append(task_id)
        return [
            self.get(r["id"], c) for r in c.execute(sql + " ORDER BY updated DESC", args).fetchall()
        ]

    def save(self, kind, data, task_id=None, entity_id=None, actor="QA local"):
        data = clean(data)
        if kind not in [
            "task",
            "case",
            "execution",
            "knowledge",
            "plan",
            "defect",
            "exploration",
            "attachment",
            "knowledge-cycle",
        ]:
            raise ValueError("Tipo inválido")
        required = {
            "task": ["identifier", "title", "system"],
            "case": ["title", "steps", "expected"],
            "execution": ["case_id", "responsible", "status"],
            "knowledge": ["title", "description", "source"],
        }
        if any(not str(data.get(k, "")).strip() for k in required.get(kind, [])):
            raise ValueError("Preencha todos os campos obrigatórios")
        if kind != "task" and not task_id:
            raise ValueError("Registro exige tarefa relacionada")
        if (
            kind == "knowledge-cycle"
            and data.get("reviewed")
            and (not data.get("reviewer", "").strip() or not data.get("notes", "").strip())
        ):
            raise ValueError("Revisão exige responsável e conclusão")
        for field, allowed in [
            (
                "status",
                TASK_STATES if kind == "task" else RESULTS if kind == "execution" else None,
            ),
            ("state", KNOWLEDGE_STATES if kind == "knowledge" else None),
            ("editorial", EDITORIAL if kind == "knowledge" else None),
        ]:
            if allowed and data.get(field) not in allowed:
                raise ValueError(f"{field} inválido")
        if data.get("url") and not re.match(r"^https?://[^\s]+$", data["url"]):
            raise ValueError("URL deve usar HTTP ou HTTPS")
        if (
            kind == "execution"
            and data["status"] in ["Aprovado", "Reprovado", "Bloqueado"]
            and not data.get("observed", "").strip()
        ):
            raise ValueError("Informe o resultado observado")
        with self.connect() as c:
            before = self.get(entity_id, c) if entity_id else None
            if before and before["kind"] != kind:
                raise ValueError("Tipo de registro incompatível")
            if before and before["task_id"] != task_id:
                raise ValueError("Vínculo de tarefa não pode ser alterado")
            if before and kind in ["execution", "attachment"]:
                raise ValueError(
                    "Registros de execução e evidências são imutáveis; crie um novo registro"
                )
            if task_id and self.get(task_id, c)["kind"] != "task":
                raise ValueError("Tarefa inválida")
            if kind == "task":
                if any(
                    normalize(t["identifier"]) == normalize(data["identifier"])
                    and t["id"] != entity_id
                    for t in self.list("task", c=c)
                ):
                    raise ValueError("Identificador da tarefa já cadastrado")
                if data["status"] == "Concluída":
                    cycles = self.list("knowledge-cycle", entity_id, c) if entity_id else []
                    if not cycles or not cycles[0].get("reviewed"):
                        raise ValueError(
                            "Revise o ciclo de conhecimento antes de concluir a tarefa"
                        )
            if kind == "execution":
                case = self.get(data["case_id"], c)
                if case["kind"] != "case" or case["task_id"] != task_id:
                    raise ValueError("Caso não pertence à tarefa")
                data["case_snapshot"] = case
            if kind == "knowledge":
                if data.get("editorial") == "Aprovado" and not data.get("reviewer", "").strip():
                    raise ValueError("A aprovação exige um revisor identificado")
                if (
                    before
                    and before["state"] == "Confirmado"
                    and before["editorial"] == "Aprovado"
                    and data
                    != {
                        k: v
                        for k, v in before.items()
                        if k not in ["id", "kind", "task_id", "created", "updated"]
                    }
                ):
                    raise ValueError(
                        "Regra confirmada protegida: crie uma proposta de revisão relacionada"
                    )
                for rule in self.list("knowledge", task_id, c):
                    if (
                        rule["id"] != entity_id
                        and normalize(rule["title"]) == normalize(data["title"])
                        and normalize(rule["description"]) == normalize(data["description"])
                    ):
                        raise ValueError("Proposta duplicada")
            ident = entity_id or f"{kind.upper()}-{uuid.uuid4().hex[:12]}"
            timestamp = now()
            payload = json.dumps(data, ensure_ascii=False)
            c.execute(
                "INSERT INTO entities VALUES (?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data, updated=excluded.updated",
                (ident, kind, task_id, payload, timestamp, timestamp),
            )
            c.execute(
                "INSERT INTO audit(entity_id,action,actor,timestamp,before_data,after_data) VALUES (?,?,?,?,?,?)",
                (
                    ident,
                    "update" if before else "create",
                    actor,
                    timestamp,
                    json.dumps(before, ensure_ascii=False),
                    payload,
                ),
            )
            if kind == "task" and not before:
                cycle_id = f"CYCLE-{uuid.uuid4().hex[:12]}"
                c.execute(
                    "INSERT INTO entities VALUES (?,?,?,?,?,?)",
                    (
                        cycle_id,
                        "knowledge-cycle",
                        ident,
                        json.dumps({"reviewed": False, "notes": ""}),
                        timestamp,
                        timestamp,
                    ),
                )
            self._index(c, ident if kind == "task" else task_id)
        return ident

    def _index(self, c, task_id):
        if not task_id:
            return
        task = self.get(task_id, c)
        children = c.execute("SELECT data FROM entities WHERE task_id=?", (task_id,)).fetchall()
        body = normalize(
            json.dumps(task, ensure_ascii=False) + " ".join(r["data"] for r in children)
        )
        c.execute("DELETE FROM search WHERE id=?", (task_id,))
        c.execute("INSERT INTO search VALUES (?,?)", (task_id, body))

    def search(self, text="", filters=None, order="updated", page=0, size=20):
        filters = filters or {}
        with self.connect() as c:
            terms = normalize(text).split()
            if terms:
                if all(len(t) >= 3 for t in terms):
                    expression = " AND ".join('"' + t.replace('"', '""') + '"' for t in terms)
                    ids = [
                        r["id"]
                        for r in c.execute(
                            "SELECT id FROM search WHERE search MATCH ?", (expression,)
                        )
                    ]
                else:
                    ids = [
                        r["id"]
                        for r in c.execute("SELECT id FROM search").fetchall()
                        if all(
                            t
                            in c.execute(
                                "SELECT body FROM search WHERE id=?", (r["id"],)
                            ).fetchone()["body"]
                            for t in terms
                        )
                    ]
                tasks = [self.get(i, c) for i in ids]
            else:
                tasks = self.list("task", c=c)
            found = []
            for t in tasks:
                if any(
                    v and t.get(k) != v
                    for k, v in filters.items()
                    if k
                    in [
                        "system",
                        "module",
                        "status",
                        "priority",
                        "environment",
                        "responsible",
                        "result",
                    ]
                ):
                    continue
                cases, runs = (
                    self.list("case", t["id"], c),
                    self.list("execution", t["id"], c),
                )
                if filters.get("test_type") and not any(
                    x.get("test_type") == filters["test_type"] for x in cases
                ):
                    continue
                if filters.get("from") or filters.get("to"):
                    if not any(
                        (not filters.get("from") or r["created"][:10] >= str(filters["from"]))
                        and (not filters.get("to") or r["created"][:10] <= str(filters["to"]))
                        for r in runs
                    ):
                        continue
                rejected = False
                for key, kind in [
                    ("has_defects", "defect"),
                    ("has_evidence", "attachment"),
                    ("has_knowledge", "knowledge"),
                ]:
                    if (
                        filters.get(key) is not None
                        and bool(self.list(kind, t["id"], c)) != filters[key]
                    ):
                        rejected = True
                if rejected:
                    continue
                found.append(
                    {
                        **t,
                        "cases": len(cases),
                        "passed": sum(r["status"] == "Aprovado" for r in runs),
                        "failed": sum(r["status"] == "Reprovado" for r in runs),
                        "last_run": max([r["created"] for r in runs], default="—"),
                    }
                )
            found.sort(key=lambda t: t.get(order, ""), reverse=order != "title")
            return found[page * size : (page + 1) * size], len(found)

    def reuse(self, case_id, target_task):
        case = self.get(case_id)
        if case["kind"] != "case" or case["task_id"] == target_task:
            raise ValueError("Escolha caso e tarefa de destino diferentes")
        data = {
            k: v
            for k, v in case.items()
            if k not in ["id", "kind", "task_id", "created", "updated"]
        }
        data.update(original_case_id=case_id, original_task_id=case["task_id"])
        return self.save("case", data, target_task)

    def attach(self, task_id, name, content, execution_id=None):
        if len(content) > 20 * 1024 * 1024:
            raise ValueError("Limite de 20 MB por arquivo")
        if Path(name).suffix.lower() not in [
            ".png",
            ".jpg",
            ".jpeg",
            ".pdf",
            ".txt",
            ".md",
            ".csv",
            ".json",
            ".log",
        ]:
            raise ValueError("Formato de arquivo não permitido")
        self.get(task_id)
        if execution_id and self.get(execution_id)["task_id"] != task_id:
            raise ValueError("Execução de outra tarefa")
        digest = hashlib.sha256(content).hexdigest()
        if any(a["sha256"] == digest for a in self.list("attachment", task_id)):
            raise ValueError("Arquivo já anexado à tarefa")
        folder = self.root / "evidence"
        folder.mkdir(exist_ok=True)
        filename = uuid.uuid4().hex + Path(name).suffix.lower()
        (folder / filename).write_bytes(content)
        return self.save(
            "attachment",
            {
                "title": Path(name).name,
                "file": filename,
                "sha256": digest,
                "execution_id": execution_id,
            },
            task_id,
        )

    def evidence(self, attachment):
        path = (self.root / "evidence" / attachment["file"]).resolve()
        if not path.is_relative_to(self.root / "evidence"):
            raise ValueError("Caminho inválido")
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != attachment["sha256"]:
            raise ValueError("Integridade da evidência comprometida")
        return content

    def history(self, entity_id):
        with self.connect() as c:
            return [
                dict(r)
                for r in c.execute(
                    "SELECT * FROM audit WHERE entity_id=? ORDER BY seq DESC",
                    (entity_id,),
                )
            ]

    def settings(self, values=None):
        with self.connect() as c:
            if values:
                for k, v in values.items():
                    c.execute(
                        "INSERT OR REPLACE INTO settings VALUES (?,?)",
                        (k, json.dumps(v)),
                    )
            return {r["key"]: json.loads(r["value"]) for r in c.execute("SELECT * FROM settings")}

    def backup(self):
        folder = self.root / "backups"
        folder.mkdir(exist_ok=True)
        target = folder / f"qa-lsf-{uuid.uuid4().hex[:12]}.sqlite3"
        with self.connect() as c, sqlite3.connect(target) as dest:
            c.backup(dest)
        return target

    def similar(self, task):
        words = set(
            re.findall(r"\w{4,}", normalize(task["title"] + " " + task.get("keywords", "")))
        )
        ranked = []
        for other in self.list("task"):
            if other["id"] == task["id"]:
                continue
            score = len(
                words
                & set(
                    re.findall(
                        r"\w{4,}",
                        normalize(other["title"] + " " + other.get("keywords", "")),
                    )
                )
            )
            score += 2 if other.get("module") and other.get("module") == task.get("module") else 0
            if score:
                ranked.append((score, other))
        return [t for _, t in sorted(ranked, key=lambda x: x[0], reverse=True)[:5]]
