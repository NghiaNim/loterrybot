#!/usr/bin/env python3
"""
Apply to ALL eligible sale lotteries
Uses the same pagination approach as get_lottery_ids.py
"""

from housing_connect_bot import HousingConnectBot
import time
import random


def random_delay(min_sec=2, max_sec=5):
    """Random delay to appear more human-like and avoid rate limits"""
    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)


def main():
    print("=" * 60)
    print("APPLYING TO ALL SALE LOTTERIES")
    print("=" * 60)
    print()
    
    with HousingConnectBot(headless=False) as bot:
        print(f"Username: {bot.username}")
        print(f"Your income: ${bot.annual_income:,}")
        print()
        
        # Login first
        print("Step 1: Logging in...")
        if not bot.login():
            print("ERROR: Login failed!")
            return
        
        # Navigate to sales
        print("\nStep 2: Navigating to sale lotteries...")
        bot.navigate_to_lotteries("sale")
        
        # Get total pages
        total_pages = bot._get_total_pages()
        print(f"\nTotal pages: {total_pages}")
        
        all_results = []
        processed_titles = set()
        
        for page_num in range(1, total_pages + 1):
            print(f"\n{'='*60}")
            print(f"PAGE {page_num} OF {total_pages}")
            print(f"{'='*60}")
            
            # Navigate to the correct page using the bot's _go_to_page method
            if page_num > 1:
                print(f"Navigating to page {page_num}...")
                bot._go_to_page(page_num)
                random_delay(2, 4)
            
            # Get cards on this page
            cards = bot.page.query_selector_all('app-lottery-grid-card')
            num_cards = len(cards)
            print(f"Found {num_cards} lotteries on this page")
            
            # Collect card data FIRST before any navigation
            card_data = []
            for i, card in enumerate(cards):
                title_el = card.query_selector('.title.title-h3')
                title = title_el.text_content().strip() if title_el else f"Unknown_{i}"
                
                # Check if already applied on card
                applied_btn = card.query_selector('button.btn-grey-90')
                is_applied = applied_btn and 'Applied' in (applied_btn.text_content() or '')
                
                card_data.append({
                    'index': i,
                    'title': title,
                    'is_applied': is_applied
                })
            
            # Process each card
            for data in card_data:
                card_index = data['index']
                title = data['title']
                
                print(f"\n--- Lottery {card_index+1}/{num_cards}: {title} ---")
                
                if title in processed_titles:
                    print(f"  Skipping duplicate")
                    continue
                
                processed_titles.add(title)
                
                if data['is_applied']:
                    print(f"  ⚠ Already applied (skipping)")
                    all_results.append({
                        'success': False,
                        'already_applied': True,
                        'eligible': True,
                        'title': title,
                        'message': 'Already applied'
                    })
                    continue
                
                # Navigate back to lotteries and to the correct page
                bot.navigate_to_lotteries("sale")
                random_delay(2, 3)
                
                if page_num > 1:
                    bot._go_to_page(page_num)
                    random_delay(2, 3)
                
                # Apply using the card index
                result = bot.apply_to_lottery_by_click(card_index, "sale")
                all_results.append(result)
                
                random_delay(2, 4)
        
        # Final Summary
        print("\n" + "=" * 60)
        print("FINAL SUMMARY")
        print("=" * 60)
        
        applied = [r for r in all_results if r['success']]
        already = [r for r in all_results if r['already_applied']]
        not_eligible = [r for r in all_results if not r['eligible']]
        failed = [r for r in all_results if not r['success'] and not r['already_applied'] and r['eligible']]
        
        print(f"\n✓ Successfully Applied ({len(applied)}):")
        for r in applied:
            print(f"    - {r['title']}")
        
        print(f"\n⚠ Already Applied ({len(already)}):")
        for r in already:
            print(f"    - {r['title']}")
        
        print(f"\n✗ Not Eligible ({len(not_eligible)}):")
        for r in not_eligible:
            print(f"    - {r['title']}: {r['message']}")
        
        if failed:
            print(f"\n? Failed ({len(failed)}):")
            for r in failed:
                print(f"    - {r['title']}: {r['message']}")
        
        print(f"\n" + "-" * 40)
        print(f"TOTAL: {len(all_results)} processed")
        print(f"  - Applied: {len(applied)}")
        print(f"  - Already Applied: {len(already)}")
        print(f"  - Not Eligible: {len(not_eligible)}")
        print(f"  - Failed: {len(failed)}")
        
        print("\n  Keeping browser open for 5 seconds...")
        time.sleep(5)


if __name__ == "__main__":
    main()
