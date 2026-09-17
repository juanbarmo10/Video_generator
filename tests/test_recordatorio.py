"""Tests de `herramientas/12_recordatorio.py`.

Por qué estos y no otros: este archivo es lo único que le dice al dueño qué
hacer, y sus fallos son todos del tipo que no se nota. Un aviso que no salta se
parece mucho a una semana tranquila, y uno que salta siempre se aprende a
ignorar — con lo que tampoco se lee el día que trae algo de verdad.

Los dos casos reales del 16 sep están congelados aquí:
  · `guiones_sin_revisar()` prometía "y siguen sin publicar" y no lo comprobaba:
    listaba 12 guiones de agosto ya publicados, sobre los que no se puede hacer
    nada. De 12 avisos, 11 eran ruido.
  · `resumen_metricas()` importaba el paso 11 sin llamar a `sincronizar_lotes()`,
    así que comparaba con el `lote_nuevo` por defecto del archivo (congelado en
    v3) mientras el paso 10 iba por v5: números de una tanda bajo el título de
    otra.

Se corren con:  python -m unittest discover tests
"""

import csv
import importlib.util
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def cargar():
    ruta = RAIZ / "herramientas" / "12_recordatorio.py"
    spec = importlib.util.spec_from_file_location(ruta.stem, ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def escribir_csv(ruta: Path, columnas: list[str], filas: list[dict]) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columnas)
        w.writeheader()
        w.writerows(filas)


class EnTmp(unittest.TestCase):
    """⚠️ Apunta el CONFIG a un temporal. Sin esto leería el repositorio de
    verdad y los tests cambiarían de veredicto según lo publicado esa semana."""

    def setUp(self):
        self.rec = cargar()
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self._cfg = dict(self.rec.CONFIG)
        self.rec.CONFIG.update({
            "calendario": str(self.tmp / "calendario.csv"),
            "publicado": str(self.tmp / "publicado.csv"),
            "metricas": str(self.tmp / "metricas.csv"),
            "proyectos": str(self.tmp / "proyectos"),
        })

    def tearDown(self):
        self.rec.CONFIG.clear()
        self.rec.CONFIG.update(self._cfg)
        self._tmp.cleanup()

    def calendario(self, filas):
        escribir_csv(Path(self.rec.CONFIG["calendario"]),
                     ["fecha", "proyecto"], filas)

    def publicado(self, filas):
        escribir_csv(Path(self.rec.CONFIG["publicado"]),
                     ["fecha", "proyecto", "red", "id_publicacion"], filas)

    def metricas(self, filas):
        escribir_csv(Path(self.rec.CONFIG["metricas"]),
                     ["PROYECTO", "fecha_snapshot"], filas)

    def veredicto(self, proyecto, nota, aprobado):
        d = Path(self.rec.CONFIG["proyectos"]) / proyecto
        d.mkdir(parents=True, exist_ok=True)
        (d / "calidad_guion.json").write_text(
            json.dumps({"nota": nota, "aprobado": aprobado}), encoding="utf-8")


class PendientesDeSubir(EnTmp):
    def test_calla_mientras_el_atraso_lo_explique_el_ritmo(self):
        """El calendario reparte uno al día y se suben 5-6 por semana, así que a
        mitad de semana sobra siempre algún vencido. Avisar de eso cada domingo
        es enseñar a ignorar el aviso."""
        self.calendario([{"fecha": "2026-09-16", "proyecto": "H1"},
                         {"fecha": "2026-09-17", "proyecto": "H2"}])
        self.publicado([])
        self.assertIsNone(self.rec.pendientes_de_subir(date(2026, 9, 18)))

    def test_avisa_cuando_el_atraso_ya_no_es_el_ritmo(self):
        self.calendario([{"fecha": f"2026-09-{d:02d}", "proyecto": f"H{d}"}
                         for d in range(10, 20)])
        self.publicado([])
        aviso = self.rec.pendientes_de_subir(date(2026, 9, 25))
        self.assertIsNotNone(aviso)
        self.assertIn("--marcar", aviso["accion"],
                      "el consejo tiene que decir cómo anotarlo, no mandar a un log")

    def test_lo_anotado_deja_de_contar(self):
        """Es lo que hace `--marcar`: sin esto el registro no crece y el aviso
        repite para siempre lo que ya subiste."""
        filas = [{"fecha": f"2026-09-{d:02d}", "proyecto": f"H{d}"}
                 for d in range(10, 20)]
        self.calendario(filas)
        self.publicado([{"fecha": "2026-09-20", "proyecto": f"H{d}", "red": red,
                         "id_publicacion": ""}
                        for d in range(10, 20)
                        for red in self.rec.CONFIG["redes_a_mano"]])
        self.assertIsNone(self.rec.pendientes_de_subir(date(2026, 9, 25)))


class TocaMedir(EnTmp):
    def test_avisa_de_lo_publicado_despues_de_la_ultima_foto(self):
        self.publicado([{"fecha": "2026-09-16", "proyecto": "H1",
                         "red": "instagram", "id_publicacion": ""}])
        self.metricas([{"PROYECTO": "H0", "fecha_snapshot": "2026-09-15"}])
        aviso = self.rec.toca_medir(date(2026, 9, 25))
        self.assertIsNotNone(aviso)
        self.assertIn("YouTube", aviso["accion"],
                      "el export de YouTube es el único que trae se_quedaron_pct")

    def test_calla_si_el_video_aun_no_maduro(self):
        """El reel de Instagram se congela hacia el día 5: medir antes da un
        número a medias."""
        self.publicado([{"fecha": "2026-09-16", "proyecto": "H1",
                         "red": "instagram", "id_publicacion": ""}])
        self.metricas([{"PROYECTO": "H0", "fecha_snapshot": "2026-09-15"}])
        self.assertIsNone(self.rec.toca_medir(date(2026, 9, 18)))

    def test_calla_si_ya_se_midio_despues(self):
        self.publicado([{"fecha": "2026-09-16", "proyecto": "H1",
                         "red": "instagram", "id_publicacion": ""}])
        self.metricas([{"PROYECTO": "H1", "fecha_snapshot": "2026-09-24"}])
        self.assertIsNone(self.rec.toca_medir(date(2026, 9, 25)))


class GuionesSinRevisar(EnTmp):
    """El aviso prometía 'y siguen sin publicar' y no lo comprobaba."""

    def setUp(self):
        super().setUp()
        self.calendario([]); self.publicado([]); self.metricas([])

    def test_no_avisa_de_uno_que_ya_salio(self):
        self.veredicto("H1", 4, False)
        self.publicado([{"fecha": "2026-09-01", "proyecto": "H1",
                         "red": "instagram", "id_publicacion": "x"}])
        self.assertIsNone(self.rec.guiones_sin_revisar())

    def test_tampoco_si_solo_tiene_metricas(self):
        """Los de antes de que existiera el registro no están en `publicado.csv`,
        pero tener métricas ya prueba que se publicaron."""
        self.veredicto("H1", 4, False)
        self.metricas([{"PROYECTO": "H1", "fecha_snapshot": "2026-08-15"}])
        self.assertIsNone(self.rec.guiones_sin_revisar())

    def test_si_avisa_del_que_nunca_salio(self):
        self.veredicto("H1", 4, False)
        aviso = self.rec.guiones_sin_revisar()
        self.assertIsNotNone(aviso)
        self.assertIn("H1", aviso["texto"])


class UmbralesEnSintonia(unittest.TestCase):
    """⚠️ La nota del recordatorio y la de la puerta son la misma escala. Con la
    del recordatorio más alta, marcaba 'por revisar' justo lo que la puerta
    aprueba, y como la mitad del lote sale con 6 el aviso llegaba con media
    tanda dentro."""

    def test_la_nota_minima_es_la_misma_que_la_del_paso_01(self):
        rec = cargar()
        ruta = RAIZ / "pipeline" / "01_script_generator.py"
        spec = importlib.util.spec_from_file_location("paso01_cfg", ruta)
        texto = ruta.read_text(encoding="utf-8")
        import re
        m = re.search(r'"nota_minima":\s*(\d+)', texto)
        self.assertIsNotNone(m, "no encontré nota_minima en el paso 01")
        self.assertEqual(rec.CONFIG["nota_minima"], int(m.group(1)))
