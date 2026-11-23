"""Event -> notification rules. Messages contain NO financial values, only plain statements and links (ADR-0023, 08 §7)."""
from __future__ import annotations

from typing import Callable

REASONS = {
    "AUTH_ERROR": "bexio refused the connection. Please reconnect bexio.",
    "PROVIDER_UNAVAILABLE": "bexio is temporarily unavailable. Please try again later.",
    "PROVIDER_ERROR": "The import could not be completed. Please try again.",
    "MAX_ATTEMPTS": "The import kept failing and was stopped. Please try again.",
}


def _validation(code: str) -> str:
    return "Your accounting data did not pass our consistency checks (" + code.removeprefix("VALIDATION_").replace("_", " ").lower() + ")."


def note(org, kind, title, body, link=None, ref=None):
    return {"org": org, "kind": kind, "title": title, "body": body, "link": link, "ref": ref}


# event name (without credsort. prefix and .v1) -> function(data) -> list of notes
RULES: dict[str, Callable[[dict], list[dict]]] = {
    "accounting.import.completed": lambda d: [note(d["org_id"], "import.completed", "Accounting data imported", "We are building your financial profile now.", "/sme/data")],
    "accounting.import.failed": lambda d: [note(d["org_id"], "import.failed", "Import did not finish",
                                                _validation(d["reason_code"]) if d["reason_code"].startswith("VALIDATION_") else REASONS.get(d["reason_code"], "The import failed. Please try again."), "/sme/data")],
    "intelligence.assessment.created": lambda d: [note(d["org_id"], "assessment.created", "Your financial profile is ready", "A new preliminary assessment is available.", "/sme/profile")],
    "intelligence.assessment.failed": lambda d: [note(d["org_id"], "assessment.failed", "We could not build your profile", "Your previous profile stays available. Please check your data connection.", "/sme/data")],
    "marketplace.application.matched": lambda d: [note(o, "application.matched", "New application matches your criteria", "Open your matches to review it.", "/lender/matches", d["application_id"]) for o in d["lender_org_ids"]],
    "marketplace.offer.submitted": lambda d: [note(d["sme_org_id"], "offer.submitted", "You received a new offer", "Compare it with your other offers.", f"/sme/applications/{d['application_id']}", d["application_id"])],
    "marketplace.offer.withdrawn": lambda d: [note(d["sme_org_id"], "offer.withdrawn", "A lender withdrew an offer", "The offer is no longer available.", f"/sme/applications/{d['application_id']}", d["application_id"])],
    "marketplace.offer.selected": lambda d: [note(d["lender_org_id"], "offer.selected", "Your offer was selected", "Complete the loan with the borrower, then confirm the payout here.", "/lender/offers"),
                                             *[note(o, "offer.rejected", "Another offer was selected", "Thank you for bidding.", "/lender/offers") for o in d["other_lender_org_ids"]]],
    "marketplace.loan.funded": lambda d: [note(d["sme_org_id"], "loan.funded", "Payout confirmed by your lender", "If you did not receive the money, you can dispute this within 14 days.", f"/sme/applications/{d['application_id']}", d["application_id"])],
    "marketplace.loan.disputed": lambda d: [note(d["lender_org_id"], "loan.disputed", "The borrower disputed the payout", "CredSort has put the fee on hold while this is clarified.", "/lender/offers")],
    "marketplace.loan.cancelled": lambda d: [note(d["sme_org_id"], "loan.cancelled", "Your loan was cancelled", "The lender cancelled before payout. No fee is due.", f"/sme/applications/{d['application_id']}", d["application_id"])],
    "marketplace.access.requested": lambda d: [note(d["sme_org_id"], "access.requested", "A lender asks for more information", "Review the request and decide what to share.", "/sme/requests", d["application_id"])],
    "marketplace.access.decided": lambda d: [note(d["lender_org_id"], "access.decided", "Your information request was " + d["decision"].lower(), "Open the application to see what is shared.", "/lender/matches", d["application_id"])],
    "billing.unlock.paid": lambda d: [note(d["org_id"], "offers.unlocked", "Offers unlocked", "You can now see who made each offer. Our partner is checking your identity.", f"/sme/loans/{d['application_id']}", d["application_id"])],
    "identity.organization.kyc_completed": lambda d: [note(d["org_id"], "kyc.completed", "Identity check " + d["kyc_status"].lower(), "Your company identity check is finished.", "/sme")],
    "billing.charge.status_changed": lambda d: [note(d["org_id"], "charge.changed", "A fee changed status", "See your fees for details.", "/settings/fees")],
    "identity.organization.verification_changed": lambda d: [note(d["org_id"], "verification.changed", "Verification status updated", "Your organization is now " + d["kyb_status"].lower() + ".", "/settings")],
    "identity.delegation.granted": lambda d: [note(d["fiduciary_org_id"], "delegation.granted", "A client shared access with you", "You can now prepare applications on their behalf.", "/fiduciary/clients")],
    "identity.delegation.revoked": lambda d: [note(d["fiduciary_org_id"], "delegation.revoked", "A client ended your access", "You can no longer act for this client.", "/fiduciary/clients")],
}

# events after which lender-facing notifications about an application must disappear (consent revocation across services)
WITHDRAW_FOR_LENDERS = {"marketplace.disclosure.revoked", "marketplace.application.withdrawn"}
