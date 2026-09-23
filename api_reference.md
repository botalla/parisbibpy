# Python API Reference

Complete API reference for **`parisbibpy`**, a modern, synchronous, type-safe Python client for the Paris public library system (Archimed Syracuse portal backend).

---

## Table of Contents

- [Client (`ParisBibClient`)](#client-parisbibclient)
  - [Initialization & Context Management](#initialization--context-management)
  - [Layer 1: Low-Level Endpoints](#layer-1-low-level-endpoints)
  - [Layer 2: Family Coordinator Facade](#layer-2-family-coordinator-facade)
- [Domain Models & Collections](#domain-models--collections)
  - [FamilyOverview](#familyoverview)
  - [AccountLoans](#accountloans)
  - [LoanCollection](#loancollection)
  - [Loan](#loan)
  - [LibraryTrip](#librarytrip)
  - [BookingCollection](#bookingcollection)
  - [Booking](#booking)
  - [AccountSummary](#accountsummary)
  - [PairedAccount](#pairedaccount)
  - [RenewalReport & RenewalFailure](#renewalreport--renewalfailure)
- [Exceptions](#exceptions)

---

## Client (`ParisBibClient`)

```python
from parisbibpy import ParisBibClient
```

The primary entry point. Supports both direct 1:1 Syracuse API calls (Layer 1) and the high-level family management facade (Layer 2).

### Initialization & Context Management

```python
ParisBibClient(
    username: str | None = None,
    password: str | None = None,
    session_cookies: dict[str, str] | None = None,
    base_url: str = "https://bibliotheques.paris.fr",
    timeout: float = 15.0,
    session: requests.Session | curl_cffi.requests.Session | None = None,
    impersonate: str | None = "chrome",
)
```

#### Parameters:
- `username` *(str | None)*: Primary library card barcode (e.g. `"22272392XXXXXX"`).
- `password` *(str | None)*: Account password or birthdate PIN (e.g. `"DDMMYYYY"`).
- `session_cookies` *(dict[str, str] | None)*: Pre-existing session cookies (e.g. `{"_syrSessGuid": "..."}`). If provided, bypasses `login()`.
- `base_url` *(str)*: Syracuse portal base URL (default: `https://bibliotheques.paris.fr`).
- `timeout` *(float)*: HTTP network timeout in seconds (default: `15.0`).
- `session` *(Session | None)*: Custom `requests` or `curl_cffi` session. If omitted, an internal session is instantiated.
- `impersonate` *(str | None)*: Browser TLS fingerprint to impersonate via `curl_cffi` (default: `"chrome"`). Set to `None` to use standard Python `requests`.

#### Context Manager:
```python
with ParisBibClient(username="...", password="...") as client:
    # Automatically calls client.login() if credentials are provided
    family = client.get_family()
# Automatically closes underlying HTTP session and connection pool
```

---

### Layer 1: Low-Level Endpoints

Direct 1:1 mappings to Archimed Syracuse JSON-RPC / WCF services (`UserAccountService.svc`, `logon.svc`).

#### `login(username=None, password=None, remember_me=False) -> bool`
Authenticates against `/Portal/Recherche/logon.svc/logon`. Establishes the `_syrSessGuid` session cookie.
- **Raises**: `AuthenticationError` on invalid credentials.

#### `get_summary(user_unique_identifier=None) -> AccountSummary`
Fetches high-level metrics for an account from `RetrieveAccountSummary`.
- **Parameters**: `user_unique_identifier` *(str | None)*: Target account GUID. If omitted, queries the primary account.
- **Returns**: `AccountSummary`.

#### `get_loans(user_unique_identifier=None) -> LoanCollection`
Fetches active borrowed documents from `ListLoans`.
- **Parameters**: `user_unique_identifier` *(str | None)*: Target account GUID. If omitted, queries the primary account.
- **Returns**: `LoanCollection`.

#### `get_bookings(user_unique_identifier=None) -> BookingCollection`
Fetches active reservations and holds from `ListBookings`.
- **Parameters**: `user_unique_identifier` *(str | None)*: Target account GUID. If omitted, queries the primary account.
- **Returns**: `BookingCollection`.

#### `get_paired_accounts() -> list[PairedAccount]`
Fetches linked family accounts from `ListUserPairings`.
- **Returns**: `list[PairedAccount]`.

#### `renew_loans(loans, user_unique_identifier=None) -> RenewalReport`
Submits one or more loans for extension in a single batch request to `RenewLoans`.
- **Parameters**:
  - `loans` *(Sequence[Loan | dict[str, Any]])*: List of loans or holding dicts to renew.
  - `user_unique_identifier` *(str | None)*: Account GUID owning the loans.
- **Returns**: `RenewalReport`.

#### `renew_loan(loan_or_holding, user_unique_identifier=None) -> bool`
Convenience wrapper to renew a single loan by `Loan` object or holding barcode string.
- **Returns**: `True` if successfully extended.
- **Raises**: `RenewalError` if rejected by Syracuse.

#### `close() -> None`
Closes the underlying session and releases pooled TCP connections.

---

### Layer 2: Family Coordinator Facade

High-level multi-card orchestration, automatic tagging, and trip planning.

#### `get_family() -> FamilyOverview`
Queries the primary card and all linked family cards concurrently/sequentially, tags all loans and bookings with cardholder context, and returns a unified `FamilyOverview`. Resilient to individual paired card errors.

#### `get_family_loans() -> LoanCollection`
Convenience method returning a combined `LoanCollection` containing all active loans across all family accounts.

#### `get_family_bookings() -> BookingCollection`
Convenience method returning a combined `BookingCollection` containing all reservations across all family accounts.

#### `renew_all_family_loans(due_within_days=None) -> RenewalReport`
Identifies all renewable items across all family accounts (optionally filtered by urgency) and executes batch renewals grouped by card account (**1 batch request per family card**).

---

## Domain Models & Collections

### `FamilyOverview`

```python
from parisbibpy import FamilyOverview
```

Container representing the complete multi-card household state.

#### Attributes:
- `primary_account` *(AccountLoans)*: Primary cardholder data.
- `paired_accounts` *(list[AccountLoans])*: List of linked cardholder data.
- `failed_accounts` *(list[tuple[Any, str]])*: Accounts that could not be loaded, along with the diagnostic reason.

#### Properties:
- `accounts -> list[AccountLoans]`: All successfully loaded accounts (primary + paired).
- `loans -> LoanCollection`: Combined collection of all family loans.
- `bookings -> BookingCollection`: Combined collection of all family reservations.

#### Methods:
- `plan_library_trips() -> list[LibraryTrip]`: Groups family loans by library branch and ranks branches by return urgency.

---

### `AccountLoans`

```python
from parisbibpy import AccountLoans
```

Bundles an individual cardholder's metadata, summary, loans, and reservations.

#### Attributes:
- `account_name` *(str)*: Patron display name.
- `barcode` *(str)*: Library card barcode.
- `unique_identifier` *(str | None)*: Syracuse account GUID (None for primary card).
- `summary` *(AccountSummary)*: Patron overview metrics.
- `loans` *(LoanCollection)*: Patron's active loans.
- `bookings` *(BookingCollection)*: Patron's reservations.

---

### `LoanCollection`

```python
from parisbibpy import LoanCollection
```

Rich collection extending `UserList[Loan]` with multi-dimensional filtering, grouping, and trip planning.

#### Properties:
- `total_count -> int`: Total number of loans in the collection.
- `overdue_count -> int`: Count of loans currently past their due date.
- `renewable_count -> int`: Count of loans eligible for online renewal.
- `earliest_due_date -> date | None`: The closest due date across all items.

#### Methods:
- `group_by_library() -> dict[str, list[Loan]]`: Groups loans by physical library branch name.
- `group_by_account() -> dict[str, list[Loan]]`: Groups loans by cardholder display name.
- `group_by_type() -> dict[str, list[Loan]]`: Groups loans by document category (e.g. `"BD"`, `"Livre"`, `"Jeu de société"`).
- `filter(library=None, account_name=None, doc_type=None, is_overdue=None, is_renewable=None, due_within_days=None) -> LoanCollection`: Returns a filtered sub-collection.
- `due_soon(days=3) -> LoanCollection`: Returns items overdue or due within `days` days.
- `sorted_by_due_date(reverse=False) -> LoanCollection`: Returns items sorted chronologically by return deadline.
- `plan_library_trips() -> list[LibraryTrip]`: Organizes loans into drop-off packing lists sorted by urgency.

---

### `Loan`

```python
from parisbibpy import Loan
```

Represents an individual borrowed document.

#### Attributes:
- `id` *(str)*: Syracuse loan ID.
- `holding_id` *(str)*: Physical item copy barcode.
- `record_id` *(str)*: Bibliographic catalog record ID.
- `title` *(str)*: Title of the document.
- `type_of_document` *(str)*: Material type (`"BD"`, `"Livre"`, `"Revue"`, `"Jeu de société"`).
- `location` *(str)*: Library branch where the item was borrowed.
- `due_date` *(date | None)*: Return deadline date.
- `state` *(str)*: Textual state (`"En cours"`, `"A rendre bientôt"`).
- `is_late` *(bool)*: `True` if the loan is overdue.
- `is_soon_late` *(bool)*: `True` if the return deadline is imminent.
- `can_renew` *(bool)*: `True` if online renewal is currently permitted.
- `cannot_renew_reason` *(str | None)*: Explanation if renewal is blocked.
- `thumbnail_url` *(str | None)*: Book cover thumbnail URL.
- `account_name` *(str | None)*: Display name of the family member who borrowed it.
- `account_barcode` *(str | None)*: Barcode of the family member's card.
- `user_unique_identifier` *(str | None)*: Account GUID.

#### Properties:
- `days_remaining -> int | None`: Calendar days until the due date (negative if overdue).
- `urgency_score -> int`: Numerical priority used for visit sorting.

#### Methods:
- `to_syracuse_dict() -> dict[str, Any]`: Formats the loan object for Syracuse `RenewLoans` payloads.

---

### `LibraryTrip`

```python
from parisbibpy import LibraryTrip
```

Drop-off plan for a specific library branch.

#### Attributes:
- `library` *(str)*: Branch name (e.g. `"75015 - Andrée Chedid"`).
- `loans` *(LoanCollection)*: Items to return to this branch.

#### Properties:
- `total_items -> int`: Count of books/items for this library.
- `overdue_items -> int`: Count of overdue items for this library.
- `earliest_due_date -> date | None`: Earliest deadline among items at this branch.
- `urgency_score -> int`: Sorting rank based on overdue items and deadline proximity.

---

### `BookingCollection`

```python
from parisbibpy import BookingCollection
```

Collection extending `UserList[Booking]`.

#### Properties:
- `total_count -> int`: Total active reservations.
- `ready_for_pickup -> list[Booking]`: Items on the shelf ready for collection.
- `in_transit -> list[Booking]`: Items in queue or shipping between branches.

#### Methods:
- `group_by_library() -> dict[str, list[Booking]]`: Groups reservations by pickup branch.

---

### `Booking`

```python
from parisbibpy import Booking
```

Represents a hold or reservation.

#### Attributes:
- `id` *(str)*: Syracuse booking identifier.
- `holding_id` *(str | None)*: Assigned physical item barcode.
- `record_id` *(str)*: Bibliographic catalog record ID.
- `title` *(str)*: Title of the reserved item.
- `type_of_document` *(str)*: Material type (`"BD"`, `"Livre"`, etc.).
- `pickup_location` *(str)*: Branch where item will be picked up.
- `state` *(str)*: Current processing state.
- `is_available` *(bool)*: `True` if ready on the shelf.
- `booking_date` *(datetime | None)*: Date the request was submitted.
- `available_until` *(date | None)*: Expiration deadline for patron pickup.
- `rank_in_queue` *(int | None)*: Queue rank if waiting.
- `can_cancel` *(bool)*: Whether online cancellation is allowed.
- `account_name` *(str | None)*: Name of the cardholder.

---

### `AccountSummary`

```python
from parisbibpy import AccountSummary
```

High-level status metrics for a library card.

#### Attributes:
- `barcode` *(str)*: Card barcode.
- `display_name` *(str)*: Patron name.
- `loans_total_count` *(int)*: Total items currently borrowed.
- `loans_late_count` *(int)*: Number of overdue items.
- `loans_next_handing_date` *(datetime | None)*: Next due date.
- `bookings_total_count` *(int)*: Active reservation count.

#### Properties:
- `has_overdue -> bool`: `True` if `loans_late_count > 0`.
- `days_until_next_due -> int | None`: Calendar days until the closest return date.

---

### `PairedAccount`

```python
from parisbibpy import PairedAccount
```

Linked card account returned by `ListUserPairings`.

#### Attributes:
- `id` *(int)*: Pairing ID.
- `barcode` *(str)*: Linked card barcode.
- `display_name` *(str)*: Linked patron name.
- `user_unique_identifier` *(str)*: Linked account GUID.
- `is_reciprocal` *(bool)*: Whether mutual sharing is enabled.

---

### `RenewalReport` & `RenewalFailure`

```python
from parisbibpy import RenewalReport, RenewalFailure
```

Summary outcome of a batch renewal operation.

#### `RenewalReport` Attributes:
- `succeeded` *(list[Loan])*: Loans successfully extended.
- `failed` *(list[RenewalFailure])*: Loans rejected by the library server.
- `skipped_not_renewable` *(list[Loan])*: Loans omitted because `can_renew` was `False`.

#### `RenewalReport` Properties:
- `total_attempted -> int`: Total loans submitted.
- `is_all_successful -> bool`: `True` if all attempted loans succeeded.

#### `RenewalFailure` Attributes:
- `loan` *(Loan)*: The loan that failed to extend.
- `reason` *(str)*: Reason provided by the library backend (e.g. `"Exemplaire déjà prolongé aujourd'hui"`).

---

## Exceptions

```python
from parisbibpy import (
    ParisBibError,
    AuthenticationError,
    SessionExpiredError,
    SyracuseApiError,
    ResourceNotFoundError,
    RenewalError,
)
```

### Hierarchy:

```text
Exception
└── ParisBibError
    ├── AuthenticationError
    │   └── SessionExpiredError
    ├── SyracuseApiError
    ├── ResourceNotFoundError
    └── RenewalError
```

- **`ParisBibError`**: Base class for all library errors. Has `message` and optional `details`.
- **`AuthenticationError`**: Raised on invalid barcode or PIN.
- **`SessionExpiredError`**: Raised when a session cookie is expired or rejected (`401`/`403`).
- **`SyracuseApiError`**: Raised when Syracuse returns `"success": false` or an error payload. Contains `.errors` and `.raw_response`.
- **`ResourceNotFoundError`**: Raised when a requested resource or endpoint returns `404`.
- **`RenewalError`**: Raised by `renew_loan()` when single renewal fails. Contains `.holding_id` and `.reason`.
