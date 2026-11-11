# aser_analysis_planner.py

import pandas as pd


class ASERAnalysisPlanner:
    """
    Converts:

        metadata dictionary/dataframe
        +
        analysis registry
        +
        scored dataframe

    into a fully expanded analysis plan.

    One row in the analysis plan =
    one analysis / visualisation to run.

    Example:

        gender + levels
        -> stack_bar
        -> ord_logit

        age + foundational_learning
        -> line
        -> logit
    """

    def __init__(
        self,
        df: pd.DataFrame,
        metadata: pd.DataFrame,
        analysis_registry: pd.DataFrame,
        design: str,
    ):
        self.df = df.copy()
        self.metadata = metadata.copy()
        self.analysis_registry = analysis_registry.copy()
        self.design = design

    # =====================================================
    # VARIABLE CLASSIFICATION
    # =====================================================

    def indicator_type(self, meta):
        """
        Classify indicator into:

            binary
            cat_low
            cat_high
            ord_low
            cont
        """

        variable = meta["name"]

        if variable not in self.df.columns:
            return "unknown"

        n_unique = self.df[variable].nunique(dropna=True)

        if meta["type"] == "continuous":
            return "cont"

        if meta["type"] == "categorical":

            if n_unique == 2:
                return "binary"

            if n_unique <= 5:
                return "cat_low"

            return "cat_high"

        if meta["type"] == "ordinal":

            if n_unique <= 5:
                return "ord_low"

            return "cont"

        return "unknown"

    # =====================================================
    # OUTCOME DETECTION
    # =====================================================

    def get_available_outcomes(self):
        """
        Returns outcome columns present in dataset.
        """

        candidates = [

            # cross-sectional
            "literacy_level",
            "numeracy_level",

            "foundational_literacy",
            "foundational_numeracy",

            # repeat measures
            "literacy_change",
            "numeracy_change",

            "literacy_change_binary",
            "numeracy_change_binary",
        ]

        return [
            c
            for c in candidates
            if c in self.df.columns
        ]

    # =====================================================
    # OUTCOME --> REGISTRY OUTCOME
    # =====================================================

    @staticmethod
    def registry_outcome(outcome):

        mapping = {

            "literacy_level":
                "levels",

            "numeracy_level":
                "levels",

            "foundational_literacy":
                "foundational_learning",

            "foundational_numeracy":
                "foundational_learning",

            "literacy_change":
                "mean_change",

            "numeracy_change":
                "mean_change",

            "literacy_change_binary":
                "change_binary",

            "numeracy_change_binary":
                "change_binary",
        }

        return mapping.get(outcome)

    # =====================================================
    # ANALYSIS VARIABLES
    # =====================================================

    def get_analysis_variables(self):
        """
        Returns all disaggregation variables.
        """

        variables = []

        for _, meta in self.metadata.iterrows():

            variable = meta["name"]

            if variable not in self.df.columns:
                continue

            if meta.get("role") != "disaggregation":
                continue

            grouping = self.indicator_type(meta)

            if grouping == "unknown":
                continue

            variables.append(
                {
                    "variable": variable,
                    "grouping": grouping,
                    "n_unique":
                        self.df[variable]
                        .nunique(dropna=True)
                }
            )

        # "round" is compared as a binary predictor ahead of all
        # other variables (baseline vs endline overview figures).
        variables = [
            item for item in variables if item["variable"] != "round"
        ]
        if (
            self.design != "cross_section"
            and "round" in self.df.columns
            and self.df["round"].nunique(dropna=True) >= 2
        ):
            variables.insert(
                0,
                {
                    "variable": "round",
                    "grouping": "round",
                    "n_unique": self.df["round"].nunique(dropna=True),
                },
            )

        return variables

    # =====================================================
    # ANALYSIS PLAN
    # =====================================================

    DESIGN_ORDER = [
        "cross_section",
        "repeat_cross",
        "repeat_measures",
    ]

    PLAN_COLUMNS = [
        "design",
        "variable",
        "grouping",
        "domain",
        "outcome",
        "registry_outcome",
        "change",
        "interaction",
        "vis",
        "double_repeat",
        "model",
        "stat",
        "symbol",
        "n_unique",
        "enabled",
    ]

    def included_designs(self):
        """
        Designs are cumulative:

            cross_section   -> cross_section
            repeat_cross    -> cross_section, repeat_cross
            repeat_measures -> all three
        """

        if self.design not in self.DESIGN_ORDER:
            return [self.design]

        return self.DESIGN_ORDER[
            : self.DESIGN_ORDER.index(self.design) + 1
        ]

    @staticmethod
    def outcome_domain(outcome):

        for domain in ("literacy", "numeracy"):
            if domain in str(outcome):
                return domain

        return "other"

    def build_analysis_plan(self):
        """
        Expand:

            variables
            x
            outcomes
            x
            registry (cumulative over designs)

        into one analysis plan dataframe, ordered by domain, round
        overviews first, then one block per variable (paired
        baseline/endline figures, then single figures).
        """

        rows = []

        designs = self.included_designs()

        registry = self.analysis_registry[
            self.analysis_registry["design"].isin(designs)
        ].copy()

        registry["_rule_order"] = range(len(registry))

        outcome_order = list(
            dict.fromkeys(registry["outcome"])
        )

        outcomes = self.get_available_outcomes()

        variables = self.get_analysis_variables()

        for outcome in outcomes:

            registry_outcome = (
                self.registry_outcome(outcome)
            )

            if registry_outcome is None:
                continue

            for var_order, var_info in enumerate(variables):

                variable = var_info["variable"]
                grouping = var_info["grouping"]

                matches = registry[
                    (
                        registry["outcome"]
                        == registry_outcome
                    )
                    &
                    (
                        registry["grouping"]
                        == grouping
                    )
                ]
                
                for _, rule in matches.iterrows():
                    visual = rule.get("vis")
                    if pd.isna(visual) or not str(visual).strip():
                        continue

                    if (
                        variable == "round"
                        and outcome in {
                            "foundational_literacy",
                            "foundational_numeracy",
                        }
                        and visual == "line"
                    ):
                        visual = "bar"

                    double_repeat = (
                        "yes"
                        if (
                            self.design != "cross_section"
                            and variable != "round"
                            and rule["design"] == "cross_section"
                            and rule.get("double_repeat") == "yes"
                            and visual in {
                                "bar", "stack_bar", "stacked_bar", "line"
                            }
                        )
                        else "no"
                    )

                    rows.append({
                        "design": rule["design"],
                        "variable": variable,
                        "grouping": grouping,
                        "domain": self.outcome_domain(outcome),
                        "outcome": outcome,
                        "registry_outcome": registry_outcome,
                        "change": rule.get("change"),
                        "interaction": rule.get("interaction"),
                        "vis": visual,
                        "double_repeat": double_repeat,
                        "model": rule.get("model"),
                        "stat": rule.get("stat"),
                        "symbol": rule.get("symbol"),
                        "n_unique": var_info["n_unique"],
                        "enabled": True,
                        "_domain_order": (
                            ["literacy", "numeracy"].index(
                                self.outcome_domain(outcome)
                            )
                            if self.outcome_domain(outcome)
                            in ("literacy", "numeracy")
                            else 2
                        ),
                        "_top_priority": (
                            0 if variable == "round" else 1
                        ),
                        "_double_rank": (
                            0 if double_repeat == "yes" else 1
                        ),
                        "_outcome_order": outcome_order.index(
                            registry_outcome
                        ),
                        "_variable_order": var_order,
                        "_rule_order": rule["_rule_order"],
                    })

        if len(rows) == 0:

            return pd.DataFrame(columns=self.PLAN_COLUMNS)

        plan = pd.DataFrame(rows)

        plan = (
            plan.sort_values(
                [
                    "_domain_order",
                    "_top_priority",
                    "_variable_order",
                    "_double_rank",
                    "_outcome_order",
                    "_rule_order",
                ],
                kind="stable",
            )
            .drop(columns=[
                "_top_priority",
                "_domain_order",
                "_double_rank",
                "_outcome_order",
                "_variable_order",
                "_rule_order",
            ])
            .reset_index(drop=True)
        )

        return plan
