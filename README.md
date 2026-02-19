# Scraping-Emails

A free, stealth web scraping engine for B2B lead extraction from Clutch.co and Sortlist.com with automatic email discovery.

## 🚀 Live Demo

**Try it now:** [https://scraping-emails-production.up.railway.app](https://scraping-emails-production.up.railway.app)

## Features

- 📧 Automatic email extraction from company websites
- 🎯 Multi-source scraping (Clutch.co & Sortlist.com)
- 🖥️ Interactive Streamlit dashboard
- 📊 Real-time progress tracking
- 💾 Export to CSV and Excel
- 🐳 Docker support
- 🔒 Stealth browsing with Camoufox (Firefox-based)

## Installation

### Local Setup

```bash
# Clone the repository
git clone https://github.com/AhmedTElKodsh/scraping-emails.git
cd scraping-emails

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install-deps
python -m camoufox fetch

# Run the application
streamlit run app.py
```

### Docker Setup

```bash
# Build and run with Docker Compose
docker-compose up --build

# Access the dashboard at http://localhost:8501
```

## Usage

1. Open the Streamlit dashboard in your browser
2. Select a site (Clutch.co, Sortlist.com, or Both)
3. Choose a category to scrape
4. Click "Start Scraping"
5. Monitor progress in real-time
6. Download results as CSV or Excel

## Project Structure

```
scraping-emails/
├── app.py                  # Main Streamlit application
├── config/
│   ├── categories.py       # Site categories and URL mappings
│   └── email_filters.py    # Email validation rules
├── scrapers/
│   ├── base.py            # Base scraper with browser management
│   ├── clutch.py          # Clutch.co scraper
│   └── sortlist.py        # Sortlist.com scraper
├── extractors/
│   └── email_extractor.py # Email discovery from websites
├── utils/
│   └── export.py          # CSV/Excel export utilities
├── requirements.txt       # Python dependencies
├── Dockerfile            # Docker configuration
└── docker-compose.yml    # Docker Compose setup
```

## Technologies

- **Streamlit** - Interactive web dashboard
- **Camoufox** - Stealth browser automation (Firefox-based)
- **Playwright** - Browser control
- **BeautifulSoup** - HTML parsing
- **Pandas** - Data manipulation
- **Docker** - Containerization

## Deployment

Deployed on [Railway](https://railway.app) with automatic builds from the main branch.

## License

MIT License - feel free to use this project for your own purposes.

## Disclaimer

This tool is for educational purposes. Always respect website terms of service and robots.txt files. Use responsibly and ethically.
