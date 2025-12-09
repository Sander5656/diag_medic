Descripción y características
Repositorio que contiene un motor de inferencia con interfaz gráfica (GUI) diseñado como herramienta auxiliar para apoyar procesos de diagnóstico clínico a partir de los síntomas y signos reportados por el paciente. El proyecto está pensado como apoyo informativo para profesionales de la salud y no sustituye la evaluación médica.
Características principales
- Motor de reglas y/o basado en conocimiento (soporte para reglas IF/THEN y encadenamiento hacia adelante).
- Interfaz gráfica para ingreso de síntomas, visualización de hipótesis diagnósticas y trazabilidad de la inferencia.
- Almacenamiento local de sesiones en CSV/JSON y opción de exportar resultados.
- Módulo de configuración para gestionar reglas, pesos y umbrales.
- Registro de logs con timestamps y trazado de decisiones para auditoría.
- Extensible: diseño modular para integrar nuevos conjuntos de reglas, modelos probabilísticos o conectores externos.

Requisitos e instalación
Requisitos
- Python 3.8+ (o el runtime que use el proyecto).
- Librerías listadas en requirements.txt (p. ej., framework GUI, motor de reglas, pyyaml, pandas).
- Entorno con permisos para leer/escribir archivos locales.
