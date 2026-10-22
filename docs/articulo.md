# Optimización de la Inversión en Certificados de Depósito a Término (CDT) mediante Programación Lineal Entera Mixta

**Autores:** Samuel Herrera Galvis, León, Emmanuel

**Institución:** Universidad EAFIT — Curso Optimización 1

<!--
ESTRUCTURA DEL ARTÍCULO (Requisito 5.1)
Orden exigido de las 8 secciones:
  1. Resumen
  2. Introducción
  3. Revisión de Literatura
  4. Metodología
  5. Resultados
  6. Discusión y Análisis de Sensibilidad
  7. Conclusiones
  8. Referencias

ESTADO DE REDACCIÓN POR SUB-TAREA:
  - 9.1: esqueleto con las 8 secciones en orden. [HECHO]
  - 9.2: redactar Introducción y Revisión de Literatura. [HECHO]
  - 9.3: redactar Metodología con ecuaciones explícitas. [HECHO]
  - 9.4: redactar Resultados y Discusión con salidas de Python; completar
         Resumen y Conclusiones. [HECHO]
-->

---

## 1. Resumen

La asignación de excedentes de tesorería entre Certificados de Depósito a
Término (CDT) de distintos bancos, plazos y tramos de monto es un problema de
decisión combinatorio que difícilmente se resuelve "a ojo". Este trabajo
formula esa asignación como un modelo de Programación Lineal Entera Mixta
(MILP) que maximiza el rendimiento efectivo total de un capital `A` colocado en
CDT de cinco entidades colombianas, usando como coeficiente objetivo el factor
de rendimiento del periodo de tenencia `f_ijk = (1 + r_ijk)^(j/360) − 1` para
comparar correctamente plazos heterogéneos. El modelo incorpora tasas
escalonadas por monto mediante variables binarias de activación de tramo y
restricciones realistas de presupuesto, diversificación por banco, montos
mínimos de apertura y liquidez. Sobre la solución entera se construye un
Programa Lineal (LP) restringido —fijando las binarias en su valor óptimo— que
habilita un análisis riguroso de dualidad y sensibilidad, tal como exige el
curso. El modelo se implementó en Python con PuLP (solver CBC) en módulos
separados de carga de datos, modelo, resolución, sensibilidad y reporte. Como
ninguna fuente pública desagrega las tasas por los tres tramos de monto, los
resultados se generan sobre un escenario de tasas explícitamente supuestas, no
reales. En ese escenario, el óptimo concentra el capital en productos a 720 días
—los de mayor rendimiento efectivo pese a no tener la tasa anual más alta— y
agota el capital disponible. El análisis dual arroja un precio sombra del
capital de ≈ 0,2288, topes de concentración activos con costo de oportunidad
cuantificado, holgura complementaria verificada (`(x*)^T s* = 0`) y rangos de
estabilidad que acotan la robustez de la cartera.

**Palabras clave:** optimización de inversiones; CDT; programación lineal entera
mixta; dualidad; análisis de sensibilidad; gestión de tesorería.

---

## 2. Introducción

La gestión de tesorería es una de las funciones financieras más sensibles de cualquier organización: consiste en decidir cómo colocar el capital disponible de modo que conserve valor, mantenga la liquidez necesaria para la operación y, al mismo tiempo, genere el mayor rendimiento posible dentro de un nivel de riesgo tolerable. En el contexto colombiano, uno de los instrumentos más utilizados para la colocación de excedentes de caja es el Certificado de Depósito a Término (CDT), un título de renta fija emitido por una entidad financiera a cambio de un depósito de dinero por un plazo previamente pactado, con una tasa de interés fijada desde la apertura [1]. El CDT ofrece una rentabilidad conocida de antemano, no está expuesto a riesgo de mercado durante su vigencia y, cuando la entidad emisora está inscrita en el Fondo de Garantías de Instituciones Financieras (Fogafín), cuenta con un seguro de depósito que protege al ahorrador hasta cierto monto por depositante y por entidad [2]. Estas características lo convierten en una alternativa natural para la administración de excedentes de tesorería que buscan rentabilidad superior a la de una cuenta de ahorros sin asumir volatilidad de precios.

El mercado colombiano de CDT es amplio y heterogéneo. Las entidades vigiladas por la Superintendencia Financiera de Colombia ofrecen productos a distintos plazos —típicamente de 30, 60, 90, 180 y 360 días, con opciones a mayor horizonte— y el Banco de la República calcula y publica las tasas de captación como promedio ponderado por monto de las operaciones transadas [3][4]. En la práctica, la tasa ofrecida a un inversionista no es única: depende de la entidad, del plazo y, con frecuencia, del monto depositado, pues muchos bancos aplican tasas escalonadas que mejoran a medida que el capital colocado supera determinados umbrales. Esta estructura escalonada, sumada a la diversidad de emisores y plazos, genera un espacio de decisión combinatorio en el que elegir "a ojo" la mejor colocación es, en el mejor de los casos, subóptimo.

El problema que aborda este trabajo es, por tanto, el de **asignar un capital total `A` entre un conjunto de productos CDT ofrecidos por varias entidades, a distintos plazos y con tasas escalonadas por tramos de monto, de forma que se maximice el rendimiento total al vencimiento sujeto a restricciones realistas de riesgo y liquidez**. Las restricciones recogen límites de diversificación por entidad (evitar concentrar el capital en un solo banco), montos mínimos de apertura, la lógica de que cada producto activa a lo sumo un tramo de tasa, y cotas de reparto entre plazos cortos y largos que reflejan la política de liquidez de la tesorería. La presencia de tramos escalonados y de montos mínimos introduce decisiones de tipo "todo o nada" que exigen variables binarias, de modo que el problema se formula de forma natural como un modelo de Programación Lineal Entera Mixta (MILP).

Los objetivos concretos de este trabajo son: (i) formular un modelo MILP que maximice el rendimiento efectivo total del capital colocado en CDT, usando como coeficiente objetivo el factor de rendimiento del periodo de tenencia `f_ijk = (1 + r_ijk)^(j/360) − 1` para comparar correctamente plazos heterogéneos a partir de la Tasa Efectiva Anual `r_ijk`; (ii) incorporar la lógica de tasas escalonadas por tramos mediante variables binarias de activación y las restricciones de riesgo y liquidez antes descritas; (iii) resolver el modelo con herramientas de código abierto en Python y presentar la asignación óptima de capital por banco, plazo y tramo; y (iv) realizar un análisis de dualidad y sensibilidad —sobre el LP que resulta de fijar las binarias en su valor óptimo— para interpretar económicamente los precios sombra del capital y de las restricciones de concentración, verificar el teorema de holgura complementaria y calcular los rangos de estabilidad de la base óptima. Con ello, el trabajo articula un problema aplicado de tesorería con los contenidos de dualidad y sensibilidad del curso de Optimización 1.

---

## 3. Revisión de Literatura

### 3.1 Modelos de selección de portafolios

El estudio formal de la asignación de capital entre activos arranca con el trabajo seminal de Markowitz sobre selección de portafolios, que plantea el problema como un balance entre el rendimiento esperado y el riesgo medido por la varianza del portafolio [5]. El modelo media-varianza de Markowitz es un problema de optimización cuadrática: maximizar el rendimiento esperado para un nivel de varianza dado, o minimizar la varianza para un rendimiento objetivo, sujeto a que los pesos de inversión sumen la unidad. De este enfoque se derivan la frontera eficiente y buena parte de la teoría moderna de portafolios.

Para instrumentos de renta fija como los CDT, donde la tasa se pacta al inicio y no hay riesgo de precio durante la vigencia del título, la componente de varianza del retorno pierde protagonismo frente a restricciones operativas y de política: diversificación por emisor, montos mínimos, cupos y horizontes de liquidez. En estos contextos es habitual sustituir o aproximar el término cuadrático por formulaciones lineales o lineales enteras mixtas, que resultan más tratables y permiten incorporar directamente decisiones discretas. La literatura de optimización para selección de portafolios con restricciones de cardinalidad, lotes mínimos (minimum buy-in) y umbrales de inversión muestra precisamente esta transición: dichas condiciones se modelan con variables binarias, convirtiendo el problema en un MILP [7]. El modelo propuesto en este trabajo se inscribe en esa línea: conserva la idea de diversificación de Markowitz a través de cotas de concentración por banco, pero prescinde del término de varianza —innecesario para un portafolio de CDT de rentabilidad pactada— y sitúa el énfasis en la estructura entera de las decisiones.

### 3.2 La notación `R||A_max` de secuenciación y su analogía con el problema

En la teoría de secuenciación y programación de tareas (scheduling) se emplea la notación de tres campos `α | β | γ` introducida por Graham, Lawler, Lenstra y Rinnooy Kan para clasificar problemas según el entorno de máquinas (`α`), las restricciones del proceso (`β`) y el criterio de optimización (`γ`) [8]. En esa taxonomía, `R` denota máquinas paralelas no relacionadas (unrelated parallel machines), es decir, máquinas en las que el tiempo de procesamiento de una tarea depende de la máquina a la que se asigne; el campo `γ` especifica la función objetivo, como el makespan `C_max` (minimizar el instante de finalización máximo) [9]. La variante referida en el enunciado del curso como `R||A_max` corresponde conceptualmente a un entorno de máquinas paralelas no relacionadas en el que se controla una magnitud máxima del campo de optimización.

La analogía con el problema de inversión en CDT es ilustrativa y motiva el encuadre del curso. Los "bancos" (o las combinaciones banco–plazo) hacen las veces de **máquinas no relacionadas**: una misma porción de capital produce un rendimiento distinto según la entidad y el plazo al que se asigne, igual que una tarea toma tiempos distintos en máquinas distintas. Asignar capital a productos es, estructuralmente, el mismo tipo de problema de asignación de un recurso divisible entre alternativas con coeficientes dependientes de la alternativa. La diferencia esencial está en el objetivo y el signo: la secuenciación `R||...` típicamente **minimiza** un máximo (por ejemplo, el makespan), mientras que el problema de tesorería **maximiza** un rendimiento agregado. Aun así, el paralelismo justifica por qué el problema se puede leer con las herramientas de asignación óptima sobre máquinas no relacionadas y refuerza su naturaleza combinatoria. Un tratamiento sistemático de estos modelos y de la notación de tres campos se encuentra en Pinedo [9].

### 3.3 Programación entera mixta y estructuras por tramos (piecewise)

La programación lineal, cuyo desarrollo algorítmico moderno se asocia al método simplex de Dantzig, es el marco natural para problemas de asignación de recursos con objetivo y restricciones lineales [6]. Cuando algunas decisiones son indivisibles o condicionales —activar o no un producto, respetar un monto mínimo, elegir un único tramo de tasa— se requieren variables enteras o binarias, dando lugar a la Programación Lineal Entera Mixta (MILP), cuyo tratamiento teórico y algorítmico (ramificación y acotamiento, planos de corte, formulaciones fuertes) se expone de forma estándar en Wolsey [10] y en Nemhauser y Wolsey [11].

Un recurso de modelado central para este trabajo es la representación de funciones y relaciones **por tramos (piecewise)**. Las tasas escalonadas por monto de los CDT definen, de hecho, una relación rendimiento–monto que cambia por segmentos: cada tramo `k` tiene una cota inferior `L_k` y superior `U_k` y una tasa asociada `r_ijk`. Esta estructura se modela con una variable binaria de activación `z_ijk` por tramo y restricciones de vínculo del tipo `L_k · z_ijk ≤ x_ijk ≤ U_k · z_ijk`, junto con la condición de que a lo sumo un tramo quede activo por producto `(i, j)`. Estas son las técnicas clásicas de linealización de funciones por tramos y de modelado de disyunciones y costos fijos con binarias documentadas en la literatura de MILP [10][11], y en textos aplicados de modelado como Williams [12]. El modelo de este trabajo combina los tres hilos revisados: la lógica de diversificación heredada de la selección de portafolios, el encuadre de asignación sobre alternativas no relacionadas afín a `R||A_max`, y la maquinaria de MILP por tramos para representar fielmente las tasas escalonadas del mercado colombiano de CDT.

---

## 4. Metodología

La metodología formaliza el problema de asignación de capital en CDT como un modelo de Programación Lineal Entera Mixta (MILP) y, sobre su solución entera, construye un Programa Lineal (LP) restringido que habilita el análisis riguroso de dualidad y sensibilidad. Esta subsección presenta, en orden, los conjuntos e índices, los parámetros, las variables de decisión, la función objetivo, las ocho familias de restricciones y, finalmente, la formulación explícita del Primal y del Dual del LP restringido con sus condiciones de holgura complementaria.

### 4.1 Conjuntos e índices

- $I$: conjunto de **bancos** emisores, con índice $i \in I$.
- $J$: conjunto de **plazos** en días, con índice $j \in J$. En este trabajo $J = \{30, 60, 90, 180, 360, 540, 720\}$.
- $K$: conjunto de **tramos de monto**, con índice $k \in K = \{1, 2, 3\}$.

Cada combinación $(i, j, k)$ representa un producto concreto: un CDT del banco $i$, al plazo $j$, en el tramo de monto $k$.

### 4.2 Parámetros

- $A$: capital total disponible para invertir.
- $r_{ijk}$: **Tasa Efectiva Anual** (E.A.) de la combinación $(i, j, k)$.
- $f_{ijk}$: **factor de rendimiento efectivo del periodo de tenencia** (coeficiente objetivo), derivado de la tasa E.A. y del plazo $j$:

$$
f_{ijk} = (1 + r_{ijk})^{\,j/360} - 1 .
$$

- $L_k,\ U_k$: cota inferior y superior del tramo $k$. El último tramo es abierto por arriba, $U_3 = \infty$ (se modela sin cota superior o con un valor grande, p. ej. $A$).
- $m_{ij}$: monto **mínimo de apertura** del banco $i$ al plazo $j$.
- $p_i$: fracción **máxima de concentración** del capital admisible en el banco $i$, con $0 < p_i \le 1$.
- $disp_{ijk} \in \{0, 1\}$: indicador de **disponibilidad**; vale 1 si el producto $(i, j, k)$ se ofrece efectivamente.
- $J_{\text{corto}} = \{\, j \in J : j \le 180 \,\}$ y $J_{\text{largo}} = \{\, j \in J : j > 180 \,\}$: particiones de **liquidez** del conjunto de plazos.
- $L_{\text{corto}},\ U_{\text{corto}},\ L_{\text{largo}},\ U_{\text{largo}}$: fracciones mínima y máxima de $A$ a colocar en plazos cortos y largos (política de tesorería). Se dejan **parametrizadas**; cuando una cota no se define (valor nulo), la restricción correspondiente se **desactiva** (equivale a $0$ para la inferior y a $1$ para la superior).

**Justificación del coeficiente $f_{ijk}$.** La tasa $r_{ijk}$ es una Tasa Efectiva Anual, de modo que usar directamente $\sum r_{ijk}\,x_{ijk}$ valoraría igual un peso inmovilizado 30 días y uno inmovilizado 720 días, sesgando la solución hacia plazos cortos de alta tasa sin reconocer el tiempo real de inmovilización del capital. El factor $f_{ijk}$ convierte la tasa E.A. al rendimiento efectivo del periodo de tenencia, que es la magnitud correcta para sumar retornos entre plazos heterogéneos. Como $f_{ijk}$ es una constante **precalculada**, el objetivo sigue siendo **lineal en $x_{ijk}$** y la teoría dual conserva plena validez sobre el LP restringido.

### 4.3 Variables de decisión

- $x_{ijk} \ge 0$: **monto** de capital asignado a la combinación $(i, j, k)$ (variable continua).
- $z_{ijk} \in \{0, 1\}$: variable **binaria** de activación; vale 1 si se activa el tramo $k$ del producto $(i, j)$. (En el enunciado del curso esta binaria figura como $y_{ijk}$; es la misma variable.)
- $s_0 \ge 0$: **holgura de no-inversión**; capital que queda sin colocar. Permite mantener la restricción de capital como igualdad sin arriesgar la infactibilidad del modelo.

### 4.4 Función objetivo

Se maximiza el **valor efectivo al vencimiento** del capital colocado. El coeficiente de cada producto es el factor de rendimiento efectivo $f_{ijk}$:

$$
\max\ Z \;=\; \sum_{i \in I} \sum_{j \in J} \sum_{k \in K} f_{ijk}\, x_{ijk} .
$$

> **Variante didáctica.** Para contraste puede reportarse también el objetivo lineal directo $\sum_{i}\sum_{j}\sum_{k} r_{ijk}\, x_{ijk}$, que acumula la tasa E.A. sin ajustar por plazo. El modelo expone ambos coeficientes; el de producción es $f_{ijk}$, por la justificación de la subsección 4.2.

### 4.5 Restricciones

El modelo incorpora ocho familias de restricciones.

**(1) Inversión total del capital (igualdad con holgura de no-inversión).**

$$
\sum_{i \in I} \sum_{j \in J} \sum_{k \in K} x_{ijk} + s_0 = A, \qquad s_0 \ge 0 .
$$

La igualdad modela la intención real de la tesorería —colocar todo el capital $A$— y dota al precio sombra $\lambda$ de esta restricción de su interpretación económica más rica (el retorno marginal de un peso adicional de capital). La holgura $s_0$ garantiza factibilidad: si los mínimos de apertura y la concentración impiden sumar exactamente $A$, $s_0$ absorbe y reporta el capital no colocado.

**(2) Concentración máxima por banco (diversificación).**

$$
\sum_{j \in J} \sum_{k \in K} x_{ijk} \le p_i \cdot A, \qquad \forall\, i \in I .
$$

**(3) Activación de tramo (vínculo $x$–$z$).**

$$
L_k \cdot z_{ijk} \le x_{ijk} \le U_k \cdot z_{ijk}, \qquad \forall\, (i, j, k) .
$$

Si $z_{ijk} = 0$, el vínculo fuerza $x_{ijk} = 0$; si $z_{ijk} = 1$, el monto queda confinado al rango $[L_k, U_k]$ del tramo.

**(4) Monto mínimo de apertura.**

$$
x_{ijk} \ge m_{ij} \cdot z_{ijk}, \qquad \forall\, (i, j, k) .
$$

**(5) A lo sumo un tramo por producto $(i, j)$.**

$$
\sum_{k \in K} z_{ijk} \le 1, \qquad \forall\, (i, j) .
$$

**(6) Liquidez (reparto corto vs. largo plazo).**

$$
L_{\text{corto}} \cdot A \le \sum_{i \in I} \sum_{j \in J_{\text{corto}}} \sum_{k \in K} x_{ijk} \le U_{\text{corto}} \cdot A ,
$$

$$
L_{\text{largo}} \cdot A \le \sum_{i \in I} \sum_{j \in J_{\text{largo}}} \sum_{k \in K} x_{ijk} \le U_{\text{largo}} \cdot A .
$$

Estas cotas limitan la exposición a cada horizonte de liquidez para equilibrar disponibilidad de caja y retorno. Los coeficientes se dejan parametrizados como política de tesorería; cada cota se activa solo si se define.

**(7) Disponibilidad.**

$$
z_{ijk} \le disp_{ijk}, \qquad \forall\, (i, j, k) .
$$

**(8) No negatividad e integralidad.**

$$
x_{ijk} \ge 0, \qquad s_0 \ge 0, \qquad z_{ijk} \in \{0, 1\}, \qquad \forall\, (i, j, k) .
$$

### 4.6 Estrategia MILP + LP restringido para dualidad y sensibilidad

En un MILP las variables binarias rompen la convexidad del problema, por lo que los precios sombra y los rangos de sensibilidad **no gozan de la garantía de dualidad fuerte**: la teoría dual que los sustenta es válida únicamente para un LP. Para obtener una interpretación económica rigurosa se adopta la siguiente estrategia en dos etapas:

```
┌─────────────────────┐     fija z = z*      ┌──────────────────────┐
│   MILP (asignación)  │ ───────────────────► │  LP restringido       │
│  x_ijk, z_ijk        │                      │  solo x_ijk activas   │
│  → solución óptima    │                      │  → dual, precios       │
│                      │                      │    sombra, rangos      │
└─────────────────────┘                      └──────────────────────┘
```

1. Se resuelve el MILP completo y se obtiene la solución entera óptima $z^*_{ijk}$.
2. Se **fijan** las binarias en su valor óptimo, $z_{ijk} = z^*_{ijk}$, y se conservan únicamente las combinaciones **activas** $Act = \{\, (i, j, k) : z^*_{ijk} = 1 \,\}$, junto con la holgura $s_0$. El problema residual es un LP puramente lineal, sobre el que la dualidad fuerte es válida.

Al fijar $z^* = 1$, las restricciones que dependían de las binarias se transforman en cotas constantes de las variables continuas: el vínculo de tramo $L_k \le x_{ijk} \le U_k$ y el mínimo de apertura $x_{ijk} \ge m_{ij}$ se combinan en $\max(L_k, m_{ij}) \le x_{ijk} \le U_k$ (impuesto como cotas inferior/superior de la variable), mientras que "a lo sumo un tramo" ($\sum_k z \le 1$) y la disponibilidad ($z \le disp$) quedan satisfechas por $z^*$ y no aportan filas al LP. **Toda la sensibilidad y todos los precios sombra reportados se refieren a este LP restringido, no al MILP original**; el informe lo advierte explícitamente.

### 4.7 Primal del LP restringido (P)

Sea $x = (x_{ijk})_{(i,j,k)\in Act}$ el vector de montos continuos de las combinaciones activas, más la holgura $s_0 \ge 0$. El Primal es:

$$
\text{(P)}\quad
\begin{aligned}
\max\ \ & \sum_{(i,j,k)\in Act} f_{ijk}\, x_{ijk} \\[2pt]
\text{s.a.}\quad
& \sum_{(i,j,k)\in Act} x_{ijk} + s_0 = A && (\lambda) \\
& \sum_{(j,k):(i,j,k)\in Act} x_{ijk} \le p_i \cdot A && (\mu_i \ge 0),\ \forall\, i \\
& \sum_{(i,j,k)\in Act,\ j\in J_{\text{corto/largo}}} x_{ijk} \ge L_\cdot \cdot A && (\sigma^- \ge 0) \\
& \sum_{(i,j,k)\in Act,\ j\in J_{\text{corto/largo}}} x_{ijk} \le U_\cdot \cdot A && (\sigma^+ \ge 0) \\
& \text{cota}^{\text{inf}}_{ijk} \le x_{ijk} \le \text{cota}^{\text{sup}}_{ijk} && (\nu_{ijk}) \\
& x_{ijk} \ge 0,\quad s_0 \ge 0 &&
\end{aligned}
$$

donde $\text{cota}^{\text{inf}}_{ijk} = \max(L_k, m_{ij})$ y $\text{cota}^{\text{sup}}_{ijk} = U_k$ (o $A$ si el tramo es abierto por arriba). Entre paréntesis se anotan las variables duales asociadas a cada familia de restricciones: $\lambda$ para el capital, $\mu_i$ para la concentración, $\sigma^\pm$ para las cotas de liquidez y $\nu_{ijk}$ para las cotas de cada variable (mínimo de apertura y límites de tramo). Las cotas de tramo y el mínimo de apertura se imponen como cotas de la variable, por lo que su precio sombra $\nu_{ijk}$ corresponde al costo reducido (reduced cost) de $x_{ijk}$.

### 4.8 Dual del LP restringido (D)

El Dual asocia una variable a cada restricción del Primal y minimiza el costo imputado de los recursos. Con $\lambda$ **libre** (por corresponder a una igualdad) y $\mu_i, \sigma^+, \sigma^- \ge 0$:

$$
\text{(D)}\quad
\begin{aligned}
\min\ \ & A\,\lambda \;+\; \sum_{i} (p_i A)\,\mu_i \;+\; \sum (U_\cdot A)\,\sigma^+ \;-\; \sum (L_\cdot A)\,\sigma^- \;+\; (\text{términos de cotas } \nu) \\[2pt]
\text{s.a.}\quad
& \lambda + \mu_{i(ijk)} + \sigma_{\text{liq}(ijk)} + \nu_{ijk} \;\ge\; f_{ijk} && \forall\, (i,j,k)\in Act \\
& \lambda \;\ge\; 0 && (\text{fila de } s_0,\ \text{coef. } 0 \text{ en P}) \\
& \mu_i \ge 0,\quad \sigma^+ \ge 0,\quad \sigma^- \ge 0,\quad \lambda\ \text{libre} &&
\end{aligned}
$$

La restricción dual exige que el **precio compuesto** de los recursos que consume cada peso colocado en $(i, j, k)$ cubra al menos su rendimiento $f_{ijk}$. En la base óptima, esta desigualdad se vuelve igualdad para las variables básicas, lo que constituye la condición de holgura complementaria.

**Interpretación económica de los precios sombra.**

- $\lambda^*$ (**capital**): retorno marginal de una unidad monetaria adicional de capital $A$; cuánto crecería el objetivo $\sum f_{ijk}\,x_{ijk}$ con un peso más para invertir, manteniendo óptima la base.
- $\mu_i^*$ (**concentración** del banco $i$): costo de oportunidad del tope $p_i A$. Si $\mu_i^* > 0$, el tope del banco $i$ está activo y limita; relajarlo permitiría colocar un peso más en esa entidad y ganar $\mu_i^*$ de rendimiento.
- $\sigma^*$ (**liquidez** corto/largo): costo o valor marginal de las cotas de reparto entre horizontes; mide cuánto cuesta en rendimiento la exigencia de mantener cierta fracción de $A$ en plazos cortos o largos.

### 4.9 Holgura complementaria y relación $s_0^*\leftrightarrow\lambda^*$

En el óptimo del par Primal–Dual se cumple la condición de **holgura complementaria**, que sobre el LP restringido se expresa como

$$
(x^*)^{\mathsf T} s^* = 0 ,
$$

es decir, el producto de cada variable primal por la holgura de su restricción complementaria es nulo (dentro de una tolerancia numérica, p. ej. $10^{-6}$). Esto se descompone en dos familias de términos: por restricción, $slack_c \cdot \pi_c = 0$ (una restricción con holgura tiene precio sombra nulo); y por variable, $dj_v \cdot (v - \text{cota activa}) = 0$ (una variable estrictamente dentro de sus cotas tiene costo reducido nulo).

La holgura de no-inversión $s_0$ entra en la restricción de capital con coeficiente $0$ en el objetivo, de modo que su condición dual es $\lambda \ge 0$ y la complementariedad impone $s_0^* \cdot \lambda^* = 0$:

- Si $s_0^* > 0$ (**sobró capital** sin colocar), entonces necesariamente $\lambda^* = 0$: tener más capital no agrega retorno, pues ni siquiera se colocó todo el disponible; son las restricciones activas de concentración, liquidez o tramos —no la escasez de capital— las que limitan la solución.
- Si $s_0^* = 0$ (**capital agotado**), entonces $\lambda^*$ puede ser positivo y revela el valor marginal del capital: cada peso adicional sí se colocaría y produciría ese rendimiento extra.

Sobre este mismo LP restringido se calculan, finalmente, los **rangos de sensibilidad**: el intervalo de variación de cada coeficiente objetivo $f_{ijk}$ y de cada término del lado derecho $b$ (capital $A$ y topes $p_i A$) dentro del cual la base óptima se mantiene y los precios sombra permanecen constantes. La interpretación y los valores numéricos de estos precios sombra y rangos se desarrollan en la Sección 6.

---

## 5. Resultados

> **Nota sobre los datos de esta sección (cero invención de datos).** La matriz
> real `data/cdt_productos.csv` deja la tasa `tasa_ea` **vacía** en las 105
> combinaciones `(i, j, k)`, porque ninguna fuente pública consultada desagrega
> la tasa por los tres tramos de monto del spec (los bancos cotizan el CDT por
> plazo, no por esos tramos). En consecuencia, ejecutar el modelo sobre los
> datos reales no produce asignación: el flujo termina de forma controlada
> pidiendo que se fijen tasas supuestas explícitas. Para obtener resultados
> numéricos **reproducibles y generados por el propio modelo** —no cifras
> escritas a mano— todos los números de esta sección provienen de un
> **escenario ilustrativo de tasas supuestas**, `data/escenario_supuesto.csv`,
> en el que las 90 combinaciones disponibles tienen `es_supuesto = True` y una
> tasa construida con una regla declarada (`base_banco[i] + ajuste_plazo[j] +
> prima_tramo[k]`, ver `data/generar_escenario_supuesto.py`). **Estas tasas no
> son tasas reales de mercado** y no deben interpretarse como tales; son un
> supuesto didáctico para ejercitar el modelo de punta a punta (ver la nota de
> la Sección 8).

### 5.1 Reproducibilidad

Los resultados se obtienen ejecutando el pipeline real del proyecto
(`cargar_datos → construir_modelo → agregar_restricciones_* → resolver →
construir_lp_restringido → extraer_precios_sombra →
verificar_holgura_complementaria → calcular_rangos_sensibilidad`) sobre el
escenario supuesto. La secuencia reproducible en Windows/PowerShell con Python
es:

```powershell
# 1. (Re)generar el escenario ilustrativo de tasas supuestas
python data\generar_escenario_supuesto.py

# 2. Resolver sobre el escenario (apuntando el loader a ese CSV)
#    y producir el informe de dualidad/sensibilidad en results/
python -c "import sys; sys.path.insert(0,'src'); from data_loader import cargar_datos; \
from model import construir_modelo, agregar_restricciones_tramos, agregar_restricciones_riesgo; \
from solver import resolver; \
d=cargar_datos(archivo_datos='escenario_supuesto.csv'); \
m=construir_modelo(d); agregar_restricciones_tramos(m); agregar_restricciones_riesgo(m); \
print(resolver(m).objetivo)"
```

El solver reportado es **CBC** (el que acompaña a PuLP), y el estado de todas
las corridas de esta sección es `Optimal`. El objetivo de producción es el
rendimiento efectivo del periodo `Z = Σ f_ijk·x_ijk` (Sección 4.4).

### 5.2 Escenario base y solución óptima (Req. 5.5)

El escenario base usa capital `A = 100.000.000`, concentración máxima uniforme
`p_i = 0,40` para los cinco bancos, los tres tramos del spec y **sin** cotas de
liquidez activas (las cuatro quedan en `None`, por el principio de no inventar
política de tesorería). De las 90 combinaciones disponibles, el óptimo coloca
**todo** el capital (`s_0* = 0`) en tres productos, todos a **720 días** y en el
**tramo 2** de monto:

| Banco | Plazo (días) | Tramo | Monto `x*` (COP) | `r_ijk` (E.A.) | `f_ijk` (periodo) | Rendimiento `f·x*` (COP) | % de `A` |
| --- | ---: | :---: | ---: | ---: | ---: | ---: | ---: |
| Bancolombia | 720 | 2 | 20.000.000,00 | 10,85 % | 22,8772 % | 4.575.445,00 | 20,00 % |
| Davivienda | 720 | 2 | 40.000.000,00 | 11,10 % | 23,4321 % | 9.372.840,00 | 40,00 % |
| Nu Bank | 720 | 2 | 40.000.000,00 | 10,90 % | 22,9881 % | 9.195.240,00 | 40,00 % |
| **Total** | | | **100.000.000,00** | | | **23.143.525,00** | **100,00 %** |

- **Valor objetivo** `Z* = Σ f_ijk·x*_ijk = 23.143.525,00 COP`: el rendimiento
  efectivo total acumulado a 720 días del capital colocado (≈ 23,14 % sobre `A`).
- **Capital no colocado** `s_0* = 0`: se invirtió el 100 % del capital
  disponible; no quedó holgura de no-inversión.
- **Variante didáctica** `Σ r_ijk·x*_ijk = 10.970.000,00 COP`: la misma solución
  valorada con la tasa E.A. "plana" (sin ajustar por el horizonte de tenencia).
  El contraste es grande (≈ 23,14 % vs. ≈ 10,97 %) y precisamente ilustra por
  qué el objetivo correcto para comparar plazos heterogéneos es `f_ijk` y no
  `r_ijk`: `f` reconoce que el capital a 720 días está inmovilizado dos años y
  capitaliza en ese horizonte, mientras que `r` reporta solo la tasa anual.

**Por qué 720 días y tramo 2.** El coeficiente objetivo `f_ijk = (1 +
r_ijk)^(j/360) − 1` crece con el plazo porque capitaliza la tasa anual sobre el
horizonte de tenencia. Los seis `f_ijk` más altos del escenario son todos de 720
días; el máximo global es Davivienda 720/tramo 3 con `f = 24,0996 %`. El tramo
elegido es el 2 (no el 3, de mejor tasa) porque el tramo 3 exige un monto
superior a 50.000.000 y la concentración `p_i·A = 0,40 · 100.000.000 =
40.000.000` impide colocar tanto en un solo banco: con `A = 100M` el mayor monto
admisible por banco (40M) cae dentro del tramo 2 `[10.000.001, 50.000.000]`. El
modelo satura por tanto los dos bancos de mejor `f` a 720 días (Davivienda y Nu
Bank, cada uno al tope de 40M) y coloca el remanente de 20M en el tercero
(Bancolombia), también a 720 días.

**Un hallazgo no trivial: Lulo Bank queda fuera pese a tener la tasa E.A. más
alta.** En el escenario, Lulo Bank tiene las tasas anuales más altas (hasta
`r = 12,65 %` a 540 días, tramo 3), pero **no ofrece el plazo de 720 días**
(solo 90–540 días, coherente con `cdt_productos.csv`). Su mejor rendimiento
efectivo del periodo es Lulo 540/tramo 3 con `f = 19,5630 %`, por debajo del
`f ≈ 22,9–24,1 %` de los productos a 720 días de los otros bancos. El modelo, al
optimizar `f_ijk` y no `r_ijk`, prefiere correctamente el horizonte que
capitaliza más, aunque su tasa anual nominal sea menor. Este resultado sería
imposible de ver "a ojo" mirando solo las tasas E.A. y es justamente el tipo de
decisión que el modelo está diseñado para capturar.

### 5.3 Comparativa de escenarios (Req. 5.5)

Para mostrar cómo responde la solución a los parámetros, se re-ejecutó el modelo
variando un elemento a la vez respecto del base.

**Escenario 2 — Más capital (`A = 300.000.000`).** Al triplicar el capital, los
topes de concentración suben a `p_i·A = 120.000.000`, que ya superan el umbral
del tramo 3 (> 50M). El modelo migra al **tramo 3** (de mejor tasa) en los
mismos tres bancos y vuelve a colocar todo (`s_0* = 0`):

| Banco | Plazo | Tramo | Monto `x*` (COP) | `r_ijk` | `f_ijk` | % de `A` |
| --- | ---: | :---: | ---: | ---: | ---: | ---: |
| Bancolombia | 720 | 3 | 60.000.000,00 | 11,15 % | 23,5432 % | 20,00 % |
| Davivienda | 720 | 3 | 120.000.000,00 | 11,40 % | 24,0996 % | 40,00 % |
| Nu Bank | 720 | 3 | 120.000.000,00 | 11,20 % | 23,6544 % | 40,00 % |
| **Total** | | | **300.000.000,00** | | | **100,00 %** |

Valor objetivo `Z* = 71.430.735,00 COP` (≈ 23,81 % sobre `A`, algo mayor que el
23,14 % del base porque el tramo 3 paga la prima de monto más alta). La
estructura de la solución (mismos tres bancos, mismo plazo, mismos porcentajes
por banco) es robusta al nivel de capital; lo que cambia es el **tramo activado**
al cruzar el umbral de 50M.

**Escenario 3 — Diversificación más estricta (`p_i = 0,25`).** Al bajar el tope
de concentración al 25 %, ningún banco puede absorber más del 25 % de `A`, de
modo que el modelo se ve **obligado a repartir** entre cuatro bancos en lugar de
tres:

| Banco | Plazo | Tramo | Monto `x*` (COP) | `r_ijk` | `f_ijk` | % de `A` |
| --- | ---: | :---: | ---: | ---: | ---: | ---: |
| Banco de Bogotá | 720 | 2 | 25.000.000,00 | 10,25 % | 21,5506 % | 25,00 % |
| Bancolombia | 720 | 2 | 25.000.000,00 | 10,85 % | 22,8772 % | 25,00 % |
| Davivienda | 720 | 2 | 25.000.000,00 | 11,10 % | 23,4321 % | 25,00 % |
| Nu Bank | 720 | 2 | 25.000.000,00 | 10,90 % | 22,9881 % | 25,00 % |
| **Total** | | | **100.000.000,00** | | | **100,00 %** |

Ahora entra el cuarto mejor banco a 720 días (Banco de Bogotá, antes excluido),
y el valor objetivo **baja** a `Z* = 22.712.012,50 COP` (≈ 22,71 % sobre `A`).
La diferencia frente al base, `23.143.525,00 − 22.712.012,50 = 431.512,50 COP`,
es el **costo de la diversificación**: imponer más reparto obliga a colocar
capital en un producto de menor rendimiento efectivo. Este costo reaparece,
cuantificado en el margen, en los precios sombra de la Sección 6.

**Escenario 4 — Objetivo con la variante `r_ijk` (contraste didáctico).** Si en
lugar de `f_ijk` se optimiza la tasa E.A. plana `Σ r_ijk·x_ijk`, la solución
cambia por completo: el modelo abandona los 720 días y elige **360 días, tramo
2**, incluyendo a **Lulo Bank**:

| Banco | Plazo | Tramo | Monto `x*` (COP) | `r_ijk` | % de `A` |
| --- | ---: | :---: | ---: | ---: | ---: |
| Davivienda | 360 | 2 | 40.000.000,00 | 11,40 % | 40,00 % |
| Lulo Bank | 360 | 2 | 40.000.000,00 | 12,45 % | 40,00 % |
| Nu Bank | 360 | 2 | 20.000.000,00 | 11,20 % | 20,00 % |

Con el objetivo `r`, la tasa anual nominal de Lulo (12,45 % a 360 días) resulta
atractiva y entra a la cartera. Pero este objetivo **no reconoce el horizonte de
inmovilización**: valora igual un peso colocado 360 días y uno colocado 720. La
comparación entre los escenarios base y 4 demuestra que la elección del
coeficiente objetivo **no es un detalle de formato**, sino que cambia la
decisión de inversión; por eso el modelo de producción usa `f_ijk` (Sección 4.2).

---

## 6. Discusión y Análisis de Sensibilidad

> **Advertencia transversal (Req. 4.7).** Todo el análisis de esta sección
> —precios sombra, interpretación económica, rangos de estabilidad y holgura
> complementaria— se refiere al **LP restringido** que resulta de fijar las
> binarias en su valor óptimo `z = z*` (Sección 4.6), **no al MILP original**.
> En el MILP las variables binarias rompen la convexidad y la dualidad fuerte no
> está definida; los valores duales solo son rigurosos sobre este LP. Los
> números provienen del mismo escenario supuesto de la Sección 5 (escenario
> base, salvo indicación contraria) y los genera el módulo `sensitivity.py`.

### 6.1 Precios sombra del escenario base (Req. 5.6)

Fijadas las tres binarias activas del óptimo base (Bancolombia 720/2,
Davivienda 720/2, Nu Bank 720/2) y resuelto el LP restringido, los valores
duales son:

| Recurso | Símbolo | Precio sombra | Lectura |
| --- | --- | ---: | --- |
| Capital `Σx + s_0 = A` | `λ*` | 0,22877225 | retorno marginal de 1 COP más de capital |
| Concentración Davivienda `≤ p·A` | `μ*_Davivienda` | 0,00554875 | tope activo (limita) |
| Concentración Nu Bank `≤ p·A` | `μ*_NuBank` | 0,00110875 | tope activo (limita) |
| Concentración Bancolombia `≤ p·A` | `μ*_Bancolombia` | ≈ 0 | tope no activo (hay holgura) |

**Capital `λ* = 0,228772`.** Como el capital se agotó en el óptimo (`s_0* = 0`),
el precio sombra del capital es positivo y vale el rendimiento efectivo del mejor
producto todavía ampliable en el margen. Económicamente: un peso adicional de
capital, colocado de forma óptima bajo las restricciones vigentes, incrementaría
el objetivo en ≈ 0,2288 COP de rendimiento a 720 días (≈ 22,88 %). No es
casualidad que `λ*` coincida con el `f_ijk` de Bancolombia 720/2 (22,8772 %): ese
es el producto "marginal" —el de menor `f` entre los activos y con tope de banco
aún no saturado—, de modo que el siguiente peso de capital se colocaría
precisamente ahí.

**Concentración `μ_i*`.** Los topes de Davivienda y Nu Bank están **activos**
(ambos saturados en 40M) y por eso tienen precio sombra positivo:
`μ*_Davivienda = 0,005549` y `μ*_NuBank = 0,001109`. Son el **costo de
oportunidad de la diversificación**: si se permitiera colocar un peso más en
Davivienda (relajar su tope), el objetivo crecería ≈ 0,005549 COP adicionales,
porque ese peso saldría del producto marginal (`f = 22,8772 %`) y entraría al de
Davivienda (`f = 23,4321 %`); la diferencia `0,234321 − 0,228772 = 0,005549` es
exactamente `μ*_Davivienda`. El mismo razonamiento da `μ*_NuBank = 0,229881 −
0,228772 = 0,001109`. En cambio Bancolombia tiene `μ* ≈ 0`: su tope no está
saturado (solo recibe 20M de los 40M permitidos), así que relajarlo no agrega
nada. **No hay cotas de liquidez activas** (`σ*` vacío), coherente con que la
configuración las deja desactivadas.

**Lectura conjunta.** Los precios sombra ordenan las restricciones por su valor
marginal: el capital es el recurso más valioso (`λ*` ≈ 0,23), seguido muy de
lejos por los topes de concentración de los dos bancos de mejor tasa. La
diversificación "cuesta" rendimiento, y ese costo es cuantificable y pequeño en
relación con el retorno del capital.

### 6.2 El precio del capital depende de qué restricción es activa

El escenario 3 (concentración estricta `p_i = 0,25`) ilustra de forma nítida
cómo cambia la estructura dual cuando cambia qué restricción "manda". Allí el
precio sombra del capital resulta **`λ* = 0`**, mientras que los cuatro topes de
concentración se vuelven activos con precios sombra altos:
`μ*_BancoBogotá = 0,215506`, `μ*_Bancolombia = 0,228772`,
`μ*_Davivienda = 0,234321`, `μ*_NuBank = 0,229881` (cada uno igual al `f_ijk` del
producto 720/2 del banco respectivo). La interpretación es que, con la
diversificación apretada, **el recurso escaso ya no es el capital sino los cupos
por banco**: todo peso colocado está "pegado" al tope de algún banco, así que el
valor marginal migra del capital (`λ*`) a los cupos (`μ_i*`). Comparar los
escenarios base y 3 muestra que los precios sombra no son constantes del
problema, sino que dependen de cuáles restricciones estén activas en el óptimo.

### 6.3 Verificación del Teorema de Holgura Complementaria (Req. 4.4)

Sobre el LP restringido del escenario base se verifica la condición
`(x*)^T s* = 0`, descompuesta término a término (por restricción, `slack·π`, y
por variable, `dj·(v − cota)`):

- **Condición verificada:** sí.
- **Máxima violación:** `0,00e+00`, muy por debajo de la tolerancia `1e-06`.
- **Producto global:** `0,00e+00`.

El resultado confirma la coherencia entre la solución primal y la dual: toda
restricción no activa tiene precio sombra nulo y toda variable estrictamente
interior a sus cotas tiene costo reducido nulo. En particular, la relación
`s_0*·λ* = 0` se cumple en el caso "capital agotado": `s_0* = 0` y `λ* > 0`, es
decir, como no sobró capital, su valor marginal puede ser positivo (Sección 4.9).
El escenario 3 muestra el otro extremo compatible con la misma identidad: allí
`λ* = 0` porque el margen lo fijan los cupos, no el capital.

### 6.4 Rangos de estabilidad de la base óptima (Req. 5.6)

El módulo calcula los rangos por **perturbación y re-solución** (un parámetro a
la vez, ceteris paribus), porque CBC no expone el ranging exacto del símplex. El
LP restringido del escenario base **no es degenerado**, de modo que los rangos
están bien definidos.

**Lado derecho (RHS) — capital `A` y topes `p_i·A` (Req. 4.6).**

| Recurso | RHS base (COP) | Límite inferior | Límite superior | Puede bajar | Puede subir |
| --- | ---: | ---: | ---: | ---: | ---: |
| Capital `A` | 100.000.000 | 90.000.000 | 120.000.000 | 10.000.000 | 20.000.000 |
| Concentración Davivienda | 40.000.000 | 20.000.000 | 50.000.000 | 20.000.000 | 10.000.000 |
| Concentración Nu Bank | 40.000.000 | 20.000.000 | 50.000.000 | 20.000.000 | 10.000.000 |
| Concentración Bancolombia | 40.000.000 | 20.000.000 | +∞ | 20.000.000 | +∞ |

Dentro de cada intervalo la base óptima se mantiene y el precio sombra es
constante, con `Δobjetivo = π·Δb`. Lecturas:

- **Capital `A`.** La base aguanta hasta `A = 120.000.000` por arriba; en ese
  punto el tope de Davivienda (50M del tramo 2) y el de Nu Bank se saturarían al
  límite superior del tramo y la base cambiaría (habría que abrir el tramo 3 o un
  cuarto banco). Por abajo aguanta hasta `A = 90.000.000`. Mientras `A` se mueva
  en `[90M, 120M]`, cada peso adicional de capital rinde `λ* = 0,228772`.
- **Topes de concentración.** Los cupos de Davivienda y Nu Bank (activos) pueden
  subir hasta 50M (donde se agota el tramo 2) o bajar hasta 20M antes de cambiar
  la base. El cupo de Bancolombia (no activo) puede crecer sin límite superior
  efectivo (`+∞`) sin alterar la solución, porque no está saturado.

**Coeficientes objetivo `f_ijk` de las variables activas (Req. 4.5).**

| Combinación activa | `f` base | Puede bajar hasta | Puede subir hasta |
| --- | ---: | ---: | ---: |
| Bancolombia 720/2 | 0,228772 | 0,0 (baja ≈ 0,22877) | 0,236398 (sube ≈ 0,00763) |
| Davivienda 720/2 | 0,234321 | 0,226510 (baja ≈ 0,00781) | +∞ |
| Nu Bank 720/2 | 0,229881 | 0,222218 (baja ≈ 0,00766) | +∞ |

Interpretación: el rendimiento de Bancolombia 720/2 (el producto marginal) puede
subir hasta ≈ 0,2364 antes de que convenga reasignar capital hacia él (desplazando
a otro banco), y puede caer hasta volverse nulo sin que salga de la base porque
sigue siendo la mejor opción para el remanente de 20M. Los productos saturados de
Davivienda y Nu Bank admiten subidas ilimitadas de su `f` sin cambio de base (ya
están al tope) y solo salen de la base si su `f` cae por debajo del umbral
indicado (≈ 0,2265 y ≈ 0,2222 respectivamente), punto en que otro banco los
reemplazaría. Estos rangos acotan cuánto pueden moverse las tasas supuestas antes
de que la recomendación de cartera cambie, lo que da una medida directa de la
robustez de la solución.

### 6.5 Limitaciones del análisis

Los rangos son numéricos (perturbación + re-solución), válidos "un parámetro a la
vez" y no cubren variaciones simultáneas (regla del 100 %). Si el LP restringido
fuera degenerado, los precios sombra podrían no ser únicos; no es el caso aquí,
pero el informe lo advierte cuando ocurre. Y, de nuevo, **todo el análisis aplica
al LP restringido con `z = z*`**: si cambia la solución entera (por ejemplo, al
cruzar el umbral de un tramo como en el escenario 2), el conjunto de variables
activas cambia y el análisis dual debe rehacerse sobre la nueva base.

---

## 7. Conclusiones

Este trabajo formuló y resolvió la asignación de capital en CDT como un modelo
MILP y, sobre su solución entera, construyó el LP restringido que habilita el
análisis de dualidad y sensibilidad del curso. Los cuatro objetivos planteados
en la Introducción se cumplieron: (i) se maximizó el rendimiento efectivo total
con el coeficiente `f_ijk`; (ii) se incorporó la lógica de tasas escalonadas por
tramos con binarias y las restricciones de riesgo y liquidez; (iii) se resolvió
el modelo con PuLP/CBC y se reportó la asignación óptima por banco, plazo y
tramo; y (iv) se interpretaron económicamente los precios sombra, se verificó la
holgura complementaria y se calcularon los rangos de estabilidad de la base.

**Hallazgos principales.** En el escenario ilustrativo, la solución óptima
concentra el capital en productos a 720 días y lo agota por completo. El
resultado más instructivo es que **el banco con la tasa E.A. más alta (Lulo Bank)
queda fuera de la cartera** porque no ofrece el plazo largo: al optimizar el
rendimiento efectivo del periodo `f_ijk` y no la tasa anual plana, el modelo
prefiere el horizonte que capitaliza más. El contraste con la variante que
optimiza `Σ r_ijk·x` —que sí elige a Lulo a 360 días— demuestra que la elección
del coeficiente objetivo cambia la decisión de inversión, no solo su
presentación. El análisis dual, por su parte, cuantifica el valor marginal del
capital (`λ* ≈ 0,2288`) y el costo de oportunidad de la diversificación
(`μ_i*` de los bancos saturados), y muestra que la identidad de la restricción
"escasa" se desplaza del capital a los cupos por banco cuando se endurece la
diversificación. La holgura complementaria se verificó exactamente
(`(x*)^T s* = 0`).

**Limitaciones.** La más importante es metodológica y transversal: los precios
sombra y los rangos de sensibilidad son rigurosos solo sobre el **LP restringido
con las binarias fijadas**, no sobre el MILP original; si la solución entera
cambia (por ejemplo al cruzar el umbral de un tramo, como ocurre al triplicar el
capital), el análisis dual debe rehacerse sobre la nueva base. Los rangos se
obtienen por perturbación numérica, un parámetro a la vez, y no cubren
variaciones simultáneas. La limitación de datos también es relevante: ninguna
fuente pública desagrega las tasas por los tres tramos de monto del problema, por
lo que los números de los Resultados provienen de un **escenario de tasas
supuestas**, no de tarifarios reales; sirven para ejercitar y validar el modelo,
no como recomendación de inversión. Finalmente, el modelo ignora el riesgo de
reinversión, los impuestos (retención en la fuente) y la posibilidad de retiro
anticipado.

**Trabajo futuro.** Entre las extensiones naturales están: alimentar el modelo
con tarifarios reales por tramo cuando estén disponibles (o con tasas negociadas
caso a caso); incorporar el tratamiento tributario y los costos de reinversión
para plazos cortos; añadir una componente de riesgo de crédito por emisor (más
allá de la cobertura de Fogafín) que module la diversificación; modelar
escalonamiento de vencimientos (laddering) para equilibrar liquidez y
rendimiento; y estudiar la sensibilidad del MILP completo mediante reoptimización
sistemática ante cambios de parámetros, complementando el análisis dual del LP
restringido.

---

## 8. Referencias

<!--
Referencias introducidas por las secciones 2 (Introducción), 3 (Revisión de
Literatura) y 5-6 (Resultados/Discusión) — Requisito 5.7. Fuentes reales; sin
DOIs inventados. La sub-tarea 9.4 NO introduce nuevas fuentes bibliográficas
académicas (reutiliza [1]-[12]); sí añade la NOTA sobre las tasas supuestas del
escenario de Resultados, al final de esta sección.
-->

[1] Banco de la República. *Certificado de depósito a término (CDT)* (entrada de glosario). Disponible en: https://www.banrep.gov.co/es/glosario/certificado-deposito-termino-cdt

[2] Fondo de Garantías de Instituciones Financieras (Fogafín). *¿Qué es el Seguro de Depósitos?* Disponible en: https://www.fogafin.gov.co/que-es-el-seguro-de-depositos

[3] Superintendencia Financiera de Colombia. *Portal institucional — información y protección del consumidor financiero.* Disponible en: https://www.superfinanciera.gov.co/

[4] Banco de la República. *Tasas de captación de los CDT* (entrada de glosario). Disponible en: https://www.banrep.gov.co/es/glosario/tasas-captacion

[5] Markowitz, H. (1952). Portfolio Selection. *The Journal of Finance*, 7(1), 77–91.

[6] Dantzig, G. B. (1963). *Linear Programming and Extensions.* Princeton University Press.

[7] Bertsimas, D., & Shioda, R. (2009). Algorithm for cardinality-constrained quadratic optimization. *Computational Optimization and Applications*, 43(1), 1–22.

[8] Graham, R. L., Lawler, E. L., Lenstra, J. K., & Rinnooy Kan, A. H. G. (1979). Optimization and approximation in deterministic sequencing and scheduling: a survey. *Annals of Discrete Mathematics*, 5, 287–326.

[9] Pinedo, M. L. (2016). *Scheduling: Theory, Algorithms, and Systems* (5a ed.). Springer.

[10] Wolsey, L. A. (1998). *Integer Programming.* Wiley-Interscience.

[11] Nemhauser, G. L., & Wolsey, L. A. (1988). *Integer and Combinatorial Optimization.* Wiley.

[12] Williams, H. P. (2013). *Model Building in Mathematical Programming* (5a ed.). Wiley.

> Nota de atribución: el contexto del mercado colombiano de CDT (naturaleza del instrumento, tasas de captación y seguro de depósitos) se apoya en fuentes públicas del Banco de la República, la Superintendencia Financiera de Colombia y Fogafín, parafraseadas para esta redacción. Contenido reformulado para cumplir con restricciones de licenciamiento.

> **Nota sobre las tasas usadas en Resultados (Req. 1.5 y 5.7) — NO son tasas reales.** Los números de las Secciones 5 y 6 se generaron sobre un **escenario ilustrativo de tasas supuestas**, no sobre tarifarios reales de mercado. Ninguna fuente pública consultada desagrega la tasa E.A. de los CDT por los tres tramos de monto definidos en este trabajo ([50.000–10.000.000] / [10.000.001–50.000.000] / > 50.000.000); los bancos cotizan por plazo, no por esos tramos. Por eso la matriz real `data/cdt_productos.csv` deja la tasa vacía en las 105 combinaciones, todas marcadas `es_supuesto = True`. Para ejercitar el modelo de punta a punta se construyó el archivo `data/escenario_supuesto.csv` (generado por `data/generar_escenario_supuesto.py`), donde cada tasa se obtiene con la regla declarada `tasa_ea(i, j, k) = base_banco[i] + ajuste_plazo[j] + prima_tramo[k]`, con todas las filas `es_supuesto = True`. Las anclas de orden de magnitud por banco se inspiran en los agregadores citados en los campos `fuente` de `cdt_productos.csv` (p. ej. bancolombia.com, bancodebogota.com, davivienda.com, Nu Colombia, lulobank.com y el agregador de referencia; consulta 2026-02), pero las cifras finales por `(i, j, k)` **son un supuesto del artículo y no deben citarse como tasas de mercado**.
