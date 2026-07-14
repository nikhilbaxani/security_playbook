# Ejemplos de referencia (few-shot)

Los siguientes son ejemplos del formato y nivel de detalle esperado. Son versiones
condensadas: el playbook real que generes debe seguir la estructura completa definida
en las instrucciones.

---

## Ejemplo 1

**Input del usuario:**
- Tipo de incidente: ransomware
- Contexto: servidor de ficheros on-prem cifrado, empresa de ~50 empleados, sin backups verificados recientes

**Output esperado (extracto):**

# Playbook: Ransomware en servidor de ficheros on-prem

## Resumen del escenario
Servidor de ficheros on-prem con contenido cifrado por ransomware. Organización de ~50
empleados. No hay backups verificados recientes, por lo que la preservación de evidencia
y de datos cifrados es crítica: puede ser la única copia existente. Criticidad: ALTA.

## Supuestos tomados
- Se asume que existe al menos un firewall/switch gestionable para aislar el segmento (no confirmado).
- Se asume que no se ha pagado ni contactado al actor (no confirmado).
- No se conoce el vector de entrada; se tratará como desconocido hasta el análisis.

## Fase 2 — Detección y Análisis (NIST 800-61 §3.2)
1. **Aislar el servidor afectado de la red** (desconexión física o cuarentena vía EDR/switch),
   SIN apagarlo: la memoria RAM puede contener claves de cifrado. — *Rol: Admin de sistemas.*
   *Evidencia: anotar hora exacta y método de aislamiento.*
2. **Identificar la variante**: extensión de los ficheros cifrados y nota de rescate;
   contrastar con recursos públicos (ej. ID Ransomware, No More Ransom). — *Rol: Analista.*
3. **Determinar el alcance**: revisar logs de autenticación y comparticiones SMB para saber
   si otros equipos accedieron/replicaron el cifrado. — *Rol: Analista. Evidencia: export de logs.*

## Fase 3 — Contención, Erradicación y Recuperación (NIST 800-61 §3.3)
### 3.1 Contención
1. Bloquear en firewall las IPs/dominios de la nota de rescate y C2 conocidos de la variante. — *Rol: Red/Seguridad.*
2. Forzar rotación de credenciales privilegiadas usadas en el servidor. — *Rol: Admin.*
   *Criterio de éxito: ninguna sesión activa con credenciales antiguas.*

(…resto de fases con el mismo nivel de detalle…)

## Checklist rápido
| Fase | Acción | Rol | Hecho |
|---|---|---|---|
| Detección (§3.2) | Aislar servidor sin apagar | Admin sistemas | [ ] |
| Detección (§3.2) | Identificar variante | Analista | [ ] |
| Contención (§3.3.1) | Rotar credenciales privilegiadas | Admin | [ ] |

---

## Ejemplo 2

**Input del usuario:**
- Tipo de incidente: credential leak
- Contexto: credenciales corporativas aparecen en un dump público, org usa Microsoft 365, MFA parcial

**Output esperado (extracto):**

# Playbook: Filtración de credenciales corporativas en dump público

## Resumen del escenario
Credenciales de dominio corporativo detectadas en un volcado público. Entorno Microsoft 365
con MFA desplegado solo parcialmente: las cuentas sin MFA son el riesgo inmediato de
account takeover. Criticidad: ALTA hasta confirmar qué cuentas carecen de MFA.

## Supuestos tomados
- Se asume que el dump es de una brecha de un tercero (password reuse), no de la propia org (a confirmar en §3.2).
- Se asume acceso administrativo al tenant de M365 para forzar resets y revisar sign-in logs.

## Fase 2 — Detección y Análisis (NIST 800-61 §3.2)
1. **Validar el listado**: confirmar qué cuentas del dump siguen activas en el directorio. — *Rol: Admin identidad.*
2. **Cruzar con sign-in logs** (últimos 30 días): buscar accesos exitosos desde IPs/países
   anómalos en las cuentas afectadas. — *Rol: Analista. Evidencia: export de sign-in logs.*
3. **Clasificar**: cuentas con MFA vs sin MFA; las sin MFA con login anómalo pasan a
   tratarse como compromiso confirmado. — *Rol: Analista.*

### 3.1 Contención
1. Reset de contraseña + revocación de sesiones/tokens de TODAS las cuentas del dump,
   empezando por las sin MFA. — *Rol: Admin identidad. Criterio de éxito: 0 sesiones previas válidas.*
2. Habilitar MFA obligatorio para las cuentas afectadas antes de reactivarlas. — *Rol: Admin identidad.*

(…resto de fases…)

---

## Ejemplo 3

**Input del usuario:**
- Tipo de incidente: DDoS
- Contexto: web pública de e-commerce caída, tráfico anómalo, sin CDN ni servicio anti-DDoS contratado

**Output esperado (extracto):**

# Playbook: DDoS contra web pública de e-commerce

## Resumen del escenario
Sitio de e-commerce inaccesible por tráfico anómalo masivo. No existe CDN ni mitigación
anti-DDoS contratada, lo que limita las opciones a filtrado upstream por el ISP y
mitigaciones locales. Impacto directo en negocio. Criticidad: ALTA mientras dure la caída.

## Supuestos tomados
- Se asume que es volumétrico hasta analizar si es de capa 7 (a confirmar en §3.2 con los logs del servidor web).
- Se asume contacto disponible con el ISP/hosting (crítico: si no existe, es el gap nº1 de Preparación).

## Fase 2 — Detección y Análisis (NIST 800-61 §3.2)
1. **Caracterizar el ataque**: volumétrico (saturación de ancho de banda) vs capa de
   aplicación (muchas requests HTTP válidas). Revisar gráficas de tráfico y logs del web
   server. — *Rol: Red/Sysadmin. Evidencia: capturas de gráficas + muestra de logs.*
2. **Identificar patrón**: IPs origen (¿distribuidas?), user-agents, rutas atacadas. — *Rol: Analista.*
3. **Descartar cortina de humo**: revisar alertas de otros sistemas durante la ventana del
   ataque (el DDoS puede encubrir una intrusión). — *Rol: Analista.*

### 3.1 Contención
1. Contactar al ISP/hosting para filtrado upstream o blackholing selectivo. — *Rol: Responsable de infra.*
2. Si es capa 7: rate limiting y bloqueo por patrón (user-agent, ruta, geo) en el propio
   web server o WAF si existe. — *Rol: Sysadmin. Criterio de éxito: el sitio responde para tráfico legítimo.*

## Fase 4 — Actividad Post-Incidente (NIST 800-61 §3.4)
1. Evaluar contratación de CDN/anti-DDoS gestionado: fue el gap principal. — *Rol: Dirección/Infra.*
2. Documentar métricas: duración de la caída, coste estimado, tiempo de respuesta del ISP. — *Rol: Coordinador.*

(…resto de fases…)
