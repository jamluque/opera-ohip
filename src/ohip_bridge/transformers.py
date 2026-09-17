from __future__ import annotations

from typing import Any


class ReservationTransformer:
    def transform(
        self, payload: dict[str, Any], *, hotel_id: str, reservation_id: str
    ) -> dict[str, Any]:
        reservation = payload.get("reservation") or payload.get("reservations") or payload
        if isinstance(reservation, list):
            reservation = reservation[0] if reservation else {}
        return {
            "hotel_id": hotel_id,
            "reservation_id": str(
                reservation.get("reservationId")
                or reservation.get("reservationIdList", [{}])[0].get("id")
                if isinstance(reservation.get("reservationIdList"), list)
                else reservation_id
            ),
            "confirmation_no": reservation.get("confirmationNo")
            or reservation.get("confirmationNumber"),
            "arrival_date": reservation.get("arrivalDate"),
            "departure_date": reservation.get("departureDate"),
            "reservation_status": reservation.get("reservationStatus") or reservation.get("status"),
            "source_updated_at": reservation.get("lastModifyDateTime")
            or reservation.get("updateDate"),
        }


class ProfileTransformer:
    def transform(self, payload: dict[str, Any], *, profile_id: str) -> dict[str, Any]:
        profile = payload.get("profile") or payload.get("profiles") or payload
        if isinstance(profile, list):
            profile = profile[0] if profile else {}
        name = profile.get("customer", {}).get("personName", [{}])
        primary_name = name[0] if isinstance(name, list) and name else {}
        return {
            "profile_id": str(profile.get("profileId") or profile.get("id") or profile_id),
            "profile_type": profile.get("profileType") or profile.get("type"),
            "first_name": primary_name.get("givenName") or profile.get("firstName"),
            "last_name": primary_name.get("surname") or profile.get("lastName"),
            "email": self._email(profile),
            "source_updated_at": profile.get("lastModifyDateTime") or profile.get("updateDate"),
        }

    def _email(self, profile: dict[str, Any]) -> str | None:
        emails = profile.get("emails") or profile.get("emailInfo") or []
        if isinstance(emails, list) and emails:
            item = emails[0]
            if isinstance(item, dict):
                return item.get("email") or item.get("emailAddress")
        return profile.get("email")


class FolioTransformer:
    def transform_folios(
        self, payload: dict[str, Any], *, hotel_id: str, reservation_id: str
    ) -> list[dict[str, Any]]:
        folios = payload.get("folios") or payload.get("folio") or payload.get("items") or []
        if isinstance(folios, dict):
            folios = [folios]
        return [
            {
                "hotel_id": hotel_id,
                "reservation_id": reservation_id,
                "folio_id": str(folio.get("folioId") or folio.get("id") or index),
                "folio_no": folio.get("folioNo") or folio.get("folioNumber"),
                "balance_amount": folio.get("balance") or folio.get("balanceAmount"),
                "currency_code": folio.get("currencyCode") or folio.get("currency"),
                "source_updated_at": folio.get("lastModifyDateTime") or folio.get("updateDate"),
            }
            for index, folio in enumerate(folios, start=1)
            if isinstance(folio, dict)
        ]

    def transform_transaction(
        self, payload: dict[str, Any], *, hotel_id: str, transaction_no: str
    ) -> dict[str, Any]:
        transaction = payload.get("transaction") or payload.get("transactionDetails") or payload
        if isinstance(transaction, list):
            transaction = transaction[0] if transaction else {}
        return {
            "hotel_id": hotel_id,
            "transaction_no": str(transaction.get("transactionNo") or transaction_no),
            "reservation_id": transaction.get("reservationId") or transaction.get("resvNameId"),
            "folio_id": transaction.get("folioId"),
            "amount": transaction.get("amount") or transaction.get("grossAmount"),
            "currency_code": transaction.get("currencyCode") or transaction.get("currency"),
            "transaction_code": transaction.get("transactionCode") or transaction.get("trxCode"),
            "source_updated_at": transaction.get("lastModifyDateTime")
            or transaction.get("updateDate"),
        }
