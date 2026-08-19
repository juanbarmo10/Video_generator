"""Tests de las funciones puras de los 8 pasos (`pipeline/0N_*.py`).

⚠️ **Los pasos trabajan al importarse** — hacen `SystemExit` si falta `PROYECTO`,
instancian clientes de API, llaman a `verificar_estado()`. TODO.md proponía mover
esas guardas dentro de `main()` para poder probarlos; **no hace falta**. Basta
prepararles el entorno desde fuera, que es lo que hace `cargar_paso()`:

  · `chdir` a un temporal → `verificar_estado()` no encuentra sello y vuelve sin
    abortar, y ningún `open()` relativo toca los archivos del tema EN CURSO.
  · claves de API **falsas** en el entorno → los clientes se instancian pero no
    llaman a nadie; nada de esto hace red.

Así se prueban sin modificar ni una línea de `pipeline/`, y se pueden correr con
un lote en marcha.

Se corren con:  python -m unittest discover tests
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

from test_reporte import RAIZ, _cargar

_CLAVES_FALSAS = {
    "PROYECTO": "TestUnitario",
    "TEMA": "Tema de prueba",
    "TITULO_VIDEO": "Titulo de prueba",
    "OPENAI_API_KEY": "sk-falsa-solo-para-instanciar",
    "ELEVENLABS_API_KEY": "falsa",
    "FAL_KEY": "falsa",
}


def cargar_paso(nombre: str):
    """Importa un paso con el entorno preparado y el cwd fuera del repositorio.

    ⚠️ `pipeline/` va a `sys.path` porque 6 de los 8 pasos hacen
    `from estado import ...`. Eso funciona al correrlos con
    `python pipeline/0N_….py` —Python pone en `sys.path` el directorio del
    script— pero no con `importlib`. Es la misma línea que CLAUDE.md pide
    ejecutar antes de la primera celda en VS Code.
    """
    ruta_pipeline = str(RAIZ / "pipeline")
    if ruta_pipeline not in sys.path:
        sys.path.insert(0, ruta_pipeline)

    antes_cwd = Path.cwd()
    antes_env = dict(os.environ)
    try:
        os.environ.update(_CLAVES_FALSAS)
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            assert Path.cwd().resolve() != RAIZ, "no se puede importar sobre la raíz"
            return _cargar(RAIZ / "pipeline" / nombre)
    finally:
        os.chdir(antes_cwd)
        os.environ.clear()
        os.environ.update(antes_env)


p01 = cargar_paso("01_script_generator.py")
p02 = cargar_paso("02_social_media_generator.py")
p07 = cargar_paso("07_video_generator.py")


# ═══════════════════════════════════════════════════════════════════════
#   PASO 01 — las reglas que se miden en Python porque un LLM las falla
# ═══════════════════════════════════════════════════════════════════════

GUION_OK = (
    "Robin Hood no fue quien te contaron. "
    "Su nombre aparece en registros legales auténticos, pero no como defensor "
    "de los pobres, sino acusado de crímenes comunes. Su historia se fue "
    "mezclando con la de otros bandidos del bosque de Barnsdale. El de las "
    "baladas no repartió nada entre los pobres, y esa parte se añadió mucho "
    "más tarde para hacerlo simpático al público inglés de entonces."
)


class ReglasMecanicas(unittest.TestCase):
    """`verificar_reglas_mecanicas()` es la capa gratis: cuesta cero y caza en
    Python lo que el crítico cobraría por señalar. Existe porque **a un LLM no
    se le pide que cuente palabras**: lo hace mal y cobra por hacerlo mal."""

    def graves(self, script):
        return p01.verificar_reglas_mecanicas(script)[0]

    def leves(self, script):
        return p01.verificar_reglas_mecanicas(script)[1]

    def test_un_guion_correcto_no_tiene_faltas_graves(self):
        n = len(GUION_OK.split())
        self.assertTrue(60 <= n <= 80, f"el guion de prueba mide {n} palabras")
        self.assertEqual(self.graves(GUION_OK), [])

    def test_demasiado_corto_es_grave(self):
        self.assertTrue(any("palabras" in g for g in self.graves("Muy corto. Ya está.")))

    def test_un_poco_fuera_de_rango_es_leve_no_grave(self):
        """La tolerancia existe para no tirar un guion bueno por dos palabras.

        El guion se arma con frases cortas a propósito: si fuera una sola frase
        larga saltaría la regla del gancho y no se estaría midiendo esto."""
        cfg = p01.CONFIG
        total = cfg["palabras_max"] + 2          # dentro de la tolerancia
        frases = ["Algo raro ocurrió allí."]     # gancho corto, 4 palabras
        restantes = total - 4
        while restantes:
            trozo = min(8, restantes)            # frases cortas, como pide el prompt
            frases.append(" ".join(["dato"] * trozo) + ".")
            restantes -= trozo
        script = " ".join(frases)
        self.assertGreater(len(script.split()), cfg["palabras_max"])
        self.assertLessEqual(len(script.split()),
                             cfg["palabras_max"] + cfg["palabras_tolerancia"])
        self.assertEqual([g for g in self.graves(script) if "palabras" in g], [])
        self.assertTrue(any("un poco fuera" in l for l in self.leves(script)))

    def test_primera_frase_larga_es_grave(self):
        """Es el gancho: la regla que más pesa de todo el prompt."""
        script = GUION_OK.replace(
            "Robin Hood no fue quien te contaron.",
            "Robin Hood no fue en absoluto la persona que todo el mundo cree que fue.")
        self.assertTrue(any("primera frase" in g for g in self.graves(script)))

    def test_inicio_prohibido_es_grave_y_no_le_afectan_las_tildes(self):
        for inicio in ("En", "Cuando", "Fue"):
            script = f"{inicio} aquel lugar todo cambió. " + GUION_OK
            self.assertTrue(any("prohibido" in g for g in self.graves(script)),
                            f"no detectó el inicio '{inicio}'")

    def test_una_fecha_de_cuatro_cifras_es_grave(self):
        self.assertTrue(any("1762" in g for g in self.graves(
            GUION_OK.replace("mucho", "en 1762 mucho"))))

    def test_un_mes_escrito_es_grave(self):
        self.assertTrue(any("mes" in g for g in self.graves(
            GUION_OK.replace("mucho", "en agosto mucho"))))

    def test_una_muletilla_es_grave(self):
        """'se dice' delata justo lo que el crítico va a rechazar después."""
        self.assertTrue(any("verificable" in g for g in self.graves(
            "Se dice que " + GUION_OK)))

    def test_los_absolutos_son_LEVES_no_graves(self):
        """⚠️ Deliberado: *'nunca robó a los ricos'* estaba en el ÚNICO guion que
        aprobó el control. Como graves habrían tirado el mejor guion del lote."""
        script = GUION_OK.replace("no repartió nada", "nunca repartió nada")
        self.assertEqual([g for g in self.graves(script) if "bsoluto" in g], [])
        self.assertTrue(any("bsoluto" in l for l in self.leves(script)))

    def test_los_similes_y_los_verbos_de_mente_son_leves(self):
        con_simil = GUION_OK.replace("mezclando", "mezclando, como si fuera humo,")
        self.assertTrue(any("ímil" in l for l in self.leves(con_simil)))
        self.assertEqual([g for g in self.graves(con_simil) if "ímil" in g], [])

        con_mente = GUION_OK.replace("Su historia se fue", "Él pensó que su historia se fue")
        self.assertTrue(any("mentales" in l for l in self.leves(con_mente)))

    def test_un_guion_vacio_no_revienta(self):
        graves, _ = p01.verificar_reglas_mecanicas("")
        self.assertTrue(graves)


class LaPuerta(unittest.TestCase):
    """`cumple_la_puerta()` decide **qué se publica**, no solo cuándo dejar de
    reintentar. Con `abortar_si_ninguno_pasa: True` y nadie leyendo los guiones,
    es lo único que separa un dato falso de YouTube. Los umbrales están
    calibrados sobre Historia09-15 y estos tests los congelan."""

    def veredicto(self, nota=8, dudosas=0):
        return {"nota": nota, "afirmaciones_dudosas": ["x"] * dudosas,
                "problemas": []}

    def test_un_guion_limpio_pasa(self):
        pasa, motivos = p01.cumple_la_puerta([], self.veredicto(8, 0))
        self.assertTrue(pasa)
        self.assertEqual(motivos, [])

    def test_una_falta_grave_lo_tumba_aunque_el_critico_lo_adore(self):
        """Las graves son mecánicas y objetivas: una fecha en el guion no se
        compensa con un 10 del crítico."""
        pasa, motivos = p01.cumple_la_puerta(["Contiene la fecha '1762'."],
                                             self.veredicto(10, 0))
        self.assertFalse(pasa)
        self.assertTrue(any("grave" in m for m in motivos))

    def test_el_umbral_de_dudosas_es_el_calibrado(self):
        """3 pasa y 4 no: es exactamente donde cae la frontera medida entre
        Historia15 (datos documentados) e Historia09 ('lujo romano')."""
        cfg = p01.CONFIG
        self.assertEqual(cfg["dudosas_max"], 3, "umbral calibrado el 15 ago")
        self.assertTrue(p01.cumple_la_puerta([], self.veredicto(6, 3))[0])
        self.assertFalse(p01.cumple_la_puerta([], self.veredicto(6, 4))[0])

    def test_la_nota_minima_sigue_siendo_un_suelo(self):
        pasa, motivos = p01.cumple_la_puerta(
            [], self.veredicto(p01.CONFIG["nota_minima"] - 1, 0))
        self.assertFalse(pasa)
        self.assertTrue(any("nota" in m for m in motivos))

    def test_los_motivos_explican_todos_los_fallos_no_solo_el_primero(self):
        """El mensaje de aborto es lo único que queda en el log cuando el tema
        se cae: tiene que decir todo lo que falló, no cortar en el primero."""
        _, motivos = p01.cumple_la_puerta(["grave"], self.veredicto(2, 9))
        self.assertEqual(len(motivos), 3, motivos)

    def test_un_veredicto_incompleto_no_revienta_y_no_aprueba(self):
        """Si el crítico devuelve algo raro, el fallo seguro es NO publicar."""
        pasa, _ = p01.cumple_la_puerta([], {})
        self.assertFalse(pasa)

    def test_el_flujo_automatico_esta_activado(self):
        """⚠️ Congela la decisión del 15 ago: nadie lee los guiones, así que un
        guion que no pasa la puerta no puede convertirse en video. Si alguien
        pone esto en False, publica lo que entre."""
        self.assertTrue(p01.CONFIG["abortar_si_ninguno_pasa"])


# ═══════════════════════════════════════════════════════════════════════
#   PASO 02 — lo que va al .env lo lee BASH
# ═══════════════════════════════════════════════════════════════════════

class SanearValorEnv(unittest.TestCase):
    """⚠️ Lo más delicado del repositorio. `run_pipeline.sh` hace `source .env`:
    ese archivo lo ejecuta **bash**, y el título lo escribe un LLM.

    Pasó de verdad con `Historia07`: un salto de línea partió la entrada en
    varias líneas del `.env`, `save_to_env()` solo reemplaza la primera que
    empieza por `TITULO_VIDEO=`, y bash intentó ejecutar las sueltas como
    comandos — con `set -e`, abortando el pipeline."""

    def test_los_saltos_de_linea_se_colapsan(self):
        r = p02.sanear_valor_env("Titulo\ncon salto\r\ny otro\ttab")
        self.assertNotIn("\n", r)
        self.assertNotIn("\r", r)
        self.assertNotIn("\t", r)
        self.assertEqual(r, "Titulo con salto y otro tab")

    def test_quita_lo_que_bash_ejecutaria(self):
        """Dentro de comillas dobles, un título con `$(...)` se EJECUTARÍA."""
        r = p02.sanear_valor_env('Un $(rm -rf /) titulo `peligroso` con "comillas" y \\')
        for caracter in ('"', "`", "$", "\\"):
            self.assertNotIn(caracter, r)

    def test_no_deja_espacios_de_mas_al_quitar_caracteres(self):
        """Quitar un carácter no puede dejar el hueco: el valor se vuelve a
        colapsar DESPUÉS de la limpieza, no antes."""
        r = p02.sanear_valor_env('Einstein  $  y   el "examen" \\ de ingreso')
        self.assertNotIn("  ", r)
        self.assertEqual(r, r.strip())

    def test_un_titulo_normal_no_se_toca(self):
        titulo = "Robin Hood: el forajido medieval tras la leyenda"
        self.assertEqual(p02.sanear_valor_env(titulo), titulo)


class SepararHashtags(unittest.TestCase):
    """Se separan en Python recorriendo las líneas desde el final y tomando las
    que solo tienen tokens que empiezan por `#`."""

    def test_separa_el_bloque_final(self):
        cuerpo, tags = p02.separar_hashtags(
            "Una historia buenísima.\n¿Tú qué harías?\n\n#historia #curiosidades")
        self.assertIn("¿Tú qué harías?", cuerpo)
        self.assertNotIn("#historia", cuerpo)
        self.assertIn("#historia", tags)

    def test_sin_hashtags_devuelve_el_texto_entero_y_no_revienta(self):
        cuerpo, tags = p02.separar_hashtags("Solo texto, sin etiquetas.")
        self.assertIn("Solo texto", cuerpo)
        self.assertEqual(tags.strip(), "")

    def test_una_almohadilla_dentro_de_una_frase_no_cuenta(self):
        """`#1` no es un hashtag: un hashtag de verdad lleva alguna letra."""
        cuerpo, _ = p02.separar_hashtags("Le pusieron el #1 del ranking mundial.")
        self.assertIn("ranking", cuerpo)
        self.assertTrue(cuerpo.endswith("mundial."))

    def test_los_pegados_al_final_del_parrafo_tambien_se_separan(self):
        """El caso real de `Historia07`, que salió a Facebook con 24 hashtags.

        El modelo los dejó en la MISMA línea que la última frase, así que el
        barrido por líneas no los veía; después `escribir_descripcion()` añadía
        su bloque debajo y el texto se publicaba con los dos juegos.
        """
        cuerpo, tags = p02.separar_hashtags(
            "¿Qué otros secretos siguen sumergidos en las aguas de Vigo? "
            "#HistoriaNaval #Galeón #España")
        self.assertTrue(cuerpo.endswith("aguas de Vigo?"), cuerpo)
        self.assertNotIn("#", cuerpo)
        self.assertEqual(tags.split(), ["#HistoriaNaval", "#Galeón", "#España"])

    def test_pegados_y_bloque_se_juntan_en_orden(self):
        cuerpo, tags = p02.separar_hashtags("Final. #uno #dos\n\n#tres")
        self.assertEqual(cuerpo, "Final.")
        self.assertEqual(tags.split(), ["#uno", "#dos", "#tres"])

    def test_la_descripcion_larga_no_duplica_los_hashtags(self):
        """`escribir_descripcion()` pasa la larga por `separar_hashtags()`.

        Sin eso, una larga que ya traía hashtags pegados recibía encima el
        bloque de la general: 12 + 12 = 24, que es spam declarado en Meta.
        """
        import tempfile, os
        general = "Pie del reel.\n\n#historia #curiosidades"
        detallada = {"titulo": "Un título", "tags": ["a", "b"],
                     "descripcion": "Párrafo largo. #historia #curiosidades",
                     "comentario_fijado": "¿Tú qué opinas?"}
        destino = os.path.join(tempfile.mkdtemp(), "descripcion.txt")
        p02.escribir_descripcion(destino, general, detallada)
        with open(destino, encoding="utf-8") as fh:
            escrito = fh.read()
        self.assertEqual(escrito.count("#historia"), 2)   # una por descripción
        self.assertNotIn("Párrafo largo. #historia", escrito)


class LimitesDeTexto(unittest.TestCase):
    """Los límites los garantiza **Python**, nunca el prompt: a un LLM no se le
    pide que cuente caracteres."""

    def test_la_descripcion_larga_cabe_en_el_limite(self):
        parrafos = ["Párrafo de relleno. " * 20] * 6
        larga = "\n\n".join(parrafos)
        tags = "#historia #curiosidades #viral"
        r = p02.recortar_a_limite(larga, tags, p02.LIMITE_DESCRIPCION_LARGA)
        self.assertLessEqual(len(r), p02.LIMITE_DESCRIPCION_LARGA)

    def test_recortar_conserva_siempre_el_ultimo_parrafo(self):
        """Ahí está la pregunta que invita a comentar; es lo último que se tira."""
        larga = "\n\n".join(["Relleno larguísimo. " * 30] * 5
                            + ["¿Y tú qué habrías hecho en su lugar?"])
        r = p02.recortar_a_limite(larga, "#historia", p02.LIMITE_DESCRIPCION_LARGA)
        self.assertIn("¿Y tú qué habrías hecho", r)

    def test_lo_que_ya_cabe_no_se_toca(self):
        corta = "Una descripción corta."
        r = p02.recortar_a_limite(corta, "#historia", p02.LIMITE_DESCRIPCION_LARGA)
        self.assertIn("Una descripción corta.", r)

    def test_truncar_titulo_corta_por_una_frontera_y_no_a_machete(self):
        titulo = ("Albert Einstein y el examen de ingreso que cambió su destino: "
                  "la historia completa del año que pasó en Aarau")
        r = p02._truncar_titulo(titulo, p02.LIMITE_TITULO)
        self.assertLessEqual(len(r), p02.LIMITE_TITULO)
        self.assertFalse(r.endswith(" "))
        self.assertNotIn("  ", r)

    def test_truncar_no_deja_una_palabra_partida(self):
        titulo = "Una historia absolutamente extraordinaria sobre naufragios romanos increibles"
        r = p02._truncar_titulo(titulo, p02.LIMITE_TITULO)
        self.assertTrue(titulo.startswith(r.rstrip("…").rstrip()),
                        f"{r!r} no es un prefijo limpio del original")

    def test_un_titulo_que_ya_cabe_sale_igual(self):
        titulo = "Robin Hood: el forajido tras la leyenda"
        self.assertEqual(p02._truncar_titulo(titulo, p02.LIMITE_TITULO), titulo)


# ═══════════════════════════════════════════════════════════════════════
#   PASO 07 — el orden de los planos (P-15)
# ═══════════════════════════════════════════════════════════════════════

CFG_DISPERSA = {"dispersar_planos": True, "ventana_dispersion": 2}
CFG_CLASICA = {"dispersar_planos": False, "ventana_dispersion": 2}


class RepartirPlanos(unittest.TestCase):
    def test_reparte_segun_la_duracion_real_no_un_numero_fijo(self):
        cfg = {"duracion_plano_objetivo": 1.8}
        reparto = p07.repartir_planos(6, 25.0, cfg)
        self.assertEqual(len(reparto), 6)
        self.assertEqual(sum(reparto), round(25.0 / 1.8))

    def test_ninguna_imagen_se_queda_sin_plano(self):
        """Con un audio muy corto y muchas imágenes, el reparto no puede dar 0:
        una imagen sin planos desaparecería del video."""
        reparto = p07.repartir_planos(8, 4.0, {"duracion_plano_objetivo": 1.8})
        self.assertEqual(len(reparto), 8)
        self.assertTrue(all(n >= 1 for n in reparto), reparto)

    def test_el_override_manda(self):
        self.assertEqual(p07.repartir_planos(4, 25.0, {"planos_por_imagen": 3}),
                         [3, 3, 3, 3])


class DispersarPlanos(unittest.TestCase):
    """P-15. Antes la secuencia era `A1 A2 B1 B2`: dos encuadres seguidos de la
    misma imagen, que el ojo lee como zoom y no como corte. Medido sobre un
    reparto real, 8 de 13 transiciones eran la misma imagen; ahora son 0."""

    def transiciones_repetidas(self, orden):
        return sum(1 for a, b in zip(orden, orden[1:]) if a[0] == b[0])

    def test_no_pierde_ni_duplica_ningun_plano(self):
        """⚠️ El test que congela el bug de `grupos[-2] += grupos.pop()`: Python
        evaluaba el pop antes de asignar, así que con 5 imágenes se comía las dos
        primeras y duplicaba la última. El video salía completo y equivocado."""
        for reparto in ([2, 2, 2], [2, 2, 2, 2, 2], [3, 1, 2, 1, 4], [1] * 7, [5, 1]):
            orden = p07.dispersar_planos(reparto, CFG_DISPERSA)
            with self.subTest(reparto=reparto):
                self.assertEqual(len(orden), sum(reparto))
                self.assertEqual(sorted(orden),
                                 sorted((i, k) for i, n in enumerate(reparto)
                                        for k in range(n)))

    def test_el_primer_plano_es_siempre_la_imagen_1(self):
        """El voraz abriría por la segunda si esa tiene más planos — y el frame 0
        es el que lleva el título y el que decide si te quedas."""
        for reparto in ([1, 4], [1, 5, 1], [2, 2], [1, 9]):
            with self.subTest(reparto=reparto):
                self.assertEqual(p07.dispersar_planos(reparto, CFG_DISPERSA)[0], (0, 0))

    def test_dispersa_de_verdad_las_transiciones(self):
        reparto = [2] * 6
        clasico = p07.dispersar_planos(reparto, CFG_CLASICA)
        disperso = p07.dispersar_planos(reparto, CFG_DISPERSA)
        self.assertEqual(self.transiciones_repetidas(clasico), 6)
        self.assertEqual(self.transiciones_repetidas(disperso), 0)

    def test_no_baraja_la_narrativa_solo_intercala_vecinas(self):
        """Las imágenes vienen en orden narrativo del paso 04 —la 1 ilustra la
        primera frase y la última el desenlace—, así que un barajado global
        pondría el final en el segundo 3. Con ventana 2 el desfase es un plano."""
        reparto = [2] * 8
        orden = p07.dispersar_planos(reparto, CFG_DISPERSA)
        posicion_media = {}
        for pos, (img, _) in enumerate(orden):
            posicion_media.setdefault(img, []).append(pos)
        medias = [sum(v) / len(v) for _, v in sorted(posicion_media.items())]
        self.assertEqual(medias, sorted(medias),
                         "el avance narrativo general debe conservarse")
        self.assertEqual(orden[-1][0], 7, "la última imagen cierra el video")

    def test_el_interruptor_restaura_el_orden_clasico(self):
        """`dispersar_planos: False` sirve para comparar lotes (P-12)."""
        self.assertEqual(p07.dispersar_planos([2, 2, 2], CFG_CLASICA),
                         [(0, 0), (0, 1), (1, 0), (1, 1), (2, 0), (2, 1)])

    def test_una_sola_imagen_no_revienta(self):
        self.assertEqual(p07.dispersar_planos([3], CFG_DISPERSA),
                         [(0, 0), (0, 1), (0, 2)])


if __name__ == "__main__":
    unittest.main()
