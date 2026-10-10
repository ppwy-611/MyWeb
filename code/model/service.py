"""Use the saved Ridge and explain exact contributions about median inputs."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from compact_features import RAW_COLUMNS

MODEL_PATH = Path(__file__).resolve().parent / "final_model.joblib"
FIELDS = [
    dict(key="tst", label="总睡眠时长", unit="分钟", min=0, exclusive_min=True,
         hint="这一晚实际睡着的总时长，不含清醒时间。", placeholder="例如 420", basic=True),
    dict(key="sol", label="入睡耗时", unit="分钟", min=0, exclusive_min=False,
         hint="从尝试入睡到睡着的时间。0 表示几乎立即入睡；不知道可以留空。", placeholder="例如 20", basic=True),
    dict(key="waso", label="夜间清醒时长", unit="分钟", min=0, exclusive_min=False,
         hint="入睡之后所有清醒时段的累计时长，不是觉醒次数。", placeholder="例如 35", basic=True),
    dict(key="n3_percentage", label="深睡占比", unit="%", min=0, max=100, exclusive_min=False,
         hint="N3 深睡占总睡眠的百分比，按设备报告填写。", placeholder="例如 18", basic=False),
    dict(key="rem_percentage", label="REM 占比", unit="%", min=0, max=100, exclusive_min=False,
         hint="快速眼动睡眠占总睡眠的百分比，按设备报告填写。", placeholder="例如 22", basic=False),
    dict(key="n3_latency_aasm", label="深睡潜伏期", unit="分钟", min=0, exclusive_min=False,
         hint="N3 深睡的潜伏期，请填写报告中的值；不同设备的定义可能不同。", placeholder="例如 25", basic=False),
    dict(key="sleep_efficiency", label="睡眠效率", unit="%", min=0, max=100, exclusive_min=True,
         hint="实际睡眠时长与卧床时长的比值，填写 0–100 之间的百分数。", placeholder="例如 88", basic=True),
]
FIELD_MAP = {f["key"]: f for f in FIELDS}
LOG_FIELDS = {"sol", "waso", "n3_latency_aasm"}


class InputError(ValueError):
    def __init__(self, errors: dict[str, str]):
        super().__init__("请检查输入后再评估")
        self.errors = errors


def validate_inputs(inputs: dict[str, Any]) -> dict[str, float]:
    values, errors = {}, {}
    for key, raw in inputs.items():
        if key not in FIELD_MAP:
            errors[key] = "无法识别此指标，请使用页面中的字段"
            continue
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            continue
        field = FIELD_MAP[key]
        try:
            if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
                raise ValueError
            value = float(raw)
            if not math.isfinite(value):
                raise ValueError
        except (ValueError, TypeError, OverflowError):
            errors[key] = "请填写有效数字，或留空表示未提供"
            continue
        if value < 0 or (field["exclusive_min"] and value == 0):
            errors[key] = "请填写大于 0 的数值" if field["exclusive_min"] else "数值不能小于 0"
        elif field.get("max") is not None and value > field["max"]:
            errors[key] = "百分比不能超过 100"
        else:
            values[key] = value
    if values.get("n3_percentage", 0) + values.get("rem_percentage", 0) > 100:
        for key in ("n3_percentage", "rem_percentage"):
            errors[key] = "深睡与 REM 占比相加不能超过 100%"
    if not values and not errors:
        errors["_form"] = "请至少填写一项睡眠指标；不知道的指标可以留空"
    if errors:
        raise InputError(errors)
    return values


def display_score(prediction: float) -> dict:
    raw = 100 * (14 - prediction) / 14
    bounded = min(100.0, max(0.0, raw))
    # Classify the same one-decimal value visible to the user at boundaries.
    score = round(bounded, 1)
    if score >= 80:
        grade, code = "舒适", "comfortable"
    elif score >= 60:
        grade, code = "一般", "average"
    else:
        grade, code = "较差", "poor"
    return dict(value=score, unrounded_value=bounded, unclipped_value=raw, grade=grade, grade_code=code,
                clipped=raw < 0 or raw > 100,
                scale_note="百分制是模型估计的展示指数，不表示概率、准确率或健康百分比")


def fmt(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".")


def friendly_observation(factor: dict) -> str:
    """Describe provided measurements relative to the model's reference."""
    if math.isclose(factor["value"], factor["typical_value"], rel_tol=1e-9, abs_tol=1e-9):
        return factor["label"] + "与参考记录相近"
    higher = factor["value"] > factor["typical_value"]
    phrases = {
        "tst": ("睡眠时长更长一些", "睡眠时长短了一些"),
        "sol": ("入睡花的时间更长一些", "入睡花的时间少了一些"),
        "waso": ("夜里清醒的时间更长一些", "夜里清醒的时间少了一些"),
        "n3_percentage": ("深睡比例更高一些", "深睡比例少了一些"),
        "rem_percentage": ("REM 比例更高一些", "REM 比例低了一些"),
        "n3_latency_aasm": ("深睡潜伏期更长一些", "深睡潜伏期短了一些"),
        "sleep_efficiency": ("睡眠效率更高一些", "睡眠效率低了一些"),
    }
    return phrases[factor["key"]][0 if higher else 1]


def friendly_summary(factors: list[dict], mode: str) -> str:
    down = [f for f in factors if f["direction"] == "down"]
    up = [f for f in factors if f["direction"] == "up"]
    if down:
        sentence = f"和参考记录相比，这一晚{friendly_observation(down[0])}，拉低了这次模型评分"
        if up:
            sentence += f"，不过{up[0]['label']}也给分数提供了一些支撑"
        sentence += "。"
    elif up:
        sentence = f"和参考记录相比，这一晚{friendly_observation(up[0])}，为这次模型评分加了分。"
    else:
        sentence = "你填写的指标在模型中的影响与参考记录比较接近，这一晚的估计没有明显的加分或减分项。"
    if len(factors) < 3:
        sentence = sentence.removesuffix("。") + "，现在知道的还不多，补充几项真实记录后可以再看看。"
    if mode == "simulation":
        sentence = "在这次模拟中，" + sentence.replace("和参考记录相比，这一晚", "相对参考记录，调整后的")
    return sentence


class SleepModel:
    def __init__(self, path: Path = MODEL_PATH):
        self.artifact = joblib.load(path)
        self.pipeline = self.artifact["pipeline"]
        self.imputer = self.pipeline.named_steps["imputer"]
        self.scaler = self.pipeline.named_steps["scaler"]
        self.ridge = self.pipeline.named_steps["model"]
        self.median = np.asarray(self.imputer.statistics_, dtype=float)
        self.z_median = self.scaler.transform(self.median[None, :])[0]
        self.baseline_prediction = float(self.ridge.predict(self.z_median[None, :])[0])
        self.reference = self.artifact.get("missing_input_reference", {})

    def config(self) -> dict:
        return dict(fields=FIELDS, score_thresholds=dict(comfortable=80, average=60),
                    presets={
                        "three": dict(tst=420, waso=35, sleep_efficiency=88),
                        "four": dict(tst=420, sol=20, waso=35, sleep_efficiency=88),
                        "full": dict(tst=420, sol=20, waso=35, n3_percentage=18, rem_percentage=22,
                                     n3_latency_aasm=25, sleep_efficiency=88),
                    }, report_engine="ridge_contributions_and_local_templates")

    def evaluate(self, inputs: dict[str, Any], mode: str = "record") -> dict:
        values = validate_inputs(inputs)
        frame = pd.DataFrame([values])
        prediction = float(self.pipeline.predict(frame)[0])
        if not math.isfinite(prediction):
            raise InputError({"_form": "这些数值过大，无法得到有限预测；请检查单位与输入"})
        features = self.pipeline.named_steps["features"].transform(frame)
        z = self.scaler.transform(self.imputer.transform(features))[0]
        gsqs_contributions = (z - self.z_median) * self.ridge.coef_
        factors = []
        for index, key in enumerate(RAW_COLUMNS):
            if key not in values:
                continue
            field = FIELD_MAP[key]
            typical = float(np.expm1(self.median[index]) if key in LOG_FIELDS else self.median[index])
            impact = float(-100 / 14 * gsqs_contributions[index])
            if abs(impact) < .05:
                direction, narrative = "neutral", "相对训练典型值，这一项对本次估计影响较小。"
            else:
                direction = "up" if impact > 0 else "down"
                verb = "上调" if impact > 0 else "下调"
                narrative = f"相对训练典型值 {fmt(typical)} {field['unit']}，这一项使模型的体验指数{verb}约 {abs(impact):.1f} 分。"
            factors.append(dict(key=key, label=field["label"], value=values[key], unit=field["unit"],
                                typical_value=typical, gsqs_contribution=float(gsqs_contributions[index]),
                                score_contribution=impact, direction=direction, explanation=narrative,
                                definition=field["hint"]))
        factors.sort(key=lambda f: abs(f["score_contribution"]), reverse=True)
        missing = [key for key in RAW_COLUMNS if key not in values]
        mask = sum(1 << i for i, key in enumerate(RAW_COLUMNS) if key in values)
        reference = self.reference.get(str(mask), {})
        score = display_score(prediction)
        headline = friendly_summary(factors, mode)
        missing_labels = [FIELD_MAP[k]["label"] for k in missing]
        if missing:
            missing_note = f"你提供了 {len(values)} 项指标；{'、'.join(missing_labels)}未提供，使用训练典型值填补，不能据此判断这些指标的实际情况。"
        else:
            missing_note = "本次提供了完整七项指标，没有使用缺失值填补。"
        next_steps = ["可以核对测量单位和数值，修改或补充真实指标后再次评估。"]
        if missing:
            next_steps.insert(0, f"如果能获取{missing_labels[0]}，可以补充后观察估计及解释的变化。")
        if len(values) < 3:
            next_steps.insert(0, "当前仅有一项或两项输入，个体信息有限，优先补充可获得的指标。")
        if mode == "simulation":
            next_steps.insert(0, "模拟输入的变化只反映模型计算关系，不代表现实中的改善效果。")
        return dict(prediction=prediction, target="Groningen_ts", score=score, mode=mode, inputs=values,
                    valid_input_count=len(values), used_features=list(values), missing_features=missing,
                    input_status="complete_input" if not missing else "partial_input" if len(values) >= 3 else "limited_input",
                    reference=dict(cv_mae=reference.get("cv_mae"), cv_rmse=reference.get("cv_rmse"),
                                   validation_rmse=reference.get("validation_rmse"),
                                   note="同组合历史群体误差，不是这条预测的实际误差或置信区间"),
                    baseline=dict(prediction=self.baseline_prediction,
                                  score_unclipped=100 * (14 - self.baseline_prediction) / 14,
                                  name="所有指标使用训练典型值的参考输入"),
                    factors=factors,
                    report=dict(summary=headline, drivers=[
                                    f"相对参考记录，{friendly_observation(f)}，" +
                                    ("在模型中拉低了评分。" if f["direction"] == "down" else
                                     "在模型中给评分提供了支撑。" if f["direction"] == "up" else "对这次模型评分影响较小。")
                                    for f in factors[:3]],
                                reference_note="这里的参考记录是训练数据的典型输入，不能将偏高或偏低直接理解为健康标准。",
                                missing_note=missing_note, next_steps=next_steps,
                                boundary_note="等级来自原型展示规则；影响因素解释模型中的关联，不表示因果关系。",
                                engine="本地模型贡献分析"))
