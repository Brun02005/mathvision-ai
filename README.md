# MathVision AI

> 🚧 Proyecto en desarrollo.

App web que resuelve ejercicios universitarios de matemática **paso a paso y en español**. Sacás una foto del ejercicio (o escribís el LaTeX), la IA lo lee, detecta el tema y lo resuelve con cálculo simbólico, explicando cada paso como lo haría un profesor y graficando la función cuando tiene sentido.

## Cómo funciona

```
Imagen ──► Preprocesamiento (OpenCV) ──► OCR a LaTeX (Gemini Vision · respaldo local pix2tex)
                                                   │
                                                   ▼
        Gráfico (Plotly) ◄── Explicación pedagógica ◄── Motor simbólico (SymPy) ◄── Clasificador de tema
```

- **Modo Profesor:** solución completa con cada paso explicado.
- **Modo Examen:** solo el resultado.
- **Integrales con método explicado:** división de polinomios, fracciones parciales, trigonométricas, exponenciales, regla de la potencia. También derivadas y ecuaciones.
- **Historial:** cada problema resuelto se guarda en la base de datos.

## Stack

**Backend:** Python · FastAPI · SymPy · NumPy/SciPy · OpenCV · Pillow · SQLAlchemy (SQLite) · pytest
**IA:** Google Gemini Vision (imagen → LaTeX) con pix2tex como respaldo local
**Frontend:** React 19 · Vite · Tailwind · React Router · KaTeX · Plotly

## Puesta en marcha

Backend:

```bash
cd backend
python -m venv venv
venv\Scripts\activate            # Windows
pip install -r requirements.txt
set GEMINI_API_KEY=tu_clave      # Windows (cmd)
uvicorn main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## Estado

**Hecho:** API (resolver texto, subir imagen, historial, health), pipeline completo de imagen a solución, solucionadores de integrales, derivadas y ecuaciones, dashboard.

**Pendiente:**
- Páginas de Historial y Configuración en el frontend.
- Conectar el parser de PDF ya implementado.
- Solucionadores dedicados para ecuaciones diferenciales, álgebra lineal, series y física.
- Actualizar el modelo de Gemini y arreglar los tests de motores.
- Autenticación y deploy.
