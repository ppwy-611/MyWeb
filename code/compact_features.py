"""Input transformer needed by the saved seven-feature sleep model."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin


RAW_COLUMNS = (
    "tst", "sol", "waso", "n3_percentage", "rem_percentage",
    "n3_latency_aasm", "sleep_efficiency",
)
MODEL_COLUMNS = (
    "tst", "log1p_sol", "log1p_waso", "n3_percentage",
    "rem_percentage", "log1p_n3_latency", "sleep_efficiency",
)


class CompactSleepFeatures(BaseEstimator, TransformerMixin):
    """Convert seven raw sleep measurements to the saved model's inputs."""

    def __init__(self, scheme: str = "log7_waso") -> None:
        self.scheme = scheme

    def fit(self, X: pd.DataFrame, y=None):
        self._check_input(X)
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        self._check_input(X)
        # Absent columns and blank/invalid cells have the same missing-input
        # semantics. The saved training median handles them later in the pipeline.
        source = X.reindex(columns=list(RAW_COLUMNS)).apply(pd.to_numeric, errors="coerce")
        source = source.replace([np.inf, -np.inf], np.nan)
        for column in RAW_COLUMNS:
            if column in {"n3_percentage", "rem_percentage"}:
                source.loc[~source[column].between(0, 100), column] = np.nan
            elif column == "sleep_efficiency":
                source.loc[~source[column].between(0, 100, inclusive="right"), column] = np.nan
            else:
                source.loc[source[column] < 0, column] = np.nan
        source.loc[source["tst"] <= 0, "tst"] = np.nan
        unusable = source.notna().sum(axis=1).eq(0)
        if unusable.any():
            rows = source.index[unusable].tolist()[:10]
            raise ValueError(f"这些行没有任何有效睡眠输入：{rows}；请至少提供一项有效指标")
        return pd.DataFrame({
            "tst": source["tst"],
            "log1p_sol": np.log1p(source["sol"]),
            "log1p_waso": np.log1p(source["waso"]),
            "n3_percentage": source["n3_percentage"],
            "rem_percentage": source["rem_percentage"],
            "log1p_n3_latency": np.log1p(source["n3_latency_aasm"]),
            "sleep_efficiency": source["sleep_efficiency"],
        }, index=X.index).replace([np.inf, -np.inf], np.nan)

    def get_feature_names_out(self, input_features=None) -> np.ndarray:
        if self.scheme != "log7_waso":
            raise ValueError(f"未知紧凑输入方案：{self.scheme}")
        return np.asarray(MODEL_COLUMNS, dtype=object)

    def _check_input(self, X: pd.DataFrame) -> None:
        if self.scheme != "log7_waso":
            raise ValueError(f"未知紧凑输入方案：{self.scheme}")
        if not isinstance(X, pd.DataFrame):
            raise TypeError("输入必须是带原始字段名的 pandas DataFrame")
        if not X.columns.is_unique:
            raise ValueError("输入字段名不能重复")
