-- 1) Usuarios (hashed_password: ejemplos bcrypt; reemplaza por tus hashes si quieres)
INSERT INTO usuarios (nombre, correo, rol, hashed_password) VALUES
('Admin Demo',   'admin@demo.com',    'admin',  '$2b$12$EXRkfkdmXn2gzds2SSituuJQe6yZK1Zb2OQ1r9v0Yqj1u9xQZ0G6'), -- clave: demo123
('Dr. Laura Ruiz','laura.ruiz@clinica', 'medico', '$2b$12$7QJfKz1b9x9K2h3r9AqEzuJvQY0g6p1T3W8H2zK5b6FvEo2Z9YbqW'), -- clave: medico123
('Enfermeria1',  'enf1@clinica',       'enfermera', '$2b$12$9mYt1Kxq2vC3b4d5E6fGhiJkLmNoPqRstUvWxYzAAbBcCdEeFfGhi'); -- clave: enf123


-- 2) Pacientes
INSERT INTO pacientes (numero_identificacion, nombre, fecha_nacimiento, sexo, direccion, telefono) VALUES
('ID-1001', 'María González', '1980-05-12', 'F', 'Calle A 123, Zapopan', '3312345678'),
('ID-1002', 'Juan Pérez',     '1975-11-02', 'M', 'Av. Central 45, Guadalajara', '3319876543'),
('ID-1003', 'Ana Torres',     '2002-03-21', 'F', 'Col. Centro 9, Zapopan', '3321122334'),
('ID-1004', 'Carlos López',   '1968-01-15', 'M', 'Pueblo Nuevo 7, Zapopan', '3334455667'),
('ID-1005', 'Sofía Ramírez',  '1994-09-30', 'F', 'Río Bravo 11, GDL', '3345566778');

-- 3) Enfermedades (ejemplos con códigos ICD simplificados)
INSERT INTO enfermedades (codigo_icd, nombre, descripcion, gravedad) VALUES
('A09', 'Gastroenteritis', 'Inflamación del tracto gastrointestinal, diarrea y vómito', 2),
('I10', 'Hipertensión esencial', 'Presión arterial alta crónica', 3),
('J06', 'Infección respiratoria aguda', 'Rinitis y faringitis típicas', 2),
('E11', 'Diabetes mellitus tipo 2', 'Alteración crónica del metabolismo de glucosa', 4),
('K35', 'Apendicitis aguda', 'Inflamación del apéndice', 5);

-- 4) Signos catálogo
INSERT INTO signos_catalogo (nombre, descripcion) VALUES
('Temperatura corporal', 'Medición de temperatura en grados Celsius'),
('Frecuencia cardiaca', 'Pulsaciones por minuto'),
('Presión arterial sistólica', 'Presión sistólica en mmHg'),
('Presión arterial diastólica', 'Presión diastólica en mmHg'),
('Frecuencia respiratoria', 'Respiraciones por minuto'),
('Sat O2', 'Saturación de oxígeno en sangre (%)'),
('Nivel de conciencia', 'Escala AVPU o Glasgow (registrar como texto)'),
('Peso', 'Peso en kilogramos'),
('Talla', 'Talla en centímetros'),
('Glasgow', 'Puntuación de Glasgow');

-- 5) Síntomas catálogo
INSERT INTO sintomas_catalogo (nombre, descripcion) VALUES
('Fiebre', 'Elevación de la temperatura corporal subjetiva o medida'),
('Tos', 'Tos seca o productiva'),
('Dolor abdominal', 'Dolor en la región abdominal'),
('Náuseas', 'Sensación de querer vomitar'),
('Vómito', 'Expulsión forzada del contenido gástrico'),
('Cefalea', 'Dolor de cabeza'),
('Cansancio', 'Fatiga o astenia'),
('Pérdida de apetito', 'Disminución del deseo de comer'),
('Disnea', 'Dificultad para respirar'),
('Mialgias', 'Dolores musculares');

-- 6) Pruebas de laboratorio catálogo
INSERT INTO pruebas_lab_catalogo (codigo, nombre, unidad, rango_normal_low, rango_normal_high, descripcion) VALUES
('HB', 'Hemoglobina', 'g/dL', 13.5, 17.5, 'Hemoglobina en sangre periférica (varía por sexo)'),
('HCT', 'Hematocrito', '%', 41, 53, 'Porcentaje de volumen de glóbulos rojos'),
('GLU', 'Glucosa en ayunas', 'mg/dL', 70, 99, 'Glucosa plasmática en ayunas'),
('CRP', 'Proteína C reactiva', 'mg/L', 0, 5, 'Marcador de inflamación'),
('PCR', 'Velocidad de sedimentación globular', 'mm/h', 0, 20, 'Inflamación no específica'),
('UREA', 'Urea', 'mg/dL', 10, 50, 'Función renal'),
('CREA', 'Creatinina', 'mg/dL', 0.6, 1.3, 'Función renal');

-- 7) Pruebas post mortem catálogo
INSERT INTO pruebas_post_catalogo (nombre, descripcion) VALUES
('Autopsia completa', 'Examen macroscópico y microscópico completo'),
('Toxicología', 'Panel toxicológico para drogas y toxinas'),
('Cultivo bacteriano', 'Cultivo de muestras de tejidos'),
('Biopsia histológica', 'Examen histopatológico de muestras');

-- 8) Encuentros (vincular a pacientes y creadores)
-- created_by corresponde a usuario_id (asumimos 1=Admin Demo, 2=Dr. Laura Ruiz, 3=Enfermeria1)
INSERT INTO encuentros (paciente_id, fecha, tipo_encuentro, motivo, created_by) VALUES
(1, '2025-10-01 09:15:00+00', 'consulta', 'Fiebre y tos de 2 días', 2),
(2, '2025-09-20 14:30:00+00', 'consulta', 'Control de hipertensión', 2),
(1, '2025-10-02 10:00:00+00', 'urgencia',  'Dolor abdominal intenso', 2),
(3, '2025-08-12 11:00:00+00', 'consulta', 'Dolor de cabeza y nauseas', 2),
(4, '2025-07-05 08:00:00+00', 'control',  'Chequeo preoperatorio', 1);

-- 9) Observaciones de signos (vinculadas a encuentros)
-- buscar signo_id según lo insertado arriba; aquí asumimos orden incremental
INSERT INTO observacion_signos (encuentro_id, signo_id, valor_texto, valor_numerico, unidad, recorded_by) VALUES
(1, 1, NULL, 38.6, '°C', 3),  -- Temperatura corporal
(1, 2, NULL, 110, 'ppm', 3),  -- Frecuencia cardiaca
(1, 6, NULL, 95, '%', 3),     -- Sat O2
(2, 3, NULL, 150, 'mmHg', 3), -- PAS
(2, 4, NULL, 95, 'mmHg', 3),  -- PAD
(3, 1, NULL, 39.2, '°C', 3),
(3, 8, NULL, 72.5, 'kg', 3),
(4, 1, NULL, 37.8, '°C', 3),
(4, 2, NULL, 88, 'ppm', 3);

-- 10) Observaciones de síntomas
INSERT INTO observacion_sintomas (encuentro_id, sintoma_id, severidad, inicio_fecha, notas, recorded_by) VALUES
(1, 1, 3, '2025-09-30', 'Comenzó con escalofríos', 3), -- Fiebre
(1, 2, 2, '2025-09-30', 'Tos seca especialmente en la noche', 3), -- Tos
(3, 3, 4, '2025-10-02', 'Dolor tipo cólico, 8/10', 3), -- Dolor abdominal
(4, 6, 2, '2025-08-11', 'Cefalea intermitente', 3), -- Cefalea
(2, 9, 1, '2025-09-15', 'Leve disnea al subir escaleras', 3); -- Disnea

-- 11) Diagnósticos (vinculados a paciente y encuentro)
INSERT INTO diagnosticos (paciente_id, encuentro_id, enfermedad_id, tipo, probabilidad, fuente, regla_id, notas, created_by) VALUES
(1, 1, 3, 'presuntivo', 0.7, 'clínico', 'R1', 'Sospecha de infección respiratoria aguda', 2),
(1, 3, 5, 'definitivo', 0.95, 'imagen', 'R2', 'Sospecha de apendicitis aguda por examen físico', 2),
(2, 2, 2, 'crónico', 0.99, 'historial', 'R3', 'Hipertensión arterial controlada con medicación', 2),
(3, 4, 3, 'presuntivo', 0.6, 'clínico', 'R4', 'Cefalea tensional probable', 2);

-- 12) Tratamientos (vinculados a diagnósticos)
INSERT INTO tratamientos (diagnostico_id, nombre, descripcion, inicio_fecha, fin_fecha, prescrito_por, estado) VALUES
(1, 'Paracetamol 500 mg', 'Cada 6 horas si hay fiebre', '2025-10-01', '2025-10-05', 2, 'activo'),
(2, 'Cirugía: apendicectomía', 'Programada urgente', '2025-10-02', NULL, 2, 'pendiente'),
(3, 'Enalapril 10 mg', 'Una vez al día para TA', '2025-09-20', NULL, 2, 'activo'),
(4, 'Ibuprofeno 400 mg', 'Si dolor, cada 8 horas', '2025-08-12', '2025-08-15', 2, 'finalizado');
