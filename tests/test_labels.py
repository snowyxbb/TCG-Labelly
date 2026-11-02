import pytest
from jinja2.exceptions import SecurityError

from app.labels import _env


def test_sandbox_blocks_class_escape():
    """User-supplied templates must not reach Python internals (SSTI)."""
    with pytest.raises(SecurityError):
        _env.from_string("{{ ''.__class__ }}").render()


def test_sandbox_allows_normal_templates():
    assert _env.from_string("{{ 1 + 1 }}").render() == "2"
