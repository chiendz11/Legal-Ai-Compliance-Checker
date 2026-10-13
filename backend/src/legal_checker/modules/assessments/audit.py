"""Stable hashes of run inputs/outputs used by the transactional audit record."""

import hashlib
import json


def digest(model):
    return hashlib.sha256(
        json.dumps(model.model_dump(mode="json"), sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
