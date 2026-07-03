"""Fase 3a: GET /briefing/initiatives replaces the broken briefing_worker.

Two layers:
  - TestInitiativeEngineOnGraph: real InitiativeEngine against an isolated
    KuzuDB; a hot node linked to a cold neighbor must yield an initiative,
    and scope filtering must hold.
  - TestInitiativesEndpoint: gateway imported with the heavy backend mocked
    out; the route function returns the declared shape and respects the
    engine output.

Run: python3 -m unittest tests/test_initiatives.py
"""
import os
import sys
import shutil
import tempfile
import unittest
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.kuzu_manager import KuzuManager
from butler.initiative import InitiativeEngine


class TestInitiativeEngineOnGraph(unittest.TestCase):
    def setUp(self):
        self.dbroot = tempfile.mkdtemp()
        self.kuzu = KuzuManager(db_path=os.path.join(self.dbroot, "kuzu"))

    def tearDown(self):
        self.kuzu.close()
        shutil.rmtree(self.dbroot, ignore_errors=True)

    def test_hot_node_with_cold_neighbor_yields_initiative(self):
        self.kuzu.add_node("progetto_caldo", initial_activation=0.9, scope="Private")
        self.kuzu.add_node("tema_freddo", initial_activation=0.1, scope="Private")
        self.kuzu.add_edge("progetto_caldo", "tema_freddo", "RELATED_TO")
        engine = InitiativeEngine(self.kuzu, config={})
        items = engine.generate_initiatives()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["source"], "progetto_caldo")
        self.assertEqual(items[0]["target"], "tema_freddo")
        self.assertIn("message", items[0])
        self.assertIn("reason", items[0])

    def test_warm_neighbor_yields_nothing(self):
        self.kuzu.add_node("progetto_caldo", initial_activation=0.9, scope="Private")
        self.kuzu.add_node("tema_attivo", initial_activation=0.8, scope="Private")
        self.kuzu.add_edge("progetto_caldo", "tema_attivo", "RELATED_TO")
        engine = InitiativeEngine(self.kuzu, config={})
        self.assertEqual(engine.generate_initiatives(), [])

    def test_scope_filter_hides_private_pairs_from_public_key(self):
        self.kuzu.add_node("caldo_privato", initial_activation=0.9, scope="Private")
        self.kuzu.add_node("freddo_privato", initial_activation=0.1, scope="Private")
        self.kuzu.add_edge("caldo_privato", "freddo_privato", "RELATED_TO")
        engine = InitiativeEngine(self.kuzu, config={})
        self.assertEqual(engine.generate_initiatives(scopes=["Public"]), [],
                         "a Public-scoped request must not see Private initiatives")
        self.assertEqual(len(engine.generate_initiatives(scopes=["Private"])), 1)


class TestInitiativesEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._patchers = [
            mock.patch("core.kuzu_manager.KuzuManager"),
            mock.patch("core.vector_store.VectorStore"),
            mock.patch("core.attention.AttentionModel"),
            mock.patch("workers.gardener.Gardener"),
            mock.patch("workers.file_watcher.WikiSyncHandler"),
            mock.patch("watchdog.observers.Observer"),
            mock.patch("gateway.mcp_app.create_mcp_server"),
            mock.patch("butler.llm.get_llm_provider"),
        ]
        for p in cls._patchers:
            p.start()
        import gateway.http_server as hs
        cls.hs = hs

    @classmethod
    def tearDownClass(cls):
        for p in cls._patchers:
            p.stop()

    def test_endpoint_shape_and_passthrough(self):
        canned = [{"source": "a", "target": "b", "message": "m", "reason": "r"}]
        with mock.patch.object(self.hs, "InitiativeEngine") as Eng:
            Eng.return_value.generate_initiatives.return_value = canned
            resp = self.hs.get_initiatives(api_auth={"scopes": ["*"]})
        self.assertEqual(resp["count"], 1)
        self.assertEqual(resp["initiatives"], canned)
        self.assertIn("timestamp", resp)
        # full-scope key -> engine called without scope or territory filter
        Eng.return_value.generate_initiatives.assert_called_once_with(scopes=None, read_grants=None)

    def test_endpoint_scopes_are_intersected(self):
        with mock.patch.object(self.hs, "InitiativeEngine") as Eng:
            Eng.return_value.generate_initiatives.return_value = []
            self.hs.get_initiatives(scopes="Private,Public", api_auth={"scopes": ["Public"]})
        called_scopes = Eng.return_value.generate_initiatives.call_args.kwargs["scopes"]
        self.assertEqual(called_scopes, ["Public"],
                         "the key's allowed scopes must cap the requested ones")


if __name__ == "__main__":
    unittest.main(verbosity=2)
