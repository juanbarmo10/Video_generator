"""Tests de [pipeline/estado.py](../pipeline/estado.py).

Es el único módulo de `pipeline/` que se puede importar sin que trabaje: los 8
pasos hacen cosas al importarse (leen `script.txt`, instancian clientes, hacen
`SystemExit` si falta `PROYECTO`), y por eso todavía no tienen tests.

⚠️ `estado.py` escribe `.estado_actual` y `.costo_actual.json` **relativos al
directorio de trabajo**, que es justo el estado global del tema en curso. Todos
los tests de aquí corren dentro de un `tmpdir` (`EnTmpDir`) para no pisar un
lote que esté ejecutándose. El `assertNotEqual` contra la raíz del repositorio
no es paranoia decorativa: sin él, un `chdir` que falle borraría el sello del
tema en curso y el pipeline seguiría con los datos del anterior.

Se corren con:  python -m unittest discover tests
"""

import json
import os
import tempfile
import unittest
from pathlib import Path

from test_reporte import RAIZ, cargar_pipeline  # noqa: F401  (ver test_reporte)

estado = cargar_pipeline("estado.py")


class EnTmpDir(unittest.TestCase):
    """Aísla el directorio de trabajo. Sin esto, los tests escribirían el sello
    y el contador de costo del tema que el pipeline esté procesando."""

    def setUp(self):
        self._antes = Path.cwd()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        os.chdir(self.tmp)
        self.addCleanup(os.chdir, self._antes)
        self.assertNotEqual(Path.cwd().resolve(), RAIZ,
                            "los tests NO pueden correr sobre la raíz del repo")
        self._env = dict(os.environ)
        self.addCleanup(lambda: (os.environ.clear(), os.environ.update(self._env)))


class Sello(EnTmpDir):
    """El sello evita el fallo que motivó todo el módulo: si un paso revienta a
    mitad del pipeline, los siguientes trabajarían con los archivos de la raíz
    del tema ANTERIOR y producirían un video convincente pero equivocado."""

    def test_sella_y_relee(self):
        estado.sellar_estado("Historia09", "Naufragio Romano")
        self.assertEqual(estado.leer_estado(), ("Historia09", "Naufragio Romano"))

    def test_aborta_si_los_archivos_son_de_otro_proyecto(self):
        estado.sellar_estado("Historia09", "Naufragio Romano")
        os.environ["PROYECTO"] = "Historia10"
        with self.assertRaises(SystemExit) as ctx:
            estado.verificar_estado("07")
        mensaje = str(ctx.exception)
        self.assertIn("Historia09", mensaje)
        self.assertIn("Historia10", mensaje)

    def test_no_aborta_si_es_el_mismo_proyecto(self):
        estado.sellar_estado("Historia09", "Naufragio Romano")
        os.environ["PROYECTO"] = "Historia09"
        estado.verificar_estado("07")      # no debe lanzar

    def test_sin_sello_no_aborta(self):
        """Correr un paso suelto a mano sobre artefactos ya existentes es un
        flujo legítimo y documentado; el sello no puede prohibirlo."""
        os.environ["PROYECTO"] = "Historia09"
        estado.verificar_estado("07")

    def test_sin_proyecto_en_el_entorno_no_aborta(self):
        estado.sellar_estado("Historia09", "Naufragio Romano")
        os.environ.pop("PROYECTO", None)
        estado.verificar_estado("07")

    def test_el_tema_es_opcional(self):
        estado.sellar_estado("Historia09")
        self.assertEqual(estado.leer_estado(), ("Historia09", ""))


class ContadorDeCosto(EnTmpDir):
    def test_reset_arranca_en_cero(self):
        estado.registrar_costo("algo", 1.0)
        estado.reset_costo()
        self.assertIn("$0.0000", estado.resumen_costo())

    def test_suma_y_guarda_el_detalle(self):
        estado.reset_costo()
        estado.registrar_costo("uno", 0.01)
        estado.registrar_costo("dos", 0.02)
        datos = json.loads(Path(estado.ARCHIVO_COSTO).read_text(encoding="utf-8"))
        self.assertAlmostEqual(datos["total_usd"], 0.03)
        self.assertEqual([d["concepto"] for d in datos["detalle"]], ["uno", "dos"])

    def test_un_json_corrupto_no_tumba_el_pipeline(self):
        """El contador es contabilidad, no producto: si el archivo se corrompe,
        perder la cuenta es aceptable; abortar el tema a mitad no lo es."""
        Path(estado.ARCHIVO_COSTO).write_text("{roto", encoding="utf-8")
        estado.registrar_costo("uno", 0.01)
        self.assertIn("0.0100", estado.resumen_costo())


class PreciosQueFaltan(EnTmpDir):
    """⚠️ La trampa documentada: `registrar_openai()` hace `if not precio:
    return`, así que **un modelo que no esté en `PRECIOS_OPENAI` no se cobra y
    el contador miente en silencio**. Es peor que fallar, porque el número que
    sale al final del paso parece correcto."""

    class _Uso:
        prompt_tokens = 1_000_000
        completion_tokens = 1_000_000

    class _Respuesta:
        usage = None

    def respuesta(self):
        r = self._Respuesta()
        r.usage = self._Uso()
        return r

    def test_un_modelo_conocido_se_cobra(self):
        estado.reset_costo()
        estado.registrar_openai(self.respuesta(), "gpt-4.1", "guion")
        datos = json.loads(Path(estado.ARCHIVO_COSTO).read_text(encoding="utf-8"))
        self.assertAlmostEqual(datos["total_usd"], 10.0)   # 2.00 in + 8.00 out

    def test_un_modelo_desconocido_no_suma_nada(self):
        """Congela el comportamiento real para que quede escrito que es así, no
        para bendecirlo: si algún día se prefiere que reviente, este test es el
        que hay que cambiar a propósito."""
        estado.reset_costo()
        estado.registrar_openai(self.respuesta(), "gpt-inventado", "guion")
        datos = json.loads(Path(estado.ARCHIVO_COSTO).read_text(encoding="utf-8"))
        self.assertEqual(datos["total_usd"], 0.0)

    def test_los_modelos_que_usa_el_pipeline_tienen_precio(self):
        """La red de seguridad de verdad: los modelos que los pasos nombran hoy
        tienen que estar tarifados. Si alguien cambia un `modelo_*` en un CONFIG
        y olvida `PRECIOS_OPENAI`, esto falla antes de que el contador mienta."""
        import re
        usados = set()
        for py in (RAIZ / "pipeline").glob("*.py"):
            texto = py.read_text(encoding="utf-8")
            usados |= set(re.findall(r'model\s*=\s*"(gpt-[\w.\-]+)"', texto))
            usados |= set(re.findall(r'"modelo\w*":\s*"(gpt-[\w.\-]+)"', texto))
        self.assertTrue(usados, "no se encontró ningún modelo gpt en pipeline/")
        faltan = sorted(usados - set(estado.PRECIOS_OPENAI))
        self.assertEqual(faltan, [], f"modelos sin precio en estado.py: {faltan}")

    def test_anthropic_tambien_esta_tarifado(self):
        self.assertIn("claude-opus-5", estado.PRECIOS_ANTHROPIC)


class Reintentos(EnTmpDir):
    """Un 429 o un corte de red a mitad del pipeline abortaba el tema habiendo
    pagado ya los pasos anteriores."""

    def test_devuelve_al_primer_intento_sin_esperar(self):
        llamadas = []
        r = estado.con_reintentos(lambda: llamadas.append(1) or "ok", intentos=3)
        self.assertEqual(r, "ok")
        self.assertEqual(len(llamadas), 1)

    def test_reintenta_y_acaba_devolviendo(self):
        llamadas = []

        def falla_dos_veces():
            llamadas.append(1)
            if len(llamadas) < 3:
                raise ConnectionError("429")
            return "ok"

        r = estado.con_reintentos(falla_dos_veces, intentos=3, espera_base=0)
        self.assertEqual(r, "ok")
        self.assertEqual(len(llamadas), 3)

    def test_si_fallan_todos_propaga_la_excepcion_original(self):
        """No puede tragarse el error: el paso tiene que abortar el tema, no
        seguir con un resultado vacío."""
        def siempre_falla():
            raise ConnectionError("429")

        with self.assertRaises(ConnectionError):
            estado.con_reintentos(siempre_falla, intentos=2, espera_base=0)


if __name__ == "__main__":
    unittest.main()
