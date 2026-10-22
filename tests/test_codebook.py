#### Preamble ####
# Purpose: Check the codebook (data/codebook.md) matches the schemas, so it cannot fall out of date.
# Author: Sean Murphy
# Date: 21 October 2026
# Pre-requisites: uv run scripts/write_codebook.py
# Run from the repo root: uv run pytest

from pathlib import Path

from senate_forecast_2026.codebook import codebook_markdown
from senate_forecast_2026.schemas import FILE_SCHEMAS


def test_codebook_is_up_to_date():
    # If this fails, a schema changed: run `uv run scripts/write_codebook.py` and commit data/codebook.md.
    assert Path("data/codebook.md").read_text() == codebook_markdown()


def test_every_column_has_a_description():
    for file_name, schema in FILE_SCHEMAS.items():
        for column_name, column in schema.to_schema().columns.items():
            assert column.description, f"{file_name}.{column_name} has no description"
