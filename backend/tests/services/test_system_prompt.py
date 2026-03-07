"""Tests for S7.2 — System Prompt (TRANSLATION_SYSTEM_PROMPT + _build_system_prompt).

Pure-function tests — no mocking needed. The constant is a template string and
_build_system_prompt() is a pure string-formatting function.
"""

from __future__ import annotations

import inspect


# ---------------------------------------------------------------------------
# 1-4: TRANSLATION_SYSTEM_PROMPT constant
# ---------------------------------------------------------------------------


def test_translation_system_prompt_importable():
    """TRANSLATION_SYSTEM_PROMPT is importable from translation module."""
    from backend.app.services.translation import TRANSLATION_SYSTEM_PROMPT  # noqa: F401


def test_translation_system_prompt_is_string():
    """TRANSLATION_SYSTEM_PROMPT is a str."""
    from backend.app.services.translation import TRANSLATION_SYSTEM_PROMPT

    assert isinstance(TRANSLATION_SYSTEM_PROMPT, str)


def test_translation_system_prompt_non_empty():
    """TRANSLATION_SYSTEM_PROMPT has length > 100 (meaningful content)."""
    from backend.app.services.translation import TRANSLATION_SYSTEM_PROMPT

    assert len(TRANSLATION_SYSTEM_PROMPT) > 100


def test_translation_system_prompt_has_placeholder():
    """TRANSLATION_SYSTEM_PROMPT contains {glossary_context} placeholder."""
    from backend.app.services.translation import TRANSLATION_SYSTEM_PROMPT

    assert "{glossary_context}" in TRANSLATION_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# 5-8: _build_system_prompt basics
# ---------------------------------------------------------------------------


def test_build_system_prompt_importable():
    """_build_system_prompt is importable from translation module."""
    from backend.app.services.translation import _build_system_prompt  # noqa: F401


def test_build_system_prompt_callable():
    """_build_system_prompt is callable."""
    from backend.app.services.translation import _build_system_prompt

    assert callable(_build_system_prompt)


def test_build_system_prompt_signature():
    """_build_system_prompt accepts glossary_context kwarg with default ''."""
    from backend.app.services.translation import _build_system_prompt

    sig = inspect.signature(_build_system_prompt)
    param = sig.parameters["glossary_context"]
    assert param.default == ""


def test_build_system_prompt_returns_string():
    """_build_system_prompt returns a str."""
    from backend.app.services.translation import _build_system_prompt

    result = _build_system_prompt()
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# 9-13: Glossary injection behaviour
# ---------------------------------------------------------------------------


def test_build_system_prompt_empty_glossary():
    """Empty glossary → no 'Use the following' glossary header in output."""
    from backend.app.services.translation import _build_system_prompt

    result = _build_system_prompt(glossary_context="")
    assert "Use the following" not in result


def test_build_system_prompt_with_glossary():
    """Non-empty glossary → glossary text appears in output."""
    from backend.app.services.translation import _build_system_prompt

    glossary = "Metformin (मेटफॉर्मिन): a diabetes medicine"
    result = _build_system_prompt(glossary_context=glossary)
    assert glossary in result


def test_build_system_prompt_glossary_section_present():
    """Non-empty glossary → output contains 'verified medical term translations'."""
    from backend.app.services.translation import _build_system_prompt

    result = _build_system_prompt(glossary_context="some glossary entries")
    assert "verified medical term translations" in result


def test_build_system_prompt_none_glossary():
    """glossary_context=None does not raise and omits glossary section."""
    from backend.app.services.translation import _build_system_prompt

    result = _build_system_prompt(glossary_context=None)
    assert "Use the following" not in result
    assert isinstance(result, str)


def test_build_system_prompt_whitespace_glossary():
    """Whitespace-only glossary → omits glossary section."""
    from backend.app.services.translation import _build_system_prompt

    result = _build_system_prompt(glossary_context="   ")
    assert "Use the following" not in result


# ---------------------------------------------------------------------------
# 14-19: Prompt quality — all 6 rules present
# ---------------------------------------------------------------------------


def test_prompt_contains_persona():
    """Rendered prompt contains 'health educator'."""
    from backend.app.services.translation import _build_system_prompt

    result = _build_system_prompt()
    assert "health educator" in result


def test_prompt_contains_drug_name_rule():
    """Rendered prompt mentions keeping drug names in English."""
    from backend.app.services.translation import _build_system_prompt

    result = _build_system_prompt()
    assert "drug names" in result.lower()
    assert "English" in result


def test_prompt_contains_no_advice_rule():
    """Rendered prompt mentions not adding clinical advice."""
    from backend.app.services.translation import _build_system_prompt

    result = _build_system_prompt()
    assert "clinical advice" in result.lower() or "advice" in result.lower()


def test_prompt_contains_confidence_flag_rule():
    """Rendered prompt mentions confidence and warning."""
    from backend.app.services.translation import _build_system_prompt

    result = _build_system_prompt()
    assert "confidence" in result.lower()
    assert "warning" in result.lower() or "verify" in result.lower()


def test_prompt_contains_word_limit_rule():
    """Rendered prompt mentions word limit."""
    from backend.app.services.translation import _build_system_prompt

    result = _build_system_prompt()
    assert "400 words" in result


def test_prompt_contains_disclaimer_rule():
    """Rendered prompt mentions disclaimer or consult."""
    from backend.app.services.translation import _build_system_prompt

    result = _build_system_prompt()
    result_lower = result.lower()
    assert "disclaimer" in result_lower or "consult" in result_lower


# ---------------------------------------------------------------------------
# 20: No remaining placeholders
# ---------------------------------------------------------------------------


def test_prompt_no_remaining_placeholders():
    """No { or } template syntax in rendered output (with or without glossary)."""
    from backend.app.services.translation import _build_system_prompt

    # Without glossary
    result_empty = _build_system_prompt(glossary_context="")
    assert "{" not in result_empty
    assert "}" not in result_empty

    # With glossary
    result_with = _build_system_prompt(glossary_context="some glossary text")
    assert "{" not in result_with
    assert "}" not in result_with
