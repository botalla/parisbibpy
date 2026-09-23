"""Sample 4: Reservations & Ready-for-Pickup Alerts against the live backend.

Fetches real reservations across all family cards from bibliotheques.paris.fr:
- Checks if any reserved items are waiting on the shelf ready for pickup
- Shows pickup locations and expiration dates
- Lists reservations currently in transit or processing
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from common import get_authenticated_client


def main():
    with get_authenticated_client() as client:
        print("Fetching reservations from Paris Public Libraries backend...")
        bookings = client.get_family_bookings()

        print("=" * 60)
        print(" FAMILY RESERVATIONS (LIVE)")
        print("=" * 60)

        print(f"\nTotal Active Reservations across Family: {bookings.total_count}")

        # 1. Ready for pickup alerts
        ready = bookings.ready_for_pickup
        if ready:
            print("\n🎉 ITEMS WAITING ON THE SHELF FOR PICKUP:")
            for b in ready:
                print(f"   🏛️ Location : {b.pickup_location}")
                print(f"      Item     : '{b.title}' [{b.type_of_document}]")
                print(f"      Card     : {b.account_name}")
                print(f"      Deadline : Pick up before {b.available_until}")
                print("      " + "-" * 40)
        else:
            print("\nℹ️ No reservations currently ready for pickup.")

        # 2. In-progress reservations
        pending = [b for b in bookings if not b.is_available]
        if pending:
            print("\n⏳ RESERVATIONS IN TRANSIT OR PROCESSING:")
            for b in pending:
                print(f"   • '{b.title}' ({b.account_name}) -> Status: {b.state} @ {b.pickup_location}")


if __name__ == "__main__":
    main()
