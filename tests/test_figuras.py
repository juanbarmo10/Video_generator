"""Tests de `herramientas/19_figuras.py`.

Por qué estos y no otros: las figuras tienen el mismo tipo de fallo que el
informe —se dibujan igual de bien digan lo que digan— con un agravante, que es
que una columna que desaparece **no deja hueco visible**: el panel sale con
menos puntos y nadie lo nota.

Pasó de verdad el 16 sep: `ultima_foto()` se quedaba con la fila más reciente
entera, así que `se_quedaron_pct` —que solo existe en el snapshot del 15 ago,
porque la da el export de YouTube y no la API— desaparecía al aplanar, y la
métrica de la que trata P-20 salía con n=0 en todas las figuras sin avisar.

⚠️ Este módulo es el único del repositorio que necesita matplotlib, así que el
archivo entero se salta si no está: el resto de la suite sigue sin dependencias.

Se corren con:  python -m unittest discover tests
"""

import importlib.util
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

try:
    import matplotlib  # noqa: F401
    HAY_MATPLOTLIB = True
except ImportError:
    HAY_MATPLOTLIB = False


def cargar():
    ruta = RAIZ / "herramientas" / "19_figuras.py"
    spec = importlib.util.spec_from_file_location(ruta.stem, ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def foto(id_="v1", fecha="2026-08-15", plataforma="youtube", **campos):
    base = {"plataforma": plataforma, "id_plataforma": id_, "fecha_snapshot": fecha}
    base.update(campos)
    return base


@unittest.skipUnless(HAY_MATPLOTLIB, "19_figuras.py necesita matplotlib")
class AplanarSinPerderColumnas(unittest.TestCase):
    """El fallo del 16 sep. Una métrica que solo se midió una vez desaparecía al
    quedarse con la última fila entera, y no dejaba hueco visible."""

    def setUp(self):
        self.fig = cargar()

    def test_arrastra_una_tasa_medida_solo_en_una_foto_vieja(self):
        filas = [foto(fecha="2026-08-15", vistas="100", se_quedaron_pct="48"),
                 foto(fecha="2026-09-15", vistas="500", se_quedaron_pct="")]
        (fila,) = self.fig.ultima_foto(filas)
        self.assertEqual(fila["se_quedaron_pct"], "48",
                         "una tasa no crece con la edad: sigue valiendo")
        self.assertEqual(fila["vistas"], "500")

    def test_NO_arrastra_un_acumulado(self):
        """El punto entero de la corrección. Pegar un recuento viejo a la fecha
        de la foto nueva afirmaría que las vistas de agosto son las de hoy, que
        es justo lo que `TIPO_METRICA` existe para impedir."""
        filas = [foto(fecha="2026-08-15", vistas="100", alcance="80"),
                 foto(fecha="2026-09-15", vistas="500", alcance="")]
        (fila,) = self.fig.ultima_foto(filas)
        self.assertEqual(fila["alcance"], "",
                         "`alcance` es acumulativa: no se arrastra")

    def test_la_fecha_es_siempre_la_de_la_foto_mas_reciente(self):
        """Es la que fija la edad del video; heredarla de la vieja movería todas
        las comparaciones por edad."""
        filas = [foto(fecha="2026-08-15", se_quedaron_pct="48"),
                 foto(fecha="2026-09-15", vistas="500")]
        (fila,) = self.fig.ultima_foto(filas)
        self.assertEqual(fila["fecha_snapshot"], "2026-09-15")

    def test_una_fila_por_video_y_no_una_por_foto(self):
        """Sin aplanar, un video medido seis semanas pesa seis veces en cada
        mediana solo por llevar más tiempo."""
        filas = [foto(id_="v1", fecha="2026-08-15"), foto(id_="v1", fecha="2026-09-15"),
                 foto(id_="v2", fecha="2026-09-15")]
        self.assertEqual(len(self.fig.ultima_foto(filas)), 2)

    def test_no_mezcla_videos_de_plataformas_distintas(self):
        """Los id son nativos de cada red y pueden repetirse entre ellas."""
        filas = [foto(id_="x", plataforma="youtube", se_quedaron_pct="48"),
                 foto(id_="x", plataforma="tiktok")]
        aplanadas = self.fig.ultima_foto(filas)
        self.assertEqual(len(aplanadas), 2)
        tiktok = next(f for f in aplanadas if f["plataforma"] == "tiktok")
        self.assertFalse(tiktok.get("se_quedaron_pct"))

    def test_descarta_las_filas_sin_id(self):
        self.assertEqual(self.fig.ultima_foto([foto(id_="")]), [])
