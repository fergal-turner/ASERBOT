import os

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns


class ASER_Analyser:

    def __init__(
        self,
        df,
        metadata,
        reading_col="literacy_level",
        numeracy_col="numeracy_level",
        output_dir="outputs"
    ):

        self.df = df.copy()
        self.metadata = metadata

        self.reading_col = reading_col
        self.numeracy_col = numeracy_col

        self.output_dir = output_dir

        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(f"{output_dir}/figures", exist_ok=True)

    # =====================================================
    # ANALYSIS TYPE
    # =====================================================

    def detect_analysis_type(self):

        if "round" not in self.df.columns:
            return "cross_section"

        if "uid" not in self.df.columns:
            return "repeated_cross_section"

        rounds_per_child = (
            self.df.groupby("uid")["round"]
            .nunique()
        )

        if rounds_per_child.max() > 1:
            return "repeated_measures"

        return "repeated_cross_section"

    # =====================================================
    # VARIABLE HELPERS
    # =====================================================

    @staticmethod
    def title_text(text):
        text = text.replace("_", " ")
        text = text.title()
        return text


    def get_analysis_variables(self):

        variables = []

        for var, meta in self.metadata.items():

            if var not in self.df.columns:
                continue

            if meta.get("role") != "disaggregation":
                continue

            n_unique = self.df[var].nunique(
                dropna=True
            )

            if n_unique <= 1:
                continue

            variables.append(
                (var, meta, n_unique)
            )

        return variables

    def chart_type(
        self,
        variable,
        meta,
        n_unique
    ):

        if meta["type"] == "continuous":
            return "grouped_lineplot"

        if meta["type"] == "categorical":

            if n_unique <= 10:
                return "stacked_bar"

            return "heatmap"

        if meta["type"] == "ordinal":

            if n_unique <= 10:
                return "heatmap"

            return "lineplot"

    # =====================================================
    # GENERIC CHARTS
    # =====================================================

    def stacked_bar(
        self,
        df,
        variable,
        outcome,
        ax=None
    ):

        tab = pd.crosstab(
            df[variable],
            df[outcome],
            normalize="index"
        )

        if ax is None:
            _, ax = plt.subplots()

        tab.plot(
            kind="bar",
            stacked=True,
            ax=ax,
            zorder=3
        )

        ax.set_xticklabels([self.title_text(t.get_text()) for t in ax.get_xticklabels()], rotation=0)
        ax.set_ylabel("Proportion")

    def heatmap(
        self,
        df,
        variable,
        outcome,
        ax=None
    ):

        table = pd.crosstab(
            df[variable],
            df[outcome],
            normalize="index"
        )

        if ax is None:
            _, ax = plt.subplots()

        sns.heatmap(
            table,
            cmap="Blues",
            ax=ax,
            zorder=3
        )

    def lineplot(
        self,
        df,
        variable,
        outcome,
        ax=None,
        ):

        summary = (
            df.groupby(variable)[outcome]
            .mean()
            .reset_index()
        )

        if ax is None:
            _, ax = plt.subplots()

        sns.lineplot(
            data=summary,
            x=variable,
            y=outcome,
            marker="o",
            ax=ax,
            zorder=3
        )

    def grouped_lineplot(
            self,
            df,
            variable,
            outcome,
            ax=None
        ):
            df = df.copy()
            df[variable] = pd.to_numeric(
            df[variable],
            errors="coerce"
        )

            
            summary = (
                df.groupby(variable)[outcome]
                .mean()
                .reset_index()
                .sort_values(variable)
            )

            if ax is None:
                _, ax = plt.subplots()

            sns.lineplot(
                data=summary,
                x=variable,
                y=outcome,
                marker="o",
                ax=ax
            )

            ax.set_ylabel(
                f"Mean {self.title_text(outcome)}"
            )

    def boxplot(
        self,
        df,
        variable,
        outcome,
        ax=None
    ):

        if ax is None:
            _, ax = plt.subplots()

        sns.boxplot(
            data=df,
            x=outcome,
            y=variable,
            ax=ax, 
            zorder=3
        )

    # =====================================================
    # CROSS SECTION
    # =====================================================

    def run_cross_section_analysis(self):

        outcomes = [
            self.reading_col,
            self.numeracy_col
        ]

        for outcome in outcomes:

            for (
                variable,
                meta,
                n_unique
            ) in self.get_analysis_variables():

                chart = self.chart_type(
                    variable,
                    meta,
                    n_unique
                )

                plt.figure(
                    figsize=(8, 5)
                )

                if chart == "stacked_bar":

                    self.stacked_bar(
                        self.df,
                        variable,
                        outcome
                    )

                elif chart == "heatmap":

                    self.heatmap(
                        self.df,
                        variable,
                        outcome
                    )

                elif chart == "grouped_lineplot":

                    self.grouped_lineplot(
                        self.df,
                        variable,
                        outcome
                    )

                elif chart == "lineplot":

                    self.lineplot(
                        self.df,
                        variable,
                        outcome
                    )

                elif chart == "boxplot":

                    self.boxplot(
                        self.df,
                        variable,
                        outcome
                    )

                plt.title(
                    f"{self.title_text(variable)}: {self.title_text(outcome)}"
                )

                plt.tight_layout()

                plt.savefig(
                    f"{self.output_dir}/figures/"
                    f"{outcome}_{variable}.png"
                )

                plt.close()

    # =====================================================
    # REPEATED CROSS SECTION
    # =====================================================

    def round_distribution(
        self,
        outcome
    ):

        table = pd.crosstab(
            self.df["round"],
            self.df[outcome],
            normalize="index"
        )

        ax = table.plot(
            kind="bar",
            stacked=True,
            figsize=(8, 5), 
            zorder=3
        )

        ax.set_ylabel(
            "Proportion"
        )

        plt.tight_layout()

        plt.savefig(
            f"{self.output_dir}/figures/"
            f"round_distribution_{outcome}.png"
        )

        plt.close()

    def comparison_figure(
        self,
        variable,
        outcome,
        chart_type
    ):

        rounds = sorted(
            self.df["round"].dropna().unique()
        )

        baseline = rounds[0]
        endline = rounds[-1]

        base_df = self.df[
            self.df["round"] == baseline
        ]

        end_df = self.df[
            self.df["round"] == endline
        ]

        fig, axes = plt.subplots(
            1,
            2,
            figsize=(14, 6)
        )

        if chart_type == "stacked_bar":

            self.stacked_bar(
                base_df,
                variable,
                outcome,
                axes[0]
            )

            self.stacked_bar(
                end_df,
                variable,
                outcome,
                axes[1]
            )

        elif chart_type == "heatmap":

            self.heatmap(
                base_df,
                variable,
                outcome,
                axes[0]
            )

            self.heatmap(
                end_df,
                variable,
                outcome,
                axes[1]
            )

        elif chart_type == "grouped_lineplot":

            self.grouped_lineplot(
                base_df,
                variable,
                outcome,
                axes[0]
            )

            self.grouped_lineplot(
                end_df,
                variable,
                outcome,
                axes[1]
            )

        elif chart_type == "lineplot":

            self.lineplot(
                base_df,
                variable,
                outcome,
                axes[0]
            )

            self.lineplot(
                end_df,
                variable,
                outcome,
                axes[1]
            )

        elif chart_type == "boxplot":

            self.boxplot(
                base_df,
                variable,
                outcome,
                axes[0]
            )

            self.boxplot(
                end_df,
                variable,
                outcome,
                axes[1]
            )

        axes[0].set_title(
            f"Baseline ({baseline})"
        )

        axes[1].set_title(
            f"Endline ({endline})"
        )

        plt.tight_layout()

        plt.savefig(
            f"{self.output_dir}/figures/"
            f"comparison_{outcome}_{variable}.png"
        )

        plt.close()

    def difference_heatmap(
        self,
        variable,
        outcome
    ):

        rounds = sorted(
            self.df["round"].dropna().unique()
        )

        baseline = rounds[0]
        endline = rounds[-1]

        base = pd.crosstab(
            self.df.loc[
                self.df["round"] == baseline,
                variable
            ],
            self.df.loc[
                self.df["round"] == baseline,
                outcome
            ],
            normalize="index"
        )

        end = pd.crosstab(
            self.df.loc[
                self.df["round"] == endline,
                variable
            ],
            self.df.loc[
                self.df["round"] == endline,
                outcome
            ],
            normalize="index"
        )

        diff = (
            end.fillna(0)
            .reindex_like(base)
            .fillna(0)
            - base.fillna(0)
        )

        plt.figure(figsize=(8, 5))

        sns.heatmap(
            diff,
            center=0,
            cmap="RdBu_r",
            zorder=3
        )

        plt.title(
            f"{variable}: Distribution Change"
        )

        plt.tight_layout()

        plt.savefig(
            f"{self.output_dir}/figures/"
            f"difference_{outcome}_{variable}.png"
        )

        plt.close()

    def highest_attainment_lines(
        self,
        variable,
        outcome
    ):

        highest = (
            self.df[outcome].max()
        )

        summary = (
            self.df.assign(
                highest=lambda x:
                (
                    x[outcome] == highest
                ).astype(int)
            )
            .groupby(
                [variable, "round"]
            )
            ["highest"]
            .mean()
            .reset_index()
        )

        plt.figure(figsize=(8, 5))

        sns.lineplot(
            data=summary,
            x="round",
            y="highest",
            hue=variable,
            marker="o"
        )

        plt.ylabel(
            "Proportion at Highest Level"
        )

        plt.tight_layout()

        plt.savefig(
            f"{self.output_dir}/figures/"
            f"highest_{outcome}_{variable}.png"
        )

        plt.close()

    def change_ranking_plot(
        self,
        variable,
        outcome
    ):

        rounds = sorted(
            self.df["round"].dropna().unique()
        )

        baseline = rounds[0]
        endline = rounds[-1]

        base = (
            self.df[
                self.df["round"] == baseline
            ]
            .groupby(variable)[outcome]
            .mean()
        )

        end = (
            self.df[
                self.df["round"] == endline
            ]
            .groupby(variable)[outcome]
            .mean()
        )

        change = (
            end - base
        ).sort_values()

        plt.figure(
            figsize=(8, 8)
        )

        sns.barplot(
            x=change.values,
            y=change.index
        )

        plt.xlabel(
            "Change in Mean Level"
        )

        plt.tight_layout()

        plt.savefig(
            f"{self.output_dir}/figures/"
            f"ranking_{outcome}_{variable}.png"
        )

        plt.close()

    def run_repeated_cross_section_analysis(self):

        outcomes = [
            self.reading_col,
            self.numeracy_col
        ]

        for outcome in outcomes:

            self.round_distribution(
                outcome
            )

            for (
                variable,
                meta,
                n_unique
            ) in self.get_analysis_variables():

                chart = self.chart_type(
                    variable,
                    meta,
                    n_unique
                )

                self.comparison_figure(
                    variable,
                    outcome,
                    chart
                )

                if (
                    meta["type"]
                    in ["categorical", "ordinal"]
                    and n_unique <= 5
                ):

                    self.difference_heatmap(
                        variable,
                        outcome
                    )

                    self.highest_attainment_lines(
                        variable,
                        outcome
                    )

                elif (
                    meta["type"] == "categorical"
                    and n_unique > 5
                ):

                    self.change_ranking_plot(
                        variable,
                        outcome
                    )

                # elif (
                #     meta["type"] == "ordinal"
                #     and n_unique > 10
                # ):

                #     self.highest_attainment_lines(
                #         variable,
                #         outcome
                #     )

    # =====================================================
    # ANALYSIS PLAN
    # =====================================================

    def analysis_plan(self):

        analysis_type = self.detect_analysis_type()

        plan = {
            "analysis_type": analysis_type,
            "figures": []
        }

        for outcome in [
            self.reading_col,
            self.numeracy_col
        ]:

            if analysis_type == "cross_section":

                for (
                    variable,
                    meta,
                    n_unique
                ) in self.get_analysis_variables():

                    chart = self.chart_type(
                        variable,
                        meta,
                        n_unique
                    )

                    plan["figures"].append(
                        f"{chart}: {variable} vs {outcome}"
                    )

            elif analysis_type == "repeated_cross_section":

                plan["figures"].append(
                    f"Round distribution: {outcome}"
                )

                for (
                    variable,
                    meta,
                    n_unique
                ) in self.get_analysis_variables():

                    plan["figures"].append(
                        f"Comparison figure: {variable} ({outcome})"
                    )

        return plan