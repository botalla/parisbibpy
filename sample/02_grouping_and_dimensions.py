"""Sample 2: Multi-Dimensional Grouping and Filtering against the live backend.

Fetches real family loans from bibliotheques.paris.fr and organizes them:
1. Per Family Member / Account (Who has what?)
2. Per Document Type (BD, Livre, Jeu de société, etc.)
3. Per Library Branch (Where do items need to go back?)
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
        print(" MULTI-DIMENSIONAL LOANS VIEW (LIVE)")
        print("=" * 60)

        if not loans:
            print("No active loans found across any family cards.")
            return

        # 1. GROUP BY ACCOUNT (Family member)
        print("\n[1] LOANS GROUPED BY FAMILY MEMBER:")
        for member_name, acc_loans in loans.group_by_account().items():
            overdue_note = f", ⚠️ {acc_loans.overdue_count} overdue" if acc_loans.overdue_count else ""
            print(f"\n👤 {member_name} ({acc_loans.total_count} items{overdue_note})")
            for item in acc_loans.sorted_by_due_date():
                status = "🚨 OVERDUE" if item.is_late else f"in {item.days_remaining}d"
                print(f"   • [{item.type_of_document}] '{item.title}' (due {status})")

        # 2. GROUP BY DOCUMENT TYPE (BD, Book, Game)
        print("\n" + "-" * 60)
        print("[2] LOANS GROUPED BY DOCUMENT TYPE:")
        for doc_type, type_loans in loans.group_by_type().items():
            print(f"\n📦 {doc_type} ({type_loans.total_count} borrowed):")
            for item in type_loans:
                print(f"   • '{item.title}' -> borrowed by {item.account_name}")

        # 3. GROUP BY LIBRARY BRANCH
        print("\n" + "-" * 60)
        print("[3] LOANS GROUPED BY LIBRARY BRANCH (Physical Location):")
        for lib, branch_loans in loans.group_by_library().items():
            print(f"\n🏛️ {lib} ({branch_loans.total_count} items to return here):")
            for item in branch_loans:
                print(f"   • '{item.title}' [{item.type_of_document}] ({item.account_name})")


if __name__ == "__main__":
    main()
