"""Comprehensive tests for utils.export module."""

import pytest
import pandas as pd
from utils.export import to_csv, to_excel


@pytest.fixture
def sample_df():
    """Standard test DataFrame."""
    return pd.DataFrame([
        {"name": "Acme Corp", "email": "info@acme.com", "rating": "4.5", "location": "New York, US"},
        {"name": "Beta Inc", "email": "Unreachable", "rating": "4.0", "location": "London, UK"},
        {"name": "Gamma LLC", "email": "hello@gamma.io", "rating": "5.0", "location": "Berlin, Germany"},
    ])


@pytest.fixture
def empty_df():
    """Empty DataFrame with columns."""
    return pd.DataFrame(columns=["name", "email", "rating"])


@pytest.fixture
def unicode_df():
    """DataFrame with international characters."""
    return pd.DataFrame([
        {"name": "Café Résumé", "location": "Zürich, Switzerland"},
        {"name": "Poznań Studio", "location": "Poznań, Poland"},
        {"name": "日本語会社", "location": "Tokyo, Japan"},
    ])


class TestToCsv:
    def test_returns_bytes(self, sample_df):
        result = to_csv(sample_df)
        assert isinstance(result, bytes)

    def test_contains_data(self, sample_df):
        result = to_csv(sample_df)
        text = result.decode("utf-8-sig")
        assert "Acme Corp" in text
        assert "info@acme.com" in text
        assert "4.5" in text

    def test_contains_header(self, sample_df):
        result = to_csv(sample_df)
        text = result.decode("utf-8-sig")
        first_line = text.split("\n")[0]
        assert "name" in first_line
        assert "email" in first_line

    def test_correct_row_count(self, sample_df):
        result = to_csv(sample_df)
        text = result.decode("utf-8-sig").strip()
        lines = text.split("\n")
        assert len(lines) == 4  # header + 3 data rows

    def test_empty_dataframe(self, empty_df):
        result = to_csv(empty_df)
        assert isinstance(result, bytes)
        text = result.decode("utf-8-sig").strip()
        assert "name" in text  # header still present

    def test_unicode_content(self, unicode_df):
        result = to_csv(unicode_df)
        text = result.decode("utf-8-sig")
        assert "Zürich" in text
        assert "Poznań" in text

    def test_no_index_column(self, sample_df):
        result = to_csv(sample_df)
        text = result.decode("utf-8-sig")
        # First column should be "name", not a numeric index
        lines = text.strip().split("\n")
        assert not lines[1].startswith("0")

    def test_bom_present(self, sample_df):
        """UTF-8 BOM is included for Excel compatibility."""
        result = to_csv(sample_df)
        assert result[:3] == b"\xef\xbb\xbf"


class TestToExcel:
    def test_returns_bytes(self, sample_df):
        result = to_excel(sample_df)
        assert isinstance(result, bytes)

    def test_non_empty(self, sample_df):
        result = to_excel(sample_df)
        assert len(result) > 100  # Excel files have metadata overhead

    def test_valid_xlsx_magic_bytes(self, sample_df):
        result = to_excel(sample_df)
        # XLSX files are ZIP archives starting with PK
        assert result[:2] == b"PK"

    def test_roundtrip(self, sample_df):
        """Write to Excel then read back — data should match."""
        import io
        result = to_excel(sample_df)
        df_back = pd.read_excel(io.BytesIO(result), sheet_name="Companies")
        assert list(df_back.columns) == list(sample_df.columns)
        assert len(df_back) == len(sample_df)
        assert df_back.iloc[0]["name"] == "Acme Corp"

    def test_empty_dataframe(self, empty_df):
        result = to_excel(empty_df)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_unicode_roundtrip(self, unicode_df):
        import io
        result = to_excel(unicode_df)
        df_back = pd.read_excel(io.BytesIO(result), sheet_name="Companies")
        assert df_back.iloc[0]["name"] == "Café Résumé"
        assert df_back.iloc[1]["location"] == "Poznań, Poland"

    def test_sheet_name_is_companies(self, sample_df):
        import io
        result = to_excel(sample_df)
        xls = pd.ExcelFile(io.BytesIO(result))
        assert "Companies" in xls.sheet_names
