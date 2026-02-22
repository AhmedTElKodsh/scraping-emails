"""Comprehensive tests for config.categories module."""

import pytest
from config.categories import get_category_url, get_site_names, get_categories, SITES


class TestSiteConfiguration:
    """Tests for the SITES configuration dict."""

    def test_two_sites_configured(self):
        assert len(SITES) == 2

    def test_clutch_exists(self):
        assert "Clutch.co" in SITES

    def test_sortlist_exists(self):
        assert "Sortlist.com" in SITES

    def test_clutch_has_base_url(self):
        assert SITES["Clutch.co"]["base_url"] == "https://clutch.co"

    def test_sortlist_has_base_url(self):
        assert SITES["Sortlist.com"]["base_url"] == "https://www.sortlist.com"

    def test_clutch_has_5_categories(self):
        assert len(SITES["Clutch.co"]["categories"]) == 5

    def test_sortlist_has_4_categories(self):
        assert len(SITES["Sortlist.com"]["categories"]) == 4

    def test_all_category_paths_start_with_slash(self):
        for site_name, site_config in SITES.items():
            for cat, path in site_config["categories"].items():
                assert path.startswith("/"), f"{site_name}/{cat} path doesn't start with /: {path}"


class TestGetSiteNames:
    def test_returns_list(self):
        result = get_site_names()
        assert isinstance(result, list)

    def test_correct_names(self):
        assert get_site_names() == ["Clutch.co", "Sortlist.com"]


class TestGetCategories:
    def test_clutch_categories(self):
        cats = get_categories("Clutch.co")
        assert "Development" in cats
        assert "IT Services" in cats
        assert "Marketing" in cats
        assert "Design" in cats
        assert "Business Services" in cats

    def test_sortlist_categories(self):
        cats = get_categories("Sortlist.com")
        assert "Advertising & Marketing" in cats
        assert "Creative & Visual" in cats
        assert "Development & Product" in cats
        assert "IT Services" in cats

    def test_invalid_site_raises(self):
        with pytest.raises(KeyError):
            get_categories("Unknown.com")


class TestGetCategoryUrl:
    # Clutch URLs
    @pytest.mark.parametrize("category,expected", [
        ("Development", "https://clutch.co/developers"),
        ("IT Services", "https://clutch.co/it-services"),
        ("Marketing", "https://clutch.co/agencies"),
        ("Design", "https://clutch.co/design"),
        ("Business Services", "https://clutch.co/business-services"),
    ])
    def test_clutch_urls(self, category, expected):
        assert get_category_url("Clutch.co", category) == expected

    # Sortlist URLs
    @pytest.mark.parametrize("category,expected", [
        ("Advertising & Marketing", "https://www.sortlist.com/advertising"),
        ("Creative & Visual", "https://www.sortlist.com/design"),
        ("Development & Product", "https://www.sortlist.com/web-development"),
        ("IT Services", "https://www.sortlist.com/cloud-consulting"),
    ])
    def test_sortlist_urls(self, category, expected):
        assert get_category_url("Sortlist.com", category) == expected

    def test_invalid_site_raises(self):
        with pytest.raises(KeyError):
            get_category_url("Unknown.com", "Development")

    def test_invalid_category_raises(self):
        with pytest.raises(KeyError):
            get_category_url("Clutch.co", "Nonexistent Category")
