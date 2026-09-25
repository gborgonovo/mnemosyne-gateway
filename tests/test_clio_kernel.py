"""Richieste di Clio al kernel (project_documentation/richieste-da-clio.md).

1. Le cartelle nascoste (.stversions, .trash, .git) non producono mai nodi, né alla
   scansione né agli eventi in tempo reale; spostare una nota nel cestino la cancella.

Run: python3 -m unittest tests/test_clio_kernel.py
"""
import os
import sys
from types import SimpleNamespace

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests.test_robustness import _Base
from workers.file_watcher import _is_indexable_md


def _evento(src, dest=None):
    return SimpleNamespace(is_directory=False, src_path=src, dest_path=dest)


class TestCartelleNascoste(_Base):
    def test_percorso_nascosto_non_indicizzabile(self):
        self.assertTrue(_is_indexable_md(os.path.join(self.kdir, "Lavoro", "nota.md"), self.kdir))
        self.assertFalse(_is_indexable_md(os.path.join(self.kdir, ".stversions", "nota~20260925.md"), self.kdir))
        self.assertFalse(_is_indexable_md(os.path.join(self.kdir, "Lavoro", ".trash", "nota.md"), self.kdir))
        self.assertFalse(_is_indexable_md(os.path.join(self.kdir, ".nota.md"), self.kdir))

    def test_evento_in_stversions_non_crea_nodi(self):
        path = self._write("nota~20260925-120000", {"type": "Node", "scope": "Private"}, "Versione archiviata", ".stversions")
        self.handler.on_created(_evento(path))
        self.assertEqual(self.kuzu.get_all_nodes(), [])

    def test_spostamento_nel_cestino_cancella_il_nodo(self):
        path = self._write("nota", {"type": "Node", "scope": "Private"}, "Contenuto della nota")
        self.handler.on_created(_evento(path))
        self.assertTrue(self.kuzu.get_node("nota"))
        cestino = os.path.join(self.kdir, ".trash")
        os.makedirs(cestino)
        destinazione = os.path.join(cestino, "nota.md")
        os.rename(path, destinazione)
        self.handler.on_moved(_evento(path, destinazione))
        self.assertFalse(self.kuzu.get_node("nota"))

    def test_scansione_ignora_le_cartelle_nascoste(self):
        self._write("vera", {"type": "Node", "scope": "Private"}, "Nota vera")
        self._write("copia", {"type": "Node", "scope": "Private"}, "Copia archiviata", ".stversions")
        self.assertEqual(self.handler._on_disk_ids(), {"vera"})


class TestScritturaDellaMacchina(_Base):
    """2-3. enrichment: skip e importazione fredda (machine_body_hash)."""

    def _con_impronta(self, slug, body, **fm):
        from workers.file_watcher import _hash_body
        return self._write(slug, {"type": "Episodio", "scope": "Private", "created_by": "clio",
                                  "machine_body_hash": _hash_body(body.strip()), **fm}, body, "Clio")

    def test_nasce_freddo_e_non_scalda_i_vicini(self):
        vicino = self._write("Davide", {"type": "Reference", "scope": "Private"}, "Socio in GiodaLab")
        self.handler._sync_file(vicino, is_startup_sync=True)
        prima = self.kuzu.get_node("davide").get("activation_level") or 0.0
        path = self._con_impronta("episodio", "Riunione con [[Davide]] sul progetto.")
        self.handler._sync_file(path, is_startup_sync=False)
        nodo = self.kuzu.get_node("clio__episodio")
        self.assertIsNotNone(nodo)
        self.assertEqual(nodo.get("activation_level") or 0.0, 0.0)
        self.assertEqual(self.kuzu.get_node("davide").get("activation_level") or 0.0, prima)

    def test_quando_giorgio_modifica_il_corpo_si_scalda(self):
        path = self._con_impronta("episodio", "Testo scritto dalla macchina.")
        self.handler._sync_file(path, is_startup_sync=False)
        with open(path, "a", encoding="utf-8") as f:
            f.write("\nNota di Giorgio: me lo ricordo bene.")
        self.handler._sync_file(path, is_startup_sync=False)
        self.assertGreater(self.kuzu.get_node("clio__episodio").get("activation_level") or 0.0, 0.0)

    def test_senza_impronta_il_calore_funziona_come_sempre(self):
        path = self._write("nota", {"type": "Node", "scope": "Private"}, "Nota scritta a mano")
        self.handler._sync_file(path, is_startup_sync=False)
        self.assertGreater(self.kuzu.get_node("nota").get("activation_level") or 0.0, 0.0)

    def test_enrichment_skip(self):
        from unittest import mock
        self.handler.llm = mock.Mock()
        with mock.patch.object(self.handler._enrich_queue, "put") as put:
            lungo = "Un corpo abbastanza lungo da superare la soglia dei centocinquanta caratteri. " * 3
            self.handler._sync_file(self._write("a", {"type": "Node", "scope": "Private", "enrichment": "skip"}, lungo),
                                    is_startup_sync=False)
            self.assertEqual(put.call_count, 0)
            self.handler._sync_file(self._write("b", {"type": "Node", "scope": "Private"}, lungo), is_startup_sync=False)
            self.assertEqual(put.call_count, 1)

    def test_backfill_rispetta_skip_anche_con_force(self):
        from scripts.backfill_enrichment import needs_enrichment
        self.assertFalse(needs_enrichment("x.md", {"enrichment": "skip"}, force=True))


class TestDecadimento(_Base):
    """4. La configurazione integra i tassi del codice; Episodio e Reference hanno il loro."""

    def test_tassi_integrati(self):
        from core.attention import AttentionModel
        am = AttentionModel(self.kuzu, config={"decay_rates": {"Node": 0.01}})
        self.assertEqual(am.decay_rates["Node"], 0.01)
        self.assertEqual(am.decay_rates["Episodio"], 0.0007)
        self.assertEqual(am.decay_rates["Reference"], 0.0007)
