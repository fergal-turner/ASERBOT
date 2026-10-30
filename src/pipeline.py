# main.py

import pandas as pd


from dataset_interpreter import DataInterpreter
from aser_column_matcher import ASERColumnMatcher
from aser_validator import ASERValidator
from aser_scorer import ASERScorer
from aser_analyser import ASER_Analyser

from sc_theme import *



default_aser = {
    "reading_letter": {
        "domain": "reading",
        "possible_variations": [
            "letter",
            "letters",
            "letter_reading",
            "read_letter",
            "letter_level",
        ],
    },
    "reading_word": {
        "domain": "reading",
        "possible_variations": [
            "word",
            "words",
            "word_reading",
            "read_word",
            "word_level",
        ],
    },
    "reading_sentence": {
        "domain": "reading",
        "possible_variations": [
            "sentence",
            "sentences",
            "sentence_reading",
            "read_sentence",
            "sentence_level",
        ],
    },
    "reading_story": {
        "domain": "reading",
        "possible_variations": [
            "story",
            "stories",
            "paragraph",
            "passage",
            "read_story",
            "story_level",
        ],
    },
    "reading_comprehension": {
        "domain": "reading",
        "possible_variations": [
            "comprehension",
            "story_comprehension",
            "story_questions",
            "questions",
            "reading_comprehension",
        ],
    },
    "number_recognition_1_10": {
        "domain": "math",
        "possible_variations": [
            "number_1_10",
            "single_digit",
            "digit_1_10",
            "num_1_10",
            "numrec",
        ],
    },
    "number_recognition_1_99": {
        "domain": "math",
        "possible_variations": [
            "number_1_99",
            "double_digit",
            "two_digit",
            "digit_1_99",
            "num_1_99",
            "numrec2",
        ],
    },
    "number_recognition": {
        "domain": "math",
        "possible_variations": [
            "number_recognition",
            "number_id",
            "numbers",
            "number_test",
        ],
    },
    "addition": {
        "domain": "math",
        "possible_variations": [
            "addition",
            "add",
            "addition_task",
            "addition_test",
        ],
    },
    "subtraction": {
        "domain": "math",
        "possible_variations": [
            "subtraction",
            "subtract",
            "subtraction_task",
            "subtraction_test",
        ],
    },
    "multiplication": {
        "domain": "math",
        "possible_variations": [
            "multiplication",
            "multiply",
            "mult",
            "multiplication_task",
            "multiplication_test",
        ],
    },
    "division": {
        "domain": "math",
        "possible_variations": [
            "division",
            "divide",
            "division_task",
            "division_test",
        ],
    },
}


# =====================================================
# HELPERS
# =====================================================

def load_dataset(path):

    if path.lower().endswith(".csv"):
        return pd.read_csv(path)

    if path.lower().endswith(".xlsx"):
        return pd.read_excel(path)

    raise ValueError(
        "Dataset must be CSV or XLSX."
    )


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

    data_file = input(
        "Dataset path: "
    )

    metadata_dictionary = input(
        "Metadata dictionary CSV (leave blank to use default): "
    )

    aser_dictionary = input(
        "ASER dictionary CSV (leave blank to use default): "
    )

    print("\nLoading dataset...")

    df = load_dataset(data_file)

    if metadata_dictionary:
        metadata_dict = pd.read_csv(
            metadata_dictionary
        )
    else:
        metadata_dict = (
            pd.DataFrame.from_dict(
                default_metadata,
                orient="index"
            )
            .reset_index()
            .rename(
                columns={
                    "index": "canonical_column"
                }
            )
        )

    if aser_dictionary:
        aser_dict = pd.read_csv(
            aser_dictionary
        )
    else:
        aser_dict = (
            pd.DataFrame.from_dict(
                default_aser,
                orient="index"
            )
            .reset_index()
            .rename(
                columns={
                    "index": "canonical_column"
                }
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

    scorer = ASERScorer(
        df=df,
        metadata_columns=
        metadata_columns
    )

    scoring_results = (
        scorer.run()
    )

    scored_df = scoring_results[
        "scored_df"
    ]

    # =====================================
    # ANALYSIS
    # =====================================

    analyzer = ASER_Analyser(
        df=scored_df,
            metadata=(
        metadata_dict
        .set_index("canonical_column")
        .to_dict(orient="index")
        )
        )

    plan = analyzer.analysis_plan()

    print("\nANALYSIS PLAN")
    print("=" * 60)

    print(f"\nType: {plan['analysis_type']}")

    print("\nFigures:")
    for item in plan["figures"]:
        print(f"  • {item}")


    proceed = input(
            "\nProceed with analysis? (y/n): "
        )

    if proceed.lower() != "y":
        print("Analysis cancelled.")
        return

    analysis_type = (
        analyzer.detect_analysis_type()
    )

    if analysis_type == "cross_section":

        analyzer.run_cross_section_analysis()

    elif analysis_type == "repeated_cross_section":

        analyzer.run_repeated_cross_section_analysis()

    # elif analysis_type == "repeated_measures":

    #     analyzer.run_repeated_measures_analysis()

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