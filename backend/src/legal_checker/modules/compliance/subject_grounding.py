"""Conservative role checks supplement quote matching; they never prove compliance."""

import re

from legal_checker.modules.retrieval.fact_evidence import fold


def subject_supported(criterion_id, text):
    if criterion_id != "TC_PV_HYC010_01":
        return True
    # A dispute caused by the buyer is not the seller's sale through an intermediary.
    return bool(
        re.search(
            r"moi gioi|dai ly|san giao dich|trung gian|"
            r"ban (?:can ho )?(?:thong )?qua ben thu ba|uy quyen ban",
            fold(text),
        )
    )
