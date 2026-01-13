"""
NYC Housing Connect Lottery Bot

Automates the process of:
1. Scraping available lottery IDs (rentals and sales) - NO LOGIN REQUIRED
2. Logging in and applying to eligible lotteries
"""

import os
import re
import json
import time
import random
from typing import Optional
from dataclasses import dataclass
from playwright.sync_api import sync_playwright, Page, Browser, TimeoutError as PlaywrightTimeout

from dotenv import load_dotenv

load_dotenv()


@dataclass
class LotteryInfo:
    """Information about a lottery listing"""
    id: str
    title: str
    lottery_type: str  # 'rental' or 'sale'
    location: Optional[str] = None
    units_available: Optional[int] = None
    days_until_closing: Optional[int] = None
    min_income: Optional[int] = None
    max_income: Optional[int] = None
    is_applied: bool = False
    url: Optional[str] = None


class HousingConnectBot:
    """Bot to automate NYC Housing Connect lottery applications"""
    
    BASE_URL = "https://housingconnect.nyc.gov/PublicWeb"
    LOGIN_URL = f"{BASE_URL}/login"
    LOTTERIES_URL = f"{BASE_URL}/search-lotteries"
    
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.username = os.getenv("USERNAME")
        self.password = os.getenv("PASSWORD")
        # Support both SALARY and ANNUAL_INCOME env variables
        self.annual_income = int(os.getenv("SALARY") or os.getenv("ANNUAL_INCOME") or 50000)
        
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def start(self):
        """Start the browser"""
        self.playwright = sync_playwright().start()
        
        # Simple browser launch - no fancy args
        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            slow_mo=100  # Slower to appear more human-like and avoid rate limits
        )
        
        # Create a simple page
        self.page = self.browser.new_page(
            viewport={'width': 1280, 'height': 800}
        )
        self.page.set_default_timeout(60000)  # 60 second default timeout
        print("Browser started successfully")
    
    def close(self):
        """Close the browser"""
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
    
    def navigate_to_lotteries(self, lottery_type: str = "rental") -> bool:
        """
        Navigate to the lotteries page (NO LOGIN REQUIRED)
        lottery_type: 'rental' or 'sale'
        """
        print(f"Navigating to {lottery_type} lotteries...")
        self.page.goto(self.LOTTERIES_URL)
        
        # Wait for page to load
        time.sleep(3)
        
        # Wait for lottery cards to appear
        try:
            self.page.wait_for_selector('app-lottery-grid-card', timeout=15000)
            print("Lottery cards loaded")
        except PlaywrightTimeout:
            print("Timeout waiting for lottery cards, trying to continue...")
        
        # Click on the appropriate tab
        tab_text = "Rentals" if lottery_type == "rental" else "Sales"
        
        try:
            # The tab is a span with class font-lg
            tab = self.page.query_selector(f'span.font-lg:text-is("{tab_text}")')
            if tab:
                tab.click()
                time.sleep(2)
                print(f"Clicked on {tab_text} tab")
                return True
            else:
                # Try broader selector
                tab = self.page.query_selector(f'text="{tab_text}"')
                if tab:
                    tab.click()
                    time.sleep(2)
                    print(f"Clicked on {tab_text} tab (alt)")
                    return True
        except Exception as e:
            print(f"Could not click tab: {e}")
        
        return True
    
    def _get_total_pages(self) -> int:
        """Get total number of pages from pagination"""
        try:
            # Look for pagination info like "1 / 4"
            pagination_text = self.page.query_selector('.small-screen')
            if pagination_text:
                text = pagination_text.text_content()
                print(f"Pagination text: {text}")
                match = re.search(r'(\d+)\s*/\s*(\d+)', text)
                if match:
                    return int(match.group(2))
        except Exception as e:
            print(f"Error getting total pages: {e}")
        
        return 1
    
    def _go_to_page(self, page_num: int) -> bool:
        """Navigate to a specific page"""
        try:
            # Get current first lottery ID to detect page change
            first_card = self.page.query_selector('app-lottery-grid-card img.card-image')
            old_src = first_card.get_attribute('src') if first_card else None
            
            # Find and click the page link
            page_link = self.page.query_selector(f'.ngx-pagination li a >> text="{page_num}"')
            if not page_link:
                # Try alternative selector
                links = self.page.query_selector_all('.ngx-pagination li a')
                for link in links:
                    if link.text_content().strip() == str(page_num):
                        page_link = link
                        break
            
            if page_link:
                page_link.click()
                
                # Wait for page content to actually change
                for _ in range(10):  # Wait up to 5 seconds
                    time.sleep(0.5)
                    new_first_card = self.page.query_selector('app-lottery-grid-card img.card-image')
                    new_src = new_first_card.get_attribute('src') if new_first_card else None
                    if new_src != old_src:
                        time.sleep(0.5)  # Small additional wait for full render
                        return True
                
                print(f"  Warning: Page content may not have changed")
                return True
        except Exception as e:
            print(f"Error navigating to page {page_num}: {e}")
        return False
    
    def get_lottery_ids(self, lottery_type: str = "rental") -> list[LotteryInfo]:
        """
        Get all lottery IDs from all pages (NO LOGIN REQUIRED)
        lottery_type: 'rental' or 'sale'
        Returns list of LotteryInfo objects
        """
        self.navigate_to_lotteries(lottery_type)
        
        all_lotteries = []
        seen_ids = set()
        
        # Get total number of pages
        total_pages = self._get_total_pages()
        print(f"Found {total_pages} pages of {lottery_type} lotteries")
        
        for page_num in range(1, total_pages + 1):
            if page_num > 1:
                print(f"Navigating to page {page_num}...")
                self._go_to_page(page_num)
            
            # Get lotteries from current page
            page_lotteries = self._get_lotteries_from_current_page(lottery_type)
            
            # Deduplicate - only add new lotteries
            new_count = 0
            for lottery in page_lotteries:
                if lottery.id not in seen_ids:
                    seen_ids.add(lottery.id)
                    all_lotteries.append(lottery)
                    new_count += 1
            
            print(f"  Page {page_num}: Found {len(page_lotteries)} cards, {new_count} new lotteries")
        
        print(f"Total: Found {len(all_lotteries)} unique {lottery_type} lotteries")
        return all_lotteries
    
    def _get_lotteries_from_current_page(self, lottery_type: str) -> list[LotteryInfo]:
        """Get all lotteries from the current page"""
        lotteries = []
        time.sleep(1)
        
        # Find all lottery cards
        cards = self.page.query_selector_all('app-lottery-grid-card')
        print(f"  Found {len(cards)} cards on page")
        
        if not cards:
            return []
        
        for i, card in enumerate(cards):
            lottery_info = self._parse_lottery_card(card, lottery_type)
            if lottery_info:
                lotteries.append(lottery_info)
                print(f"    [{lottery_info.id}] {lottery_info.title}")
        
        return lotteries
    
    def _parse_lottery_card(self, card, lottery_type: str) -> Optional[LotteryInfo]:
        """Parse a single lottery card element"""
        try:
            lottery_id = None
            title = "Unknown"
            location = None
            units = None
            days_closing = None
            is_applied = False
            
            # Extract lottery ID from image src URL
            # Example: src="https://a806-housingconnectapi.nyc.gov/MailTemplates/photos/34926806.png"
            img = card.query_selector('img.card-image')
            if img:
                src = img.get_attribute('src')
                if src:
                    match = re.search(r'/photos/(\d+)\.', src)
                    if match:
                        lottery_id = match.group(1)
            
            # Get title from .title.title-h3
            title_el = card.query_selector('.title.title-h3')
            if title_el:
                title = title_el.text_content().strip()
            
            # Get location from .location
            location_el = card.query_selector('.location')
            if location_el:
                location = location_el.text_content().strip()
            
            # Get units available
            units_el = card.query_selector('.pb-xs.title-h6')
            if units_el:
                units_text = units_el.text_content()
                match = re.search(r'(\d+)\s*Unit', units_text)
                if match:
                    units = int(match.group(1))
            
            # Get days until closing
            closing_el = card.query_selector('.prefix.title-h4')
            if closing_el:
                closing_text = closing_el.text_content()
                match = re.search(r'(\d+)\s*days?', closing_text, re.IGNORECASE)
                if match:
                    days_closing = int(match.group(1))
            
            # Check if already applied
            applied_btn = card.query_selector('button.btn-grey-90')
            if applied_btn:
                btn_text = applied_btn.text_content().strip()
                if 'Applied' in btn_text:
                    is_applied = True
            
            if lottery_id:
                return LotteryInfo(
                    id=lottery_id,
                    title=title,
                    lottery_type=lottery_type,
                    location=location,
                    units_available=units,
                    days_until_closing=days_closing,
                    is_applied=is_applied,
                    url=f"{self.BASE_URL}/lottery-details/{lottery_id}"
                )
                
        except Exception as e:
            print(f"Error parsing card: {e}")
        
        return None
    
    def _parse_income_range(self, text: str) -> tuple[Optional[int], Optional[int]]:
        """Parse income range from text like 'Eligible Income: $32,195 - $226,800'"""
        match = re.search(r'Eligible Income:?\s*\$?([\d,]+)\s*-\s*\$?([\d,]+)', text, re.IGNORECASE)
        if match:
            min_income = int(match.group(1).replace(',', ''))
            max_income = int(match.group(2).replace(',', ''))
            return min_income, max_income
        return None, None
    
    # ========== LOGIN AND APPLY METHODS (Require credentials) ==========
    
    def login(self) -> bool:
        """
        Login to Housing Connect
        
        Flow:
        1. Go to main page
        2. Click login link (redirects to external auth)
        3. Fill credentials on auth page
        4. Submit and wait for redirect back
        """
        if not self.username or not self.password:
            print("ERROR: USERNAME and PASSWORD must be set in .env file")
            return False
        
        print(f"Step 1: Navigating to main page...")
        self.page.goto(self.BASE_URL)
        time.sleep(3)
        
        try:
            # Step 2: Find and click login link
            print("Step 2: Looking for login link...")
            login_link = self.page.query_selector('a:has-text("Log In"), a:has-text("Login"), a:has-text("Sign In")')
            
            if login_link:
                login_link.click()
                time.sleep(3)
                print(f"  Redirected to: {self.page.url[:60]}...")
            else:
                print("  Could not find login link")
                return False
            
            # Step 3: Wait for and fill login form
            print("Step 3: Filling login form...")
            
            # Wait for the external auth page to load
            email_input = self.page.wait_for_selector(
                'input[type="email"], input[type="text"], input[name="email"], input#email',
                timeout=10000
            )
            
            password_input = self.page.query_selector('input[type="password"]')
            
            if not email_input or not password_input:
                print("  Could not find login form fields")
                return False
            
            # Fill credentials
            email_input.fill(self.username)
            time.sleep(0.5)
            password_input.fill(self.password)
            time.sleep(0.5)
            
            # Step 4: Submit login
            print("Step 4: Submitting login...")
            submit_btn = self.page.query_selector(
                'button[type="submit"], input[type="submit"], button:has-text("Log In"), button:has-text("Login")'
            )
            
            if submit_btn:
                submit_btn.click()
            else:
                # Try pressing Enter
                password_input.press('Enter')
            
            # Wait for redirect back to main site
            time.sleep(5)
            
            # Check if login succeeded (should be back on main site with tokens)
            current_url = self.page.url
            if 'housingconnect.nyc.gov/PublicWeb' in current_url and 'id4/account/login' not in current_url:
                print("✓ Login successful!")
                return True
            else:
                print(f"✗ Login may have failed. Current URL: {current_url[:60]}...")
                return False
                
        except Exception as e:
            print(f"Login error: {e}")
            return False
    
    def apply_to_lottery_by_click(self, card_index: int, lottery_type: str = "rental") -> dict:
        """
        Apply to a lottery by clicking through the UI (REQUIRES LOGIN)
        
        Args:
            card_index: Index of the card on the current page (0-based)
            lottery_type: 'rental' or 'sale'
        
        Returns dict with result info
        """
        result = {
            'success': False,
            'message': '',
            'already_applied': False,
            'eligible': True,
            'title': 'Unknown'
        }
        
        # Make sure we're on the lotteries page
        if 'search-lotteries' not in self.page.url:
            self.navigate_to_lotteries(lottery_type)
        
        # Get the card
        cards = self.page.query_selector_all('app-lottery-grid-card')
        if card_index >= len(cards):
            result['message'] = f"Card index {card_index} out of range"
            return result
        
        card = cards[card_index]
        
        # Get title
        title_el = card.query_selector('.title.title-h3')
        result['title'] = title_el.text_content().strip() if title_el else "Unknown"
        print(f"\nProcessing: {result['title']}")
        
        # Check if already applied (on the card)
        applied_btn = card.query_selector('button.btn-grey-90')
        if applied_btn and 'Applied' in (applied_btn.text_content() or ''):
            result['already_applied'] = True
            result['message'] = "Already applied"
            print(f"  ⚠ Already applied (skipping)")
            return result
        
        # Hover and click View Details
        card.hover()
        time.sleep(0.5)
        
        view_btn = card.query_selector('button:has-text("View Details")')
        if not view_btn:
            result['message'] = "Could not find View Details button"
            print(f"  ✗ {result['message']}")
            return result
        
        view_btn.click()
        
        # Wait for detail page to fully load (longer timeout for rate-limited pages)
        print(f"  Waiting for detail page to load...")
        time.sleep(random.uniform(3, 5))  # Initial wait for SPA navigation
        
        try:
            # Wait for any of these indicators: Apply Now button, Applied button, or income text
            self.page.wait_for_selector(
                'a.btn-primary:has-text("Apply Now"), button.btn-grey-90:has-text("Applied"), '
                'div:has-text("Eligible Income"), .col-md-6:has-text("Eligible Income")',
                timeout=45000
            )
        except PlaywrightTimeout:
            print(f"  Warning: Timeout waiting for detail page content, retrying...")
            self.page.reload()
            time.sleep(random.uniform(5, 8))
            try:
                self.page.wait_for_selector(
                    'a.btn-primary:has-text("Apply Now"), button.btn-grey-90:has-text("Applied")',
                    timeout=45000
                )
            except PlaywrightTimeout:
                print(f"  Still waiting, giving extra time...")
                time.sleep(10)
        
        time.sleep(random.uniform(2, 4))  # Extra settle time for SPA rendering
        
        # Check if already applied (on detail page) - check multiple selectors
        applied_indicator = self.page.query_selector('button.btn-grey-90:has-text("Applied")')
        if not applied_indicator:
            # Try other selectors for "Applied" status
            applied_indicator = self.page.query_selector('button:has-text("Applied")')
        if not applied_indicator:
            # Check if page text contains "Applied" prominently
            page_text_check = self.page.text_content('body') or ''
            if 'You have already applied' in page_text_check or 'Application Submitted' in page_text_check:
                applied_indicator = True
        
        if applied_indicator:
            result['already_applied'] = True
            result['message'] = "Already applied"
            print(f"  ⚠ Already applied (detail page)")
            return result
        
        # Now on detail page - check eligibility
        page_text = self.page.text_content('body') or ''
        min_income, max_income = self._parse_income_range(page_text)
        
        if min_income is not None and max_income is not None:
            if not (min_income <= self.annual_income <= max_income):
                result['eligible'] = False
                result['message'] = f"Not eligible: ${self.annual_income:,} outside ${min_income:,} - ${max_income:,}"
                print(f"  ✗ {result['message']}")
                return result
            print(f"  ✓ Eligible: ${self.annual_income:,} within ${min_income:,} - ${max_income:,}")
        
        # Find Apply Now button
        # Selector: <a class="btn btn-primary m-btn m-btn--icon m-btn--pill mt-sm">Apply Now</a>
        apply_btn = self.page.query_selector('a.btn.btn-primary:has-text("Apply Now")')
        if not apply_btn:
            apply_btn = self.page.query_selector('a.btn-primary:has-text("Apply Now")')
        if not apply_btn:
            apply_btn = self.page.query_selector('a:has-text("Apply Now")')
        
        if not apply_btn:
            result['message'] = "Could not find Apply Now button"
            print(f"  ✗ {result['message']}")
            return result
        
        print(f"  Clicking Apply Now...")
        apply_btn.click()
        time.sleep(2)
        
        # Handle confirmation dialog - checkbox and Submit button
        try:
            # Wait for the checkbox to appear
            self.page.wait_for_selector('.mat-checkbox-inner-container', timeout=5000)
            
            # Click specifically on the checkbox frame/box, NOT the label text (which has a link)
            # The .mat-checkbox-inner-container contains the actual clickable box
            checkbox_box = self.page.query_selector('.mat-checkbox-inner-container')
            if checkbox_box:
                print(f"  Clicking agreement checkbox...")
                checkbox_box.click()
                time.sleep(0.5)
            
            # Click Submit button
            submit_btn = self.page.query_selector('button:has-text("Submit"), span:has-text("Submit")')
            if submit_btn:
                # If it's a span, get the parent button
                tag_name = submit_btn.evaluate('el => el.tagName')
                if tag_name == 'SPAN':
                    submit_btn = self.page.query_selector('button:has(span:has-text("Submit"))')
                
                if submit_btn:
                    print(f"  Clicking Submit...")
                    submit_btn.click()
                    time.sleep(3)
        except PlaywrightTimeout:
            # No confirmation dialog, continue
            print(f"  No confirmation dialog found")
        
        # Check for success (Applied button should now appear)
        applied_check = self.page.query_selector('button.btn-grey-90:has-text("Applied")')
        if applied_check:
            result['success'] = True
            result['message'] = "Successfully applied!"
            print(f"  ✓ {result['message']}")
        else:
            # May have been redirected to login - check URL
            if 'login' in self.page.url.lower() or 'id4/account' in self.page.url.lower():
                result['message'] = "Redirected to login - not logged in"
                print(f"  ⚠ {result['message']}")
            else:
                result['success'] = True
                result['message'] = "Application submitted (unverified)"
                print(f"  ? {result['message']}")
        
        # Navigate back to lotteries list
        print(f"  Navigating back to list...")
        self.page.goto(self.LOTTERIES_URL)
        time.sleep(random.uniform(3, 5))
        
        try:
            self.page.wait_for_selector('app-lottery-grid-card', timeout=45000)
        except PlaywrightTimeout:
            print(f"  Timeout on list, retrying...")
            self.page.reload()
            time.sleep(random.uniform(5, 8))
            self.page.wait_for_selector('app-lottery-grid-card', timeout=60000)
        
        # Click the appropriate tab
        if lottery_type == "sale":
            tab = self.page.query_selector('span.font-lg:text-is("Sales")')
        else:
            tab = self.page.query_selector('span.font-lg:text-is("Rentals")')
        if tab:
            tab.click()
            time.sleep(random.uniform(2, 3))
        
        return result
    
    def apply_to_all_lotteries(self, lottery_type: str = "rental") -> list[dict]:
        """
        Apply to all eligible lotteries by clicking through each one
        
        MUST BE LOGGED IN FIRST
        """
        print(f"\n{'='*60}")
        print(f"APPLYING TO ALL {lottery_type.upper()} LOTTERIES")
        print(f"{'='*60}\n")
        
        self.navigate_to_lotteries(lottery_type)
        
        all_results = []
        total_pages = self._get_total_pages()
        
        for page_num in range(1, total_pages + 1):
            print(f"\n--- Page {page_num} of {total_pages} ---")
            
            if page_num > 1:
                self._go_to_page(page_num)
            
            # Get number of cards on this page
            cards = self.page.query_selector_all('app-lottery-grid-card')
            num_cards = len(cards)
            print(f"Found {num_cards} lotteries on this page")
            
            for i in range(num_cards):
                # Navigate back to list page before each card
                if 'search-lotteries' not in self.page.url:
                    self.page.goto(self.LOTTERIES_URL)
                    time.sleep(2)
                    self.page.wait_for_selector('app-lottery-grid-card', timeout=15000)
                    
                    # Click correct tab
                    tab_text = "Rentals" if lottery_type == "rental" else "Sales"
                    tab = self.page.query_selector(f'span.font-lg:text-is("{tab_text}")')
                    if tab:
                        tab.click()
                        time.sleep(1)
                    
                    # Go to correct page
                    if page_num > 1:
                        self._go_to_page(page_num)
                
                result = self.apply_to_lottery_by_click(i, lottery_type)
                all_results.append(result)
                
                # Small delay between applications
                time.sleep(1)
        
        # Summary
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        
        applied = sum(1 for r in all_results if r['success'])
        already = sum(1 for r in all_results if r['already_applied'])
        not_eligible = sum(1 for r in all_results if not r['eligible'])
        failed = sum(1 for r in all_results if not r['success'] and not r['already_applied'] and r['eligible'])
        
        print(f"\n  ✓ Newly applied: {applied}")
        print(f"  ⚠ Already applied: {already}")
        print(f"  ✗ Not eligible: {not_eligible}")
        print(f"  ? Failed: {failed}")
        print(f"\n  Total processed: {len(all_results)}")
        
        return all_results


def get_all_lottery_ids(headless: bool = False) -> tuple[list[LotteryInfo], list[LotteryInfo]]:
    """Get all lottery info (NO LOGIN REQUIRED)"""
    with HousingConnectBot(headless=headless) as bot:
        rental_lotteries = bot.get_lottery_ids("rental")
        sale_lotteries = bot.get_lottery_ids("sale")
        return rental_lotteries, sale_lotteries


def check_and_apply(lottery_id: str, headless: bool = False) -> dict:
    """Login and apply to a lottery"""
    with HousingConnectBot(headless=headless) as bot:
        if not bot.login():
            return {'success': False, 'message': 'Login failed', 'lottery_id': lottery_id}
        return bot.apply_to_lottery(lottery_id)


if __name__ == "__main__":
    print("NYC Housing Connect Lottery Bot")
    print("================================\n")
    
    rental_lotteries, sale_lotteries = get_all_lottery_ids(headless=False)
    
    rental_ids = [l.id for l in rental_lotteries]
    sale_ids = [l.id for l in sale_lotteries]
    
    print(f"\nRental IDs: {rental_ids}")
    print(f"Sale IDs: {sale_ids}")
    
    with open("rental_ids.txt", "w") as f:
        f.write("\n".join(rental_ids))
    
    with open("sale_ids.txt", "w") as f:
        f.write("\n".join(sale_ids))
    
    print("\nSaved to rental_ids.txt and sale_ids.txt")
