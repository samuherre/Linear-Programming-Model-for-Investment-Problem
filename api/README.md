# API REST — Modelo de Inversión en CDT

Capa HTTP (FastAPI) que expone el modelo MILP de inversión en CDT ya
implementado en `src/`. **No reimplementa el modelo**: reusa los módulos
`data_loader`, `model`, `solver` y `sensitivity`, más la configuración de
`data/config.py`. Pensada para que un front externo (p. ej. construido en
Lovable) la consuma vía HTTP y JSON.

## Instalación

Desde la raíz del proyecto. Primero las dependencias del modelo (PuLP, pandas,
numpy) y luego las de la API:

```powershell
pip install -r requirements.txt
pip install -r api/requirements-api.txt
```

> `pulp`, `pandas` y `numpy` **no** se duplican en `api/requirements-api.txt`:
> ya están en el `requirements.txt` de la raíz.

## Cómo correr

Desde la **raíz** del proyecto (para que el paquete `api` sea importable):

```powershell
uvicorn api.app:app --reload --port 8000
```

- API base URL: `http://localhost:8000`
- Documentación interactiva (Swagger UI): `http://localhost:8000/docs`
- Esquema OpenAPI: `http://localhost:8000/openapi.json`

## Endpoints

| Método | Ruta         | Descripción                                                        |
|--------|--------------|--------------------------------------------------------------------|
| GET    | `/health`    | Estado de salud. → `{"status":"ok","solver":"CBC"}`                |
| GET    | `/datos`     | Parámetros del modelo: A, bancos, plazos, tramos, concentración, liquidez y resumen de carga. |
| GET    | `/productos` | Matriz de combinaciones `(banco, plazo, tramo)` utilizables con su tasa EA, `f_ijk`, mínimo de apertura y si es supuesto. |
| POST   | `/optimizar` | Resuelve el MILP para un escenario (parámetros opcionales) y devuelve solución + dualidad/sensibilidad. |
| POST   | `/simular-liquidez` | Barrido de liquidez (escalera de CDT): resuelve varios niveles de exigencia a corto plazo y devuelve la comparativa con el costo de oportunidad. |

### `POST /simular-liquidez` — body (todo opcional)

Resuelve el modelo una vez por cada escenario de liquidez y compara la ganancia
`Z*` frente al primer escenario (referencia), cuantificando el **costo de
oportunidad** de mantener capital disponible a corto plazo (≤180 días). Replica
`examples/simulacion_liquidez.py` vía HTTP.

```jsonc
{
  "A": 10000000,                          // capital; por defecto el de config
  "concentracion_max": 0.40,              // float (a todos) o dict {banco: fracción}
  "archivo_datos": "escenario_supuesto.csv", // tasas completas por (i,j,k)
  "escenarios": [                         // opcional; si se omite, barrido por defecto
    { "etiqueta": "Libre",            "L_corto": null, "U_corto": null },
    { "etiqueta": "2M a corto (20%)", "L_corto": 0.20, "U_corto": 0.20 },
    { "etiqueta": "4M a corto (40%)", "L_corto": 0.40, "U_corto": 0.40 }
  ]
}
```

Barrido por defecto (si se omite `escenarios`): Libre, 10%, 20%, 30% y 40% a
corto plazo. Nota: fijar `L_corto = U_corto` **ancla** un monto exacto en el
bucket corto; el optimizador elige el banco/plazo corto que más rinde.

Respuesta resumida:

```jsonc
{
  "ok": true,
  "A": 10000000.0,
  "concentracion_max": { "Bancolombia": 0.40, "...": 0.40 },
  "archivo_datos": "escenario_supuesto.csv",
  "referencia": "primer escenario (costo_oportunidad = Z*_ref − Z*_escenario)",
  "escenarios": [
    { "etiqueta": "Libre",            "ok": true, "objetivo": 2247861.0, "rendimiento_efectivo_pct": 22.479, "monto_corto": 0,       "monto_largo": 10000000, "num_cdt": 3, "costo_oportunidad": 0 },
    { "etiqueta": "20% a corto",      "ok": true, "objetivo": 1919256.0, "rendimiento_efectivo_pct": 19.193, "monto_corto": 2000000, "monto_largo": 8000000,  "num_cdt": 3, "costo_oportunidad": 328605.0 }
  ],
  "advertencia_lp_restringido": "..."
}
```

### `POST /optimizar` — body (todo opcional)

Un body vacío `{}` resuelve el **escenario base** con los valores reales de
`data/config.py`.

```jsonc
{
  "A": 150000000,                         // capital; por defecto el de config
  "concentracion_max": 0.30,              // float (aplica a todos) o dict {banco: fracción}
  "liquidez": {                           // cotas (fracción de A) o null = desactivada
    "L_corto": null, "U_corto": 0.6,
    "L_largo": null, "U_largo": null
  },
  "tasas": {                              // override puntual de tasas EA
    "Bancolombia|720|2": 0.125            // clave "Banco|plazo|tramo", valor fracción EA
  }
}
```

Notas de diseño:

- El override de `tasas` se aplica **en memoria** sobre el `DatosCDT`
  recalculando `f_ijk = (1 + r)^(plazo/360) − 1` solo para las claves
  afectadas (no se usan CSV temporales). Solo acepta combinaciones ya
  utilizables (ver `GET /productos`).
- `DataLoaderError` → HTTP **400** con el mensaje.
- Escenario **sin óptimo** o **sin combinaciones** → HTTP **200** con
  `ok: false` y un `mensaje` accionable (nunca 500).
- Las claves tupla `(banco, plazo, tramo)` se serializan como
  `"Banco|plazo|tramo"`. Los valores `inf`/`-inf`/`NaN` (p. ej. `U_3 = ∞` o
  rangos no acotados) se serializan como `null`.

### Respuesta resumida de `POST /optimizar` con `{}` (escenario base)

```jsonc
{
  "ok": true,
  "estado": "Optimal",
  "solver": "PULP_CBC_CMD",
  "objetivo": 24590300.0,            // Z* (rendimiento efectivo Σ f_ijk·x_ijk)
  "objetivo_r": 11620000.0,          // variante didáctica Σ r_ijk·x_ijk
  "capital_colocado": 100000000.0,
  "s0": 0.0,
  "A": 100000000.0,
  "asignacion": [
    { "clave": "Banco de Bogota|720|2", "monto": 40000000.0, "tasa_ea": 0.117, "pct_capital": 0.40, "rendimiento": 10075200.0, "es_supuesto": true },
    { "clave": "Davivienda|720|2",      "monto": 20000000.0, "tasa_ea": 0.115, "pct_capital": 0.20 },
    { "clave": "Nu Bank|720|2",         "monto": 40000000.0, "tasa_ea": 0.116, "pct_capital": 0.40 }
  ],
  "precios_sombra": {
    "lambda_capital": 0.243225,        // λ*: retorno marginal del capital
    "mu_concentracion": { "Banco de Bogota": 0.0 },
    "sigma_liquidez": {},
    "capital_agotado": true,
    "interpretacion": { "lambda": "λ* = ... retorno marginal ...", "s0_lambda": "..." }
  },
  "holgura_complementaria": { "cumple": true, "max_violacion": 0.0, "tolerancia": 1e-6 },
  "rangos": {
    "degenerado": false,
    "objetivo_f": { "Banco de Bogota|720|2": { "valor_base": 0.26..., "limite_inferior": ..., "limite_superior": ... } },
    "rhs": { "capital_A": { "valor_base": 100000000.0, "limite_inferior": ..., "limite_superior": ... } }
  },
  "advertencia_lp_restringido": "Los precios sombra ... se calculan sobre el LP restringido (z = z*) ... (Requisito 4.7)."
}
```

El `Z* = 24.590.300` coincide con el pipeline de consola (`python src/main.py`).

## Conectar desde Lovable

- Apunta el front al **base URL** `http://localhost:8000` en desarrollo.
- Explora y prueba los endpoints en `http://localhost:8000/docs`; el esquema
  OpenAPI (`/openapi.json`) sirve para generar clientes tipados.
- Flujo típico del front:
  1. `GET /datos` y `GET /productos` para pintar los parámetros y tasas.
  2. `POST /optimizar` con el escenario que arme el usuario (A, concentración,
     liquidez, tasas); render de `asignacion`, `precios_sombra` y `rangos`.
- **CORS**: en desarrollo está abierto (`allow_origins=["*"]`) para permitir el
  origen de Lovable. **En producción** restringe `allow_origins` al dominio real
  del front en `api/app.py` y despliega la API (p. ej. detrás de HTTPS).
