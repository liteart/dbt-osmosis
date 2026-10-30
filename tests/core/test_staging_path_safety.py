"""Security regressions for AI-provided staging model names."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from ruamel.yaml import YAML

from dbt_osmosis.core.generators import _resolve_staging_output_paths
from dbt_osmosis.core.llm import ColumnTransformation, StagingModelSpec
from dbt_osmosis.core.staging import (
    StagingGenerationResult,
    _generate_staging_yaml,
    _infer_staging_model_path,
    write_staging_files,
)


@pytest.mark.parametrize(
    "name", ["../escape", "/tmp/escape", r"..\escape", "", "..", "bad\0name", "C:escape"]
)
def test_both_staging_generators_reject_unsafe_names(tmp_path: Path, name: str) -> None:
    project = SimpleNamespace(config=SimpleNamespace(project_dir=str(tmp_path)))
    with pytest.raises(ValueError, match="Invalid staging model name"):
        _infer_staging_model_path(project, None, name)
    with pytest.raises(ValueError, match="Invalid staging model name"):
        _resolve_staging_output_paths(project, name, None)


@pytest.mark.parametrize("extension", ["sql", "yml"])
def test_both_staging_generators_reject_symlink_escape(tmp_path: Path, extension: str) -> None:
    root = tmp_path / "models" / "staging"
    root.mkdir(parents=True)
    (root / f"stg_orders.{extension}").symlink_to(tmp_path / "outside")
    project = SimpleNamespace(config=SimpleNamespace(project_dir=str(tmp_path)))
    with pytest.raises(ValueError, match="outside the staging directory"):
        _infer_staging_model_path(project, None, "stg_orders")
    with pytest.raises(ValueError, match="outside the staging directory"):
        _resolve_staging_output_paths(project, "stg_orders", None)


def test_valid_staging_paths_remain_in_configured_directory(tmp_path: Path) -> None:
    project = SimpleNamespace(config=SimpleNamespace(project_dir=str(tmp_path)))
    expected = (tmp_path / "custom" / "stg_orders.sql", tmp_path / "custom" / "stg_orders.yml")
    assert _resolve_staging_output_paths(project, "stg_orders", tmp_path / "custom") == expected


def test_default_staging_directory_cannot_be_a_symlink_outside_project(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    (project_root / "models").mkdir(parents=True)
    (project_root / "models" / "staging").symlink_to(tmp_path, target_is_directory=True)
    project = SimpleNamespace(config=SimpleNamespace(project_dir=str(project_root)))
    with pytest.raises(ValueError, match="outside the project root"):
        _infer_staging_model_path(project, None, "stg_orders")
    with pytest.raises(ValueError, match="outside the project root"):
        _resolve_staging_output_paths(project, "stg_orders", None)


def test_staging_yaml_preserves_untrusted_descriptions_as_scalars() -> None:
    description = 'quoted "text"\n    config:\n      enabled: false'
    spec = StagingModelSpec(
        source_name="raw.orders",
        staging_name="stg_orders",
        description=description,
        columns=[ColumnTransformation("id", "id", description=description)],
    )
    model = YAML(typ="safe").load(_generate_staging_yaml(spec))["models"][0]
    assert model == {
        "name": "stg_orders",
        "description": description,
        "columns": [{"name": "id", "description": description}],
    }


def test_write_rechecks_symlink_before_writing_either_file(tmp_path: Path) -> None:
    root = tmp_path / "staging"
    root.mkdir()
    sql_path = root / "stg_orders.sql"
    yaml_path = root / "stg_orders.yml"
    yaml_path.symlink_to(tmp_path / "outside.yml")
    spec = StagingModelSpec("raw.orders", "stg_orders", "", [])
    result = StagingGenerationResult(
        "raw.orders", spec=spec, sql_path=sql_path, yaml_path=yaml_path
    )
    with pytest.raises(ValueError, match="outside the staging directory"):
        write_staging_files(result)
    assert not sql_path.exists()
    assert not (tmp_path / "outside.yml").exists()


@pytest.mark.parametrize("existing_extension", ["sql", "yml"])
def test_legacy_writer_requires_explicit_overwrite(tmp_path: Path, existing_extension: str) -> None:
    sql_path = tmp_path / "stg_orders.sql"
    yaml_path = tmp_path / "stg_orders.yml"
    existing = tmp_path / f"stg_orders.{existing_extension}"
    existing.write_text("original", encoding="utf-8")
    result = StagingGenerationResult(
        "raw.orders",
        spec=StagingModelSpec("raw.orders", "stg_orders", "", []),
        sql_path=sql_path,
        yaml_path=yaml_path,
    )
    with pytest.raises(FileExistsError):
        write_staging_files(result)
    assert existing.read_text(encoding="utf-8") == "original"
    assert not (yaml_path if existing == sql_path else sql_path).exists()
    write_staging_files(result, overwrite=True)
    assert sql_path.exists() and yaml_path.exists()
