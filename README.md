# MathVision AI

[![CI](https://github.com/Brun02005/mathvision-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/Brun02005/mathvision-ai/actions/workflows/ci.yml)

App web que resuelve ejercicios de matemática y física **paso a paso y en español**. El ejercicio puede llegar de cualquier forma: una foto (aunque esté torcida o escrita a mano), un PDF, LaTeX, texto común ("x al cuadrado menos 4 igual a 0") o el enunciado completo de un problema. La app explica cada paso como lo haría un profesor y grafica cuando tiene sentido.

## Cómo funciona

```
Foto / PDF ──► OCR (Gemini Vision) ──┐
Texto, LaTeX, enunciado ─────────────┴──► 1. Motor exacto (SymPy) ── resuelve y verifica
                                                │ no pudo
                                                ▼
                                          2. La IA traduce el ejercicio a notación matemática
                                             → el motor exacto lo resuelve y lo verifica
                                                │ no pudo
                                                ▼
                                          3. La IA lo resuelve (etiquetado, sin sello de verificado)
```

Los tres niveles se prueban **siempre en este orden**, y la respuesta dice cuál resolvió (`method`):

| Nivel | Cuándo | Qué ve el usuario |
|---|---|---|
| `symbolic` | El motor entiende el ejercicio tal como llegó, incluido texto simple como "raíz cuadrada de 16 más 2" | Resultado exacto, con sello **Verificado** cuando la comprobación pasa |
| `interpreted` | Enunciados en palabras, notación rara, errores de OCR. La IA **solo traduce**, no resuelve | Marca "Interpretado con IA", cómo se entendió el ejercicio, y el resultado exacto y verificado del motor |
| `ai` | Lo que el motor no cubre (probabilidad con enunciado, geometría, demostraciones…) | Aviso "Resuelto con IA, revisá el resultado". **Nunca** lleva el sello de verificado |

La IA nunca calcula lo que el motor puede calcular: un modelo de lenguaje puede equivocarse con total seguridad, y SymPy no. Lo que devuelve la IA se trata como dato no confiable: se valida el formato y el tamaño, y se muestra como texto escapado y KaTeX sin `trust`. Las traducciones y soluciones que salen bien se guardan en caché, porque el mismo ejercicio se pide muchas veces y cada llamada cuesta.

Sin `GEMINI_API_KEY`, la app funciona igual con el nivel 1. Los enunciados en palabras se rechazan con un mensaje claro, nunca con una respuesta inventada.

Cada ejercicio se resuelve en un **proceso aparte con límite de tiempo** (`solver_pool.py`). Si un cálculo se pasa del límite, se mata ese proceso y se lo reemplaza, y el usuario recibe un mensaje claro en vez de dejar el servidor trabado. Si todos los procesos están ocupados, la API responde `503` en lugar de acumular pedidos sin límite. Cuando SymPy no logra resolver algo, la respuesta dice "No se pudo resolver", nunca "Sin solución".

### Resultados verificados

Antes de mostrar un resultado, el motor lo comprueba por un camino independiente del que usó para calcularlo:

| Qué | Cómo se verifica |
|---|---|
| Ecuaciones y sistemas | Se sustituye cada solución en la ecuación **original** con aritmética de 30 dígitos. Las que no la cumplen (raíz o logaritmo de un negativo, división por cero) se descartan y se explica por qué |
| Inecuaciones | Se prueban puntos dentro y fuera del conjunto solución, incluidos los bordes |
| Integrales indefinidas | Se deriva la primitiva y se compara con el integrando |
| Integrales definidas | Se compara con integración numérica |
| Límites | Se evalúa la función cada vez más cerca del punto. Si los números contradicen el resultado simbólico, no se muestra |
| Ecuaciones diferenciales | Se sustituye la solución en la ecuación y en las condiciones iniciales |
| Simplificar, factorizar, desarrollar, Taylor | Se comprueba que el resultado sea equivalente a la expresión original |

Cuando la verificación pasa, la web muestra el sello **Verificado**.

## Qué resuelve

Se puede elegir la operación en la web, pasar `operation` a la API o escribirla delante del ejercicio (`factorizar x^3 - 8`, `media de 2, 4, 6`). En modo **Automático** se deduce de la forma de la expresión.

| Tema | Ejemplo | Qué explica |
|---|---|---|
| Aritmética | `\frac{3}{4} + \frac{1}{8}` · `15\% de 200` · `\sqrt[3]{-27}` | Común denominador, porcentajes, potencias, raíces, logaritmos, combinatoria |
| Números complejos | `(2 + 3i)(1 - i)` | Forma binómica, módulo, argumento, forma polar, conjugado |
| Simplificar / factorizar / desarrollar | `factorizar x^3 - 8` · `desarrollar (x+2)^3` | Factor común, productos notables, Ruffini, binomio de Newton, restricciones de dominio |
| Factorización en primos | `factorizar 360` | Tabla de divisiones sucesivas |
| Fracciones parciales | `fracciones parciales \frac{3x+5}{x^2+3x+2}` | Factorización del denominador y coeficientes |
| Ecuaciones | `\log_{2}(x) + \log_{2}(x-2) = 3` · `\|2x-3\| = 5` | Tipo de ecuación, discriminante, descarte de soluciones fuera del dominio, soluciones complejas |
| Ecuaciones trigonométricas | `\tan(x) = 1` | Soluciones en [0, 2π) y solución general periódica |
| Inecuaciones | `\frac{x - 1}{x + 2} \geq 0` | Puntos críticos, análisis de signo, conjunto solución |
| Sistemas de ecuaciones | `2x + 3y = 6; x - y = 1` | Forma matricial, Gauss-Jordan, Rouché–Frobenius, sistemas no lineales |
| Análisis de funciones | `f(x) = x^3 - 3x` | Dominio, raíces, ordenada al origen, extremos relativos |
| Límites | `\lim_{x \to 0} \frac{\sin(x)}{x}` | Indeterminaciones, L'Hôpital, límites laterales |
| Derivadas | `\frac{d}{dx}(x^2 \sin(x))` · `x^2 + y^2 = 25, \frac{dy}{dx}` | Reglas usadas, orden superior, derivadas parciales e implícitas |
| Integrales | `\int x e^{x} dx` · `\int_{0}^{1}\int_{0}^{2} x y \, dy \, dx` | Fracciones parciales, sustitución, por partes (LIATE), Barrow, impropias, integrales dobles y triples |
| Series y Taylor | `\sum_{n=1}^{\infty} \frac{1}{n^2}` · `\text{Taylor de } e^{x} \text{ en } x = 0 \text{ orden } 4` | Criterios de convergencia, sumas finitas, polinomio de Taylor y Maclaurin |
| Ecuaciones diferenciales | `y'' + y = 0, y(0) = 1, y'(0) = 0` | Clasificación (separable, lineal, Bernoulli, exacta…), ecuación característica, condiciones iniciales |
| Álgebra lineal | `\begin{pmatrix} 2 & 1 \\ 1 & 2 \end{pmatrix}` | Determinante, rango, inversa, autovalores y autovectores; operaciones `A B`, `A^{-1}`, `A^T`, `\det` |
| Vectores | `(1, 2, 3) \times (4, 5, 6)` | Producto escalar y vectorial, módulo, versor, ángulo |
| Estadística | `media de 2, 4, 4, 4, 5, 5, 7, 9` | Media, mediana, moda, rango, varianza y desvío (poblacional y muestral) |
| Física | `F = m a, m = 10 \text{kg}, a = 5` | Reconoce la ley (Newton, MRUV, energía, Ohm…) y despeja la incógnita |

Convenciones: `\log` sin base es logaritmo decimal y `\ln` es natural; `i` es la unidad imaginaria (salvo como índice de una sumatoria); las raíces impares de negativos son reales; en las estadísticas, si los números llevan coma decimal, se separan con `;`.

**Precisión medida:** 658 de 658 ejercicios del banco (ver [Banco de ejercicios](#banco-de-ejercicios)). Que el banco esté completo no significa que el motor no falle: significa que no falla en los casos que conocemos.

**Limitaciones:**
- Sin `GEMINI_API_KEY`, los problemas escritos en palabras se rechazan con un mensaje, en vez de inventar una respuesta.
- Las respuestas del nivel `ai` no están verificadas: por eso se etiquetan.

Además:

- **Modo Profesor / Modo Examen:** solución completa o solo el resultado.
- **Gráficas:** función y derivada, área bajo la curva en integrales definidas, raíces y extremos marcados, familia de soluciones de una EDO.
- **Historial:** búsqueda, detalle de cada ejercicio y borrado.
- **Configuración:** modo por defecto, gráficas, estado del servidor y del OCR.

## Stack

**Backend:** Python 3.13 · FastAPI · SymPy · NumPy/SciPy · OpenCV · Pillow · PyMuPDF · SQLAlchemy + Alembic (Postgres en producción, SQLite en desarrollo) · pytest · Ruff
**IA:** Google Gemini (`google-genai`) para OCR y asistente; pix2tex como respaldo local opcional
**Cuentas y cobros:** Supabase Auth (email y Google) · Mercado Pago (suscripción mensual)
**Frontend:** React 19 · Vite · Tailwind · React Router · KaTeX · Plotly · supabase-js
**Infra:** Docker Compose (nginx + uvicorn) · GitHub Actions

## Puesta en marcha

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate              # Windows  (Linux/macOS: source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env             # trae ENV=development; completá GEMINI_API_KEY (Linux/macOS: cp)
uvicorn main:app --reload
```

La API queda en `http://localhost:8000` y la documentación interactiva en `http://localhost:8000/docs`.
Sin `GEMINI_API_KEY` funciona todo excepto la lectura de imágenes y el asistente de IA. Para OCR local sin API: `pip install pix2tex` (descarga ~400 MB).
Con `ENV=development` y sin `SUPABASE_URL`, corre en modo local sin login, con un único usuario. **Sin `ENV=development` se comporta como producción** y no arranca si falta configuración (falla cerrado a propósito).

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Abrí `http://localhost:5173`. Vite redirige `/api` al backend, así que no hace falta configurar CORS en desarrollo.
Para apuntar a otro backend: `VITE_API_URL=https://mi-api.com/api npm run build`.

### Con Docker

```bash
ENV=development GEMINI_API_KEY=tu_clave docker compose up --build   # prueba local
```

La app queda en `http://localhost:8080`. Sin `ENV=development`, Docker arranca en modo producción y exige Supabase, Postgres, CORS y Mercado Pago configurados.

## Cuentas, planes y suscripción

| | Gratis | Pro (mensual) |
|---|---|---|
| Ejercicios por día | 15 | 500 (uso justo) |
| Ejercicios con IA por día (enunciados, fotos difíciles) | 3 | 100 |

Los valores se configuran con variables de entorno (ver `backend/.env.example`). Los ejercicios que no se pudieron resolver no se cuentan, y el costo en tokens de IA de cada usuario queda registrado por día (`daily_usage`).

Cómo está armado:
- **Login:** con Supabase Auth. El backend nunca ve contraseñas: valida el token firmado (JWT) contra las claves públicas del proyecto y rechaza tokens vencidos, de otro proyecto o firmados con un secreto compartido.
- **Historial:** cada usuario ve, borra y vacía solo lo suyo. Un ejercicio ajeno responde `404`, no `403`, para no confirmar que el id existe.
- **Cupos:** se reservan con un `UPDATE ... WHERE usados < límite` atómico. Dos pedidos simultáneos con un solo ejercicio disponible no pueden pasar los dos.
- **Pro como fecha de vencimiento:** Pro es una fecha (`pro_until`), no un interruptor. Cada pago **aprobado** lo extiende un mes desde la fecha del cobro. Si una renovación no llega, el plan vence solo.
- **Webhook de Mercado Pago:** se valida la firma HMAC y después se consulta el estado real a la API de Mercado Pago, sin usar el contenido del aviso. Procesar dos veces el mismo pago da el mismo resultado.
- **Sin configurar:** con `ENV=development` y sin `SUPABASE_URL`, la app corre en **modo local** con un único usuario, sin login. Cualquier otro valor de `ENV` (o ninguno) es producción: el servidor **no arranca** si falta Supabase, Postgres, CORS o el secreto del webhook.
- **Registro de pagos:** cada cobro queda en la tabla `payments`, y `pro_until` es el máximo entre los pagos aprobados. Un reintegro o un contracargo (aviso `payment`) le quita al pago su estado de aprobado y el Pro se recalcula solo.
- **Una sola suscripción:** si ya hay una activa no se crea otra; si hay una a medio pagar se reutiliza su link. Si igual aparecen dos, se cancela la vieja.

## Seguridad y privacidad

Revisado con un análisis independiente; cada punto tiene tests en `tests/test_security.py` y `tests/test_accounts.py`.

| Riesgo | Protección |
|---|---|
| Ejecución de código vía `parse_expr` de SymPy (usa `eval`) | `safe_parse_expr`: alfabeto cerrado (sin `_`, comillas, corchetes ni `:`), sin acceso a atributos, `eval` sin builtins de Python. Los procesos de cálculo arrancan sin ninguna clave en su entorno |
| Configuración insegura en producción | Falla cerrado: sin `ENV=development` el servidor exige Supabase, Postgres, CORS y el secreto del webhook |
| Abuso de cómputo y de la API paga | Cupo diario, límite por minuto por usuario, límite por IP en nginx, y los intentos fallidos caros (timeout, llamadas a Gemini) cuentan |
| Imágenes y PDF "bomba" | Se verifica el tamaño declarado antes de decodificar; las páginas de PDF tienen un tope de píxeles |
| Doble cobro, Pro sin pagar o después de un reintegro | Una suscripción por usuario, Pro derivado de pagos aprobados, reintegros y contracargos lo quitan |
| Navegador | CSP estricta (solo scripts propios y Supabase), `nosniff`, `frame-ancestors 'none'`, sin fuentes ni recursos de terceros |
| Datos personales | Las fotos se borran después de leerlas; los logs no guardan el texto de los ejercicios; borrado de cuenta completo desde "Mi cuenta"; cada respuesta lleva `X-Request-ID` para rastrear un reclamo |

### Legales (Argentina)

- **Botón de arrepentimiento** (`/arrepentimiento`): público, sin login, devuelve un código de seguimiento al instante. Las solicitudes quedan en la tabla `revocation_requests` y en el log (`Withdrawal request ARR-…`). Hay que procesarlas a mano: reintegrar el pago en Mercado Pago, que a su vez quita el Pro automáticamente. La norma pide responder dentro de 24 horas.
- **Botón de baja:** "Mi cuenta", sección de suscripción.
- **Términos y Privacidad** (`/terminos`, `/privacidad`): son **borradores** y muestran un aviso hasta configurar `VITE_LEGAL_REVIEWED=true`. Completá los datos de la empresa (`VITE_LEGAL_*` en `frontend/.env.example`) y hacelos revisar por un abogado antes de cobrar.
- Al registrarse se declara la mayoría de edad y se aceptan los términos; la fecha queda en el perfil de Supabase.

### Antes de abrir al público

- Configurar todo lo de [Puesta en producción](#puesta-en-producción), incluida `SUPABASE_SERVICE_ROLE_KEY` (sin ella, el servidor no arranca en producción: el borrado de cuenta la necesita).
- Probar el ciclo de cobro completo en el sandbox de Mercado Pago, incluido un reintegro (tiene que quitar el Pro).
- **HSTS:** activarlo en lo que termine TLS (la plataforma de hosting o el balanceador).
- **Arrepentimiento:** el formulario no verifica que el email sea del titular. Antes de reintegrar, confirmá la solicitud respondiendo al email de la cuenta.
- **CDN o proxy delante de nginx:** si lo agregás, nginx tiene que tomar la IP real del cliente (`real_ip_header`); si no, todos los usuarios compartirían el mismo límite por IP.
- **API en otro dominio** (`VITE_API_URL`): sumalo a `connect-src` de la CSP en `frontend/nginx.conf`.
- **Límite de memoria por proceso de cálculo (Linux):** no está activado. El aislamiento por procesos ya evita que un archivo hostil tire el servidor, pero un límite explícito (`RLIMIT_AS`, o el límite de memoria del contenedor) suma una barrera. Hay que probarlo con NumPy antes de activarlo.

### Puesta en producción

**1. Supabase** ([supabase.com](https://supabase.com)):
1. Creá un proyecto.
2. En **Authentication > Sign In / Providers**, activá Email (con confirmación) y Google. Google necesita un OAuth Client de Google Cloud.
3. En **Authentication > URL Configuration**, poné la URL pública de la app como *Site URL* y en *Redirect URLs*.
4. En **Project Settings > JWT Keys**, usá **claves de firma asimétricas** (ECC/RSA). El backend valida contra las claves públicas (JWKS) y rechaza el secreto compartido HS256.
5. En el backend: `SUPABASE_URL`, y `DATABASE_URL` con el connection string de Postgres (botón **Connect**, *Session pooler*, con el prefijo `postgresql+psycopg://`). Las tablas se crean solas al arrancar (migraciones de Alembic).
6. En el frontend: `VITE_SUPABASE_URL` y `VITE_SUPABASE_ANON_KEY` (la *publishable key*). **Nunca** la `service_role`.

**2. Mercado Pago** ([Tus integraciones](https://www.mercadopago.com.ar/developers/panel/app)):
1. Creá una aplicación y copiá el **Access Token de prueba** en `MP_ACCESS_TOKEN`.
2. En **Webhooks**, configurá la URL `https://TU-BACKEND/api/billing/webhook`, con los eventos de **suscripciones** (vinculación y pagos autorizados). Copiá la clave secreta en `MP_WEBHOOK_SECRET`.
3. Definí `FRONTEND_URL` (adonde vuelve el usuario después de pagar) y `PRO_PRICE_ARS`.
4. **Probá el ciclo completo con usuarios y tarjetas de prueba** antes de usar las credenciales productivas: suscribirse, recibir el aviso, ver el plan Pro y cancelar.

**3. Producción:** `ENV=production`, `CORS_ORIGINS` con tu dominio y la facturación de Gemini activada (ver [Gemini API — Pricing](https://ai.google.dev/gemini-api/docs/pricing)).

> **Edad mínima:** los términos de la API de Gemini exigen usuarios mayores de 18 años y no permiten apps dirigidas a menores ([Gemini API Additional Terms](https://ai.google.dev/gemini-api/terms)). El público y los términos del servicio tienen que reflejarlo.

## Configuración

Variables de entorno del backend (también se leen de `backend/.env`; la lista completa, con cuentas, planes y cobros, está en `backend/.env.example`):

| Variable | Por defecto | Descripción |
|---|---|---|
| `GEMINI_API_KEY` | — | Clave de Google AI Studio. Activa el OCR de fotos y el asistente de IA (niveles 2 y 3) |
| `GEMINI_MODEL` | `gemini-flash-latest` | Modelo de Gemini usado para leer imágenes |
| `DATABASE_URL` | `sqlite:///backend/mathvision.db` | Cualquier URL de SQLAlchemy |
| `UPLOAD_DIR` | `backend/temp` | Carpeta de imágenes subidas |
| `MAX_UPLOAD_MB` | `10` | Tamaño máximo de archivo |
| `CORS_ORIGINS` | — | Orígenes permitidos en producción, separados por coma |
| `SOLVER_WORKERS` | `2` | Ejercicios resueltos en paralelo (procesos). `0` desactiva el aislamiento, solo para depurar |
| `SOLVE_TIMEOUT_SECONDS` | `20` | Tiempo máximo por ejercicio |
| `SOLVER_QUEUE_TIMEOUT` | `15` | Espera máxima por un proceso libre antes de responder `503` |

## API

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/solve-text` | Resuelve una expresión LaTeX (`latex_expression`, `mode`, `operation`) |
| `POST` | `/api/upload` | Resuelve una imagen o PDF (`file`, `mode`, `operation`) |
| `GET` | `/api/history` | Historial paginado del usuario (`skip`, `limit`, `q`) |
| `GET` | `/api/history/{id}` | Ejercicio completo con pasos y gráfica |
| `DELETE` | `/api/history/{id}` | Elimina un ejercicio |
| `DELETE` | `/api/history` | Vacía el historial del usuario |
| `GET` | `/api/me` | Cuenta, plan, vencimiento de Pro y uso del día |
| `POST` | `/api/billing/subscribe` | Crea la suscripción y devuelve la URL de pago de Mercado Pago |
| `POST` | `/api/billing/cancel` | Cancela la suscripción (lo pagado se mantiene hasta su vencimiento) |
| `POST` | `/api/billing/webhook` | Avisos de Mercado Pago (público, con firma) |
| `GET` | `/api/health` | Estado del servidor, OCR y asistente de IA (público) |

Todas las rutas, salvo `/health` y el webhook, requieren `Authorization: Bearer <token de Supabase>`. Si se supera el límite diario, la respuesta es `429` con `detail.code = "daily_limit"`.

## Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest              # motores, clasificador, API y banco de ejercicios (el OCR se simula)
python -m benchmark # precisión por tema del motor exacto
python -m benchmark --ai  # enunciados y texto libre con la IA (necesita GEMINI_API_KEY; cada corrida consume API)
ruff check .
```

### Banco de ejercicios

Son 658 ejercicios con su respuesta correcta, **escrita a mano a partir de la matemática y no copiada de lo que devuelve el motor**. Están en dos archivos:
- `cases.py`: 217 casos escritos junto con el motor, incluidas las regresiones de cada error encontrado.
- `cases_independent.py`: 421 casos escritos por un revisor que no vio ni el código ni el otro archivo, pensados para encontrar errores (raíces que no verifican, indeterminaciones, notación escrita como la tipea un estudiante).

Cada respuesta se compara matemáticamente, no como texto: `x = 1/2` y `x = 0.5` son la misma; dos primitivas que difieren en una constante también. Corre en cada push como parte de `pytest`, y el CI publica la tabla de precisión por tema.

Reglas para sumar casos:
- Si el motor da una respuesta incorrecta y no se puede arreglar en el momento, el caso se queda y se marca con `xfail="motivo"`. Así la limitación queda a la vista en vez de esconderse.
- Cuando una limitación se arregla, el test falla hasta que se le quita la marca, para que la lista de limitaciones nunca quede desactualizada.
- Los casos `kind="rejected"` exigen que el motor diga que no pudo resolverlos: nunca debe inventar una respuesta.

```bash
cd frontend
npm run lint
npm run build
```

## Estructura

```
backend/
  api/router.py            Endpoints de ejercicios e historial
  api/account.py           Cuenta, suscripción y webhook de Mercado Pago
  auth.py                  Validación de tokens de Supabase
  billing/                 Límites diarios y costo de IA (usage.py), Mercado Pago (mercadopago.py)
  api/legal.py             Botón de arrepentimiento
  ratelimit.py             Límite de pedidos por IP o usuario (en memoria)
  migrations/              Migraciones de Alembic (se aplican solas al arrancar)
  benchmark/               Banco de ejercicios con respuestas esperadas y comparación matemática
  classifier/              Operación pedida (intent.py) y tema del ejercicio (domain_router.py)
  engines/math/            Álgebra, transformaciones, cálculo, series, EDO, álgebra lineal, vectores, estadística
  engines/physics/         Fórmulas físicas con datos
  explanations/            Capa pedagógica (introducción y consejos por tema)
  interpreter/             Texto común a notación matemática (natural.py) y asistente de IA (llm.py)
  graphs/generator.py      Datos para Plotly a partir de expresiones SymPy
  ocr/  pdf/               Lectura de imágenes y PDF
  pipeline.py              Orquestación OCR → clasificar → resolver → explicar → graficar
  solver_pool.py           Procesos de cálculo con límite de tiempo y control de concurrencia
frontend/src/
  pages/                   Resolver, Historial, Detalle, Mi cuenta, Login, Configuración
  context/AuthContext.jsx  Sesión de Supabase (modo local si no está configurado)
  components/              Renderizado de LaTeX, pasos, gráficas, solución
```

## Pendiente

- Revisión legal de Términos y Privacidad, y datos de la empresa.
- Avisos por email (solicitud de arrepentimiento recibida, pago rechazado, suscripción por vencer). Hoy las solicitudes de arrepentimiento se ven en el log y en la tabla `revocation_requests`.
- Panel interno de métricas: usuarios activos, conversión a Pro y costo de IA por usuario (los datos ya se guardan en `daily_usage`).
- Con más de un servidor: mover los límites por minuto (hoy en memoria) a un almacenamiento compartido como Redis.
