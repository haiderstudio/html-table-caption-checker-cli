# html-table-caption-checker-cli

Check every HTML table carries a caption as its first child, fail CI when one does not.

[![CI](https://github.com/haiderstudio/html-table-caption-checker-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/haiderstudio/html-table-caption-checker-cli/actions/workflows/ci.yml) [![Licence: MIT](https://img.shields.io/badge/Licence-MIT-yellow.svg)](LICENSE)

## What it does

`html_table_caption_checker` reads HTML files,
parses them with the standard library HTML parser,
and reports each `<table>` whose first child is not
a `<caption>`, with the file and the line number. It
exits 1 when any such table is found, so it can fail
a CI run. A file where every table opens with a
caption exits 0.

- A table with no caption is announced to
  screen-reader users with no context — they hear
  rows of numbers with no idea what the table is
  about, while sighted users read the heading above
  it. One `<caption>` per table is the fix, and this
  gate names the tables still missing one.
- A caption that comes after a row, or after any
  other element, is not a first child and is
  reported. The caption must open the table.
- Whitespace and comments before the caption are
  fine — they are not elements. A stray line of text
  before the caption is not fine: the caption is no
  longer the first child.
- Tag names are matched without caring about upper
  or lower case, so `<TABLE>` with `<CAPTION>` passes
  and `<TABLE>` with no caption fails. A caption
  written inside a comment is not a caption.
- A nested table is checked on its own: the inner
  table's opening tag is an element before the outer
  table's caption, so an outer table that opens with
  a nested table fails, and the inner table is still
  checked separately. A table that is never closed
  is still checked — a caption that never arrived
  is a miss either way.
- A file given directly on the command line is always
  checked, whatever its name. A folder is walked for
  files ending in `.html` or `.htm` only, recursively
  by default (`--no-recursive` stops at the top
  level). `.git` folders are never walked, and
  directory links are never followed.
- `--json` prints the result as JSON, and `--stdin`
  checks one HTML document read from standard input.
- A file that cannot be read — a file that is not
  valid UTF-8 — is reported as an error and fails the
  check the same way a finding does.

## Who it is for

Anyone who ships a page with tables — which is
every site owner with a pricing table, a comparison
table, or a data table. A caption is one tag, and
without it a screen-reader user meets the numbers
with no idea what they are. This is the gate that
names the tables still missing one at the pull
request, before it ships.

## What it does NOT do

- It does not check whether a table has header cells.
  That is repo #115, html-table-header-checker-cli,
  which checks `<th>` headers — headers are a
  different element on the same tables.
- It does not check whether images have alt text.
  That is repo #81, markdown-image-alt-checker-cli
  for Markdown and repo #83, html-img-attr-checker-cli
  for HTML — alt text is a different check on
  different elements.
- It does not check form labels. That is repo #85,
  html-label-checker-cli — labels are a different
  check on different elements.
- It does not check the caption's wording, only that
  one is there and that it comes first. A caption
  that says nothing useful still passes.
- It does not add a caption or move one. It reports,
  you change the line.
- It never touches the network, and it only reads the
  files and folders you point it at.

## How this differs

- A fresh search of GitHub on Nov 18, 2026 found 0
  results for `"html-table-caption-checker-cli"` and
  0 results for `html table caption checker` — the
  field is empty for this job. No rival is a tested
  command-line gate that checks HTML tables for a
  caption as first child.
- So the narrow slice stands: caption-as-first-child
  only, parsed with the standard library, per-line
  reporting, a CI exit code, and a report-only tool
  that never edits a file.

## Install

```sh
git clone https://github.com/haiderstudio/html-table-caption-checker-cli.git
cd html-table-caption-checker-cli
```

There is nothing else to install: Python 3.10 or newer,
standard library only, no dependencies.

## Usage

Check one page:

```sh
python3 src/html_table_caption_checker.py page.html
```

A page where every table has a caption passes:

```sh
$ python3 src/html_table_caption_checker.py examples/clean.html
OK — 1 file(s) checked, every <table> has a <caption> as its first child.
```

A page with tables missing a caption fails, with the
line for each one:

```sh
$ python3 src/html_table_caption_checker.py examples/flagged.html
FAIL examples/flagged.html: line 4 table has no <caption> as its first child — <table class="prices">
FAIL examples/flagged.html: line 12 table has no <caption> as its first child — <table>
Checked 1 file(s), 2 table(s) without a <caption> as first child in 1 file(s).
```

Check a whole folder (`.html` and `.htm` files only):

```sh
$ python3 src/html_table_caption_checker.py examples/
FAIL examples/flagged.html: line 4 table has no <caption> as its first child — <table class="prices">
FAIL examples/flagged.html: line 12 table has no <caption> as its first child — <table>
Checked 3 file(s), 2 table(s) without a <caption> as first child in 1 file(s).
```

Check one document from standard input:

```sh
$ python3 src/html_table_caption_checker.py --stdin < examples/flagged.html
FAIL <stdin>: line 4 table has no <caption> as its first child — <table class="prices">
FAIL <stdin>: line 12 table has no <caption> as its first child — <table>
Checked 1 file(s), 2 table(s) without a <caption> as first child in 1 file(s).
```

Machine-readable output:

```sh
$ python3 src/html_table_caption_checker.py --json examples/flagged.html
{
  "files": [
    {
      "path": "examples/flagged.html",
      "findings": [
        {
          "line": 4,
          "statement": "<table class=\"prices\">"
        },
        {
          "line": 12,
          "statement": "<table>"
        }
      ],
      "errors": []
    }
  ],
  "checked": 1,
  "findings": 2
}
```

Exit codes: 0 when every table has a caption as its
first child, 1 when any table does not or a file
error is found, 2 for a usage error (a missing path,
a bad flag, or no `.html` files found).

## Examples

A table with no caption is caught with the line and
the opening tag:

```sh
$ printf '<table>\n  <tr><td>Apples</td></tr>\n</table>\n' > bare.html
$ python3 src/html_table_caption_checker.py bare.html
FAIL bare.html: line 1 table has no <caption> as its first child — <table>
Checked 1 file(s), 1 table(s) without a <caption> as first child in 1 file(s).
```

A caption that comes after a row is not a first
child — it fails too:

```sh
$ printf '<table>\n  <tr><td>Apples</td></tr>\n  <caption>Too late</caption>\n</table>\n' > late.html
$ python3 src/html_table_caption_checker.py late.html
FAIL late.html: line 1 table has no <caption> as its first child — <table>
Checked 1 file(s), 1 table(s) without a <caption> as first child in 1 file(s).
```

A comment before the caption is fine — it is not an
element, so the caption is still first.
`examples/edge.html` holds that case, plus uppercase
tags and blank lines before the caption, and it
passes:

```sh
$ python3 src/html_table_caption_checker.py examples/edge.html
OK — 1 file(s) checked, every <table> has a <caption> as its first child.
```

## How it is tested

```sh
python3 -m unittest discover -s tests
```

The suite checks the parser directly (caption first,
caption late, empty tables, nested tables, unclosed
tables, uppercase tags, captions inside comments),
the command line (folders, `--json`, `--stdin`,
`--exclude`, `--no-recursive`, missing paths, bad
UTF-8, a fake home folder), the examples (clean
passes, flagged fails with two findings on lines 4
and 12, edge passes), and repo hygiene (no
placeholder text, no absolute paths, standard
library imports only, no network use, `.env` first
in `.gitignore`, CI markers). `examples/run-example.sh`
runs the checker over every example file; its output
is recorded in `examples/sample-output.md` and the
tests check the two match.

## Contributing

Small, focused improvements are welcome.

- Open an issue first for anything larger than a typo or a clearer example, so the scope can be agreed before work starts.
- Never weaken the safety rules: a table without a caption as its first child must stay a fail, and the tool must never edit a file.
- Every claim in a proposed change must be verifiable: a command must be runnable, a pass or fail must be real, a badge must be true.
- Run `python3 -m unittest discover -s tests` before opening a pull request. It must pass.
- Do not add placeholder text, invented features, or copied content without attribution.
- Python standard library only — no new dependency without a reason in the issue.

## Licence

MIT — see [LICENSE](LICENSE).

## Original work

This tool is original work, built from the HTML
`<caption>` rule itself: a caption must be the first
child of a table, so that assistive technology can
announce what the table is about before reading its
rows. It builds on nothing copied and no other tool.
