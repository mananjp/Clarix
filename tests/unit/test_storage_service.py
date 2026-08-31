"""
Unit tests for Storage Abstraction (Phase 7).
"""

import os
import sys
import tempfile


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.services.storage import LocalStorageBackend, get_storage_backend


class TestLocalStorageBackend:
    def test_save_load_exists_delete(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = LocalStorageBackend(base_dir=tmpdir)
            data = b"Hello, Clarix ESG storage!"
            key = "test_doc.txt"

            # Save
            path = backend.save(data, key)
            assert os.path.exists(path)

            # Exists
            assert backend.exists(key) is True

            # Load
            loaded = backend.load(key)
            assert loaded == data

            # Delete
            backend.delete(key)
            assert backend.exists(key) is False

    def test_get_storage_backend_singleton(self):
        backend1 = get_storage_backend()
        backend2 = get_storage_backend()
        assert backend1 is backend2
