# Incident Response Playbook Generator

Herramienta que, dado un tipo de incidente de seguridad (ransomware, credential leak,
DDoS, phishing, insider threat...) y contexto opcional de la organización, genera un
**playbook de respuesta paso a paso** siguiendo el framework **NIST SP 800-61 Rev. 2**,
con acciones concretas, roles sugeridos y checklist por fase.

> ⚠️ **Aviso**: esta es una herramienta educativa/de apoyo. NO sustituye un plan de
> respuesta a incidentes certificado ni revisado por profesionales, ni constituye
> asesoría legal o de cumplimiento normativo.

## Ejemplo

```bash
python -m app.cli --incident ransomware \
  --context "servidor de ficheros on-prem cifrado, ~50 empleados, sin backups verificados recientes"
```

Genera un playbook en Markdown estructurado en las 4 fases NIST (Preparación → Detección
y Análisis → Contención/Erradicación/Recuperación → Post-incidente), con supuestos
declarados, roles y checklist, y lo guarda en `output/`.

## Instalación

```bash
git clone <este-repo>
cd incident-response-playbook-generator
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # y pon tu GEMINI_API_KEY
```

La API key **nunca va en el código**: vive en `.env` (ignorado por git). Consigue una
gratis en https://aistudio.google.com/apikey.

## Uso

```bash
# Modo interactivo (te pregunta tipo de incidente y contexto)
python -m app.cli

# Modo directo
python -m app.cli -i "credential leak" -c "M365, MFA parcial, credenciales en dump público"

# Solo imprimir, sin guardar en output/
python -m app.cli -i ddos --no-save

# Forzar un proveedor concreto para esta ejecución
python -m app.cli -i ransomware -p ollama
```

## Arquitectura modular de proveedores

El core es **agnóstico del LLM**. Todos los proveedores implementan la misma interfaz:

```python
class LLMProvider(ABC):
    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str: ...
```

| Proveedor | Variable de entorno | SDK necesario |
|---|---|---|
| `gemini` (default) | `GEMINI_API_KEY` | `google-genai` |
| `claude` | `ANTHROPIC_API_KEY` | `anthropic` |
| `openai` | `OPENAI_API_KEY` | `openai` |
| `ollama` (local, gratis) | — | ninguno (API HTTP local) |

Se cambia de proveedor con **una variable de entorno** (`LLM_PROVIDER=claude` en `.env`),
sin tocar el resto del código. Los imports son perezosos: solo necesitas instalar el SDK
del proveedor que uses.

### Añadir un proveedor nuevo

1. Crea `providers/mi_provider.py` con una clase que herede de `LLMProvider` e implemente `generate()`.
2. Regístrala en el diccionario `PROVIDERS` de `providers/__init__.py`.
3. Listo — los prompts y la CLI no cambian.

## Estructura

```
├── prompts/
│   ├── system_prompt.md       # instrucciones fijas + estructura NIST + reglas anti-alucinación
│   └── few_shot_examples.md   # 3 playbooks de ejemplo (ransomware, credential leak, DDoS)
├── providers/                 # capa modular de LLMs
│   ├── __init__.py            # factoría get_provider() + registro PROVIDERS
│   ├── base.py                # interfaz LLMProvider (clase abstracta)
│   ├── gemini_provider.py     # default (capa gratuita)
│   ├── claude_provider.py
│   ├── openai_provider.py
│   └── ollama_provider.py     # local/offline
├── retrieval/                 # RAG opcional
│   ├── ingest.py              # descarga fuentes, trocea y vectoriza (Chroma)
│   └── search.py              # búsqueda semántica + formateo de referencias
├── reference/                 # fuentes descargadas + índice vectorial (no va a git)
├── generation/
│   └── generate_playbook.py   # arma el prompt final y llama al provider activo
├── app/
│   └── cli.py
├── output/                    # playbooks generados (.md)
└── tests/
    └── test_generation.py     # sin llamadas a APIs reales
```

## Control de alucinaciones

El system prompt obliga al modelo a:
- Citar la fase NIST exacta de cada acción (ej. §3.3.1).
- Declarar explícitamente los supuestos cuando falta contexto, en vez de inventar datos.
- No inventar herramientas propietarias — solo categorías estándar (EDR, SIEM, WAF...).
- Derivar temas legales/regulatorios a "consultar con asesoría legal".

## Modo RAG: grounding con fuentes públicas reales

Con `--rag`, cada playbook se genera con **referencias reales recuperadas de un índice
vectorial local**, y el modelo solo puede citar IDs que existan en lo recuperado —
cada cita del output (`[RA2301]`, `[IR-4]`, `[800-61 p.35]`) es verificable contra la fuente.

Fuentes indexadas (todas públicas y gratuitas):

| Fuente | Formato | Qué aporta |
|---|---|---|
| [RE&CT](https://atc-project.github.io/atc-react/) | JSON estructurado | 216 acciones de respuesta a incidentes con ID `RA####`, organizadas en 6 etapas |
| [NIST SP 800-53 r5](https://github.com/usnistgov/oscal-content) (OSCAL) | JSON estructurado | Controles de las familias IR (Incident Response) y CP (Contingency Planning) |
| [NIST SP 800-61 r2](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-61r2.pdf) | PDF (troceado por página) | El framework de fases en el que se estructura el playbook |

Pipeline: `retrieval/ingest.py` descarga las fuentes → las trocea en chunks con metadata
(ID citable, etapa, fuente, URL) → las vectoriza con `sentence-transformers` (modelo
multilingüe local, gratis) → las indexa en Chroma. En generación, se recuperan los
top-k chunks relevantes al incidente+contexto y se inyectan en el prompt con reglas
de cita estrictas.

```bash
# 1. Construir el índice (una sola vez; descarga fuentes + modelo de embeddings)
python -m retrieval.ingest

# 2. Generar con grounding
python -m app.cli -i ransomware -c "on-prem, sin backups" --rag
```

RAG *reduce* la alucinación, no la elimina: su valor real es que hace el output
**auditable** — cualquier ID citado se puede comprobar contra la fuente original.

## Tests

```bash
pytest
```

Los tests validan el ensamblado de prompts, la factoría de proveedores y el guardado,
usando un provider falso — no consumen API.

## Referencias

- [NIST SP 800-61 Rev. 2 — Computer Security Incident Handling Guide](https://csrc.nist.gov/pubs/sp/800/61/r2/final)
- [SANS Incident Handler's Handbook (PICERL)](https://www.sans.org/white-papers/33901/)
- [CISA #StopRansomware Guide](https://www.cisa.gov/stopransomware/ransomware-guide)

## Nota sobre consistencia entre proveedores

El proyecto se ha probado principalmente con **Gemini**. Cada LLM responde distinto al
mismo prompt (formato, longitud, tendencia a alucinar), así que el output puede variar
ligeramente con otros proveedores.
