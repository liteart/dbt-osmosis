"""The staging generator must treat dbt names as Jinja data."""

import pytest
from jinja2 import Environment

from dbt_osmosis.core.llm import ColumnTransformation, StagingModelSpec


@pytest.mark.parametrize("source_type", ["source", "model", "seed"])
@pytest.mark.parametrize(
    ("name", "source_args"),
    [
        ("orders'); dangerous(); ref('other", ("orders'); dangerous(); ref('other",) * 2),
        (
            "raw.orders'); dangerous(); source('other",
            ("raw", "orders'); dangerous(); source('other"),
        ),
    ],
)
def test_staging_names_and_materialization_are_jinja_literals(
    source_type: str, name: str, source_args: tuple[str, str]
) -> None:
    calls: list[tuple[str, object]] = []
    materialization = "view'); dangerous(); config(materialized='table"
    spec = StagingModelSpec(
        source_name=name,
        staging_name="stg_orders",
        description="",
        columns=[ColumnTransformation("id", "id")],
        materialization=materialization,
        source_type=source_type,
    )

    def record(kind: str, value: object) -> str:
        calls.append((kind, value))
        return "safe"

    rendered = (
        Environment()
        .from_string(spec.to_sql())
        .render(
            config=lambda **kwargs: record("config", kwargs),
            source=lambda *args: record("source", args),
            ref=lambda *args: record("ref", args),
            dangerous=lambda: pytest.fail("untrusted data executed as Jinja"),
        )
    )
    assert calls == [
        ("config", {"materialized": materialization}),
        ("source", source_args) if source_type == "source" else ("ref", (name,)),
    ]
    assert "select * from safe" in rendered
