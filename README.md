# NYC Housing Connect Lottery Bot

Automates applying to NYC Housing Connect lotteries at https://housingconnect.nyc.gov/PublicWeb/

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

2. **Configure credentials:**
   Create a `.env` file with:
   ```
   USERNAME=your_housingconnect_username
   PASSWORD=your_password
   SALARY=75000
   ```
   Note: Both `SALARY` and `ANNUAL_INCOME` are supported for the income variable.

## Usage

### Get All Lottery IDs (No Login Required)

```bash
python get_lottery_ids.py
```

This will:
- Scrape all rental lottery IDs → saves to `rental_ids.txt`
- Scrape all sale lottery IDs → saves to `sale_ids.txt`
- Save detailed info to `all_lotteries.json`

### Apply to All Rental Lotteries

```bash
python apply_all_rentals.py
```

This will:
- Login to Housing Connect
- Go through all pages of rental lotteries
- Skip already-applied lotteries
- Check income eligibility for each lottery
- Apply to eligible lotteries (checkbox + submit)
- Print summary at the end

### Apply to All Sale Lotteries

```bash
python apply_all_sales.py
```

Same as above but for sale lotteries.

## How It Works

1. **Login**: Navigates to main page, clicks login link, fills credentials on external auth page
2. **Navigate**: Goes to Open Lotteries → Rentals or Sales tab
3. **Pagination**: Uses page number links to navigate through all pages
4. **For each lottery**:
   - Checks if "Applied" button exists on card (skip if yes)
   - Clicks "View Details" to open detail page
   - Parses "Eligible Income: $X - $Y" range
   - Compares against your `SALARY` from `.env`
   - If eligible: clicks "Apply Now" → checks agreement checkbox → clicks "Submit"
5. **Rate Limiting**: Random delays (2-5 seconds) between actions to avoid being blocked

## Files

| File | Description |
|------|-------------|
| `housing_connect_bot.py` | Core bot class with all automation logic |
| `get_lottery_ids.py` | Script to scrape all lottery IDs (no login) |
| `apply_all_rentals.py` | Script to apply to all rental lotteries |
| `apply_all_sales.py` | Script to apply to all sale lotteries |
| `rental_ids.txt` | Generated: one rental lottery ID per line |
| `sale_ids.txt` | Generated: one sale lottery ID per line |
| `all_lotteries.json` | Generated: detailed info about all lotteries |

## Programmatic Usage

```python
from housing_connect_bot import HousingConnectBot

with HousingConnectBot(headless=False) as bot:
    # Get lottery IDs (no login required)
    rentals = bot.get_lottery_ids("rental")
    sales = bot.get_lottery_ids("sale")
    
    # Login
    bot.login()
    
    # Navigate to lotteries
    bot.navigate_to_lotteries("rental")
    
    # Apply to a specific card by index
    result = bot.apply_to_lottery_by_click(0, "rental")
    print(result)
    # {'success': True, 'already_applied': False, 'eligible': True, 'title': '...', 'message': '...'}
```

## Notes

- The bot detects "Applied" button to skip already-applied lotteries
- Eligibility is checked against `SALARY` or `ANNUAL_INCOME` in `.env`
- Browser runs visible by default (`headless=False`) for monitoring
- Timeouts are generous (45-60s) to handle slow page loads
- Random delays help avoid rate limiting
