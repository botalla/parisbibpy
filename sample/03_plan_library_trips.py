"""Sample 3: Library Trip Planning & Visit Prioritization against the live backend.

Fetches real family loans from bibliotheques.paris.fr and:
- Automatically groups loans by library branch
- Ranks branches by return urgency (overdue items first, followed by nearest due date)
- Produces an exact drop-off packing list for each branch
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from common import get_authenticated_client


def main():
    with get_authenticated_client() as client:
        print("Fetching all family loans from Paris Public Libraries backend...")
        loans = client.get_family_loans()

        print("=" * 60)
        print(" RECOMMENDED LIBRARY VISITS (LIVE TRIP PLANNER)")
        print("=" * 60)

        if not loans:
            print("No active loans found across any family cards.")
            return

        trips = loans.plan_library_trips()

        for idx, trip in enumerate(trips, 1):
            if trip.overdue_count > 0:
                badge = "🚨 CRITICAL - OVERDUE ITEMS"
            elif trip.has_urgency(within_days=5):
                badge = "⏰ URGENT - DUE SOON"
            else:
                badge = "✅ RELAXED - PLENTY OF TIME"

            print(f"\n[Stop #{idx}] {trip.library}")
            print(f"   Status               : {badge}")
            print(f"   Total items to return: {trip.total_items}")
            print(f"   Overdue items        : {trip.overdue_count}")
            print(f"   Earliest due date    : {trip.earliest_due_date} ({trip.days_until_first_due} days remaining)")

            print("   🎒 Packing List for this branch:")
            for item in trip.loans.sorted_by_due_date():
                prefix = "⚠️ OVERDUE" if item.is_late else f"{item.days_remaining}d left"
                print(f"      • [{prefix:>10}] '{item.title}' [{item.type_of_document}] - Card: {item.account_name}")


if __name__ == "__main__":
    main()
