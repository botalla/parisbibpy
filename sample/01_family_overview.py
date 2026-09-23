"""Sample 1: Single Glance Family Overview against the live backend.

Fetches real metrics across all family cards from bibliotheques.paris.fr:
- Total loans and card accounts managed
- Overdue items count
- Renewable items count
- Earliest return date
- Urgent items due in the next 3 days
"""

import sys
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from common import get_authenticated_client


def main():
    with get_authenticated_client() as client:
        print("Fetching family overview from Paris Public Libraries backend...")
        family = client.get_family()
        loans = family.loans
        bookings = family.bookings

        print("=" * 60)
        print(" PARIS PUBLIC LIBRARIES - LIVE FAMILY OVERVIEW")
        print("=" * 60)

        print(f"\n👨‍👩‍👧‍👦 Family Accounts Managed : {len(family.accounts)}")
        for acc in family.accounts:
            late_indicator = "⚠️ OVERDUE" if acc.summary.has_overdue else "OK"
            print(f"   • {acc.account_name} ({acc.barcode}): {acc.loans.total_count} loans [{late_indicator}]")

        print("\n📊 Family-Wide Metrics:")
        print(f"   • Total Active Loans   : {loans.total_count}")
        print(f"   • Overdue Items        : {loans.overdue_count} {'🚨 Action required!' if loans.overdue_count > 0 else '✅'}")
        print(f"   • Renewable Items      : {loans.renewable_count}")
        print(f"   • Total Reservations   : {bookings.total_count}")
        print(f"   • Ready for Pickup     : {len(bookings.ready_for_pickup)}")
        print(f"   • Earliest Return Date : {loans.earliest_due_date}")

        urgent_loans = loans.due_soon(days=3)
        if urgent_loans:
            print(f"\n⏰ Items Due in the Next 3 Days ({urgent_loans.total_count}):")
            for item in urgent_loans.sorted_by_due_date():
                prefix = "⚠️ OVERDUE" if item.is_late else f"Due in {item.days_remaining}d"
                print(f"   [{prefix}] '{item.title}' ({item.account_name}) @ {item.location}")

        if family.failed_accounts:
            print("\n⚠️ Diagnostics on Linked Family Accounts:")
            for item in family.failed_accounts:
                acc = item[0]
                reason = item[1]
                name = getattr(acc, "display_name", str(acc))
                code = getattr(acc, "barcode", "")
                print(f"   • {name} ({code}): {reason}")


if __name__ == "__main__":
    main()
