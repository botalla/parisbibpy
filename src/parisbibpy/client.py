import sys
from collections import defaultdict
from collections.abc import Sequence
from typing import Any

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

import requests
from curl_cffi import requests as curl_requests
from curl_cffi.requests.errors import CurlError, RequestsError

from parisbibpy.exceptions import (
    AuthenticationError,
    ParisBibError,
    RenewalError,
    ResourceNotFoundError,
    SessionExpiredError,
    SyracuseApiError,
)
from parisbibpy.models.account import AccountLoans, AccountSummary, PairedAccount
from parisbibpy.models.booking import Booking, BookingCollection
from parisbibpy.models.family import FamilyOverview
from parisbibpy.models.loan import Loan, LoanCollection
from parisbibpy.models.renewal import RenewalFailure, RenewalReport

_DEFAULT_SENTINEL = object()


class ParisBibClient:
    """Synchronous client providing both Layer 1 (direct API) and Layer 2 (family facade) access."""

    DEFAULT_IMPERSONATE: str | None = "chrome"

    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        session_cookies: dict[str, str] | None = None,
        base_url: str = "https://bibliotheques.paris.fr",
        timeout: float = 15.0,
        session: requests.Session | Any | None = None,
        impersonate: Any = _DEFAULT_SENTINEL,
    ) -> None:
        self.username = username
        self.password = password
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        self._external_session = session is not None
        actual_impersonate: str | None = (
            self.DEFAULT_IMPERSONATE if impersonate is _DEFAULT_SENTINEL else impersonate
        )

        self._session: Any
        if session is not None:
            self._session = session
        elif actual_impersonate is not None:
            self._session = curl_requests.Session(impersonate=actual_impersonate)
        else:
            self._session = requests.Session()

        self._session.headers.update(
            {
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Origin": "https://bibliotheques.paris.fr",
                "Referer": "https://bibliotheques.paris.fr/",
            }
        )
        if not actual_impersonate:
            self._session.headers.update(
                {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/131.0.0.0 Safari/537.36"
                    )
                }
            )

        if session_cookies:
            self._session.cookies.update(session_cookies)

        self._authenticated = bool(self._session.cookies.get("_syrSessGuid"))

    def __enter__(self) -> Self:
        if self.username and self.password and not self._authenticated:
            self.login()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP session if it was created internally."""
        if not self._external_session:
            self._session.close()

    def _ensure_authenticated(self) -> None:
        """Ensure session has credentials or cookie before making requests."""
        if not self._authenticated and self.username and self.password:
            self.login()

    def _warmup_session(self) -> None:
        """Perform an initial GET request to establish Syracuse and WAF session cookies if jar is empty."""
        if not self._session.cookies:
            warmup_headers = {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
            }
            try:
                self._session.get(
                    f"{self.base_url}/",
                    headers=warmup_headers,
                    timeout=self.timeout,
                )
            except (requests.RequestException, RequestsError, CurlError):
                pass

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        data: Any | None = None,
        json: Any | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Execute an HTTP request and unpack Syracuse envelope."""
        url = f"{self.base_url}{path}"
        req_headers = dict(headers or {})

        try:
            resp = self._session.request(
                method=method,
                url=url,
                params=params,
                data=data,
                json=json,
                headers=req_headers,
                timeout=self.timeout,
            )
        except requests.exceptions.ChunkedEncodingError as e:
            raise SyracuseApiError(
                f"Connection severed by the library server ({url}). "
                "This typically indicates temporary rate-limiting or anti-bot throttling. "
                "Please wait a few minutes before retrying."
            ) from e
        except (requests.RequestException, RequestsError, CurlError) as e:
            raise SyracuseApiError(f"HTTP request to {url} failed: {e}") from e

        if resp.status_code == 401 or resp.status_code == 403:
            raise SessionExpiredError("Session has expired or credentials are invalid.")

        if resp.status_code == 404:
            raise ResourceNotFoundError(f"Endpoint not found: {url}")

        if not resp.ok:
            raise SyracuseApiError(
                f"Syracuse HTTP error {resp.status_code}: {resp.text[:200]}"
            )

        try:
            res_json: dict[str, Any] = resp.json()
        except ValueError as e:
            raise SyracuseApiError(f"Invalid JSON returned from {url}: {resp.text[:200]}") from e

        # Validate Syracuse envelope
        success = res_json.get("success", True)
        errors = res_json.get("errors") or []
        if not success or errors:
            raise SyracuseApiError(
                message=res_json.get("message") or "Syracuse returned an error.",
                errors=errors,
                raw_response=res_json,
            )

        return res_json

    # =========================================================================
    # LAYER 1: Low-Level 1:1 Syracuse Endpoints
    # =========================================================================

    def login(
        self,
        username: str | None = None,
        password: str | None = None,
        remember_me: bool = False,
    ) -> bool:
        """Authenticate via /Portal/Recherche/logon.svc/logon."""
        u = username or self.username
        p = password or self.password

        if not u or not p:
            raise AuthenticationError("Username and password must be provided to log in.")

        self._warmup_session()

        payload = {
            "username": u,
            "password": p,
            "rememberMe": "true" if remember_me else "false",
        }

        headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}
        try:
            res_json = self._request("POST", "/Portal/Recherche/logon.svc/logon", data=payload, headers=headers)
        except SyracuseApiError as e:
            err_msg = None
            if e.errors and isinstance(e.errors, list) and len(e.errors) > 0:
                err_item = e.errors[0]
                if isinstance(err_item, dict):
                    err_msg = err_item.get("msg")
            raise AuthenticationError(err_msg or str(e)) from e

        d = res_json.get("d")
        if isinstance(d, dict):
            if not d.get("Success", False):
                err_msg = d.get("ErrorMessage") or "Login failed with invalid credentials."
                raise AuthenticationError(err_msg)
        elif isinstance(d, str):
            if d.lower() == "anonymous" or not res_json.get("success", False):
                raise AuthenticationError("Login failed with invalid credentials.")
        elif not res_json.get("success", False):
            raise AuthenticationError("Login failed with invalid credentials.")

        self._authenticated = True
        return True

    def get_summary(
        self, user_unique_identifier: str | None = None
    ) -> AccountSummary:
        """Fetch account metrics for the primary user or a paired user GUID."""
        self._ensure_authenticated()
        params = {
            "serviceCode": "SYRACUSE",
            "userUniqueIdentifier": user_unique_identifier or "",
        }
        res_json = self._request(
            "GET",
            "/Portal/Services/UserAccountService.svc/RetrieveAccountSummary",
            params=params,
        )

        d = res_json.get("d") or {}
        summary_raw = d.get("AccountSummary") or {}
        return AccountSummary.model_validate(summary_raw)

    def get_loans(
        self, user_unique_identifier: str | None = None
    ) -> LoanCollection:
        """Fetch active loans for the primary user or a paired user GUID."""
        self._ensure_authenticated()
        params = {
            "serviceCode": "SYRACUSE",
            "userUniqueIdentifier": user_unique_identifier or "",
        }
        res_json = self._request(
            "GET",
            "/Portal/Services/UserAccountService.svc/ListLoans",
            params=params,
        )

        d = res_json.get("d") or {}
        loans_raw = d.get("Loans") or []
        loans = [Loan.model_validate(item) for item in loans_raw]
        return LoanCollection(loans)

    def get_bookings(
        self, user_unique_identifier: str | None = None
    ) -> BookingCollection:
        """Fetch active reservations (bookings) for the primary user or a paired user GUID."""
        self._ensure_authenticated()
        params = {
            "serviceCode": "SYRACUSE",
            "userUniqueIdentifier": user_unique_identifier or "",
        }
        res_json = self._request(
            "GET",
            "/Portal/Services/UserAccountService.svc/ListBookings",
            params=params,
        )

        d = res_json.get("d") or {}
        bookings_raw = d.get("Bookings") or []
        bookings = [Booking.model_validate(item) for item in bookings_raw]
        return BookingCollection(bookings)

    def get_paired_accounts(self) -> list[PairedAccount]:
        """Fetch all linked family accounts."""
        self._ensure_authenticated()
        res_json = self._request(
            "GET",
            "/Portal/Services/UserAccountService.svc/ListUserPairings",
        )

        d = res_json.get("d") or {}
        pairings_raw = d.get("UserPairings") or []
        return [PairedAccount.model_validate(p) for p in pairings_raw]

    def renew_loans(
        self,
        loans: Sequence[Loan | dict[str, Any]],
        user_unique_identifier: str | None = None,
    ) -> RenewalReport:
        """Batch-renew loans for an account via /Portal/Services/UserAccountService.svc/RenewLoans."""
        self._ensure_authenticated()

        if not loans:
            return RenewalReport()

        loans_payload = [
            l.to_syracuse_dict() if isinstance(l, Loan) else l
            for l in loans
        ]
        payload = {
            "loans": loans_payload,
            "userUniqueIdentifier": user_unique_identifier or "",
        }

        res_json = self._request(
            "POST",
            "/Portal/Services/UserAccountService.svc/RenewLoans",
            json=payload,
        )

        d = res_json.get("d") or {}
        successes_raw = d.get("Successes") or []
        errors_raw = d.get("Errors") or []

        report = RenewalReport()

        # Map holding_id to original loan for tracking context
        orig_map: dict[str, Loan] = {}
        for l in loans:
            if isinstance(l, Loan):
                orig_map[l.holding_id] = l

        for succ in successes_raw:
            try:
                updated_loan = Loan.model_validate(succ)
                if updated_loan.holding_id in orig_map:
                    orig = orig_map[updated_loan.holding_id]
                    updated_loan.account_name = orig.account_name
                    updated_loan.account_barcode = orig.account_barcode
                    updated_loan.user_unique_identifier = orig.user_unique_identifier
                report.succeeded.append(updated_loan)
            except (ValueError, TypeError, KeyError):
                continue

        for err in errors_raw:
            holding_id = str(err.get("HoldingId") or err.get("Id") or "")
            reason = (
                err.get("CannotRenewReason")
                or err.get("Message")
                or "Renewal rejected by library server"
            )
            loan_obj = orig_map.get(holding_id)
            if not loan_obj:
                try:
                    loan_obj = Loan.model_validate(err)
                except (ValueError, TypeError, KeyError):
                    continue
            report.failed.append(RenewalFailure(loan=loan_obj, reason=reason))

        return report

    def renew_loan(
        self,
        loan_or_holding: Loan | str,
        user_unique_identifier: str | None = None,
    ) -> bool:
        """Renew a single loan by Loan instance or holding ID."""
        if isinstance(loan_or_holding, Loan):
            guid = user_unique_identifier or loan_or_holding.user_unique_identifier
            report = self.renew_loans([loan_or_holding], user_unique_identifier=guid)
        else:
            mock_payload = {
                "HoldingId": loan_or_holding,
                "Id": loan_or_holding,
                "RecordBase": "SYRACUSE",
            }
            report = self.renew_loans([mock_payload], user_unique_identifier=user_unique_identifier)

        if not report.is_all_successful and report.failed:
            failure = report.failed[0]
            raise RenewalError(
                failure.reason,
                holding_id=failure.loan.holding_id,
                reason=failure.reason,
            )

        return True

    # =========================================================================
    # LAYER 2: High-Level Convenience Facade & Family Coordinator
    # =========================================================================

    def get_family(self) -> FamilyOverview:
        """Fetch summaries, loans, and bookings for primary and all paired cards."""
        self._ensure_authenticated()

        # 1. Fetch primary account
        primary_summary = self.get_summary()
        primary_loans = self.get_loans()
        try:
            primary_bookings = self.get_bookings()
        except SyracuseApiError:
            primary_bookings = BookingCollection([])

        # Tag primary items with cardholder context
        for loan in primary_loans:
            loan.account_name = primary_summary.display_name
            loan.account_barcode = primary_summary.barcode

        for b in primary_bookings:
            b.account_name = primary_summary.display_name
            b.account_barcode = primary_summary.barcode

        primary_account = AccountLoans(
            account_name=primary_summary.display_name,
            barcode=primary_summary.barcode,
            unique_identifier=None,
            summary=primary_summary,
            loans=primary_loans,
            bookings=primary_bookings,
        )

        # 2. Fetch paired accounts with per-account resilience
        paired_accounts: list[AccountLoans] = []
        failed_accounts: list[Any] = []

        for pairing in self.get_paired_accounts():
            uuid = pairing.user_unique_identifier

            # Step 1: Attempt summary (fallback to dummy summary if Syracuse session is missing)
            summary: AccountSummary
            try:
                summary = self.get_summary(uuid)
            except (ParisBibError, requests.RequestException) as e:
                failed_accounts.append((pairing, f"Summary: {e}"))
                summary = AccountSummary(
                    Barcode=pairing.barcode,
                    DisplayName=pairing.display_name,
                    LoansTotalCount=0,
                )

            # Step 2: Attempt loans independently
            loans: LoanCollection
            try:
                loans = self.get_loans(uuid)
                if summary.loans_total_count == 0 and len(loans) > 0:
                    summary.loans_total_count = len(loans)
            except (ParisBibError, requests.RequestException) as e:
                loans = LoanCollection([])
                failed_accounts.append((pairing, f"Loans: {e}"))

            # Step 3: Attempt bookings independently
            bookings: BookingCollection
            try:
                bookings = self.get_bookings(uuid)
            except (ParisBibError, requests.RequestException):
                bookings = BookingCollection([])

            # Tag paired items with cardholder context
            for loan in loans:
                loan.account_name = pairing.display_name
                loan.account_barcode = pairing.barcode
                loan.user_unique_identifier = uuid

            for b in bookings:
                b.account_name = pairing.display_name
                b.account_barcode = pairing.barcode
                b.user_unique_identifier = uuid

            paired_accounts.append(
                AccountLoans(
                    account_name=pairing.display_name,
                    barcode=pairing.barcode,
                    unique_identifier=uuid,
                    summary=summary,
                    loans=loans,
                    bookings=bookings,
                )
            )

        return FamilyOverview(
            primary_account=primary_account,
            paired_accounts=paired_accounts,
            failed_accounts=failed_accounts,
        )

    def get_family_loans(self) -> LoanCollection:
        """Shortcut to fetch all loans across all family cards."""
        return self.get_family().loans

    def get_family_bookings(self) -> BookingCollection:
        """Shortcut to fetch all bookings across all family cards."""
        return self.get_family().bookings

    def renew_all_family_loans(
        self,
        due_within_days: int | None = None,
        library: str | None = None,
        only_renewable: bool = True,
    ) -> RenewalReport:
        """Batch-renew loans across all family accounts in single API calls per card."""
        family = self.get_family()
        candidates = family.loans.filter(due_within_days=due_within_days, library=library)

        report = RenewalReport()

        # Group candidate loans by card (user_unique_identifier)
        by_card: dict[str | None, list[Loan]] = defaultdict(list)
        for loan in candidates:
            if only_renewable and not loan.can_renew:
                report.skipped_not_renewable.append(loan)
                continue
            by_card[loan.user_unique_identifier].append(loan)

        # Execute 1 RenewLoans request per card account
        for card_guid, card_loans in by_card.items():
            if not card_loans:
                continue
            try:
                card_report = self.renew_loans(card_loans, user_unique_identifier=card_guid)
                report.succeeded.extend(card_report.succeeded)
                report.failed.extend(card_report.failed)
            except (ParisBibError, requests.RequestException) as e:
                for l in card_loans:
                    report.failed.append(RenewalFailure(loan=l, reason=str(e)))

        return report
