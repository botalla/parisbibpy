"""Sample 5: Batch Renewals Across Accounts against the live backend.

Demonstrates extending loans across all linked family cards on bibliotheques.paris.fr:
- Inspects all loans across all family cards
- Identifies items eligible for renewal due soon (e.g. within 5 days)
- Requests user confirmation before executing changes
- Executes batch renewals and prints a detailed RenewalReport (succeeded, blocked, skipped)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from common import get_authenticated_client


def main():
    with get_authenticated_client() as client:
        print("Fetching loans across all family accounts from Paris Public Libraries backend...")
        family = client.get_family()
        loans = family.loans

        print("=" * 60)
        print(" BATCH RENEWALS ACROSS FAMILY ACCOUNTS (LIVE)")
        print("=" * 60)

        print(f"\nTotal active family loans : {loans.total_count}")
        print(f"Renewable items           : {loans.renewable_count}")

        # Target items that can be renewed and are due within 5 days (or already overdue)
        candidates = loans.filter(due_within_days=5, is_renewable=True)
        print(f"Renewable items due within 5 days : {len(candidates)}")

        if not candidates:
            print("\n✅ No loans require urgent extension right now.")
            return

        print("\nCandidates eligible for extension:")
        for item in candidates:
            status = "OVERDUE" if item.is_late else f"due in {item.days_remaining}d"
            print(f"   • '{item.title}' [{item.type_of_document}] ({item.account_name}) - {status}")

        try:
            confirm = input("\nDo you want to execute renewal for these items on your real account? (y/N): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            return

        if confirm.lower() != "y":
            print("Renewal cancelled by user.")
            return

        print("\n⚡ Sending renewal requests to Syracuse API...")
        report = client.renew_all_family_loans(due_within_days=5)

        print("\n📋 RENEWAL REPORT SUMMARY:")
        print(f"   • Succeeded : {len(report.succeeded)}")
        print(f"   • Failed    : {len(report.failed)}")
        print(f"   • Skipped   : {len(report.skipped_not_renewable)}")

        if report.succeeded:
            print("\n✅ Successfully Extended:")
            for item in report.succeeded:
                print(f"   • '{item.title}' ({item.account_name}) -> New due date: {item.due_date}")

        if report.failed:
            print("\n❌ Renewal Failed / Blocked by Library:")
            for f in report.failed:
                print(f"   • '{f.loan.title}' ({f.loan.account_name}) -> Reason: {f.reason}")


if __name__ == "__main__":
    main()
