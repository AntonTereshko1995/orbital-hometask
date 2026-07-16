from __future__ import annotations

from ai.analysis import count_sources_cited


def test_empty_string() -> None:
    assert count_sources_cited("") == 0


def test_no_references() -> None:
    assert count_sources_cited("The parties agree to the following terms.") == 0


def test_section_reference() -> None:
    assert count_sources_cited("See Section 1 for the rent schedule.") == 1


def test_clause_reference() -> None:
    assert count_sources_cited("As per Clause 3 of the agreement.") == 1


def test_page_reference() -> None:
    assert count_sources_cited("The plan is shown on Page 4.") == 1


def test_paragraph_reference() -> None:
    assert count_sources_cited("Refer to Paragraph 2 for obligations.") == 1


def test_multiple_references_same_type() -> None:
    assert count_sources_cited("Section 1, Section 2, and Section 3 apply.") == 3


def test_multiple_references_mixed_types() -> None:
    assert count_sources_cited("Section 1, Section 2, and Clause 3 apply.") == 3


def test_case_insensitive() -> None:
    assert count_sources_cited("SECTION 5 and CLAUSE 2") == 2


def test_partial_keyword_without_digit_not_counted() -> None:
    # "section" without a following digit must not match
    assert count_sources_cited("this section contains no number") == 0


def test_multi_pattern_response() -> None:
    text = "See Section 1, Page 4, Paragraph 7, and Clause 2 for details."
    assert count_sources_cited(text) == 4


def test_section_with_extra_whitespace() -> None:
    # \s+ matches multiple spaces
    assert count_sources_cited("Section  5 applies.") == 1
