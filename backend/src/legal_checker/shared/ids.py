from uuid import NAMESPACE_URL, uuid5

from legal_checker.shared.contracts.common import Context


def stable_id(context: Context, kind: str, key: str) -> str:
    return f"{kind}_{uuid5(NAMESPACE_URL, f'{context.ca_id}/{context.run_id}/{kind}/{key}')}"
