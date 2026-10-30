"""Non-interactive smoke test: sample data -> scored -> Plotly figures."""
import sys
from pathlib import Path

import pandas as pd

from default_dictionaries import get_default_metadata_df, get_default_aser_df
from dataset_interpreter import DataInterpreter
from aser_column_matcher import ASERColumnMatcher
from aser_validator import ASERValidator
from aser_scorer import ASERScorer
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

scored = ASERScorer(df=df, metadata_columns=metadata_columns).run()["scored_df"]

analyser = ASER_Analyser_Plotly(
    scored, metadata_df.set_index("canonical_column").to_dict(orient="index")
)
print("type:", analyser.detect_analysis_type())
results = analyser.run()
print(len(results), "figures")
for r in results:
    r["figure"].to_json()
    print(" -", r["section"], "|", r["title"])

out = root / "src" / "outputs" / "preview.html"
html = "".join(r["figure"].to_html(full_html=False, include_plotlyjs=(i == 0 and "cdn")) for i, r in enumerate(results))
out.write_text(f"<html><body>{html}</body></html>", encoding="utf-8")
print("preview:", out)
