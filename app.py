import streamlit as st
from groq import Groq
from firecrawl import FirecrawlApp
import json
import re
import os
import requests
from bs4 import BeautifulSoup
import base64

st.set_page_config(page_title="Detector de Estafas - Marketplace", page_icon="🛡️", layout="centered")

# =========================================================
# CONFIGURACIÓN
# =========================================================
try:
    API_KEY = st.secrets.get("GROQ_API_KEY", "") or os.environ.get("GROQ_API_KEY", "")
    FIRECRAWL_KEY = st.secrets.get("FIRECRAWL_API_KEY", "") or os.environ.get("FIRECRAWL_API_KEY", "")
except Exception:
    API_KEY = os.environ.get("GROQ_API_KEY", "")
    FIRECRAWL_KEY = os.environ.get("FIRECRAWL_API_KEY", "")

if not API_KEY:
    st.sidebar.warning("🔑 GROQ_API_KEY no detectada.")
    api_key_input = st.sidebar.text_input(
        "Ingresa tu Groq API Key:",
        type="password",
        help="Obtenela gratis en https://console.groq.com/"
    )
    if api_key_input:
        API_KEY = api_key_input

client = Groq(api_key=API_KEY) if API_KEY else None
firecrawl = FirecrawlApp(api_key=FIRECRAWL_KEY) if FIRECRAWL_KEY else None

PLATAFORMAS_STEALTH = ["facebook", "mercadolibre", "olx", "mercadopago", "falabella", "exito"]


# =========================================================
# UTILIDADES COMUNES
# =========================================================
def limpiar_json(raw):
    raw = raw.strip()
    raw = re.sub(r"^```json|^```|```$", "", raw, flags=re.MULTILINE).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "riesgo": "DESCONOCIDO",
            "puntaje": 0,
            "senales": ["No se pudo procesar la respuesta del modelo"],
            "explicacion": raw[:400],
            "recomendacion": "Intenta de nuevo o revisa tu API key."
        }


def llamar_groq(system_prompt, user_text, imagen_base64=None):
    """Llama a Groq con texto o texto+imagen, y devuelve JSON parseado."""
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
                {"type": "text", "text": user_text},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{imagen_base64}"}
                }
            ]
        else:
            model_name = "llama-3.3-70b-versatile"
            content_list = [{"type": "text", "text": user_text}]

        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content_list}
            ],
            response_format={"type": "json_object"}
        )
        raw = response.choices[0].message.content
        return limpiar_json(raw)

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


def mostrar_resultado(resultado):
    if "error" in resultado:
        st.error(resultado["error"])
        st.markdown(f"**Detalles:** {resultado.get('explicacion', '')}")
        st.info(f"💡 **Recomendación:** {resultado.get('recomendacion', '')}")
        return

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


def api_lista():
    return bool(API_KEY)


# =========================================================
# EXTRACCIÓN DE URL (módulo 1 - original)
# =========================================================
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

    usa_firecrawl = any(p in parsed.netloc for p in PLATAFORMAS_STEALTH)

    if usa_firecrawl and firecrawl:
        try:
            st.info(f"🔍 Intentando extraer contenido con Firecrawl de: {parsed.netloc}")
            result = firecrawl.scrape_url(url=url, formats=["markdown"], only_main_content=True)
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

    try:
        if "facebook.com" in parsed.netloc:
            url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "es-ES,es;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
        }

        response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)

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
            partes.append(f"Título alternativo: {og_title.get('content').strip()}")
        if meta_desc and meta_desc.get("content"):
            partes.append(f"Descripción corta: {meta_desc.get('content').strip()}")
        if og_desc and og_desc.get("content"):
            partes.append(f"Descripción detallada: {og_desc.get('content').strip()}")

        if len(partes) < 2:
            for script in soup(["script", "style"]):
                script.decompose()
            texto_cuerpo = soup.get_text(separator=" ", strip=True)
            partes.append(f"Contenido del anuncio:\n{texto_cuerpo[:3000]}")

        return "\n\n".join(partes)

    except Exception as e:
        err_msg = str(e)
        plataforma = "Facebook Marketplace" if "facebook.com" in parsed.netloc else "la plataforma"
        raise Exception(
            f"No se pudo extraer la información del enlace automáticamente ({err_msg}).\n\n"
            f"¿Por qué ocurre esto? {plataforma} utiliza sistemas de seguridad muy estrictos para bloquear el acceso de robots y proteger sus datos.\n\n"
            f"¿Cómo continuar?\n"
            f"1. Copiá y pegá el texto del anuncio en la pestaña 📝 Pegar Texto.\n"
            f"2. O tomá una captura de pantalla del anuncio y subila en la pestaña 📸 Subir Imagen (Captura)."
        )


SYSTEM_PROMPT_ANUNCIO = """Eres un experto en detectar estafas en marketplaces colombianos (Facebook Marketplace, OLX, Mercado Libre).
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
"""


# =========================================================
# PROMPTS — MÓDULOS NUEVOS (conversación / email)
# =========================================================
SYSTEM_PROMPT_CONVERSACION = """Eres un experto en detectar estafas de marketplace en Latinoamérica
(Facebook Marketplace, OLX, Mercado Libre), especialmente el patrón conocido
en Perú y Colombia donde el "comprador":

1. Acepta el precio sin negociar para generar confianza rápida.
2. Convence al vendedor de mover la publicación o el pago a Mercado Libre,
   argumentando "seguridad", aunque el contacto inicial fue en Marketplace.
3. Luego envía un email falso simulando una notificación de pago recibido
   de Mercado Libre, y coordina un "courier" para recoger el producto sin
   que el dinero realmente esté disponible.

Analiza la siguiente conversación y responde SOLO con un JSON válido (sin
markdown, sin texto adicional) con esta estructura:

{
  "riesgo": "ALTO" | "MEDIO" | "BAJO",
  "puntaje": numero entre 0 y 100,
  "senales": ["señal 1", "señal 2", "..."],
  "explicacion": "explicación breve de 2-3 frases sobre el patrón detectado",
  "recomendacion": "qué debe hacer el vendedor AHORA, antes de continuar"
}
"""

SYSTEM_PROMPT_EMAIL = """Eres un experto en detectar phishing y correos de
suplantación de Mercado Libre y plataformas similares en Latinoamérica.

Los correos legítimos de Mercado Libre NUNCA piden "confirmar la entrega"
para "liberar" un pago a través de un link externo, y el dinero de una
venta real queda disponible en la billetera de Mercado Pago dentro de la
app oficial, no por confirmación vía email a un repartidor externo.

Analiza el texto de email proporcionado y responde SOLO con un JSON válido
(sin markdown, sin texto adicional) con esta estructura:

{
  "riesgo": "ALTO" | "MEDIO" | "BAJO",
  "puntaje": numero entre 0 y 100,
  "senales": ["señal 1", "señal 2", "..."],
  "explicacion": "explicación breve de 2-3 frases",
  "recomendacion": "qué debe verificar el usuario directamente en la app oficial antes de entregar nada"
}

Considera señales como:
- Dominio del remitente que no es exactamente mercadolibre.com / mercadopago.com
- Lenguaje de urgencia ("el repartidor llega en X minutos", "confirma ya")
- Pide hacer clic en un link para "liberar" o "confirmar" el pago
- Pide entregar el producto antes de que el dinero esté disponible para retiro
- Errores de gramática, formato o diseño inusual para ser una empresa grande
"""


# =========================================================
# INTERFAZ
# =========================================================
st.title("🛡️ Detector de Estafas - Marketplace")
st.caption(
    "Analiza anuncios, conversaciones, emails de pago y verifica antes de "
    "entregar tu producto. Cubre la estafa de suplantación de Mercado Libre / "
    "couriers falsos, muy común en Perú y Colombia."
)

tab1, tab2, tab3, tab4 = st.tabs([
    "📦 1. Anuncio",
    "💬 2. Conversación",
    "📧 3. Email de pago",
    "✅ 4. Checklist entrega"
])

# ---------------------------------------------------------
# TAB 1 — Anuncio (original: texto, link, imagen)
# ---------------------------------------------------------
with tab1:
    st.subheader("Analiza el anuncio")
    st.write("Pega el texto, un enlace o subí una captura del anuncio que querés revisar.")

    metodo_entrada = st.radio(
        "Seleccioná el método de entrada:",
        ["📝 Pegar Texto", "🔗 Analizar Enlace", "📸 Subir Imagen (Captura)"],
        horizontal=True,
        key="metodo_entrada_tab1"
    )

    texto_analisis = ""
    imagen_base64 = None
    imagen_archivo = None

    if metodo_entrada == "📝 Pegar Texto":
        texto_analisis = st.text_area(
            "Texto del anuncio o conversación:",
            height=200,
            placeholder="Ej: Vendo iPhone 15 nuevo, $1.200.000, solo pago por Nequi, no atiendo llamadas...",
            key="texto_tab1"
        )

    elif metodo_entrada == "🔗 Analizar Enlace":
        enlace_url = st.text_input(
            "Enlace de la publicación:",
            placeholder="https://articulo.mercadolibre.com.co/... o link de Marketplace",
            key="url_tab1"
        )
        st.caption(
            "⚠️ **Nota**: Facebook, Instagram y algunas redes protegen con fuerza sus plataformas contra el rastreo automático. "
            "Si el rastreo falla o lee datos incompletos, te sugerimos copiar el texto del anuncio o subir una captura de pantalla."
        )
        texto_analisis = enlace_url

    else:  # Subir imagen
        imagen_archivo = st.file_uploader(
            "Subí la captura de pantalla de la publicación o del chat:",
            type=["png", "jpg", "jpeg"],
            key="img_tab1"
        )
        texto_analisis = st.text_area(
            "Contexto o detalles adicionales (opcional):",
            placeholder="Ej: El vendedor me pide pago anticipado para reservar el producto...",
            key="contexto_tab1"
        )
        if imagen_archivo:
            imagen_base64 = base64.b64encode(imagen_archivo.read()).decode('utf-8')

    if st.button("🔍 Analizar anuncio", type="primary", key="btn_tab1"):
        if metodo_entrada == "📝 Pegar Texto" and not texto_analisis.strip():
            st.warning("⚠️ Por favor, pegá el texto del anuncio primero.")
        elif metodo_entrada == "🔗 Analizar Enlace" and not texto_analisis.strip():
            st.warning("⚠️ Por favor, ingresá una dirección web (URL) válida.")
        elif metodo_entrada == "📸 Subir Imagen (Captura)" and not imagen_archivo:
            st.warning("⚠️ Por favor, cargá una imagen o captura de pantalla.")
        elif not api_lista():
            st.error("❌ Falta configurar tu API key de Groq. Obtenela gratis en console.groq.com")
        else:
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
                if imagen_base64:
                    user_text = f"Por favor, analizá el anuncio o captura de pantalla provista. Texto o contexto adicional: {texto_para_llm or 'Ninguno.'}"
                else:
                    user_text = f"Anuncio a analizar:\n{texto_para_llm}"

                with st.spinner("🕵️ Analizando patrones y señales con Inteligencia Artificial..."):
                    resultado = llamar_groq(SYSTEM_PROMPT_ANUNCIO, user_text, imagen_base64)

                mostrar_resultado(resultado)


# ---------------------------------------------------------
# TAB 2 — Conversación con el "comprador"
# ---------------------------------------------------------
with tab2:
    st.subheader("Analiza la conversación con el comprador")
    st.write(
        "Pega aquí los mensajes que te ha enviado la persona interesada en tu "
        "producto. El agente busca señales de manipulación típicas (te pide "
        "moverte a otra plataforma, acepta todo sin negociar, genera presión, etc.)"
    )

    conversacion = st.text_area(
        "Mensajes de la conversación",
        height=200,
        placeholder=(
            "Ej: Hola, me interesa tu iPhone, te pago el mismo precio que pides. "
            "Mejor para nuestra seguridad publícalo en Mercado Libre y ahí te compro..."
        ),
        key="conversacion_input"
    )

    if st.button("🔍 Analizar conversación", type="primary", key="btn_conv"):
        if not conversacion.strip():
            st.warning("⚠️ Pega la conversación primero.")
        elif not api_lista():
            st.error("❌ Falta configurar tu API key de Groq.")
        else:
            user_text = f"Conversación a analizar:\n\"\"\"{conversacion}\"\"\""
            with st.spinner("🕵️ Analizando conversación..."):
                resultado = llamar_groq(SYSTEM_PROMPT_CONVERSACION, user_text)
            mostrar_resultado(resultado)


# ---------------------------------------------------------
# TAB 3 — Email de "pago recibido"
# ---------------------------------------------------------
with tab3:
    st.subheader("Analiza el email de 'pago recibido'")
    st.write(
        "Pega el texto completo del correo que recibiste anunciando que tu "
        "venta fue pagada. Si quieres, incluye también el correo del "
        "remitente (ej: notificaciones@mercadolibre-pagos-seguros.com)."
    )

    remitente = st.text_input(
        "Correo del remitente (opcional)",
        placeholder="ej: pagos@mercadolibre-notificacion.net",
        key="remitente_input"
    )

    email_texto = st.text_area(
        "Texto del email",
        height=220,
        placeholder=(
            "Ej: ¡Felicidades! Tu producto fue vendido. El pago de $XXX ya está "
            "siendo procesado y estará disponible cuando confirmes la entrega "
            "al transportista..."
        ),
        key="email_input"
    )

    if st.button("🔍 Analizar email", type="primary", key="btn_email"):
        if not email_texto.strip():
            st.warning("⚠️ Pega el texto del email primero.")
        elif not api_lista():
            st.error("❌ Falta configurar tu API key de Groq.")
        else:
            user_text = (
                f"Remitente del correo: \"{remitente if remitente else 'no proporcionado'}\"\n\n"
                f"Texto del email:\n\"\"\"{email_texto}\"\"\""
            )
            with st.spinner("🕵️ Analizando email..."):
                resultado = llamar_groq(SYSTEM_PROMPT_EMAIL, user_text)
            mostrar_resultado(resultado)


# ---------------------------------------------------------
# TAB 4 — Checklist de entrega segura (sin IA, lógica pura)
# ---------------------------------------------------------
with tab4:
    st.subheader("Checklist antes de entregar el producto")
    st.write(
        "Este es el punto más importante: **NO entregues el producto** hasta "
        "que puedas marcar todas estas casillas con seguridad."
    )

    c1 = st.checkbox(
        "Entré directamente a la app oficial de Mercado Libre / Mercado Pago "
        "(no por un link de email) y confirmé la venta ahí.",
        key="c1"
    )
    c2 = st.checkbox(
        "El dinero aparece como saldo DISPONIBLE para retirar en mi cuenta, "
        "no como 'pago en proceso' o 'pendiente'.",
        key="c2"
    )
    c3 = st.checkbox(
        "El comprador y el método de pago coinciden con los datos que "
        "aparecen en la app oficial (mismo nombre, mismo monto).",
        key="c3"
    )
    c4 = st.checkbox(
        "Si llegó un repartidor o courier, pude verificar su guía/pedido "
        "dentro de la app oficial de Mercado Libre, no solo por WhatsApp o email.",
        key="c4"
    )
    c5 = st.checkbox(
        "No me han pedido 'confirmar' nada por fuera de la app oficial "
        "(ni por email, ni por un link, ni por WhatsApp) para que el pago se libere.",
        key="c5"
    )

    if st.button("🔍 Evaluar checklist", type="primary", key="btn_checklist"):
        respuestas = {
            "Verificó la venta en la app oficial": c1,
            "El dinero está disponible (no pendiente)": c2,
            "Comprador y pago coinciden en la app": c3,
            "Repartidor verificado en la app oficial": c4,
            "No se pidió confirmar nada fuera de la app": c5,
        }

        marcados = sum(respuestas.values())
        total = len(respuestas)

        if marcados == total:
            st.success(
                "✅ Todo verificado en la app oficial. El dinero está realmente "
                "disponible. Es razonable proceder con la entrega."
            )
        else:
            faltantes = [k for k, v in respuestas.items() if not v]
            st.error(
                "🔴 **NO entregues el producto todavía.** "
                f"Faltan {total - marcados} de {total} verificaciones:"
            )
            for f in faltantes:
                st.markdown(f"- ❌ {f}")

            st.info(
                "💡 **Recomendación:** El dinero solo es real cuando aparece "
                "como saldo disponible DENTRO de la app oficial de Mercado "
                "Pago/Mercado Libre, verificado por ti mismo (no por un link "
                "ni un email). Si algo de esto falta, espera antes de entregar "
                "el producto, sin importar cuánta prisa tenga el comprador o "
                "el repartidor."
            )

st.divider()
st.caption("Hecho con Streamlit + Groq API (gratis) · Proyecto para portafolio de IA — PetEvents / Anti-Estafa")
