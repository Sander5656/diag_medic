CREATE TABLE usuarios (
  usuario_id SERIAL PRIMARY KEY,
  nombre VARCHAR(150) NOT NULL,
  correo VARCHAR(255) UNIQUE,
  rol VARCHAR(50) NOT NULL,
  hashed_password VARCHAR(255),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE pacientes (
  paciente_id SERIAL PRIMARY KEY,
  numero_identificacion VARCHAR(100) UNIQUE,
  nombre VARCHAR(200) NOT NULL,
  fecha_nacimiento DATE,
  sexo CHAR(1),
  direccion TEXT,
  telefono VARCHAR(50),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE enfermedades (
  enfermedad_id SERIAL PRIMARY KEY,
  codigo_icd VARCHAR(20) UNIQUE,
  nombre VARCHAR(255) NOT NULL,
  descripcion TEXT,
  gravedad SMALLINT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE signos_catalogo (
  signo_id SERIAL PRIMARY KEY,
  nombre VARCHAR(200) NOT NULL UNIQUE,
  descripcion TEXT
);

CREATE TABLE sintomas_catalogo (
  sintoma_id SERIAL PRIMARY KEY,
  nombre VARCHAR(200) NOT NULL UNIQUE,
  descripcion TEXT
);

CREATE TABLE pruebas_lab_catalogo (
  prueba_lab_id SERIAL PRIMARY KEY,
  codigo VARCHAR(100) UNIQUE,
  nombre VARCHAR(255) NOT NULL,
  unidad VARCHAR(50),
  rango_normal_low NUMERIC,
  rango_normal_high NUMERIC,
  descripcion TEXT
);

CREATE TABLE pruebas_post_catalogo (
  prueba_post_id SERIAL PRIMARY KEY,
  nombre VARCHAR(255) NOT NULL,
  descripcion TEXT
);

CREATE TABLE encuentros (
  encuentro_id SERIAL PRIMARY KEY,
  paciente_id INT NOT NULL REFERENCES pacientes(paciente_id),
  fecha TIMESTAMP WITH TIME ZONE DEFAULT now(),
  tipo_encuentro VARCHAR(50),
  motivo TEXT,
  created_by INT REFERENCES usuarios(usuario_id)
);

CREATE TABLE observacion_signos (
  observacion_signo_id SERIAL PRIMARY KEY,
  encuentro_id INT NOT NULL REFERENCES encuentros(encuentro_id) ON DELETE CASCADE,
  signo_id INT NOT NULL REFERENCES signos_catalogo(signo_id),
  valor_texto TEXT,
  valor_numerico NUMERIC,
  unidad VARCHAR(50),
  recorded_by INT REFERENCES usuarios(usuario_id),
  recorded_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE observacion_sintomas (
  observacion_sintoma_id SERIAL PRIMARY KEY,
  encuentro_id INT NOT NULL REFERENCES encuentros(encuentro_id) ON DELETE CASCADE,
  sintoma_id INT NOT NULL REFERENCES sintomas_catalogo(sintoma_id),
  severidad SMALLINT,
  inicio_fecha DATE,
  notas TEXT,
  recorded_by INT REFERENCES usuarios(usuario_id),
  recorded_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE diagnosticos (
  diagnostico_id SERIAL PRIMARY KEY,
  paciente_id INT NOT NULL REFERENCES pacientes(paciente_id),
  encuentro_id INT REFERENCES encuentros(encuentro_id),
  enfermedad_id INT REFERENCES enfermedades(enfermedad_id),
  tipo VARCHAR(50),
  probabilidad NUMERIC,
  fuente VARCHAR(100),
  regla_id VARCHAR(100),
  notas TEXT,
  created_by INT REFERENCES usuarios(usuario_id),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE tratamientos (
  tratamiento_id SERIAL PRIMARY KEY,
  diagnostico_id INT REFERENCES diagnosticos(diagnostico_id) ON DELETE SET NULL,
  nombre VARCHAR(255) NOT NULL,
  descripcion TEXT,
  inicio_fecha DATE,
  fin_fecha DATE,
  prescrito_por INT REFERENCES usuarios(usuario_id),
  estado VARCHAR(50),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);