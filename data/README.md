# Esquema de datos — Matriz de CDT y configuración

Esta carpeta define la entrada del modelo. Se separa en dos piezas:

1. `cdt_productos.csv` — matriz tabular de productos `(i, j, k)` con las tasas.
2. `config.py` — parámetros escalares y de política (capital, tramos,
   concentración, liquidez).

> **Principio rector: cero invención de datos.** Cualquier valor no verificado
> contra una fuente real debe marcarse con `es_supuesto = True` y, si no tiene
> fuente, dejarse explícito. El reporte señalará estos casos.

---

## 1. Matriz tabular `cdt_productos.csv`

Cada fila representa un producto `(i, j, k)` = (banco, plazo, tramo).

| Columna        | Tipo          | Descripción |
|----------------|---------------|-------------|
| `banco`        | texto         | Entidad `i`. Debe pertenecer al conjunto `I`. |
| `plazo_dias`   | entero        | Plazo `j` en días. Debe pertenecer al conjunto `J`. |
| `tramo`        | entero {1,2,3}| Tramo de monto `k`. |
| `tasa_ea`      | decimal       | Tasa Efectiva Anual `r_ijk` (p. ej. `0.095` = 9,5 % E.A.). |
| `min_apertura` | decimal       | Monto mínimo de apertura `m_ij` del banco/plazo. |
| `disponible`   | booleano      | `True` si el producto se ofrece; `False` lo excluye del modelo. |
| `fuente`       | texto         | URL y/o fecha de consulta de la tasa. Vacío si es supuesto. |
| `es_supuesto`  | booleano      | `True` si la tasa NO está verificada contra fuente real. |

### Conjuntos esperados

- `I` (banco): `Bancolombia`, `Banco de Bogota`, `Davivienda`, `Nu Bank`, `Lulo Bank`.
- `J` (plazo_dias): `30, 60, 90, 180, 360, 540, 720`.
- `K` (tramo): `1, 2, 3`.

El espacio completo es `5 × 7 × 3 = 105` combinaciones. No todas existen en el
mercado: las no ofrecidas se registran con `disponible = False` (tarea 2.2) o
simplemente se omiten; el `data_loader` excluye del modelo lo no disponible.

### Reglas de poblado (tarea 2.2)

- Registrar `tasa_ea` real por combinación disponible, con `fuente` (URL + fecha)
  y `es_supuesto = False`.
- Si un producto no se ofrece, marcar `disponible = False`.
- Si una tasa es un supuesto razonado (no verificable), `es_supuesto = True` y
  documentar el criterio en `fuente`.

### Estado del poblado (tarea 2.2 — completada, tasas reales ancladas)

`cdt_productos.csv` cubre el espacio completo `5 × 7 × 3 = 105` filas. El archivo
se regenera de forma reproducible con `python data/generar_cdt_productos.py`.

El poblado aplica el principio de **trazabilidad honesta** (Requisito 1.5): lo
verificado se marca como real; lo derivado se marca como supuesto documentado.
Nunca se presenta como real una cifra no verificada. Última verificación de
fuentes: **2026-10-21** (comparador público finanzasplus.co y prensa para Lulo).

- **Disponibilidad (`disponible`) — verificada contra fuente:**
  - Bancolombia, Banco de Bogotá, Davivienda: ofrecen `30`–`720` días → todo `J`.
  - Nu Bank: plazos `90`–`720` días → `30` y `60` marcados `disponible=False`.
  - Lulo Bank: plazos `90`–`540` días → `30`, `60` y `720` marcados `disponible=False`.
  - Total: 90 combinaciones disponibles, 15 no disponibles (excluidas del modelo, Req 1.6).

- **Tasas (`tasa_ea`) — ancla real por banco + derivadas por perfil:** a diferencia
  del estado anterior (todo vacío), ahora el CSV trae tasas numéricas reales
  **ancladas** por banco y un perfil de curva declarado:

  | Banco | Tasa ancla E.A. (real) | Plazo ancla | `min_apertura` | Fuente |
  |-------|------------------------|-------------|----------------|--------|
  | Bancolombia | 11.20 % | 540 d | $500.000 | finanzasplus.co/comparar/cdts/bancolombia |
  | Banco de Bogotá | 11.50 % | 540 d | $100.000 | finanzasplus.co/comparar/cdts/banco-de-bogota |
  | Davivienda | 11.30 % | 540 d | $500.000 | finanzasplus.co/comparar/cdts/davivienda |
  | Nu Bank | 11.40 % | 540 d | $50.000 | finanzasplus.co/comparar/cdts/nu |
  | Lulo Bank | 11.50 % | 540 d | $100.000 | ayuda.lulobank.com + larepublica.co |

  - **Real verificada (`es_supuesto = False`):** la fila `(banco, plazo 540 d, tramo 1)`
    de cada banco lleva la mejor tasa E.A. verificada arriba; `fuente` cita la URL
    y "verificado 2026-10-21". Son 5 filas (una por banco).
  - **Derivada (`es_supuesto = True`):** las demás 85 filas disponibles se obtienen
    del ancla real aplicando dos supuestos de modelado documentados en el generador:
    - **Perfil de curva por plazo** (ajuste en pp respecto al ancla; plazos cortos
      pagan menos, 540/720 d pagan la mejor tasa):
      `30:-0.90  60:-0.80  90:-0.70  180:-0.50  360:-0.20  540:0.00  720:0.00` pp.
    - **Prima de tramo de monto** (ninguna fuente desagrega por los 3 tramos del spec):
      `tramo 1:+0.00  tramo 2:+0.20  tramo 3:+0.40` pp. Su `fuente` explica que son el
      ancla real ajustada por perfil/prima y cita la URL del banco.
  - **No ofrecidas (`disponible = False`, `es_supuesto = True`):** 15 filas con
    `tasa_ea` vacía y nota de que el banco no ofrece ese plazo.

- **`min_apertura`:** monto mínimo real por banco (ver tabla), dato verificable e
  independiente de la tasa.

> El perfil de curva y la prima de tramo son **supuestos de modelado** (no datos
> de mercado). El ancla sí es real y verificada; todo lo derivado queda marcado
> `es_supuesto = True` con su criterio en `fuente`, de modo que el informe lo
> señale. Con estas tasas el pipeline (`python src/main.py`) resuelve a `Optimal`.

---

## 2. Configuración `config.py`

Expone `get_config()` que devuelve:

```python
{
    "A": 100_000_000,                       # capital total
    "tramos": {                             # (L_k, U_k) por tramo; U_3 = None (∞)
        1: (50_000, 10_000_000),
        2: (10_000_001, 50_000_000),
        3: (50_000_001, None),
    },
    "concentracion_max": {banco: p_i, ...}, # fracción máxima de A por banco
    "liquidez": {                           # política de tesorería (fracciones de A)
        "L_corto": None, "U_corto": None,   # j <= 180 ; None = cota desactivada
        "L_largo": None, "U_largo": None,   # j > 180  ; None = cota desactivada
    },
}
```

- Límites de tramo: provienen del enunciado (Requisito 1.3), no son supuestos.
- `concentracion_max` (`p_i`): política de diversificación, en `(0, 1]`.
- `liquidez`: cotas parametrizadas. `None` desactiva la cota. **No inventar
  porcentajes**: dejar en `None` hasta que el equipo fije la política real.
