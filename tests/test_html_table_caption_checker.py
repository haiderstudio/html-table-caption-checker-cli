#!/usr/bin/env python3
"""Tests for html_table_caption_checker — stdlib unittest only."""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import html_table_caption_checker as checker

REPO = Path(__file__).resolve().parent.parent


def run_cli(argv):
    """Run main(argv), capture stdout/stderr, return (code, out, err)."""
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            code = checker.main(argv)
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def write(tmp, name, text, encoding="utf-8"):
    path = Path(tmp) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text, encoding=encoding)
    return str(path)


def findings_of(text):
    bad, _ = checker.check_text(text)
    return bad


class TestCaptions(unittest.TestCase):
    def test_caption_first_passes(self):
        bad = findings_of(
            "<table>\n  <caption>Prices</caption>\n"
            "  <tr><td>1</td></tr>\n</table>\n")
        self.assertEqual(bad, [])

    def test_caption_with_attributes_passes(self):
        bad = findings_of(
            '<table class="data">\n'
            '  <caption id="t1">Prices</caption>\n</table>\n')
        self.assertEqual(bad, [])

    def test_table_without_caption_flagged(self):
        bad = findings_of(
            "<table>\n  <tr><td>1</td></tr>\n</table>\n")
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["line"], 1)
        self.assertEqual(bad[0]["statement"], "<table>")

    def test_table_line_is_the_opening_tag(self):
        bad = findings_of(
            "<html>\n<body>\n<table class=\"prices\">\n"
            "  <tr><td>1</td></tr>\n</table>\n</body>\n</html>\n")
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["line"], 3)
        self.assertEqual(bad[0]["statement"], '<table class="prices">')

    def test_caption_after_a_row_is_not_first(self):
        bad = findings_of(
            "<table>\n  <tr><td>1</td></tr>\n"
            "  <caption>Too late</caption>\n</table>\n")
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["line"], 1)

    def test_caption_after_colgroup_is_not_first(self):
        bad = findings_of(
            "<table>\n  <colgroup></colgroup>\n"
            "  <caption>Too late</caption>\n</table>\n")
        self.assertEqual(len(bad), 1)

    def test_empty_table_flagged(self):
        bad = findings_of("<table></table>\n")
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["line"], 1)

    def test_table_with_only_text_flagged(self):
        bad = findings_of("<table>just words</table>\n")
        self.assertEqual(len(bad), 1)

    def test_table_with_only_whitespace_flagged(self):
        bad = findings_of("<table>\n  \n</table>\n")
        self.assertEqual(len(bad), 1)

    def test_whitespace_before_caption_passes(self):
        bad = findings_of(
            "<table>\n\n  \n  <caption>Prices</caption>\n</table>\n")
        self.assertEqual(bad, [])

    def test_comment_before_caption_passes(self):
        bad = findings_of(
            "<table>\n  <!-- a note -->\n"
            "  <caption>Prices</caption>\n</table>\n")
        self.assertEqual(bad, [])

    def test_comment_that_mentions_caption_is_not_a_caption(self):
        bad = findings_of(
            "<table>\n  <!-- <caption>not real</caption> -->\n"
            "  <tr><td>1</td></tr>\n</table>\n")
        self.assertEqual(len(bad), 1)

    def test_uppercase_tags_pass(self):
        bad = findings_of(
            "<TABLE>\n  <CAPTION>Prices</CAPTION>\n"
            "  <TR><TD>1</TD></TR>\n</TABLE>\n")
        self.assertEqual(bad, [])

    def test_uppercase_table_without_caption_flagged(self):
        bad = findings_of(
            "<TABLE>\n  <TR><TD>1</TD></TR>\n</TABLE>\n")
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["line"], 1)

    def test_mixed_case_caption_passes(self):
        bad = findings_of(
            "<Table>\n  <Caption>Prices</Caption>\n</Table>\n")
        self.assertEqual(bad, [])

    def test_caption_outside_table_ignored(self):
        bad = findings_of(
            "<caption>Loose caption</caption>\n"
            "<table>\n  <tr><td>1</td></tr>\n</table>\n")
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["line"], 2)

    def test_multiple_tables_mixed(self):
        bad = findings_of(
            "<table>\n  <caption>Good</caption>\n</table>\n"
            "<table>\n  <tr><td>1</td></tr>\n</table>\n"
            "<table>\n  <caption>Good too</caption>\n</table>\n"
            "<table>\n  <tr><td>2</td></tr>\n</table>\n")
        self.assertEqual(len(bad), 2)
        self.assertEqual([item["line"] for item in bad], [4, 10])

    def test_tables_reported_in_line_order(self):
        bad = findings_of(
            "<table>\n  <tr><td>1</td></tr>\n</table>\n"
            "<table>\n  <tr><td>2</td></tr>\n</table>\n")
        self.assertEqual([item["line"] for item in bad], [1, 4])

    def test_nested_table_inner_without_caption(self):
        bad = findings_of(
            "<table>\n  <caption>Outer</caption>\n"
            "  <tr><td>\n    <table>\n"
            "      <tr><td>inner</td></tr>\n    </table>\n"
            "  </td></tr>\n</table>\n")
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["line"], 4)

    def test_nested_table_outer_without_caption(self):
        bad = findings_of(
            "<table>\n  <tr><td>\n    <table>\n"
            "      <caption>Inner</caption>\n"
            "      <tr><td>inner</td></tr>\n    </table>\n"
            "  </td></tr>\n</table>\n")
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["line"], 1)

    def test_nested_table_both_without_caption(self):
        bad = findings_of(
            "<table>\n  <tr><td>\n    <table>\n"
            "      <tr><td>inner</td></tr>\n    </table>\n"
            "  </td></tr>\n</table>\n")
        self.assertEqual(len(bad), 2)
        self.assertEqual([item["line"] for item in bad], [1, 3])

    def test_nested_table_both_with_caption(self):
        bad = findings_of(
            "<table>\n  <caption>Outer</caption>\n"
            "  <tr><td>\n    <table>\n"
            "      <caption>Inner</caption>\n"
            "      <tr><td>inner</td></tr>\n    </table>\n"
            "  </td></tr>\n</table>\n")
        self.assertEqual(bad, [])

    def test_unclosed_table_without_caption_flagged(self):
        bad = findings_of("<table>\n  <tr><td>1</td></tr>\n")
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["line"], 1)

    def test_unclosed_table_with_caption_passes(self):
        bad = findings_of(
            "<table>\n  <caption>Prices</caption>\n"
            "  <tr><td>1</td></tr>\n")
        self.assertEqual(bad, [])

    def test_stray_text_before_caption_is_a_miss(self):
        bad = findings_of(
            "<table>\n  stray words\n"
            "  <caption>Prices</caption>\n</table>\n")
        self.assertEqual(len(bad), 1)

    def test_long_opening_line_truncated(self):
        long_attrs = "x" * 120
        bad = findings_of('<table class="%s">\n</table>\n' % long_attrs)
        self.assertEqual(len(bad), 1)
        self.assertTrue(bad[0]["statement"].endswith("..."))
        self.assertEqual(len(bad[0]["statement"]), 100)

    def test_empty_document_passes(self):
        self.assertEqual(findings_of(""), [])

    def test_document_without_tables_passes(self):
        bad = findings_of(
            "<html>\n<body>\n<p>No tables here.</p>\n"
            "</body>\n</html>\n")
        self.assertEqual(bad, [])

    def test_caption_text_with_entities_passes(self):
        bad = findings_of(
            "<table>\n  <caption>Fish &amp; Chips</caption>\n"
            "</table>\n")
        self.assertEqual(bad, [])


class TestCli(unittest.TestCase):
    def test_clean_file_exit_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "ok.html",
                         "<table>\n  <caption>Good</caption>\n</table>\n")
            code, out, _ = run_cli([path])
            self.assertEqual(code, 0)
            self.assertIn("OK", out)
            self.assertIn("every <table> has a <caption>", out)

    def test_flagged_file_exit_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.html",
                         "<table>\n  <tr><td>1</td></tr>\n</table>\n")
            code, out, _ = run_cli([path])
            self.assertEqual(code, 1)
            self.assertIn(
                "FAIL %s: line 1 table has no <caption> as its "
                "first child — <table>" % path, out)
            self.assertIn("1 table(s) without a <caption>", out)

    def test_folder_walk(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "a.html",
                  "<table>\n  <caption>Good</caption>\n</table>\n")
            write(tmp, "b.html", "<table>\n</table>\n")
            write(tmp, "b.htm", "<table>\n</table>\n")
            write(tmp, "notes.txt", "<table>\n</table>\n")
            code, out, _ = run_cli([tmp])
            self.assertEqual(code, 1)
            self.assertIn("Checked 3 file(s)", out)
            self.assertNotIn("notes.txt", out)

    def test_nested_folders(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "sub/deep.html", "<table>\n</table>\n")
            code, out, _ = run_cli([tmp])
            self.assertEqual(code, 1)
            self.assertIn("deep.html", out)

    def test_no_recursive(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "top.html",
                  "<table>\n  <caption>Good</caption>\n</table>\n")
            write(tmp, "sub/deep.html", "<table>\n</table>\n")
            code, out, _ = run_cli(["--no-recursive", tmp])
            self.assertEqual(code, 0)
            self.assertIn("OK — 1 file(s) checked", out)

    def test_exclude_skips_a_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "a.html", "<table>\n</table>\n")
            write(tmp, "skip.html", "<table>\n</table>\n")
            code, out, _ = run_cli(["--exclude", "skip.html", tmp])
            self.assertEqual(code, 1)
            self.assertIn("Checked 1 file(s)", out)
            self.assertNotIn("skip.html", out)

    def test_git_folder_skipped_in_walk(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, ".git/hooks/bad.html", "<table>\n</table>\n")
            write(tmp, "a.html",
                  "<table>\n  <caption>Good</caption>\n</table>\n")
            code, out, _ = run_cli([tmp])
            self.assertEqual(code, 0)
            self.assertIn("OK — 1 file(s) checked", out)

    def test_direct_file_checked_whatever_its_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "page.txt", "<table>\n</table>\n")
            code, out, _ = run_cli([path])
            self.assertEqual(code, 1)
            self.assertIn("page.txt", out)

    def test_duplicate_paths_checked_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.html", "<table>\n</table>\n")
            code, out, _ = run_cli([path, path])
            self.assertEqual(code, 1)
            self.assertIn("Checked 1 file(s)", out)

    def test_json_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.html", "<table>\n</table>\n")
            code, out, _ = run_cli(["--json", path])
            self.assertEqual(code, 1)
            data = json.loads(out)
            self.assertEqual(data["checked"], 1)
            self.assertEqual(data["findings"], 1)
            self.assertEqual(
                data["files"][0]["findings"][0]["line"], 1)
            self.assertEqual(
                data["files"][0]["findings"][0]["statement"],
                "<table>")
            self.assertEqual(data["files"][0]["errors"], [])

    def test_stdin_clean(self):
        old_stdin = sys.stdin
        sys.stdin = io.StringIO(
            "<table>\n  <caption>Good</caption>\n</table>\n")
        try:
            code, out, _ = run_cli(["--stdin"])
        finally:
            sys.stdin = old_stdin
        self.assertEqual(code, 0)
        self.assertIn("every <table> has a <caption>", out)

    def test_stdin_dirty(self):
        old_stdin = sys.stdin
        sys.stdin = io.StringIO("<table>\n</table>\n")
        try:
            code, out, _ = run_cli(["--stdin"])
        finally:
            sys.stdin = old_stdin
        self.assertEqual(code, 1)
        self.assertIn(
            "FAIL <stdin>: line 1 table has no <caption>", out)

    def test_stdin_with_paths_is_usage_error(self):
        code, _, err = run_cli(["--stdin", "a.html"])
        self.assertEqual(code, 2)

    def test_no_paths_is_usage_error(self):
        code, _, err = run_cli([])
        self.assertEqual(code, 2)

    def test_missing_path_exit_2(self):
        code, _, err = run_cli(["/no/such/page.html"])
        self.assertEqual(code, 2)
        self.assertIn("no such file or folder", err)

    def test_empty_folder_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _, err = run_cli([tmp])
            self.assertEqual(code, 2)
            self.assertIn("no .html files found", err)

    def test_bad_flag_exit_2(self):
        code, _, _ = run_cli(["--nope", "a.html"])
        self.assertEqual(code, 2)

    def test_version(self):
        code, out, _ = run_cli(["--version"])
        self.assertEqual(code, 0)
        self.assertIn("html_table_caption_checker", out)

    def test_non_utf8_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.html", b"\xff\xfe<>")
            code, out, _ = run_cli([path])
            self.assertEqual(code, 1)
            self.assertIn("not valid UTF-8", out)

    def test_input_files_left_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = "<table>\n</table>\n"
            path = write(tmp, "bad.html", text)
            run_cli([path])
            self.assertEqual(Path(path).read_text(), text)

    def test_cli_runs_from_another_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.html", "<table>\n</table>\n")
            result = subprocess.run(
                [sys.executable,
                 str(REPO / "src"
                     / "html_table_caption_checker.py"), path],
                capture_output=True, text=True, cwd="/")
            self.assertEqual(result.returncode, 1)
            self.assertIn("no <caption> as its first child",
                          result.stdout)

    def test_cli_runs_under_fake_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.html", "<table>\n</table>\n")
            env = dict(os.environ, HOME=tmp)
            result = subprocess.run(
                [sys.executable,
                 str(REPO / "src"
                     / "html_table_caption_checker.py"), path],
                capture_output=True, text=True, cwd=tmp, env=env)
            self.assertEqual(result.returncode, 1)

    def test_run_example_output_matches_sample(self):
        sample = (REPO / "examples" / "sample-output.md").read_text()
        result = subprocess.run(
            ["sh", str(REPO / "examples" / "run-example.sh")],
            capture_output=True, text=True, cwd=str(REPO))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), sample.strip())

    def test_readme_quotes_match_real_runs(self):
        readme = (REPO / "README.md").read_text()
        flagged = (REPO / "examples" / "flagged.html").read_text()
        bad, _ = checker.check_text(flagged)
        for item in bad:
            line = ("FAIL examples/flagged.html: line %d table has "
                    "no <caption> as its first child — %s"
                    % (item["line"], item["statement"]))
            self.assertIn(line, readme)


class TestExamples(unittest.TestCase):
    def test_clean_example_passes(self):
        code, _, _ = run_cli([str(REPO / "examples" / "clean.html")])
        self.assertEqual(code, 0)

    def test_flagged_example_fails_with_two(self):
        bad, _ = checker.check_text(
            (REPO / "examples" / "flagged.html").read_text())
        self.assertEqual(len(bad), 2)
        self.assertEqual([item["line"] for item in bad], [4, 12])
        self.assertEqual(bad[0]["statement"], '<table class="prices">')
        self.assertEqual(bad[1]["statement"], "<table>")

    def test_edge_example_passes(self):
        code, _, _ = run_cli([str(REPO / "examples" / "edge.html")])
        self.assertEqual(code, 0)


class TestHygiene(unittest.TestCase):
    def _repo_files(self, skip_tests=True):
        """Every file in the repo, minus .git and caches."""
        for path in REPO.rglob("*"):
            if path.is_dir():
                continue
            if ".git" in path.parts or "__pycache__" in path.parts:
                continue
            if path.suffix == ".pyc":
                continue
            if skip_tests and "tests" in path.parts:
                continue
            yield path

    def test_no_placeholder_text(self):
        banned = ["TODO", "coming soon", "lorem", "FIXME", "XXX"]
        hits = []
        for path in self._repo_files(skip_tests=True):
            text = path.read_text(errors="ignore")
            for word in banned:
                if word in text:
                    hits.append("%s: %s" % (path.name, word))
        self.assertEqual(hits, [])

    def test_no_absolute_paths(self):
        hits = []
        for path in self._repo_files(skip_tests=True):
            text = path.read_text(errors="ignore")
            for marker in ("/home/", "/Users/", "C:\\", "/tmp/"):
                if marker in text:
                    hits.append("%s: %s" % (path.name, marker))
        self.assertEqual(hits, [])

    def test_stdlib_imports_only(self):
        import ast
        stdlib = set(sys.stdlib_module_names)
        for target in (REPO / "src" / "html_table_caption_checker.py",
                       REPO / "tests"
                       / "test_html_table_caption_checker.py"):
            tree = ast.parse(target.read_text())
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(a.name.split(".")[0]
                                    for a in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module.split(".")[0])
            self.assertFalse(
                imported - stdlib - {"html_table_caption_checker"},
                (target.name, imported))
            self.assertNotIn("yaml", imported)

    def test_no_network_use_in_src(self):
        src = (REPO / "src"
               / "html_table_caption_checker.py").read_text()
        for marker in ("urllib.request", "requests", "socket",
                       "http.client", "urlopen", "urlretrieve"):
            self.assertNotIn(marker, src, marker)

    def test_gitignore_lists_env_first(self):
        lines = (REPO / ".gitignore").read_text().splitlines()
        self.assertTrue(lines, ".gitignore is empty")
        self.assertEqual(lines[0], ".env")

    def test_ci_runs_this_test_file(self):
        ci = (REPO / ".github" / "workflows" / "ci.yml").read_text()
        self.assertIn("tests/test_html_table_caption_checker.py", ci)
        self.assertIn("ubuntu-latest", ci)
        self.assertIn("3.12", ci)
        self.assertIn("actions/checkout", ci)
        self.assertIn("setup-python", ci)
        self.assertIn("push", ci)
        self.assertIn("pull_request", ci)

    def test_readme_names_the_neighbouring_repos(self):
        readme = (REPO / "README.md").read_text()
        for name in ("html-table-header-checker-cli",
                     "html-label-checker-cli"):
            self.assertIn(name, readme)


if __name__ == "__main__":
    unittest.main(verbosity=2)
