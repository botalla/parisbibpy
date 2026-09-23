# parisbibpy

A modern, type-safe, synchronous Python client library for the Paris public library system ([Bibliothèques de la Ville de Paris](https://bibliotheques.paris.fr)), powered by the Archimed Syracuse portal backend.

## Features

- **2-Layer Architecture**:
  - **Layer 1 (Direct Syracuse Client)**: 1:1 mapped synchronous operations with full session and cookie management.
  - **Layer 2 (Family Coordinator Facade)**: High-level family management, multi-account loan and reservation tracking, multi-dimensional grouping, and batch renewal reports.
- **Family / Multi-Card First**: Automatically retrieves and tags loans across linked cards (`UserPairings`) with cardholder context (`account_name`, `account_barcode`).
- **Trip Prioritization Planner**: Automatically organizes loans by library branch and ranks branches by return urgency, generating exact drop-off pack lists.
- **Multi-Dimensional Grouping**: Group loans by library branch, family member, or document type (comics, books, board games).
- **Batch Renewals**: Extend loans across all family cards with one call and receive a detailed `RenewalReport`.

## Quick Start

```python
from parisbibpy import ParisBibClient

with ParisBibClient(username="22272392XXXXXX", password="PIN") as client:
    # 1. Family overview
    family = client.get_family()
    print(f"Total family loans: {family.loans.total_count}")
    print(f"Overdue: {family.loans.overdue_count}")

    # 2. Plan library trips sorted by urgency
    for trip in family.plan_library_trips():
        print(f"\n🏛️ {trip.library}: {trip.total_items} items (earliest due: {trip.earliest_due_date})")
        for item in trip.loans.sorted_by_due_date():
            print(f"  - [{item.account_name}] {item.title}")

    # 3. Batch renewals for books due within 5 days
    report = client.renew_all_family_loans(due_within_days=5)
    print(f"Renewed: {len(report.succeeded)}, Failed: {len(report.failed)}")
```

## Running the Samples

The `sample/` directory contains 5 ready-to-run scripts that execute against the live Paris library backend:

```bash
# Set your library credentials (or you will be prompted interactively):
$env:PARISBIB_USERNAME="22272392XXXXXX"
$env:PARISBIB_PASSWORD="YOUR_PIN"

uv run python sample/01_family_overview.py
uv run python sample/02_grouping_and_dimensions.py
uv run python sample/03_plan_library_trips.py
uv run python sample/04_reservations_and_alerts.py
uv run python sample/05_batch_renewals.py
```

## Documentation

- **[Python API Reference](api_reference.md)**: Full documentation of `ParisBibClient`, models, collections, methods, and exceptions.
- **[Syracuse Portal API Discovery](api_discovery.md)**: Network specification of Archimed Syracuse WCF endpoints, headers, and payloads.
- **[Architecture Specification](spec.md)**: Detailed design document for the 2-layer architecture and family domain models.

