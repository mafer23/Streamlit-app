import streamlit as st
from groq import Groq
from firecrawl import FirecrawlApp
import json
import re
import requests
from bs4 import BeautifulSoup
import base64

st.set_page_config(page_title="Detector de Estafas - Marketplace CO", page_icon="🛡️")

# ---- CONFIGURACIÓN ----
import os

try:
    API_KEY = st.secrets.get("GROQ_API_KEY", "") or os.environ.get("GROQ_API_KEY", "")
    FIRECRAWL_KEY = st.secrets.get("FIRECRAWL_API_KEY", "") or os.environ.get("FIRECRAWL_API_KEY", "")
except Exception:
    API_KEY = os.environ.get("GROQ_API_KEY", "")
    FIRECRAWL_KEY = os.environ.get("FIRECRAWL_API_KEY", "")

# Permitir ingresar la API Key manualmente si no está configurada
if not API_KEY:
    st.sidebar.warning("🔑 GROQ_API_KEY no detectada.")
    api_key_input = st.sidebar.text_input(
        "Ingresa tu Groq API Key:",
        type="password",
        help="Obtenela gratis en https://console.groq.com/"
    )
    if api_key_input:
        API_KEY = api_key_input

if API_KEY:
    client = Groq(api_key=API_KEY)
else:
    client = None

if FIRECRAWL_KEY:
    firecrawl = FirecrawlApp(api_key=FIRECRAWL_KEY)
else:
    firecrawl = None

SYSTEM_PROMPT = """Eres un experto en detectar estafas en marketplaces colombianos (Facebook Marketplace, OLX, Mercado Libre).
Analiza el siguiente anuncio y responde SOLO con un JSON válido, sin texto adicional, sin markdown, con esta estructura exacta:

{
  "riesgo": "ALTO" | "MEDIO" | "BAJO",
  "puntaje": numero entre 0 y 100,
  "senales": ["señal 1", "señal 2", "señal 3"],
  "explicacion": "explicación breve de 2-3 frases",
  "recomendacion": "consejo práctico para el comprador"
}

Señales típicas de estafa en Colombia a considerar:
- Pide pago anticipado por Nequi, Daviplata o transferencia antes de entregar
- Precio muy por debajo del valor real de mercado
- Urgencia artificial ("vendo hoy", "me voy del país", "último día")
- Solo contacto por WhatsApp, no acepta llamadas ni reuniones
- No permite ver o probar el producto antes de pagar
- Cuenta nueva, sin fotos de perfil o sin historial
- Pide datos personales o financieros innecesarios
- Fotos genéricas, de stock, o que parecen bajadas de internet
- Vendedor no quiere reunirse en lugar público

Anuncio a analizar:
"""

PLATAFORMAS_STEALTH = ["facebook","mercadolibre", "olx", "mercadopago", "falabella", "exito"]

def extraer_texto_de_url(url):
    from urllib.parse import urlparse, urlunparse

    parsed = urlparse(url)
    if "facebook.com" in parsed.netloc:
        raise Exception(
            "Facebook Marketplace no permite la extracción automática de anuncios.\n\n"
            "📸 Subí una captura de pantalla del anuncio o\n"
            "📝 copiá y pegá el texto del anuncio.\n\n"
            "La IA puede analizar ambos formatos directamente."
        )
    # Detectar si es una plataforma que bloquea bots y usar Firecrawl (stealth)
    usa_firecrawl = any(p in parsed.netloc for p in PLATAFORMAS_STEALTH)

    if usa_firecrawl and firecrawl:
        try:
            st.info(f"🔍 Intentando extraer contenido con Firecrawl de: {parsed.netloc}")

            result = firecrawl.scrape_url(
                url=url,
                formats=["markdown"],
                only_main_content=True
            )

            contenido = (
                getattr(result, "markdown", None)
                or (result.get("markdown") if isinstance(result, dict) else None)
            )

            if contenido and len(contenido.strip()) > 50:
                return f"Contenido extraído del anuncio:\n{contenido[:4000]}"

            st.warning("⚠️ Firecrawl no devolvió contenido útil.")

        except Exception as e:
            st.error(f"❌ Error de Firecrawl: {str(e)}")
            raise

    elif usa_firecrawl and not firecrawl:
        raise Exception(
            "Esta plataforma requiere el scraper inteligente (Firecrawl) para acceder a su contenido, "
            "pero la clave FIRECRAWL_API_KEY no está configurada en los secrets.\n\n"
            "Por ahora, copiá el texto del anuncio o subí una captura de pantalla."
        )

    # Fallback estándar con BeautifulSoup
    try:
        if "facebook.com" in parsed.netloc:
            url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "es-ES,es;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
        }

        response = requests.get(
            url,
            headers=headers,
            timeout=10,
            allow_redirects=True
        )

        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}")

        soup = BeautifulSoup(response.text, "html.parser")

        meta_desc = soup.find("meta", attrs={"name": "description"})
        og_desc = soup.find("meta", attrs={"property": "og:description"})
        og_title = soup.find("meta", attrs={"property": "og:title"})

        title = soup.title.string if soup.title else ""

        partes = []

        if title:
            partes.append(f"Título de la publicación: {title.strip()}")

        if og_title and og_title.get("content"):
            partes.append(
                f"Título alternativo: {og_title.get('content').strip()}"
            )

        if meta_desc and meta_desc.get("content"):
            partes.append(
                f"Descripción corta: {meta_desc.get('content').strip()}"
            )

        if og_desc and og_desc.get("content"):
            partes.append(
                f"Descripción detallada: {og_desc.get('content').strip()}"
            )

        if len(partes) < 2:
            for script in soup(["script", "style"]):
                script.decompose()

            texto_cuerpo = soup.get_text(
                separator=" ",
                strip=True
            )

            partes.append(
                f"Contenido del anuncio:\n{texto_cuerpo[:3000]}"
            )

        return "\n\n".join(partes)

    except Exception as e:
        err_msg = str(e)

        plataforma = (
            "Facebook Marketplace"
            if "facebook.com" in parsed.netloc
            else "la plataforma"
        )

        raise Exception(
            f"No se pudo extraer la información del enlace automáticamente ({err_msg}).\n\n"
            f"¿Por qué ocurre esto? {plataforma} utiliza sistemas de seguridad muy estrictos para bloquear el acceso de robots y proteger sus datos.\n\n"
            f"¿Cómo continuar?\n"
            f"1. Copiá y pegá el texto del anuncio en la pestaña 📝 Pegar Texto.\n"
            f"2. O tomá una captura de pantalla del anuncio y subila en la pestaña 📸 Subir Imagen (Captura)."
        )
def analizar_anuncio(texto, imagen_base64=None):
    if not client:
        return {
            "error": "API Key de Groq no configurada.",
            "riesgo": "DESCONOCIDO",
            "puntaje": 0,
            "senales": [],
            "explicacion": "No se encontró la clave de API en secrets.toml ni en el entorno.",
            "recomendacion": "Ingresá tu API Key en la barra lateral o configurala en .streamlit/secrets.toml"
        }
    try:
        if imagen_base64:
            model_name = "meta-llama/llama-4-scout-17b-16e-instruct"
            content_list = [
                {"type": "text", "text": f"Por favor, analizá el anuncio o captura de pantalla provista. Texto o contexto adicional: {texto or 'Ninguno.'}"},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{imagen_base64}"
                    }
                }
            ]
        else:
            model_name = "llama-3.3-70b-versatile"
            content_list = [
                {"type": "text", "text": f"Anuncio a analizar:\n{texto}"}
            ]

        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": content_list}
            ],
            response_format={"type": "json_object"}
        )
        raw = response.choices[0].message.content.strip()

        # Limpiar posibles bloques de markdown ```json ... ```
        raw = re.sub(r"^```json|^```|```$", "", raw, flags=re.MULTILINE).strip()

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {
                "riesgo": "DESCONOCIDO",
                "puntaje": 0,
                "senales": ["No se pudo procesar la respuesta del modelo"],
                "explicacion": raw[:300],
                "recomendacion": "Intenta de nuevo o revisa tu API key"
            }
    except Exception as e:
        err_msg = str(e)
        if "RateLimit" in err_msg or "429" in err_msg:
            return {
                "error": "Límite de cuota excedido en Groq (429).",
                "riesgo": "DESCONOCIDO",
                "puntaje": 0,
                "senales": [],
                "explicacion": "Se superó el límite de solicitudes por minuto de la API gratuita de Groq.",
                "recomendacion": "Esperá unos segundos antes de volver a intentar."
            }
        return {
            "error": f"Error al conectar con la API de Groq: {err_msg}",
            "riesgo": "DESCONOCIDO",
            "puntaje": 0,
            "senales": [],
            "explicacion": err_msg,
            "recomendacion": "Revisá que tu API Key de Groq sea válida y que tengas conexión a internet."
        }

# ---- INTERFAZ ----
st.title("🛡️ Detector de Estafas - Marketplace")
st.caption("Analizá capturas de pantalla, enlaces o textos de publicaciones en Facebook Marketplace, OLX o Mercado Libre.")

# Selector de método de entrada
metodo_entrada = st.radio(
    "Seleccioná el método de entrada:",
    ["📝 Pegar Texto", "🔗 Analizar Enlace", "📸 Subir Imagen (Captura)"],
    horizontal=True
)

texto_analisis = ""
imagen_base64 = None

if metodo_entrada == "📝 Pegar Texto":
    texto_analisis = st.text_area(
        "Texto del anuncio o conversación:",
        height=200,
        placeholder="Ej: Vendo iPhone 15 nuevo, $1.200.000, solo pago por Nequi, no atiendo llamadas..."
    )

elif metodo_entrada == "🔗 Analizar Enlace":
    enlace_url = st.text_input(
        "Enlace de la publicación:",
        placeholder="https://articulo.mercadolibre.com.co/... o link de Marketplace"
    )
    st.caption(
        "⚠️ **Nota**: Facebook, Instagram y algunas redes protegen con fuerza sus plataformas contra el rastreo automático. "
        "Si el rastreo falla o lee datos incompletos, te sugerimos copiar el texto del anuncio o subir una captura de pantalla."
    )
    texto_analisis = enlace_url

else:  # "📸 Subir Imagen (Captura)"
    imagen_archivo = st.file_uploader(
        "Subí la captura de pantalla de la publicación o del chat:",
        type=["png", "jpg", "jpeg"]
    )
    texto_analisis = st.text_area(
        "Contexto o detalles adicionales (opcional):",
        placeholder="Ej: El vendedor me pide pago anticipado para reservar el producto..."
    )
    if imagen_archivo:
        imagen_base64 = base64.b64encode(imagen_archivo.read()).decode('utf-8')

if st.button("🔍 Analizar", type="primary"):
    # Validaciones según la entrada
    if metodo_entrada == "📝 Pegar Texto" and not texto_analisis.strip():
        st.warning("⚠️ Por favor, pegá el texto del anuncio primero.")
    elif metodo_entrada == "🔗 Analizar Enlace" and not texto_analisis.strip():
        st.warning("⚠️ Por favor, ingresá una dirección web (URL) válida.")
    elif metodo_entrada == "📸 Subir Imagen (Captura)" and not imagen_archivo:
        st.warning("⚠️ Por favor, cargá una imagen o captura de pantalla.")
    elif not API_KEY or API_KEY == "PEGA_TU_API_KEY_AQUI":
        st.error("❌ Falta configurar tu API key de Groq. Obtenela gratis en console.groq.com")
    else:
        # Procesamiento de entrada
        texto_para_llm = texto_analisis
        error_extraccion = False
        
        if metodo_entrada == "🔗 Analizar Enlace":
            with st.spinner("🕷️ Extrayendo información de la publicación..."):
                try:
                    texto_para_llm = extraer_texto_de_url(enlace_url)
                except Exception as e:
                    st.error(str(e))
                    error_extraccion = True
        
        if not error_extraccion:
            with st.spinner("🕵️ Analizando patrones y señales con Inteligencia Artificial..."):
                resultado = analizar_anuncio(texto_para_llm, imagen_base64)

            if "error" in resultado:
                st.error(resultado["error"])
                st.markdown(f"**Detalles:** {resultado['explicacion']}")
                st.info(f"💡 **Recomendación:** {resultado['recomendacion']}")
            else:
                riesgo = resultado.get("riesgo", "DESCONOCIDO")
                puntaje = resultado.get("puntaje", 0)

                colores = {"ALTO": "🔴", "MEDIO": "🟡", "BAJO": "🟢", "DESCONOCIDO": "⚪"}

                st.markdown(f"### {colores.get(riesgo, '⚪')} Riesgo: {riesgo} ({puntaje}/100)")
                st.progress(min(max(puntaje, 0), 100) / 100)

                st.markdown("**Señales detectadas:**")
                for senal in resultado.get("senales", []):
                    st.markdown(f"- {senal}")

                st.markdown("**Explicación:**")
                st.write(resultado.get("explicacion", ""))

                st.info(f"💡 **Recomendación:** {resultado.get('recomendacion', '')}")

st.divider()
st.caption("Hecho con Streamlit + Gemini API (gratis) · Proyecto para portafolio de IA")
