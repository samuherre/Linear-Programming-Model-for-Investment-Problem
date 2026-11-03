# Esquema de datos — Matriz de CDT y configuración

Esta carpeta define la entrada del modelo. Se separa en dos piezas:

1. `cdt_productos.csv` — matriz tabular de productos `(i, j, k)` con las tasas.
2. `config.py` — parámetros escalares y de política (capital, tramos,
   concentración por banco, liquidez por fecha y tope de concentración por plazo).

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

### Estado del poblado (tasas reales por plazo)

`cdt_productos.csv` cubre el espacio completo `5 × 7 × 3 = 105` filas. El archivo
se regenera de forma reproducible con `python data/generar_cdt_productos.py`.

El poblado aplica el principio de **trazabilidad honesta** (Requisito 1.5): lo
verificado se marca como real; lo no verificable, como supuesto documentado.
Última verificación de fuentes: **2026-11-01**.

> **Cambio respecto a versiones anteriores.** Antes había UNA sola tasa real por
> banco (la "mejor tasa" a plazo largo) y el resto se derivaba con un perfil de
> curva y una prima por tramo inventados. Esta versión reemplaza ese perfil
> supuesto por la **curva de tasas E.A. real por plazo** de cada banco. Con ello,
> las **90 combinaciones utilizables son todas reales** (`es_supuesto = False`).

- **Disponibilidad (`disponible`) — verificada contra fuente:**
  - Bancolombia, Banco de Bogotá, Davivienda: ofrecen `30`–`720` días → todo `J`.
  - Nu Bank: plazos `90`–`720` días → `30` y `60` marcados `disponible=False`.
  - Lulo Bank: plazos `90`–`540` días → `30`, `60` y `720` marcados `disponible=False`.
  - Total: **90 combinaciones disponibles, 15 no disponibles** (excluidas del modelo, Req 1.6).

- **Tasas (`tasa_ea`) — curva real por plazo:** cada banco usa su curva de tasas
  E.A. real por plazo, tomada de fuente verificada:

  | Banco | Fuente | Tipo de dato |
  |-------|--------|--------------|
  | Bancolombia | comparatodo.com.co/cdt/bancolombia | Promedio ponderado E.A. reportado a la SFC (corte 29-oct-2026) |
  | Davivienda | comparatodo.com.co/cdt/davivienda | Promedio ponderado E.A. reportado a la SFC (corte 29-oct-2026) |
  | Banco de Bogotá | ahorrar.com.co/cdt/banco-de-bogota | Tarifario propio por plazo (canal digital), oct-2026 |
  | Nu Bank | ahorrar.com.co/cdt/nu | Tarifario propio por plazo, vigente 6-oct-2026 |
  | Lulo Bank | ahorrar.com.co/cdt/lulo-bank | Tarifario propio por plazo (cliente estándar), vigente 20-oct-2026 |

  - **Real verificada (`es_supuesto = False`):** las 90 filas disponibles llevan la
    tasa real de su plazo; `fuente` cita la URL y "REAL verificado 2026-11-01".
    Para Bancolombia y Davivienda, la SFC publica un único valor "más de 360 días"
    que se aplica a 540 y 720 d (dato real del tramo largo, documentado).
  - **Prima por tramo de monto = 0 (decisión documentada):** el mercado real casi
    no premia el monto en el rango de capital del modelo (Nu y Lulo no diferencian
    por monto; Bancolombia y Davivienda publican un promedio SFC sin desglose;
    Banco de Bogotá desglosa en cortes de cientos de millones, ajenos a los tramos
    del modelo). Para no inventar una prima, los tres tramos de un mismo
    `(banco, plazo)` comparten la tasa real del plazo. Lo único "supuesto" es la
    desagregación por tramo en sí, no la tasa.
  - **No ofrecidas (`disponible = False`, `es_supuesto = True`):** 15 filas con
    `tasa_ea` vacía y nota de que el banco no ofrece ese plazo.

- **`min_apertura`:** monto mínimo real por banco, dato verificable e
  independiente de la tasa.

> Con estas tasas reales el pipeline (`python src/main.py`) resuelve a `Optimal`
> y reparte el capital entre varios plazos cuando las reglas de liquidez por fecha
> están activas.

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
        "reglas": [                         # liquidez por fecha: fracción que vence en <= D días
            {"hasta_dias": 180, "min_frac": 0.30, "max_frac": None},
            {"hasta_dias": 360, "min_frac": 0.60, "max_frac": None},
        ],
        "L_corto": None, "U_corto": None,   # cotas corto/largo (compatibilidad); None = desactivada
        "L_largo": None, "U_largo": None,
    },
    "concentracion_plazo_max": {            # tope máximo de A por plazo (diversificación)
        "default": 0.40,                    # ningún plazo concentra más del 40 % de A
    },
}
```

- Límites de tramo: provienen del enunciado (Requisito 1.3), no son supuestos.
- `concentracion_max` (`p_i`): política de diversificación por banco, en `(0, 1]`.
- `liquidez["reglas"]`: **liquidez por fecha**. Cada regla exige que una fracción
  del capital venza en `<= hasta_dias` días (`min_frac` ≤ fracción ≤ `max_frac`,
  en `[0, 1]`; `None` desactiva esa cota). Permite disponer de caja en una fecha
  intermedia sin forzar que todos los CDT compartan plazo.
- `liquidez["L_corto"/"U_corto"/"L_largo"/"U_largo"]`: cotas clásicas corto
  (`j ≤ 180`) / largo (`j > 180`), mantenidas por compatibilidad. `None` desactiva.
- `concentracion_plazo_max`: **tope por plazo**. Una cota global (`"default"`)
  aplica a todos los plazos; se puede afinar por plazo con claves enteras
  (p. ej. `{720: 0.30}`). Un dict vacío desactiva la restricción.

> **Supuestos del equipo (no datos de mercado).** Las reglas de liquidez por fecha
> y el tope por plazo son **política de tesorería del equipo**, no cifras de
> mercado; se declaran explícitamente aquí. Los valores del escenario base
> (30 % a ≤180 días, 60 % a ≤360 días, ≤40 % por plazo) son ilustrativos y
> editables.
