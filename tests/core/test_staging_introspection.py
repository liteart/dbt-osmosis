"""Regression tests for source metadata used in staging generation."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from dbt_osmosis.core.llm import StagingModelSpec
from dbt_osmosis.core.staging import generate_staging_for_source


def test_manifest_source_without_columns_uses_physical_identifier(
    tmp_path: Path, monkeypatch
) -> None:
    source = SimpleNamespace(
        source_name="raw",
        name="orders",
        identifier="physical_orders",
        database="warehouse",
        schema="landing",
        description="Orders",
        columns={},
    )
    relation_create = Mock(return_value=object())
    get_columns = Mock(return_value=[SimpleNamespace(name="order_id", dtype="integer")])
    project = SimpleNamespace(
        manifest=SimpleNamespace(sources={"source.raw.orders": source}),
        adapter=SimpleNamespace(
            Relation=SimpleNamespace(create=relation_create), get_columns_in_relation=get_columns
        ),
        config=SimpleNamespace(project_dir=str(tmp_path)),
    )
    generate = Mock(return_value=StagingModelSpec("raw.orders", "stg_orders", "", []))
    monkeypatch.setattr("dbt_osmosis.core.staging.generate_staging_model_spec", generate)

    result = generate_staging_for_source(project, None, "raw", "orders")

    assert result.error is None
    relation_create.assert_called_once_with(
        database="warehouse", schema="landing", identifier="physical_orders"
    )
    generate.assert_called_once_with(
        source_name="raw.orders",
        columns=[{"name": "order_id", "data_type": "integer", "description": ""}],
        table_description="Orders",
        source_type="source",
        temperature=0.3,
    )
