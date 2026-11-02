"""Offline semantic providers must not need an optional HTTP/API transport package."""

import subprocess
import sys
import textwrap


def test_transport_free_contracts_import_when_httpx_and_openai_are_unavailable():
    script = textwrap.dedent(
        """
        import importlib.abc
        import sys

        class BlockOptionalTransports(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname.split('.')[0] in {'httpx', 'openai'}:
                    raise ModuleNotFoundError('Optional transport deliberately unavailable')
                return None

        sys.meta_path.insert(0, BlockOptionalTransports())
        from legal_checker.shared.llm.types import LlmClientError, LlmResponse
        result = LlmResponse(content='{}', model_version='offline-test')
        assert result.model_version == 'offline-test'
        assert str(LlmClientError('NO_CLIENT')) == 'LLM request failed: NO_CLIENT'
        assert 'httpx' not in sys.modules and 'openai' not in sys.modules
        """
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
