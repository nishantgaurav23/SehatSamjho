"""S6.4 — Tests for format_glossary_context().

Pure function tests — no mocking, no async, no I/O.
"""

import inspect

from backend.app.models.schemas import GlossaryEntry


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _entry(
    term: str = "Hypertension",
    vernacular: str = "उच्च रक्तचाप",
    explanation: str = "High blood pressure",
) -> GlossaryEntry:
    return GlossaryEntry(term=term, vernacular=vernacular, explanation=explanation)


# ── Test group 1: Import & Signature ─────────────────────────────────────────


class TestImportAndSignature:
    """FR-1 / FR-5: importable, sync, correct signature."""

    def test_import_format_glossary_context(self):
        from backend.app.services.glossary import format_glossary_context  # noqa: F401

    def test_signature_sync(self):
        from backend.app.services.glossary import format_glossary_context

        assert not inspect.iscoroutinefunction(format_glossary_context)

    def test_return_type_is_str(self):
        from backend.app.services.glossary import format_glossary_context

        result = format_glossary_context([], "Hindi")
        assert isinstance(result, str)


# ── Test group 2: Empty / edge cases ────────────────────────────────────────


class TestEmptyAndEdge:
    """FR-1 edge cases: empty entries, empty language."""

    def test_empty_entries_returns_empty_string(self):
        from backend.app.services.glossary import format_glossary_context

        assert format_glossary_context([], "Hindi") == ""

    def test_no_trailing_newline_on_empty(self):
        from backend.app.services.glossary import format_glossary_context

        result = format_glossary_context([], "Hindi")
        assert result == ""
        assert not result.endswith("\n")

    def test_empty_language_name(self):
        from backend.app.services.glossary import format_glossary_context

        result = format_glossary_context([_entry()], "")
        assert isinstance(result, str)
        assert len(result) > 0


# ── Test group 3: Single entry formatting ────────────────────────────────────


class TestSingleEntry:
    """FR-2 / FR-3: single entry produces header + line + footer."""

    def test_single_entry_format(self):
        from backend.app.services.glossary import format_glossary_context

        result = format_glossary_context([_entry()], "Hindi")
        lines = result.strip().split("\n")
        assert len(lines) == 3  # header, one entry, footer

    def test_line_format_contains_term(self):
        from backend.app.services.glossary import format_glossary_context

        result = format_glossary_context([_entry(term="Diabetes")], "Hindi")
        assert "Term: Diabetes" in result

    def test_line_format_contains_language_arrow(self):
        from backend.app.services.glossary import format_glossary_context

        result = format_glossary_context([_entry()], "Tamil")
        assert "-> Tamil:" in result

    def test_line_format_contains_vernacular(self):
        from backend.app.services.glossary import format_glossary_context

        entry = _entry(vernacular="நீரிழிவு")
        result = format_glossary_context([entry], "Tamil")
        assert "நீரிழிவு" in result

    def test_line_format_contains_explanation(self):
        from backend.app.services.glossary import format_glossary_context

        entry = _entry(explanation="High blood pressure")
        result = format_glossary_context([entry], "Hindi")
        assert "(High blood pressure)" in result


# ── Test group 4: Block structure ────────────────────────────────────────────


class TestBlockStructure:
    """FR-3: header, footer, multiple entries."""

    def test_header_contains_language_name(self):
        from backend.app.services.glossary import format_glossary_context

        result = format_glossary_context([_entry()], "Bengali")
        first_line = result.strip().split("\n")[0]
        assert first_line == "--- Medical Glossary (Bengali) ---"

    def test_footer_separator(self):
        from backend.app.services.glossary import format_glossary_context

        result = format_glossary_context([_entry()], "Hindi")
        last_line = result.strip().split("\n")[-1]
        assert last_line == "---"

    def test_multiple_entries_all_present(self):
        from backend.app.services.glossary import format_glossary_context

        entries = [
            _entry(term="Hypertension"),
            _entry(term="Diabetes"),
            _entry(term="Anemia"),
        ]
        result = format_glossary_context(entries, "Hindi")
        lines = result.strip().split("\n")
        # header + 3 entries + footer = 5
        assert len(lines) == 5

    def test_entries_order_preserved(self):
        from backend.app.services.glossary import format_glossary_context

        entries = [
            _entry(term="Zebra"),
            _entry(term="Alpha"),
            _entry(term="Middle"),
        ]
        result = format_glossary_context(entries, "Hindi")
        lines = result.strip().split("\n")
        # lines[0] = header, lines[1..3] = entries, lines[4] = footer
        assert "Zebra" in lines[1]
        assert "Alpha" in lines[2]
        assert "Middle" in lines[3]

    def test_duplicate_entries_all_rendered(self):
        from backend.app.services.glossary import format_glossary_context

        entries = [_entry(term="Diabetes"), _entry(term="Diabetes")]
        result = format_glossary_context(entries, "Hindi")
        lines = result.strip().split("\n")
        # header + 2 entries + footer = 4
        assert len(lines) == 4


# ── Test group 5: Truncation ────────────────────────────────────────────────


class TestTruncation:
    """FR-4: token budget enforcement (~2000 chars)."""

    def _make_long_entries(self, n: int = 50) -> list[GlossaryEntry]:
        """Create N entries with long explanations to exceed 2000 chars."""
        return [
            _entry(
                term=f"MedicalTerm{i}",
                vernacular=f"वर्णाक्षर{i}" * 5,
                explanation=f"A very detailed explanation for term number {i} that is long" * 2,
            )
            for i in range(n)
        ]

    def test_truncation_over_budget(self):
        from backend.app.services.glossary import format_glossary_context

        entries = self._make_long_entries(50)
        result = format_glossary_context(entries, "Hindi")
        # Should have fewer entry lines than 50 due to truncation
        lines = result.strip().split("\n")
        # Subtract header, footer, and truncation message
        entry_lines = [ln for ln in lines[1:-1] if ln.startswith("Term:")]
        assert len(entry_lines) < 50

    def test_truncation_message(self):
        from backend.app.services.glossary import format_glossary_context

        entries = self._make_long_entries(50)
        result = format_glossary_context(entries, "Hindi")
        assert "more terms omitted)" in result

    def test_truncation_keeps_header_footer(self):
        from backend.app.services.glossary import format_glossary_context

        entries = self._make_long_entries(50)
        result = format_glossary_context(entries, "Hindi")
        lines = result.strip().split("\n")
        assert lines[0] == "--- Medical Glossary (Hindi) ---"
        assert lines[-1] == "---"

    def test_no_truncation_under_budget(self):
        from backend.app.services.glossary import format_glossary_context

        entries = [_entry(term="Fever")]
        result = format_glossary_context(entries, "Hindi")
        assert "omitted" not in result
