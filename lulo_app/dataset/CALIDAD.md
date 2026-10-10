# Calidad de la base del reto

Archivo generado por `scripts/ingest_reto.py`. No editar a mano.

- Fuente: `Base_Datos_Reto_Universidad.xlsx` · sha256 `5029790b7a29889c…`
- Periodo: 2025-11-01 a 2026-10-08 (fecha de corte)
- Uso: Académico / prototipado. No citar cifras como datos, métricas o benchmarks oficiales del banco.

| Tabla | Filas |
|---|---:|
| clientes | 600 |
| movimientos | 20.473 |
| pagos_seguros | 113 |
| cajitas | 1.708 |
| uso_app | 600 |
| seguros_mensual | 72 |
| elegibilidad | 6 |
| campanas_previas | 5 |
| excluidos | 562 |

| Pestaña | Chequeo | Estado | Detalle |
|---|---|---|---|
| LEEME/Juridico_Entrega | fecha de corte | OK | Periodo 2025-11-01 a 2026-10-08; ambas pestañas coinciden |
| Clientes | conteo vs LEEME | OK | 600 filas; LEEME declara 600 |
| Movimientos | categoría ↔ MCC 1:1 | OK | cada categoría tiene un solo MCC |
| Movimientos | créditos (ingresos) por categoría | OK | Abono recurrente: 4656 |
| Movimientos | fechas posteriores al corte | AVISO | 444 movimientos después de 2026-10-08 excluidos (Abono recurrente: 388, Transferencia fija tercero: 56) |
| Movimientos | combustible | AVISO | no existe categoría de combustible (MCC 5541/5542); la señal de vehículo solo cuenta con peajes y SOAT |
| Pagos_Seguros | coincidencia con seguros_vigentes | AVISO | porcentaje de pagos cuyo ramo aparece en seguros_vigentes del cliente: Hogar 1/24 (4%), Mascotas 0/12 (0%), SOAT 12/50 (24%), Vida 0/27 (0%). Lectura propuesta: vigentes = con Lulo; pagos = con aseguradora externa. |
| Cajitas | fechas posteriores al corte | AVISO | 118 abonos después de 2026-10-08 excluidos |
| Cajitas | consistencia con Clientes.cajitas_activas | OK | 0 clientes con la bandera distinta a la tabla |
| Uso_App | un registro por cliente | OK | 600 registros; faltan 0 |
| Uso_App | tope de contactos | OK | max_contactos_mes: {4: 600}; 202 clientes ya enviaron ≥ tope en 30 días |
| Seguros_Mensual | cobertura | OK | 12 meses (2025-11 a 2026-10) × 6 ramos |
| Seguros_Mensual | persistencia vacía | AVISO | sin persistencia_12m: SOAT (12 meses), Viajes (12 meses) |
| Elegibilidad | ramos | OK | SOAT (18+, Cualquier ocupación), Vida (18-65, Cualquier ocupación), Desempleo (18-60, Empleado), Hogar (18+, Cualquier ocupación), Mascotas (18+, Cualquier ocupación), Viajes (18+, Cualquier ocupación) |
| Elegibilidad | rangos de edad | AVISO | Clientes trae la edad en rangos; «56+» no se puede comparar con los topes de 60 (Desempleo) y 65 (Vida) |
| Campanas_Previas | conversion_impactados | AVISO | 5 de 5 filas: la columna es ventas/elegibles. Se conserva como «conversion_reportada» y se agregan los cocientes recalculados. |
| Diccionario | campos documentados | AVISO | no existen en la pestaña: Clientes.saldo_promedio, Clientes.ingreso_mensual |
