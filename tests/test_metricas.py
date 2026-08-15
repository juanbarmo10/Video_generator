"""Tests de la consolidación de métricas (`herramientas/10_metricas.py`).

Todo lo de aquí es puro Python: nada de red, nada de exports reales. Se prueban
las piezas donde un fallo **no rompe la corrida** sino que escribe un número
equivocado en `metricas.csv`, que es el archivo que sí está en git y del que
sale el informe.

Se corren con:  python -m unittest discover tests
"""

import csv
import tempfile
import unittest
from pathlib import Path

from test_reporte import RAIZ, cargar

met = cargar("10_metricas.py")


def m(plataforma="youtube", id_="v1", fecha="2026-08-15", lote="baseline", **campos):
    base = {"plataforma": plataforma, "id_plataforma": id_,
            "fecha_snapshot": fecha, "lote": lote}
    base.update(campos)
    return base


class LotePegajoso(unittest.TestCase):
    """El bug del 15 ago. `lote` se calcula desde `temas.csv`, y `temas.csv`
    cambia cada semana: sin esto, cargar la tanda siguiente degradaba la anterior
    a `baseline` en silencio. El informe pasó de comparar n=6 vs 34 a n=1 vs 44 y
    `se_quedaron_pct` de −16 % a +33 %, afirmando lo contrario de lo real."""

    def test_no_degrada_un_lote_con_nombre(self):
        previas = [m(id_="v1", lote="v2-mas-cortes", vistas="100")]
        nuevas = [m(id_="v1", lote="baseline", vistas="150")]
        filas, _, _ = met.fusionar(previas, nuevas)
        self.assertEqual(filas[0]["lote"], "v2-mas-cortes")
        self.assertEqual(filas[0]["vistas"], "150", "el resto sí debe actualizarse")

    def test_si_promueve_desde_baseline(self):
        """La asimetría: un video que entró sin emparejar y luego reconoce su
        PROYECTO tiene que poder subir al lote que de verdad le toca."""
        previas = [m(id_="v1", lote="baseline")]
        nuevas = [m(id_="v1", lote="v3-guion-y-dispersion")]
        filas, _, _ = met.fusionar(previas, nuevas)
        self.assertEqual(filas[0]["lote"], "v3-guion-y-dispersion")

    def test_el_lote_se_hereda_entre_fotos_de_distinto_dia(self):
        """La clave de fusión lleva `fecha_snapshot`, pero el lote es del VIDEO,
        no de la foto. Un snapshot nuevo no puede estrenar lote."""
        previas = [m(id_="v1", fecha="2026-08-01", lote="v2-mas-cortes")]
        nuevas = [m(id_="v1", fecha="2026-08-15", lote="baseline")]
        filas, nuevas_n, _ = met.fusionar(previas, nuevas)
        self.assertEqual(nuevas_n, 1, "es una foto nueva, no una actualización")
        self.assertTrue(all(f["lote"] == "v2-mas-cortes" for f in filas))

    def test_no_confunde_videos_de_plataformas_distintas(self):
        """Los id son nativos de cada red y pueden repetirse entre ellas."""
        previas = [m("youtube", "x", lote="v2-mas-cortes")]
        nuevas = [m("tiktok", "x", lote="baseline")]
        filas, _, _ = met.fusionar(previas, nuevas)
        lotes = {(f["plataforma"], f["lote"]) for f in filas}
        self.assertEqual(lotes, {("youtube", "v2-mas-cortes"), ("tiktok", "baseline")})

    def test_lotes_ya_asignados_ignora_baseline(self):
        previas = [m(id_="a", lote="baseline"), m(id_="b", lote="v2-mas-cortes"),
                   m(id_="c", lote="")]
        asignados = met.lotes_ya_asignados(previas)
        self.assertEqual(asignados, {("youtube", "b"): "v2-mas-cortes"})


class Fusion(unittest.TestCase):
    def test_nunca_pisa_un_valor_lleno_con_uno_vacio(self):
        """Un export que no trae una columna no puede borrar lo que ya se sabía."""
        previas = [m(id_="v1", guardados="42")]
        nuevas = [m(id_="v1", guardados="", vistas="10")]
        filas, _, _ = met.fusionar(previas, nuevas)
        self.assertEqual(filas[0]["guardados"], "42")
        self.assertEqual(filas[0]["vistas"], "10")

    def test_conserva_las_fotos_de_otros_dias(self):
        """Los deltas de 24 h y 7 d salen de restar dos fotos: si la corrida de
        hoy pisara la de la semana pasada, no habría nada que restar."""
        previas = [m(id_="v1", fecha="2026-08-01", vistas="100")]
        nuevas = [m(id_="v1", fecha="2026-08-15", vistas="500")]
        filas, _, _ = met.fusionar(previas, nuevas)
        self.assertEqual(len(filas), 2)
        self.assertEqual({f["vistas"] for f in filas}, {"100", "500"})


class IndiceDeProyectos(unittest.TestCase):
    """P-14: `proyectos/T1/` guarda los 27 respaldos de la tanda anterior un
    nivel más abajo, y con un glob de un solo nivel eran invisibles — 78 de 147
    filas de métricas se quedaban sin `PROYECTO`, o sea sin lote con el que
    compararse."""

    def preparar(self, rutas):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        raiz = Path(tmp.name)
        for r in rutas:
            posts = raiz / r / "social_posts"
            posts.mkdir(parents=True)
            (posts / "descripcion.txt").write_text(
                f"Texto de {Path(r).name} con palabras suficientes para el indice",
                encoding="utf-8")
        return {"dir_proyectos": str(raiz)}

    def test_ve_los_dos_niveles(self):
        cfg = self.preparar(["Historia01", "T1/Messi01", "T1/Tupac01"])
        self.assertEqual(set(met.indice_proyectos(cfg)),
                         {"Historia01", "Messi01", "Tupac01"})

    def test_no_baja_a_un_tercer_nivel(self):
        """Acotado a dos a propósito: un respaldo dentro de otro respaldo no es
        un proyecto, y con `rglob` entraría como si lo fuera."""
        cfg = self.preparar(["Historia01", "T1/X/Y"])
        self.assertEqual(set(met.indice_proyectos(cfg)), {"Historia01"})

    def test_una_carpeta_sin_textos_no_entra(self):
        cfg = self.preparar(["Historia01"])
        (Path(cfg["dir_proyectos"]) / "Vacio" / "social_posts").mkdir(parents=True)
        self.assertEqual(set(met.indice_proyectos(cfg)), {"Historia01"})


class NumerosQueMintieron(unittest.TestCase):
    """Cada uno de estos salió de una lectura equivocada de un export real."""

    def test_facebook_decimal_no_se_lee_como_separador_de_miles(self):
        """Facebook exporta los segundos medios como '9.378'. La regla genérica
        de '3 dígitos detrás = miles' lo leía como 9378 y daba retenciones del
        17.000 %. El tipo se decide por campo, no por heurística."""
        self.assertEqual(met.limpiar_numero("9.378", decimal=True), "9.378")
        self.assertEqual(met.limpiar_numero("1.284", decimal=False), "1284")
        self.assertIn("duracion_media_s", met.CAMPOS_DECIMALES)

    def test_porcentaje_tecleado_como_fraccion_se_convierte_y_avisa(self):
        """Mezclar 0.21 y 21 en la misma columna la deja inservible."""
        self.assertEqual(met.normalizar_porcentaje("0.21"), ("21", True))
        self.assertEqual(met.normalizar_porcentaje("21"), ("21", False))

    def test_el_100_por_cien_no_se_toma_por_una_fraccion(self):
        """El borde: 1 es ambiguo, pero 100 no puede convertirse en 10.000."""
        self.assertEqual(met.normalizar_porcentaje("100")[1], False)

    def test_retencion_no_se_recalcula_si_ya_viene_del_export(self):
        """YouTube la da y puede pasar del 100 % por los bucles de Shorts.
        Recalcularla la aplastaría a un número distinto y peor."""
        fila = {"retencion_pct": "115.7", "duracion_media_s": "44", "duracion_s": "38"}
        met.calcular_retencion(fila)
        self.assertEqual(fila["retencion_pct"], "115.7")

    def test_retencion_se_deriva_de_los_segundos_tecleados(self):
        fila = {"retencion_pct": "", "duracion_media_s": "19", "duracion_s": "38"}
        met.calcular_retencion(fila)
        self.assertEqual(fila["retencion_pct"], "50.0")

    def test_duracion_cero_no_revienta(self):
        fila = {"retencion_pct": "", "duracion_media_s": "19", "duracion_s": "0"}
        met.calcular_retencion(fila)
        self.assertEqual(fila["retencion_pct"], "")


class TikTokSinEscapar(unittest.TestCase):
    """TikTok exporta los caption sin escapar las comillas internas: una fila que
    cite algo sale con 15 campos en vez de 8 y todas las métricas corridas.
    `leer_csv()` la rehace apoyándose en la URL, que marca dónde vuelve a
    alinearse."""

    def test_una_fila_con_comillas_internas_no_corre_las_metricas(self):
        cabecera = ["Nombre del video", "Hora de publicación", "URL del video",
                    "Visualizaciones de video", "Me gusta"]
        sana = ["Un titulo normal", "2026-08-01", "https://tiktok.com/@x/video/1",
                "1000", "10"]
        rota = ('Habla de "Living With Michael Jackson", dijo,2026-08-02,'
                'https://tiktok.com/@x/video/2,2000,20')

        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "tiktok.csv"
            with ruta.open("w", encoding="utf-8", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(cabecera)
                w.writerow(sana)
            with ruta.open("a", encoding="utf-8") as fh:
                fh.write(rota + "\n")

            filas = met.leer_csv(ruta, "tiktok")

        self.assertEqual(len(filas), 2)
        self.assertEqual(filas[1]["Visualizaciones de video"], "2000",
                         "las métricas de la fila rota se leyeron corridas")
        self.assertEqual(filas[1]["Me gusta"], "20")


yt = cargar("13_youtube_api.py")


class CurvaDeRetencion(unittest.TestCase):
    """`resumir_curva()` reduce la curva a la única pregunta que importa en
    [P-12]: ¿la gente se va en el **gancho** (0-10 % del video) o en el **primer
    corte** (10-25 %)? Las dos respuestas mandan a sitios opuestos — reescribir
    el texto del guion, o cambiar el ritmo del montaje. Un tramo mal calculado
    manda a rehacer lo que no era."""

    def curva(self, valores):
        return [{"video_id": "x", "ratio": i / len(valores),
                 "audiencia": v, "relativa": None}
                for i, v in enumerate(valores)]

    def test_separa_el_gancho_del_primer_corte(self):
        """Curva plana al 1.0 en el gancho y al 0.5 después: los dos tramos
        tienen que salir distintos, no promediados juntos."""
        valores = [1.0] * 10 + [0.5] * 90        # 0-10 % alto, resto bajo
        r = yt.resumir_curva(self.curva(valores))
        self.assertAlmostEqual(r["gancho"], 1.0)
        self.assertAlmostEqual(r["primer_corte"], 0.5)

    def test_la_caida_del_gancho_se_mide_contra_el_arranque(self):
        valores = [1.0] + [0.8] * 9 + [0.5] * 90
        r = yt.resumir_curva(self.curva(valores))
        self.assertAlmostEqual(r["arranque"], 1.0)
        self.assertGreater(r["caida_gancho"], 0)

    def test_una_curva_vacia_no_revienta(self):
        r = yt.resumir_curva([])
        self.assertEqual(r["puntos"], 0)
        self.assertIsNone(r["arranque"])
        self.assertIsNone(r["caida_gancho"])

    def test_los_puntos_sin_dato_no_cuentan_como_cero(self):
        """Un None es 'YouTube no lo reporta', no 'no se quedó nadie'. Contarlo
        como 0 hundiría la media y haría creer que el gancho falla."""
        # Los 10 primeros puntos son el gancho: todos a 1.0 menos uno sin dato.
        gancho = [1.0, None, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
        r = yt.resumir_curva(self.curva(gancho + [0.5] * 90))
        self.assertAlmostEqual(r["gancho"], 1.0,
                               msg="el None se está contando como 0")


class CredencialesDeYouTube(unittest.TestCase):
    def test_pide_los_dos_permisos(self):
        """`yt-analytics.readonly` da las métricas y `youtube.readonly` dice qué
        video es cada ID. Con uno solo, la mitad de las llamadas dan 403."""
        scopes = yt.CONFIG["scopes"]
        self.assertTrue(any("yt-analytics.readonly" in s for s in scopes))
        self.assertTrue(any("youtube.readonly" in s for s in scopes))

    def test_el_token_y_el_secreto_estan_en_gitignore(self):
        """⚠️ Los dos son credenciales: el token da acceso de lectura a las
        analíticas del canal hasta que se revoque. Si esto falla, un `git add -A`
        las publica."""
        reglas = (RAIZ / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("client_secret", reglas)
        self.assertIn("token_youtube.json", reglas)
        self.assertTrue(yt.CONFIG["token"].startswith("credenciales/"))


if __name__ == "__main__":
    unittest.main()
