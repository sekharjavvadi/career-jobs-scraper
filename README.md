# Job Scraper

This project scrapes job listings from company career pages and saves them in a uniform CSV format.

## Setup

1. Install the required dependencies:

```bash
pip install -r requirements.txt
```

2. Configure the career page URLs:
   - Open `config.json`
   - Add the career page URLs you want to scrape in the `career_urls` array

## Usage

Run the scraper:

```bash
python job_scraper.py
```

The script will:

1. Load the career page URLs from config.json
2. Scrape job listings from each URL
3. Save the results to `jobs_data.csv`

## Output Format

The CSV file will contain the following columns:

- company: Company name
- title: Job title
- location: Job location
- description: Job description
- url: Direct link to the job posting
- source_url: URL of the career page

## Customization

You may need to customize the selectors in the `scrape_jobs` method of `JobScraper` class based on the HTML structure of the career pages you're scraping. The current implementation uses basic selectors that you'll need to adjust according to the specific websites you're targeting.

## Notes

- The script includes error handling and logging
- Rate limiting and respect for robots.txt are recommended when scraping multiple pages
- Some websites may have anti-scraping measures in place
