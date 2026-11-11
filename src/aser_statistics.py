# aser_statistics.py

import numpy as np
import pandas as pd

import statsmodels.formula.api as smf

from scipy import stats as sp_stats

from statsmodels.miscmodels.ordinal_model import OrderedModel
from statsmodels.stats.anova import anova_lm


class ASERStatistics:
    """
    Runs statistical analyses defined in analysis_registry.csv

    Expected registry columns:
        design
        outcome
        grouping
        visual
        model
        stat
        symbol

    Expected metadata columns:
        variable_name
        analysis_group
    """

    MIN_N = 50
    MIN_GROUP_SIZE = 10
    MIN_LEVEL_COUNT = 5
    MIN_BINARY_COUNT = 5
    REGISTRY_OUTCOMES = {
        "levels": ("literacy_level", "numeracy_level"),
        "foundational_learning": (
            "foundational_literacy",
            "foundational_numeracy",
        ),
        "mean_change": ("literacy_change", "numeracy_change"),
        "change_binary": (
            "literacy_change_binary",
            "numeracy_change_binary",
        ),
    }

    def __init__(
        self,
        metadata_df,
        registry_path
    ):
        self.metadata = metadata_df.copy()
        self.registry = (
            registry_path.copy()
            if isinstance(registry_path, pd.DataFrame)
            else pd.read_csv(registry_path)
        )
        required_columns = {
            "design",
            "outcome",
            "grouping",
            "model",
            "stat",
        }
        missing_columns = required_columns.difference(
            self.registry.columns
        )
        if missing_columns:
            raise ValueError(
                "Statistics registry is missing required columns: "
                + ", ".join(sorted(missing_columns))
            )

    # ==========================================================
    # PUBLIC ENTRY POINT
    # ==========================================================

    def run(
        self,
        df,
        design,
        outcomes=None
    ):
        """
        Returns tidy dataframe of statistical results.

        Parameters
        ----------
        df : pd.DataFrame

        design : str
            cross_section
            repeat_cross
            repeat_measures

        outcomes : list[str] | None

        Returns
        -------
        pd.DataFrame
        """

        results = []

        registry_subset = self.registry[
            self.registry["design"] == design
        ].copy()

        for _, rule in registry_subset.iterrows():

            registry_outcome = rule["outcome"]
            model = rule["model"]
            stat = rule["stat"]

            if pd.isna(model) or str(model).strip().lower() in {
                "",
                "none",
            }:
                continue

            if str(model).strip().lower() == "anova":
                model = "variance_explained"

            grouping_type = rule["grouping"]
            vars_to_test = self._get_variables_by_group(
                grouping_type
            )

            available_outcomes = [
                outcome
                for outcome in self.REGISTRY_OUTCOMES.get(
                    registry_outcome,
                    (registry_outcome,),
                )
                if outcome in df.columns
                and (outcomes is None or outcome in outcomes)
            ]

            for outcome in available_outcomes:
                for variable in vars_to_test:
                    if variable not in df.columns:
                        continue

                    record = self._run_analysis(
                        df=df,
                        outcome=outcome,
                        variable=variable,
                        model_name=model,
                        stat_name=stat,
                        design=design,
                        grouping=grouping_type
                    )
                    record["registry_outcome"] = registry_outcome
                    results.append(record)

        return pd.DataFrame(results)

    # ==========================================================
    # VARIABLE LOOKUP
    # ==========================================================

    def _get_variables_by_group(self, grouping):

        if "analysis_group" not in self.metadata.columns:
            return []

        return list(
            self.metadata.loc[
                self.metadata["analysis_group"] == grouping,
                "variable_name"
            ]
            .dropna()
            .unique()
        )

    # ==========================================================
    # DRIVER
    # ==========================================================

    def _prepare(self, df, outcome, variable, grouping, model_name):
        """
        Return a clean frame with numeric outcome `y` and predictor `x`
        (float if numeric, str if categorical), with NaN/inf removed.
        """

        y = df[outcome]
        if pd.api.types.is_bool_dtype(y):
            y = y.astype(int)
        y = pd.to_numeric(y, errors="coerce")
        y = y.replace([np.inf, -np.inf], np.nan)

        x = df[variable]
        categorical = (
            str(grouping).startswith("cat")
            or str(grouping) in {"binary", "round"}
            or pd.api.types.is_bool_dtype(x)
            or not pd.api.types.is_numeric_dtype(x)
        )
        if categorical:
            x = x.astype("object")
            x = x.where(x.notna(), None)
            x = x.map(lambda v: None if v is None else str(v).strip())
            x = x.replace("", None)
        else:
            x = pd.to_numeric(x, errors="coerce")
            x = x.replace([np.inf, -np.inf], np.nan)

        if str(grouping) == "round":
            # Compare first and last rounds, as the charts do
            rounds = x.dropna().drop_duplicates().tolist()
            if len(rounds) > 2:
                x = x.where(x.isin([rounds[0], rounds[-1]]))

        clean = pd.DataFrame({"y": y, "x": x}).dropna().reset_index(
            drop=True
        )

        if model_name == "logit" and clean["y"].nunique() == 2:
            low, high = sorted(clean["y"].unique())
            clean["y"] = (clean["y"] == high).astype(int)

        return clean, categorical

    def _run_analysis(
        self,
        df,
        outcome,
        variable,
        model_name,
        stat_name,
        design,
        grouping=None
    ):

        output = {
            "design": design,
            "outcome": outcome,
            "variable": variable,
            "model": model_name,
            "stat": stat_name,
            "value": None,
            "lower_ci": None,
            "upper_ci": None,
            "p_value": None,
            "n": None,
            "contrast": None,
            "df": None,
            "passed": False,
            "reason": None
        }

        # Multi-category predictors get one overall likelihood-ratio test
        use_lr = (
            model_name in {"logit", "ord_logit"}
            and str(grouping).startswith("cat")
        )
        if use_lr:
            output["stat"] = "lr"

        try:

            analysis_df, categorical = self._prepare(
                df,
                outcome,
                variable,
                grouping,
                model_name
            )

            output["n"] = len(analysis_df)

            if use_lr:
                output["contrast"] = "overall"
            elif model_name != "variance_explained":
                if categorical:
                    levels = sorted(analysis_df["x"].unique())
                    if len(levels) >= 2:
                        output["contrast"] = (
                            f"{levels[1]} vs {levels[0]} (reference)"
                        )
                        if len(levels) > 2:
                            output["contrast"] += (
                                "; other categories not shown"
                            )
                else:
                    output["contrast"] = "per 1-unit increase"

            passed, reason = self._check_assumptions(
                analysis_df,
                "y",
                "x",
                model_name
            )

            if not passed:
                output["reason"] = reason
                return output

            if use_lr:

                if not categorical:
                    output["reason"] = (
                        "Likelihood-ratio test needs a categorical "
                        "predictor"
                    )
                    return output

                result = self._likelihood_ratio(
                    analysis_df,
                    "y",
                    "x",
                    model_name
                )

            elif model_name == "ord_logit":

                result = self._ordinal_logit(
                    analysis_df,
                    "y",
                    "x"
                )

            elif model_name == "logit":

                result = self._logit(
                    analysis_df,
                    "y",
                    "x"
                )

            elif model_name == "linear":

                result = self._linear(
                    analysis_df,
                    "y",
                    "x"
                )

            elif model_name == "variance_explained":

                result = self._variance_explained(
                    analysis_df,
                    "y",
                    "x"
                )

            else:
                output["reason"] = (
                    f"Unknown model: {model_name}"
                )
                return output

            result = {
                key: (
                    None
                    if value is not None and not np.isfinite(value)
                    else value
                )
                for key, value in result.items()
            }

            if result.get("value") is None:
                output["reason"] = (
                    "Model did not return a finite estimate"
                )
                return output

            output.update(result)
            output["passed"] = True

        except Exception as e:

            output["reason"] = str(e)

        return output

    # ==========================================================
    # ASSUMPTIONS
    # ==========================================================

    def _check_assumptions(
        self,
        df,
        outcome,
        variable,
        model_name
    ):

        n = len(df)

        if n < self.MIN_N:
            return False, "Total N below threshold"

        if df[variable].nunique() < 2:
            return False, "Predictor has fewer than two values"

        if df[outcome].nunique() < 2:
            return False, "Outcome has fewer than two values"

        if model_name == "ord_logit":

            counts = df[outcome].value_counts()

            if counts.min() < self.MIN_LEVEL_COUNT:
                return (
                    False,
                    "Outcome levels too sparse"
                )

        elif model_name == "logit":

            counts = df[outcome].value_counts()

            if len(counts) != 2:
                return (
                    False,
                    "Outcome not binary"
                )

            if counts.min() < self.MIN_BINARY_COUNT:
                return (
                    False,
                    "Binary outcome too sparse"
                )

        if not pd.api.types.is_numeric_dtype(df[variable]):

            group_counts = (
                df[variable]
                .value_counts()
            )

            if group_counts.min() < self.MIN_GROUP_SIZE:
                return (
                    False,
                    "Group size too small"
                )

        return True, None

    # ==========================================================
    # LIKELIHOOD-RATIO TEST (multi-category predictors)
    # ==========================================================

    def _likelihood_ratio(
        self,
        df,
        outcome,
        variable,
        model_name
    ):
        """
        Overall test that the predictor is associated with the outcome:
        full model (all category dummies) against an intercept-only model.
        """

        if model_name == "ord_logit":

            x = pd.get_dummies(
                df[[variable]],
                drop_first=True,
                dtype=float
            )

            fitted = OrderedModel(
                df[outcome].astype(float),
                x,
                distr="logit"
            ).fit(method="bfgs", disp=False)

            # Thresholds-only MLE reproduces the observed level shares
            counts = df[outcome].value_counts().to_numpy(dtype=float)
            llf_null = float(np.sum(counts * np.log(counts / counts.sum())))
            llf_full = float(fitted.llf)
            degrees = x.shape[1]

        else:

            fitted = smf.logit(
                f"{outcome} ~ C({variable})",
                data=df
            ).fit(disp=False)

            llf_null = float(fitted.llnull)
            llf_full = float(fitted.llf)
            degrees = int(fitted.df_model)

        chi2 = max(2 * (llf_full - llf_null), 0.0)

        return {
            "value": chi2,
            "lower_ci": None,
            "upper_ci": None,
            "p_value": sp_stats.chi2.sf(chi2, degrees),
            "df": degrees
        }

    # ==========================================================
    # ORDINAL LOGIT
    # ==========================================================

    def _ordinal_logit(
        self,
        df,
        outcome,
        variable
    ):

        x = df[[variable]].copy()

        if not pd.api.types.is_numeric_dtype(x[variable]):
            x = pd.get_dummies(
                x,
                drop_first=True,
                dtype=float
            )
        else:
            x[variable] = x[variable].astype(float)

        model = OrderedModel(
            df[outcome].astype(float),
            x,
            distr="logit"
        )

        fitted = model.fit(
            method="bfgs",
            disp=False
        )

        coef = fitted.params.iloc[0]
        p = fitted.pvalues.iloc[0]

        ci = fitted.conf_int()

        lower = ci.iloc[0, 0]
        upper = ci.iloc[0, 1]

        return {
            "value": np.exp(coef),
            "lower_ci": np.exp(lower),
            "upper_ci": np.exp(upper),
            "p_value": p
        }

    # ==========================================================
    # BINARY LOGIT
    # ==========================================================

    def _logit(
        self,
        df,
        outcome,
        variable
    ):

        formula = f"{outcome} ~ C({variable})"

        if pd.api.types.is_numeric_dtype(
            df[variable]
        ):
            formula = (
                f"{outcome} ~ {variable}"
            )

        model = smf.logit(
            formula,
            data=df
        )

        fitted = model.fit(disp=False)

        coef = fitted.params.iloc[1]
        p = fitted.pvalues.iloc[1]

        ci = fitted.conf_int()

        lower = ci.iloc[1, 0]
        upper = ci.iloc[1, 1]

        return {
            "value": np.exp(coef),
            "lower_ci": np.exp(lower),
            "upper_ci": np.exp(upper),
            "p_value": p
        }

    # ==========================================================
    # LINEAR
    # ==========================================================

    def _linear(
        self,
        df,
        outcome,
        variable
    ):

        formula = f"{outcome} ~ C({variable})"

        if pd.api.types.is_numeric_dtype(
            df[variable]
        ):
            formula = (
                f"{outcome} ~ {variable}"
            )

        fitted = smf.ols(
            formula,
            data=df
        ).fit()

        coef = fitted.params.iloc[1]
        p = fitted.pvalues.iloc[1]

        ci = fitted.conf_int()

        lower = ci.iloc[1, 0]
        upper = ci.iloc[1, 1]

        return {
            "value": coef,
            "lower_ci": lower,
            "upper_ci": upper,
            "p_value": p
        }

    # ==========================================================
    # VARIANCE EXPLAINED
    # ==========================================================

    def _variance_explained(
        self,
        df,
        outcome,
        variable
    ):

        model = smf.ols(
            f"{outcome} ~ C({variable})",
            data=df
        ).fit()

        aov = anova_lm(model)

        ss_between = aov["sum_sq"].iloc[0]
        ss_total = aov["sum_sq"].sum()

        eta2 = ss_between / ss_total

        p = aov["PR(>F)"].iloc[0]

        return {
            "value": eta2,
            "lower_ci": None,
            "upper_ci": None,
            "p_value": p
        }