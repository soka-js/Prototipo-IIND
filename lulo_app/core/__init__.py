"""Motor v3: el mismo motor para los 600 clientes de la base del reto y para los 3 personajes.

Capas, en orden:
    schema      tipos canónicos (cliente, movimiento, abono a bolsillo, póliza, uso de la app)
    store       carga la base ingerida (lulo_app/dataset) y los personajes traducidos al mismo esquema
    catalog     productos con prima, comisión, persistencia y conversión previa, todo leído de la base
    rules       parámetros versionados (v1), aprobados antes de medir
    features    rasgos de un cliente a una fecha
    signals     señales con regla, fuerza y evidencia
    eligibility requisitos de la hoja Elegibilidad
    contact     política de contacto (tope, fatiga, latencia; push frente a banner)
    experiment  grupo de control determinista
    engine      evaluación por cliente, eventos en tiempo real y plan de campaña
    backtest    recorre el año y verifica las invariantes
"""
