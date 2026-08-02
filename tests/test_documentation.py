#!/usr/bin/env python3
"""Bilingual documentation and local Markdown link contracts."""

from __future__ import annotations

import re
import unittest
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"(?<!!)\[[^]]+\]\(([^)]+)\)")


class DocumentationTest(unittest.TestCase):
    def markdown_files(self) -> list[Path]:
        return sorted(
            path
            for path in ROOT.rglob("*.md")
            if ".git" not in path.parts and "dist" not in path.parts
        )

    def test_current_documents_have_full_ukrainian_counterparts(self):
        for english in self.markdown_files():
            relative = english.relative_to(ROOT)
            if "archive" in relative.parts or english.stem.endswith(".uk"):
                continue
            ukrainian = (
                english.with_name("README.uk.md")
                if english.name == "README.md"
                else english.with_name(f"{english.stem}.uk.md")
            )
            self.assertTrue(ukrainian.is_file(), f"missing Ukrainian counterpart: {relative}")
            english_text = english.read_text(encoding="utf-8")
            ukrainian_text = ukrainian.read_text(encoding="utf-8")
            self.assertIn(ukrainian.name, english_text, f"missing UK link: {relative}")
            self.assertIn(english.name, ukrainian_text, f"missing EN link: {ukrainian.relative_to(ROOT)}")
            self.assertGreater(
                len(ukrainian_text),
                len(english_text) * 0.45,
                f"Ukrainian counterpart appears incomplete: {ukrainian.relative_to(ROOT)}",
            )

    def test_local_markdown_links_resolve(self):
        for document in self.markdown_files():
            text = document.read_text(encoding="utf-8")
            for raw_target in LINK.findall(text):
                target = raw_target.strip().strip("<>").split(maxsplit=1)[0]
                if target.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                target = unquote(target.split("#", 1)[0].split("?", 1)[0])
                if not target or "<" in target or ">" in target:
                    continue
                resolved = (document.parent / target).resolve()
                self.assertTrue(
                    resolved.exists(),
                    f"broken local link in {document.relative_to(ROOT)}: {raw_target}",
                )


if __name__ == "__main__":
    unittest.main()
