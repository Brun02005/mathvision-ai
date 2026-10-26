# MathVision AI

[![CI](https://github.com/Brun02005/mathvision-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/Brun02005/mathvision-ai/actions/workflows/ci.yml)

App web que resuelve ejercicios universitarios de matemática y física **paso a paso y en español**. Sacás una foto del ejercicio (o subís un PDF, o escribís el LaTeX), la IA lo lee, detecta el tema y lo resuelve con cálculo simbólico exacto, explicando cada paso como lo haría un profesor y graficando cuando tiene sentido.

## Cómo funciona

```
Imagen / PDF ──► OCR a LaTeX (Gemini Vision · respaldo local pix2tex)
                                   │
                                   ▼
Gráfico (Plotly) ◄── Explicación pedagógica ◄── Motor simbólico (SymPy) ◄── Clasificador de tema
```

La IA solo se usa para **leer** el ejercicio. La resolución es simbólica (SymPy), así que los resultados son exactos y verificables, no generados por un modelo de lenguaje.

## Qué resuelve

| Tema | Ejemplo | Qué explica |
|---|---|---|
| Aritmética | `\frac{3}{4} + \frac{1}{8}` | Común denominador, aproximación decimal |
| Ecuaciones | `x^2 - 5x + 6 = 0` | Tipo de ecuación, discriminante, fórmula resolvente, verificación, soluciones complejas |
| Ecuaciones trigonométricas | `\sin(x) = \frac{1}{2}` | Soluciones principales y solución general periódica |
| Inecuaciones | `x^2 - 4 > 0` | Puntos críticos, análisis de signo, conjunto solución |
| Sistemas de ecuaciones | `2x + 3y = 6; x - y = 1` | Forma matricial, Gauss-Jordan, Rouché–Frobenius |
| Análisis de funciones | `f(x) = x^3 - 3x` | Dominio, raíces, ordenada al origen, extremos relativos |
| Límites | `\lim_{x \to 0} \frac{\sin(x)}{x}` | Indeterminaciones, L'Hôpital, límites laterales |
| Derivadas | `\frac{d}{dx}(x^2 \sin(x))` | Reglas usadas (producto, cociente, cadena), orden superior |
| Integrales | `\int \frac{x^5 + x^4 - 8}{x^3 - 4x} dx` | División de polinomios, fracciones parciales, sustitución, por partes (LIATE), Barrow, impropias |
| Series | `\sum_{n=1}^{\infty} \frac{1}{n^2}` | Condición necesaria, serie p, criterio del cociente, serie geométrica |
| Ecuaciones diferenciales | `y'' + y = 0, y(0) = 1, y'(0) = 0` | Clasificación (separable, lineal, Bernoulli, exacta…), ecuación característica, condiciones iniciales |
| Álgebra lineal | `\begin{pmatrix} 2 & 1 \\ 1 & 2 \end{pmatrix}` | Determinante, rango, inversa, autovalores y autovectores; operaciones `A B`, `A^{-1}`, `A^T`, `\det` |
| Física | `F = m a, m = 10 \text{kg}, a = 5` | Reconoce la ley (Newton, MRUV, energía, Ohm…) y despeja la incógnita |

Además:

- **Modo Profesor / Modo Examen:** solución completa o solo el resultado.
- **Gráficas:** función y derivada, área bajo la curva en integrales definidas, raíces y extremos marcados, familia de soluciones de una EDO.
- **Historial:** búsqueda, detalle de cada ejercicio y borrado.
- **Configuración:** modo por defecto, gráficas, estado del servidor y del OCR.

## Stack

**Backend:** Python 3.13 · FastAPI · SymPy · NumPy/SciPy · OpenCV · Pillow · PyMuPDF · SQLAlchemy (SQLite) · pytest · Ruff
**IA:** Google Gemini Vision (`google-genai`) con pix2tex como respaldo local opcional
**Frontend:** React 19 · Vite · Tailwind · React Router · KaTeX · Plotly
**Infra:** Docker Compose (nginx + uvicorn) · GitHub Actions

## Puesta en marcha

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate              # Windows  (Linux/macOS: source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env             # y completá GEMINI_API_KEY (Linux/macOS: cp)
uvicorn main:app --reload
```

La API queda en `http://localhost:8000` y la documentación interactiva en `http://localhost:8000/docs`.
Sin `GEMINI_API_KEY` funciona todo excepto la lectura de imágenes. Para OCR local sin API: `pip install pix2tex` (descarga ~400 MB).

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
GEMINI_API_KEY=tu_clave docker compose up --build
```

La app queda en `http://localhost:8080`. La base de datos y las imágenes se guardan en el volumen `mathvision-data`.

## Configuración

Variables de entorno del backend (también se leen de `backend/.env`):

| Variable | Por defecto | Descripción |
|---|---|---|
| `GEMINI_API_KEY` | — | Clave de Google AI Studio para el OCR |
| `GEMINI_MODEL` | `gemini-flash-latest` | Modelo de Gemini usado para leer imágenes |
| `DATABASE_URL` | `sqlite:///backend/mathvision.db` | Cualquier URL de SQLAlchemy |
| `UPLOAD_DIR` | `backend/temp` | Carpeta de imágenes subidas |
| `MAX_UPLOAD_MB` | `10` | Tamaño máximo de archivo |
| `CORS_ORIGINS` | — | Orígenes permitidos en producción, separados por coma |

## API

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/solve-text` | Resuelve una expresión LaTeX (`latex_expression`, `mode`) |
| `POST` | `/api/upload` | Resuelve una imagen o PDF (`file`, `mode`) |
| `GET` | `/api/history` | Historial paginado (`skip`, `limit`, `q`) |
| `GET` | `/api/history/{id}` | Ejercicio completo con pasos y gráfica |
| `DELETE` | `/api/history/{id}` | Elimina un ejercicio |
| `DELETE` | `/api/history` | Vacía el historial |
| `GET` | `/api/health` | Estado del servidor y proveedores de OCR |

## Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest          # motores, clasificador y API (el OCR se simula)
ruff check .
```

```bash
cd frontend
npm run lint
npm run build
```

## Estructura

```
backend/
  api/router.py            Endpoints REST
  classifier/              Detección del tema del ejercicio
  engines/math/            Álgebra, cálculo, series, EDO, álgebra lineal
  engines/physics/         Fórmulas físicas con datos
  explanations/            Capa pedagógica (introducción y consejos por tema)
  graphs/generator.py      Datos para Plotly a partir de expresiones SymPy
  ocr/  pdf/               Lectura de imágenes y PDF
  pipeline.py              Orquestación OCR → clasificar → resolver → explicar → graficar
frontend/src/
  pages/                   Resolver, Historial, Detalle, Configuración
  components/              Renderizado de LaTeX, pasos, gráficas, solución
```

## Pendiente

- Autenticación y cuentas de usuario (hoy el historial es compartido por todos los que usan la instancia).
- Límite de tiempo por ejercicio: un cálculo simbólico muy costoso ocupa un worker hasta terminar.
- Problemas de física en lenguaje natural sin pasar por el OCR.
