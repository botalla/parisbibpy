# `parisbibpy` Specification

A modern, type-safe, synchronous Python client library for the Paris public library system ([Bibliothèques de la Ville de Paris](https://bibliotheques.paris.fr)), powered by the Archimed Syracuse portal backend.

---

## 1. Project Overview & Objectives

### 1.1. Motivation
The Paris public library network operates dozens of branches with thousands of daily patrons. Patrons frequently manage multi-card family accounts, need alerts before items become overdue, and wish to automate renewals. Currently, no official Python library exists to interface with the Syracuse-based patron services.

### 1.2. Core Goals
- **Two-Layer Architecture**:
  - **Layer 1 (Low-Level Client)**: Direct 1:1 mapping with Syracuse JSON-RPC endpoints. Deterministic, explicit (1 call = 1 HTTP request), giving power users complete control over network calls and session handling.
  - **Layer 2 (Convenience Facade)**: High-level family manager providing single-glance family visibility, multi-account loan and reservation aggregation, multi-dimensional grouping (by library, by account, by document type), trip planning prioritization, and batch renewals across cards.
- **Simple & Synchronous**: Straightforward, linear execution using standard synchronous HTTP (`requests`). No `async`/`await` complexity or event-loop boilerplate.
- **Type-safe & Developer-friendly**: Built with Python 3.10+ and Pydantic v2 for robust data validation, type hints, and rich IDE auto-completion.
- **Family & Multi-Card First**: Native support for linked Syracuse accounts (`UserPairings`), tagging every loan and booking with its cardholder context (`account_name`, `account_barcode`, `user_unique_identifier`).
- **Integration Ready**: Clean data models designed for CLI utilities, automation scripts, desktop widgets, and Home Assistant sensors.

---

## 2. Architecture & Technology Stack

| Component | Choice | Rationale |
| :--- | :--- | :--- |
| **Language Target** | Python >= 3.10 | Modern typing features (`|` union syntax, pattern matching). |
| **HTTP Engine** | `requests` | Battle-tested, synchronous HTTP library with automatic session cookie jar management. |
| **Data Models** | `pydantic` >= 2.0 | High performance serialization, deserialization, and strict validation. |
| **Collections** | `collections.UserList` | Rich domain list subclasses (`LoanCollection`, `BookingCollection`) with fluent grouping, filtering, and sorting. |
| **Build & Packaging** | `pyproject.toml` (Hatchling or Flit) | Modern PEP 621 / PEP 517 standard packaging. |
| **Code Quality** | `ruff` (linter & formatter), `mypy` | Fast, consistent style and static type checking. |
| **Testing** | `pytest`, `responses` | Declarative testing with mocked HTTP requests and recorded Syracuse fixtures. |

---

## 3. Directory Layout

```text
parisbibpy/
├── src/
│   └── parisbibpy/
│       ├── __init__.py          # Public exports (ParisBibClient, models, collections, errors)
│       ├── client.py            # Synchronous ParisBibClient (Layer 1 + Layer 2 methods)
│       ├── models/
│       │   ├── __init__.py      # Models export
│       │   ├── account.py       # AccountSummary, PairedAccount, AccountLoans
│       │   ├── loan.py          # Loan, LoanCollection, LibraryTrip
│       │   ├── booking.py       # Booking, BookingCollection
│       │   ├── renewal.py       # RenewalResult, RenewalReport
│       │   ├── family.py        # FamilyOverview facade
│       │   └── common.py        # SyracuseResponse envelope
│       ├── exceptions.py        # Custom exception hierarchy
│       ├── utils.py             # Syracuse date parser, timestamp helpers
│       └── py.typed             # PEP 561 marker
├── tests/
│   ├── conftest.py              # Pytest fixtures and mock client
│   ├── fixtures/                # Real JSON responses from api_discovery.md
│   │   ├── account_summary.json
│   │   ├── list_loans.json
│   │   ├── list_bookings.json
│   │   └── user_pairings.json
│   ├── test_models.py           # Model parsing, date conversion & collection tests
│   └── test_client.py           # Synchronous client and facade unit tests
├── api_discovery.md             # Reverse-engineered API reference
├── spec.md                      # This specification document
├── pyproject.toml
└── README.md
```

---

## 4. Syracuse Data & Date Handling

### 4.1. Date Parsing
Syracuse serializes dates using Microsoft's JSON date format:
`\/Date(1790373600000+0200)\/`

`parisbibpy.utils.parse_syracuse_date` handles:
1. Extracting timestamp milliseconds and timezone offset via regex:
   `r"\/Date\((\d+)(?:([+-]\d{2})(\d{2}))?\)\/"`
2. Converting milliseconds to UTC seconds.
3. Attaching the corresponding `datetime.timezone` offset if present, returning a timezone-aware `datetime.datetime` or a `datetime.date` object for due dates.
4. Serializing back to ISO-8601 strings in model exports.

### 4.2. API Response Envelope
Responses return wrapped in:
```json
{
  "d": { ... },
  "errors": [],
  "message": null,
  "success": true
}
```

The client automatically:
- Checks `success is True` and `len(errors) == 0`.
- Raises `SyracuseApiError` or `AuthenticationError` if `success is False`.
- Unpacks and passes `response_json["d"]` to the corresponding Pydantic model.

---

## 5. Domain Models & Collections (`parisbibpy.models`)

### 5.1. `AccountSummary`
Represents patron loan and booking metrics:
```python
class AccountSummary(BaseModel):
    barcode: str
    display_name: str
    loans_total_count: int
    loans_not_late_count: int
    loans_late_count: int
    loans_next_handing_count: int
    loans_next_handing_date: Optional[datetime] = None
    loans_next_handing_is_soon_late: bool
    bookings_total_count: int
    bookings_available_count: int
    bookings_not_available_count: int

    @property
    def has_overdue(self) -> bool:
        return self.loans_late_count > 0

    @property
    def days_until_next_due(self) -> Optional[int]:
        if not self.loans_next_handing_date:
            return None
        today = datetime.now(self.loans_next_handing_date.tzinfo).date()
        return (self.loans_next_handing_date.date() - today).days
```

### 5.2. `Loan` & Cardholder Context
Represents an individual checked-out item, retaining its cardholder context:
```python
class Loan(BaseModel):
    id: str
    holding_id: str
    record_id: str
    title: str
    type_of_document: str  # "BD", "Livre", "Jeu de société", "Revue", etc.
    location: str          # e.g. "75015 - Marguerite Yourcenar"
    when_back: datetime
    state: str
    is_late: bool
    is_soon_late: bool
    can_renew: bool
    cannot_renew_reason: Optional[str] = None
    thumbnail_url: Optional[HttpUrl] = None
    title_link: Optional[HttpUrl] = None
    is_renewal: bool = False

    # Family context fields (populated when aggregated)
    account_name: Optional[str] = None
    account_barcode: Optional[str] = None
    user_unique_identifier: Optional[str] = None

    @property
    def is_renewable(self) -> bool:
        return self.can_renew

    @property
    def due_date(self) -> date:
        return self.when_back.date()

    @property
    def days_remaining(self) -> int:
        today = datetime.now(self.when_back.tzinfo).date()
        return (self.due_date - today).days
```

### 5.3. `LibraryTrip`
Represents a planned drop-off trip to a single library branch:
```python
class LibraryTrip(BaseModel):
    library: str
    loans: "LoanCollection"
    earliest_due_date: Optional[date] = None
    days_until_first_due: Optional[int] = None
    overdue_count: int = 0
    total_items: int = 0

    def has_urgency(self, within_days: int = 7) -> bool:
        """Returns True if any item is overdue or due within N days."""
        if self.overdue_count > 0:
            return True
        if self.days_until_first_due is not None:
            return self.days_until_first_due <= within_days
        return False
```

### 5.4. `LoanCollection` (Multi-Dimensional Grouping & Trips)
Subclasses `collections.UserList[Loan]` to provide rich grouping, filtering, and trip planning:
```python
class LoanCollection(UserList[Loan]):
    @property
    def total_count(self) -> int:
        return len(self.data)

    @property
    def overdue(self) -> "LoanCollection":
        return LoanCollection([loan for loan in self.data if loan.is_late])

    @property
    def overdue_count(self) -> int:
        return len(self.overdue)

    @property
    def renewable(self) -> "LoanCollection":
        return LoanCollection([loan for loan in self.data if loan.can_renew])

    @property
    def renewable_count(self) -> int:
        return len(self.renewable)

    @property
    def earliest_due_date(self) -> Optional[date]:
        if not self.data:
            return None
        return min(loan.due_date for loan in self.data)

    def due_soon(self, days: int = 5) -> "LoanCollection":
        """Items due within N days or already overdue."""
        return LoanCollection([loan for loan in self.data if loan.days_remaining <= days])

    def filter(
        self,
        due_within_days: Optional[int] = None,
        is_renewable: Optional[bool] = None,
        is_late: Optional[bool] = None,
        library: Optional[str] = None,
        doc_type: Optional[str] = None,
        account_name: Optional[str] = None,
    ) -> "LoanCollection":
        """Filter loans by any combination of criteria."""
        items = self.data
        if due_within_days is not None:
            items = [item for item in items if item.days_remaining <= due_within_days]
        if is_renewable is not None:
            items = [item for item in items if item.can_renew == is_renewable]
        if is_late is not None:
            items = [item for item in items if item.is_late == is_late]
        if library is not None:
            items = [item for item in items if library.lower() in item.location.lower()]
        if doc_type is not None:
            items = [item for item in items if doc_type.lower() == item.type_of_document.lower()]
        if account_name is not None:
            items = [item for item in items if item.account_name and account_name.lower() in item.account_name.lower()]
        return LoanCollection(items)

    def group_by_library(self) -> dict[str, "LoanCollection"]:
        """Group loans by physical library branch."""
        groups: dict[str, list[Loan]] = defaultdict(list)
        for loan in self.data:
            groups[loan.location].append(loan)
        return {lib: LoanCollection(items) for lib, items in sorted(groups.items())}

    def group_by_account(self) -> dict[str, "LoanCollection"]:
        """Group loans by family member / cardholder account."""
        groups: dict[str, list[Loan]] = defaultdict(list)
        for loan in self.data:
            key = loan.account_name or "Primary Account"
            groups[key].append(loan)
        return {acc: LoanCollection(items) for acc, items in sorted(groups.items())}

    def group_by_type(self) -> dict[str, "LoanCollection"]:
        """Group loans by document type (BD, Livre, Jeu de société, etc.)."""
        groups: dict[str, list[Loan]] = defaultdict(list)
        for loan in self.data:
            groups[loan.type_of_document].append(loan)
        return {dt: LoanCollection(items) for dt, items in sorted(groups.items())}

    def sorted_by_due_date(self, descending: bool = False) -> "LoanCollection":
        """Sort loans by due date."""
        return LoanCollection(sorted(self.data, key=lambda l: l.when_back, reverse=descending))

    def plan_library_trips(self) -> list[LibraryTrip]:
        """Group loans by library and sort trips by urgency of due dates."""
        trips = []
        for lib, branch_loans in self.group_by_library().items():
            earliest = branch_loans.earliest_due_date
            days_until = None
            if earliest:
                today = datetime.now().date()
                days_until = (earliest - today).days
            trips.append(
                LibraryTrip(
                    library=lib,
                    loans=branch_loans,
                    earliest_due_date=earliest,
                    days_until_first_due=days_until,
                    overdue_count=branch_loans.overdue_count,
                    total_items=branch_loans.total_count,
                )
            )
        # Prioritize: overdue trips first, then closest due date
        return sorted(
            trips,
            key=lambda t: (
                0 if t.overdue_count > 0 else 1,
                t.days_until_first_due if t.days_until_first_due is not None else 9999,
            ),
        )
```

### 5.5. `Booking` & `BookingCollection` (Reservations)
Represents patron reservations across the family:
```python
class Booking(BaseModel):
    id: str
    holding_id: Optional[str] = None
    record_id: str
    title: str
    type_of_document: str
    pickup_location: str
    state: str                 # "En attente", "En cours d'acheminement", "Disponible"
    is_available: bool         # Ready for patron pickup
    available_until: Optional[date] = None
    rank_in_queue: Optional[int] = None
    
    # Family context
    account_name: Optional[str] = None
    account_barcode: Optional[str] = None
    user_unique_identifier: Optional[str] = None

class BookingCollection(UserList[Booking]):
    @property
    def total_count(self) -> int:
        return len(self.data)

    @property
    def ready_for_pickup(self) -> "BookingCollection":
        """All items currently awaiting pickup at a library branch."""
        return BookingCollection([b for b in self.data if b.is_available])

    def group_by_pickup_library(self) -> dict[str, "BookingCollection"]:
        groups: dict[str, list[Booking]] = defaultdict(list)
        for b in self.data:
            groups[b.pickup_location].append(b)
        return {lib: BookingCollection(items) for lib, items in sorted(groups.items())}

    def group_by_account(self) -> dict[str, "BookingCollection"]:
        groups: dict[str, list[Booking]] = defaultdict(list)
        for b in self.data:
            key = b.account_name or "Primary Account"
            groups[key].append(b)
        return {acc: BookingCollection(items) for acc, items in sorted(groups.items())}
```

### 5.6. `RenewalReport` (Batch Renewal Reporting)
Detailed outcome report when renewing across accounts:
```python
class RenewalFailure(BaseModel):
    loan: Loan
    reason: str

class RenewalReport(BaseModel):
    succeeded: list[Loan] = []
    failed: list[RenewalFailure] = []
    skipped_not_renewable: list[Loan] = []

    @property
    def total_attempted(self) -> int:
        return len(self.succeeded) + len(self.failed)

    @property
    def is_all_successful(self) -> bool:
        return len(self.failed) == 0
```

### 5.7. `PairedAccount` & `FamilyOverview` (Domain Facade)
```python
class PairedAccount(BaseModel):
    id: int
    barcode: str
    display_name: str
    user_unique_identifier: str
    is_reciprocal: bool
    state: int

class AccountLoans(BaseModel):
    account_name: str
    barcode: str
    unique_identifier: Optional[str] = None
    summary: AccountSummary
    loans: LoanCollection
    bookings: BookingCollection

class FamilyOverview(BaseModel):
    primary_account: AccountLoans
    paired_accounts: list[AccountLoans] = []
    failed_accounts: list[tuple[PairedAccount, str]] = []

    @property
    def accounts(self) -> list[AccountLoans]:
        return [self.primary_account] + self.paired_accounts

    @property
    def loans(self) -> LoanCollection:
        """Flattened collection of all family loans with cardholder metadata."""
        items: list[Loan] = list(self.primary_account.loans)
        for pa in self.paired_accounts:
            items.extend(pa.loans)
        return LoanCollection(items)

    @property
    def bookings(self) -> BookingCollection:
        """Flattened collection of all family reservations."""
        items: list[Booking] = list(self.primary_account.bookings)
        for pa in self.paired_accounts:
            items.extend(pa.bookings)
        return BookingCollection(items)

    def plan_library_trips(self) -> list[LibraryTrip]:
        """Direct shortcut to plan library trips across all family loans."""
        return self.loans.plan_library_trips()
```

---

## 6. Client API Specification

### 6.1. Synchronous Client (`ParisBibClient`)

The client exposes both **Layer 1 (Direct API operations)** and **Layer 2 (Convenience Facades)**:

```python
class ParisBibClient:
    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        session_cookies: Optional[dict[str, str]] = None,
        base_url: str = "https://bibliotheques.paris.fr",
        timeout: float = 15.0,
        session: Optional[requests.Session] = None,
    ) -> None:
        """Initialize the Paris library client."""
        ...

    def __enter__(self) -> "ParisBibClient": ...
    def __exit__(self, exc_type, exc_val, exc_tb) -> None: ...

    # -------------------------------------------------------------
    # LAYER 1: Low-Level 1:1 Syracuse Endpoints
    # -------------------------------------------------------------
    def login(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        remember_me: bool = False,
    ) -> bool:
        """Authenticate via /Portal/Recherche/logon.svc/logon."""
        ...

    def get_summary(
        self, user_unique_identifier: Optional[str] = None
    ) -> AccountSummary:
        """Fetch account metrics for the primary user or a paired user GUID."""
        ...

    def get_loans(
        self, user_unique_identifier: Optional[str] = None
    ) -> LoanCollection:
        """Fetch active loans for the primary user or a paired user GUID."""
        ...

    def get_bookings(
        self, user_unique_identifier: Optional[str] = None
    ) -> BookingCollection:
        """Fetch reservations for the primary user or a paired user GUID."""
        ...

    def get_paired_accounts(self) -> list[PairedAccount]:
        """Fetch all linked family accounts."""
        ...

    def renew_loans(
        self,
        loans: Sequence[Loan | dict[str, Any]],
        user_unique_identifier: Optional[str] = None,
    ) -> RenewalReport:
        """Batch-renew loans via /Portal/Services/UserAccountService.svc/RenewLoans."""
        ...

    def renew_loan(
        self,
        loan_or_holding: Loan | str,
        user_unique_identifier: Optional[str] = None,
    ) -> bool:
        """Renew a single loan by Loan instance or holding ID."""
        ...

    # -------------------------------------------------------------
    # LAYER 2: High-Level Convenience Facade & Family Coordinator
    # -------------------------------------------------------------
    def get_family(self) -> FamilyOverview:
        """Fetch summaries, loans, and bookings for primary and all paired cards."""
        ...

    def get_family_loans(self) -> LoanCollection:
        """Shortcut to fetch all loans across all family cards."""
        ...

    def get_family_bookings(self) -> BookingCollection:
        """Shortcut to fetch all bookings across all family cards."""
        ...

    def renew_all_family_loans(
        self,
        due_within_days: Optional[int] = None,
        library: Optional[str] = None,
        only_renewable: bool = True,
    ) -> RenewalReport:
        """Batch-renew loans across all family accounts matching criteria."""
        ...
```

---

### 6.2. End-to-End Usage Examples

#### Example 1: Single Glance Family Overview & Status
```python
from parisbibpy import ParisBibClient

with ParisBibClient(username="22272392XXXXXX", password="PIN") as client:
    family = client.get_family()
    loans = family.loans

    print(f"Total family loans: {loans.total_count}")
    print(f"Overdue items: {loans.overdue_count}")
    print(f"Renewable items: {loans.renewable_count}")
    print(f"Earliest return date: {loans.earliest_due_date}")
```

#### Example 2: Multi-Dimensional Grouping (Account, Type, Library)
```python
with ParisBibClient(username="22272392XXXXXX", password="PIN") as client:
    loans = client.get_family_loans()

    # 1. Group by Account (Family Members)
    print("=== LOANS PER FAMILY MEMBER ===")
    for account_name, acc_loans in loans.group_by_account().items():
        print(f"👤 {account_name}: {acc_loans.total_count} items ({acc_loans.overdue_count} overdue)")

    # 2. Group by Type of Document (Books, Comics, Board Games)
    print("\n=== LOANS PER DOCUMENT TYPE ===")
    for doc_type, type_loans in loans.group_by_type().items():
        print(f"📦 {doc_type}: {type_loans.total_count} items")

    # 3. Group by Library
    print("\n=== LOANS PER LIBRARY BRANCH ===")
    for library, branch_loans in loans.group_by_library().items():
        print(f"🏛️ {library}: {branch_loans.total_count} items")
```

#### Example 3: Trip Planning & Visit Prioritization
```python
with ParisBibClient(username="22272392XXXXXX", password="PIN") as client:
    loans = client.get_family_loans()

    # plan_library_trips() sorts branches by urgency of return date
    print("=== RECOMMENDED LIBRARY VISITS ===")
    for trip in loans.plan_library_trips():
        urgency = "🚨 URGENT" if trip.has_urgency(within_days=7) else "OK"
        print(f"\n[{urgency}] Library: {trip.library}")
        print(f"  - Total items to drop off: {trip.total_items}")
        print(f"  - Earliest due date: {trip.earliest_due_date} ({trip.days_until_first_due} days left)")

        # Print items packed for this library trip
        for item in trip.loans.sorted_by_due_date():
            status = "OVERDUE" if item.is_late else f"{item.days_remaining}d left"
            print(f"    • [{status}] '{item.title}' (Card: {item.account_name})")
```

#### Example 4: Reservations & Ready-for-Pickup Alerts
```python
with ParisBibClient(username="22272392XXXXXX", password="PIN") as client:
    bookings = client.get_family_bookings()

    print(f"Active reservations across family: {bookings.total_count}")
    
    # Check items ready for pickup before a library visit
    for b in bookings.ready_for_pickup:
        print(f"🎉 Ready at {b.pickup_location}: '{b.title}' for {b.account_name} (pickup by {b.available_until})")
```

#### Example 5: High-Level Batch Renewal Across Family Accounts
```python
with ParisBibClient(username="22272392XXXXXX", password="PIN") as client:
    # Extend all items due within 5 days across every family card:
    report = client.renew_all_family_loans(due_within_days=5)

    print(f"Successfully renewed: {len(report.succeeded)}")
    for loan in report.succeeded:
        print(f"  ✅ {loan.title} ({loan.account_name}) -> new due date: {loan.due_date}")

    if report.failed:
        print(f"Renewal blocked for {len(report.failed)} items:")
        for failure in report.failed:
            print(f"  ❌ {failure.loan.title}: {failure.reason}")
```

---

## 7. Error Handling Hierarchy

```text
ParisBibError (Base exception)
├── AuthenticationError        # Invalid credentials or logon failure
│   └── SessionExpiredError   # Session was previously valid but timed out (_syrSessGuid expired)
├── SyracuseApiError           # Syracuse returned success=false with errors
├── ResourceNotFoundError      # Specified record or holding ID not found
└── RenewalError               # Syracuse rejected renewal with specific reason
```

---

## 8. Authentication & Session Strategy

1. **Direct Logon (Primary)**:
   - Client sends a synchronous `POST /Portal/Recherche/logon.svc/logon` with form-encoded body:
     ```text
     username=<card_barcode>&password=<pin_or_password>&rememberMe=false
     ```
   - On success, Syracuse sets the `_syrSessGuid` cookie in the `requests.Session` cookie jar.
   - Subsequent calls to `UserAccountService.svc` automatically include `_syrSessGuid`.
   - If `username` and `password` are provided, login occurs automatically on the first request or entering the context manager.

2. **Pre-authenticated Session Import (Alternative)**:
   - Accept pre-authenticated cookie dictionary (`{"_syrSessGuid": "..."}`) from environment variables for headless cron jobs.
   - Validate session on first request; raise `SessionExpiredError` if expired.

---

## 9. Development & Release Roadmap

- [x] **Milestone 1**: Reverse-engineer core endpoints (`logon`, `RetrieveAccountSummary`, `ListLoans`, `ListUserPairings`) and document schemas.
- [ ] **Milestone 2**: Setup Python packaging (`pyproject.toml`, test harness with `pytest` and `responses`).
- [ ] **Milestone 3**: Implement date parsing, response envelopes, and Pydantic domain models (`AccountSummary`, `Loan`, `Booking`, `PairedAccount`).
- [ ] **Milestone 4**: Implement `LoanCollection`, `BookingCollection`, `LibraryTrip`, and multi-dimensional grouping methods.
- [ ] **Milestone 5**: Implement Layer 1 client operations (`get_summary`, `get_loans`, `get_bookings`, `get_paired_accounts`, `renew_loan`).
- [ ] **Milestone 6**: Implement Layer 2 facade (`FamilyOverview`, `get_family_loans`, `renew_all_family_loans`, `plan_library_trips`).
- [ ] **Milestone 7**: Build CLI tool (`parisbibpy summary`, `parisbibpy trips`, `parisbibpy renew`) and Home Assistant sensor integration blueprint.