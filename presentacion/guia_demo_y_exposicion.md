# Guía de demo y exposición — Optimización de Inversión en CDT

Documento de apoyo para la sustentación. Dos partes:
1. **Guía de usuario + casos de prueba** para la demo interactiva.
2. **Guion por diapositiva**: lo más importante a decir en cada slide.

---

## Parte 1 — Guía de usuario y casos de prueba para la demo

### 1.1 Preparación antes de exponer (hacer esto ANTES, no en vivo)

Deja todo encendido y probado minutos antes de la presentación:

1. **Activar el entorno y levantar la API** (desde la raíz del proyecto):
   ```powershell
   .\.venv\Scripts\Activate.ps1
   uvicorn api.app:app --port 8000
   ```
2. **Abrir la documentación interactiva** en el navegador:
   `http://localhost:8000/docs`
   Esta es la mejor pantalla para la demo: permite ejecutar los endpoints con el botón **"Try it out"** sin escribir código.
3. (Opcional, si muestran el front de Lovable) Levantar **ngrok** y confirmar que la URL pública responde. Recuerda el header `ngrok-skip-browser-warning: true` en el front.

> **Plan B si algo falla en vivo:** ten una pestaña con la salida de `python src/main.py` ya ejecutada, o capturas de los resultados. Nunca dependas al 100% de la red en una sustentación.

### 1.2 Qué mostrar y en qué orden (recorrido de la demo, ~3-4 min)

1. **`GET /datos`** — muestra que el modelo carga datos reales: los 5 bancos, los 7 plazos, las reglas de liquidez por fecha y el tope por plazo. Sirve para decir "estos son datos reales, no inventados".
2. **`GET /productos`** — la matriz de combinaciones utilizables con su tasa E.A. y factor `f_ijk`.
3. **`POST /optimizar`** — el corazón de la demo. Ejecuta los casos de abajo.
4. **`POST /simular-liquidez`** (opcional) — barrido automático que muestra el costo de oportunidad a varios niveles de liquidez en una sola llamada.

### 1.3 Casos de prueba (valores verificados con el modelo real)

Todos usan capital `A = 100.000.000` (valor por defecto). Para cada caso se da el **cuerpo JSON** a pegar en `/optimizar` → "Try it out", y el **resultado esperado** para que sepas qué va a salir.

#### CASO A — Escenario base (con liquidez por fecha) ✅ el principal

**Cuerpo:** `{}` (vacío, usa la política por defecto)

**Resultado esperado:** `Estado: Optimal`, `Z* = 15.405.781 COP`, capital 100% colocado.

| Banco | Plazo | Monto | % |
|---|---|---|---|
| Bancolombia | 180 d | $10.000.000 | 10 % |
| Lulo Bank | 180 d | $20.000.000 | 20 % |
| Bancolombia | 360 d | $30.000.000 | 30 % |
| Davivienda | 720 d | $40.000.000 | 40 % |

**Qué decir:** "El capital se reparte entre tres plazos. Cumple exactamente las reglas de liquidez: 30 % vence en ≤180 días, 60 % en ≤360 días, y ningún plazo supera el 40 %."

#### CASO B — Sin exigir liquidez (contraste) 🔑 el más vendible

**Cuerpo:**
```json
{ "liquidez_reglas": [], "concentracion_plazo_max": {} }
```

**Resultado esperado:** `Z* = 24.832.032 COP`, con TODO el capital a 720 días:

| Banco | Plazo | % |
|---|---|---|
| Banco de Bogotá | 720 d | 20 % |
| Bancolombia | 720 d | 40 % |
| Davivienda | 720 d | 40 % |

**Qué decir:** "Al quitar la exigencia de liquidez, el modelo pone todo en el plazo más rentable (720 días) y gana más: $24,8M. La diferencia con el caso base, **$9.426.250**, es el costo de oportunidad de mantener liquidez. Ese número es imposible de estimar 'a ojo'."

#### CASO C — Liquidez agresiva a corto plazo (muestra flexibilidad)

**Cuerpo:**
```json
{
  "liquidez_reglas": [ { "hasta_dias": 90, "min_frac": 0.50 } ],
  "concentracion_plazo_max": 0.40
}
```

**Resultado esperado:** `Z* = 13.282.012 COP`. El modelo mete 50 % en plazos ≤90 días:

| Banco | Plazo | % |
|---|---|---|
| Bancolombia | 60 d | 10 % |
| Bancolombia | 90 d | 30 % |
| Lulo Bank | 90 d | 10 % |
| Lulo Bank | 540 d | 10 % |
| Davivienda | 720 d | 40 % |

**Qué decir:** "Si la tesorería necesita la mitad del dinero disponible en 3 meses, el modelo reacomoda la cartera y el rendimiento baja a $13,3M. A mayor exigencia de liquidez, mayor costo de oportunidad: el modelo lo cuantifica."

#### CASO D — Validación de errores (robustez, opcional)

**Cuerpo:** `{ "liquidez": { "U_corto": 60 } }`

**Resultado esperado:** `HTTP 422` con mensaje claro: *"'U_corto'=60 parece un PORCENTAJE. Use 0.6 para 60%."*

**Qué decir:** "La API valida las entradas: si el usuario confunde porcentaje con fracción, recibe un mensaje accionable en vez de un error técnico."

### 1.4 Secuencia recomendada para la demo

Caso A → Caso B (contraste del costo de oportunidad) → Caso C (flexibilidad). Con esos tres queda demostrada la tesis del proyecto. El Caso D solo si sobra tiempo.

---

## Parte 2 — Guion por diapositiva (lo esencial a decir)

Objetivo: 20 minutos, 15 slides (~1,3 min cada una). Sugerencia de reparto al final.

### Slide 1 — Portada
Presentar el proyecto, los tres autores y el curso. Una frase: "Vamos a mostrar cómo decidir, de forma óptima, en qué CDT invertir un capital para maximizar el rendimiento respetando necesidades reales de liquidez."

### Slide 2 — ¿Cómo invertir? (planteamiento)
Plantear el problema: hay 5 bancos, 7 plazos y 3 tramos → 105 combinaciones (90 utilizables). Hacerlo "a ojo" es subóptimo porque las decisiones interactúan. Aquí engancha el problema.

### Slide 3 — Por qué importa
Contexto del CDT colombiano: renta fija con tasa pactada, protegido por Fogafín, instrumento típico de tesorería. Las tasas cambian por banco y plazo, de ahí la necesidad de optimizar.

### Slide 4 — Metodología: decidir, fijar, interpretar
Explicar la estrategia en 3 pasos: (1) el MILP decide la asignación óptima; (2) se fijan las variables binarias; (3) sobre el LP restringido resultante se hace el análisis dual. **Punto clave:** la dualidad fuerte solo vale para un LP, no para un MILP; por eso se separa.

### Slide 5 — Maximizar el rendimiento efectivo
La función objetivo. **Lo más importante:** por qué se usa `f_ijk = (1+r)^(j/360) − 1` y no la tasa anual plana. Si usáramos la tasa anual, valoraríamos igual un CDT de 30 días y uno de 720 → decisión sesgada. `f_ijk` ajusta la tasa al horizonte real. *(Pregunta probable del jurado; dominarla.)*

### Slide 6 — Diez familias de restricciones
Repaso rápido de las 10 familias. No leerlas todas; destacar que las **familias 9 (liquidez por fecha) y 10 (concentración por plazo)** son el aporte propio del equipo, incorporado tras la retroalimentación de la profesora.

### Slide 7 — Liquidez por fecha + concentración por plazo
Explicar el aporte con palabras simples: "La tesorería puede necesitar dinero disponible en una fecha (ej. a 6 meses) sin amarrar todo al mismo plazo." La liquidez por fecha exige que una fracción venza antes de un umbral; la concentración por plazo evita poner todo en un solo horizonte.

### Slide 8 — Herramientas y datos
Stack: Python, PuLP/CBC, pandas/NumPy, FastAPI. **Énfasis en datos reales:** los 5 bancos con nombre, tasas de la SFC y tarifarios (corte oct–nov 2026), 90 combinaciones reales y 15 excluidas por no ofrecerse. "Cero invención de datos."

### Slide 9 — Resultado: asignación óptima  ← aquí puede ir la DEMO (Caso A)
Mostrar Z* = $15.405.781, capital 100% colocado. El hallazgo: el capital se reparte entre 180, 360 y 720 días, cumpliendo las reglas de liquidez. **Momento ideal para abrir la demo y ejecutar el Caso A en vivo.**

### Slide 10 — Costo de oportunidad de la liquidez  ← DEMO (Caso B)
El resultado más vendible. Sin liquidez: $24,8M (todo a 720 d). Con liquidez: $15,4M. La diferencia **$9.426.250** es lo que "cuesta" mantener disponibilidad. **Ejecutar el Caso B en vivo para mostrar el contraste.**

### Slide 11 — Análisis de sensibilidad
Precios sombra: λ* = 0,1201 (valor marginal del capital). Las restricciones que "mandan" son la liquidez a 180 días (−0,0665) y el tope del plazo de 720 días (+0,1347). Mencionar que la holgura complementaria se verificó: (x*)ᵀs* = 0.

### Slide 12 — Validación rigurosa, limitación honesta
Holgura complementaria verificada (coherencia primal-dual). **Honestidad académica:** con las nuevas restricciones el LP restringido resultó degenerado, así que los precios sombra pueden no ser únicos y se interpretan con prudencia. Mostrar esto suma puntos: demuestra rigor.

### Slide 13 — Contribuciones
Las 5 contribuciones: decisión reproducible, retorno comparable (f_ijk), liquidez explícita, control de concentración, lectura económica vía dualidad. Conectar cada una con lo mostrado.

### Slide 14 — Aprendizajes y trabajo futuro
Aprendizajes del curso aplicados (modelar la tasa al horizonte, separar decisión e interpretación, dualidad). Trabajo futuro: reinversión, incertidumbre en tasas, más escenarios de liquidez.

### Slide 15 — Cierre
Agradecer y abrir preguntas. Si hubo demo, cerrarla aquí.

### Sugerencia de reparto (3 expositores, ~6-7 min c/u)
- **Expositor 1 — Planteamiento:** slides 1, 2, 3, 4.
- **Expositor 2 — Modelo y método:** slides 5, 6, 7, 8.
- **Expositor 3 — Resultados y cierre:** slides 9, 10, 11, 12, 13, 14, 15 (lleva la demo).

> Ajusten el reparto a quién domina cada tema. Lo importante: que quien exponga las slides 5 y 10 sepa defender `f_ijk` y el costo de oportunidad, que son las preguntas más probables.

### Preguntas probables del jurado (prepararlas)
1. **¿Por qué `f_ijk` y no la tasa anual?** → Para comparar plazos distintos; la tasa plana sesga hacia plazos cortos.
2. **¿Por qué el análisis dual es sobre el LP y no el MILP?** → La dualidad fuerte solo está garantizada para problemas lineales; las binarias rompen la convexidad.
3. **¿Los datos son reales?** → Sí, tasas de la SFC y tarifarios por plazo, verificadas. Lo único no desagregado por el mercado es el tramo de monto (prima = 0, documentado).
4. **¿Qué significa el precio sombra negativo de liquidez?** → Que exigir liquidez a corto plazo resta rendimiento; es el costo marginal de esa exigencia.
