# Guía de demo y exposición — Optimización de Inversión en CDT

Documento de apoyo para la sustentación. Dos partes:
1. **Guía de la demo interactiva en la interfaz de Lovable** (pestañas Optimizador y Simulación de Liquidez), con casos de prueba listos.
2. **Guion por diapositiva**: lo más importante a decir en cada slide.

---

## Parte 1 — Demo interactiva en la interfaz web (Lovable)

La aplicación tiene dos pestañas en la parte superior: **Optimizador** y **Simulación de Liquidez**. Verifica que arriba a la derecha diga **"API conectada"** (punto verde) antes de empezar.

> **Importante sobre los porcentajes:** en la interfaz, los valores de liquidez y concentración se escriben en **porcentaje** (ej. `30`, `40`, `60`), no en fracción. La app hace la conversión internamente.

### Preparación antes de exponer (hacerlo ANTES, no en vivo)

1. Levantar la API local y ngrok (o el despliegue que uses) y confirmar que la web muestra **"API conectada"**.
2. Abrir la pestaña **Optimizador** y verificar que el panel superior carga: Capital Base, 90 combinaciones utilizables, 90/0 reales/supuestas, los 5 bancos y las reglas de liquidez vigentes.
3. **Plan B:** ten capturas de los resultados esperados (abajo) por si la red falla en vivo.

---

### PESTAÑA 1 — "Optimizador"

El panel superior muestra el contexto (solo lectura): capital base, combinaciones, bancos/plazos, liquidez por fecha vigente y tope por plazo. El panel izquierdo "Escenario" es donde se configura y se pulsa **Optimizar**; el resultado aparece a la derecha.

#### Caso 1 — Escenario base con liquidez por fecha ✅ (el principal)

**Qué configurar en el panel "Escenario":**
- **Capital (A) en COP:** `100000000` (o dejarlo como está).
- **Limitar concentración por plazo:** ✅ activado → **Máximo (%):** `40`.
- **Liquidez por fecha:** ✅ activado, con dos reglas:
  - Regla 1: umbral **< 180 días**, **Mínimo (%):** `30`, Máximo: vacío.
  - Pulsar **+ Agregar regla** → Regla 2: umbral **< 360 días**, **Mínimo (%):** `60`, Máximo: vacío.
- Pulsar **Optimizar**.

**Resultado esperado:** `Óptimo`, **Z\* = $15.405.781**, 100% del capital colocado, repartido entre tres plazos:

| Banco | Plazo | Monto | % |
|---|---|---|---|
| Bancolombia | 180 d | $10.000.000 | 10 % |
| Lulo Bank | 180 d | $20.000.000 | 20 % |
| Bancolombia | 360 d | $30.000.000 | 30 % |
| Davivienda | 720 d | $40.000.000 | 40 % |

**Qué decir:** "El capital se reparte entre 180, 360 y 720 días. Cumple exactamente las reglas: 30% vence en ≤180 días, 60% en ≤360 días, y ningún plazo supera el 40%. El modelo no amarra todo al mismo plazo."

#### Caso 2 — Sin exigir liquidez (contraste) 🔑 (el más vendible)

**Qué configurar:** partiendo del Caso 1,
- **Desactivar** el checkbox **Liquidez por fecha** (quitar el ✅).
- **Desactivar** el checkbox **Limitar concentración por plazo** (quitar el ✅).
- Capital: `100000000`.
- Pulsar **Optimizar**.

**Resultado esperado:** **Z\* = $24.832.032**, con TODO el capital a 720 días:

| Banco | Plazo | % |
|---|---|---|
| Banco de Bogotá | 720 d | 20 % |
| Bancolombia | 720 d | 40 % |
| Davivienda | 720 d | 40 % |

**Qué decir:** "Al quitar la exigencia de liquidez, el modelo concentra todo en el plazo más rentable (720 días) y rinde $24,8M. La diferencia con el Caso 1, **$9.426.250**, es el costo de oportunidad de mantener liquidez. Ese número es imposible de estimar 'a ojo' y es la contribución central del proyecto."

> **Secuencia recomendada:** ejecutar Caso 1, luego Caso 2, y comparar los dos Z* en voz alta. El contraste $15,4M vs $24,8M es el momento clave de la demo.

---

### PESTAÑA 2 — "Simulación de Liquidez"

Esta pestaña hace un **barrido automático**: resuelve el modelo a varios niveles de exigencia de liquidez a corto plazo de una sola vez, y muestra cómo cae el rendimiento (el costo de oportunidad) a medida que se exige más liquidez. Usa el archivo `escenario_supuesto.csv`.

> **Nota honesta para la exposición:** esta pestaña trabaja sobre un **escenario de tasas supuestas** (no los datos reales del optimizador), por eso sus cifras son distintas y menores. Es un ejemplo ilustrativo del *comportamiento* del costo de oportunidad. Vale la pena aclararlo si alguien pregunta.

#### Caso 3 — Barrido de liquidez

**Qué configurar en el panel "Parámetros":**
- **Capital (COP):** `10000000`.
- **Concentración máxima por banco (%):** `40`.
- Pulsar **Simular liquidez**.

**Resultado esperado:** una tabla/gráfico comparando escenarios de liquidez a corto plazo. Valores de referencia (aprox.):

| Escenario | Rendimiento Z* | Costo de oportunidad |
|---|---|---|
| Libre (sin exigencia) | ≈ $2.247.861 | $0 (referencia) |
| 20 % a corto (≤180 d) | ≈ $1.919.256 | ≈ $328.605 |
| (y así, subiendo la exigencia) | (baja) | (sube) |

**Qué decir:** "A medida que exigimos más capital disponible a corto plazo, el rendimiento baja. Esa pérdida progresiva es el costo de oportunidad de la liquidez, cuantificado para cada nivel. Es la misma idea del Caso 2, pero mostrada como una escalera completa."

---

### Resumen de la demo (3 ejecuciones bastan)

1. **Optimizador — Caso 1** (base con liquidez): el modelo reparte entre plazos.
2. **Optimizador — Caso 2** (sin liquidez): todo a 720 d → aparece el costo de oportunidad de $9,43M.
3. **Simulación de Liquidez — Caso 3** (barrido): el costo de oportunidad como escalera.

Con eso queda demostrado que la app funciona y que el modelo responde a la necesidad de liquidez.

---

## Parte 2 — Guion por diapositiva (lo esencial a decir)

Objetivo: 20 minutos, 15 slides (~1,3 min cada una). Reparto sugerido al final.

### Slide 1 — Portada
Presentar el proyecto, los tres autores y el curso. Frase de apertura: "Vamos a mostrar cómo decidir, de forma óptima, en qué CDT invertir un capital para maximizar el rendimiento respetando necesidades reales de liquidez."

### Slide 2 — ¿Cómo invertir? (planteamiento)
Plantear el problema: 5 bancos × 7 plazos × 3 tramos = 105 combinaciones (90 utilizables). Hacerlo "a ojo" es subóptimo porque las decisiones interactúan. Aquí engancha el problema.

### Slide 3 — Por qué importa
Contexto del CDT colombiano: renta fija con tasa pactada, protegido por Fogafín, instrumento típico de tesorería. Las tasas cambian por banco y plazo, de ahí la necesidad de optimizar.

### Slide 4 — Metodología: decidir, fijar, interpretar
La estrategia en 3 pasos: (1) el MILP decide la asignación óptima; (2) se fijan las binarias; (3) sobre el LP restringido se hace el análisis dual. **Clave:** la dualidad fuerte solo vale para un LP, no para un MILP; por eso se separa.

### Slide 5 — Maximizar el rendimiento efectivo
La función objetivo. **Lo más importante:** por qué se usa `f_ijk = (1+r)^(j/360) − 1` y no la tasa anual plana. Con la tasa plana valoraríamos igual un CDT de 30 días y uno de 720 → decisión sesgada. `f_ijk` ajusta la tasa al horizonte real. *(Pregunta probable del jurado.)*

### Slide 6 — Diez familias de restricciones
Repaso rápido. No leerlas todas; destacar que las **familias 9 (liquidez por fecha) y 10 (concentración por plazo)** son el aporte propio del equipo, tras la retroalimentación de la profesora.

### Slide 7 — Liquidez por fecha + concentración por plazo
Explicar el aporte en simple: "La tesorería puede necesitar dinero disponible en una fecha (ej. a 6 meses) sin amarrar todo al mismo plazo." La liquidez por fecha exige que una fracción venza antes de un umbral; la concentración por plazo evita poner todo en un solo horizonte.

### Slide 8 — Herramientas y datos
Stack: Python, PuLP/CBC, pandas/NumPy, FastAPI. **Énfasis en datos reales:** los 5 bancos con nombre, tasas de la SFC y tarifarios (corte oct–nov 2026), 90 combinaciones reales y 15 excluidas. "Cero invención de datos."

### Slide 9 — Resultado: asignación óptima  ← aquí va la DEMO (Optimizador, Caso 1)
Mostrar Z* = $15.405.781, 100% colocado, reparto entre tres plazos. **Momento ideal para cambiar a la interfaz web y ejecutar el Caso 1 en vivo.**

### Slide 10 — Costo de oportunidad de la liquidez  ← DEMO (Optimizador, Caso 2)
El resultado más vendible. Sin liquidez: $24,8M. Con liquidez: $15,4M. Diferencia **$9.426.250**. **Ejecutar el Caso 2 en vivo y comparar los dos Z* en pantalla.** Si hay tiempo, mostrar la pestaña de Simulación de Liquidez (Caso 3).

### Slide 11 — Análisis de sensibilidad
Precios sombra: λ* = 0,1201 (valor marginal del capital). Restricciones activas: liquidez a 180 días (−0,0665) y tope del plazo de 720 días (+0,1347). Holgura complementaria verificada: (x*)ᵀs* = 0.

### Slide 12 — Validación rigurosa, limitación honesta
Holgura complementaria verificada (coherencia primal-dual). **Honestidad académica:** con las nuevas restricciones el LP restringido resultó degenerado, así que los precios sombra pueden no ser únicos y se interpretan con prudencia. Mostrar esto suma: demuestra rigor.

### Slide 13 — Contribuciones
Las 5 contribuciones: decisión reproducible, retorno comparable (f_ijk), liquidez explícita, control de concentración, lectura económica vía dualidad.

### Slide 14 — Aprendizajes y trabajo futuro
Aprendizajes del curso aplicados. Trabajo futuro: reinversión, incertidumbre en tasas, más escenarios de liquidez.

### Slide 15 — Cierre
Agradecer y abrir preguntas. Si hubo demo, cerrarla aquí.

### Sugerencia de reparto (3 expositores, ~6-7 min c/u)
- **Expositor 1 — Planteamiento:** slides 1, 2, 3, 4.
- **Expositor 2 — Modelo y método:** slides 5, 6, 7, 8.
- **Expositor 3 — Resultados y cierre:** slides 9, 10, 11, 12, 13, 14, 15 (lleva la demo en la interfaz).

> Lo importante: que quien exponga las slides 5 y 10 sepa defender `f_ijk` y el costo de oportunidad, que son las preguntas más probables.

### Preguntas probables del jurado (prepararlas)
1. **¿Por qué `f_ijk` y no la tasa anual?** → Para comparar plazos distintos; la tasa plana sesga hacia plazos cortos.
2. **¿Por qué el análisis dual es sobre el LP y no el MILP?** → La dualidad fuerte solo está garantizada para problemas lineales; las binarias rompen la convexidad.
3. **¿Los datos son reales?** → Sí, tasas de la SFC y tarifarios por plazo, verificadas. Lo único no desagregado por el mercado es el tramo de monto (prima = 0, documentado). *(La pestaña de Simulación de Liquidez usa un escenario supuesto; aclararlo si preguntan.)*
4. **¿Qué significa el precio sombra negativo de liquidez?** → Que exigir liquidez a corto plazo resta rendimiento; es el costo marginal de esa exigencia.
