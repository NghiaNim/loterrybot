#!/usr/bin/env python3
"""
Script to get all lottery IDs from NYC Housing Connect
NO LOGIN REQUIRED - public data

Saves to rental_ids.txt, sale_ids.txt, and all_lotteries.json
"""

import json
from housing_connect_bot import HousingConnectBot


def main():
    print("=" * 60)
    print("NYC Housing Connect - Getting All Lottery IDs")
    print("(No login required)")
    print("=" * 60)
    print()
    
    # headless=False to see the browser for debugging
    with HousingConnectBot(headless=False) as bot:
        print("Step 1: Getting rental lottery IDs...")
        rental_lotteries = bot.get_lottery_ids("rental")
        
        print("\nStep 2: Getting sale lottery IDs...")
        sale_lotteries = bot.get_lottery_ids("sale")
    
    # Results
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    
    print(f"\nRental Lotteries: {len(rental_lotteries)} found")
    for lottery in rental_lotteries:
        days = f"({lottery.days_until_closing} days left)" if lottery.days_until_closing else ""
        print(f"  [{lottery.id}] {lottery.title} {days}")
    
    rental_ids = [l.id for l in rental_lotteries]
    with open("rental_ids.txt", "w") as f:
        f.write("\n".join(rental_ids))
    print(f"\n  → Saved {len(rental_ids)} IDs to rental_ids.txt")
    
    print(f"\nSale Lotteries: {len(sale_lotteries)} found")
    for lottery in sale_lotteries:
        days = f"({lottery.days_until_closing} days left)" if lottery.days_until_closing else ""
        print(f"  [{lottery.id}] {lottery.title} {days}")
    
    sale_ids = [l.id for l in sale_lotteries]
    with open("sale_ids.txt", "w") as f:
        f.write("\n".join(sale_ids))
    print(f"\n  → Saved {len(sale_ids)} IDs to sale_ids.txt")
    
    # Save detailed JSON
    all_lotteries = {
        "rentals": [
            {
                "id": l.id,
                "title": l.title,
                "location": l.location,
                "units_available": l.units_available,
                "days_until_closing": l.days_until_closing,
                "is_applied": l.is_applied,
                "url": l.url
            }
            for l in rental_lotteries
        ],
        "sales": [
            {
                "id": l.id,
                "title": l.title,
                "location": l.location,
                "units_available": l.units_available,
                "days_until_closing": l.days_until_closing,
                "is_applied": l.is_applied,
                "url": l.url
            }
            for l in sale_lotteries
        ]
    }
    
    with open("all_lotteries.json", "w") as f:
        json.dump(all_lotteries, f, indent=2)
    print(f"\n  → Full details saved to all_lotteries.json")
    
    print("\n" + "=" * 60)
    print("COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
