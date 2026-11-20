#!/usr/bin/env python3
"""Check every <table> carries a <caption> as its first child.

Run: python3 src/html_table_caption_checker.py page.html
     python3 src/html_table_caption_checker.py site/
     python3 src/html_table_caption_checker.py --stdin < page.html

A table with no caption is announced to screen-reader
users with no context — they hear rows of numbers with
no idea what the table is about, while sighted users
read the heading above it. This tool names each table
whose first child is not a <caption>, with the file
and the line number, and exits 1 when any is found, so
it can fail a CI run. A file where every table opens
with a caption exits 0.

The check uses the standard library HTML parser, so
it reads the document the way a browser does: tags
inside comments are not tags, tag names are matched
without caring about upper or lower case, and a
caption that comes after a row, or after another
element, is not a first child. Whitespace and comments
before the caption are fine — they are not elements.
A nested table is checked on its own: the inner
table's opening tag is an element before the outer
table's caption, so an outer table that opens with a
nested table fails, and the inner table is still
checked separately.

It reads HTML only. It never edits a file, never
touches the network, and reads only the files and
folders you point it at.
"""

import argparse
import fnmatch
import json
import os
import sys
from html.parser import HTMLParser
from pathlib import Path

__version__ = "1.0.0"

HTML_SUFFIXES = (".html", ".htm")


class _TableTracker(HTMLParser):
    """Track open tables and whether a caption came first.

    Each open table keeps its line number and whether
    its first child element was a <caption>. A table
    is decided the moment its first child element
    arrives: a caption decides it as good, anything
    else decides it as a miss. A table that closes
    undecided — it held only text, whitespace, or
    comments — is a miss too: a caption never arrived.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.findings = []

    def _note_line(self, line_no):
        """The source line holding the table's opening tag."""
        lines = self._source.splitlines()
        if 1 <= line_no <= len(lines):
            line = lines[line_no - 1].strip()
        else:
            line = "<table>"
        if len(line) > 100:
            line = line[:97] + "..."
        return line

    def handle_starttag(self, tag, attrs):
        line, _ = self.getpos()
        if tag == "table":
            if self.stack:
                self._decide_current(False)
            self.stack.append({
                "line": line,
                "caption_first": False,
                "decided": False,
                "statement": self._note_line(line),
            })
            return
        if self.stack:
            self._decide_current(tag == "caption")

    def handle_startendtag(self, tag, attrs):
        # A self-closing tag is still an element: a
        # self-closing <caption/> inside a table counts
        # as the caption, anything else decides a miss.
        # A self-closing <table/> opens and closes at
        # once, so it is a miss unless it held nothing.
        if tag == "table":
            if self.stack:
                self._decide_current(False)
            line, _ = self.getpos()
            self.findings.append({
                "line": line,
                "statement": self._note_line(line),
            })
            return
        if self.stack:
            self._decide_current(tag == "caption")

    def handle_endtag(self, tag):
        if tag == "table" and self.stack:
            table = self.stack.pop()
            if not table["caption_first"]:
                self.findings.append({
                    "line": table["line"],
                    "statement": table["statement"],
                })

    def handle_data(self, data):
        # Text that is not just whitespace is content
        # before the caption, so it decides a miss —
        # a caption after stray text is not a first
        # child. Whitespace alone is fine.
        if self.stack and data.strip():
            self._decide_current(False)

    def _decide_current(self, caption_first):
        table = self.stack[-1]
        if not table["decided"]:
            table["decided"] = True
            table["caption_first"] = caption_first

    def close(self):
        super().close()
        # A table never closed still counts: a caption
        # that never arrived is a miss either way.
        while self.stack:
            table = self.stack.pop()
            if not table["caption_first"]:
                self.findings.append({
                    "line": table["line"],
                    "statement": table["statement"],
                })

    def check(self, text):
        """Check one HTML document given as text.

        Returns a list of findings. A finding is a dict
        with "line" and "statement".
        """
        self._source = text
        self.stack = []
        self.findings = []
        self.feed(text)
        self.close()
        self.findings.sort(key=lambda item: item["line"])
        return self.findings


def check_text(text):
    """Check one HTML document given as text.

    Returns (findings, errors). A finding is a dict
    with "line" and "statement". The parser is
    forgiving by design, so malformed HTML reports
    findings, not errors — there is no error case
    here, and the empty list is kept so the shape
    matches the other checkers.
    """
    tracker = _TableTracker()
    return tracker.check(text), []


def check_file(path):
    """Check one file. Returns (findings, errors)."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return [], ["not valid UTF-8"]
    except OSError as exc:
        return [], ["could not read the file: %s" % exc]
    return check_text(text)


def _is_excluded(name, patterns):
    return any(fnmatch.fnmatch(name, pat) for pat in patterns)


def collect_paths(paths, recursive, exclude):
    """Turn command-line paths into a sorted list of files.

    A file given directly is always checked, whatever its
    name. A folder is walked for files ending in .html
    or .htm only, recursively by default
    (--no-recursive stops at the top level). .git
    folders are never walked, and directory links are
    never followed.
    """
    found = []
    seen = set()
    for given in paths:
        target = Path(given)
        if target.is_file():
            key = str(target.resolve())
            if key not in seen:
                seen.add(key)
                found.append(str(target))
        elif target.is_dir():
            if recursive:
                walker = os.walk(target, followlinks=False)
            else:
                walker = [(str(target), [], sorted(
                    p.name for p in target.iterdir() if p.is_file()))]
            for root, dirs, files in walker:
                dirs[:] = sorted(
                    d for d in dirs if d != ".git")
                for name in sorted(files):
                    if not name.lower().endswith(HTML_SUFFIXES):
                        continue
                    if _is_excluded(name, exclude):
                        continue
                    full = os.path.join(root, name)
                    key = str(Path(full).resolve())
                    if key not in seen:
                        seen.add(key)
                        found.append(full)
        else:
            found.append(given)
    return sorted(found)


def _fail_line(path, finding):
    return ('FAIL %s: line %d table has no <caption> as its '
            'first child — %s'
            % (path, finding["line"], finding["statement"]))


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="html_table_caption_checker",
        description="Check every <table> carries a <caption> "
        "as its first child.")
    parser.add_argument("paths", nargs="*", metavar="PATH",
                        help="HTML file or folder to check")
    parser.add_argument("--json", action="store_true",
                        help="print the result as JSON")
    parser.add_argument("--stdin", action="store_true",
                        help="check one HTML document from standard input")
    parser.add_argument("--no-recursive", action="store_true",
                        help="do not walk into subfolders")
    parser.add_argument("--exclude", action="append", default=[],
                        metavar="PATTERN",
                        help="skip files whose name matches the pattern "
                        "(may be given more than once)")
    parser.add_argument("--version", action="version",
                        version="html_table_caption_checker "
                        + __version__)
    args = parser.parse_args(argv)

    results = []
    if args.stdin:
        if args.paths:
            print("error: --stdin takes no paths",
                  file=sys.stderr)
            return 2
        text = sys.stdin.read()
        findings, errors = check_text(text)
        results.append(("<stdin>", findings, errors))
    else:
        if not args.paths:
            print("error: give at least one file or folder to check",
                  file=sys.stderr)
            return 2
        missing = [p for p in args.paths
                   if not Path(p).exists()]
        if missing:
            for path in missing:
                print("error: no such file or folder: %s" % path,
                      file=sys.stderr)
            return 2
        files = collect_paths(args.paths, not args.no_recursive,
                              args.exclude)
        if not files:
            print("error: no .html files found", file=sys.stderr)
            return 2
        for path in files:
            findings, errors = check_file(path)
            results.append((path, findings, errors))

    checked = len(results)
    total_findings = sum(len(f) for _, f, _ in results)
    bad_files = sum(1 for _, f, e in results if f or e)

    if args.json:
        print(json.dumps({
            "files": [
                {"path": path, "findings": findings,
                 "errors": errors}
                for path, findings, errors in results
            ],
            "checked": checked,
            "findings": total_findings,
        }, indent=2))
    else:
        for path, findings, errors in results:
            for finding in findings:
                print(_fail_line(path, finding))
            for error in errors:
                print("ERROR %s: %s" % (path, error))
        if total_findings == 0 and bad_files == 0:
            print("OK — %d file(s) checked, every <table> has a "
                  "<caption> as its first child." % checked)
        else:
            print("Checked %d file(s), %d table(s) without a "
                  "<caption> as first child in %d file(s)."
                  % (checked, total_findings, bad_files))

    if total_findings or bad_files:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
