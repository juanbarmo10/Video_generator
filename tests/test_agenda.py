"""Tests de la agenda de publicación (`herramientas/16_agenda.py`) y del hilo
de Threads (`herramientas/15_threads_api.py`).

Por qué estos: la agenda la dispara `cron`, o sea que **nadie la mira cuando
corre**. Sus dos fallos posibles no dan error —publicar dos veces el mismo tema,
o publicar el mismo tema en las tres redes la misma semana— y solo se ven ya
publicados, en la cuenta. Es el mismo tipo de fallo silencioso que justificó los
tests del informe.

Ninguno toca la red ni el `.env`: todo sale de CSV escritos en un temporal.

Se corren con:  python -m unittest discover tests
"""

import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def cargar(nombre: str):
    ruta = RAIZ / "herramientas" / nombre
    spec = importlib.util.spec_from_file_location(ruta.stem, ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


ag = cargar("16_agenda.py")
th = cargar("15_threads_api.py")


class AgendaFalsa(unittest.TestCase):
    """Monta un `publicar/` de mentira y apunta la agenda a él.

    ⚠️ Cambia `ag.RAIZ`, que es de dónde la agenda lee TODO. Sin esto los tests
    leerían el `publicar/` de verdad y, peor, `temas_ya_usados()` daría
    resultados distintos según lo que se hubiera publicado esa semana.
    """

    CAL = [
        ("2026-08-16", "12:00", "Historia08", "no"),
        ("2026-08-17", "12:00", "Historia09", "SÍ — el guion no pasó el control"),
    ]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self.tmp.name)
        self._raiz_real = ag.RAIZ
        ag.RAIZ = self.raiz

        pub = self.raiz / "publicar"
        for tema in ("Historia01", "Historia02", "Historia03",
                     "Historia08", "Historia09", "Test01"):
            carr = pub / tema / "carrusel"
            carr.mkdir(parents=True)
            for n in range(6):
                (carr / f"slide_0{n}.jpg").write_bytes(b"x")

        with (pub / "calendario.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["fecha", "hora", "proyecto", "revisar_a_mano"])
            w.writerows(self.CAL)

    def tearDown(self):
        ag.RAIZ = self._raiz_real
        self.tmp.cleanup()

    def anotar(self, *filas):
        ruta = self.raiz / "publicar" / "publicado.csv"
        with ruta.open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["fecha", "proyecto", "red", "id_publicacion"])
            w.writerows(filas)


class TestMaterial(AgendaFalsa):

    def test_solo_temas_con_carrusel(self):
        (self.raiz / "publicar" / "SinCarrusel").mkdir()
        self.assertNotIn("SinCarrusel", ag.temas_con_material())

    def test_excluye_los_de_config(self):
        self.assertNotIn("Test01", ag.temas_con_material())

    def test_orden_estable(self):
        temas = ag.temas_con_material()
        self.assertEqual(temas, sorted(temas))


class TestRotacion(AgendaFalsa):
    """La regla que da la variedad: un tema gasta UN extra en toda su vida."""

    def test_empieza_por_el_mas_antiguo(self):
        self.assertEqual(ag.siguiente_tema("2026-08-15"), "Historia01")

    def test_no_repite_tema_entre_redes(self):
        """El caso que motiva el test: martes carrusel, jueves álbum, sábado
        hilo. Si los tres cogieran el mismo tema, las tres redes contarían lo
        mismo esa semana — justo lo contrario de lo que se busca."""
        self.anotar(("2026-08-18", "Historia01", "instagram_carrusel", "1"))
        self.assertEqual(ag.siguiente_tema("2026-08-20"), "Historia02")

        self.anotar(("2026-08-18", "Historia01", "instagram_carrusel", "1"),
                    ("2026-08-20", "Historia02", "facebook_album", "2"))
        self.assertEqual(ag.siguiente_tema("2026-08-22"), "Historia03")

    def test_el_reel_no_gasta_el_turno(self):
        """Publicar el reel NO consume el extra: si lo hiciera, ningún tema
        tendría nunca carrusel, porque todos salen antes en video."""
        self.anotar(("2026-08-15", "Historia01", "instagram", "1"),
                    ("2026-08-15", "Historia01", "facebook", "2"))
        self.assertEqual(ag.siguiente_tema("2026-08-16"), "Historia01")

    def test_no_adelanta_un_tema_a_su_propio_reel(self):
        """Historia08 y Historia09 tienen el reel programado para mañana: su
        carrusel no puede salir hoy."""
        self.anotar(*[(f"2026-08-1{i}", f"Historia0{i}", "instagram_carrusel", str(i))
                      for i in (1, 2, 3)])
        self.assertIsNone(ag.siguiente_tema("2026-08-15"))

    def test_entra_en_cuanto_pasa_su_fecha(self):
        self.anotar(*[(f"2026-08-1{i}", f"Historia0{i}", "instagram_carrusel", str(i))
                      for i in (1, 2, 3)])
        self.assertEqual(ag.siguiente_tema("2026-08-17"), "Historia08")

    def test_cola_agotada_devuelve_none(self):
        self.anotar(*[(f"2026-08-1{i}", t, "facebook_album", str(i))
                      for i, t in enumerate(("Historia01", "Historia02", "Historia03",
                                             "Historia08", "Historia09"), 1)])
        self.assertIsNone(ag.siguiente_tema("2026-08-30"))


class TestCalendario(AgendaFalsa):

    def test_toca_hoy_encuentra_la_fila(self):
        self.assertEqual(ag.toca_hoy("2026-08-16")["proyecto"], "Historia08")

    def test_dia_sin_fila_no_publica(self):
        self.assertIsNone(ag.toca_hoy("2026-08-30"))

    def test_dia_sin_extra_no_elige_tema(self):
        """Lunes (weekday 0) no está en `dias_extra`: no debe publicar nada."""
        self.assertFalse(ag.publicar_extra("2026-08-17", dry_run=True))

    def test_ya_salio_distingue_la_red(self):
        self.anotar(("2026-08-15", "Historia01", "instagram", "9"))
        self.assertIsNotNone(ag.ya_salio("Historia01", "instagram"))
        self.assertIsNone(ag.ya_salio("Historia01", "instagram_carrusel"))


class TestRecuperacion(AgendaFalsa):
    """Lo que pasa cuando el PC estuvo apagado. Es el caso que no se ve fallar:
    nada da error, simplemente ese video no sale nunca."""

    CAL = [
        ("2026-08-16", "12:00", "Historia08", "no"),
        ("2026-08-17", "12:00", "Historia09", "no"),
        ("2026-08-18", "12:00", "Historia03", "no"),
    ]

    def test_un_dia_perdido_no_pierde_el_video(self):
        """Con `toca_hoy()` a secas, Historia08 no se publicaba jamás."""
        cola = ag.pendientes("2026-08-18")
        self.assertEqual([f["proyecto"] for f in cola],
                         ["Historia08", "Historia09", "Historia03"])

    def test_publica_el_mas_antiguo_primero(self):
        self.assertEqual(ag.pendientes("2026-08-20")[0]["proyecto"], "Historia08")

    def test_no_adelanta_los_del_futuro(self):
        self.assertEqual([f["proyecto"] for f in ag.pendientes("2026-08-16")],
                         ["Historia08"])

    def test_lo_ya_publicado_sale_de_la_cola(self):
        self.anotar(("2026-08-16", "Historia08", "instagram", "1"),
                    ("2026-08-16", "Historia08", "facebook", "2"))
        self.assertEqual([f["proyecto"] for f in ag.pendientes("2026-08-20")],
                         ["Historia09", "Historia03"])

    def test_una_red_a_medias_sigue_pendiente(self):
        """Si una red salió y la otra falló, la fila vuelve mañana: dentro,
        `publicar()` se salta la red que ya está.

        ⚠️ Fija sus DOS redes en vez de leer `CONFIG["redes_reel"]`. Lo que
        prueba es la regla —«a medias sigue pendiente»—, no cuántas redes haya
        configuradas hoy; y el 28 ago Facebook salió del reel automático
        (P-31), lo que dejó la lista en una sola red y tumbó este test sin que
        la regla hubiera cambiado.
        """
        previas = ag.CONFIG["redes_reel"]
        ag.CONFIG["redes_reel"] = ["instagram", "facebook"]
        try:
            self.anotar(("2026-08-16", "Historia08", "instagram", "1"))
            self.assertEqual(ag.pendientes("2026-08-20")[0]["proyecto"],
                             "Historia08")
        finally:
            ag.CONFIG["redes_reel"] = previas

    def test_extra_perdido_se_recupera_el_mismo_semana(self):
        """Martes apagado: el carrusel sale el miércoles, no la semana que viene."""
        self.assertEqual(ag.extra_que_toca("2026-08-19"), "instagram_carrusel")

    def test_extra_ya_hecho_no_se_repite(self):
        self.anotar(("2026-08-18", "Historia01", "instagram_carrusel", "1"))
        self.assertEqual(ag.extra_que_toca("2026-08-19"), None)

    def test_el_de_la_semana_pasada_no_cuenta(self):
        """Lunes 17 abre semana nueva: lo del martes anterior no vale."""
        self.anotar(("2026-08-11", "Historia01", "instagram_carrusel", "1"))
        self.assertEqual(ag.extra_que_toca("2026-08-18"), "instagram_carrusel")

    def test_uno_por_corrida(self):
        """Sábado con los tres pendientes: sale el primero, no los tres."""
        self.assertEqual(ag.extra_que_toca("2026-08-22"), "instagram_carrusel")
        self.anotar(("2026-08-22", "Historia01", "instagram_carrusel", "1"))
        self.assertEqual(ag.extra_que_toca("2026-08-22"), "facebook_album")

    def test_lunes_no_toca_nada(self):
        self.assertIsNone(ag.extra_que_toca("2026-08-17"))

    def test_la_semana_empieza_en_lunes(self):
        self.assertEqual(ag.inicio_de_semana("2026-08-22"), "2026-08-17")
        self.assertEqual(ag.inicio_de_semana("2026-08-17"), "2026-08-17")


class TestDiasExtra(unittest.TestCase):

    def test_una_red_por_dia(self):
        """Dos extras el mismo día se pisarían: el dict solo deja uno, así que
        lo que hay que comprobar es que no falte ninguna red."""
        self.assertEqual(len(CONF := ag.CONFIG["dias_extra"]), len(set(CONF.values())))

    def test_los_dias_son_validos(self):
        for dia in ag.CONFIG["dias_extra"]:
            self.assertIn(dia, range(7))

    def test_el_reel_no_esta_entre_los_extras(self):
        """Si `instagram` acabara en `dias_extra`, `temas_ya_usados()` contaría
        los reels y la cola de extras nacería vacía."""
        for red in ag.CONFIG["redes_reel"]:
            self.assertNotIn(red, ag.CONFIG["dias_extra"].values())


class TestRecorteHilo(unittest.TestCase):
    """Threads corta a 500 caracteres. Lo garantiza Python, no el prompt."""

    def test_texto_corto_intacto(self):
        self.assertEqual(th.recortar("Hola mundo"), "Hola mundo")

    def test_no_parte_palabras(self):
        largo = "palabra " * 100
        corto = th.recortar(largo, 50)
        self.assertLessEqual(len(corto), 51)          # +1 por el «…»
        self.assertTrue(corto.endswith("…"))
        self.assertNotIn("palab…", corto)

    def test_quita_la_puntuacion_colgante(self):
        self.assertEqual(th.recortar("uno dos, tres", 9), "uno dos…")

    def test_respeta_el_limite_de_threads(self):
        self.assertLessEqual(ag.CONFIG and th.CONFIG["max_chars"], 500)


if __name__ == "__main__":
    unittest.main()

class OrdenDeRecuperacion(AgendaFalsa):
    """`pendientes()` devuelve **por fecha**, no por orden del archivo.

    Congela el fallo del 25 ago: al reprogramar las resubidas de Facebook, una
    fila quedó al final del CSV con fecha anterior a las de arriba. El código
    prometía «el más antiguo» en su docstring y entregaba «el primero del
    archivo», así que el atraso se habría recuperado al revés en silencio.
    """

    # La fila más antigua va la ÚLTIMA del archivo, que es justo el caso real.
    CAL = [
        ("2026-08-28", "12:00", "Historia08", "no"),
        ("2026-08-27", "12:00", "Historia07", "no"),
    ]

    def test_devuelve_el_mas_antiguo_aunque_este_al_final_del_csv(self):
        self.anotar()
        cola = ag.pendientes("2026-08-29")
        self.assertEqual([f["proyecto"] for f in cola],
                         ["Historia07", "Historia08"])
