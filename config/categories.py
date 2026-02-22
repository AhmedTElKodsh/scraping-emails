"""Site categories and URL mappings for Clutch.co and Sortlist.com."""

SITES = {
    "Clutch.co": {
        "base_url": "https://clutch.co",
        "categories": {
            "Development": "/developers",
            "IT Services": "/it-services",
            "Marketing": "/agencies",
            "Design": "/design",
            "Business Services": "/business-services",
        },
    },
    "Sortlist.com": {
        "base_url": "https://www.sortlist.com",
        "categories": {
            "Advertising & Marketing": "/advertising",
            "Creative & Visual": "/design",
            "Development & Product": "/web-development",
            "IT Services": "/cloud-consulting",
        },
    },
}


def get_category_url(site: str, category: str) -> str:
    """Build the full URL for a site + category combination."""
    site_config = SITES[site]
    return site_config["base_url"] + site_config["categories"][category]


def get_site_names() -> list[str]:
    """Return available site names."""
    return list(SITES.keys())


def get_categories(site: str) -> list[str]:
    """Return available categories for a given site."""
    return list(SITES[site]["categories"].keys())
