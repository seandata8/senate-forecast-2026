#### Preamble ####
# Purpose: Build the codebook (data/codebook.md) from the schemas in schemas.py, so the two can never disagree.
#          Each column's type, whether it can be missing, its allowed values and its description come from its schema.
# Author: Sean Murphy
# Date: 21 October 2026
# Pre-requisites: none

from senate_forecast_2026.schemas import FILE_SCHEMAS

INTRODUCTION = """# Codebook

Every data file the pipeline makes, column by column. Simulated versions are in `data/00-simulated_data/`,
real versions in `data/02-analysis_data/`, with the same names and columns. Each file is a parquet, with a
readable CSV next to it: `<name>.csv` in full for small files, `samp_<name>.csv` (25 rows) for large ones.

**Missing values.** A column marked "yes" under *Missing* can be empty (null); its description says what that
means. Every other column is never empty: the scripts check this before saving (`save_data()` in `save.py`).

**Transformations.** Each description says where the column comes from and anything we changed, such as CES
categories we combined.

This file is written by `scripts/write_codebook.py` from `src/senate_forecast_2026/schemas.py`. Edit the
schemas, not this file, then run the script.
"""

def describe_check(check):
    """One pandera check in words, e.g. "≥ 0" or "AL, AK, ..."."""
    if check.name == "isin":
        return ", ".join(str(value) for value in check.statistics["allowed_values"])
    if check.name == "greater_than":
        return f"> {check.statistics['min_value']}"
    if check.name == "greater_than_or_equal_to":
        return f"≥ {check.statistics['min_value']}"
    if check.name == "less_than_or_equal_to":
        return f"≤ {check.statistics['max_value']}"
    raise ValueError(f"No wording for check {check.name!r}; add it to describe_check()")


def allowed_values(column):
    """All of a column's checks in words, e.g. "≥ 0, ≤ 1". "unique" if no two rows may share a value."""
    rules = [describe_check(check) for check in column.checks]
    if column.unique:
        rules.append("unique")
    return ", ".join(rules) if rules else "any"


def codebook_markdown():
    """The whole codebook as Markdown text: an introduction, then one table per schema."""
    # Files that share a schema (the three responses files) get one table.
    files_by_schema = {}
    for file_name, schema in FILE_SCHEMAS.items():
        files_by_schema.setdefault(schema, []).append(file_name)

    sections = [INTRODUCTION]
    for schema, file_names in files_by_schema.items():
        title = ", ".join(f"`{name}`" for name in file_names)
        description = " ".join(schema.__doc__.split())  # the class docstring, on one line
        rows = [
            "| Column | Type | Missing | Allowed values | Description |",
            "|---|---|---|---|---|",
        ]
        for name, column in schema.to_schema().columns.items():
            missing = "yes" if column.nullable else "no"
            rows.append(f"| `{name}` | {column.dtype} | {missing} | {allowed_values(column)} | {column.description} |")
        sections.append(f"## {title}\n\n{description}\n\n" + "\n".join(rows) + "\n")
    return "\n".join(sections)
