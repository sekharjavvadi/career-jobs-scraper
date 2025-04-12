import os
import json
import pandas as pd
from bs4 import BeautifulSoup
import logging
from typing import List, Dict, Optional
from datetime import datetime
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class JobScraper:
    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self.jobs_data = []
        
    def load_config(self) -> List[str]:
        """Load career page URLs from config file"""
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
                return config.get('career_urls', [])
        except FileNotFoundError:
            logger.error(f"Config file {self.config_file} not found")
            return []
        except json.JSONDecodeError:
            logger.error("Invalid JSON in config file")
            return []

    def scrape_jobs(self, url: str) -> List[Dict]:
        """Scrape jobs from a single career page"""
        try:
            with sync_playwright() as p:
                # Launch browser with stealth mode
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                    viewport={'width': 1920, 'height': 1080},
                    device_scale_factor=1,
                )
                
                # Add stealth scripts
                context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                """)
                
                page = context.new_page()
                
                # Set longer timeout for initial load
                page.set_default_timeout(60000)
                
                # Navigate to URL
                logger.info(f"Navigating to {url}")
                try:
                    page.goto(url, wait_until='networkidle', timeout=60000)
                except PlaywrightTimeout:
                    logger.warning(f"Timeout waiting for networkidle on {url}, proceeding anyway")
                
                # Scroll to load dynamic content
                for _ in range(3):
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(2)
                
                # Wait for common job listing selectors
                selectors = [
                    'div[class*="job-"]',
                    'div[class*="career-"]',
                    'div[class*="position-"]',
                    '.job-listing',
                    '.careers-list',
                    '.jobs-list',
                    '.positions-list',
                    '.job-posting',
                    '.career-posting',
                    '.position-posting',
                    '.jobs-list-item',
                    '.career-opportunities',
                    '.vacancy-item'
                ]
                
                for selector in selectors:
                    try:
                        page.wait_for_selector(selector, timeout=5000)
                        break
                    except PlaywrightTimeout:
                        continue
                
                # Get page content
                content = page.content()
                soup = BeautifulSoup(content, 'lxml')
                
                # Try different common selectors for job listings
                job_elements = []
                for selector in selectors:
                    job_elements = soup.select(selector)
                    if job_elements:
                        logger.info(f"Found job elements using selector: {selector}")
                        break
                
                if not job_elements:
                    # Try finding job listings by looking for common patterns
                    job_elements = []
                    patterns = [
                        # Look for elements containing job-related text
                        lambda tag: tag.name in ['div', 'article', 'li'] and any(
                            keyword in (tag.get('class', []) + [tag.get_text().lower()])
                            for keyword in ['job', 'career', 'position', 'vacancy', 'opening']
                        ),
                        # Look for elements with job titles
                        lambda tag: tag.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']) is not None
                    ]
                    
                    for pattern in patterns:
                        job_elements = soup.find_all(pattern)
                        if job_elements:
                            logger.info(f"Found job elements using pattern matching")
                            break
                
                jobs = []
                for job in job_elements:
                    job_data = {
                        'company': self._extract_company_name(url),
                        'title': self._extract_job_title(job),
                        'location': self._extract_location(job),
                        'description': self._extract_description(job),
                        'url': self._extract_job_url(job, url),
                        'source_url': url,
                        'date_posted': self._extract_date_posted(job),
                        'department': self._extract_department(job),
                        'employment_type': self._extract_employment_type(job),
                        'scraped_date': datetime.now().isoformat()
                    }
                    if job_data['title']:  # Only add if we found at least a job title
                        jobs.append(job_data)
                
                # Close browser
                browser.close()
                return jobs
                
        except Exception as e:
            logger.error(f"Error scraping {url}: {str(e)}")
            return []

    def _extract_job_title(self, element) -> str:
        """Extract job title using multiple possible selectors"""
        selectors = [
            'h1, h2, h3, h4, h5, h6',
            '[class*="title"]',
            '[class*="position"]',
            '[class*="role"]',
            '[class*="job-name"]',
            'a'
        ]
        for selector in selectors:
            title = self._extract_text(element, selector)
            if title:
                return title.strip()
        return ""

    def _extract_location(self, element) -> str:
        """Extract job location"""
        location_selectors = [
            '[class*="location"]',
            '[class*="place"]',
            '[class*="city"]',
            '[class*="region"]',
            '[data-location]',
            '[class*="address"]'
        ]
        for selector in location_selectors:
            location = self._extract_text(element, selector)
            if location:
                return location.strip()
        return ""

    def _extract_description(self, element) -> str:
        """Extract job description"""
        desc_selectors = [
            '[class*="description"]',
            '[class*="summary"]',
            '[class*="details"]',
            '[class*="content"]',
            'p'
        ]
        for selector in desc_selectors:
            desc = self._extract_text(element, selector)
            if desc:
                return desc.strip()
        return ""

    def _extract_job_url(self, element, base_url: str) -> str:
        """Extract job URL and make it absolute"""
        try:
            # First try finding a direct link
            link = element.find('a')
            if link and 'href' in link.attrs:
                return urljoin(base_url, link['href'])
            
            # Try finding a link in parent elements
            parent = element.parent
            for _ in range(3):  # Check up to 3 levels up
                if parent:
                    link = parent.find('a')
                    if link and 'href' in link.attrs:
                        return urljoin(base_url, link['href'])
                    parent = parent.parent
            return ""
        except (AttributeError, TypeError):
            return ""

    def _extract_date_posted(self, element) -> Optional[str]:
        """Extract job posting date"""
        date_selectors = [
            '[class*="date"]',
            '[class*="posted"]',
            '[class*="published"]',
            'time',
            '[datetime]'
        ]
        for selector in date_selectors:
            date = self._extract_text(element, selector)
            if date:
                return date.strip()
        return None

    def _extract_department(self, element) -> str:
        """Extract job department"""
        dept_selectors = [
            '[class*="department"]',
            '[class*="team"]',
            '[class*="category"]',
            '[class*="function"]'
        ]
        for selector in dept_selectors:
            dept = self._extract_text(element, selector)
            if dept:
                return dept.strip()
        return ""

    def _extract_employment_type(self, element) -> str:
        """Extract employment type"""
        type_selectors = [
            '[class*="type"]',
            '[class*="employment"]',
            '[class*="contract"]',
            '[class*="work-type"]'
        ]
        for selector in type_selectors:
            emp_type = self._extract_text(element, selector)
            if emp_type:
                return emp_type.strip()
        return ""

    def _extract_text(self, element, selector: str) -> str:
        """Extract text from an element using a selector"""
        try:
            found = element.select_one(selector)
            if not found:
                found = element.find(selector)
            return found.get_text(strip=True) if found else ""
        except (AttributeError, TypeError):
            return ""

    def _extract_company_name(self, url: str) -> str:
        """Extract company name from URL"""
        try:
            domain = url.split('//')[1].split('/')[0]
            company = domain.replace('www.', '').split('.')[0]
            return company.capitalize()
        except:
            return url

    def run(self):
        """Run the scraper for all URLs in config"""
        urls = self.load_config()
        if not urls:
            logger.error("No URLs found in config file")
            return

        for url in urls:
            logger.info(f"Scraping jobs from {url}")
            jobs = self.scrape_jobs(url)
            self.jobs_data.extend(jobs)
            logger.info(f"Found {len(jobs)} jobs from {url}")

        self.save_to_csv()

    def save_to_csv(self):
        """Save scraped jobs to CSV file"""
        if not self.jobs_data:
            logger.warning("No jobs data to save")
            return

        df = pd.DataFrame(self.jobs_data)
        output_file = f"jobs_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df.to_csv(output_file, index=False, encoding='utf-8')
        logger.info(f"Saved {len(self.jobs_data)} jobs to {output_file}")

if __name__ == "__main__":
    scraper = JobScraper()
    scraper.run() 