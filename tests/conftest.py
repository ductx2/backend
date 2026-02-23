import sys
from unittest.mock import MagicMock

_fake_db = MagicMock()
_fake_db.get_database_sync = MagicMock()
_fake_db.get_database = MagicMock()
_fake_db.SupabaseConnection = MagicMock

if "app.core.database" not in sys.modules:
    sys.modules["app.core.database"] = _fake_db
