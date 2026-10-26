#### Preamble ####
# Purpose: Small helpers shared by the test files (pytest puts tests/ on the import path, so they can import it).
# Author: Sean Murphy
# Date: 26 October 2026
# Pre-requisites: none

import polars as pl


def share_of(table, group_column, group, outcome_column, outcomes):
    """One cell of a cross-tab: among rows where `group_column` is `group`, the share whose `outcome_column` is in `outcomes`."""
    in_group = table.filter(pl.col(group_column) == group)
    return in_group[outcome_column].is_in(outcomes).mean()
