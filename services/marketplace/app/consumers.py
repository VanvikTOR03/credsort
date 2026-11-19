from __future__ import annotations

from credsort_common.background import Consumer

from . import lending


def consumers() -> list[Consumer]:
    return [
        Consumer("marketplace-matcher", ["marketplace.application.published.*"], lending.notify_matches),
        Consumer("marketplace-deletion", ["identity.organization.deletion_requested.*"], lambda s, e: lending.delete_org_data(s, e["credsortorgid"])),
    ]
