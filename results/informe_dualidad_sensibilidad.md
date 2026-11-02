# Informe de dualidad y análisis de sensibilidad

_Generado: 2026-11-02 17:49:44_

> **ADVERTENCIA (Requisito 4.7).** Todo el análisis de este
> informe —precios sombra, interpretación económica, rangos de
> sensibilidad y holgura complementaria— se refiere al **LP
> restringido** que resulta de fijar las variables binarias en
> su valor óptimo `z = z*`, **NO al MILP original**. En un MILP
> las binarias rompen la convexidad y la dualidad fuerte no está
> definida; los precios sombra y rangos son rigurosos solo sobre
> este LP (binarias fijadas). Interpretar los resultados en ese
> marco.

> **DEGENERACIÓN.** ADVERTENCIA: el LP restringido es DEGENERADO (alguna variable básica pegada a su cota o restricción activa con dual nulo). Los rangos de sensibilidad pueden NO ser únicos y el precio sombra puede no ser una derivada bien definida; interpretar con cautela (design.md).

## 1. Estado del LP restringido

- Estado del solver: `Optimal`
- Óptimo alcanzado: `True`
- Valor objetivo `Z* = Σ f_ijk·x*_ijk`: **15,405,781.00**
- Capital sin colocar `s_0*`: **0.00** (capital agotado: `True`)

## 2. Precios sombra (valores duales)

| Recurso | Símbolo | Precio sombra |
| --- | --- | --- |
| Capital `Σx + s_0 = A` | `λ*` | 0.12010000 |
| Concentración banco Bancolombia `≤ p_i·A` | `μ_Bancolombia*` | -0.00000000 |
| Concentración banco Davivienda `≤ p_i·A` | `μ_Davivienda*` | -0.00000000 |
| Concentración banco Lulo Bank `≤ p_i·A` | `μ_Lulo Bank*` | -0.00000000 |
| Liquidez `liquidez_hasta_180_inf` | `σ_liquidez_hasta_180_inf*` | -0.06653463 |
| Liquidez `liquidez_hasta_360_inf` | `σ_liquidez_hasta_360_inf*` | -0.00000000 |
| Liquidez `plazo_max_180` | `σ_plazo_max_180*` | -0.00000000 |
| Liquidez `plazo_max_360` | `σ_plazo_max_360*` | -0.00000000 |
| Liquidez `plazo_max_720` | `σ_plazo_max_720*` | 0.13474804 |

## 3. Interpretación económica (Req. 4.3)

- λ* = 0.12010000: retorno marginal de una unidad adicional de capital A. Es el incremento del objetivo Σ f_ijk·x_ijk por cada peso extra de capital disponible, manteniendo óptima la base del LP restringido.
- μ_Bancolombia* ≈ 0: el tope de concentración del banco 'Bancolombia' NO está activo (hay holgura); relajarlo no mejoraría el objetivo.
- μ_Davivienda* ≈ 0: el tope de concentración del banco 'Davivienda' NO está activo (hay holgura); relajarlo no mejoraría el objetivo.
- μ_Lulo Bank* ≈ 0: el tope de concentración del banco 'Lulo Bank' NO está activo (hay holgura); relajarlo no mejoraría el objetivo.
- σ_liquidez_hasta_180_inf* = -0.06653463: la cota de liquidez 'liquidez_hasta_180_inf' está activa; es el costo/valor marginal en rendimiento de exigir ese reparto de capital entre plazos cortos y largos.
- σ_liquidez_hasta_360_inf* ≈ 0: la cota de liquidez 'liquidez_hasta_360_inf' no está activa; no restringe la solución óptima.
- σ_plazo_max_180* ≈ 0: la cota de liquidez 'plazo_max_180' no está activa; no restringe la solución óptima.
- σ_plazo_max_360* ≈ 0: la cota de liquidez 'plazo_max_360' no está activa; no restringe la solución óptima.
- σ_plazo_max_720* = 0.13474804: la cota de liquidez 'plazo_max_720' está activa; es el costo/valor marginal en rendimiento de exigir ese reparto de capital entre plazos cortos y largos.
- s_0* ≈ 0 (capital agotado): λ* = 0.12010000 revela el valor marginal del capital: cada peso adicional sí se colocaría y produciría ese rendimiento extra.

## 4. Rangos de sensibilidad

**Método.** Rangos por PERTURBACIÓN + re-solución del LP restringido (un parámetro a la vez, ceteris paribus). CBC no expone el ranging exacto del símplex; los extremos son numéricos y dependen del paso de búsqueda. No cubre cambios simultáneos (regla del 100%). Válido solo para el LP restringido con z fijadas en z* (Req. 4.7).

### 4.1 Coeficientes objetivo `f_ijk` (Req. 4.5)

| Combinación (i,j,k) | `f` base | Límite inferior | Límite superior | Baja ≤ | Sube ≤ |
| --- | --- | --- | --- | --- | --- |
| `Bancolombia|180|1` | 0.053755 | 0.051963 | +∞ | 0.001792 | +∞ |
| `Bancolombia|360|2` | 0.120100 | 0.052043 | 0.256213 | 0.068057 | 0.136113 |
| `Davivienda|720|2` | 0.254848 | 0.118929 | +∞ | 0.135919 | +∞ |
| `Lulo Bank|180|2` | 0.053565 | −∞ | 0.055351 | +∞ | 0.001786 |

### 4.2 Lado derecho RHS: capital `A` y topes `p_i·A` (Req. 4.6)

| Recurso | RHS base | Límite inferior | Límite superior | Baja ≤ | Sube ≤ |
| --- | --- | --- | --- | --- | --- |
| `capital_A` | 100,000,000.00 | 99,000,000.00 | 101,000,000.00 | 1,000,000.00 | 1,000,000.00 |
| `concentracion_Bancolombia` | 40,000,000.00 | 39,600,000.00 | 40,400,000.00 | 400,000.00 | 400,000.00 |
| `concentracion_Davivienda` | 40,000,000.00 | 39,600,000.00 | 40,400,000.00 | 400,000.00 | 400,000.00 |
| `concentracion_Lulo Bank` | 40,000,000.00 | 20,000,000.00 | +∞ | 20,000,000.00 | +∞ |
| `liquidez_hasta_180_inf` | 30,000,000.00 | 29,700,000.00 | 30,300,000.00 | 300,000.00 | 300,000.00 |
| `liquidez_hasta_360_inf` | 60,000,000.00 | 59,400,000.00 | 60,600,000.00 | 600,000.00 | 600,000.00 |
| `plazo_max_180` | 40,000,000.00 | 30,000,000.00 | +∞ | 10,000,000.00 | +∞ |
| `plazo_max_360` | 40,000,000.00 | 30,000,000.00 | +∞ | 10,000,000.00 | +∞ |
| `plazo_max_720` | 40,000,000.00 | 39,600,000.00 | 40,400,000.00 | 400,000.00 | 400,000.00 |

Dentro de cada intervalo la base óptima (y el precio sombra) se mantiene y la variación del objetivo es lineal: `Δobjetivo = π·Δb`.

## 5. Verificación de holgura complementaria (Req. 4.4)

- Condición `(x*)^T s* = 0` verificada: **True**
- Máxima violación: `0.00e+00` (tolerancia `1e-06`)
- Producto global `Σ dj_v·(v−cota)`: `0.00e+00`

Holgura complementaria VERIFICADA: la máxima violación (0.00e+00) está por debajo de la tolerancia (1e-06). El óptimo primal y el dual son coherentes: toda restricción no activa tiene precio sombra nulo y toda variable interior tiene reduced cost nulo. Término más holgado: 'capital_total' (|producto| = 0.00e+00).

Términos más holgados (mayor |producto| primero):

| Tipo | Nombre | Factor A | Factor B | Producto |
| --- | --- | --- | --- | --- |
| restriccion | `capital_total` | -0 | 0.1201 | -0.00e+00 |
| restriccion | `concentracion_Bancolombia` | -0 | -0 | 0.00e+00 |
| restriccion | `concentracion_Davivienda` | -0 | -0 | 0.00e+00 |
| restriccion | `concentracion_Lulo_Bank` | 2e+07 | -0 | -0.00e+00 |
| restriccion | `liquidez_hasta_180_inf` | -0 | -0.0665346 | 0.00e+00 |
| restriccion | `liquidez_hasta_360_inf` | -0 | -0 | 0.00e+00 |
| restriccion | `plazo_max_180` | 1e+07 | -0 | -0.00e+00 |
| restriccion | `plazo_max_360` | 1e+07 | -0 | -0.00e+00 |
| restriccion | `plazo_max_720` | -0 | 0.134748 | -0.00e+00 |
| variable | `x_Bancolombia_180_1` | 0.000189814 | 0 | 0.00e+00 |
