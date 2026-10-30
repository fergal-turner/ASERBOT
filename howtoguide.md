# ASERBOT app: how the files fit together

This guide explains how the browser app is put together and where to make common edits. It focuses on the user interface and the hand-off between the browser and Python; the analysis logic itself lives in Python modules.

## The short version

ASERBOT is a web page that runs its Python analysis in the user's browser using Pyodide. JavaScript handles the page and user interactions. It passes the dataset and confirmed column mappings to Python, then displays the returned summary and Plotly charts.

| File | Purpose | Usually edit it to… |
| --- | --- | --- |
| `src/app_template.html` | Source for the HTML page, styles, browser-side JavaScript, and build placeholders. | Change the interface, appearance, text, or browser behaviour. |
| `src/build_app.py` | Combines the template, Python modules, and sample CSV into the distributable HTML. | Change which files are included or how the bundle is produced. |
| `src/run_app.py` | Browser-facing Python functions for matching columns and running the analysis pipeline. | Change how browser inputs are prepared, checked, and passed into the pipeline. |
| `ASERBOT.html` | Generated, standalone HTML app that users open. | Normally do not edit this directly; rebuild it from the source files. |

The overall flow is:

```text
src/app_template.html + Python modules + Data/sample_data.csv
                              |
                              v
                       src/build_app.py
                              |
                              v
                         ASERBOT.html
                              |
                     opened in a browser
                              |
              JavaScript calls Python through Pyodide
                              |
                         src/run_app.py
                              |
                 matching, validation, scoring, plots
```

## 1. `src/app_template.html`: the interface source

This is the main source file for the web page. It contains three web technologies:

- **HTML** describes the elements on the page.
- **CSS** controls how those elements look and how they fit different screen sizes.
- **JavaScript** responds to user actions and connects the page to Python.

The template also has two placeholders:

```js
const PY_MODULES = __PY_MODULES__;
const SAMPLE_CSV = __SAMPLE_CSV__;
```

`src/build_app.py` replaces these placeholders with the Python source code and sample CSV text. The placeholders are expected in the template, but not in the final generated `ASERBOT.html`.

### HTML: the page elements

The page body is organized into a few main areas:

1. **Header** — the ASERBOT title and short description.
2. **Upload panel** — dataset picker, action buttons, and optional dictionary uploaders.
3. **Status panel** — messages such as “Loading Python engine…” and “Ready.”
4. **Column-review panel** — dropdowns for checking or changing proposed column matches.
5. **Summary panel** — row count, analysis type, mappings, warnings, and errors.
6. **Results area** — containers for the Plotly charts.

For example:

```html
<button id="runBtn" disabled>Run analysis</button>
```

`button` is the element type. `id="runBtn"` gives this particular button a unique name, and `disabled` prevents it being clicked until JavaScript enables it. JavaScript finds it using `$("runBtn")`.

The file-picker controls pair a visible `<label>` with a file input. The label's `for` attribute must match the input's `id`; that pairing lets the styled label open the hidden file chooser:

```html
<label for="dataFile">Choose dataset (CSV)</label>
<input type="file" id="dataFile" accept=".csv">
```

When editing an element's text, keep its `id` if JavaScript relies on it. Renaming or removing an ID without updating the JavaScript can break that interaction.

### CSS: the visual design

The CSS is inside the `<style>` element near the top of the file. Shared colours are defined as variables in `:root`:

```css
:root {
  --red: #da291c;
  --teal: #00B2A9;
  --bg: #F5F5F5;
}
```

To change a colour used throughout the page, edit its variable. CSS selectors determine which elements a rule affects:

- `body`, `header`, and `button` select all elements of that type.
- `.panel`, `.card`, and `.hidden` select elements with that class.
- `#status`, `#review`, and `#results` select the element with that ID.

For example, `.panel` styles the app's white bordered sections; `#results` refers to the results container specifically. The `.hidden` class hides an element. JavaScript shows or hides sections by adding or removing this class.

The `@media` rules define adjustments for narrow screens. If you change layout or sizing, check those rules as well as the default layout.

### JavaScript: state and page behaviour

The JavaScript is inside the `<script>` element near the bottom. It loads Pyodide, reads local files, runs the two Python stages, and displays the result.

These variables keep the current app state while the page is open:

```js
let pyodide = null;
let datasetText = null;
let metaText = null;
let aserText = null;
```

They hold the Pyodide runtime and the text of the selected dataset and optional dictionaries. The app reads selected CSV files in the browser with `file.text()` and keeps their contents in memory for the analysis.

This small helper finds a page element by ID:

```js
const $ = id => document.getElementById(id);
```

For example, `$("runBtn")` is shorthand for `document.getElementById("runBtn")`.

#### Loading Python: `initPython()`

`initPython()` runs when the page loads. It:

1. loads Pyodide;
2. loads pandas and `micropip`;
3. installs Python's Plotly package;
4. writes the embedded Python module files into Pyodide's virtual filesystem;
5. imports `detect_columns` and `run_analysis` from `run_app.py`;
6. updates the status and enables the buttons when the runtime is ready.

The page also loads Pyodide and the JavaScript Plotly library from external CDNs. An internet connection may be needed to load these resources and install packages, especially on first use.

#### Reading files and loading sample data

`readFile()` attaches a `change` event listener to a file input. When the user selects a file, it reads the file as text, stores that text in the corresponding state variable, updates the displayed filename, and refreshes button states.

The three calls to `readFile()` connect this behaviour to the dataset, metadata dictionary, and ASER dictionary inputs.

The sample-data button uses the embedded `SAMPLE_CSV` text. It sets that text as the current dataset and starts column detection.

#### Reviewing column matches

Clicking **Run analysis** first calls `startReview()`. It does not immediately run scoring: it first lets the user review the proposed field-to-column matches.

`startReview()` sends the dataset and any uploaded dictionary text to Python's `detect_columns()` function. If detection succeeds, `renderReview()` builds the review interface.

`fieldRow()` creates one row in that interface. A row contains:

- the field's canonical name and group;
- a dropdown containing “(none)” and dataset columns;
- suggested columns, when the matcher provided them;
- a status tag and example values from the currently selected column.

`refreshReview()` updates the status tags and checks for conflicts. A conflict happens when two fields select the same dataset column. The conflicting rows are highlighted and the confirm button is disabled until the conflict is fixed.

`collectMappings()` reads all the dropdown selections and creates an object shaped like this:

```js
{
  "canonical_field": "dataset_column"
}
```

Fields set to “(none)” are omitted from the object.

#### Running the analysis and showing results

Clicking **Confirm and run** calls `runAnalysis()` with the reviewed mappings. That function passes the dataset text, optional dictionary text, and mappings to Python's `run_analysis()`.

The Python function returns JSON text. JavaScript parses it and:

- calls `renderSummary()` to show the row count, analysis type, mappings, and messages;
- calls `renderFigures()` to create chart containers and draw each Plotly figure;
- updates the status message.

The `esc()` helper replaces special HTML characters before certain text is inserted into HTML. Keep escaping in place for text that may come from dataset columns, field names, or analysis output.

## 2. `src/build_app.py`: building the standalone HTML

`src/build_app.py` packages the parts required by the browser app. It does not perform the analysis itself.

The script:

1. locates its own `src` directory and the parent app directory;
2. lists the Python modules to bundle in `MODULES`;
3. reads those modules as text;
4. reads `Data/sample_data.csv`;
5. reads `src/app_template.html`;
6. substitutes the embedded module code and sample data for the template placeholders;
7. writes the result to `ASERBOT.html`.

The `MODULES` list is important. A Python file needed by the browser must be listed there so the build can embed it. The current list contains the dictionaries, matching, validation, scoring, plotting, and browser-entry modules.

The `embed()` helper converts the module dictionary or CSV text into JSON suitable for JavaScript. It also escapes `</` so embedded text cannot accidentally close the HTML `<script>` element.

### Rebuilding after a change

After editing the template, `run_app.py`, another bundled Python module, or the sample CSV, rebuild the app from the ASERBOT folder:

```powershell
python .\src\build_app.py
```

The script determines its paths relative to itself, so this command can also be run from another working directory by providing the full path to `build_app.py`.

If you create a new Python module that the browser needs, add its filename to `MODULES` in `src/build_app.py`. Also make sure the module imports work in the bundled environment.

## 3. `src/run_app.py`: the Python interface for the page

`src/run_app.py` adapts browser-provided CSV text to the existing Python analysis pipeline. The two public functions return JSON strings so JavaScript can parse their responses.

### `_read_dictionary()`: uploaded or default dictionaries

`_read_dictionary()` reads an uploaded dictionary CSV when non-empty text is supplied. If no dictionary was uploaded, it calls the appropriate default-dictionary function. This is what makes the advanced dictionary uploads optional.

### `detect_columns()`: propose field-to-column matches

`detect_columns(csv_text, metadata_csv=None, aser_csv=None)`:

1. reads the dataset CSV into a pandas DataFrame;
2. loads uploaded dictionaries or the defaults;
3. calls `_detect()` to obtain proposed metadata and assessment-column matches;
4. collects up to three example values for each dataset column;
5. returns JSON describing the dataset and the proposed matches.

On success, the response includes `ok`, row count, column names, samples, metadata fields, and ASER fields. If an exception occurs, the response includes `ok: false` and an error message. The browser uses this response to build the review dropdowns.

### `_detect()`: coordinate the matchers

`_detect()` calls `DataInterpreter` to identify metadata columns and obtain a rename map. It then renames those columns for the assessment matching step and calls `ASERColumnMatcher`.

It converts the matcher output into field records for the browser. Clear ASER matches are selected automatically; ambiguous matches are left for the user to review. Candidate names are converted back to the original dataset column names so that the dropdowns show names the user recognizes.

### `run_analysis()`: validate, score, and create figures

`run_analysis(csv_text, mappings_json=None, metadata_csv=None, aser_csv=None)` runs the confirmed analysis:

1. reads the dataset and uploaded or default dictionaries;
2. uses the confirmed mappings, or detects mappings automatically if none were supplied;
3. checks that mapped columns exist and that no column is assigned to more than one field;
4. renames mapped dataset columns to their canonical field names;
5. validates the dataset with `ASERValidator`;
6. returns validation errors and warnings if the dataset is not ready;
7. scores the data with `ASERScorer`;
8. constructs the Plotly analyser and determines the analysis type;
9. runs the analyser and serializes each figure as JSON.

The result has this general shape:

```json
{
  "ok": true,
  "log": {
    "rows": 0,
    "analysis_type": null,
    "mappings": {},
    "unmapped": [],
    "errors": [],
    "warnings": []
  },
  "figures": []
}
```

The actual values depend on the uploaded dataset. The browser uses `log` for the summary and messages, and `figures` for the charts.

## 4. `ASERBOT.html`: the generated app users open

`ASERBOT.html` is the build output. It contains the template's HTML, CSS, and JavaScript, plus the embedded Python modules and sample data.

Treat it as a generated file:

- Make lasting interface changes in `src/app_template.html`.
- Make lasting browser/Python hand-off changes in `src/run_app.py`.
- Make lasting analysis changes in the appropriate source Python module.
- Make sample-data changes in `Data/sample_data.csv`.
- Run `python .\src\build_app.py` to refresh `ASERBOT.html`.

Editing `ASERBOT.html` directly is useful for a temporary experiment, but a later build will overwrite those changes.

## A practical editing and checking workflow

1. Decide whether the change is about appearance, browser interaction, Python hand-off, or analysis.
2. Edit the source file responsible for that part.
3. If the change affects anything bundled into the page, rebuild `ASERBOT.html`.
4. Open the generated HTML in a browser and test the relevant user journey:
   - choose a dataset or load the sample;
   - check and, if appropriate, change the proposed mappings;
   - confirm and run;
   - inspect the summary, errors/warnings, and charts.
5. If you changed the layout, also check the page at a narrow/mobile width.

When adding or changing page elements, check both sides of the interaction: the HTML element and the JavaScript that finds it by ID or attaches an event listener.

## Quick glossary

- **Element:** a piece of the page, such as a button, section, or heading.
- **Tag:** the markup that defines an element, such as `<button>`.
- **Attribute:** extra information on a tag, such as `id="runBtn"` or `disabled`.
- **ID:** a unique name for an element, used by JavaScript to find it.
- **Class:** a reusable label, commonly used to apply CSS to multiple elements.
- **Event listener:** code that runs in response to an action, such as a click or file selection.
- **DOM:** the browser's in-memory representation of the page; JavaScript uses it to inspect and update elements.
- **JSON:** a text format for passing structured data between JavaScript and Python in this app.
- **`async` / `await`:** JavaScript syntax for waiting for operations that take time, such as loading Pyodide or reading a file.
