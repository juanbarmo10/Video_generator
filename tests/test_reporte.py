"""Tests del informe de métricas (`herramientas/11_reporte.py`).

Por qué estos y no otros: aquí un signo invertido o una métrica mal clasificada
**no rompe nada**. El informe se genera igual, se ve bien y afirma lo contrario
de lo que pasó. Es el peor tipo de fallo que tiene el repositorio, y el único
que no se nota corriendo el pipeline.

Pasó de verdad el 15 ago (dos veces):
  · `vistas_por_dia` clasificada como tasa daba «+5591 % en Instagram» sobre
    unos datos cuya diferencia real era 3.4×.
  · Cambiar `temas.csv` degradó la tanda anterior a baseline y `se_quedaron_pct`
    en YouTube pasó de −16 % a +33 % sin que nada avisara.

Se corren con:  python -m unittest discover tests
"""

import importlib.util
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _cargar(ruta: Path):
    """Importa por ruta. Con importlib porque los nombres empiezan por dígito y
    `import` no los acepta (mismo truco que usa 12_recordatorio.py)."""
    spec = importlib.util.spec_from_file_location(ruta.stem, ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def cargar(nombre: str):
    """Un `herramientas/NN_*.py`."""
    return _cargar(RAIZ / "herramientas" / nombre)


def cargar_pipeline(nombre: str):
    """Un módulo de `pipeline/`. ⚠️ Hoy solo vale para `estado.py`: los 8 pasos
    trabajan al importarse, que es el obstáculo real de P-11."""
    return _cargar(RAIZ / "pipeline" / nombre)


rep = cargar("11_reporte.py")
met = cargar("10_metricas.py")


def fila(plataforma="youtube", lote="v2-mas-cortes", edad=4, **campos):
    base = {"plataforma": plataforma, "lote": lote, "edad_dias": edad}
    base.update(campos)
    return base


class TipoMetrica(unittest.TestCase):
    """`TIPO_METRICA` es lo que decide si una comparación se publica o se aparta."""

    def test_toda_columna_mostrada_tiene_tipo(self):
        """Sin entrada explícita, `comparar_lotes()` asume 'acumulativa'. Ese
        default es el seguro (aparta en vez de afirmar), pero una métrica de
        ventana o de tasa que se olvide aquí se esconde sin motivo."""
        mostradas = {c for cols in rep.COLUMNAS_POR_PLATAFORMA.values() for c in cols}
        sin_tipo = sorted(mostradas - set(rep.TIPO_METRICA))
        self.assertEqual(sin_tipo, [], f"columnas sin TIPO_METRICA: {sin_tipo}")

    def test_vistas_por_dia_es_acumulativa_no_tasa(self):
        """La trampa documentada: parece que corrige la antigüedad y hace lo
        contrario — supone acumulación lineal cuando en video social casi todas
        las vistas llegan en 48 h. Si alguien la 'arregla' a tasa, el informe
        vuelve a publicar porcentajes de cuatro cifras."""
        self.assertEqual(rep.TIPO_METRICA["vistas_por_dia"], "acumulativa")

    def test_ventanas_e_internas_bien_clasificadas(self):
        self.assertEqual(rep.TIPO_METRICA["vistas_24h"], "ventana")
        self.assertEqual(rep.TIPO_METRICA["vistas_7d"], "ventana")
        self.assertEqual(rep.TIPO_METRICA["retencion_relativa"], "interna")


class Comparabilidad(unittest.TestCase):
    """Qué se publica como veredicto y qué se aparta con el motivo escrito."""

    def comparar(self, campo, tipo_filas, edad_nuevo=4, edad_base=66):
        filas = ([fila(lote="v2-mas-cortes", edad=edad_nuevo, **{campo: v})
                  for v in tipo_filas[0]]
                 + [fila(lote="baseline", edad=edad_base, **{campo: v})
                    for v in tipo_filas[1]])
        return rep.comparar_lotes(filas, "youtube", campo)

    def test_interna_nunca_es_comparable(self):
        """Está normalizada dentro de su propio lote: la comparación daría 0 %
        por construcción, así que publicarla sería inventar una conclusión."""
        r = self.comparar("retencion_relativa", ([1.2, 1.0], [1.0, 0.9]))
        self.assertFalse(r["comparable"])
        self.assertIn("propio lote", r["motivo"])

    def test_acumulativa_con_edades_dispares_no_es_comparable(self):
        """4 días contra 66: el baseline lleva 16 veces más tiempo sumando."""
        r = self.comparar("vistas", ([100, 120], [900, 1100]), 4, 66)
        self.assertFalse(r["comparable"])
        self.assertIn("edades no se parecen", r["motivo"])

    def test_acumulativa_con_edades_parecidas_si_es_comparable(self):
        """El filtro es por diferencia de edad, no por el tipo: si los dos lotes
        llevan lo mismo publicados, un acumulado sí dice algo."""
        r = self.comparar("vistas", ([100, 120], [90, 80]), 60, 66)
        self.assertTrue(r["comparable"], r["motivo"])

    def test_ventana_es_comparable_aunque_las_edades_difieran(self):
        """Es el punto de las ventanas: 'las primeras 24 h' iguala la edad por
        construcción, así que la diferencia de antigüedad ya no importa."""
        r = self.comparar("vistas_24h", ([300, 340], [50, 60]), 4, 66)
        self.assertTrue(r["comparable"], r["motivo"])

    def test_tasa_es_comparable_aunque_las_edades_difieran(self):
        r = self.comparar("retencion_pct", ([40, 44], [30, 32]), 4, 66)
        self.assertTrue(r["comparable"], r["motivo"])

    def test_sin_datos_en_un_lote_devuelve_none(self):
        filas = [fila(lote="v2-mas-cortes", vistas=100)]
        self.assertIsNone(rep.comparar_lotes(filas, "youtube", "vistas"))

    def test_no_mezcla_plataformas(self):
        """Cada red se compara consigo misma: un video de TikTok no puede entrar
        en el baseline de YouTube."""
        filas = [fila("youtube", "v2-mas-cortes", vistas_24h=300),
                 fila("tiktok", "baseline", vistas_24h=10),
                 fila("youtube", "baseline", vistas_24h=100)]
        r = rep.comparar_lotes(filas, "youtube", "vistas_24h")
        self.assertEqual(r["base"]["n"], 1)
        self.assertEqual(r["base"]["mediana"], 100)


class SignoYFiabilidad(unittest.TestCase):
    """El signo es justo lo que nadie revisa y lo que da la vuelta al veredicto."""

    def test_subida_es_mejora_y_el_porcentaje_sale_positivo(self):
        filas = [fila(lote="v2-mas-cortes", vistas_24h=v) for v in (200, 200)] \
              + [fila(lote="baseline", vistas_24h=v) for v in (100, 100)]
        r = rep.comparar_lotes(filas, "youtube", "vistas_24h")
        self.assertAlmostEqual(r["cambio_pct"], 100.0)
        self.assertTrue(r["mejora"])

    def test_bajada_no_es_mejora_y_el_porcentaje_sale_negativo(self):
        filas = [fila(lote="v2-mas-cortes", se_quedaron_pct=v) for v in (40, 40)] \
              + [fila(lote="baseline", se_quedaron_pct=v) for v in (50, 50)]
        r = rep.comparar_lotes(filas, "youtube", "se_quedaron_pct")
        self.assertAlmostEqual(r["cambio_pct"], -20.0)
        self.assertFalse(r["mejora"])

    def test_menos_es_mejor_invierte_el_juicio_no_el_porcentaje(self):
        """`MENOS_ES_MEJOR` hoy está vacío, pero existe para que nadie invierta
        un signo a mano el día que haga falta. Si alguien mete una métrica ahí,
        el porcentaje debe seguir diciendo la verdad y solo cambiar `mejora`."""
        rep.MENOS_ES_MEJOR.add("se_quedaron_pct")
        try:
            filas = [fila(lote="v2-mas-cortes", se_quedaron_pct=40)] * 2 \
                  + [fila(lote="baseline", se_quedaron_pct=50)] * 2
            r = rep.comparar_lotes(filas, "youtube", "se_quedaron_pct")
            self.assertAlmostEqual(r["cambio_pct"], -20.0)
            self.assertTrue(r["mejora"])
        finally:
            rep.MENOS_ES_MEJOR.discard("se_quedaron_pct")

    def test_fiable_mira_la_n_mas_pequena_de_las_dos(self):
        """Con n=1 en el lote nuevo la comparación no es concluyente aunque el
        baseline tenga 40 videos. Es exactamente el caso al que llegó el informe
        cuando el lote se degradó solo."""
        n_min = rep.CONFIG["n_minimo_fiable"]
        filas = [fila(lote="v2-mas-cortes", vistas_24h=300)] \
              + [fila(lote="baseline", vistas_24h=100)] * (n_min + 10)
        self.assertFalse(rep.comparar_lotes(filas, "youtube", "vistas_24h")["fiable"])

        filas = [fila(lote="v2-mas-cortes", vistas_24h=300)] * n_min \
              + [fila(lote="baseline", vistas_24h=100)] * n_min
        self.assertTrue(rep.comparar_lotes(filas, "youtube", "vistas_24h")["fiable"])


class Resumen(unittest.TestCase):
    def test_usa_mediana_no_promedio(self):
        """Con n=6 un solo video viral decide el promedio. Toda la comparación
        del informe está construida sobre la mediana justamente por eso."""
        filas = [fila(vistas=v) for v in (10, 10, 10, 10, 10_000)]
        self.assertEqual(rep.resumen(filas, "vistas")["mediana"], 10)

    def test_ignora_las_celdas_vacias_y_las_no_aplica(self):
        """'—' significa 'esta red no exporta el campo', que no es lo mismo que
        'falta el dato'. Ninguno de los dos debe contar como un cero."""
        filas = [fila(vistas=10), fila(vistas=""), fila(vistas="—"), fila(vistas=30)]
        r = rep.resumen(filas, "vistas")
        self.assertEqual(r["n"], 2)
        self.assertEqual(r["mediana"], 20)

    def test_sin_ningun_dato_devuelve_none(self):
        self.assertIsNone(rep.resumen([fila(vistas="")], "vistas"))


class ConfigsQueDebenCoincidir(unittest.TestCase):
    """El paso 10 escribe los nombres de lote y el 11 los lee. Son dos archivos
    distintos con el mismo literal escrito a mano, y nada los ata: si divergen,
    el informe compara un lote que no existe y no encuentra nada que decir."""

    def test_baseline_coincide_entre_paso_10_y_paso_11(self):
        self.assertEqual(met.CONFIG["lote_baseline"], rep.CONFIG["lote_baseline"])

    def test_el_informe_conoce_el_lote_que_escribe_el_paso_10(self):
        """El paso 10 puede ir por delante (se sube `lote_nuevo` al cargar un
        `temas.csv` nuevo) sin que el informe lo sepa todavía, y eso es legítimo
        mientras ese lote no tenga métricas. Lo que no vale es que el informe
        apunte a un lote que el paso 10 no escribe ni ha escrito nunca."""
        conocidos = {met.CONFIG["lote_nuevo"], met.CONFIG["lote_baseline"]}
        historicos = set()
        csv_metricas = RAIZ / met.CONFIG["salida"]
        if csv_metricas.exists():
            historicos = {(f.get("lote") or "").strip()
                          for f in met.leer_csv(csv_metricas)}
        self.assertIn(rep.CONFIG["lote_nuevo"], conocidos | historicos)


if __name__ == "__main__":
    unittest.main()
