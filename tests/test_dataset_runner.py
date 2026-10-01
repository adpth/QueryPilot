import json
from pathlib import Path
from evals import dataset, runner
from querypilot.agent import AgentState


def test_load_dataset(tmp_path: Path):
    jsonl_file = tmp_path / "data.jsonl"
    jsonl_file.write_text(
        '{"id": "ex-1", "database": "db1", "question": "q1", "reference_sql": "SELECT 1"}\n'
        '{"id": "ex-2", "database": "db1", "question": "q2", "reference_sql": "SELECT * FROM t ORDER BY id"}\n'
    )
    examples = dataset.load(jsonl_file)
    assert len(examples) == 2
    assert examples[0].id == "ex-1"
    assert examples[0].order_matters is False
    assert examples[1].order_matters is True


def test_evaluate_one(tmp_path: Path):
    db_file = tmp_path / "db1.sqlite"
    import sqlite3
    conn = sqlite3.connect(db_file)
    conn.execute("CREATE TABLE t (v INTEGER)")
    conn.execute("INSERT INTO t VALUES (42)")
    conn.commit()
    conn.close()

    example = dataset.Example(
        id="ex-1", database="db1", question="get value", reference_sql="SELECT v FROM t"
    )

    def dummy_agent(question, db_path):
        return AgentState(
            question=question,
            db_path=db_path,
            sql="SELECT v FROM t",
            tool_calls=1,
            repairs=0,
            input_tokens=100,
            output_tokens=10,
        )

    record = runner.evaluate_one(example, db_file, dummy_agent)
    assert record.id == "ex-1"
    assert record.correct is True
    assert record.sql_valid is True
    assert record.input_tokens == 100
    assert record.output_tokens == 10


def test_runner_main_success_and_gate(tmp_path: Path, monkeypatch):
    db_file = tmp_path / "db1.sqlite"
    import sqlite3
    conn = sqlite3.connect(db_file)
    conn.execute("CREATE TABLE t (v INTEGER)")
    conn.execute("INSERT INTO t VALUES (42)")
    conn.commit()
    conn.close()

    dataset_file = tmp_path / "data.jsonl"
    dataset_file.write_text('{"id": "ex-1", "database": "db1", "question": "get v", "reference_sql": "SELECT 1"}\n')
    out_file = tmp_path / "report.json"
    baseline_file = tmp_path / "baseline.json"
    baseline_file.write_text(json.dumps({"summary": {"execution_accuracy": 100.0}}))

    from querypilot.config import settings
    monkeypatch.setattr(settings, "db_dir", tmp_path)
    monkeypatch.setattr(settings, "mock_mode", True)

    monkeypatch.setattr(
        "sys.argv",
        ["runner.py", "--dataset", str(dataset_file), "--out", str(out_file), "--baseline", str(baseline_file), "--mock"],
    )

    exit_code = runner.main()
    assert exit_code == 0
    assert out_file.exists()


def test_runner_main_gate_failure(tmp_path: Path, monkeypatch):
    dataset_file = tmp_path / "data.jsonl"
    dataset_file.write_text('{"id": "ex-1", "database": "empty_db", "question": "q", "reference_sql": "SELECT 1"}\n')
    out_file = tmp_path / "report.json"
    baseline_file = tmp_path / "baseline.json"
    baseline_file.write_text(json.dumps({"summary": {"execution_accuracy": 100.0}}))

    from querypilot.config import settings
    monkeypatch.setattr(settings, "db_dir", tmp_path)
    monkeypatch.setattr(settings, "mock_mode", True)

    monkeypatch.setattr(
        "sys.argv",
        ["runner.py", "--dataset", str(dataset_file), "--out", str(out_file), "--baseline", str(baseline_file), "--mock"],
    )

    exit_code = runner.main()
    assert exit_code == 1

