# Informe de dualidad y análisis de sensibilidad

_Generado: 2026-10-22 00:27:22_

> **ADVERTENCIA (Requisito 4.7).** Todo el análisis de este
> informe —precios sombra, interpretación económica, rangos de
> sensibilidad y holgura complementaria— se refiere al **LP
> restringido** que resulta de fijar las variables binarias en
> su valor óptimo `z = z*`, **NO al MILP original**. En un MILP
> las binarias rompen la convexidad y la dualidad fuerte no está
> definida; los precios sombra y rangos son rigurosos solo sobre
> este LP (binarias fijadas). Interpretar los resultados en ese
> marco.

## 1. Estado del LP restringido

- Estado del solver: `Optimal`
- Óptimo alcanzado: `True`
- Valor objetivo `Z* = Σ f_ijk·x*_ijk`: **24,590,300.00**
- Capital sin colocar `s_0*`: **0.00** (capital agotado: `True`)

## 2. Precios sombra (valores duales)

| Recurso | Símbolo | Precio sombra |
| --- | --- | --- |
| Capital `Σx + s_0 = A` | `λ*` | 0.24322500 |
| Concentración banco Banco de Bogota `≤ p_i·A` | `μ_Banco de Bogota*` | 0.00446400 |
| Concentración banco Davivienda `≤ p_i·A` | `μ_Davivienda*` | -0.00000000 |
| Concentración banco Nu Bank `≤ p_i·A` | `μ_Nu Bank*` | 0.00223100 |

## 3. Interpretación económica (Req. 4.3)

- λ* = 0.24322500: retorno marginal de una unidad adicional de capital A. Es el incremento del objetivo Σ f_ijk·x_ijk por cada peso extra de capital disponible, manteniendo óptima la base del LP restringido.
- μ_Banco de Bogota* = 0.00446400 > 0: el tope de concentración p·A del banco 'Banco de Bogota' está ACTIVO. Es el costo de oportunidad de la diversificación: cuánto rendimiento extra se ganaría si se permitiera colocar un peso más en ese banco.
- μ_Davivienda* ≈ 0: el tope de concentración del banco 'Davivienda' NO está activo (hay holgura); relajarlo no mejoraría el objetivo.
- μ_Nu Bank* = 0.00223100 > 0: el tope de concentración p·A del banco 'Nu Bank' está ACTIVO. Es el costo de oportunidad de la diversificación: cuánto rendimiento extra se ganaría si se permitiera colocar un peso más en ese banco.
- s_0* ≈ 0 (capital agotado): λ* = 0.24322500 revela el valor marginal del capital: cada peso adicional sí se colocaría y produciría ese rendimiento extra.

## 4. Rangos de sensibilidad

**Método.** Rangos por PERTURBACIÓN + re-solución del LP restringido (un parámetro a la vez, ceteris paribus). CBC no expone el ranging exacto del símplex; los extremos son numéricos y dependen del paso de búsqueda. No cubre cambios simultáneos (regla del 100%). Válido solo para el LP restringido con z fijadas en z* (Req. 4.7).

### 4.1 Coeficientes objetivo `f_ijk` (Req. 4.5)

| Combinación (i,j,k) | `f` base | Límite inferior | Límite superior | Baja ≤ | Sube ≤ |
| --- | --- | --- | --- | --- | --- |
| `Banco de Bogota|720|2` | 0.247689 | 0.239433 | +∞ | 0.008256 | +∞ |
| `Davivienda|720|2` | 0.243225 | 0.000000 | 0.251333 | 0.243225 | 0.008107 |
| `Nu Bank|720|2` | 0.245456 | 0.237274 | +∞ | 0.008182 | +∞ |

### 4.2 Lado derecho RHS: capital `A` y topes `p_i·A` (Req. 4.6)

| Recurso | RHS base | Límite inferior | Límite superior | Baja ≤ | Sube ≤ |
| --- | --- | --- | --- | --- | --- |
| `capital_A` | 100,000,000.00 | 90,000,000.00 | 120,000,000.00 | 10,000,000.00 | 20,000,000.00 |
| `concentracion_Banco de Bogota` | 40,000,000.00 | 20,000,000.00 | 50,000,000.00 | 20,000,000.00 | 10,000,000.00 |
| `concentracion_Davivienda` | 40,000,000.00 | 20,000,000.00 | +∞ | 20,000,000.00 | +∞ |
| `concentracion_Nu Bank` | 40,000,000.00 | 20,000,000.00 | 50,000,000.00 | 20,000,000.00 | 10,000,000.00 |

Dentro de cada intervalo la base óptima (y el precio sombra) se mantiene y la variación del objetivo es lineal: `Δobjetivo = π·Δb`.

## 5. Verificación de holgura complementaria (Req. 4.4)

- Condición `(x*)^T s* = 0` verificada: **True**
- Máxima violación: `0.00e+00` (tolerancia `1e-06`)
- Producto global `Σ dj_v·(v−cota)`: `0.00e+00`

Holgura complementaria VERIFICADA: la máxima violación (0.00e+00) está por debajo de la tolerancia (1e-06). El óptimo primal y el dual son coherentes: toda restricción no activa tiene precio sombra nulo y toda variable interior tiene reduced cost nulo. Término más holgado: 'capital_total' (|producto| = 0.00e+00).

Términos más holgados (mayor |producto| primero):

| Tipo | Nombre | Factor A | Factor B | Producto |
| --- | --- | --- | --- | --- |
| restriccion | `capital_total` | -0 | 0.243225 | -0.00e+00 |
| restriccion | `concentracion_Banco_de_Bogota` | -0 | 0.004464 | -0.00e+00 |
| restriccion | `concentracion_Davivienda` | 2e+07 | -0 | -0.00e+00 |
| restriccion | `concentracion_Nu_Bank` | -0 | 0.002231 | -0.00e+00 |
| variable | `x_Banco_de_Bogota_720_2` | 0 | 1e+07 | 0.00e+00 |
| variable | `x_Davivienda_720_2` | 0 | 1e+07 | 0.00e+00 |
| variable | `x_Nu_Bank_720_2` | 0 | 1e+07 | 0.00e+00 |
| variable | `s_0` | -0.243225 | 0 | -0.00e+00 |
