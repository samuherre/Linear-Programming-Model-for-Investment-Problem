"""API REST (FastAPI) que expone el modelo MILP de inversión en CDT.

Esta API NO reimplementa el modelo: REUSA los módulos ya implementados en
`src/` (data_loader, model, solver, sensitivity) y la configuración de
`data/config.py`. Es una capa HTTP delgada pensada para que un front externo
(p. ej. construido en Lovable) la consuma vía HTTP y JSON.

Patrón de importación
---------------------
El proyecto ejecuta con `src/` en el path (ver `src/main.py`, que importa
`from data_loader import ...`). Replicamos ese patrón: insertamos al inicio del
`sys.path` las rutas absolutas de `src/` y `data/`, de modo que los imports de
los módulos existentes funcionen sin modificarlos.

Serialización a JSON
--------------------
Los módulos de `src/` indexan muchas estructuras por claves tupla
`(banco, plazo, tramo)`, que no son claves JSON válidas. Se serializan a texto
legible con el helper `clave_a_texto` del propio módulo `sensitivity`
("Banco|plazo|tramo"). Los valores `float('inf')`/`-inf`/`NaN` no son JSON
válidos (no estándar): se convierten a `None` (null) con `_num_seguro`, que es
la convención documentada de esta API para "sin cota / no acotado".

Decisión sobre el override de tasas (POST /optimizar)
-----------------------------------------------------
Cuando el body trae `tasas` (override puntual de tasas EA), NO se escribe un CSV
temporal: se carga el `DatosCDT` normal y se aplica el override EN MEMORIA sobre
los dicts `r`/`f` del `DatosCDT`, recalculando `f_ijk = (1+r)^(plazo/360) - 1`
solo para las claves afectadas (misma fórmula que `data_loader`). Es la vía más
simple y robusta: evita I/O temporal, condiciones de carrera entre peticiones y
limpieza de archivos, y mantiene intactos los módulos de `src/`.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Optional

# ---------------------------------------------------------------------------
# sys.path: insertar src/ y data/ ANTES de importar los módulos del proyecto,
# replicando el patrón de ejecución de src/main.py (imports planos).
# ---------------------------------------------------------------------------
_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC = os.path.join(_RAIZ, "src")
_DATA = os.path.join(_RAIZ, "data")
for _ruta in (_SRC, _DATA):
    if _ruta not in sys.path:
        sys.path.insert(0, _ruta)

# Importaciones de los módulos existentes de src/ (NO se modifican).
from data_loader import DataLoaderError, DatosCDT, cargar_datos  # noqa: E402
from model import (  # noqa: E402
    agregar_restricciones_riesgo,
    agregar_restricciones_tramos,
    construir_modelo,
)
from solver import resolver  # noqa: E402
from sensitivity import (  # noqa: E402
    calcular_rangos_sensibilidad,
    clave_a_texto,
    construir_lp_restringido,
    extraer_precios_sombra,
    verificar_holgura_complementaria,
)

# Configuración escalar del proyecto (data/config.py::get_config()).
import config as config_modulo  # noqa: E402

from fastapi import FastAPI, HTTPException, Request  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from pydantic import BaseModel, Field, field_validator, model_validator  # noqa: E402


# Texto de advertencia del Requisito 4.7: la sensibilidad/dualidad aplica al LP
# restringido (binarias fijadas en z*), NO al MILP original.
ADVERTENCIA_LP_RESTRINGIDO = (
    "Los precios sombra, la holgura complementaria y los rangos de "
    "sensibilidad se calculan sobre el LP restringido (las binarias z se fijan "
    "en su valor óptimo z* del MILP). La teoría de dualidad fuerte solo es "
    "válida para un LP, no para el MILP original: interprete estos resultados "
    "como propios del LP restringido con z = z* (Requisito 4.7)."
)


# ===========================================================================
# Utilidades de serialización segura a JSON
# ===========================================================================
def _num_seguro(valor: Any) -> Optional[float]:
    """Convierte un número a un valor JSON seguro.

    `float('inf')`, `float('-inf')` y `NaN` no son JSON estándar; esta API los
    representa como `null` (convención: "sin cota / no acotado / no definido").
    Un `None` de entrada se mantiene como `None`.
    """
    if valor is None:
        return None
    try:
        f = float(valor)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN
        return None
    if f in (float("inf"), float("-inf")):
        return None
    return f


def _dict_claves_tupla_a_texto(d: dict) -> dict:
    """Serializa un dict indexado por `(banco, plazo, tramo)` a claves texto.

    Usa `clave_a_texto` de `sensitivity` ("Banco|plazo|tramo") para producir
    claves JSON legibles y estables.
    """
    salida: dict[str, Any] = {}
    for clave, valor in d.items():
        if isinstance(clave, tuple):
            salida[clave_a_texto(clave)] = valor
        else:
            salida[str(clave)] = valor
    return salida


def _texto_a_clave(texto: str) -> tuple[str, int, int]:
    """Convierte "Banco|plazo|tramo" de vuelta a la tupla `(banco, plazo, tramo)`.

    Inversa de `clave_a_texto`. Se usa para interpretar el override de tasas que
    llega del front con claves string.
    """
    partes = texto.split("|")
    if len(partes) != 3:
        raise ValueError(
            f"Clave de tasa inválida '{texto}'. Formato esperado "
            "'Banco|plazo|tramo', p. ej. 'Bancolombia|360|2'."
        )
    banco, plazo_txt, tramo_txt = partes
    try:
        return (banco.strip(), int(plazo_txt), int(tramo_txt))
    except ValueError as exc:
        raise ValueError(
            f"Clave de tasa inválida '{texto}': plazo y tramo deben ser enteros."
        ) from exc


# ===========================================================================
# Modelos Pydantic (contratos de request / response documentados en /docs)
# ===========================================================================
class CotasLiquidez(BaseModel):
    """Cotas de liquidez: cuánto del capital debe ir a corto vs largo plazo.

    ¿Qué controlan estos campos?
    ----------------------------
    El modelo reparte el capital entre CDT de **corto plazo** (vencimiento
    ≤180 días, dinero que recuperas pronto) y de **largo plazo** (>180 días,
    queda amarrado más tiempo pero suele rendir más). Estas cuatro cotas te
    dejan EXIGIR qué fracción del capital va a cada grupo:

      - `L_corto` / `U_corto`: mínimo y máximo que puede ir a CORTO plazo.
      - `L_largo` / `U_largo`: mínimo y máximo que puede ir a LARGO plazo.

    Escala: FRACCIÓN del capital, entre 0 y 1 (NO porcentaje).
    ---------------------------------------------------------
      - 0.20  = 20% del capital      0.60 = 60%      1.0 = 100%
      - Para "20% a 60% a corto plazo": L_corto=0.20, U_corto=0.60.
      - Un campo en `null` (o ausente) = esa cota está DESACTIVADA (el modelo
        decide libremente). Si no quieres exigir liquidez, deja los cuatro en
        null y el optimizador reparte solo para maximizar el rendimiento.

    Reglas que se validan ANTES de resolver (si no se cumplen, HTTP 400):
      1. Cada valor debe estar en el rango [0, 1] (o ser null).
      2. El mínimo no puede superar al máximo del mismo grupo: L_corto ≤ U_corto
         y L_largo ≤ U_largo.
    """

    L_corto: Optional[float] = Field(
        default=None,
        ge=0,
        le=1,
        description=(
            "Fracción MÍNIMA del capital en plazos ≤180 días. Valor entre 0 y 1 "
            "(p. ej. 0.20 = 20%) o null = sin exigencia."
        ),
    )
    U_corto: Optional[float] = Field(
        default=None,
        ge=0,
        le=1,
        description=(
            "Fracción MÁXIMA del capital en plazos ≤180 días. Valor entre 0 y 1 "
            "(p. ej. 0.60 = 60%) o null = sin tope. Debe ser ≥ L_corto."
        ),
    )
    L_largo: Optional[float] = Field(
        default=None,
        ge=0,
        le=1,
        description=(
            "Fracción MÍNIMA del capital en plazos >180 días. Valor entre 0 y 1 "
            "o null = sin exigencia."
        ),
    )
    U_largo: Optional[float] = Field(
        default=None,
        ge=0,
        le=1,
        description=(
            "Fracción MÁXIMA del capital en plazos >180 días. Valor entre 0 y 1 "
            "o null = sin tope. Debe ser ≥ L_largo."
        ),
    )

    @field_validator("L_corto", "U_corto", "L_largo", "U_largo", mode="before")
    @classmethod
    def _rechazar_escala_porcentaje(cls, valor: Any, info: Any) -> Any:
        """Detecta el error típico de enviar porcentaje (p. ej. 60) en vez de 0.60.

        Da un mensaje accionable en vez del críptico "fuera de rango", que es la
        causa más común de confusión (el front rotula "%", pero aquí van
        fracciones 0–1).
        """
        if valor is None:
            return valor
        try:
            numero = float(valor)
        except (TypeError, ValueError):
            # Deja que la validación estándar de tipo de Pydantic lo reporte.
            return valor
        if numero > 1:
            raise ValueError(
                f"'{info.field_name}'={numero} parece un PORCENTAJE. Este campo "
                f"usa FRACCIÓN del capital entre 0 y 1: use {numero / 100:g} "
                f"para {numero:g}% (p. ej. 0.60 = 60%)."
            )
        if numero < 0:
            raise ValueError(
                f"'{info.field_name}'={numero} no puede ser negativo. Use una "
                "fracción entre 0 y 1, o null para desactivar la cota."
            )
        return valor

    @model_validator(mode="after")
    def _validar_min_menor_que_max(self) -> "CotasLiquidez":
        """Exige L ≤ U en cada grupo (corto y largo) antes de llegar al solver.

        Captura el caso imposible "mínimo mayor que máximo" (p. ej. L_corto=0.60
        con U_corto=0.20) con un mensaje claro, en vez de un error de infactibilidad
        difícil de interpretar.
        """
        if (
            self.L_corto is not None
            and self.U_corto is not None
            and self.L_corto > self.U_corto
        ):
            raise ValueError(
                f"Liquidez a corto plazo incoherente: el mínimo L_corto="
                f"{self.L_corto:g} no puede ser mayor que el máximo U_corto="
                f"{self.U_corto:g}. Invierta los valores o ajústelos "
                f"(ejemplo válido: L_corto=0.20, U_corto=0.60)."
            )
        if (
            self.L_largo is not None
            and self.U_largo is not None
            and self.L_largo > self.U_largo
        ):
            raise ValueError(
                f"Liquidez a largo plazo incoherente: el mínimo L_largo="
                f"{self.L_largo:g} no puede ser mayor que el máximo U_largo="
                f"{self.U_largo:g}. Invierta los valores o ajústelos "
                f"(ejemplo válido: L_largo=0.40, U_largo=1.0)."
            )
        return self


class ReglaLiquidez(BaseModel):
    """Regla de liquidez por fecha: fracción de A que vence en ≤ hasta_dias.

    Modela la necesidad de disponer de parte del capital en una fecha intermedia
    (p. ej. a los 180 días) sin inmovilizar todo el dinero en el plazo más
    rentable. Restringe el capital colocado en CDT con plazo ≤ hasta_dias:
        min_frac·A ≤ (capital en plazos ≤ hasta_dias) ≤ max_frac·A
    """

    hasta_dias: int = Field(
        gt=0, description="Umbral de plazo en días. Agrupa los CDT que vencen en ≤ este valor."
    )
    min_frac: Optional[float] = Field(
        default=None, ge=0, le=1,
        description="Fracción mínima de A que debe vencer en ≤ hasta_dias (0..1) o null.",
    )
    max_frac: Optional[float] = Field(
        default=None, ge=0, le=1,
        description="Fracción máxima de A que puede quedar en ≤ hasta_dias (0..1) o null.",
    )


class OptimizarRequest(BaseModel):
    """Parámetros OPCIONALES de escenario para `POST /optimizar`.

    Todos los campos son opcionales; al omitirlos se usan los valores reales de
    `data/config.py`. Así, un body vacío `{}` resuelve el escenario base.
    """

    A: Optional[float] = Field(
        default=None, gt=0, description="Capital total a invertir. Por defecto, el de config."
    )
    concentracion_max: Optional[Any] = Field(
        default=None,
        description=(
            "Concentración máxima por banco. Puede ser un único float (0..1] "
            "que aplica a TODOS los bancos, o un dict {banco: fracción}."
        ),
    )
    liquidez: Optional[CotasLiquidez] = Field(
        default=None, description="Cotas de liquidez corto/largo. Por defecto, las de config (None=off)."
    )
    liquidez_reglas: Optional[list[ReglaLiquidez]] = Field(
        default=None,
        description=(
            "Reglas de liquidez por fecha. Sobrescriben las reglas de config. "
            "Lista vacía [] las desactiva; null = usar las de config."
        ),
    )
    concentracion_plazo_max: Optional[Any] = Field(
        default=None,
        description=(
            "Diversificación por plazo: fracción máxima de A en un mismo plazo. "
            "Un único float (0..1] aplica a TODOS los plazos, o un dict "
            "{'default': q, <plazo>: q_j}. Evita concentrar todo en un plazo."
        ),
    )
    tasas: Optional[dict[str, float]] = Field(
        default=None,
        description=(
            "Override puntual de tasas EA por combinación. Claves "
            "'Banco|plazo|tramo' (p. ej. 'Bancolombia|360|2') y valor la tasa "
            "EA en fracción (0..1). Recalcula f_ijk de las claves afectadas."
        ),
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {},
                {"A": 200000000, "concentracion_max": 0.30},
                {
                    "A": 150000000,
                    "concentracion_max": {"Bancolombia": 0.25, "Nu Bank": 0.5},
                    "liquidez_reglas": [
                        {"hasta_dias": 180, "min_frac": 0.30},
                        {"hasta_dias": 360, "min_frac": 0.60},
                    ],
                    "concentracion_plazo_max": 0.40,
                    "tasas": {"Bancolombia|360|2": 0.125},
                },
            ]
        }
    }


class EscenarioLiquidez(BaseModel):
    """Un escenario del barrido de liquidez (cota corto plazo, ≤180 días).

    Misma escala y reglas que `CotasLiquidez`: los valores son FRACCIÓN del
    capital entre 0 y 1 (no porcentaje) y `L_corto` no puede superar a `U_corto`.
    Fijar `L_corto = U_corto` ANCLA un monto exacto en el bucket corto.
    """

    etiqueta: Optional[str] = Field(
        default=None,
        description="Nombre legible del escenario (p. ej. '2M a corto (20%)').",
    )
    L_corto: Optional[float] = Field(
        default=None,
        ge=0,
        le=1,
        description=(
            "Fracción MÍNIMA del capital en plazos ≤180 días. Entre 0 y 1 "
            "(p. ej. 0.20 = 20%) o null = sin cota."
        ),
    )
    U_corto: Optional[float] = Field(
        default=None,
        ge=0,
        le=1,
        description=(
            "Fracción MÁXIMA del capital en plazos ≤180 días. Entre 0 y 1 o "
            "null = sin cota. Debe ser ≥ L_corto."
        ),
    )

    @field_validator("L_corto", "U_corto", mode="before")
    @classmethod
    def _rechazar_escala_porcentaje(cls, valor: Any, info: Any) -> Any:
        """Igual que en CotasLiquidez: detecta porcentaje (>1) o valor negativo."""
        if valor is None:
            return valor
        try:
            numero = float(valor)
        except (TypeError, ValueError):
            return valor
        if numero > 1:
            raise ValueError(
                f"'{info.field_name}'={numero} parece un PORCENTAJE. Use "
                f"FRACCIÓN entre 0 y 1: {numero / 100:g} para {numero:g}%."
            )
        if numero < 0:
            raise ValueError(
                f"'{info.field_name}'={numero} no puede ser negativo "
                "(use 0..1 o null)."
            )
        return valor

    @model_validator(mode="after")
    def _validar_min_menor_que_max(self) -> "EscenarioLiquidez":
        """Exige L_corto ≤ U_corto en el escenario."""
        if (
            self.L_corto is not None
            and self.U_corto is not None
            and self.L_corto > self.U_corto
        ):
            etiqueta = f" ('{self.etiqueta}')" if self.etiqueta else ""
            raise ValueError(
                f"Escenario de liquidez{etiqueta} incoherente: el mínimo "
                f"L_corto={self.L_corto:g} no puede superar al máximo "
                f"U_corto={self.U_corto:g}."
            )
        return self


class SimularLiquidezRequest(BaseModel):
    """Parámetros del barrido de liquidez ("escalera" de CDT).

    Resuelve el MILP una vez por cada escenario de liquidez y compara la
    ganancia (Z*) frente a un escenario de referencia SIN exigencia de liquidez,
    cuantificando el costo de oportunidad de mantener capital disponible a corto
    plazo. Replica el ejemplo `examples/simulacion_liquidez.py` vía HTTP.
    """

    A: Optional[float] = Field(
        default=None, gt=0, description="Capital total. Por defecto, el de config."
    )
    concentracion_max: Optional[Any] = Field(
        default=None,
        description="Concentración máxima por banco: float (aplica a todos) o dict {banco: fracción}.",
    )
    archivo_datos: Optional[str] = Field(
        default=None,
        description=(
            "Archivo de datos a usar (dentro de data/). Por defecto el del "
            "proyecto. Para tasas completas por (i,j,k) use 'escenario_supuesto.csv'."
        ),
    )
    escenarios: Optional[list[EscenarioLiquidez]] = Field(
        default=None,
        description=(
            "Lista de escenarios de liquidez a comparar. Si se omite, se usa un "
            "barrido por defecto: libre, 10%, 20%, 30% y 40% a corto plazo."
        ),
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {},
                {
                    "A": 10000000,
                    "concentracion_max": 0.40,
                    "archivo_datos": "escenario_supuesto.csv",
                    "escenarios": [
                        {"etiqueta": "Libre", "L_corto": None, "U_corto": None},
                        {"etiqueta": "2M a corto (20%)", "L_corto": 0.20, "U_corto": 0.20},
                        {"etiqueta": "4M a corto (40%)", "L_corto": 0.40, "U_corto": 0.40},
                    ],
                },
            ]
        }
    }


# Barrido por defecto del endpoint de liquidez: (etiqueta, L_corto, U_corto).
# Fijar L=U ancla un monto exacto en el bucket corto (≤180 días).
_BARRIDO_LIQUIDEZ_DEFECTO = [
    ("Libre (sin exigencia de liquidez)", None, None),
    ("10% a corto", 0.10, 0.10),
    ("20% a corto", 0.20, 0.20),
    ("30% a corto", 0.30, 0.30),
    ("40% a corto", 0.40, 0.40),
]


# ===========================================================================
# Aplicación FastAPI + CORS
# ===========================================================================
app = FastAPI(
    title="API de Optimización de Inversión en CDT",
    version="1.0.0",
    description=(
        "Expone el modelo MILP de inversión en CDT (Python + PuLP/CBC) sobre "
        "HTTP para consumo de un front externo. Reusa los módulos de `src/` "
        "sin reimplementar el modelo. Documentación interactiva en /docs."
    ),
)

# CORS ABIERTO para desarrollo: permite que un front en otro origen (p. ej.
# Lovable) consuma la API. EN PRODUCCIÓN restrinja `allow_origins` al dominio
# real del front en vez de usar "*".
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # PRODUCCIÓN: fijar el/los origen(es) reales del front.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===========================================================================
# Manejo uniforme de errores: mensajes claros y accionables para el front
# ===========================================================================
def _ubicacion_legible(loc: tuple) -> str:
    """Traduce la ruta técnica del error (`loc` de Pydantic) a texto legible.

    Pydantic reporta `loc` como ('body', 'liquidez', 'U_corto'); aquí lo
    convertimos a "liquidez → U_corto", omitiendo el prefijo técnico 'body'
    para que el usuario vea el campo que falló.
    """
    partes = [str(p) for p in loc if p not in ("body", "__root__")]
    return " → ".join(partes) if partes else "(cuerpo de la petición)"


@app.exception_handler(RequestValidationError)
async def _handler_validacion(request: Request, exc: RequestValidationError):
    """Aplana los errores de validación (422) en un mensaje claro.

    FastAPI devuelve por defecto una lista anidada difícil de mostrar en un
    front. Este handler la convierte en:
      - `mensaje`: una o varias frases legibles (campo + motivo), listas para
        mostrarse tal cual al usuario.
      - `errores`: el detalle estructurado por si el front quiere resaltar
        campos concretos.
    Así, el caso típico (poner 60 en vez de 0.60, o un mínimo mayor que el
    máximo) llega al usuario con una explicación entendible, no con jerga.
    """
    mensajes: list[str] = []
    detalles: list[dict[str, Any]] = []
    for err in exc.errors():
        campo = _ubicacion_legible(err.get("loc", ()))
        motivo = err.get("msg", "valor inválido")
        # Pydantic antepone "Value error, " a los ValueError de nuestros
        # validadores; lo quitamos para que el mensaje quede limpio.
        motivo = motivo.replace("Value error, ", "")
        mensajes.append(f"{campo}: {motivo}")
        detalles.append({"campo": campo, "motivo": motivo})

    return JSONResponse(
        status_code=422,
        content={
            "ok": False,
            "error": "datos_invalidos",
            "mensaje": " | ".join(mensajes),
            "errores": detalles,
        },
    )


@app.exception_handler(HTTPException)
async def _handler_http(request: Request, exc: HTTPException):
    """Da forma uniforme a los errores HTTP lanzados a propósito (p. ej. 400).

    Mantiene el `status_code` original pero envuelve el `detail` en el mismo
    sobre `{ok, error, mensaje}` que usa el resto de la API, para que el front
    siempre pueda leer `mensaje` sin importar el tipo de error.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "ok": False,
            "error": "peticion_invalida" if exc.status_code == 400 else "error_http",
            "mensaje": exc.detail,
        },
    )


# ===========================================================================
# Helpers de dominio (carga de datos con override de escenario)
# ===========================================================================
def _construir_config_override(req: OptimizarRequest) -> dict[str, Any]:
    """Construye un config a partir de `get_config()` aplicando el override.

    Parte de la configuración real (`data/config.py::get_config()`) y sobrescribe
    SOLO lo que venga en el request: capital `A`, concentración por banco y cotas
    de liquidez. No toca los tramos (provienen del enunciado del problema).
    """
    base = config_modulo.get_config()
    config = {
        "A": base["A"],
        "tramos": base["tramos"],
        "concentracion_max": dict(base["concentracion_max"]),
        "liquidez": dict(base["liquidez"]),
        "concentracion_plazo_max": dict(base.get("concentracion_plazo_max", {}) or {}),
    }
    # Copia profunda de las reglas de liquidez (lista de dicts) para no mutar base.
    config["liquidez"]["reglas"] = [
        dict(r) for r in (base.get("liquidez", {}).get("reglas", []) or [])
    ]

    if req.A is not None:
        config["A"] = float(req.A)

    if req.concentracion_max is not None:
        cm = req.concentracion_max
        if isinstance(cm, (int, float)):
            # Un único float aplica a TODOS los bancos conocidos.
            config["concentracion_max"] = {
                banco: float(cm) for banco in config["concentracion_max"]
            }
        elif isinstance(cm, dict):
            # Override por banco; se mantienen los no mencionados.
            nuevo = dict(config["concentracion_max"])
            for banco, valor in cm.items():
                if banco not in nuevo:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Banco '{banco}' en concentracion_max no pertenece "
                            f"al conjunto de bancos: {sorted(nuevo)}."
                        ),
                    )
                nuevo[banco] = float(valor)
            config["concentracion_max"] = nuevo
        else:
            raise HTTPException(
                status_code=400,
                detail="concentracion_max debe ser un número o un dict {banco: fracción}.",
            )

    if req.liquidez is not None:
        # Override de las 4 cotas corto/largo (compatibilidad).
        for clave, valor in req.liquidez.model_dump().items():
            config["liquidez"][clave] = valor

    if req.liquidez_reglas is not None:
        # Reemplaza por completo las reglas por fecha ([] las desactiva).
        config["liquidez"]["reglas"] = [
            {
                "hasta_dias": int(regla.hasta_dias),
                "min_frac": regla.min_frac,
                "max_frac": regla.max_frac,
            }
            for regla in req.liquidez_reglas
        ]

    if req.concentracion_plazo_max is not None:
        cpm = req.concentracion_plazo_max
        if isinstance(cpm, (int, float)):
            # Un único float = tope global para todos los plazos.
            config["concentracion_plazo_max"] = {"default": float(cpm)}
        elif isinstance(cpm, dict):
            nuevo: dict[Any, float] = {}
            for clave, valor in cpm.items():
                if clave == "default":
                    nuevo["default"] = float(valor)
                else:
                    try:
                        nuevo[int(clave)] = float(valor)
                    except (TypeError, ValueError):
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                f"concentracion_plazo_max: clave '{clave}' debe "
                                "ser 'default' o un plazo entero."
                            ),
                        )
            config["concentracion_plazo_max"] = nuevo
        else:
            raise HTTPException(
                status_code=400,
                detail=(
                    "concentracion_plazo_max debe ser un número o un dict "
                    "{'default': q, <plazo>: q_j}."
                ),
            )

    return config


def _aplicar_override_tasas(datos: DatosCDT, tasas: dict[str, float]) -> None:
    """Aplica en memoria un override de tasas EA sobre `datos.r`/`datos.f`.

    Recalcula `f_ijk = (1 + r)^(plazo/360) - 1` para cada clave afectada, con la
    MISMA fórmula que `data_loader`. Solo permite sobrescribir combinaciones ya
    presentes en `datos.combinaciones` (no crea nuevas, para no inventar datos).
    """
    for texto, tasa in tasas.items():
        clave = _texto_a_clave(texto)
        if clave not in datos.r:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"La tasa override '{texto}' no corresponde a una "
                    "combinación utilizable del modelo. Consulte GET /productos "
                    "para ver las claves válidas."
                ),
            )
        try:
            r_ijk = float(tasa)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400,
                detail=f"La tasa override de '{texto}' no es un número válido.",
            )
        if not (0.0 <= r_ijk < 1.0):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"La tasa override de '{texto}'={r_ijk} debe estar en "
                    "[0, 1) (fracción EA, p. ej. 0.12 para 12%)."
                ),
            )
        _banco, plazo, _tramo = clave
        datos.r[clave] = r_ijk
        datos.f[clave] = (1.0 + r_ijk) ** (plazo / 360.0) - 1.0


def _es_supuesto_por_clave(datos: DatosCDT) -> dict[tuple[str, int, int], bool]:
    """Mapa `(i,j,k) -> es_supuesto` a partir de `datos.info['supuestos']`."""
    supuestos = set(datos.info.get("supuestos", []))
    return {clave: (clave in supuestos) for clave in datos.combinaciones}


# ===========================================================================
# Endpoints
# ===========================================================================
@app.get("/health", summary="Estado de salud de la API")
def health() -> dict[str, str]:
    """Verificación simple de que la API está arriba y qué solver usa."""
    return {"status": "ok", "solver": "CBC"}


@app.get("/datos", summary="Parámetros actuales del modelo (config + resumen de carga)")
def obtener_datos() -> dict[str, Any]:
    """Carga los datos reales por defecto y devuelve los parámetros del modelo.

    Útil para que el front muestre el escenario base: capital `A`, bancos,
    plazos, tramos con sus límites `(L_k, U_k)`, concentración por banco,
    cotas de liquidez y un resumen de `info` (totales, utilizables, cuántas
    combinaciones son supuestas).
    """
    try:
        datos = cargar_datos()
    except DataLoaderError as err:
        raise HTTPException(status_code=400, detail=str(err))

    tramos = {
        str(k): {
            "L_k": _num_seguro(limites[0]),
            "U_k": _num_seguro(limites[1]),  # None (∞) -> null
        }
        for k, limites in sorted(datos.tramos_limites.items())
    }

    info = datos.info
    resumen_info = {
        "total_filas": info.get("total_filas"),
        "combinaciones_utilizables": info.get("combinaciones_utilizables"),
        "excluidos_no_disponibles": len(info.get("excluidos_no_disponibles", [])),
        "excluidos_sin_tasa": len(info.get("excluidos_sin_tasa", [])),
        "marcadas_supuesto": len(info.get("supuestos", [])),
        "reales": info.get("combinaciones_utilizables", 0)
        - len([c for c in info.get("supuestos", []) if c in set(datos.combinaciones)]),
        "supuestas": len([c for c in info.get("supuestos", []) if c in set(datos.combinaciones)]),
        "todas_supuestas": info.get("todas_supuestas"),
    }

    # Serialización de liquidez: cotas corto/largo (números) + reglas (lista).
    liq = datos.liquidez or {}
    liquidez_serial = {
        k: _num_seguro(liq.get(k))
        for k in ("L_corto", "U_corto", "L_largo", "U_largo")
    }
    liquidez_serial["reglas"] = [
        {
            "hasta_dias": int(r["hasta_dias"]),
            "min_frac": _num_seguro(r.get("min_frac")),
            "max_frac": _num_seguro(r.get("max_frac")),
        }
        for r in (liq.get("reglas", []) or [])
    ]

    # Concentración por plazo (diversificación). Claves int se pasan a str JSON.
    cpm = datos.concentracion_plazo_max or {}
    concentracion_plazo = {str(k): _num_seguro(v) for k, v in cpm.items()}

    return {
        "A": _num_seguro(datos.A),
        "bancos": datos.bancos,
        "plazos": datos.plazos,
        "tramos": tramos,
        "concentracion_max": {b: _num_seguro(v) for b, v in datos.p.items()},
        "liquidez": liquidez_serial,
        "concentracion_plazo_max": concentracion_plazo,
        "info": resumen_info,
    }


@app.get("/productos", summary="Matriz de productos utilizables (i, j, k)")
def obtener_productos() -> dict[str, Any]:
    """Devuelve la lista de combinaciones utilizables con sus parámetros.

    Cada producto trae `banco`, `plazo`, `tramo`, tasa EA `r`, factor `f_ijk`,
    monto mínimo de apertura y si es supuesto. El front lo usa para mostrar o
    elegir tasas. La clave textual ("Banco|plazo|tramo") permite referenciar la
    combinación en el override `tasas` de `POST /optimizar`.
    """
    try:
        datos = cargar_datos()
    except DataLoaderError as err:
        raise HTTPException(status_code=400, detail=str(err))

    supuesto_por_clave = _es_supuesto_por_clave(datos)
    productos = []
    for clave in datos.combinaciones:
        banco, plazo, tramo = clave
        productos.append(
            {
                "clave": clave_a_texto(clave),
                "banco": banco,
                "plazo": plazo,
                "tramo": tramo,
                "tasa_ea": _num_seguro(datos.r[clave]),
                "f_ijk": _num_seguro(datos.f[clave]),
                "min_apertura": _num_seguro(datos.m[clave]),
                "es_supuesto": supuesto_por_clave.get(clave, False),
            }
        )

    return {"total": len(productos), "productos": productos}


def _serializar_rango(rango) -> dict[str, Any]:
    """Serializa un `RangoSensibilidad` a JSON seguro (inf -> null)."""
    return {
        "parametro": rango.parametro,
        "valor_base": _num_seguro(rango.valor_base),
        "limite_inferior": _num_seguro(rango.limite_inferior),
        "limite_superior": _num_seguro(rango.limite_superior),
        "permitido_bajar": _num_seguro(rango.permitido_bajar),
        "permitido_subir": _num_seguro(rango.permitido_subir),
        "interpretacion": rango.interpretacion,
    }


@app.post("/optimizar", summary="Resuelve el MILP para un escenario y devuelve la solución + sensibilidad")
def optimizar(req: OptimizarRequest) -> dict[str, Any]:
    """Construye, resuelve y analiza el modelo para el escenario dado.

    Flujo (reusa íntegramente los módulos de `src/`):
      1. Config override a partir de `get_config()` + parámetros del body.
      2. `cargar_datos(config=...)`; override de tasas en memoria si se envía.
      3. `construir_modelo` + restricciones de tramos + restricciones de riesgo.
      4. `resolver` (CBC).
      5. Si es óptimo: LP restringido -> precios sombra + holgura complementaria
         + rangos de sensibilidad.

    Respuesta:
      - Óptimo: `ok=true` con estado, Z*, objetivo_r, capital_colocado, s0,
        asignacion[], precios_sombra, holgura_complementaria, rangos y la
        advertencia del LP restringido (Req. 4.7).
      - Sin óptimo o sin combinaciones: `ok=false` con estado y un mensaje
        accionable (HTTP 200, no 500).
    """
    # 1) Config override.
    config = _construir_config_override(req)

    # 2) Cargar datos con el config custom.
    try:
        datos = cargar_datos(config=config)
    except DataLoaderError as err:
        raise HTTPException(status_code=400, detail=str(err))

    # Override de tasas en memoria (recalcula f_ijk de las claves afectadas).
    if req.tasas:
        _aplicar_override_tasas(datos, req.tasas)

    # Sin combinaciones utilizables: no hay modelo que resolver.
    if not datos.combinaciones:
        return {
            "ok": False,
            "estado": "SinCombinaciones",
            "mensaje": (
                "No hay combinaciones utilizables (todas las tasas están "
                "vacías). Fije tasas supuestas en data/cdt_productos.csv o "
                "envíelas vía el campo 'tasas' del body."
            ),
            "advertencia_lp_restringido": ADVERTENCIA_LP_RESTRINGIDO,
        }

    # 3) Construir el modelo con todas sus restricciones.
    modelo = construir_modelo(datos)
    agregar_restricciones_tramos(modelo)
    agregar_restricciones_riesgo(modelo)

    # 4) Resolver.
    resultado = resolver(modelo)

    if not resultado.es_optimo:
        return {
            "ok": False,
            "estado": resultado.estado,
            "solver": resultado.solver,
            "mensaje": (
                f"El solver no alcanzó una solución óptima (estado: "
                f"{resultado.estado}). Revise las cotas de liquidez y "
                "concentración frente a los mínimos de apertura: pueden ser "
                "incompatibles entre sí."
            ),
            "advertencia_lp_restringido": ADVERTENCIA_LP_RESTRINGIDO,
        }

    # Asignación óptima legible.
    supuesto_por_clave = _es_supuesto_por_clave(datos)
    asignacion = []
    for clave, monto in sorted(resultado.x.items()):
        banco, plazo, tramo = clave
        r_ijk = datos.r[clave]
        f_ijk = datos.f[clave]
        asignacion.append(
            {
                "clave": clave_a_texto(clave),
                "banco": banco,
                "plazo": plazo,
                "tramo": tramo,
                "monto": _num_seguro(monto),
                "tasa_ea": _num_seguro(r_ijk),
                "f_ijk": _num_seguro(f_ijk),
                "rendimiento": _num_seguro(f_ijk * monto),
                "pct_capital": _num_seguro(monto / datos.A) if datos.A else None,
                "es_supuesto": supuesto_por_clave.get(clave, False),
            }
        )

    # 5) Dualidad y sensibilidad sobre el LP restringido.
    lp = construir_lp_restringido(datos, resultado)
    precios = extraer_precios_sombra(lp)
    holgura = verificar_holgura_complementaria(lp)
    rangos = calcular_rangos_sensibilidad(lp)

    precios_sombra = {
        "estado": precios.estado,
        "es_optimo": precios.es_optimo,
        "objetivo": _num_seguro(precios.objetivo),
        "lambda_capital": _num_seguro(precios.lambda_capital),
        "mu_concentracion": {b: _num_seguro(v) for b, v in precios.mu_concentracion.items()},
        "sigma_liquidez": {e: _num_seguro(v) for e, v in precios.sigma_liquidez.items()},
        "s0_valor": _num_seguro(precios.s0_valor),
        "capital_agotado": precios.capital_agotado,
        "interpretacion": precios.interpretacion,
    }

    holgura_complementaria = {
        "cumple": holgura.cumple,
        "max_violacion": _num_seguro(holgura.max_violacion),
        "tolerancia": _num_seguro(holgura.tolerancia),
        "interpretacion": holgura.interpretacion,
    }

    rangos_serial = {
        "degenerado": rangos.degenerado,
        "metodo": rangos.metodo,
        "advertencia_degeneracion": rangos.advertencia_degeneracion,
        "objetivo_f": {
            clave_a_texto(clave): _serializar_rango(r)
            for clave, r in rangos.objetivo_f.items()
        },
        "rhs": {nombre: _serializar_rango(r) for nombre, r in rangos.rhs.items()},
    }

    return {
        "ok": True,
        "estado": resultado.estado,
        "es_optimo": resultado.es_optimo,
        "solver": resultado.solver,
        "objetivo": _num_seguro(resultado.objetivo),       # Z* (producción f)
        "objetivo_r": _num_seguro(resultado.objetivo_r),   # variante Σ r·x
        "capital_colocado": _num_seguro(resultado.capital_colocado),
        "s0": _num_seguro(resultado.s0),
        "A": _num_seguro(datos.A),
        "asignacion": asignacion,
        "precios_sombra": precios_sombra,
        "holgura_complementaria": holgura_complementaria,
        "rangos": rangos_serial,
        "advertencia_lp_restringido": ADVERTENCIA_LP_RESTRINGIDO,
    }


# ===========================================================================
# Simulación de liquidez (escalera de CDT): barrido corto vs rendimiento
# ===========================================================================
def _concentracion_override(base_conc: dict, concentracion_max: Any) -> dict:
    """Resuelve el override de concentración (float global o dict por banco).

    Reutiliza la misma semántica de `_construir_config_override`: un float
    aplica a todos los bancos; un dict sobrescribe los bancos indicados.
    """
    if concentracion_max is None:
        return dict(base_conc)
    if isinstance(concentracion_max, (int, float)):
        return {banco: float(concentracion_max) for banco in base_conc}
    if isinstance(concentracion_max, dict):
        nuevo = dict(base_conc)
        for banco, valor in concentracion_max.items():
            if banco not in nuevo:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Banco '{banco}' en concentracion_max no pertenece al "
                        f"conjunto de bancos: {sorted(nuevo)}."
                    ),
                )
            nuevo[banco] = float(valor)
        return nuevo
    raise HTTPException(
        status_code=400,
        detail="concentracion_max debe ser un número o un dict {banco: fracción}.",
    )


@app.post(
    "/simular-liquidez",
    summary="Barrido de liquidez (escalera de CDT): costo de oportunidad corto vs largo",
)
def simular_liquidez(req: SimularLiquidezRequest) -> dict[str, Any]:
    """Resuelve el MILP para varios niveles de liquidez y los compara.

    Caso de uso ("escalera" de CDT): el inversionista quiere mantener parte del
    capital disponible a corto plazo (≤180 días) y colocar el resto a plazos
    largos, que rinden más por periodo. Este endpoint barre varios niveles de
    exigencia de liquidez a corto (`L_corto`/`U_corto`) y, para cada uno, resuelve
    el modelo y reporta la ganancia `Z*`, el reparto corto/largo y el **costo de
    oportunidad** frente al primer escenario (referencia, normalmente "Libre").

    Reusa íntegramente el pipeline de `src/` (mismo modelo que `/optimizar`); solo
    cambia la cota de liquidez entre escenarios. Si se omiten `escenarios`, usa un
    barrido por defecto (libre, 10%, 20%, 30%, 40% a corto).

    Respuesta: `A`, `concentracion_max` efectiva, lista `escenarios` (cada uno con
    etiqueta, cotas, estado, `objetivo`/Z*, rendimiento efectivo %, montos corto y
    largo, nº de CDT y `costo_oportunidad` vs la referencia) y la advertencia de LP
    restringido. Si algún escenario no es óptimo, ese elemento trae `ok=false` con
    su estado; los demás se resuelven igual.
    """
    base = config_modulo.get_config()

    # Config común (capital y concentración) para todos los escenarios.
    A = float(req.A) if req.A is not None else float(base["A"])
    concentracion = _concentracion_override(base["concentracion_max"], req.concentracion_max)
    archivo_datos = req.archivo_datos  # None => archivo por defecto del proyecto

    # Escenarios a barrer: los del request o el barrido por defecto.
    if req.escenarios:
        escenarios = [
            (e.etiqueta or f"L={e.L_corto}/U={e.U_corto}", e.L_corto, e.U_corto)
            for e in req.escenarios
        ]
    else:
        escenarios = list(_BARRIDO_LIQUIDEZ_DEFECTO)

    resultados: list[dict[str, Any]] = []
    z_referencia: Optional[float] = None  # Z* del primer escenario óptimo.

    for etiqueta, l_corto, u_corto in escenarios:
        config = {
            "A": A,
            "tramos": base["tramos"],
            "concentracion_max": dict(concentracion),
            "liquidez": {
                "L_corto": l_corto,
                "U_corto": u_corto,
                "L_largo": None,
                "U_largo": None,
            },
        }

        try:
            datos = cargar_datos(archivo_datos=archivo_datos, config=config)
        except DataLoaderError as err:
            raise HTTPException(status_code=400, detail=str(err))

        if not datos.combinaciones:
            resultados.append(
                {
                    "etiqueta": etiqueta,
                    "L_corto": l_corto,
                    "U_corto": u_corto,
                    "ok": False,
                    "estado": "SinCombinaciones",
                    "mensaje": (
                        "No hay combinaciones utilizables (tasas vacías). Use "
                        "archivo_datos='escenario_supuesto.csv' o cargue tasas."
                    ),
                }
            )
            continue

        modelo = construir_modelo(datos)
        agregar_restricciones_tramos(modelo)
        agregar_restricciones_riesgo(modelo)
        resultado = resolver(modelo)

        if not resultado.es_optimo:
            resultados.append(
                {
                    "etiqueta": etiqueta,
                    "L_corto": l_corto,
                    "U_corto": u_corto,
                    "ok": False,
                    "estado": resultado.estado,
                    "mensaje": (
                        "Escenario infactible/no óptimo: la exigencia de liquidez "
                        "puede ser incompatible con la concentración por banco."
                    ),
                }
            )
            continue

        # Reparto corto (≤180) vs largo (>180) y nº de CDT activos.
        corto = sum(v for c, v in resultado.x.items() if c[1] <= 180)
        largo = sum(v for c, v in resultado.x.items() if c[1] > 180)
        rend_efectivo = (resultado.objetivo / A * 100.0) if (resultado.objetivo and A) else None

        # El primer escenario óptimo fija la referencia para el costo de oportunidad.
        if z_referencia is None and resultado.objetivo is not None:
            z_referencia = resultado.objetivo
        costo_oportunidad = (
            _num_seguro(z_referencia - resultado.objetivo)
            if (z_referencia is not None and resultado.objetivo is not None)
            else None
        )

        resultados.append(
            {
                "etiqueta": etiqueta,
                "L_corto": l_corto,
                "U_corto": u_corto,
                "ok": True,
                "estado": resultado.estado,
                "objetivo": _num_seguro(resultado.objetivo),
                "rendimiento_efectivo_pct": _num_seguro(rend_efectivo),
                "monto_corto": _num_seguro(corto),
                "monto_largo": _num_seguro(largo),
                "num_cdt": len(resultado.x),
                "costo_oportunidad": costo_oportunidad,
            }
        )

    return {
        "ok": True,
        "A": _num_seguro(A),
        "concentracion_max": {b: _num_seguro(v) for b, v in concentracion.items()},
        "archivo_datos": archivo_datos or "(por defecto del proyecto)",
        "referencia": "primer escenario (costo_oportunidad = Z*_ref − Z*_escenario)",
        "escenarios": resultados,
        "advertencia_lp_restringido": ADVERTENCIA_LP_RESTRINGIDO,
    }
