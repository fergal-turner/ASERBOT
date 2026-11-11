"""Statistics smoke test: messy dtypes and NaN must not break the models."""
import numpy as np
import pandas as pd

from aser_statistics import ASERStatistics

rng = np.random.default_rng(0)
n = 400
df = pd.DataFrame({
    "sex": rng.choice(["female", "male", None], n, p=[0.45, 0.45, 0.1]),
    "disability": rng.choice([True, False], n),
    "region code": rng.choice([1, 2, 3], n),
    "age": rng.integers(5, 17, n).astype(float),
    "grade": pd.Categorical(rng.choice(["a", "b", "c"], n)),
    "literacy_level": rng.integers(0, 5, n).astype(float),
    "foundational_literacy": rng.integers(0, 2, n).astype(float),
})
df.loc[rng.choice(n, 30, replace=False), "age"] = np.nan
df.loc[rng.choice(n, 20, replace=False), "literacy_level"] = np.nan
df.loc[5, "age"] = np.inf
df["sex"] = df["sex"].astype("string")

metadata = pd.DataFrame({
    "variable_name": ["sex", "disability", "region code", "age", "grade"],
    "analysis_group": ["binary", "binary", "cat_low", "cont", "cat_high"],
})
registry = pd.DataFrame([
    ("cross_section", "levels", g, "ord_logit", "or")
    for g in ("binary", "cat_low", "cat_high", "cont")
] + [
    ("cross_section", "foundational_learning", g, "logit", "or")
    for g in ("binary", "cat_low", "cat_high", "cont")
] + [
    ("cross_section", "foundational_learning", "binary", "anova", "eta2"),
], columns=["design", "outcome", "grouping", "model", "stat"])

results = ASERStatistics(metadata, registry).run(df, "cross_section")
print(results[["outcome", "variable", "model", "stat", "df", "n", "value", "p_value", "passed", "reason"]])

assert results["passed"].all(), results.loc[~results["passed"], ["variable", "model", "reason"]]
assert np.isfinite(results["value"].astype(float)).all()
sex_n = results.loc[results["variable"] == "sex", "n"]
assert (sex_n < n).all()
assert (results.loc[results["variable"] == "age", "n"] < n - 30).all()

lr = results[results["variable"].isin(["region code", "grade"])
             & (results["model"] != "variance_explained")]
assert len(lr) == 4 and (lr["stat"] == "lr").all()
assert (lr["df"] == 2).all()
assert (lr["value"] >= 0).all() and lr["p_value"].between(0, 1).all()
assert lr["lower_ci"].isna().all()
assert (results.loc[results["variable"].isin(["sex", "age"])
                    & (results["model"] != "variance_explained"), "stat"] == "or").all()
print("ok")
