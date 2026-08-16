"""Tests de las funciones puras de los pasos **04, 05 y 06** (P-11).

Por qué estos y no otros — la misma regla que en el resto del repositorio: se
prueba por **tipo de fallo**, no por cobertura. En estos tres pasos casi todo
error se ve enseguida (el tema aborta, o el video sale mal y se nota), salvo
cuatro cosas que **degradan en silencio**:

  · `build_prompt()` recortando el estilo base en vez de la escena → las
    imágenes pierden el look y el anclaje de época, y nadie mira los prompts.
  · `sanitize_prompt()` dejando pasar una palabra vetada → fal la rechaza y el
    tema se queda con menos imágenes de las que cree.
  · `parse_image_list()` → una línea mal leída es una foto real menos, y el
    paso 07 sigue sin quejarse.
  · `parse_carrusel()` → **el contrato de formato con el paso 02**. Si el prompt
    del 02 cambia, aquí el hook pasa a ser CTA y el carrusel sale del revés,
    sin un solo error.

Como el resto, no tocan la red ni los archivos del tema en curso: `cargar_paso()`
prepara el entorno desde fuera.

Se corren con:  python -m unittest discover tests
"""

import tempfile
import unittest
from pathlib import Path

from test_pipeline import cargar_paso

p04 = cargar_paso("04_image_generator.py")
p05 = cargar_paso("05_download_images.py")
p06 = cargar_paso("06_carrusel_generator.py")


# ══════════════════════════════════════════════════════════════
#   PASO 04 — el prompt de las imágenes
# ══════════════════════════════════════════════════════════════

class ConstruirPrompt(unittest.TestCase):
    """⚠️ Lo que se protege aquí es **qué se recorta cuando no cabe**."""

    CONTEXTO = {"personaje": "Einstein", "epoca": "1905",
                "estilo_visual": "vintage"}

    def test_respeta_el_limite(self):
        prompt = p04.build_prompt("escena " * 500, self.CONTEXTO)
        self.assertLessEqual(len(prompt), p04.PROMPT_MAX_CHARS)

    def test_el_estilo_base_sobrevive_al_recorte(self):
        """Con una escena enorme, el encabezado que define el look tiene que
        seguir entero: es lo que hace que las 6 imágenes parezcan del mismo
        video. Recortarlo a él sería invisible hasta ver el resultado."""
        prompt = p04.build_prompt("x" * 5000, self.CONTEXTO)
        self.assertTrue(prompt.startswith(p04.BASE_PROMPT[:40]))

    def test_el_contexto_de_epoca_sobrevive_al_recorte(self):
        prompt = p04.build_prompt("x" * 5000, self.CONTEXTO)
        self.assertIn("1905", prompt)

    def test_sin_contexto_no_revienta(self):
        """`extract_context()` degrada a None si GPT no devuelve json usable."""
        prompt = p04.build_prompt("una escena cualquiera", None)
        self.assertTrue(prompt)
        self.assertLessEqual(len(prompt), p04.PROMPT_MAX_CHARS)

    def test_la_escena_entra_si_cabe(self):
        prompt = p04.build_prompt("un laboratorio con pizarras", self.CONTEXTO)
        self.assertIn("laboratorio", prompt)


class SanearPrompt(unittest.TestCase):
    """Las palabras que disparan el filtro de moderación."""

    def test_reemplaza_lo_declarado(self):
        for palabra, sustituto in list(p04.REPLACEMENTS.items())[:5]:
            salida = p04.sanitize_prompt(f"a {palabra} b")
            self.assertNotIn(palabra.lower(), salida.lower(),
                             f"«{palabra}» no se reemplazó")
            self.assertIn(sustituto.split()[0], salida)

    def test_no_toca_palabras_que_solo_la_contienen(self):
        """El reemplazo usa `\\b`: «warmth» no debe convertirse por «war»."""
        if "war" in p04.REPLACEMENTS:
            self.assertIn("warmth", p04.sanitize_prompt("warmth of the fire"))

    def test_es_insensible_a_mayusculas(self):
        palabra = next(iter(p04.REPLACEMENTS))
        self.assertNotIn(palabra.lower(),
                         p04.sanitize_prompt(palabra.upper()).lower())

    def test_texto_limpio_pasa_igual(self):
        limpio = "an old library with wooden shelves"
        self.assertEqual(p04.sanitize_prompt(limpio), limpio)


# ══════════════════════════════════════════════════════════════
#   PASO 05 — la lista de fotos reales
# ══════════════════════════════════════════════════════════════

class ListaDeImagenes(unittest.TestCase):
    """El formato `img_N.jpg → query` es un contrato con el paso 02."""

    def escribir(self, texto: str) -> str:
        tmp = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False,
                                          encoding="utf-8")
        tmp.write(texto)
        tmp.close()
        self.addCleanup(lambda: Path(tmp.name).unlink(missing_ok=True))
        return tmp.name

    def test_lee_las_lineas_validas(self):
        ruta = self.escribir("img_0.jpg → Albert Einstein 1905\n"
                             "img_1.jpg → Patent office Bern\n")
        self.assertEqual(p05.parse_image_list(ruta),
                         [("img_0.jpg", "Albert Einstein 1905"),
                          ("img_1.jpg", "Patent office Bern")])

    def test_ignora_prosa_y_lineas_vacias(self):
        """El paso 02 a veces envuelve la lista en texto. Colarse una línea de
        prosa como query gastaría una búsqueda en una frase sin sentido."""
        ruta = self.escribir("Aquí van las imágenes:\n\n"
                             "img_0.jpg → Einstein\n"
                             "(fin de la lista)\n")
        self.assertEqual(p05.parse_image_list(ruta), [("img_0.jpg", "Einstein")])

    def test_tolera_espacios_alrededor_de_la_flecha(self):
        ruta = self.escribir("img_2.jpg    →     Bern   \n")
        self.assertEqual(p05.parse_image_list(ruta), [("img_2.jpg", "Bern")])

    def test_archivo_sin_ninguna_linea_valida(self):
        self.assertEqual(p05.parse_image_list(self.escribir("nada útil\n")), [])


class ConstruirQuery(unittest.TestCase):

    def test_quita_puntuacion_que_rompe_la_busqueda(self):
        self.assertEqual(p05.build_query('Einstein\'s "office" (1905)'),
                         "Einstein s office 1905")

    def test_colapsa_espacios(self):
        self.assertEqual(p05.build_query("a    b\t c"), "a b c")

    def test_texto_limpio_no_cambia(self):
        self.assertEqual(p05.build_query("Albert Einstein 1905"),
                         "Albert Einstein 1905")


class EsRelevante(unittest.TestCase):
    """Primer filtro de las candidatas, antes de la validación con visión."""

    def test_acepta_si_coincide_la_mitad(self):
        self.assertTrue(p05.is_relevant(
            "Albert Einstein 1905",
            {"title": "Albert Einstein portrait", "url": "", "image": ""}))

    def test_rechaza_lo_que_no_tiene_nada_que_ver(self):
        self.assertFalse(p05.is_relevant(
            "Albert Einstein 1905",
            {"title": "Cat on a sofa", "url": "", "image": ""}))

    def test_las_palabras_vacias_no_cuentan_como_coincidencia(self):
        """Si «the» y «of» contaran, cualquier título en inglés pasaría."""
        self.assertFalse(p05.is_relevant(
            "the fall of the roman empire",
            {"title": "the making of a sandwich", "url": "", "image": ""}))

    def test_mira_tambien_la_url(self):
        self.assertTrue(p05.is_relevant(
            "Einstein Bern",
            {"title": "", "url": "https://x.org/einstein_bern_1905", "image": ""}))


# ══════════════════════════════════════════════════════════════
#   PASO 06 — el contrato de formato con el paso 02
# ══════════════════════════════════════════════════════════════

class ParseoDelCarrusel(unittest.TestCase):
    """⚠️ `carrusel.txt` son párrafos separados por línea en blanco, SIN
    etiquetas «Slide N». Si el prompt del paso 02 cambia, esto se rompe en
    silencio: el carrusel sale con el hook de CTA y nadie ve un error."""

    def parsear(self, texto: str) -> dict:
        tmp = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False,
                                          encoding="utf-8")
        tmp.write(texto)
        tmp.close()
        self.addCleanup(lambda: Path(tmp.name).unlink(missing_ok=True))
        return p06.parse_carrusel(tmp.name)

    TEXTO = ("El gancho que abre.\n\n"
             "Primer dato del cuerpo.\n\n"
             "Segundo dato del cuerpo.\n\n"
             "Sígueme para más historias.\n\n"
             "#historia #curiosidades")

    def test_reparte_portada_cuerpo_y_cta(self):
        post = self.parsear(self.TEXTO)
        self.assertEqual(post["hook"], "El gancho que abre.")
        self.assertEqual(post["cta"], "Sígueme para más historias.")
        self.assertEqual(len(post["body"]), 2)

    def test_los_hashtags_salen_del_cuerpo(self):
        post = self.parsear(self.TEXTO)
        self.assertIn("#historia", post["hashtags"])
        self.assertNotIn("#historia", " ".join([post["cta"], *post["body"]]))

    def test_sin_hashtags_no_revienta(self):
        post = self.parsear("Gancho.\n\nCuerpo.\n\nCTA.")
        self.assertEqual(post["hashtags"], "")
        self.assertEqual(post["hook"], "Gancho.")

    def test_un_solo_parrafo_es_solo_portada(self):
        """Sin cuerpo ni CTA no debe duplicar el hook en los tres sitios."""
        post = self.parsear("Solo el gancho.")
        self.assertEqual(post["hook"], "Solo el gancho.")
        self.assertEqual(post["cta"], "")
        self.assertEqual(post["body"], [])

    def test_dos_parrafos_son_portada_y_cta_sin_cuerpo(self):
        post = self.parsear("Gancho.\n\nCTA.")
        self.assertEqual(post["body"], [])
        self.assertEqual(post["cta"], "CTA.")

    def test_no_quedan_parrafos_vacios_por_lineas_de_mas(self):
        post = self.parsear("Gancho.\n\n\n\nCuerpo.\n\n\nCTA.")
        self.assertEqual(len(post["body"]), 1)


class UnaSolaDefinicion(unittest.TestCase):
    """⚠️ El paso 06 tenía **dos** `parse_instagram_file()` y ganaba la segunda,
    así que editar la primera no hacía nada (trampa 2 de CLAUDE.md). Se borró la
    muerta; esto evita que vuelva."""

    def test_el_paso_06_no_repite_definiciones(self):
        fuente = (Path(p06.__file__).read_text(encoding="utf-8")
                  if hasattr(p06, "__file__") else "")
        nombres = [l.split("(")[0].removeprefix("def ").strip()
                   for l in fuente.splitlines() if l.startswith("def ")]
        repes = {n for n in nombres if nombres.count(n) > 1}
        self.assertEqual(repes, set(), f"definiciones duplicadas: {repes}")


if __name__ == "__main__":
    unittest.main()
