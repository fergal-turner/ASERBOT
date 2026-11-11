"""Non-interactive smoke test: sample data -> scored -> Plotly figures."""
import sys
from pathlib import Path

import pandas as pd

from default_dictionaries import get_default_metadata_df, get_default_aser_df
from dataset_interpreter import DataInterpreter
from aser_column_matcher import ASERColumnMatcher
from aser_validator import ASERValidator
from aser_scorer import ASERScorer
from aser_analysisplanner import ASERAnalysisPlanner
from aser_analyser_plotly import ASER_Analyser_Plotly

root = Path(__file__).resolve().parent.parent
df = pd.read_csv(sys.argv[1] if len(sys.argv) > 1 else root / "Data" / "sample_data.csv")
metadata_df = get_default_metadata_df()

interp = DataInterpreter(df, metadata_df).identify_columns()
df = df.rename(columns=interp["rename_map"])

match = ASERColumnMatcher(df, get_default_aser_df()).identify_assessment_columns()
df = df.rename(columns=match["rename_map"])

metadata_columns = interp["metadata_columns"]
validation = ASERValidator(df=df, metadata={c: c for c in metadata_columns}).validate()
print("validation:", validation["dataset_ready"], validation["errors"], validation["warnings"])

if "round" not in df.columns:
    analysis_type = "cross_section"
elif "uid" not in df.columns:
    analysis_type = "repeated_cross_section"
elif df.groupby("uid")["round"].nunique().max() > 1:
    analysis_type = "repeated_measures"
else:
    analysis_type = "repeated_cross_section"

scoring_type = (
    "repeat_measures"
    if analysis_type == "repeated_measures"
    else analysis_type
)
planner_design = {
    "cross_section": "cross_section",
    "repeated_cross_section": "repeat_cross",
    "repeated_measures": "repeat_measures",
}[analysis_type]
scored = ASERScorer(
    df=df,
    metadata_columns=metadata_columns,
    analysis_type=scoring_type,
).run()["scored_df"]
assert "foundational_literacy" in scored
assert "foundational_numeracy" in scored
assert scored["foundational_literacy"].equals(
    (scored["literacy_level"] == scored["literacy_level"].max()).astype(int)
)
assert scored["foundational_numeracy"].equals(
    (scored["numeracy_level"] == scored["numeracy_level"].max()).astype(int)
)

registry = pd.read_csv(root / "Resources" / "analysis_registry.csv")
plan = ASERAnalysisPlanner(
    df=scored,
    metadata=metadata_df.rename(columns={"canonical_column": "name"}),
    analysis_registry=registry,
    design=planner_design,
).build_analysis_plan()
included = {
    "cross_section": ["cross_section"],
    "repeat_cross": ["cross_section", "repeat_cross"],
    "repeat_measures": ["cross_section", "repeat_cross", "repeat_measures"],
}[planner_design]
assert set(plan["design"]).issubset(included)
assert "cross_section" in set(plan["design"])
if planner_design != "cross_section":
    assert len(set(plan["design"])) > 1
    cross_section_plan = ASERAnalysisPlanner(
        df=scored.drop(columns=["round"]),
        metadata=metadata_df.rename(columns={"canonical_column": "name"}),
        analysis_registry=registry,
        design="cross_section",
    ).build_analysis_plan()
    assert not cross_section_plan["double_repeat"].eq("yes").any()
    cross_section_results = ASER_Analyser_Plotly(
        scored.drop(columns=["round"]),
        cross_section_plan,
    ).run()
    assert all(
        result["figure"].layout.to_plotly_json().get("xaxis2") is None
        for result in cross_section_results
    )

domains = plan["domain"].tolist()
assert domains == sorted(domains, key=["literacy", "numeracy"].index)
for _, domain_plan in plan.groupby("domain", sort=False):
    variables_in_order = domain_plan["variable"].tolist()
    assert variables_in_order == sorted(
        variables_in_order, key=list(dict.fromkeys(variables_in_order)).index
    )
    if analysis_type == "repeated_cross_section":
        assert variables_in_order[:2] == ["round", "round"]
        block = domain_plan[domain_plan["variable"].eq("sex")]
        assert block["double_repeat"].tolist()[:2] == ["yes", "yes"]
        assert set(block["double_repeat"].tolist()[2:]) == {"no"}
analyser = ASER_Analyser_Plotly(
    scored,
    plan,
)
print("type:", analysis_type)
expected_figures = plan["vis"].notna() & plan["vis"].astype(str).str.strip().ne("")
results = analyser.run()
assert len(results) == int(expected_figures.sum())
titles = {result["title"]: result["figure"] for result in results}
assert all(
    result["title"] == (
        f"{ASER_Analyser_Plotly.title_text(row['outcome'])} by "
        f"{ASER_Analyser_Plotly.title_text(row['variable'])}"
    )
    for result, (_, row) in zip(results, plan.iterrows())
)
if analysis_type == "repeated_cross_section":
    assert plan[["outcome", "variable"]].head(2).values.tolist() == [
        ["literacy_level", "round"],
        ["foundational_literacy", "round"],
    ]
    assert results[0]["title"] == "Literacy Level by Round"
    assert results[1]["title"] == "Foundational Literacy by Round"
    assert all(trace.type == "bar" for trace in results[1]["figure"].data)
    assert results[1]["figure"].layout.yaxis.tickformat == ".0%"

    paired_index = plan.index[
        plan["design"].eq("cross_section")
        & plan["variable"].eq("sex")
        & plan["outcome"].eq("literacy_level")
    ][0]
    paired_bars = results[paired_index]["figure"]
    assert paired_bars.layout.barmode == "stack"
    assert paired_bars.layout.xaxis2 is not None
    assert all(trace.type == "bar" for trace in paired_bars.data)
    level_count = scored["literacy_level"].nunique()
    assert paired_bars.data[0].marker.color == "#D9D9D9"
    assert paired_bars.data[level_count - 1].marker.color == "#2f8a63"

    paired_line_index = plan.index[
        plan["design"].eq("cross_section")
        & plan["variable"].eq("age")
        & plan["outcome"].eq("foundational_literacy")
    ][0]
    paired_lines = results[paired_line_index]["figure"]
    assert paired_lines.layout.xaxis2 is not None
    assert all(trace.type == "scatter" for trace in paired_lines.data)

    assert titles["Foundational Literacy by Sex"].data[0].type == "scatter"
    assert titles["Foundational Literacy by Sex"].layout.yaxis.tickformat == ".0%"

print(len(results), "figures")
for r in results:
    r["figure"].to_json()
    print(" -", r["section"], "|", r["title"])

if analysis_type == "repeated_cross_section":
    synthetic_plan = pd.DataFrame([
        {
            "design": "repeat_cross", "variable": "sex",
            "grouping": "cat_low", "outcome": "literacy_level",
            "registry_outcome": "levels", "change": "yes", "vis": "heatmap",
        },
        {
            "design": "repeat_cross", "variable": "age",
            "grouping": "cont", "outcome": "foundational_literacy",
            "registry_outcome": "foundational_learning", "change": "yes",
            "vis": "line_cont",
        },
        {
            "design": "repeat_cross", "variable": "sex",
            "grouping": "binary", "outcome": "foundational_literacy",
            "registry_outcome": "foundational_learning", "change": "yes",
            "vis": "scatters",
        },
    ])
    synthetic = ASER_Analyser_Plotly(scored, synthetic_plan).run()
    dots = synthetic[2]["figure"]
    assert synthetic[2]["title"] == "Foundational Literacy by Sex"
    assert len(dots.data) == scored["round"].nunique()
    assert all(
        trace.type == "scatter" and trace.mode == "markers"
        for trace in dots.data
    )
    assert dots.layout.yaxis.tickformat == ".0%"
    level_heatmap = synthetic[0]["figure"]
    assert synthetic[0]["title"] == "Literacy Level by Sex"
    assert level_heatmap.data[0].type == "heatmap"
    assert level_heatmap.data[0].colorscale[0][1] == "#D9D9D9"
    assert level_heatmap.data[0].colorscale[-1][1] == "#2f8a63"
    assert len(level_heatmap.data[0].y) == scored["sex"].nunique()
    assert len(level_heatmap.data[0].x) == scored["literacy_level"].nunique()

    age_lines = synthetic[1]["figure"]
    assert len(age_lines.data) == scored["round"].nunique()
    assert all(trace.type == "scatter" for trace in age_lines.data)
    assert [trace.name for trace in age_lines.data] == [
        f"Round {r}" for r in scored["round"].dropna().drop_duplicates()
    ]
    assert age_lines.layout.xaxis.title.text == "Age"

note_data = pd.DataFrame({
    "sex": ["female", "male"],
    "literacy_level": [1, 2],
})
note_plan = pd.DataFrame([{
    "design": "cross_section",
    "variable": "sex",
    "outcome": "literacy_level",
    "vis": "stack_bar",
    "symbol": "OR",
}])
note_results = pd.DataFrame([{
    "design": "cross_section",
    "variable": "sex",
    "outcome": "literacy_level",
    "model": "ord_logit",
    "value": 1.25,
    "lower_ci": 1.01,
    "upper_ci": 1.55,
    "p_value": 0.049,
    "n": 1200,
    "contrast": "male vs female (reference)",
    "passed": True,
}])
note_figure = ASER_Analyser_Plotly(
    note_data,
    note_plan,
    statistics=True,
    statistics_results=note_results,
).run()[0]["figure"]
note_lines = note_figure.layout.annotations[0].text.split("<br>")
assert note_lines[0] == "<b>OR = 1.25*</b>"
assert note_lines[1] == (
    "Odds ratio of a higher literacy level: sex male vs female (reference)"
)
assert note_lines[2] == "95% CI 1.01\u20131.55, p = 0.049, n = 1,200"
assert note_lines[3] == "* significant at p < .05"

lr_results = pd.DataFrame([{
    "design": "cross_section",
    "variable": "sex",
    "outcome": "literacy_level",
    "model": "ord_logit",
    "stat": "lr",
    "value": 7.314,
    "df": 2,
    "p_value": 0.0258,
    "n": 1200,
    "contrast": "overall",
    "passed": True,
}])
lr_figure = ASER_Analyser_Plotly(
    note_data,
    note_plan,
    statistics=True,
    statistics_results=lr_results,
).run()[0]["figure"]
lr_lines = lr_figure.layout.annotations[0].text.split("<br>")
assert lr_lines[0] == "<b>LR \u03c7\u00b2(2) = 7.31, p = 0.026*</b>"
assert "likelihood-ratio test" in lr_lines[1]
assert lr_lines[2] == "n = 1,200"
assert lr_lines[3] == "* significant at p < .05"

out = root / "src" / "outputs" / "preview.html"
html = "".join(r["figure"].to_html(full_html=False, include_plotlyjs=(i == 0 and "cdn")) for i, r in enumerate(results))
out.write_text(f"<html><body>{html}</body></html>", encoding="utf-8")
print("preview:", out)
