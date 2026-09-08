from __future__ import annotations

import pytest

from backend import credentials


@pytest.fixture(autouse=True)
def _clear_user_id_cache():
    credentials.clear_user_id_cache()
    yield
    credentials.clear_user_id_cache()
