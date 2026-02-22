"""Site categories and URL mappings for Clutch.co and Sortlist.com.

Hierarchical structure: Service -> Field -> URL path.
Both sites share the same 5 top-level service names for easy merging in the UI.
"""

# ── Clutch.co ────────────────────────────────────────────────────────

CLUTCH_CATEGORIES = {
    "Development": {
        "Custom Software Development": "/developers",
        "Web Development": "/web-developers",
        "App Development": "/app-developers",
        "E-Commerce Development": "/developers/ecommerce",
        "Python & Django": "/developers/python-django",
        "Java": "/developers/java",
        "PHP": "/web-developers/php",
        ".NET": "/developers/dot-net",
        "WordPress": "/developers/wordpress",
        "Flutter": "/developers/flutter",
        "Blockchain": "/developers/blockchain",
        "AR/VR": "/developers/virtual-reality",
        "Freelance Developers": "/developers/freelance",
    },
    "IT Services": {
        "All IT Services": "/it-services",
        "Managed IT (MSP)": "/it-services/msp",
        "Cybersecurity": "/it-services/cybersecurity",
        "IT Staff Augmentation": "/it-services/staff-augmentation",
    },
    "Marketing": {
        "Full-Service Digital": "/agencies/digital",
        "Digital Marketing": "/agencies/digital-marketing",
        "PPC": "/agencies/ppc",
        "Social Media Marketing": "/agencies/social-media-marketing",
        "Content Marketing": "/agencies/content-marketing",
        "Email Marketing": "/agencies/email",
        "PR Firms": "/pr-firms",
    },
    "Design": {
        "Design Agencies": "/agencies/design",
        "Web Design": "/web-designers",
        "UI/UX Design": "/agencies/ui-ux",
        "Logo Design": "/agencies/logo-designers",
    },
    "Business Services": {
        "Consulting": "/consulting",
        "Small Business Consulting": "/consulting/small-business",
        "Boutique Consulting": "/consulting/boutique",
        "HR Services": "/hr",
        "Staffing": "/hr/staffing",
        "Recruiting": "/hr/recruiting",
        "Accounting": "/accounting",
    },
}

# ── Sortlist.com ─────────────────────────────────────────────────────

SORTLIST_CATEGORIES = {
    "Development": {
        "Web Development": "/web-development",
        "App Development": "/app-development",
        "Software Development": "/software-development",
        "E-Commerce Development": "/e-commerce-development",
        "Mobile App Development": "/mobile-app-development",
    },
    "IT Services": {
        "Cloud Consulting": "/cloud-consulting",
        "Cybersecurity": "/cybersecurity",
        "IT Strategy Consulting": "/it-strategy-consulting",
        "Blockchain Consulting": "/blockchain-consulting",
    },
    "Marketing": {
        "Advertising": "/advertising",
        "SEO": "/seo",
        "Social Media": "/social-media",
        "Content Marketing": "/content-marketing",
        "Digital Marketing": "/digital-marketing",
        "Email Marketing": "/email-marketing",
        "Growth Marketing": "/growth-marketing",
    },
    "Design": {
        "Design Agencies": "/design",
        "Web Design": "/web-design",
        "UX Design": "/ux-design",
        "Graphic Design": "/graphic-design",
        "Branding": "/branding",
        "Landing Page Design": "/landing-page-design",
    },
    "Business Services": {
        "Business Consulting": "/business-consulting",
        "HR Consulting": "/hr-consulting",
        "Financial Advisory": "/financial-advisory",
    },
}

# ── Unified site config ──────────────────────────────────────────────

SITES = {
    "Clutch.co": {
        "base_url": "https://clutch.co",
        "categories": CLUTCH_CATEGORIES,
    },
    "Sortlist.com": {
        "base_url": "https://www.sortlist.com",
        "categories": SORTLIST_CATEGORIES,
    },
}


# ── Helper functions ─────────────────────────────────────────────────

def get_site_names() -> list[str]:
    return list(SITES.keys())


def get_all_scrape_tasks(site: str) -> list[tuple[str, str, str]]:
    """Return all (service, field, full_url) tuples for bulk scraping."""
    site_config = SITES[site]
    base = site_config["base_url"]
    tasks = []
    for service, fields in site_config["categories"].items():
        for field, path in fields.items():
            tasks.append((service, field, base + path))
    return tasks


def get_services(site: str) -> list[str]:
    return list(SITES[site]["categories"].keys())


def get_fields(site: str, service: str) -> list[str]:
    return list(SITES[site]["categories"].get(service, {}).keys())


def get_category_url(site: str, service: str, field: str) -> str:
    site_config = SITES[site]
    path = site_config["categories"][service][field]
    return site_config["base_url"] + path


def get_merged_services() -> list[str]:
    """Return union of service names across all sites."""
    all_services = set()
    for site_config in SITES.values():
        all_services.update(site_config["categories"].keys())
    return sorted(all_services)


def get_merged_fields(service: str) -> list[tuple[str, str]]:
    """Return all (field_name, source_site) tuples for a service across both sites."""
    results = []
    for site_name, site_config in SITES.items():
        fields = site_config["categories"].get(service, {})
        for field in fields:
            results.append((field, site_name))
    return results
