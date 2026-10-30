# dataset_interpreter.py

import pandas as pd


class DataInterpreter:

    def __init__(self, df, dictionary_df):

        self.df = df
        self.dictionary = dictionary_df

    def identify_columns(self):

        metadata = {}
        rename_map = {}
        metadata_columns = []

        df_columns_lower = {
            col.lower().strip(): col
            for col in self.df.columns
        }

        for _, row in self.dictionary.iterrows():

            canonical = row["canonical_column"]

            variations = [
                x.strip().lower()
                for x in str(
                    row["possible_variations"]
                ).split(",")
            ]

            for variation in variations:

                if variation in df_columns_lower:

                    original = df_columns_lower[
                        variation
                    ]

                    metadata[
                        canonical
                    ] = original

                    metadata_columns.append(canonical)

                    rename_map[
                        original
                    ] = canonical

                    break

        return {
            "metadata": metadata,
            "metadata_columns": metadata_columns,
            "rename_map": rename_map
        }

    def apply_renaming(self, rename_map):

        self.df.rename(
            columns=rename_map,
            inplace=True
        )

        return self.df

    def create_child_id(self):

        if "child_id" in self.df.columns:
            return

        if {
            "school_id",
            "grade"
        }.issubset(self.df.columns):

            self.df["child_id"] = (
                self.df["school_id"]
                .astype(str)
                + "_"
                + self.df["grade"]
                .astype(str)
                + "_"
                + (
                    self.df.groupby(
                        ["school_id", "grade"]
                    )
                    .cumcount()
                    + 1
                ).astype(str)
            )

        else:

            self.df["child_id"] = (
                range(
                    1,
                    len(self.df) + 1
                )
            )

    def summarise(self):

        return {
            "rows": len(self.df),
            "columns": len(self.df.columns),
            "column_names": list(
                self.df.columns
            )
        }

    def run(self):

        results = self.identify_columns()

        self.apply_renaming(
            results["rename_map"]
        )

        self.create_child_id()

        return {
            "metadata": results["metadata"],
            "metadata_columns": results["metadata_columns"],
            "rename_map": results["rename_map"],
            "summary": self.summarise()
        }