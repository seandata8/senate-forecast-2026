#### Preamble ####
# Purpose: Write the codebook, data/codebook.md, from the schemas. Run it after changing src/senate_forecast_2026/schemas.py;
#          tests/test_codebook.py fails if the codebook is out of date.
# Author: Sean Murphy
# Date: 21 October 2026
# Pre-requisites: uv sync
# Run: uv run scripts/write_codebook.py (or PyCharm's run button)

from senate_forecast_2026.codebook import codebook_markdown
from senate_forecast_2026.paths import CODEBOOK

CODEBOOK.write_text(codebook_markdown())
print(f"wrote {CODEBOOK}")
