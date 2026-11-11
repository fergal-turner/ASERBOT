import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

COLOURS = {
    "dark_red": "#a61b14",
    "red": "#da291c",
    "medium_red": "#ed7b73",
    "light_red": "#f9d3d0",

    "dark_purple": "#7e5aa6",
    "purple": "#ae90c3",
    "medium_purple": "#cebcdb",
    "light_purple": "#efe9f3",

    "dark_yellow": "#c9a300",
    "yellow": "#F2A900",
    "medium_yellow": "#ffeca9",
    "light_yellow": "#fff5d4",

    "dark_blue": "#007f79",
    "blue": "#009CA6",
    "medium_blue": "#66CCC6",
    "light_blue": "#CCEEEC",

    "dark_green": "#2f8a63",
    "green": "#45B383",
    "medium_green": "#8dd3b5",
    "light_green": "#d9f0e6",

    "orange": "#FC4C02",
    "biscuit": "#D1CCBD",
    "pink": "#F6B0BD",

    "grey_1000": "#222221",
    "grey_900": "#2B2B2B",
    "grey_700": "#666666",
    "grey_500": "#999999",
    "grey_300": "#D9D9D9",
    "grey_200": "#EEEEEE",
    "grey_100": "#F5F5F5",
}

GREENSCALE = [
    COLOURS["grey_300"],
    COLOURS["light_green"],
    COLOURS["medium_green"],
    COLOURS["green"],
    COLOURS["dark_green"],
]

PALETTE = [
    COLOURS["red"],
    COLOURS["blue"],
    COLOURS["green"],
    COLOURS["purple"],
    COLOURS["yellow"],
    COLOURS["orange"],
    COLOURS["pink"],
    COLOURS["biscuit"],
]


BG = COLOURS["grey_100"]
PLOT_BG = COLOURS["grey_200"]
TEXT = COLOURS["grey_1000"]


class ASER_Analyser_Plotly:
    """Create Plotly figures by executing each row in an analysis plan."""

    REQUIRED_PLAN_COLUMNS = {"variable", "outcome", "vis"}
    SUPPORTED_VISUALS = {
        "bar",
        "change_heatmap",
        "heatmap",
        "line",
        "line_cont",
        "lines",
        "paired_stack_bar",
        "scatter",
        "scatters",
        "stack_bar",
        "stacked_bar",
    }

    def __init__(
        self,
        df,
        analysis_plan,
        statistics=False,
        statistics_results=None,
    ):
        self.df = df.copy()
        if not isinstance(analysis_plan, pd.DataFrame):
            raise TypeError("analysis_plan must be a pandas DataFrame.")

        missing_columns = self.REQUIRED_PLAN_COLUMNS.difference(
            analysis_plan.columns
        )
        if missing_columns:
            raise ValueError(
                "Analysis plan is missing required columns: "
                + ", ".join(sorted(missing_columns))
            )

        self.analysis_plan = analysis_plan.copy()
        self.statistics = statistics
        if statistics and not isinstance(statistics_results, pd.DataFrame):
            raise TypeError(
                "statistics_results must be a pandas DataFrame when "
                "statistics=True."
            )
        self.statistics_results = (
            statistics_results.copy()
            if statistics_results is not None
            else pd.DataFrame()
        )

    @staticmethod
    def title_text(text):
        return str(text).replace("_", " ").title()

    @staticmethod
    def _is_missing(value):
        return value is None or pd.isna(value)

    @staticmethod
    def _style(fig, title, height=450):
        fig.update_layout(
            title=dict(text=title, x=0.01),
            paper_bgcolor=BG,
            plot_bgcolor=PLOT_BG,
            font=dict(family="Segoe UI, Arial, sans-serif", color=TEXT),
            colorway=PALETTE,
            height=height,
            margin=dict(l=42, r=18, t=55, b=42),
            legend=dict(title=None),
        )
        fig.update_xaxes(showgrid=False, zeroline=False)
        fig.update_yaxes(showgrid=True, gridcolor=BG, zeroline=False)
        return fig

    def _summary(self, df, variable, outcome, grouping):
        data = df[[variable, outcome]].copy()
        data[outcome] = pd.to_numeric(data[outcome], errors="coerce")
        data = data.dropna(subset=[outcome])

        if grouping == "cont":
            data[variable] = pd.to_numeric(data[variable], errors="coerce")
            data = data.dropna(subset=[variable])

        summary = (
            data.groupby(variable, dropna=False, sort=False, observed=True)[outcome]
            .mean()
            .reset_index()
        )
        if grouping == "cont":
            summary = summary.sort_values(variable)

        return summary

    def _stack_bar(self, row, df):
        variable = row["variable"]
        outcome = row["outcome"]
        table = pd.crosstab(
            df[variable],
            df[outcome],
            normalize="index",
            dropna=False,
        )
        fig = go.Figure()

        for index, level in enumerate(table.columns):
            color_index = (
                round(index * (len(GREENSCALE) - 1) / (len(table.columns) - 1))
                if len(table.columns) > 1
                else 0
            )
            fig.add_trace(go.Bar(
                x=[str(value) for value in table.index],
                y=table[level],
                name=str(level),
                marker_color=GREENSCALE[color_index],
                hovertemplate=(
                    "%{x}<br>"
                    f"{self.title_text(outcome)} {level}: "
                    "%{y:.1%}<extra></extra>"
                ),
            ))

        fig.update_layout(barmode="stack")
        fig.update_yaxes(title_text="Proportion", tickformat=".0%")
        fig.update_xaxes(title_text=self.title_text(variable))
        return fig

    @staticmethod
    def _comparison_rounds(df):
        rounds = df["round"].dropna().drop_duplicates().tolist()
        if len(rounds) < 2:
            raise ValueError(
                "The repeated-cross-section comparison visuals require "
                "at least two rounds."
            )
        return rounds[0], rounds[-1]



    def _change_heatmap(self, row, df):
        variable = row["variable"]
        outcome = row["outcome"]
        baseline, endline = self._comparison_rounds(df)
        categories = df[variable].dropna().drop_duplicates().tolist()
        levels = sorted(df[outcome].dropna().unique())

        def distribution(round_value):
            round_df = df.loc[df["round"] == round_value]
            return pd.crosstab(
                round_df[variable],
                round_df[outcome],
                normalize="index",
                dropna=False,
            ).reindex(index=categories, columns=levels, fill_value=0)

        change = distribution(endline) - distribution(baseline)
        limit = max(float(change.abs().to_numpy().max()), 0.01)
        fig = go.Figure(go.Heatmap(
            z=change.to_numpy(),
            x=[str(value) for value in levels],
            y=[str(value) for value in categories],
            colorscale=GREENSCALE,
            zmin=-limit,
            zmax=limit,
            zmid=0,
            colorbar=dict(title="Change in proportion"),
            hovertemplate=(
                f"{self.title_text(variable)}: %{{y}}<br>"
                f"{self.title_text(outcome)}: %{{x}}<br>"
                "Change in proportion: %{z:+.1%}<extra></extra>"
            ),
        ))
        fig.update_xaxes(title_text=self.title_text(outcome))
        fig.update_yaxes(title_text=self.title_text(variable))
        return fig

    def _bar(self, row, df):
        variable = row["variable"]
        outcome = row["outcome"]
        summary = self._summary(
            df, variable, outcome, row.get("grouping")
        )
        binary = set(
            pd.to_numeric(df[outcome], errors="coerce").dropna().unique()
        ).issubset({0, 1})

        fig = go.Figure(go.Bar(
            x=[str(value) for value in summary[variable]],
            y=summary[outcome],
            marker_color=PALETTE[1],
            hovertemplate="%{x}<br>Mean: %{y:.3f}<extra></extra>",
        ))
        fig.update_xaxes(title_text=self.title_text(variable))
        fig.update_yaxes(
            title_text="Proportion" if binary else f"Mean {self.title_text(outcome)}",
            tickformat=".0%" if binary else None, range=[0, 1]
        )
        return fig

    def _line(self, row, df):
        variable = row["variable"]
        outcome = row["outcome"]
        summary = self._summary(
            df, variable, outcome, row.get("grouping")
        )
        x_values = summary[variable]
        if row.get("grouping") != "cont":
            x_values = x_values.astype(str)

        binary = set(
            pd.to_numeric(df[outcome], errors="coerce").dropna().unique()
        ).issubset({0, 1})
        fig = go.Figure(go.Scatter(
            x=x_values,
            y=summary[outcome],
            mode="lines+markers",
            line=dict(color=PALETTE[0]),
            name=self.title_text(outcome),
            hovertemplate="%{x}<br>Mean: %{y:.3f}<extra></extra>",
        ))
        fig.update_xaxes(title_text=self.title_text(variable))
        fig.update_yaxes(
            title_text=(
                "Proportion" if binary
                else f"Mean {self.title_text(outcome)}"
            ),
            tickformat=".0%" if binary else None,
        )
        return fig

    def _scatter(self, row, df):
        variable = row["variable"]
        outcome = row["outcome"]
        summary = self._summary(
            df, variable, outcome, row.get("grouping")
        )
        x_values = summary[variable]
        if row.get("grouping") != "cont":
            x_values = x_values.astype(str)

        fig = go.Figure(go.Scatter(
            x=x_values,
            y=summary[outcome],
            mode="markers",
            marker=dict(color=PALETTE[2], size=9),
            name=self.title_text(outcome),
            hovertemplate="%{x}<br>Mean: %{y:.3f}<extra></extra>",
        ))
        fig.update_xaxes(title_text=self.title_text(variable))
        fig.update_yaxes(title_text=f"Mean {self.title_text(outcome)}")
        return fig

    def _scatters(self, row, df):
        """Layered dot plot: categories on x, one marker series per round."""
        variable = row["variable"]
        outcome = row["outcome"]
        if "round" not in df.columns:
            raise ValueError(
                "The 'scatters' visual requires a round column."
            )

        data = df[[variable, "round", outcome]].copy()
        data[outcome] = pd.to_numeric(data[outcome], errors="coerce")
        data = data.dropna(subset=[outcome, "round", variable])

        summary = (
            data.groupby(["round", variable], sort=False, observed=True)[
                outcome
            ]
            .mean()
            .reset_index()
        )
        categories = [
            str(value) for value in data[variable].drop_duplicates()
        ]
        fig = go.Figure()

        for index, round_value in enumerate(data["round"].drop_duplicates()):
            round_data = summary[summary["round"] == round_value]
            fig.add_trace(go.Scatter(
                x=[str(value) for value in round_data[variable]],
                y=round_data[outcome],
                mode="markers",
                name=f"{round_value}",
                marker=dict(
                    color=PALETTE[index % len(PALETTE)],
                    size=12,
                    line=dict(color="white", width=1),
                ),
                hovertemplate=(
                    f"{self.title_text(variable)}: %{{x}}<br>"
                    f"{round_value}: %{{y:.1%}}<extra></extra>"
                ),
            ))

        fig.update_xaxes(
            title_text=self.title_text(variable),
            categoryorder="array",
            categoryarray=categories,
        )
        if outcome in {"foundational_literacy", "foundational_numeracy"}:
            fig.update_yaxes(
                title_text="Proportion at highest assessment level",
                tickformat=".0%",
                range=[0, 1],
            )
        else:
            fig.update_yaxes(title_text=f"Mean {self.title_text(outcome)}")
        return fig

    def _lines(self, row, df):
        variable = row["variable"]
        outcome = row["outcome"]
        if "round" not in df.columns:
            raise ValueError(
                "The 'lines' visual requires a round column."
            )

        data = df[[variable, "round", outcome]].copy()
        data[outcome] = pd.to_numeric(data[outcome], errors="coerce")
        data = data.dropna(subset=[outcome, "round"])
        if row.get("grouping") == "cont":
            data[variable] = pd.to_numeric(data[variable], errors="coerce")
            data = data.dropna(subset=[variable])

        summary = (
            data.groupby(
                [variable, "round"],
                dropna=False,
                sort=False,
                observed=True,
            )[outcome]
            .mean()
            .reset_index()
        )
        fig = go.Figure()

        for index, (group, group_data) in enumerate(
            summary.groupby(variable, sort=False, dropna=False, observed=True)
        ):
            group_data = group_data.set_index("round").reindex(
                data["round"].drop_duplicates()
            )
            fig.add_trace(go.Scatter(
                x=[str(value) for value in group_data.index],
                y=group_data[outcome],
                mode="lines+markers",
                name=str(group),
                line=dict(color=PALETTE[index % len(PALETTE)]),
                connectgaps=False,
            ))

        fig.update_xaxes(title_text="Round")
        if outcome in {"foundational_literacy", "foundational_numeracy"}:
            fig.update_yaxes(
                title_text="Proportion at highest assessment level",
                tickformat=".0%",
                range=[0, 1],
            )
        else:
            fig.update_yaxes(title_text=f"Mean {self.title_text(outcome)}")
        return fig

    def _line_cont(self, row, df):
        variable = row["variable"]
        outcome = row["outcome"]
        if "round" not in df.columns:
            raise ValueError(
                "The 'line_cont' visual requires a round column."
            )

        data = df[[variable, "round", outcome]].copy()
        data[outcome] = pd.to_numeric(data[outcome], errors="coerce")
        data[variable] = pd.to_numeric(data[variable], errors="coerce")
        data = data.dropna(subset=[outcome, variable, "round"])

        summary = (
            data.groupby(["round", variable], observed=True)[outcome]
            .mean()
            .reset_index()
            .sort_values(variable)
        )
        fig = go.Figure()

        for index, round_value in enumerate(
            data["round"].drop_duplicates()
        ):
            round_data = summary[summary["round"] == round_value]
            fig.add_trace(go.Scatter(
                x=round_data[variable],
                y=round_data[outcome],
                mode="lines+markers",
                name=f"Round {round_value}",
                line=dict(color=PALETTE[index % len(PALETTE)]),
                hovertemplate=(
                    f"{self.title_text(variable)}: %{{x}}<br>"
                    f"Round {round_value}: %{{y:.3f}}<extra></extra>"
                ),
            ))

        fig.update_xaxes(title_text=self.title_text(variable))
        if outcome in {"foundational_literacy", "foundational_numeracy"}:
            fig.update_yaxes(
                title_text="Proportion at highest assessment level",
                tickformat=".0%",
                range=[0, 1],
            )
        else:
            fig.update_yaxes(title_text=f"Mean {self.title_text(outcome)}")
        return fig

    def _heatmap(self, row, df):
        if row.get("registry_outcome") == "levels":
            return self._change_heatmap(row, df)

        variable = row["variable"]
        outcome = row["outcome"]
        if "round" not in df.columns:
            raise ValueError(
                "The 'heatmap' visual requires a round column."
            )

        data = df[[variable, "round", outcome]].copy()
        data[outcome] = pd.to_numeric(data[outcome], errors="coerce")
        data = data.dropna(subset=[outcome, "round"])
        if row.get("grouping") == "cont":
            data[variable] = pd.to_numeric(data[variable], errors="coerce")
            data = data.dropna(subset=[variable])

        table = data.pivot_table(
            index=variable,
            columns="round",
            values=outcome,
            aggfunc="mean",
            sort=False,
        )
        fig = go.Figure(go.Heatmap(
            z=table.values,
            x=[str(value) for value in table.columns],
            y=[str(value) for value in table.index],
            colorscale=GREENSCALE,
            colorbar=dict(title=self.title_text(outcome)),
            hovertemplate=(
                f"{self.title_text(variable)}: %{{y}}<br>"
                "Round: %{x}<br>"
                f"Mean {self.title_text(outcome)}: %{{z:.2f}}"
                "<extra></extra>"
            ),
        ))
        fig.update_xaxes(title_text="Round")
        fig.update_yaxes(title_text=self.title_text(variable))
        return fig

    def _double_builder(self, row, df):
        baseline, endline = self._comparison_rounds(df)

        visual = str(row["vis"]).strip().lower()
        if visual == "paired_stack_bar":
            visual = "stack_bar"

        builder_lookup = {
            "bar": self._bar,
            "stack_bar": self._stack_bar,
            "stacked_bar": self._stack_bar,
            "line": self._line,
        }

        builder = builder_lookup[visual]

        fig = make_subplots(
            rows=1,
            cols=2,
            shared_yaxes=True,
            subplot_titles=(
                f"Baseline ({baseline})",
                f"Endline ({endline})",
            ),
        )

        for col, round_value in enumerate([baseline, endline], start=1):

            round_df = df[df["round"] == round_value]

            single_fig = builder(row, round_df)

            for trace in single_fig.data:
                if hasattr(trace, "showlegend"):
                    trace.showlegend = (col == 1)
                fig.add_trace(trace, row=1, col=col)

        if visual in {"stack_bar", "stacked_bar"}:
            fig.update_layout(barmode="stack")

        fig.update_xaxes(
            title_text=self.title_text(row["variable"]),
            row=1,
            col=1,
        )
        fig.update_xaxes(
            title_text=self.title_text(row["variable"]),
            row=1,
            col=2,
        )

        fig.update_yaxes(row=1, col=1)

        return fig

    def _build_figure(self, row):
        variable = row["variable"]
        outcome = row["outcome"]
        double_repeat = str(row.get("double_repeat", "no")).strip().lower()
        visual = str(row["vis"]).strip().lower()
        data = self.df

        if variable not in data.columns:
            raise ValueError(
                f"Analysis plan variable '{variable}' is not in the dataset."
            )
        if outcome not in data.columns:
            raise ValueError(
                f"Analysis plan outcome '{outcome}' is not in the dataset."
            )

        builders = {
            "bar": self._bar,
            "change_heatmap": self._change_heatmap,
            "heatmap": self._heatmap,
            "line": self._line,
            "line_cont": self._line_cont,
            "lines": self._lines,
            "paired_stack_bar": self._stack_bar,
            "scatter": self._scatter,
            "scatters": self._scatters,
            "stack_bar": self._stack_bar,
            "stacked_bar": self._stack_bar,
        }

        try:
            builder = builders[visual]
        except KeyError as exc:
            raise ValueError(
                f"Unsupported visualisation '{visual}' in analysis plan."
            ) from exc

        if double_repeat == "yes" or visual == "paired_stack_bar":
            figure = self._double_builder(row, data)
        else:
            figure = builder(row, data)
        title = (
            f"{self.title_text(outcome)} by "
            f"{self.title_text(variable)}"
        )
        return self._style(figure, title)

    def _statistic_note(self, plan_row):
        if not self.statistics or "symbol" not in plan_row:
            return None

        matches = self.statistics_results
        for column in ("variable", "outcome"):
            if column not in matches.columns:
                raise ValueError(
                    "Statistics results must contain 'variable' and "
                    "'outcome' columns."
                )
            matches = matches[matches[column] == plan_row[column]]

        if "design" in matches.columns and "design" in plan_row:
            matches = matches[matches["design"] == plan_row["design"]]

        if matches.empty:
            return None
        if len(matches) > 1:
            raise ValueError(
                "Statistics results contain multiple estimates for "
                f"{plan_row['variable']} and {plan_row['outcome']}."
            )

        result = matches.iloc[0]
        value = result.get("value")
        passed = result.get("passed")
        if (
            pd.isna(value)
            or (
                not self._is_missing(passed)
                and not bool(passed)
            )
        ):
            return None

        stat_name = str(result.get("stat", "")).strip().lower()
        is_lr = stat_name == "lr"

        symbol = plan_row["symbol"]
        if is_lr:
            symbol = "LR \u03c7\u00b2"
        elif self._is_missing(symbol) or not str(symbol).strip():
            return None

        symbol_text = str(symbol).strip()
        p_value = pd.to_numeric(
            pd.Series([result.get("p_value")]),
            errors="coerce",
        ).iloc[0]
        significant = pd.notna(p_value) and p_value < 0.05
        p_text = (
            "p < .001" if pd.notna(p_value) and p_value < 0.001
            else f"p = {p_value:.3f}" if pd.notna(p_value)
            else None
        )

        if is_lr:
            degrees = pd.to_numeric(
                pd.Series([result.get("df")]), errors="coerce"
            ).iloc[0]
            df_text = f"({int(degrees)})" if pd.notna(degrees) else ""
            headline = (
                f"{symbol_text}{df_text} = {float(value):.2f}"
                + (f", {p_text}" if p_text else "")
            )
        else:
            headline = f"{symbol_text} = {float(value):.2f}"

        lines = [f"<b>{headline}{'*' if significant else ''}</b>"]
        lines.append(self._statistic_description(plan_row, result))

        details = []
        lower = pd.to_numeric(
            pd.Series([result.get("lower_ci")]), errors="coerce"
        ).iloc[0]
        upper = pd.to_numeric(
            pd.Series([result.get("upper_ci")]), errors="coerce"
        ).iloc[0]
        if pd.notna(lower) and pd.notna(upper):
            details.append(f"95% CI {lower:.2f}\u2013{upper:.2f}")
        if p_text and not is_lr:
            details.append(p_text)
        n_value = pd.to_numeric(
            pd.Series([result.get("n")]), errors="coerce"
        ).iloc[0]
        if pd.notna(n_value):
            details.append(f"n = {int(n_value):,}")
        if details:
            lines.append(", ".join(details))
        if significant:
            lines.append("* significant at p < .05")

        return "<br>".join(lines)

    def _statistic_description(self, plan_row, result):
        """Plain-language description of the estimate being shown."""
        outcome = self.title_text(plan_row["outcome"]).lower()
        variable = self.title_text(plan_row["variable"]).lower()
        model = str(result.get("model", plan_row.get("model", ""))).strip()
        contrast = result.get("contrast")
        contrast = (
            None if self._is_missing(contrast) else str(contrast).strip()
        )

        if str(result.get("stat", "")).strip().lower() == "lr":
            return (
                f"Overall association between {variable} and {outcome} "
                "(likelihood-ratio test across all categories)"
            )

        if model == "variance_explained":
            return (
                f"Share of variation in {outcome} explained by "
                f"{variable} (\u03b7\u00b2)"
            )

        if model == "ord_logit":
            measure = f"Odds ratio of a higher {outcome}"
        elif model == "logit":
            measure = f"Odds ratio of {outcome}"
        elif model == "linear":
            measure = f"Mean difference in {outcome} (\u03b2)"
        else:
            measure = f"{outcome.capitalize()} estimate"

        if contrast and contrast.startswith("per "):
            return f"{measure}, {contrast} in {variable}"
        if contrast:
            return f"{measure}: {variable} {contrast}"
        return f"{measure} by {variable}"

    def run(self):
        """Render enabled plan rows in their original order."""
        results = []

        for row_number, (_, row) in enumerate(
            self.analysis_plan.iterrows(),
            start=1,
        ):
            if "enabled" in row and not self._is_missing(row["enabled"]):
                if not bool(row["enabled"]):
                    continue

            if self._is_missing(row["vis"]) or not str(row["vis"]).strip():
                continue

            visual = str(row["vis"]).strip().lower()
            if visual not in self.SUPPORTED_VISUALS:
                raise ValueError(
                    f"Unsupported visualisation '{visual}' on plan row "
                    f"{row_number}."
                )

            figure = self._build_figure(row)
            statistic_note = self._statistic_note(row)
            if statistic_note:
                figure.add_annotation(
                    text=statistic_note,
                    xref="paper",
                    yref="paper",
                    x=1,
                    y=0,
                    yshift=-62,
                    xanchor="right",
                    yanchor="top",
                    align="right",
                    font=dict(size=11),
                    showarrow=False,
                )
                figure.update_layout(
                    height=figure.layout.height + 100,
                    margin=dict(l=60, r=30, t=70, b=160),
                )

            outcome = row["outcome"]
            title = figure.layout.title.text
            results.append({
                "section": self.title_text(outcome),
                "title": title,
                "figure": figure,
            })

        return results
