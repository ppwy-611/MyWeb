"""Run the saved Ridge model with any nonempty subset of its seven inputs."""

from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

# Import keeps the custom transformer available for joblib deserialization.
from compact_features import CompactSleepFeatures, RAW_COLUMNS


MODEL_PATH = Path(__file__).resolve().parent / "model" / "final_model.joblib"


def main() -> None:
    parser = argparse.ArgumentParser(description="预测次晨 Groningen 睡眠质量分数")
    parser.add_argument("--data", type=Path, required=True, help="输入 CSV 或 Excel 文件")
    parser.add_argument("--sheet", help="Excel 工作表名称，默认第一张")
    parser.add_argument("--output", type=Path, required=True, help="输出 CSV 文件")
    args = parser.parse_args()

    suffix = args.data.suffix.lower()
    if suffix == ".csv":
        data = pd.read_csv(args.data)
    elif suffix in {".xlsx", ".xlsm"}:
        data = pd.read_excel(args.data, sheet_name=args.sheet or 0, engine="openpyxl")
    else:
        parser.error("输入只支持 .csv、.xlsx 或 .xlsm")

    artifact = joblib.load(MODEL_PATH)
    if data.empty:
        parser.error("输入文件没有数据行")
    try:
        prepared = CompactSleepFeatures().transform(data)
    except (ValueError, TypeError) as exc:
        parser.error(str(exc))
    valid = prepared.notna().to_numpy()
    counts = valid.sum(axis=1)
    masks = (valid * (1 << np.arange(len(RAW_COLUMNS)))).sum(axis=1)
    result = data.copy()
    result["prediction"] = artifact["pipeline"].predict(data)
    result["valid_input_count"] = counts
    result["used_features"] = ["|".join(c for c, keep in zip(RAW_COLUMNS, row) if keep) for row in valid]
    result["missing_features"] = ["|".join(c for c, keep in zip(RAW_COLUMNS, row) if not keep) for row in valid]
    result["input_status"] = np.where(counts == 7, "complete_input", np.where(counts >= 3, "partial_input", "limited_input"))
    references = artifact.get("missing_input_reference", {})
    for output, metric in (("reference_cv_mae", "cv_mae"), ("reference_cv_rmse", "cv_rmse"),
                           ("reference_validation_rmse", "validation_rmse")):
        result[output] = [references.get(str(int(mask)), {}).get(metric, np.nan) for mask in masks]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.output, index=False, encoding="utf-8-sig")
    print(f"已将 {len(result)} 条预测保存到 {args.output.resolve()}")
    if (counts < 7).any():
        print("缺失或无效输入使用训练中位数填补；reference_* 是该输入组合的历史评估误差，不是当前预测的置信区间。")
    if (counts < 3).any():
        print(f"其中 {int((counts < 3).sum())} 行只有一项或两项有效输入，结果标记为 limited_input。")


if __name__ == "__main__":
    main()
