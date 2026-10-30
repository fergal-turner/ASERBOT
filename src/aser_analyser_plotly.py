import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

PALETTE = [
    "#da291c", "#00B2A9", "#45b283", "#ae90c3",
    "#fecf28", "#ed7b73", "#66CCC6", "#8dd3b5",
]
BG = "#F5F5F5"
PLOT_BG = "#EEEEEE"
TEXT = "#1F1F1F"


class ASER_Analyser_Plotly:
    """Plotly version of ASER_Analyser: methods return figures, nothing is saved."""

    def __init__(
        self,
        df,
        metadata,
        reading_col="literacy_level",
        numeracy_col="numeracy_level",
    ):
        self.df = df.copy()
        self.metadata = metadata
        self.reading_col = reading_col
        self.numeracy_col = numeracy_col

    # =====================================================
    # ANALYSIS TYPE / VARIABLES (same logic as matplotlib version)
    # =====================================================

    def detect_analysis_type(self):
        if "round" not in self.df.columns:
            return "cross_section"

        if "uid" not in self.df.columns:
            return "repeated_cross_section"

        rounds_per_child = self.df.groupby("uid")["round"].nunique()

        if rounds_per_child.max() > 1:
            return "repeated_measures"

        return "repeated_cross_section"

    @staticmethod
    def title_text(text):
        return str(text).replace("_", " ").title()

    def get_analysis_variables(self):
        variables = []

        for var, meta in self.metadata.items():
            if var not in self.df.columns:
                continue

            if meta.get("role") != "disaggregation":
                continue

            n_unique = self.df[var].nunique(dropna=True)

            if n_unique <= 1:
                continue

            variables.append((var, meta, n_unique))

        return variables

    def chart_type(self, variable, meta, n_unique):
        if meta["type"] == "continuous":
            return "grouped_lineplot"

        if meta["type"] == "categorical":
            return "stacked_bar" if n_unique <= 10 else "heatmap"

        if meta["type"] == "ordinal":
            return "heatmap" if n_unique <= 10 else "lineplot"

    # =====================================================
    # HELPERS
    # =====================================================

    def _style(self, fig, title, height=450):
        fig.update_layout(
            title=dict(text=title, x=0.01),
            paper_bgcolor=BG,
            plot_bgcolor=PLOT_BG,
            font=dict(family="Segoe UI, Arial, sans-serif", color=TEXT),
            colorway=PALETTE,
            height=height,
            margin=dict(l=60, r=30, t=70, b=60),
            legend=dict(title=None),
        )
        fig.update_xaxes(showgrid=False, zeroline=False)
        fig.update_yaxes(showgrid=True, gridcolor=BG, zeroline=False)
        return fig

    @staticmethod
    def _prop_table(df, variable, outcome):
        return pd.crosstab(df[variable], df[outcome], normalize="index")

    @staticmethod
    def _sorted_labels(values):
        try:
            return sorted(values)
        except TypeError:
            return sorted(values, key=str)

    def _level_colour(self, i):
        return PALETTE[i % len(PALETTE)]

    # =====================================================
    # TRACE BUILDERS (used by single and comparison figures)
    # =====================================================

    def _stacked_bar_traces(self, df, variable, outcome, show_legend=True):
        tab = self._prop_table(df, variable, outcome)
        x = [self.title_text(i) for i in tab.index]

        return [
            go.Bar(
                x=x,
                y=tab[level],
                name=str(level),
                legendgroup=str(level),
                showlegend=show_legend,
                marker_color=self._level_colour(i),
                hovertemplate="%{x}<br>Level " + str(level) + ": %{y:.1%}<extra></extra>",
            )
            for i, level in enumerate(tab.columns)
        ]

    def _heatmap_trace(self, df, variable, outcome, show_scale=True, **kwargs):
        tab = self._prop_table(df, variable, outcome)

        return go.Heatmap(
            z=tab.values,
            x=[str(c) for c in tab.columns],
            y=[str(i) for i in tab.index],
            colorscale="Blues",
            showscale=show_scale,
            colorbar=dict(title="Proportion"),
            hovertemplate=f"{self.title_text(variable)}: %{{y}}<br>Level %{{x}}: %{{z:.1%}}<extra></extra>",
            **kwargs,
        )

    def _line_trace(self, df, variable, outcome, numeric=False, show_legend=False):
        df = df.copy()
        if numeric:
            df[variable] = pd.to_numeric(df[variable], errors="coerce")

        summary = df.groupby(variable)[outcome].mean().reset_index().sort_values(variable)

        return go.Scatter(
            x=summary[variable],
            y=summary[outcome],
            mode="lines+markers",
            line=dict(color=PALETTE[0]),
            showlegend=show_legend,
            name=f"Mean {self.title_text(outcome)}",
        )

    def _box_trace(self, df, variable, outcome, show_legend=False):
        return go.Box(
            x=df[outcome],
            y=df[variable].astype(str),
            orientation="h",
            marker_color=PALETTE[1],
            showlegend=show_legend,
        )

    def _traces(self, chart, df, variable, outcome, first=True):
        if chart == "stacked_bar":
            return self._stacked_bar_traces(df, variable, outcome, show_legend=first)
        if chart == "heatmap":
            return [self._heatmap_trace(df, variable, outcome, show_scale=first)]
        if chart == "grouped_lineplot":
            return [self._line_trace(df, variable, outcome, numeric=True)]
        if chart == "lineplot":
            return [self._line_trace(df, variable, outcome)]
        if chart == "boxplot":
            return [self._box_trace(df, variable, outcome)]
        return []

    def _y_title(self, chart, outcome):
        if chart == "stacked_bar":
            return "Proportion"
        if chart in ("grouped_lineplot", "lineplot"):
            return f"Mean {self.title_text(outcome)}"
        return None

    # =====================================================
    # SINGLE CHARTS
    # =====================================================

    def single_figure(self, chart, df, variable, outcome, title):
        fig = go.Figure()

        for trace in self._traces(chart, df, variable, outcome):
            fig.add_trace(trace)

        if chart == "stacked_bar":
            fig.update_layout(barmode="stack")
            fig.update_yaxes(tickformat=".0%")

        y_title = self._y_title(chart, outcome)
        if y_title:
            fig.update_yaxes(title_text=y_title)

        fig.update_xaxes(title_text=self.title_text(variable))

        return self._style(fig, title)

    def round_distribution(self, outcome):
        tab = pd.crosstab(self.df["round"], self.df[outcome], normalize="index")

        fig = go.Figure(
            [
                go.Bar(
                    x=[str(r) for r in tab.index],
                    y=tab[level],
                    name=str(level),
                    marker_color=self._level_colour(i),
                    hovertemplate="%{x}<br>Level " + str(level) + ": %{y:.1%}<extra></extra>",
                )
                for i, level in enumerate(tab.columns)
            ]
        )
        fig.update_layout(barmode="stack")
        fig.update_yaxes(title_text="Proportion", tickformat=".0%")

        return self._style(
            fig, f"Round Distribution: {self.title_text(outcome)}"
        )

    # =====================================================
    # REPEATED CROSS SECTION CHARTS
    # =====================================================

    def _baseline_endline(self):
        rounds = sorted(self.df["round"].dropna().unique())
        return rounds[0], rounds[-1]

    def comparison_figure(self, variable, outcome, chart):
        baseline, endline = self._baseline_endline()

        base_df = self.df[self.df["round"] == baseline]
        end_df = self.df[self.df["round"] == endline]

        fig = make_subplots(
            rows=1,
            cols=2,
            subplot_titles=(f"Baseline ({baseline})", f"Endline ({endline})"),
            shared_yaxes=True,
        )

        for col, data in enumerate([base_df, end_df], start=1):
            for trace in self._traces(chart, data, variable, outcome, first=(col == 1)):
                fig.add_trace(trace, row=1, col=col)

        if chart == "stacked_bar":
            fig.update_layout(barmode="stack")
            fig.update_yaxes(tickformat=".0%")

        y_title = self._y_title(chart, outcome)
        if y_title:
            fig.update_yaxes(title_text=y_title, row=1, col=1)

        # Share one colour scale across the two heatmaps
        if chart == "heatmap":
            fig.update_traces(zmin=0, zmax=1)

        title = f"{self.title_text(variable)}: {self.title_text(outcome)}"
        return self._style(fig, title, height=450)

    def difference_heatmap(self, variable, outcome):
        baseline, endline = self._baseline_endline()

        def table(round_value):
            sub = self.df[self.df["round"] == round_value]
            return pd.crosstab(sub[variable], sub[outcome], normalize="index")

        base = table(baseline)
        end = table(endline)

        diff = end.fillna(0).reindex_like(base).fillna(0) - base.fillna(0)
        limit = max(abs(diff.values).max(), 1e-9)

        fig = go.Figure(
            go.Heatmap(
                z=diff.values,
                x=[str(c) for c in diff.columns],
                y=[str(i) for i in diff.index],
                colorscale="RdBu_r",
                zmid=0,
                zmin=-limit,
                zmax=limit,
                colorbar=dict(title="Change"),
                hovertemplate="%{y}<br>Level %{x}: %{z:+.1%}<extra></extra>",
            )
        )
        fig.update_xaxes(title_text="Level")

        return self._style(
            fig,
            f"{self.title_text(variable)}: Distribution Change "
            f"({self.title_text(outcome)})",
        )

    def highest_attainment_lines(self, variable, outcome):
        highest = self.df[outcome].max()

        summary = (
            self.df.assign(highest=lambda x: (x[outcome] == highest).astype(int))
            .groupby([variable, "round"])["highest"]
            .mean()
            .reset_index()
        )

        fig = go.Figure()
        for i, (group, g) in enumerate(summary.groupby(variable)):
            g = g.sort_values("round")
            fig.add_trace(
                go.Scatter(
                    x=[str(r) for r in g["round"]],
                    y=g["highest"],
                    mode="lines+markers",
                    name=str(group),
                    line=dict(color=self._level_colour(i)),
                )
            )

        fig.update_yaxes(title_text="Proportion at Highest Level", tickformat=".0%")
        fig.update_xaxes(title_text="Round")

        return self._style(
            fig,
            f"{self.title_text(variable)}: Highest Level "
            f"({self.title_text(outcome)})",
        )

    def change_ranking_plot(self, variable, outcome):
        baseline, endline = self._baseline_endline()

        def means(round_value):
            sub = self.df[self.df["round"] == round_value]
            return sub.groupby(variable)[outcome].mean()

        change = (means(endline) - means(baseline)).dropna().sort_values()

        fig = go.Figure(
            go.Bar(
                x=change.values,
                y=[str(i) for i in change.index],
                orientation="h",
                marker_color=PALETTE[1],
            )
        )
        fig.update_xaxes(title_text="Change in Mean Level")

        return self._style(
            fig,
            f"{self.title_text(variable)}: Change in Mean "
            f"{self.title_text(outcome)}",
            height=max(450, 22 * len(change) + 150),
        )

    # =====================================================
    # RUNNERS - return list of {"section", "title", "figure"}
    # =====================================================

    @property
    def _outcomes(self):
        return [self.reading_col, self.numeracy_col]

    @staticmethod
    def _item(section, title, fig):
        return {"section": section, "title": title, "figure": fig}

    def run_cross_section_analysis(self):
        results = []

        for outcome in self._outcomes:
            if outcome not in self.df.columns:
                continue

            section = self.title_text(outcome)

            for variable, meta, n_unique in self.get_analysis_variables():
                chart = self.chart_type(variable, meta, n_unique)
                title = f"{self.title_text(variable)}: {self.title_text(outcome)}"

                results.append(
                    self._item(
                        section,
                        title,
                        self.single_figure(chart, self.df, variable, outcome, title),
                    )
                )

        return results

    def run_repeated_cross_section_analysis(self):
        results = []

        for outcome in self._outcomes:
            if outcome not in self.df.columns:
                continue

            section = self.title_text(outcome)

            results.append(
                self._item(
                    section,
                    f"Round Distribution: {section}",
                    self.round_distribution(outcome),
                )
            )

            for variable, meta, n_unique in self.get_analysis_variables():
                chart = self.chart_type(variable, meta, n_unique)
                label = self.title_text(variable)

                results.append(
                    self._item(
                        section,
                        f"{label}: Baseline vs Endline",
                        self.comparison_figure(variable, outcome, chart),
                    )
                )

                if meta["type"] in ["categorical", "ordinal"] and n_unique <= 5:
                    results.append(
                        self._item(
                            section,
                            f"{label}: Distribution Change",
                            self.difference_heatmap(variable, outcome),
                        )
                    )
                    results.append(
                        self._item(
                            section,
                            f"{label}: Highest Level",
                            self.highest_attainment_lines(variable, outcome),
                        )
                    )

                elif meta["type"] == "categorical" and n_unique > 5:
                    results.append(
                        self._item(
                            section,
                            f"{label}: Change in Mean Level",
                            self.change_ranking_plot(variable, outcome),
                        )
                    )

        return results

    def run(self):
        analysis_type = self.detect_analysis_type()

        if analysis_type == "cross_section":
            return self.run_cross_section_analysis()

        if analysis_type == "repeated_cross_section":
            return self.run_repeated_cross_section_analysis()

        return []
