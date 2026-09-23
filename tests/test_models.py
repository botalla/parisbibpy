"""Tests for domain models, collections, and Syracuse date parsing."""

from parisbibpy.models import (
    AccountLoans,
    AccountSummary,
    Booking,
    BookingCollection,
    FamilyOverview,
    Loan,
    LoanCollection,
)
from parisbibpy.utils import parse_syracuse_date


def test_parse_syracuse_date():
    # Offset +0200
    dt1 = parse_syracuse_date("/Date(1790373600000+0200)/")
    assert dt1 is not None
    assert dt1.tzinfo is not None

    # Escaped backslashes
    dt2 = parse_syracuse_date(r"\/Date(1790373600000+0200)\/")
    assert dt2 is not None
    assert dt1 == dt2

    # None / Empty
    assert parse_syracuse_date(None) is None
    assert parse_syracuse_date("") is None
    assert parse_syracuse_date("invalid") is None


def test_account_summary_parsing(account_summary_data):
    raw_summary = account_summary_data["d"]["AccountSummary"]
    summary = AccountSummary.model_validate(raw_summary)

    assert summary.barcode == "22272392XXXXXX"
    assert summary.display_name == "Fred DUPONT"
    assert summary.loans_total_count == 19
    assert summary.loans_late_count == 0
    assert not summary.has_overdue
    assert summary.bookings_total_count == 1
    assert summary.loans_next_handing_date is not None


def test_loan_model_and_properties(list_loans_data):
    raw_loans = list_loans_data["d"]["Loans"]
    loans = [Loan.model_validate(item) for item in raw_loans]

    assert len(loans) == 3
    assert loans[0].title == "Empereur du Japon. 02"
    assert loans[0].type_of_document == "BD"
    assert loans[0].is_renewable
    assert not loans[0].is_late

    # Item with overdue flag
    overdue_item = loans[2]
    assert overdue_item.title == "Catan: Le Jeu de Plateau"
    assert overdue_item.type_of_document == "Jeu de société"
    assert overdue_item.is_late
    assert not overdue_item.is_renewable


def test_loan_collection_multi_dimensional_grouping(list_loans_data):
    raw_loans = list_loans_data["d"]["Loans"]
    loans = [Loan.model_validate(item) for item in raw_loans]
    
    # Tag loans with different accounts to test account grouping
    loans[0].account_name = "Parent Account"
    loans[1].account_name = "Child 1"
    loans[2].account_name = "Child 1"

    collection = LoanCollection(loans)

    assert collection.total_count == 3
    assert collection.overdue_count == 1
    assert collection.renewable_count == 1

    # 1. Group by Library
    by_library = collection.group_by_library()
    assert "75015 - Marguerite Yourcenar" in by_library
    assert len(by_library["75015 - Marguerite Yourcenar"]) == 2
    assert "75015 - Vaugirard (fermée)" in by_library
    assert len(by_library["75015 - Vaugirard (fermée)"]) == 1

    # 2. Group by Account
    by_account = collection.group_by_account()
    assert len(by_account["Parent Account"]) == 1
    assert len(by_account["Child 1"]) == 2

    # 3. Group by Type of Document
    by_type = collection.group_by_type()
    assert len(by_type["BD"]) == 2
    assert len(by_type["Jeu de société"]) == 1


def test_loan_collection_filter(list_loans_data):
    raw_loans = list_loans_data["d"]["Loans"]
    collection = LoanCollection([Loan.model_validate(item) for item in raw_loans])

    # Filter renewable
    renewable = collection.filter(is_renewable=True)
    assert len(renewable) == 1
    assert renewable[0].title == "Empereur du Japon. 02"

    # Filter by doc_type
    games = collection.filter(doc_type="Jeu de société")
    assert len(games) == 1
    assert games[0].title == "Catan: Le Jeu de Plateau"

    # Filter by library
    yourcenar = collection.filter(library="Yourcenar")
    assert len(yourcenar) == 2


def test_library_trip_planning(list_loans_data):
    raw_loans = list_loans_data["d"]["Loans"]
    collection = LoanCollection([Loan.model_validate(item) for item in raw_loans])

    trips = collection.plan_library_trips()
    assert len(trips) == 2

    # Since Marguerite Yourcenar has an overdue item (Catan), it must be prioritized first!
    assert "Marguerite Yourcenar" in trips[0].library
    assert trips[0].overdue_count == 1
    assert trips[0].total_items == 2
    assert trips[0].has_urgency(within_days=7)

    # Second trip
    assert "Vaugirard" in trips[1].library
    assert trips[1].overdue_count == 0


def test_booking_model_and_collection(list_bookings_data):
    raw_bookings = list_bookings_data["d"]["Bookings"]
    bookings = [Booking.model_validate(b) for b in raw_bookings]
    
    collection = BookingCollection(bookings)
    assert collection.total_count == 2

    # Ready for pickup
    ready = collection.ready_for_pickup
    assert len(ready) == 1
    assert ready[0].title == "Garfield gribouille"
    assert ready[0].pickup_location == "75015 - Marguerite Yourcenar"
    assert ready[0].available_until is not None

    # Group by library
    by_lib = collection.group_by_pickup_library()
    assert len(by_lib) == 2
    assert "75015 - Marguerite Yourcenar" in by_lib
    assert "75015 - Andrée Chedid" in by_lib


def test_loan_to_syracuse_dict(list_loans_data):
    raw_loan = list_loans_data["d"]["Loans"][0]
    loan = Loan.model_validate(raw_loan)

    syr_dict = loan.to_syracuse_dict()
    assert syr_dict["HoldingId"] == loan.holding_id
    assert syr_dict["RecordId"] == loan.record_id
    assert syr_dict["Title"] == loan.title
    assert syr_dict["RecordBase"] == "SYRACUSE"
    assert syr_dict["WhenBack"].startswith("/Date(")
    assert syr_dict["CanRenew"] is True


def test_family_overview_facade(account_summary_data, list_loans_data, list_bookings_data):
    summary = AccountSummary.model_validate(account_summary_data["d"]["AccountSummary"])
    loans = [Loan.model_validate(item) for item in list_loans_data["d"]["Loans"]]
    bookings = [Booking.model_validate(item) for item in list_bookings_data["d"]["Bookings"]]

    primary = AccountLoans(
        account_name="Fred",
        barcode="22272392XXXXXX",
        summary=summary,
        loans=LoanCollection([loans[0]]),
        bookings=BookingCollection([bookings[0]]),
    )

    child = AccountLoans(
        account_name="Child",
        barcode="2227203240XXXX",
        summary=summary,
        loans=LoanCollection([loans[1], loans[2]]),
        bookings=BookingCollection([bookings[1]]),
    )

    family = FamilyOverview(primary_account=primary, paired_accounts=[child])

    assert len(family.accounts) == 2
    assert family.loans.total_count == 3
    assert family.bookings.total_count == 2
    
    trips = family.plan_library_trips()
    assert len(trips) == 2
