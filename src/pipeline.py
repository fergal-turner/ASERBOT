# main.py

from pathlib import Path
import re

import pandas as pd


from dataset_interpreter import DataInterpreter
from aser_column_matcher import ASERColumnMatcher
from aser_validator import ASERValidator
from aser_scorer import ASERScorer
from aser_analyser_plotly import ASER_Analyser_Plotly
from aser_analysisplanner import ASERAnalysisPlanner
from default_dictionaries import *

from sc_theme import *



default_aser = get_default_aser_df()
default_metadata = get_default_metadata_df()
default_registry = get_default_statistics_registry()

# =====================================================
# HELPERS
# =====================================================

def clean_path(value):

    return str(value).strip().strip("\"'").strip()


def load_dataset(path):

    path = clean_path(path)

    if path.lower().endswith(".csv"):
        return pd.read_csv(path)

    if path.lower().endswith(".xlsx"):
        return pd.read_excel(path)

    raise ValueError(
        f"Dataset must be CSV or XLSX (got: {path!r})."
    )


def safe_filename(text):

    return re.sub(
        r"[^A-Za-z0-9]+", "_", str(text)
    ).strip("_").lower()


def yes_no(question):

    while True:

        answer = input(
            f"{question} (y/n): "
        ).strip().lower()

        if answer in ["y", "yes"]:
            return True

        if answer in ["n", "no"]:
            return False


# =====================================================
# METADATA REVIEW
# =====================================================

def review_metadata(df, interpreter_results):

    rename_map = interpreter_results["rename_map"]

    print("\n" + "=" * 60)
    print("METADATA COLUMN MATCHES")
    print("=" * 60)

    for original, canonical in rename_map.items():

        print(
            f"{original} --> {canonical}"
        )

    if not yes_no(
        "\nAccept metadata mappings?"
    ):
        raise SystemExit(
            "User cancelled process."
        )

    df.rename(
        columns=rename_map,
        inplace=True
    )

    return df


# =====================================================
# ASER REVIEW
# =====================================================

def review_aser_columns(df, matcher_results):

    rename_map = matcher_results["rename_map"]

    print("\n" + "=" * 60)
    print("ASER ASSESSMENT MATCHES")
    print("=" * 60)

    for original, canonical in rename_map.items():

        print(
            f"{original} --> {canonical}"
        )

    if matcher_results["review_required"]:

        print("\nREVIEW REQUIRED")

        for item in matcher_results[
            "review_required"
        ]:

            print(
                f"\n{item['canonical_column']}"
            )

            print(
                f"Reason: {item['reason']}"
            )

            for col in item["columns"]:

                print(
                    f"  - {col}"
                )

            selection = input(
                "\nChoose column "
                "(ENTER = skip): "
            ).strip()

            if selection:

                rename_map[
                    selection
                ] = item[
                    "canonical_column"
                ]

    if matcher_results["unmatched"]:

        print("\nNOT FOUND")

        for item in matcher_results[
            "unmatched"
        ]:

            print(
                f"  - {item['canonical_column']}"
            )

    if not yes_no(
        "\nAccept assessment mappings?"
    ):
        raise SystemExit(
            "User cancelled process."
        )

    df.rename(
        columns=rename_map,
        inplace=True
    )

    return df


# =====================================================
# VALIDATION REVIEW
# =====================================================

def review_validation(validation):

    print("\n" + "=" * 60)
    print("VALIDATION RESULTS")
    print("=" * 60)

    if validation["errors"]:

        print("\nERRORS")

        for item in validation["errors"]:

            print(f"- {item}")

    if validation["warnings"]:

        print("\nWARNINGS")

        for item in validation["warnings"]:

            print(f"- {item}")

    if not validation["dataset_ready"]:

        if not yes_no(
            "\nValidation failed. Continue anyway?"
        ):
            raise SystemExit(
                "Analysis cancelled."
            )

    elif validation["warnings"]:

        if not yes_no(
            "\nContinue despite warnings?"
        ):
            raise SystemExit(
                "Analysis cancelled."
            )


# =====================================================
# MAIN
# =====================================================

def main():

    sc_theme()

    print("\nASERBOT")
    print("=" * 60)

    data_file = clean_path(input(
        "Dataset path: "
    ))

    metadata_dictionary = clean_path(input(
        "Metadata dictionary CSV (leave blank to use default): "
    ))

    aser_dictionary = clean_path(input(
        "ASER dictionary CSV (leave blank to use default): "
    ))

    registry_input = clean_path(input(
        "Analysis registry CSV (leave blank to use default): "
    ))

    if registry_input:
        analysis_registry = pd.read_csv(registry_input)
    else:
        analysis_registry = default_registry

    stats = yes_no(
        "Run statistical analyses?"
    )

    statistics_registry = None

    if stats:
        try:
            from aser_statistics import ASERStatistics
        except ModuleNotFoundError as exc:
            if exc.name == "statsmodels":
                raise ModuleNotFoundError(
                    "Statistics require statsmodels. Install it with "
                    "`python -m pip install statsmodels`."
                ) from exc
            raise

        statistics_registry = ASERStatistics

    try:
        import kaleido  # noqa: F401
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "Exporting PNG figures requires kaleido. Install it with "
            "`python -m pip install kaleido`."
        ) from exc

    print("\nLoading dataset...")

    df = load_dataset(data_file)

    if metadata_dictionary:
        metadata_dict = pd.read_csv(
            metadata_dictionary
        )
    else:
        metadata_dict = default_metadata

    if aser_dictionary:
        aser_dict = pd.read_csv(
            aser_dictionary
        )
    else:
        aser_dict = (
            pd.DataFrame.from_dict(
                default_aser
            )
        )

    # =====================================
    # METADATA DETECTION
    # =====================================

    interpreter = DataInterpreter(
        df,
        metadata_dict
    )

    interpreter_results = (
        interpreter.identify_columns()
    )

    df = review_metadata(
        df,
        interpreter_results
    )

    metadata_columns = (
        interpreter_results[
            "metadata_columns"
        ]
    )

    print(
        "\nMetadata columns:"
    )

    for col in metadata_columns:

        print(f"  - {col}")

    # =====================================
    # ASER DETECTION
    # =====================================

    matcher = ASERColumnMatcher(
        df,
        aser_dict
    )

    matcher_results = (
        matcher.identify_assessment_columns()
    )

    df = review_aser_columns(
        df,
        matcher_results
    )

    # =====================================
    # VALIDATION
    # =====================================

    validator = ASERValidator(
        df=df,
        metadata={
            col: col
            for col in metadata_columns
        }
    )

    validation = (
        validator.validate()
    )

    review_validation(
        validation
    )

    # =====================================
    # SCORING
    # =====================================

    if "round" not in df.columns:
        analysis_type = "cross_section"
    elif "uid" not in df.columns:
        analysis_type = "repeated_cross_section"
    elif df.groupby("uid")["round"].nunique().max() > 1:
        analysis_type = "repeated_measures"
    else:
        analysis_type = "repeated_cross_section"

    scorer = ASERScorer(
        df=df,
        metadata_columns=
        metadata_columns,
        analysis_type=(
            "repeat_measures"
            if analysis_type == "repeated_measures"
            else analysis_type
        ),
    )

    scoring_results = (
        scorer.run()
    )

    scored_df = scoring_results[
        "scored_df"
    ]

    # =====================================
    # ANALYSIS PLAN
    # =====================================

    planner_design = {
        "cross_section": "cross_section",
        "repeated_cross_section": "repeat_cross",
        "repeated_measures": "repeat_measures",
    }[analysis_type]

    analysis_plan = ASERAnalysisPlanner(
        df=scored_df,
        metadata=metadata_dict.rename(
            columns={"canonical_column": "name"}
        ),
        analysis_registry=analysis_registry,
        design=planner_design,
    ).build_analysis_plan()

    output_dir = Path("outputs")
    output_dir.mkdir(parents=True, exist_ok=True)
    analysis_plan.to_csv(output_dir / "analysis_plan.csv", index=False)

    print("\nANALYSIS PLAN")
    print("=" * 60)

    print(f"\nType: {analysis_type}")

    print("\nFigures:")
    for _, plan_row in analysis_plan.iterrows():
        if pd.isna(plan_row["vis"]) or not str(plan_row["vis"]).strip():
            continue
        print(
            f"  • {plan_row['vis']}: "
            f"{plan_row['variable']} vs {plan_row['outcome']}"
        )

    proceed = input(
        "\nProceed with analysis? (y/n): "
    )

    if proceed.lower() != "y":
        print("Analysis cancelled.")
        return

    output_dir = Path("outputs")
    figure_dir = output_dir / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)

    statistics = None

    if stats:
        if analysis_type == "repeated_measures":
            raise NotImplementedError(
                "ASERStatistics does not currently account for repeated "
                "observations of the same child."
            )

        statistics_metadata = (
            analysis_plan[["variable", "grouping"]]
            .drop_duplicates()
            .rename(columns={
                "variable": "variable_name",
                "grouping": "analysis_group",
            })
        )
        statistics_runner = statistics_registry(
            metadata_df=statistics_metadata,
            registry_path=analysis_registry,
        )
        statistics = pd.concat(
            [
                statistics_runner.run(
                    df=scored_df,
                    design=plan_design,
                    outcomes=(
                        analysis_plan.loc[
                            analysis_plan["design"] == plan_design,
                            "outcome",
                        ].dropna().unique().tolist()
                    ),
                )
                for plan_design in analysis_plan["design"].unique()
            ],
            ignore_index=True,
        )

        if statistics.empty:
            raise ValueError(
                "The statistics registry contains no applicable model "
                f"rules for design '{planner_design}'."
            )

        statistics_dir = output_dir / "statistics"
        statistics_dir.mkdir(parents=True, exist_ok=True)
        statistics_file = (
            statistics_dir / "aser_statistics.csv"
        )
        statistics.to_csv(statistics_file, index=False)

        print("\nSTATISTICAL ANALYSES")
        print(f"  - {statistics_file}")

    figures = ASER_Analyser_Plotly(
        scored_df,
        analysis_plan,
        statistics=stats,
        statistics_results=statistics,
    ).run()

    print("\nFIGURES")
    for number, item in enumerate(figures, start=1):
        figure_file = figure_dir / (
            f"{number:02d}_{safe_filename(item['title'])}.png"
        )
        item["figure"].write_image(
            str(figure_file), width=1100, height=600, scale=2
        )
        print(f"  - {figure_file}")

    # =====================================
    # SAVE OUTPUTS
    # =====================================

    # output_file = (
    #     "aserbot_scored_dataset.csv"
    # )

    # scored_df.to_csv(
    #     output_file,
    #     index=False
    # )

    # =====================================
    # SUMMARY
    # =====================================

    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETE")
    print("=" * 60)

    # print(
    #     f"\nSaved:\n{output_file}"
    # )

    print(
        "\nRows:",
        len(scored_df)
    )

    print(
        "Columns:",
        len(scored_df.columns)
    )

    print("\nLITERACY SCALE")

    for k, v in scoring_results[
        "literacy_scale"
    ].items():

        print(
            f"  {k}: {v}"
        )

    print("\nNUMERACY SCALE")

    for k, v in scoring_results[
        "numeracy_scale"
    ].items():

        print(
            f"  {k}: {v}"
        )


if __name__ == "__main__":
    main()
