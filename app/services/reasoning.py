"""Compatibility facade; business implementation lives in modules/compliance_reasoning."""

from app.core.ids import stable_id as stable_id
from app.core.validation import validate_request as validate_request
from app.modules.compliance_reasoning.numeric_rules import numeric_finding as numeric_finding
from app.modules.compliance_reasoning.service import reason as reason
