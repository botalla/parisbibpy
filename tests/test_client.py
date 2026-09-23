"""Tests for ParisBibClient synchronous client (Layer 1 and Layer 2)."""

import pytest
import responses

from parisbibpy import Loan, ParisBibClient
from parisbibpy.exceptions import AuthenticationError


@responses.activate
def test_client_login_success():
    responses.add(
        responses.POST,
        "https://bibliotheques.paris.fr/Portal/Recherche/logon.svc/logon",
        json={"d": {"Success": True, "ErrorMessage": None}},
        headers={"Set-Cookie": "_syrSessGuid=abcdef12345; Path=/; HttpOnly"},
        status=200,
    )

    client = ParisBibClient(username="card123", password="pin")
    assert client.login() is True
    assert client._session.cookies.get("_syrSessGuid") == "abcdef12345"


@responses.activate
def test_client_login_failure():
    responses.add(
        responses.POST,
        "https://bibliotheques.paris.fr/Portal/Recherche/logon.svc/logon",
        json={"d": {"Success": False, "ErrorMessage": "Identifiant ou mot de passe incorrect."}},
        status=200,
    )

    client = ParisBibClient(username="card123", password="wrong_pin")
    with pytest.raises(AuthenticationError, match="Identifiant ou mot de passe incorrect"):
        client.login()


@responses.activate
def test_layer1_get_summary_and_loans(account_summary_data, list_loans_data):
    responses.add(
        responses.GET,
        "https://bibliotheques.paris.fr/Portal/Services/UserAccountService.svc/RetrieveAccountSummary",
        json=account_summary_data,
        status=200,
    )
    responses.add(
        responses.GET,
        "https://bibliotheques.paris.fr/Portal/Services/UserAccountService.svc/ListLoans",
        json=list_loans_data,
        status=200,
    )

    with ParisBibClient(session_cookies={"_syrSessGuid": "test-token"}) as client:
        summary = client.get_summary()
        assert summary.display_name == "Fred DUPONT"
        assert summary.loans_total_count == 19

        loans = client.get_loans()
        assert len(loans) == 3
        assert loans[0].title == "Empereur du Japon. 02"


@responses.activate
def test_layer2_get_family(account_summary_data, list_loans_data, user_pairings_data, list_bookings_data):
    # Primary account endpoints
    responses.add(
        responses.GET,
        "https://bibliotheques.paris.fr/Portal/Services/UserAccountService.svc/RetrieveAccountSummary?serviceCode=SYRACUSE&userUniqueIdentifier=",
        json=account_summary_data,
        status=200,
    )
    responses.add(
        responses.GET,
        "https://bibliotheques.paris.fr/Portal/Services/UserAccountService.svc/ListLoans?serviceCode=SYRACUSE&userUniqueIdentifier=",
        json=list_loans_data,
        status=200,
    )
    responses.add(
        responses.GET,
        "https://bibliotheques.paris.fr/Portal/Services/UserAccountService.svc/ListBookings?serviceCode=SYRACUSE&userUniqueIdentifier=",
        json=list_bookings_data,
        status=200,
    )
    responses.add(
        responses.GET,
        "https://bibliotheques.paris.fr/Portal/Services/UserAccountService.svc/ListUserPairings",
        json=user_pairings_data,
        status=200,
    )

    # Paired account endpoints for Child DOE (GUID 1234a0141c3a4ab7977b56116d6f17da)
    child_summary_data = dict(account_summary_data)
    child_summary_data["d"]["AccountSummary"]["DisplayName"] = "Child DOE"
    child_summary_data["d"]["AccountSummary"]["Barcode"] = "2227203240XXXX"

    responses.add(
        responses.GET,
        "https://bibliotheques.paris.fr/Portal/Services/UserAccountService.svc/RetrieveAccountSummary?serviceCode=SYRACUSE&userUniqueIdentifier=1234a0141c3a4ab7977b56116d6f17da",
        json=child_summary_data,
        status=200,
    )
    responses.add(
        responses.GET,
        "https://bibliotheques.paris.fr/Portal/Services/UserAccountService.svc/ListLoans?serviceCode=SYRACUSE&userUniqueIdentifier=1234a0141c3a4ab7977b56116d6f17da",
        json=list_loans_data,
        status=200,
    )
    responses.add(
        responses.GET,
        "https://bibliotheques.paris.fr/Portal/Services/UserAccountService.svc/ListBookings?serviceCode=SYRACUSE&userUniqueIdentifier=1234a0141c3a4ab7977b56116d6f17da",
        json=list_bookings_data,
        status=200,
    )

    with ParisBibClient(session_cookies={"_syrSessGuid": "test-token"}) as client:
        family = client.get_family()

        assert len(family.accounts) == 2
        # Primary has 3 loans, Child has 3 loans -> total 6
        assert family.loans.total_count == 6

        # Check that cardholder context was tagged on loans
        by_account = family.loans.group_by_account()
        assert "Fred DUPONT" in by_account
        assert "Child DOE" in by_account
        assert len(by_account["Fred DUPONT"]) == 3
        assert len(by_account["Child DOE"]) == 3

        # Bookings: 2 each -> total 4
        assert family.bookings.total_count == 4
        assert len(family.bookings.ready_for_pickup) == 2


@responses.activate
def test_renew_all_family_loans(account_summary_data, list_loans_data, user_pairings_data, list_bookings_data):
    # Setup family calls
    responses.add(
        responses.GET,
        "https://bibliotheques.paris.fr/Portal/Services/UserAccountService.svc/RetrieveAccountSummary?serviceCode=SYRACUSE&userUniqueIdentifier=",
        json=account_summary_data,
        status=200,
    )
    responses.add(
        responses.GET,
        "https://bibliotheques.paris.fr/Portal/Services/UserAccountService.svc/ListLoans?serviceCode=SYRACUSE&userUniqueIdentifier=",
        json=list_loans_data,
        status=200,
    )
    responses.add(
        responses.GET,
        "https://bibliotheques.paris.fr/Portal/Services/UserAccountService.svc/ListBookings?serviceCode=SYRACUSE&userUniqueIdentifier=",
        json=list_bookings_data,
        status=200,
    )
    responses.add(
        responses.GET,
        "https://bibliotheques.paris.fr/Portal/Services/UserAccountService.svc/ListUserPairings",
        json={"d": {"UserPairings": []}},
        status=200,
    )

    # RenewLoans endpoint for the 1 renewable item in list_loans
    responses.add(
        responses.POST,
        "https://bibliotheques.paris.fr/Portal/Services/UserAccountService.svc/RenewLoans",
        json={
            "d": {
                "ErrorCount": 0,
                "Errors": [],
                "SuccessCount": 1,
                "Successes": [list_loans_data["d"]["Loans"][0]],
            }
        },
        status=200,
    )

    with ParisBibClient(session_cookies={"_syrSessGuid": "test-token"}) as client:
        report = client.renew_all_family_loans()

        assert len(report.succeeded) == 1
        assert report.succeeded[0].title == "Empereur du Japon. 02"
        # 2 non-renewable items skipped
        assert len(report.skipped_not_renewable) == 2
        assert len(report.failed) == 0
        assert report.is_all_successful


@responses.activate
def test_layer1_renew_loans_batch(renew_loans_data, list_loans_data):
    responses.add(
        responses.POST,
        "https://bibliotheques.paris.fr/Portal/Services/UserAccountService.svc/RenewLoans",
        json=renew_loans_data,
        status=200,
    )

    with ParisBibClient(session_cookies={"_syrSessGuid": "test-token"}) as client:
        loans = [Loan.model_validate(item) for item in list_loans_data["d"]["Loans"][:2]]
        report = client.renew_loans(loans, user_unique_identifier="target-guid")

        assert len(report.succeeded) == 2
        assert report.succeeded[0].title == "Garfield gribouille"
        assert report.succeeded[1].title == "Souriez"
        assert report.is_all_successful


def test_client_curl_cffi_impersonate_initialization():
    from curl_cffi.requests.session import Session as CurlSession

    client = ParisBibClient(impersonate="chrome")
    assert isinstance(client._session, CurlSession)
    assert client._session.headers.get("X-Requested-With") == "XMLHttpRequest"
    client.close()


@responses.activate
def test_get_family_resilient_to_paired_account_failure(account_summary_data, list_loans_data, user_pairings_data, list_bookings_data):
    # Primary account succeeds
    responses.add(
        responses.GET,
        "https://bibliotheques.paris.fr/Portal/Services/UserAccountService.svc/RetrieveAccountSummary?serviceCode=SYRACUSE&userUniqueIdentifier=",
        json=account_summary_data,
        status=200,
    )
    responses.add(
        responses.GET,
        "https://bibliotheques.paris.fr/Portal/Services/UserAccountService.svc/ListLoans?serviceCode=SYRACUSE&userUniqueIdentifier=",
        json=list_loans_data,
        status=200,
    )
    responses.add(
        responses.GET,
        "https://bibliotheques.paris.fr/Portal/Services/UserAccountService.svc/ListBookings?serviceCode=SYRACUSE&userUniqueIdentifier=",
        json=list_bookings_data,
        status=200,
    )
    responses.add(
        responses.GET,
        "https://bibliotheques.paris.fr/Portal/Services/UserAccountService.svc/ListUserPairings",
        json=user_pairings_data,
        status=200,
    )

    # Paired account's RetrieveAccountSummary fails with SyracuseApiError (missing session)
    responses.add(
        responses.GET,
        "https://bibliotheques.paris.fr/Portal/Services/UserAccountService.svc/RetrieveAccountSummary?serviceCode=SYRACUSE&userUniqueIdentifier=1234a0141c3a4ab7977b56116d6f17da",
        json={
            "success": False,
            "errors": [{"msg": "Aucune session récupérée pour le login 2227203240XXXX"}],
        },
        status=200,
    )
    # But ListLoans succeeds for that paired account!
    responses.add(
        responses.GET,
        "https://bibliotheques.paris.fr/Portal/Services/UserAccountService.svc/ListLoans?serviceCode=SYRACUSE&userUniqueIdentifier=1234a0141c3a4ab7977b56116d6f17da",
        json=list_loans_data,
        status=200,
    )
    responses.add(
        responses.GET,
        "https://bibliotheques.paris.fr/Portal/Services/UserAccountService.svc/ListBookings?serviceCode=SYRACUSE&userUniqueIdentifier=1234a0141c3a4ab7977b56116d6f17da",
        json=list_bookings_data,
        status=200,
    )

    with ParisBibClient(session_cookies={"_syrSessGuid": "test-token"}) as client:
        # Should not raise exception
        family = client.get_family()

        # Both primary and paired accounts are present
        assert len(family.accounts) == 2
        # Loans were still loaded for the paired account
        assert family.loans.total_count == 6
        # The failed summary warning is captured in failed_accounts
        assert len(family.failed_accounts) == 1
        assert "Aucune session" in family.failed_accounts[0][1]


