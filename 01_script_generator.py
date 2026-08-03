#%%
from dotenv import load_dotenv
import os
from openai import OpenAI

from estado import sellar_estado, reset_costo, registrar_openai, con_reintentos

load_dotenv()


# ========================================================================== #

TEMA = os.environ.get("TEMA")
PROYECTO = os.environ.get("PROYECTO")
openai_api_key = os.getenv("OPENAI_API_KEY")

# ========================================================================== #


client = OpenAI(api_key=openai_api_key)

tema_instruccion = (
    f"El evento o historia DEBE ser sobre: {TEMA}. "
    f"Busca el ángulo más oscuro, irónico o desconocido de este tema específico."
    if TEMA else
    "Elige libremente un evento histórico real que muy poca gente conoce."
)

prompt = f"""
Eres un guionista de videos virales históricos. Tu especialidad es encontrar 
el ángulo más oscuro, irónico o sorprendente de eventos reales.

TEMA: {tema_instruccion}

TAREA: Escribe un guion de exactamente 65-75 palabras sobre un evento histórico real.

REGLAS ESTRICTAS:
- El evento debe ser 100% verificable — nada de "se dice que" o "algunos creen"
- PROHIBIDO empezar con: "En", "Cuando", "Fue", "Era", "Hubo"
- La PRIMERA frase debe tener MÁXIMO 8 PALABRAS. Es la más importante del guion:
  si el espectador no se engancha ahí, no llega a la segunda. Cuéntala y si tiene
  más de 8 palabras, reescríbela.
- La primera frase debe hacer una afirmación que parezca imposible pero sea verdad
- La primera frase NO debe revelar el desenlace: abre la pregunta, no la respondas
- Incluir UN solo dato que el 95% de personas no conoce
- La última frase debe dejar una sensación de incredulidad o escalofrío
- CERO fechas en el texto (destruyen el ritmo)
- CERO palabras académicas: "acontecimiento", "hecho", "suceso", "historia"
- El evento debe ser 100% verificable — nada de "se dice que" o "algunos creen"
- PROHIBIDO exagerar consecuencias o inventar detalles para hacerlo más dramático
- Si el dato sorprendente no es verificable, no lo incluyas
- El drama debe venir de los hechos reales, no de adornos narrativos
- Una sola línea narrativa de principio a fin — sin cambiar de tema a mitad del guion
- La conclusión debe ser consecuencia directa del inicio, no una frase nueva

ÁNGULOS QUE FUNCIONAN (elige uno):
- Una decisión de segundos que cambió millones de vidas
- Un error absurdo que tuvo consecuencias enormes  
- Una coincidencia que parece inventada pero es real
- El lado oscuro de un héroe famoso
- Una tecnología, ley o costumbre cuyo origen nadie conoce

ESTILO:
- Frases de máximo 12 palabras (la primera, máximo 8)
- Ritmo: rápido, cinematográfico, como trailer de Netflix
- Cada frase debe empujar al lector a la siguiente
- Español latino neutro, conversacional
- El guion se narra en voz alta a ~160 palabras por minuto: 65-75 palabras son
  unos 25 segundos, que es la duración que mejor retiene en vertical. No te pases.

FORMATO DE SALIDA:
Solo el guion. Sin títulos, sin explicaciones, sin comillas.
"""

# El paso 01 abre el tema: reinicia el contador de costo.
reset_costo()

response = con_reintentos(
    lambda: client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {"role": "system", "content": (
                "Eres un periodista riguroso que escribe como guionista. "
                "Nunca inventas ni exageras. Si un hecho real ya es sorprendente, "
                "lo cuentas tal cual — eso es suficiente. "
                "Preferirías no escribir nada antes que distorsionar la verdad."
            )},
            {"role": "user", "content": prompt}
        ]
    ),
    etiqueta="guion (gpt-4.1)"
)

registrar_openai(response, "gpt-4.1", "guion")

script = response.choices[0].message.content
print(script)
print(f"\n📏 {len(script.split())} palabras (objetivo: 65-75)")

with open("script.txt", "w", encoding="utf-8") as f:
    f.write(script)

# Sello del tema en curso. Los archivos de la raíz (script.txt, voice.mp3,
# images_IA/...) son estado global compartido: si un paso falla a mitad, los
# siguientes seguirían trabajando con los datos del tema ANTERIOR sin notarlo.
# Los pasos 03, 04 y 07 comparan contra este archivo antes de tocar nada.
if PROYECTO:
    sellar_estado(PROYECTO, TEMA or "")
    print(f"🔖 Estado sellado: {PROYECTO}")