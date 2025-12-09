# app.py
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
import psycopg2
import bcrypt
from datetime import datetime
import bcrypt
import base64
import binascii
import difflib
import pprint

# ---------- Configuración DB ----------
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "medic_database",
    "user": "postgres",
    "password": ""
}

# ---------- Helper DB ----------
class DB:
    def __init__(self, config):
        self.config = config
        self.conn = None

    def connect(self):
        if self.conn is None or self.conn.closed:
            self.conn = psycopg2.connect(**self.config)
            self.conn.autocommit = True
        return self.conn

    def query(self, sql, params=None, fetch=False):
        conn = self.connect()
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            if fetch:
                return cur.fetchall()

    def fetchall(self, sql, params=None):
        conn = self.connect()
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchall()

    def fetchone(self, sql, params=None):
        conn = self.connect()
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchone()

db = DB(DB_CONFIG)

# ---------- Esquema y datos recomendados (tratamientos y pruebas) ----------
def ensure_recommended_schema_and_seed():
    """
    Crea tablas de recomendaciones si no existen y agrega datos básicos
    para poder mostrar tratamientos y pruebas sugeridas por enfermedad.
    """
    # Tablas de mapeo recomendadas
    db.query(
        """
        CREATE TABLE IF NOT EXISTS enfermedad_tratamientos_recomendados (
            id SERIAL PRIMARY KEY,
            enfermedad_id INT NOT NULL REFERENCES enfermedades(enfermedad_id) ON DELETE CASCADE,
            tratamiento TEXT NOT NULL,
            indicaciones TEXT,
            tipo VARCHAR(50), -- farmacologico / no_farmacologico / procedimiento
            prioridad SMALLINT, -- 1 alta, 2 media, 3 baja
            UNIQUE (enfermedad_id, tratamiento)
        )
        """
    )

    db.query(
        """
        CREATE TABLE IF NOT EXISTS enfermedad_pruebas_recomendadas (
            id SERIAL PRIMARY KEY,
            enfermedad_id INT NOT NULL REFERENCES enfermedades(enfermedad_id) ON DELETE CASCADE,
            prueba_lab_id INT NOT NULL REFERENCES pruebas_lab_catalogo(prueba_lab_id) ON DELETE CASCADE,
            nota TEXT,
            urgencia SMALLINT, -- 1 urgente, 2 prioritaria, 3 rutina
            UNIQUE (enfermedad_id, prueba_lab_id)
        )
        """
    )

    # Tabla alternativa: pruebas/estudios texto (cuando no existan en catálogo)
    db.query(
        """
        CREATE TABLE IF NOT EXISTS enfermedad_pruebas_texto_recomendadas (
            id SERIAL PRIMARY KEY,
            enfermedad_id INT NOT NULL REFERENCES enfermedades(enfermedad_id) ON DELETE CASCADE,
            nombre TEXT NOT NULL,
            nota TEXT,
            urgencia SMALLINT,
            UNIQUE (enfermedad_id, nombre)
        )
        """
    )

    # Semilla mínima: solo insertar si no hay registros
    try:
        has_any = db.fetchone("SELECT EXISTS (SELECT 1 FROM enfermedad_tratamientos_recomendados) ")
        if has_any and has_any[0]:
            return  # ya hay datos
    except Exception:
        # Si falla la consulta por cualquier razón, continuar con semilla best-effort
        pass

    # Helper: obtener enfermedad_id por patrón de nombre
    def get_enf_id(name_like):
        row = db.fetchone(
            "SELECT enfermedad_id FROM enfermedades WHERE nombre ILIKE %s ORDER BY gravedad DESC LIMIT 1",
            (f"%{name_like}%",)
        )
        return row[0] if row else None

    # Helper: obtener prueba_lab_id por nombre
    def get_lab_id(name_like):
        row = db.fetchone(
            "SELECT prueba_lab_id FROM pruebas_lab_catalogo WHERE nombre ILIKE %s LIMIT 1",
            (f"%{name_like}%",)
        )
        return row[0] if row else None

    seeds = [
        {
            "name": "Neumon",
            "tx": [
                ("Amoxicilina-clavulánico", "500/125 mg cada 8h por 5-7 días", "farmacologico", 2),
                ("Azitromicina", "500 mg día 1, luego 250 mg/día 4 días", "farmacologico", 2),
                ("Reposo e hidratación", "Ingesta de líquidos y reposo relativo", "no_farmacologico", 3)
            ],
            "labs": [
                ("Hemograma", "Leucocitosis orienta a infección bacteriana", 2),
                ("Proteína C reactiva", "Inflamación sistémica", 2),
                ("Radiografía de tórax", "Valorar consolidaciones y patrón alveolar", 1)
            ]
        },
        {
            "name": "Bronquitis",
            "tx": [
                ("Antitusígenos", "Si tos seca molesta (p. ej., dextrometorfano)", "farmacologico", 3),
                ("Broncodilatador inhalado", "Salbutamol 1-2 disparos cada 6-8h si sibilancias", "farmacologico", 2)
            ],
            "labs": [
                ("Hemograma", "Descartar infección bacteriana significativa", 3)
            ]
        },
        {
            "name": "Asma",
            "tx": [
                ("Salbutamol inhalado", "2-4 inhalaciones cada 20 min x 1h, luego según respuesta", "farmacologico", 1),
                ("Corticoide sistémico", "Prednisona 40-50 mg/día por 5-7 días en exacerbación", "farmacologico", 1)
            ],
            "labs": [
                ("Sat O2", "Oximetría de pulso para valorar hipoxemia", 1)
            ]
        },
        {
            "name": "Sepsis",
            "tx": [
                ("Antibióticos de amplio espectro", "Administrar en la primera hora", "farmacologico", 1),
                ("Líquidos IV", "Cristaloides 30 ml/kg en la primera hora", "procedimiento", 1)
            ],
            "labs": [
                ("Hemocultivos", "Antes de antibióticos si es posible", 1),
                ("Lactato", "Marcador pronóstico", 1),
                ("Función renal", "Urea y creatinina", 2)
            ]
        },
        {
            "name": "Infarto agudo de miocardio",
            "tx": [
                ("AAS", "160-325 mg masticable una sola vez (si no contraindicado)", "farmacologico", 1),
                ("Nitroglicerina", "0.4 mg SL cada 5 min x 3 si TA lo permite", "farmacologico", 1)
            ],
            "labs": [
                ("Troponina", "Biomarcador de daño miocárdico", 1),
                ("ECG", "Electrocardiograma de 12 derivaciones", 1)
            ]
        },
        {
            "name": "Apendicitis",
            "tx": [
                ("Cirugía: apendicectomía", "Derivar a cirugía general", "procedimiento", 1),
                ("Antibióticos", "Ceftriaxona + metronidazol preoperatorio", "farmacologico", 1)
            ],
            "labs": [
                ("Hemograma", "Leucocitosis con neutrofilia", 2),
                ("PCR", "Marcador inespecífico de inflamación", 3)
            ]
        },
        {
            "name": "ITU",
            "tx": [
                ("Nitrofurantoína", "100 mg cada 12h por 5 días (cistitis no complicada)", "farmacologico", 2)
            ],
            "labs": [
                ("EGO", "EGO/EGO+urocultivo si fiebre o recurrencia", 2)
            ]
        },
        {
            "name": "Meningitis",
            "tx": [
                ("Antibióticos IV", "Ceftriaxona + vancomicina (empírico)", "farmacologico", 1),
                ("Dexametasona", "10 mg IV cada 6h por 4 días (bacteriana)", "farmacologico", 1)
            ],
            "labs": [
                ("Punción lumbar", "Citoquímico de LCR, según indicación y seguridad", 1),
                ("Hemocultivos", "Antes de antibiótico si es posible", 1)
            ]
        },
        {
            "name": "Dengue",
            "tx": [
                ("Hidratación", "VO o IV según signos de alarma", "procedimiento", 1),
                ("Paracetamol", "Evitar AINES", "farmacologico", 2)
            ],
            "labs": [
                ("Hemograma", "Hematocrito y plaquetas para seguimiento", 1)
            ]
        },
        {
            "name": "Pancreatitis",
            "tx": [
                ("Hidratación IV", "Cristaloides agresivos primeras 24-48h", "procedimiento", 1),
                ("Analgesia", "Opioide según dolor", "farmacologico", 1)
            ],
            "labs": [
                ("Amilasa", "Diagnóstico y seguimiento", 1),
                ("Lipasa", "Más específica que amilasa", 1)
            ]
        },
        {
            "name": "Hipoglucemia",
            "tx": [
                ("Glucosa oral o IV", "15-20 g de glucosa oral; en severa, D50 IV", "farmacologico", 1)
            ],
            "labs": [
                ("Glucosa capilar", "Control seriado hasta normalización", 1)
            ]
        }
    ]

    for item in seeds:
        enf_id = get_enf_id(item["name"])
        if not enf_id:
            continue
        # Insertar tratamientos
        for t in item["tx"]:
            nombre_tx, indic, tipo, prioridad = t
            try:
                db.query(
                    """
                    INSERT INTO enfermedad_tratamientos_recomendados
                    (enfermedad_id, tratamiento, indicaciones, tipo, prioridad)
                    VALUES (%s,%s,%s,%s,%s)
                    ON CONFLICT (enfermedad_id, tratamiento) DO NOTHING
                    """,
                    (enf_id, nombre_tx, indic, tipo, prioridad)
                )
            except Exception:
                pass

        # Insertar pruebas: si existen en catálogo, se relacionan; si no, se guardan como texto
        for l in item["labs"]:
            nombre_lab, nota, urgencia = l
            lab_id = get_lab_id(nombre_lab)
            try:
                if lab_id:
                    db.query(
                        """
                        INSERT INTO enfermedad_pruebas_recomendadas
                        (enfermedad_id, prueba_lab_id, nota, urgencia)
                        VALUES (%s,%s,%s,%s)
                        ON CONFLICT (enfermedad_id, prueba_lab_id) DO NOTHING
                        """,
                        (enf_id, lab_id, nota, urgencia)
                    )
                else:
                    db.query(
                        """
                        INSERT INTO enfermedad_pruebas_texto_recomendadas
                        (enfermedad_id, nombre, nota, urgencia)
                        VALUES (%s,%s,%s,%s)
                        ON CONFLICT (enfermedad_id, nombre) DO NOTHING
                        """,
                        (enf_id, nombre_lab, nota, urgencia)
                    )
            except Exception:
                pass

# ---------- Seguridad de contraseña ----------
def normalize_hash_from_db(raw):
    if raw is None:
        return None
    if isinstance(raw, memoryview):
        return raw.tobytes()
    if isinstance(raw, bytes):
        return raw
    if isinstance(raw, str):
        s = raw.strip()
        if s.startswith(("$2a$", "$2b$", "$2y$")):
            return s.encode("utf-8")
        try:
            return bytes.fromhex(s)
        except (ValueError, TypeError):
            pass
        try:
            return base64.b64decode(s)
        except (binascii.Error, ValueError):
            pass
        return s.encode("utf-8")
    try:
        return bytes(raw)
    except Exception:
        return None

def verify_password(password_plain: str, hashed_raw) -> bool:
    hashed = normalize_hash_from_db(hashed_raw)
    if not hashed:
        return False
    try:
        prefix = hashed[:4].decode('utf-8', errors='ignore')
    except Exception:
        prefix = ""
    if not prefix.startswith(("$2a", "$2b", "$2y")):
        return False
    try:
        return bcrypt.checkpw(password_plain.encode('utf-8'), hashed)
    except (ValueError, TypeError):
        return False


def hash_password(password_plain: str) -> str:
    return bcrypt.hashpw(password_plain.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')




# ---------- Interfaz ----------

APP_TITLE = "Gestión Clínica - Demo"

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")
        self.title(APP_TITLE)
        self.geometry("1000x700")
        self.current_user = None
        
        # Asegurar tablas de recomendaciones y datos base
        try:
            ensure_recommended_schema_and_seed()
        except Exception as e:
            # No bloquear la app si falla semilla/esquema; se mostrará en consola
            print("WARN: no se pudo asegurar esquema recomendado:", e)
        
        # Configurar expansión de la ventana principal
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # contenedor principal (stack de frames)
        self.container = ctk.CTkFrame(self)
        self.container.grid(row=0, column=0, sticky="nsew")
        
        # Configurar expansión del contenedor
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self.frames = {}
        for F in (LoginFrame, MainMenuFrame, PacientesFrame, CatalogosFrame, EncuentrosFrame, DiagnosticosFrame, TratamientosFrame, UsuariosFrame):
            page_name = F.__name__
            frame = F(parent=self.container, controller=self)
            self.frames[page_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_frame("LoginFrame")

    def show_frame(self, name):
        frame = self.frames[name]
        frame.tkraise()
        if hasattr(frame, "on_show"):
            frame.on_show()

    def login(self, user_row):
        # user_row: (usuario_id, nombre, correo, rol, hashed_password, ...)
        self.current_user = {
            "usuario_id": user_row[0],
            "nombre": user_row[1],
            "correo": user_row[2],
            "rol": user_row[3]
        }
        self.show_frame("MainMenuFrame")

# ---------- Frame: Tratamientos ----------
class TratamientosFrame(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        top = ctk.CTkFrame(self)
        top.pack(fill="x", pady=(8,6))
        back_btn = ctk.CTkButton(top, text="Volver", command=lambda: controller.show_frame("MainMenuFrame"))
        back_btn.pack(side="left", padx=8)

        btn_add = ctk.CTkButton(top, text="Crear Tratamiento", command=self.open_add_dialog)
        btn_add.pack(side="right", padx=8)

        # Treeview para listar tratamientos
        cols = ("tratamiento_id", "paciente_nombre", "diagnostico", "tratamiento_nombre", "descripcion", "inicio_fecha", "estado")
        container = ctk.CTkFrame(self)
        container.pack(fill="both", expand=True, padx=10, pady=10)

        self.tree = ttk.Treeview(container, columns=cols, show="headings")
        
        # Configurar columnas
        column_widths = {
            "tratamiento_id": 80,
            "paciente_nombre": 150,
            "diagnostico": 150,
            "tratamiento_nombre": 150,
            "descripcion": 200,
            "inicio_fecha": 100,
            "estado": 100
        }
        
        for c in cols:
            self.tree.heading(c, text=c.replace('_', ' ').title())
            self.tree.column(c, width=column_widths.get(c, 120), anchor="w")
        
        self.tree.pack(side="left", fill="both", expand=True)

        vsb = ttk.Scrollbar(container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")

        self.tree.bind("<Double-1>", self.on_edit)

    def on_show(self):
        self.refresh()

    def refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        
        sql = """
        SELECT t.tratamiento_id, p.nombre, e.nombre, t.nombre, 
               SUBSTRING(t.descripcion FROM 1 FOR 50) || CASE WHEN LENGTH(t.descripcion) > 50 THEN '...' ELSE '' END as desc_corta,
               t.inicio_fecha, t.estado
        FROM tratamientos t
        LEFT JOIN diagnosticos d ON t.diagnostico_id = d.diagnostico_id
        LEFT JOIN pacientes p ON d.paciente_id = p.paciente_id
        LEFT JOIN enfermedades e ON d.enfermedad_id = e.enfermedad_id
        ORDER BY t.inicio_fecha DESC
        """
        rows = db.fetchall(sql)
        for r in rows:
            self.tree.insert("", "end", values=r)

    def open_add_dialog(self):
        dlg = TratamientoDialog(self, None, self.refresh)
        dlg.grab_set()

    def on_edit(self, event):
        item = self.tree.selection()
        if not item:
            return
        values = self.tree.item(item[0], "values")
        tratamiento_id = values[0]
        dlg = TratamientoDialog(self, tratamiento_id, self.refresh)
        dlg.grab_set()

class TratamientoDialog(tk.Toplevel):
    def __init__(self, parent, tratamiento_id, on_save):
        super().__init__(parent)
        self.tratamiento_id = tratamiento_id
        self.on_save = on_save
        self.title("Tratamiento Médico")
        self.geometry("700x600")  # Ventana más grande
        self.resizable(True, True)  # Permitir redimensionar

        # Frame principal con scroll
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=12, pady=12)

        # Canvas y scrollbar
        self.canvas = tk.Canvas(main_frame, bg='#2b2b2b', highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ctk.CTkFrame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Bind mouse wheel to canvas
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)

        # Contenido del formulario
        self.create_form(self.scrollable_frame)

        self.cargar_diagnosticos()
        if tratamiento_id:
            self.load()

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def create_form(self, parent):
        # Selección de diagnóstico
        ctk.CTkLabel(parent, text="Diagnóstico *", anchor="w").pack(fill="x", pady=(8,2))
        self.diagnostico_var = tk.StringVar()
        self.diagnostico_cb = ttk.Combobox(parent, textvariable=self.diagnostico_var, state="readonly")
        self.diagnostico_cb.pack(fill="x", pady=(0,8))

        # Nombre del tratamiento
        ctk.CTkLabel(parent, text="Nombre del Tratamiento *", anchor="w").pack(fill="x", pady=(8,2))
        self.nombre = ctk.CTkEntry(parent)
        self.nombre.pack(fill="x", pady=(0,8))

        # Descripción
        ctk.CTkLabel(parent, text="Descripción", anchor="w").pack(fill="x", pady=(8,2))
        self.descripcion = ctk.CTkTextbox(parent, height=120)  # Más alto
        self.descripcion.pack(fill="x", pady=(0,8))

        # Fechas en frame horizontal
        fecha_frame = ctk.CTkFrame(parent)
        fecha_frame.pack(fill="x", pady=(8,0))

        # Fecha Inicio
        fecha_inicio_frame = ctk.CTkFrame(fecha_frame)
        fecha_inicio_frame.pack(side="left", fill="x", expand=True, padx=(0, 5))
        ctk.CTkLabel(fecha_inicio_frame, text="Fecha Inicio *", anchor="w").pack(fill="x", pady=(0,2))
        self.inicio_fecha = ctk.CTkEntry(fecha_inicio_frame, placeholder_text="YYYY-MM-DD")
        self.inicio_fecha.pack(fill="x", pady=(0,8))

        # Fecha Fin
        fecha_fin_frame = ctk.CTkFrame(fecha_frame)
        fecha_fin_frame.pack(side="right", fill="x", expand=True, padx=(5, 0))
        ctk.CTkLabel(fecha_fin_frame, text="Fecha Fin", anchor="w").pack(fill="x", pady=(0,2))
        self.fin_fecha = ctk.CTkEntry(fecha_fin_frame, placeholder_text="YYYY-MM-DD")
        self.fin_fecha.pack(fill="x", pady=(0,8))

        # Estado
        ctk.CTkLabel(parent, text="Estado", anchor="w").pack(fill="x", pady=(8,2))
        self.estado_var = tk.StringVar()
        estado_cb = ttk.Combobox(parent, textvariable=self.estado_var, 
                               values=["Prescrito", "En curso", "Completado", "Cancelado", "Suspendido"])
        estado_cb.pack(fill="x", pady=(0,8))

        # Botones
        footer = ctk.CTkFrame(parent)
        footer.pack(fill="x", pady=(20,0))
        
        save_btn = ctk.CTkButton(footer, text="Guardar", command=self.save)
        save_btn.pack(side="right", padx=6)
        
        del_btn = ctk.CTkButton(footer, text="Eliminar", fg_color="red", command=self.delete)
        del_btn.pack(side="right", padx=6)

        # Espaciador
        ctk.CTkLabel(parent, text="").pack(pady=10)

    def cargar_diagnosticos(self):
        # Cargar diagnósticos disponibles
        sql = """
        SELECT d.diagnostico_id, p.nombre, e.nombre, d.created_at
        FROM diagnosticos d
        LEFT JOIN pacientes p ON d.paciente_id = p.paciente_id
        LEFT JOIN enfermedades e ON d.enfermedad_id = e.enfermedad_id
        ORDER BY d.created_at DESC
        """
        diagnosticos = db.fetchall(sql)
        self.diagnosticos_map = {f"{d[1]} - {d[2]} ({d[3]})": d[0] for d in diagnosticos}
        self.diagnostico_cb['values'] = list(self.diagnosticos_map.keys())

    def load(self):
        # Cargar datos del tratamiento existente
        sql = """
        SELECT diagnostico_id, nombre, descripcion, inicio_fecha, fin_fecha, estado
        FROM tratamientos WHERE tratamiento_id = %s
        """
        row = db.fetchone(sql, (self.tratamiento_id,))
        
        if row:
            # Buscar el diagnóstico correspondiente
            diagnostico_info = db.fetchone("""
                SELECT p.nombre, e.nombre, d.created_at
                FROM diagnosticos d
                LEFT JOIN pacientes p ON d.paciente_id = p.paciente_id
                LEFT JOIN enfermedades e ON d.enfermedad_id = e.enfermedad_id
                WHERE d.diagnostico_id = %s
            """, (row[0],))
            
            if diagnostico_info:
                display_text = f"{diagnostico_info[0]} - {diagnostico_info[1]} ({diagnostico_info[2]})"
                self.diagnostico_var.set(display_text)
            
            self.nombre.insert(0, row[1] or "")
            self.descripcion.insert("1.0", row[2] or "")
            self.inicio_fecha.insert(0, str(row[3] or ""))
            self.fin_fecha.insert(0, str(row[4] or ""))
            self.estado_var.set(row[5] or "Prescrito")

    def save(self):
        # Validaciones
        if not self.diagnostico_var.get() or not self.nombre.get().strip():
            messagebox.showwarning("Validación", "Diagnóstico y Nombre son obligatorios")
            return

        if not self.inicio_fecha.get().strip():
            messagebox.showwarning("Validación", "Fecha de inicio es obligatoria")
            return

        # Obtener ID del diagnóstico
        diagnostico_id = self.diagnosticos_map[self.diagnostico_var.get()]
        
        # Preparar datos
        datos = (
            diagnostico_id,
            self.nombre.get().strip(),
            self.descripcion.get("1.0", "end").strip() or None,
            self.inicio_fecha.get().strip(),
            self.fin_fecha.get().strip() or None,
            self.estado_var.get() or "Prescrito",
            self.master.controller.current_user["usuario_id"]
        )

        if self.tratamiento_id:
            # Actualizar
            sql = """
            UPDATE tratamientos SET 
            diagnostico_id=%s, nombre=%s, descripcion=%s, inicio_fecha=%s, 
            fin_fecha=%s, estado=%s, prescrito_por=%s
            WHERE tratamiento_id=%s
            """
            db.query(sql, datos + (self.tratamiento_id,))
        else:
            # Insertar nuevo
            sql = """
            INSERT INTO tratamientos 
            (diagnostico_id, nombre, descripcion, inicio_fecha, fin_fecha, estado, prescrito_por)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            db.query(sql, datos)

        self.on_save()
        messagebox.showinfo("Éxito", "Tratamiento guardado correctamente")
        self.destroy()

    def delete(self):
        if not self.tratamiento_id:
            messagebox.showwarning("Info", "No hay tratamiento a eliminar")
            return
        
        if messagebox.askyesno("Confirmar", "¿Eliminar tratamiento? Esta acción no se puede deshacer"):
            db.query("DELETE FROM tratamientos WHERE tratamiento_id=%s", (self.tratamiento_id,))
            self.on_save()
            self.destroy()

# ---------- Frame: Diagnósticos ----------
class DiagnosticosFrame(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        top = ctk.CTkFrame(self)
        top.pack(fill="x", pady=(8,6))
        back_btn = ctk.CTkButton(top, text="Volver", command=lambda: controller.show_frame("MainMenuFrame"))
        back_btn.pack(side="left", padx=8)

        btn_add = ctk.CTkButton(top, text="Crear Diagnóstico", command=self.open_add_dialog)
        btn_add.pack(side="right", padx=8)

        # Treeview para listar diagnósticos
        cols = ("diagnostico_id", "paciente_nombre", "enfermedad_nombre", "fecha", "tipo", "probabilidad", "notas")
        container = ctk.CTkFrame(self)
        container.pack(fill="both", expand=True, padx=10, pady=10)

        self.tree = ttk.Treeview(container, columns=cols, show="headings")
        
        # Configurar columnas
        column_widths = {
            "diagnostico_id": 80,
            "paciente_nombre": 150,
            "enfermedad_nombre": 150,
            "fecha": 120,
            "tipo": 100,
            "probabilidad": 100,
            "notas": 200
        }
        
        for c in cols:
            self.tree.heading(c, text=c.replace('_', ' ').title())
            self.tree.column(c, width=column_widths.get(c, 120), anchor="w")
        
        self.tree.pack(side="left", fill="both", expand=True)

        vsb = ttk.Scrollbar(container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")

        self.tree.bind("<Double-1>", self.on_edit)

    def on_show(self):
        self.refresh()

    def refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        
        sql = """
        SELECT d.diagnostico_id, p.nombre, e.nombre, d.created_at, d.tipo, d.probabilidad,
               SUBSTRING(d.notas FROM 1 FOR 50) || CASE WHEN LENGTH(d.notas) > 50 THEN '...' ELSE '' END as notas_corta
        FROM diagnosticos d
        LEFT JOIN pacientes p ON d.paciente_id = p.paciente_id
        LEFT JOIN enfermedades e ON d.enfermedad_id = e.enfermedad_id
        ORDER BY d.created_at DESC
        """
        rows = db.fetchall(sql)
        for r in rows:
            self.tree.insert("", "end", values=r)

    def open_add_dialog(self):
        dlg = DiagnosticoDialog(self, None, self.refresh)
        dlg.grab_set()

    def on_edit(self, event):
        item = self.tree.selection()
        if not item:
            return
        values = self.tree.item(item[0], "values")
        diagnostico_id = values[0]
        dlg = DiagnosticoDialog(self, diagnostico_id, self.refresh)
        dlg.grab_set()
# Síntomas reportados por el paciente (clave, etiqueta)


from typing import Iterable, Mapping, Set, Tuple, List, Dict, Any

from typing import Any, Dict, Iterable, List, Mapping, Set, Tuple

class Rule:
    def __init__(
        self,
        enfermedad_id: Any,
        required_signs: Iterable[str] = None,
        required_symptoms: Iterable[str] = None,
        optional_signs: Mapping[str, float] = None,
        optional_symptoms: Mapping[str, float] = None,
        rule_weight: float = 1.0,
        sign_vs_symptom_balance: float = 0.5,
        rule_id: Any = None
    ):
        self.rule_id = rule_id
        self.enfermedad_id = enfermedad_id
        self.required_signs = set(required_signs or [])
        self.required_symptoms = set(required_symptoms or [])
        self.optional_signs = dict(optional_signs or {})
        self.optional_symptoms = dict(optional_symptoms or {})
        self.rule_weight = float(rule_weight)
        self.sign_vs_symptom_balance = float(sign_vs_symptom_balance)

        # validaciones simples
        if self.rule_weight < 0:
            raise ValueError("rule_weight debe ser >= 0")
        if not (0.0 <= self.sign_vs_symptom_balance <= 1.0):
            raise ValueError("sign_vs_symptom_balance debe estar en [0,1]")
        for w in list(self.optional_signs.values()) + list(self.optional_symptoms.values()):
            if w < 0:
                raise ValueError("pesos en optional_signs/optional_symptoms deben ser >= 0")

    def _partial_score(self, optional_map: Mapping[str, float], evidence_set: Set[str]):
        total_w = sum(optional_map.values())
        if total_w <= 0:
            return None
        present_w = sum(w for s, w in optional_map.items() if s in evidence_set)
        return float(present_w / total_w)

    def match_score(self, present_signs: Set[str], present_symptoms: Set[str]) -> Tuple[float, Dict[str, Any]]:
        """
        Retorna (raw_score, breakdown). Si falta required devuelve score 0 y breakdown con razón.
        raw_score está en rango [0, rule_weight].
        """
        # required checks
        if self.required_signs and not self.required_signs.issubset(present_signs):
            return 0.0, {"reason": "missing_required_signs", "missing": list(self.required_signs - present_signs)}
        if self.required_symptoms and not self.required_symptoms.issubset(present_symptoms):
            return 0.0, {"reason": "missing_required_symptoms", "missing": list(self.required_symptoms - present_symptoms)}

        signs_partial = self._partial_score(self.optional_signs, present_signs)
        symptoms_partial = self._partial_score(self.optional_symptoms, present_symptoms)

        if signs_partial is None:
            signs_score = 1.0 if self.required_signs else 0.0
        else:
            signs_score = signs_partial

        if symptoms_partial is None:
            symptoms_score = 1.0 if self.required_symptoms else 0.0
        else:
            symptoms_score = symptoms_partial

        balance = self.sign_vs_symptom_balance
        combined = balance * signs_score + (1.0 - balance) * symptoms_score
        raw_score = float(self.rule_weight * combined)

        breakdown = {
            "rule_id": self.rule_id,
            "enfermedad_id": self.enfermedad_id,
            "required_signs": list(self.required_signs),
            "required_symptoms": list(self.required_symptoms),
            "signs_score": signs_score,
            "symptoms_score": symptoms_score,
            "combined_ratio": combined,
            "rule_weight": self.rule_weight,
            "raw_score": raw_score
        }
        return raw_score, breakdown

    def match_score_ignore_required(self, present_signs: Set[str], present_symptoms: Set[str]) -> Tuple[float, Dict[str, Any]]:
        """Versión suave que no falla por requireds (usada en fallback)."""
        signs_partial = self._partial_score(self.optional_signs, present_signs)
        symptoms_partial = self._partial_score(self.optional_symptoms, present_symptoms)

        signs_score = 1.0 if signs_partial is None and self.required_signs else (signs_partial or 0.0)
        symptoms_score = 1.0 if symptoms_partial is None and self.required_symptoms else (symptoms_partial or 0.0)

        combined = self.sign_vs_symptom_balance * signs_score + (1 - self.sign_vs_symptom_balance) * symptoms_score
        raw_score = float(self.rule_weight * combined)
        return raw_score, {"note": "soft_ignore_required", "raw_score": raw_score}

class InferenceEngine:
    def __init__(self, rules: Iterable[Rule] = None):
        self.rules: List[Rule] = list(rules or [])

    def add_rule(self, rule: Rule) -> None:
        self.rules.append(rule)

    def infer(self, present_signs: Set[str], present_symptoms: Set[str]) -> List[Tuple[Any, float, List[Any]]]:
        scores: Dict[Any, float] = {}
        details: Dict[Any, List[Tuple[Any, float, Dict[str, Any]]]] = {}

        for rule in self.rules:
            s, breakdown = rule.match_score(present_signs, present_symptoms)
            if s <= 0:
                continue
            eid = rule.enfermedad_id
            scores[eid] = scores.get(eid, 0.0) + s
            details.setdefault(eid, []).append((rule.rule_id, s, breakdown))

        if not scores:
            return []

        total = sum(scores.values())
        if total <= 1e-12:
            n = len(scores)
            results = []
            for eid in scores:
                prob = 100.0 / n
                results.append((eid, prob, details.get(eid, [])))
            results.sort(key=lambda x: x[1], reverse=True)
            return results

        results = []
        for eid, v in scores.items():
            prob = (v / total) * 100.0
            results.append((eid, prob, details.get(eid, [])))
        results.sort(key=lambda x: x[1], reverse=True)
        return results


SINTOMAS_LIST = [
    ("fiebre", "Fiebre (sensación de calor)"),
    ("escalofrios", "Escalofríos"),
    ("tos", "Tos"),
    ("disnea", "Disnea / Dificultad para respirar"),
    ("dolor_pecho", "Dolor torácico / Dolor en el pecho"),
    ("dolor_abdominal", "Dolor abdominal"),
    ("nausea", "Náusea"),
    ("vomito", "Vómito"),
    ("diarrea", "Diarrea"),
    ("cefalea", "Cefalea / Dolor de cabeza"),
    ("mareo", "Mareo / Vértigo"),
    ("confusion", "Confusión"),
    ("perdida_conciencia", "Pérdida de conciencia"),
    ("prurito", "Prurito"),
    ("dolor_articular", "Dolor articular"),
    ("dolor_muscular", "Dolor muscular"),
    ("odinofagia", "Odinofagia / Dolor al tragar"),
    ("rinorrea", "Secreción nasal / Rinorrea"),
    ("estornudos", "Estornudos"),
    ("anosmia", "Pérdida de olfato (Anosmia)"),
    ("ageusia", "Pérdida de gusto (Ageusia)"),
    ("fatiga", "Fatiga"),
    ("sudoracion_nocturna", "Sudoración nocturna"),
    ("dolor_pecho_radiado", "Dolor torácico irradiado"),
    ("poliaquiuria", "Poliaquiuria / Micciones frecuentes"),
    ("disuria", "Disuria / Dolor al orinar"),
    ("diaforesis", "Diaforesis / Sudoración profusa"),
    ("astenia", "Astenia / Debilidad general")
]

SIGNOS_LIST = [
    ("fiebre_obj", "Fiebre (medida)"),
    ("taquicardia", "Taquicardia"),
    ("bradicardia", "Bradicardia"),
    ("hipotension", "Hipotensión"),
    ("hipertension", "Hipertensión"),
    ("cianosis", "Cianosis"),
    ("palidez", "Palidez"),
    ("ictericia", "Ictericia"),
    ("lesion_cutanea", "Lesión cutánea / Exantema"),
    ("adenopatias", "Adenopatías palpables"),
    ("taquipnea", "Taquipnea"),
    ("bradipnea", "Bradipnea"),
    ("hipoxia", "Hipoxia (SpO2 baja)"),
    ("rales_respiratorios", "Rales / Crepitos"),
    ("sibilancias", "Sibilancias"),
    ("murmullo_reducido", "Murmullo vesicular reducido"),
    ("distension_abdominal", "Distensión abdominal"),
    ("hepatomegalia", "Hepatomegalia"),
    ("esplenomegalia", "Esplenomegalia"),
    ("signos_meningeos", "Signos meníngeos (rigidez nucal)"),
    ("paresia_paralisis", "Paresia / Parálisis focal"),
    ("arritmia", "Arritmia (observada/ECG)"),
    ("edema_periferico", "Edema periférico"),
    ("oliguria", "Oliguria"),
    ("sincope", "Síncope observado"),
    ("hemorragia_activa", "Hemorragia activa")
]

SYNONYMS = {
    "dificultad_respiratoria": "disnea",
    "dificultad-respiratoria": "disnea",
    "polaquiuria": "poliaquiuria",
    "congestion": "rinorrea",
    "rash": "lesion_cutanea",
    "rash_cutaneo": "lesion_cutanea",
    "sudoracion": "diaforesis",
    "sudoracion_nocturna": "sudoracion_nocturna",
    "fiebre_medida": "fiebre_obj",
    # añade más según sea necesario
}

def normalize_set(raw_set):
    """Devuelve un set con las claves normalizadas por SYNONYMS."""
    return {SYNONYMS.get(k, k) for k in raw_set}



RULES = [
    Rule(
        enfermedad_id="Neumonia",
        required_signs=["rales_respiratorios"],
        required_symptoms=["fiebre"],
        optional_signs={"hipoxia": 1.0, "taquipnea": 0.6, "fiebre_obj": 0.8},
        optional_symptoms={"tos": 0.8, "dolor_pecho": 0.5, "disnea": 0.9},
        rule_weight=1.6,
        sign_vs_symptom_balance=0.7,
        rule_id="r_neumo_1"
    ),
    Rule(
        enfermedad_id="Bronquitis",
        required_symptoms=["tos"],
        optional_signs={"sibilancias": 0.6, "rales_respiratorios": 0.3},
        optional_symptoms={"escalofrios": 0.2, "dolor_pecho": 0.2},
        rule_weight=0.9,
        sign_vs_symptom_balance=0.4,
        rule_id="r_bronq_1"
    ),
    Rule(
        enfermedad_id="Asma",
        required_signs=["sibilancias"],
        required_symptoms=["disnea"],
        optional_signs={"taquipnea": 0.5},
        optional_symptoms={"tos": 0.6, "fatiga": 0.2},
        rule_weight=1.2,
        sign_vs_symptom_balance=0.6,
        rule_id="r_asma_1"
    ),
    Rule(
        enfermedad_id="Gripe",
        required_symptoms=["fiebre", "dolor_muscular"],
        optional_signs={"fiebre_obj": 0.8},
        optional_symptoms={"tos": 0.6, "rinorrea": 0.3, "anosmia": 0.1},
        rule_weight=1.0,
        sign_vs_symptom_balance=0.3,
        rule_id="r_gripe_1"
    ),
    Rule(
        enfermedad_id="Resfriado",
        required_symptoms=["rinorrea"],
        optional_symptoms={"estornudos": 0.7, "odinofagia": 0.3},
        optional_signs={},
        rule_weight=0.7,
        sign_vs_symptom_balance=0.2,
        rule_id="r_resf_1"
    ),
    Rule(
        enfermedad_id="Sepsis",
        required_signs=["hipoxia"],
        required_symptoms=["fiebre"],
        optional_signs={"taquicardia": 0.7, "hipotension": 0.8},
        optional_symptoms={"confusion": 0.5, "oliguria": 0.6},
        rule_weight=2.0,
        sign_vs_symptom_balance=0.7,
        rule_id="r_sepsis_1"
    ),
    Rule(
        enfermedad_id="IAM",
        required_symptoms=["dolor_pecho"],
        optional_signs={"taquicardia": 0.4, "hipotension": 0.5, "arritmia": 0.6},
        optional_symptoms={"diaforesis": 0.6, "mareo": 0.3, "nausea": 0.2},
        rule_weight=1.8,
        sign_vs_symptom_balance=0.5,
        rule_id="r_iam_1"
    ),
    Rule(
        enfermedad_id="Apendicitis",
        required_symptoms=["dolor_abdominal"],
        optional_signs={"distension_abdominal": 0.4, "fiebre_obj": 0.3},
        optional_symptoms={"nausea": 0.6, "vomito": 0.5},
        rule_weight=1.0,
        sign_vs_symptom_balance=0.4,
        rule_id="r_apend_1"
    ),
    Rule(
        enfermedad_id="ITU",
        required_symptoms=["disuria"],
        optional_symptoms={"poliaquiuria": 0.8, "disuria": 1.0},
        optional_signs={"fiebre_obj": 0.3},
        rule_weight=0.8,
        sign_vs_symptom_balance=0.2,
        rule_id="r_itu_1"
    ),
    Rule(
        enfermedad_id="Meningitis",
        required_signs=["signos_meningeos"],
        required_symptoms=["cefalea", "fiebre"],
        optional_signs={"confusion": 0.6},
        optional_symptoms={"vomito": 0.4},
        rule_weight=1.9,
        sign_vs_symptom_balance=0.8,
        rule_id="r_mening_1"
    ),
    Rule(
        enfermedad_id="Dengue",
        required_symptoms=["fiebre", "dolor_muscular"],
        optional_symptoms={"sudoracion_nocturna": 0.2, "prurito": 0.5},
        optional_signs={"lesion_cutanea": 0.6, "hipotension": 0.4},
        rule_weight=1.3,
        sign_vs_symptom_balance=0.3,
        rule_id="r_dengue_1"
    ),
    Rule(
        enfermedad_id="Pancreatitis",
        required_symptoms=["dolor_abdominal"],
        optional_signs={"ictericia": 0.3},
        optional_symptoms={"vomito": 0.6, "fiebre": 0.2},
        rule_weight=1.1,
        sign_vs_symptom_balance=0.3,
        rule_id="r_pancr_1"
    ),
    Rule(
        enfermedad_id="Hipoglucemia",
        required_signs=[],
        required_symptoms=["confusion", "mareo"],
        optional_signs={"diaforesis": 0.6},
        optional_symptoms={"diaforesis": 0.5},
        rule_weight=1.0,
        sign_vs_symptom_balance=0.2,
        rule_id="r_hipo_1"
    )
]

def validate_rules(rules, sintomas_list, signos_list):
    valid_sintomas = {k for k, _ in sintomas_list}
    valid_signos = {k for k, _ in signos_list}
    report = {}
    for rule in rules:
        unknown = {"required_signs": [], "required_symptoms": [],
                   "optional_signs": [], "optional_symptoms": []}

        def check_iterables(iterable, target_set, bucket):
            for item in (iterable or []):
                if item not in target_set:
                    bucket.append(item)

        check_iterables(rule.required_signs, valid_signos, unknown["required_signs"])
        check_iterables(rule.required_symptoms, valid_sintomas, unknown["required_symptoms"])
        check_iterables(rule.optional_signs.keys(), valid_signos, unknown["optional_signs"])
        check_iterables(rule.optional_symptoms.keys(), valid_sintomas, unknown["optional_symptoms"])

        # sugerir correcciones
        suggestions = {}
        for cat, items in unknown.items():
            suggestions[cat] = {}
            target = valid_signos if "sign" in cat else valid_sintomas
            for it in items:
                cands = difflib.get_close_matches(it, target, n=3, cutoff=0.5)
                suggestions[cat][it] = cands
        report[rule.rule_id or str(rule.enfermedad_id)] = {"unknown": unknown, "suggestions": suggestions}
    return report



class DiagnosticoDialog(tk.Toplevel):



    def __init__(self, parent, diagnostico_id, on_save):
        super().__init__(parent)
        self.diagnostico_id = diagnostico_id
        self.on_save = on_save
        self.title("Diagnóstico Médico")
        self.geometry("700x600")
        self.resizable(True, True)

        # Frame principal con scroll
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=12, pady=12)

        # Canvas y scrollbar
        self.canvas = tk.Canvas(main_frame, bg='#2b2b2b', highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ctk.CTkFrame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Bind mouse wheel to canvas
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)

        # Contenido del formulario
        self.create_form(self.scrollable_frame)

        self.cargar_comboboxes()
        if diagnostico_id:
            self.load()

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")


    def run_inference(self):
        """
        Inferencia que muestra todos los candidatos (firmes + suaves) en la tabla.
        Requisitos de atributos en self: signo_vars, sintoma_vars, enfermedad_var,
        probabilidad (Entry-like), infer_result_var, enfermedades_map (opt), results_tree creado.
        """
        try:
            print("DEBUG: botón inferir pulsado")
            raw_present_signs = {k for k, v in self.signo_vars.items() if v.get()}
            raw_present_symptoms = {k for k, v in self.sintoma_vars.items() if v.get()}

            present_signs = normalize_set(raw_present_signs)
            present_symptoms = normalize_set(raw_present_symptoms)

            print("DEBUG present_signs:", present_signs)
            print("DEBUG present_symptoms:", present_symptoms)

            engine = InferenceEngine(rules=RULES)
            print("DEBUG num rules:", len(engine.rules))

            # 1) Resultados firmes (respetan requireds)
            firm_results = engine.infer(present_signs, present_symptoms)  # [(eid, prob_pct, details), ...]
            print("DEBUG firm_results:", firm_results)

            # 2) Resultados suaves (ignoran requireds)
            soft_scores = {}
            soft_details = {}
            for rule in engine.rules:
                s, breakdown = rule.match_score_ignore_required(present_signs, present_symptoms)
                if s <= 0:
                    continue
                eid = rule.enfermedad_id
                soft_scores[eid] = soft_scores.get(eid, 0.0) + s
                soft_details.setdefault(eid, []).append((rule.rule_id, s, breakdown))

            soft_results = []
            if soft_scores:
                total_soft = sum(soft_scores.values())
                soft_results = [(eid, (v / total_soft) * 100.0, soft_details.get(eid, [])) for eid, v in soft_scores.items()]
                soft_results.sort(key=lambda x: x[1], reverse=True)
            print("DEBUG soft_results:", soft_results)

            # 3) Combinar: mantener probabilidades firmes, añadir suaves para eids no presentes
            combined_map = {}   # eid -> (score_raw_equivalent, details)
            # convert firm_results pct back to raw-like values to combine meaningfully:
            for eid, prob_pct, details in firm_results:
                # store a pseudo-raw score proportional to prob (we'll renormalize later)
                combined_map[eid] = {"score": prob_pct, "details": details, "source": "firm"}

            for eid, prob_pct, details in soft_results:
                if eid in combined_map:
                    # ya existe firme, no sobrescribir pero agregar detalles
                    combined_map[eid]["details"].extend(details)
                    # opcional: keep source as 'firm'
                else:
                    combined_map[eid] = {"score": prob_pct, "details": details, "source": "soft"}

            # Si no hay ningun resultado (ni firm ni soft)
            if not combined_map:
                self.infer_result_var.set("No se encontraron coincidencias.")
                self._last_infer_details = {"mode": "none", "raw_signs": raw_present_signs, "raw_symptoms": raw_present_symptoms}
                # limpiar tabla
                self.update_results_table([])
                return

            # 4) Normalizar scores combinados a porcentajes (suma 100)
            total_score = sum(v["score"] for v in combined_map.values())
            if total_score <= 1e-12:
                # si total cero por alguna razón, distribuir uniformemente
                n = len(combined_map)
                results = [(eid, 100.0 / n, data["details"]) for eid, data in combined_map.items()]
            else:
                results = [(eid, (data["score"] / total_score) * 100.0, data["details"]) for eid, data in combined_map.items()]

            # ordenar por prob desc
            results.sort(key=lambda x: x[1], reverse=True)

            # 5) Actualizar tabla con TODOS los candidatos
            print("DEBUG combined results to show:", results)
            self.update_results_table(results)

            # guardar detalles completos
            self._last_infer_details = {"mode": "combined", "firm": firm_results, "soft": soft_results, "combined": results}

            # 6) Poner el mejor en combobox/entrada de probabilidad
            best_eid, best_prob, best_details = results[0]
            setted = False
            if getattr(self, "enfermedades_map", None):
                for display_name, eid in self.enfermedades_map.items():
                    if str(eid) == str(best_eid) or str(display_name).lower().startswith(str(best_eid).lower()):
                        self.enfermedad_var.set(display_name)
                        setted = True
                        break
            if not setted:
                try:
                    self.enfermedad_var.set(str(best_eid))
                except Exception:
                    pass

            try:
                self.probabilidad.delete(0, tk.END)
                self.probabilidad.insert(0, f"{round(best_prob, 2)}")
            except Exception:
                pass

            self.infer_result_var.set(f"Mejor: {best_eid} — {round(best_prob,2)}%")
            print("DEBUG detalle por enfermedad:")
            pprint.pprint(self._last_infer_details)

        except Exception as exc:
            print("ERROR en run_inference:", exc)
            try:
                self.infer_result_var.set(f"Error durante inferencia: {str(exc)}")
            except Exception:
                pass

    
     

    # Métodos de la clase: creación y actualización de la tabla

    def create_results_table(self, parent):
        """
        Crea un Treeview con columnas: Enfermedad | Probabilidad | Detalle.
        Se guarda en self.results_tree.
        """
        # Contenedor que añade un borde y scrollbar (ttk.Treeview se integra mejor con scrollbars)
        container = tk.Frame(parent)
        container.pack(fill="both", expand=True, padx=4, pady=4)

        columns = ("enfermedad", "prob", "detalle")
        tree = ttk.Treeview(container, columns=columns, show="headings", height=6)

        tree.heading("enfermedad", text="Enfermedad")
        tree.heading("prob", text="Probabilidad (%)")
        tree.heading("detalle", text="Detalle")

        tree.column("enfermedad", width=180, anchor="w")
        tree.column("prob", width=110, anchor="center")
        tree.column("detalle", width=360, anchor="w")

        vsb = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(container, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        # Bind doble click para ver recomendaciones
        tree.bind("<Double-1>", self.on_result_double_click)

        self.results_tree = tree

    def _resolve_enfermedad_id_from_label(self, label: str):
        """Resuelve enfermedad_id a partir del texto mostrado en la tabla.
        Intenta usar el mapa precargado y, si falla, consulta por nombre aproximado.
        """
        if not label:
            return None
        # 1) mapa cargado en el combobox (nombre -> id)
        try:
            if getattr(self, "enfermedades_map", None):
                # coincidencia exacta
                if label in self.enfermedades_map:
                    return self.enfermedades_map[label]
                # aproximado por prefijo/casefold
                lab_cf = str(label).casefold()
                for nombre, eid in self.enfermedades_map.items():
                    if str(nombre).casefold().startswith(lab_cf) or lab_cf in str(nombre).casefold():
                        return eid
        except Exception:
            pass

        # 2) consulta directa a BD
        try:
            row = db.fetchone(
                "SELECT enfermedad_id FROM enfermedades WHERE nombre ILIKE %s ORDER BY gravedad DESC LIMIT 1",
                (f"%{label}%",)
            )
            return row[0] if row else None
        except Exception:
            return None

    def on_result_double_click(self, event):
        try:
            sel = self.results_tree.selection()
            if not sel:
                return
            vals = self.results_tree.item(sel[0], "values")
            enf_label = vals[0]
            enf_id = self._resolve_enfermedad_id_from_label(enf_label)
            self.show_recommendations_dialog(enf_id, enf_label)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir recomendaciones: {e}")

    def show_recommendations_dialog(self, enfermedad_id, enfermedad_label: str):
        dlg = tk.Toplevel(self)
        dlg.title(f"Recomendaciones: {enfermedad_label}")
        dlg.geometry("700x500")
        dlg.resizable(True, True)

        root = ctk.CTkFrame(dlg)
        root.pack(fill="both", expand=True, padx=12, pady=12)

        # Encabezado
        ctk.CTkLabel(root, text=f"Enfermedad: {enfermedad_label}", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", pady=(0,8))

        body = ctk.CTkFrame(root)
        body.pack(fill="both", expand=True)

        # Panel izquierdo: Tratamientos
        left = ctk.CTkFrame(body)
        left.pack(side="left", fill="both", expand=True, padx=(0,6))
        ctk.CTkLabel(left, text="Tratamientos sugeridos", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(0,4))
        tx_cols = ("tratamiento", "indicaciones", "tipo", "prioridad")
        tx_tree = ttk.Treeview(left, columns=tx_cols, show="headings", height=8)
        for c in tx_cols:
            tx_tree.heading(c, text=c.title())
        tx_tree.column("tratamiento", width=180)
        tx_tree.column("indicaciones", width=280)
        tx_tree.column("tipo", width=120)
        tx_tree.column("prioridad", width=90, anchor="center")
        tx_tree.pack(fill="both", expand=True)

        # Panel derecho: Pruebas de laboratorio
        right = ctk.CTkFrame(body)
        right.pack(side="left", fill="both", expand=True, padx=(6,0))
        ctk.CTkLabel(right, text="Pruebas de laboratorio", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(0,4))
        lab_cols = ("prueba", "nota", "urgencia")
        lab_tree = ttk.Treeview(right, columns=lab_cols, show="headings", height=8)
        for c in lab_cols:
            lab_tree.heading(c, text=c.title())
        lab_tree.column("prueba", width=220)
        lab_tree.column("nota", width=260)
        lab_tree.column("urgencia", width=90, anchor="center")
        lab_tree.pack(fill="both", expand=True)

        # Cargar datos
        if not enfermedad_id:
            # Aviso cuando no se puede mapear con BD
            messagebox.showinfo(
                "Información",
                "No se pudo vincular la enfermedad con el catálogo para mostrar recomendaciones."
            )
            return

        try:
            # Tratamientos
            tx_rows = db.fetchall(
                """
                SELECT tratamiento, COALESCE(indicaciones, ''), COALESCE(tipo, ''), COALESCE(prioridad, 0)
                FROM enfermedad_tratamientos_recomendados
                WHERE enfermedad_id = %s
                ORDER BY COALESCE(prioridad, 99), tratamiento
                """,
                (enfermedad_id,)
            )
            # Si hay específicos (prioridad <= 2), ocultar genéricos (prioridad >= 3) con nombres comunes
            has_specific_tx = any((r[3] or 99) <= 2 for r in tx_rows)
            if has_specific_tx:
                filtered_tx = [
                    r for r in tx_rows
                    if (r[3] or 99) <= 2 or r[0] not in ("Manejo sintomático", "Analgesia/antitérmico")
                ]
            else:
                filtered_tx = tx_rows

            for r in filtered_tx:
                tx_tree.insert("", "end", values=r)

            if not filtered_tx:
                tx_tree.insert("", "end", values=("—", "No hay tratamientos registrados", "", ""))

            # Pruebas desde catálogo
            lab_rows = db.fetchall(
                """
                SELECT plc.nombre, COALESCE(epr.nota, ''), COALESCE(epr.urgencia, 0)
                FROM enfermedad_pruebas_recomendadas epr
                JOIN pruebas_lab_catalogo plc ON plc.prueba_lab_id = epr.prueba_lab_id
                WHERE epr.enfermedad_id = %s
                ORDER BY COALESCE(epr.urgencia, 99), plc.nombre
                """,
                (enfermedad_id,)
            )

            # Pruebas en texto libre
            lab_rows_text = db.fetchall(
                """
                SELECT nombre, COALESCE(nota, ''), COALESCE(urgencia, 0)
                FROM enfermedad_pruebas_texto_recomendadas
                WHERE enfermedad_id = %s
                ORDER BY COALESCE(urgencia, 99), nombre
                """,
                (enfermedad_id,)
            )

            # Si hay específicas (urgencia <= 2 o notas no genéricas), ocultar genéricas ("Estudio básico"/"Perfil básico")
            def is_specific_lab(row):
                urg = row[2] or 99
                nota = (row[1] or "").strip().lower()
                return urg <= 2 or (nota not in ("estudio básico", "perfil básico"))

            has_specific_labs = any(is_specific_lab(r) for r in (lab_rows + lab_rows_text))
            if has_specific_labs:
                filtered_labs = [r for r in lab_rows if is_specific_lab(r)]
                filtered_labs_text = [r for r in lab_rows_text if is_specific_lab(r)]
            else:
                filtered_labs = lab_rows
                filtered_labs_text = lab_rows_text

            for r in filtered_labs:
                lab_tree.insert("", "end", values=r)
            for r in filtered_labs_text:
                lab_tree.insert("", "end", values=r)

            if not filtered_labs and not filtered_labs_text:
                lab_tree.insert("", "end", values=("—", "No hay pruebas registradas", ""))
        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar recomendaciones: {e}")


    def update_results_table(self, results, mode="firm"):
        """
        Rellena self.results_tree con `results`.
        results: lista de tuplas (enfermedad_id, prob_pct, details_list)
        details_list: [(rule_id, raw_score, breakdown_dict), ...] o similar
        mode: "firm" | "soft" para prefijos en la etiqueta resumen si lo necesitas
        """
        # limpiar tabla
        for iid in self.results_tree.get_children():
            self.results_tree.delete(iid)

        if not results:
            self.infer_result_var.set("No se encontraron coincidencias.")
            return

        # Insertar filas ordenadas
        for eid, prob, details in results:
            # Generar texto de detalle legible: listar reglas y contribuciones
            if details:
                parts = []
                for item in details:
                    # soportar tuplas (rule_id, score, breakdown) o (rule_id, score)
                    if len(item) >= 3:
                        rule_id, score, breakdown = item[0], item[1], item[2]
                    else:
                        rule_id, score = item[0], item[1]
                        breakdown = {}
                    parts.append(f"{rule_id}:{round(float(score),2)}")
                detalle_txt = "; ".join(parts)
            else:
                detalle_txt = ""

            # Añadir fila a Treeview
            self.results_tree.insert("", "end", values=(str(eid), f"{round(prob,2)}", detalle_txt))

        # Seleccionar la primera fila y actualizar resumen compacto
        first = self.results_tree.get_children()
        if first:
            first_vals = self.results_tree.item(first[0], "values")
            mejor_enf = first_vals[0]
            mejor_prob = first_vals[1]
            self.infer_result_var.set(f"Mejor: {mejor_enf} — {mejor_prob}%")
        else:
            self.infer_result_var.set("No se encontraron coincidencias.")



    def create_form(self, parent):
        # Selección de paciente
        ctk.CTkLabel(parent, text="Paciente *", anchor="w").pack(fill="x", pady=(8,2))
        self.paciente_var = tk.StringVar()
        self.paciente_cb = ttk.Combobox(parent, textvariable=self.paciente_var, state="readonly")
        self.paciente_cb.pack(fill="x", pady=(0,8))
        self.paciente_cb.bind('<<ComboboxSelected>>', self.on_paciente_select)

        # Selección de encuentro (se llena cuando se selecciona paciente)
        ctk.CTkLabel(parent, text="Encuentro", anchor="w").pack(fill="x", pady=(8,2))
        self.encuentro_var = tk.StringVar()
        self.encuentro_cb = ttk.Combobox(parent, textvariable=self.encuentro_var, state="readonly")
        self.encuentro_cb.pack(fill="x", pady=(0,8))

        # Selección de enfermedad
        ctk.CTkLabel(parent, text="Enfermedad *", anchor="w").pack(fill="x", pady=(8,2))
        self.enfermedad_var = tk.StringVar()
        self.enfermedad_cb = ttk.Combobox(parent, textvariable=self.enfermedad_var, state="readonly")
        self.enfermedad_cb.pack(fill="x", pady=(0,8))

        # Tipo y probabilidad en frame horizontal
        tipo_prob_frame = ctk.CTkFrame(parent)
        tipo_prob_frame.pack(fill="x", pady=(8,0))

        # Tipo de diagnóstico
        tipo_frame = ctk.CTkFrame(tipo_prob_frame)
        tipo_frame.pack(side="left", fill="x", expand=True, padx=(0, 5))
        ctk.CTkLabel(tipo_frame, text="Tipo de Diagnóstico", anchor="w").pack(fill="x", pady=(0,2))
        self.tipo_var = tk.StringVar()
        tipo_cb = ttk.Combobox(tipo_frame, textvariable=self.tipo_var, values=["Presuntivo", "Definitivo", "Diferencial"])
        tipo_cb.pack(fill="x", pady=(0,8))
        
        # Probabilidad
        prob_frame = ctk.CTkFrame(tipo_prob_frame)
        prob_frame.pack(side="right", fill="x", expand=True, padx=(5, 0))
        ctk.CTkLabel(prob_frame, text="Probabilidad (0-100)", anchor="w").pack(fill="x", pady=(0,2))
        self.probabilidad = ctk.CTkEntry(prob_frame, placeholder_text="Ej: 85")
        self.probabilidad.pack(fill="x", pady=(0,8))

                        # ------- Inicio sección Signos y Síntomas -------
        ctk.CTkLabel(parent, text="Signos (observables por el doctor)", anchor="w").pack(fill="x", pady=(8,2))
        self.signos_list = [
            ("fiebre_obj", "Fiebre (medida)"),
            ("taquicardia", "Taquicardia"),
            ("bradicardia", "Bradicardia"),
            ("hipotension", "Hipotensión"),
            ("hipertension", "Hipertensión"),
            ("cianosis", "Cianosis"),
            ("palidez", "Palidez"),
            ("ictericia", "Ictericia"),
            ("lesion_cutanea", "Lesión cutánea / Exantema"),
            ("adenopatias", "Adenopatías palpables"),
            ("taquipnea", "Taquipnea"),
            ("bradipnea", "Bradipnea"),
            ("hipoxia", "Hipoxia (SpO2 baja)"),
            ("rales_respiratorios", "Rales / Crepitos"),
            ("sibilancias", "Sibilancias"),
            ("murmullo_reducido", "Murmullo vesicular reducido"),
            ("distension_abdominal", "Distensión abdominal"),
            ("hepatomegalia", "Hepatomegalia"),
            ("esplenomegalia", "Esplenomegalia"),
            ("signos_meningeos", "Signos meníngeos (rigidez nucal)"),
            ("paresia_paralisis", "Paresia / Parálisis focal"),
            ("arritmia", "Arritmia (observada/ECG)"),
            ("edema_periferico", "Edema periférico"),
            ("oliguria", "Oliguria"),
            ("sincope", "Síncope observado"),
            ("hemorragia_activa", "Hemorragia activa")
        ]

        signos_frame = ctk.CTkFrame(parent)
        signos_frame.pack(fill="x", pady=(0,8))
        self.signo_vars = {}
        for key, label in self.signos_list:
            var = tk.BooleanVar(value=False)
            cb = ctk.CTkCheckBox(signos_frame, text=label, variable=var)
            cb.pack(anchor="w", padx=4, pady=2)
            self.signo_vars[key] = var

        ctk.CTkLabel(parent, text="Síntomas (reportados por el paciente)", anchor="w").pack(fill="x", pady=(8,2))
        self.sintomas_list = [
            ("fiebre", "Fiebre (sensación de calor)"),
            ("escalofrios", "Escalofríos"),
            ("tos", "Tos"),
            ("disnea", "Disnea / Dificultad para respirar"),
            ("dolor_pecho", "Dolor torácico / Dolor en el pecho"),
            ("dolor_abdominal", "Dolor abdominal"),
            ("nausea", "Náusea"),
            ("vomito", "Vómito"),
            ("diarrea", "Diarrea"),
            ("cefalea", "Cefalea / Dolor de cabeza"),
            ("mareo", "Mareo / Vértigo"),
            ("confusion", "Confusión"),
            ("perdida_conciencia", "Pérdida de conciencia"),
            ("prurito", "Prurito"),
            ("dolor_articular", "Dolor articular"),
            ("dolor_muscular", "Dolor muscular"),
            ("odinofagia", "Odinofagia / Dolor al tragar"),
            ("rinorrea", "Secreción nasal / Rinorrea"),
            ("estornudos", "Estornudos"),
            ("anosmia", "Pérdida de olfato (Anosmia)"),
            ("ageusia", "Pérdida de gusto (Ageusia)"),
            ("fatiga", "Fatiga"),
            ("sudoracion_nocturna", "Sudoración nocturna"),
            ("dolor_pecho_radiado", "Dolor torácico irradiado"),
            ("poliaquiuria", "Poliaquiuria / Micciones frecuentes"),
            ("disuria", "Disuria / Dolor al orinar"),
            ("diaforesis", "Diaforesis / Sudoración profusa"),
            ("astenia", "Astenia / Debilidad general")
        ]

        sintomas_frame = ctk.CTkFrame(parent)
        sintomas_frame.pack(fill="x", pady=(0,8))
        self.sintoma_vars = {}
        for key, label in self.sintomas_list:
            var = tk.BooleanVar(value=False)
            cb = ctk.CTkCheckBox(sintomas_frame, text=label, variable=var)
            cb.pack(anchor="w", padx=4, pady=2)
            self.sintoma_vars[key] = var

        # Botones inferencia
        bottom_row = ctk.CTkFrame(parent)
        bottom_row.pack(fill="x", pady=(6,8))

        # Frame izquierdo: botones y etiqueta resumen
        inf_frame = ctk.CTkFrame(bottom_row)
        inf_frame.pack(side="left", fill="x", expand=False, padx=(0,8))

        infer_btn = ctk.CTkButton(inf_frame, text="Inferir diagnóstico", command=self.run_inference)
        infer_btn.pack(side="left", padx=(0,8))

        self.infer_result_var = tk.StringVar(value="")
        inf_lbl = ctk.CTkLabel(inf_frame, textvariable=self.infer_result_var, anchor="w")
        inf_lbl.pack(side="left", fill="x", expand=True)

        # Frame derecho: tabla de resultados
        results_container = ctk.CTkFrame(bottom_row)
        results_container.pack(side="right", fill="both", expand=True)

        # Crear la tabla (Treeview dentro de results_container)
        self.create_results_table(results_container)

    # ... (resto de create_form)


        
        # ------- Fin sección Signos y Síntomas -------
    
        # Notas
        ctk.CTkLabel(parent, text="Notas y Observaciones", anchor="w").pack(fill="x", pady=(8,2))
        self.notas = ctk.CTkTextbox(parent, height=150)
        self.notas.pack(fill="both", expand=True, pady=(0,8))

        # Botones
        footer = ctk.CTkFrame(parent)
        footer.pack(fill="x", pady=(20,0))
        
        save_btn = ctk.CTkButton(footer, text="Guardar", command=self.save)
        save_btn.pack(side="right", padx=6)
        
        del_btn = ctk.CTkButton(footer, text="Eliminar", fg_color="red", command=self.delete)
        del_btn.pack(side="right", padx=6)

        # Espaciador
        ctk.CTkLabel(parent, text="").pack(pady=10)

    def cargar_comboboxes(self):
        # Cargar pacientes
        pacientes = db.fetchall("SELECT paciente_id, nombre FROM pacientes ORDER BY nombre")
        self.pacientes_map = {f"{p[1]}": p[0] for p in pacientes}
        self.paciente_cb['values'] = list(self.pacientes_map.keys())

        # Cargar enfermedades
        enfermedades = db.fetchall("SELECT enfermedad_id, nombre FROM enfermedades ORDER BY nombre")
        self.enfermedades_map = {f"{e[1]}": e[0] for e in enfermedades}
        self.enfermedad_cb['values'] = list(self.enfermedades_map.keys())

    def on_paciente_select(self, event):
        # Cuando se selecciona paciente, cargar sus encuentros
        paciente_nombre = self.paciente_var.get()
        if not paciente_nombre:
            return
        
        paciente_id = self.pacientes_map[paciente_nombre]
        encuentros = db.fetchall("""
            SELECT encuentro_id, fecha, tipo_encuentro 
            FROM encuentros 
            WHERE paciente_id = %s 
            ORDER BY fecha DESC
        """, (paciente_id,))
        
        self.encuentros_map = {f"{e[1]} - {e[2]}": e[0] for e in encuentros}
        self.encuentro_cb['values'] = list(self.encuentros_map.keys())

    def load(self):
        # Cargar datos del diagnóstico existente
        sql = """
        SELECT paciente_id, encuentro_id, enfermedad_id, tipo, probabilidad, notas
        FROM diagnosticos WHERE diagnostico_id = %s
        """
        row = db.fetchone(sql, (self.diagnostico_id,))
        
        if row:
            # Cargar nombres para los comboboxes
            paciente = db.fetchone("SELECT nombre FROM pacientes WHERE paciente_id = %s", (row[0],))
            if paciente: 
                self.paciente_var.set(paciente[0])
            
            if row[1]:  # encuentro_id
                encuentro = db.fetchone("SELECT fecha, tipo_encuentro FROM encuentros WHERE encuentro_id = %s", (row[1],))
                if encuentro:
                    self.encuentro_var.set(f"{encuentro[0]} - {encuentro[1]}")
            
            enfermedad = db.fetchone("SELECT nombre FROM enfermedades WHERE enfermedad_id = %s", (row[2],))
            if enfermedad:
                self.enfermedad_var.set(enfermedad[0])
            
            self.tipo_var.set(row[3] or "")
            self.probabilidad.insert(0, str(row[4] or ""))
            self.notas.insert("1.0", row[5] or "")

    def save(self):
        # Validaciones
        if not self.paciente_var.get() or not self.enfermedad_var.get():
            messagebox.showwarning("Validación", "Paciente y Enfermedad son obligatorios")
            return

        # Obtener IDs
        paciente_id = self.pacientes_map[self.paciente_var.get()]
        enfermedad_id = self.enfermedades_map[self.enfermedad_var.get()]
        
        encuentro_id = None
        if self.encuentro_var.get():
            encuentro_id = self.encuentros_map[self.encuentro_var.get()]

        # Preparar datos
        datos = (
            paciente_id,
            encuentro_id,
            enfermedad_id,
            self.tipo_var.get() or None,
            float(self.probabilidad.get()) if self.probabilidad.get() else None,
            "motor_manual",  # fuente
            None,  # regla_id
            self.notas.get("1.0", "end").strip() or None,
            self.master.controller.current_user["usuario_id"]
        )

        if self.diagnostico_id:
            # Actualizar
            sql = """
            UPDATE diagnosticos SET 
            paciente_id=%s, encuentro_id=%s, enfermedad_id=%s, tipo=%s, 
            probabilidad=%s, fuente=%s, regla_id=%s, notas=%s, created_by=%s
            WHERE diagnostico_id=%s
            """
            db.query(sql, datos + (self.diagnostico_id,))
        else:
            # Insertar nuevo
            sql = """
            INSERT INTO diagnosticos 
            (paciente_id, encuentro_id, enfermedad_id, tipo, probabilidad, fuente, regla_id, notas, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            db.query(sql, datos)

        self.on_save()
        messagebox.showinfo("Éxito", "Diagnóstico guardado correctamente")
        self.destroy()

    def delete(self):
        if not self.diagnostico_id:
            messagebox.showwarning("Info", "No hay diagnóstico a eliminar")
            return
        
        if messagebox.askyesno("Confirmar", "¿Eliminar diagnóstico? Esta acción no se puede deshacer"):
            db.query("DELETE FROM diagnosticos WHERE diagnostico_id=%s", (self.diagnostico_id,))
            self.on_save()
            self.destroy()

# ---------- Frame: Gestión de Usuarios ----------
class UsuariosFrame(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        top = ctk.CTkFrame(self)
        top.pack(fill="x", pady=(8,6))
        back_btn = ctk.CTkButton(top, text="Volver", command=lambda: controller.show_frame("MainMenuFrame"))
        back_btn.pack(side="left", padx=8)

        btn_add = ctk.CTkButton(top, text="Crear Usuario", command=self.open_add_dialog)
        btn_add.pack(side="right", padx=8)

        # Treeview para listar usuarios
        cols = ("usuario_id", "nombre", "correo", "rol", "fecha_creacion")
        container = ctk.CTkFrame(self)
        container.pack(fill="both", expand=True, padx=10, pady=10)

        self.tree = ttk.Treeview(container, columns=cols, show="headings")
        
        # Configurar columnas
        column_widths = {
            "usuario_id": 80,
            "nombre": 200,
            "correo": 200,
            "rol": 120,
            "fecha_creacion": 150
        }
        
        for c in cols:
            self.tree.heading(c, text=c.replace('_', ' ').title())
            self.tree.column(c, width=column_widths.get(c, 120), anchor="w")
        
        self.tree.pack(side="left", fill="both", expand=True)

        vsb = ttk.Scrollbar(container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")

        self.tree.bind("<Double-1>", self.on_edit)

    def on_show(self):
        self.refresh()

    def refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        
        sql = """
        SELECT usuario_id, nombre, correo, rol, created_at
        FROM usuarios 
        ORDER BY nombre
        """
        rows = db.fetchall(sql)
        for r in rows:
            self.tree.insert("", "end", values=r)

    def open_add_dialog(self):
        # Verificar que solo admin puede crear usuarios
        if self.controller.current_user["rol"] != "admin":
            messagebox.showwarning("Permiso denegado", "Solo los administradores pueden gestionar usuarios")
            return
        dlg = UsuarioDialog(self, None, self.refresh)
        dlg.grab_set()

    def on_edit(self, event):
        # Verificar permisos de admin
        if self.controller.current_user["rol"] != "admin":
            messagebox.showwarning("Permiso denegado", "Solo los administradores pueden editar usuarios")
            return
            
        item = self.tree.selection()
        if not item:
            return
        values = self.tree.item(item[0], "values")
        usuario_id = values[0]
        dlg = UsuarioDialog(self, usuario_id, self.refresh)
        dlg.grab_set()

class UsuarioDialog(tk.Toplevel):
    def __init__(self, parent, usuario_id, on_save):
        super().__init__(parent)
        self.usuario_id = usuario_id
        self.on_save = on_save
        self.title("Gestión de Usuario")
        self.geometry("600x500")
        self.resizable(True, True)

        # Frame principal con scroll
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=12, pady=12)

        # Canvas y scrollbar
        self.canvas = tk.Canvas(main_frame, bg='#2b2b2b', highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ctk.CTkFrame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Bind mouse wheel to canvas
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)

        # Contenido del formulario
        self.create_form(self.scrollable_frame)

        if usuario_id:
            self.load()

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def create_form(self, parent):
        # Campos del formulario
        ctk.CTkLabel(parent, text="Nombre Completo *", anchor="w").pack(fill="x", pady=(8,2))
        self.nombre = ctk.CTkEntry(parent)
        self.nombre.pack(fill="x", pady=(0,8))

        ctk.CTkLabel(parent, text="Correo Electrónico *", anchor="w").pack(fill="x", pady=(8,2))
        self.correo = ctk.CTkEntry(parent)
        self.correo.pack(fill="x", pady=(0,8))

        ctk.CTkLabel(parent, text="Rol *", anchor="w").pack(fill="x", pady=(8,2))
        self.rol_var = tk.StringVar()
        rol_cb = ttk.Combobox(parent, textvariable=self.rol_var, 
                            values=["admin", "medico"], state="readonly")
        rol_cb.pack(fill="x", pady=(0,8))

        # Campos de contraseña
        ctk.CTkLabel(parent, text="Contraseña" + ("" if self.usuario_id else " *"), 
                    anchor="w").pack(fill="x", pady=(8,2))
        self.password = ctk.CTkEntry(parent, show="*")
        self.password.pack(fill="x", pady=(0,8))

        ctk.CTkLabel(parent, text="Confirmar Contraseña" + ("" if self.usuario_id else " *"), 
                    anchor="w").pack(fill="x", pady=(8,2))
        self.confirm_password = ctk.CTkEntry(parent, show="*")
        self.confirm_password.pack(fill="x", pady=(0,8))

        # Botones
        footer = ctk.CTkFrame(parent)
        footer.pack(fill="x", pady=(20,0))
        
        save_btn = ctk.CTkButton(footer, text="Guardar", command=self.save)
        save_btn.pack(side="right", padx=6)
        
        del_btn = ctk.CTkButton(footer, text="Eliminar", fg_color="red", command=self.delete)
        del_btn.pack(side="right", padx=6)

        # Espaciador
        ctk.CTkLabel(parent, text="").pack(pady=10)

    def load(self):
        # Cargar datos del usuario existente
        sql = "SELECT nombre, correo, rol FROM usuarios WHERE usuario_id = %s"
        row = db.fetchone(sql, (self.usuario_id,))
        
        if row:
            self.nombre.insert(0, row[0] or "")
            self.correo.insert(0, row[1] or "")
            self.rol_var.set(row[2] or "medico")

    def save(self):
        # Validaciones
        if not self.nombre.get().strip() or not self.correo.get().strip():
            messagebox.showwarning("Validación", "Nombre y Correo son obligatorios")
            return

        if not self.rol_var.get():
            messagebox.showwarning("Validación", "Debe seleccionar un rol")
            return

        # Validar formato de correo simple
        if "@" not in self.correo.get():
            messagebox.showwarning("Validación", "Formato de correo inválido")
            return

        # Validar contraseñas si se están cambiando o creando nuevo
        password = self.password.get().strip()
        confirm_password = self.confirm_password.get().strip()
        
        if self.usuario_id:
            # Edición - contraseña es opcional
            if password and password != confirm_password:
                messagebox.showwarning("Validación", "Las contraseñas no coinciden")
                return
        else:
            # Nuevo usuario - contraseña es obligatoria
            if not password:
                messagebox.showwarning("Validación", "La contraseña es obligatoria para nuevo usuario")
                return
            if password != confirm_password:
                messagebox.showwarning("Validación", "Las contraseñas no coinciden")
                return

        # Verificar si el correo ya existe (excepto para el usuario actual)
        if self.usuario_id:
            existing = db.fetchone(
                "SELECT usuario_id FROM usuarios WHERE correo = %s AND usuario_id != %s", 
                (self.correo.get().strip(), self.usuario_id)
            )
        else:
            existing = db.fetchone(
                "SELECT usuario_id FROM usuarios WHERE correo = %s", 
                (self.correo.get().strip(),)
            )
        
        if existing:
            messagebox.showwarning("Validación", "El correo electrónico ya está registrado")
            return

        # Preparar datos
        datos_base = (
            self.nombre.get().strip(),
            self.correo.get().strip(),
            self.rol_var.get()
        )

        if self.usuario_id:
            if password:
                # Actualizar con nueva contraseña
                hashed_password = hash_password(password)
                sql = """
                UPDATE usuarios SET 
                nombre=%s, correo=%s, rol=%s, hashed_password=%s, updated_at=now()
                WHERE usuario_id=%s
                """
                db.query(sql, datos_base + (hashed_password, self.usuario_id))
            else:
                # Actualizar sin cambiar contraseña
                sql = """
                UPDATE usuarios SET 
                nombre=%s, correo=%s, rol=%s, updated_at=now()
                WHERE usuario_id=%s
                """
                db.query(sql, datos_base + (self.usuario_id,))
        else:
            # Insertar nuevo usuario
            hashed_password = hash_password(password)
            sql = """
            INSERT INTO usuarios 
            (nombre, correo, rol, hashed_password)
            VALUES (%s, %s, %s, %s)
            """
            db.query(sql, datos_base + (hashed_password,))

        self.on_save()
        messagebox.showinfo("Éxito", "Usuario guardado correctamente")
        self.destroy()

    def delete(self):
            if not self.usuario_id:
                messagebox.showwarning("Info", "No hay usuario a eliminar")
                return
            
            # No permitir eliminarse a sí mismo
            current_user_id = self.master.controller.current_user["usuario_id"]
            if self.usuario_id == current_user_id:
                messagebox.showwarning("Error", "No puedes eliminar tu propio usuario")
                return

            # Verificar si el usuario tiene registros asociados
            check_sql = """
            SELECT COUNT(*) FROM (
                SELECT 1 FROM encuentros WHERE created_by = %s
                UNION ALL
                SELECT 1 FROM diagnosticos WHERE created_by = %s
                UNION ALL
                SELECT 1 FROM tratamientos WHERE prescrito_por = %s
            ) as registros
            """
            count = db.fetchone(check_sql, (self.usuario_id, self.usuario_id, self.usuario_id))[0]
            
            if count > 0:
                # Buscar otros médicos disponibles
                medicos = db.fetchall(
                    "SELECT usuario_id, nombre FROM usuarios WHERE rol = 'medico' AND usuario_id != %s ORDER BY nombre",
                    (self.usuario_id,)
                )
                
                if not medicos:
                    if messagebox.askyesno("Crear Médico", 
                        "El usuario tiene registros asociados y no hay otros médicos disponibles para reasignarlos.\n" +
                        "¿Deseas dar de alta un nuevo médico antes de eliminar este usuario?"):
                        # Abrir diálogo para crear nuevo médico
                        dlg = UsuarioDialog(self, None, self.on_save)
                        dlg.rol_var.set("medico")  # Preseleccionar rol médico
                        dlg.grab_set()
                        self.wait_window(dlg)  # Esperar a que se cierre la ventana
                        
                        # Recargar lista de médicos
                        medicos = db.fetchall(
                            "SELECT usuario_id, nombre FROM usuarios WHERE rol = 'medico' AND usuario_id != %s ORDER BY nombre",
                            (self.usuario_id,)
                        )
                    
                if not medicos:
                    messagebox.showwarning("Error", 
                        "No hay médicos disponibles para reasignar los registros.\n" +
                        "Debes crear un nuevo médico antes de eliminar este usuario.")
                    return
                
                # Crear diálogo de selección de médico
                seleccion = tk.Toplevel(self)
                seleccion.title("Reasignar Registros")
                seleccion.geometry("400x250")
                
                frm = ctk.CTkFrame(seleccion)
                frm.pack(fill="both", expand=True, padx=12, pady=12)
                
                mensaje = f"El usuario tiene {count} registros asociados.\n" + \
                        "Selecciona el médico al que se reasignarán todos los registros:"
                ctk.CTkLabel(frm, text=mensaje, wraplength=350).pack(pady=(0,10))
                
                medico_var = tk.StringVar()
                medicos_cb = ttk.Combobox(frm, textvariable=medico_var, state="readonly")
                medicos_cb["values"] = [m[1] for m in medicos]
                medicos_cb.pack(fill="x", pady=10)
                
                def confirmar_reasignacion():
                    if not medico_var.get():
                        messagebox.showwarning("Error", "Debes seleccionar un médico")
                        return
                    
                    # Obtener ID del médico seleccionado
                    medico_destino = None
                    for m in medicos:
                        if m[1] == medico_var.get():
                            medico_destino = m[0]
                            break
                    
                    if medico_destino:
                        if messagebox.askyesno("Confirmar", 
                            "¿Estás seguro de reasignar todos los registros y eliminar al usuario?\n" + 
                            "Esta acción no se puede deshacer."):
                            try:
                                # Reasignar todos los registros
                                db.query(
                                    "UPDATE encuentros SET created_by = %s WHERE created_by = %s",
                                    (medico_destino, self.usuario_id)
                                )
                                db.query(
                                    "UPDATE diagnosticos SET created_by = %s WHERE created_by = %s",
                                    (medico_destino, self.usuario_id)
                                )
                                db.query(
                                    "UPDATE tratamientos SET prescrito_por = %s WHERE prescrito_por = %s",
                                    (medico_destino, self.usuario_id)
                                )
                                
                                # Eliminar usuario
                                db.query("DELETE FROM usuarios WHERE usuario_id = %s", (self.usuario_id,))
                                
                                messagebox.showinfo("Éxito", 
                                    "Los registros han sido reasignados y el usuario ha sido eliminado.")
                                seleccion.destroy()
                                self.on_save()
                                self.destroy()
                            except Exception as e:
                                messagebox.showerror("Error", 
                                    f"Ha ocurrido un error al reasignar los registros: {str(e)}")
                
                btn_confirmar = ctk.CTkButton(frm, text="Confirmar Reasignación", command=confirmar_reasignacion)
                btn_confirmar.pack(pady=10)
                
                btn_cancelar = ctk.CTkButton(frm, text="Cancelar", 
                                        fg_color="gray", 
                                        command=seleccion.destroy)
                btn_cancelar.pack(pady=5)
                
                seleccion.transient(self)  # Hacer la ventana dependiente de la principal
                seleccion.grab_set()  # Hacer la ventana modal
                return
            
            # Si no tiene registros asociados, eliminar directamente
            if messagebox.askyesno("Confirmar", "¿Eliminar usuario? Esta acción no se puede deshacer"):
                try:
                    db.query("DELETE FROM usuarios WHERE usuario_id=%s", (self.usuario_id,))
                    self.on_save()
                    self.destroy()
                except Exception as e:
                    messagebox.showerror("Error", f"No se pudo eliminar el usuario: {str(e)}")


# ---------- Frame: Login ----------
class LoginFrame(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # Main container configuration
        main_container = ctk.CTkFrame(self, corner_radius=0)
        main_container.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.95, relheight=0.9)

        # Grid system setup
        main_container.grid_columnconfigure(0, weight=1)
        main_container.grid_columnconfigure(1, weight=1)
        main_container.grid_rowconfigure(0, weight=1)

        # Left panel setup
        left_panel = ctk.CTkFrame(main_container, corner_radius=0)
        left_panel.grid(row=0, column=0, sticky="nsew")
        left_panel.configure(fg_color="#1a1a1a")

        # Medical symbol and title
        medical_symbol = ctk.CTkLabel(
            left_panel,
            text="🩺",  # Stethoscope emoji
            font=ctk.CTkFont(size=150),
            justify="center"
        )
        medical_symbol.place(relx=0.5, rely=0.3, anchor="center")

        main_title = ctk.CTkLabel(
            left_panel,
            text="Sistema de\nDiagnóstico\nMédico",
            font=ctk.CTkFont(size=42, weight="bold"),
            justify="center"
        )
        main_title.place(relx=0.5, rely=0.6, anchor="center")

        # Subtítulo o descripción
        description = ctk.CTkLabel(
            left_panel,
            text="Gestión integral de diagnósticos\ny seguimiento de pacientes",
            font=ctk.CTkFont(size=20),
            text_color="gray",
            justify="left"
        )
        description.place(relx=0.5, rely=0.80, anchor="center")

        # Panel derecho (Formulario de login)
        right_panel = ctk.CTkFrame(main_container)
        right_panel.grid(row=0, column=1, sticky="nsew", padx=2)

        # Contenedor del formulario para centrarlo
        form_container = ctk.CTkFrame(right_panel, fg_color="transparent")
        form_container.place(relx=0.5, rely=0.5, anchor="center")

        # Título del formulario
        login_title = ctk.CTkLabel(
            form_container,
            text="Iniciar Sesión",
            font=ctk.CTkFont(size=42, weight="bold")
        )
        login_title.pack(pady=(0, 40))

        # Campos de entrada más grandes y estilizados
        self.email = ctk.CTkEntry(
            form_container,
            placeholder_text="Correo electrónico",
            width=400,
            height=60,
            font=ctk.CTkFont(size=16)
        )
        self.email.pack(pady=15)

        self.password = ctk.CTkEntry(
            form_container,
            placeholder_text="Contraseña",
            show="•",
            width=400,
            height=60,
            font=ctk.CTkFont(size=16)
        )
        self.password.pack(pady=15)

        # Botón de inicio de sesión más grande y llamativo
        btn = ctk.CTkButton(
            form_container,
            text="Iniciar Sesión",
            width=400,
            height=60,
            font=ctk.CTkFont(size=18, weight="bold"),
            corner_radius=30,  # Botón más redondeado
            command=self.attempt_login
        )
        btn.pack(pady=(25, 15))

        # Botón de usuario demo más elegante
        create_btn = ctk.CTkButton(
            form_container,
            text="Crear usuario de prueba",
            width=250,
            fg_color="transparent",
            text_color="gray",
            hover=True,
            font=ctk.CTkFont(size=16),
            command=self.create_demo_user
        )
        create_btn.pack(pady=(10, 0))

    def attempt_login(self):
        email = self.email.get().strip()
        password = self.password.get().strip()
        if not email or not password:
            messagebox.showwarning("Validación", "Introduce correo y contraseña")
            return
        row = db.fetchone("SELECT usuario_id, nombre, correo, rol, hashed_password FROM usuarios WHERE correo = %s", (email,))
        if not row:
            messagebox.showerror("Error", "Usuario no encontrado")
            return
        hashed_raw = row[4]
        if not verify_password(password, hashed_raw):
            messagebox.showerror("Error", "Contraseña incorrecta o formato de hash inválido")
            return
        self.controller.login(row)

    def create_demo_user(self):
        # crea un usuario demo con contraseña 'demo123' si no existe
        demo_email = "admin@demo.com"
        existing = db.fetchone("SELECT usuario_id FROM usuarios WHERE correo=%s", (demo_email,))
        if existing:
            messagebox.showinfo("Info", "Usuario demo ya existe")
            return
        hashed = hash_password("demo123")
        db.query("INSERT INTO usuarios (nombre, correo, rol, hashed_password) VALUES (%s,%s,%s,%s)",
                 ("Admin Demo", demo_email, "admin", hashed))
        messagebox.showinfo("Creado", "Usuario demo creado. Correo: admin@demo.com Clave: demo123")

# ---------- Frame: Main Menu ----------
class MainMenuFrame(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        top = ctk.CTkFrame(self)
        top.pack(fill="x")
        self.lbl_user = ctk.CTkLabel(top, text="Usuario: -", anchor="w")
        self.lbl_user.pack(side="left", padx=12, pady=12)

        logout_btn = ctk.CTkButton(top, text="Cerrar sesión", command=self.logout)
        logout_btn.pack(side="right", padx=12, pady=12)

        # Frame de navegación (sin botones específicos aquí)
        self.nav = ctk.CTkFrame(self)
        self.nav.pack(fill="x", padx=12, pady=(6,12))

        # Panel principal
        self.main_area = ctk.CTkFrame(self)
        self.main_area.pack(fill="both", expand=True, padx=12, pady=6)

        welcome = ctk.CTkLabel(self.main_area, text="Bienvenido al sistema. Selecciona una opción arriba.", anchor="center")
        welcome.pack(expand=True)

    def on_show(self):
        user = self.controller.current_user
        if user:
            self.lbl_user.configure(text=f"Usuario: {user['nombre']} - Rol: {user['rol']}")
            
            # Limpiar botones anteriores
            for widget in self.nav.winfo_children():
                widget.destroy()
            
            # Crear botones según el rol
            btn_pacientes = ctk.CTkButton(self.nav, text="Pacientes", command=lambda: self.controller.show_frame("PacientesFrame"))
            btn_pacientes.grid(row=0, column=0, padx=8, pady=8)
            
            btn_catalogos = ctk.CTkButton(self.nav, text="Catálogos", command=lambda: self.controller.show_frame("CatalogosFrame"))
            btn_catalogos.grid(row=0, column=1, padx=8, pady=8)
            
            btn_encuentros = ctk.CTkButton(self.nav, text="Encuentros", command=lambda: self.controller.show_frame("EncuentrosFrame"))
            btn_encuentros.grid(row=0, column=2, padx=8, pady=8)
            
            btn_diagnosticos = ctk.CTkButton(self.nav, text="Diagnósticos", command=lambda: self.controller.show_frame("DiagnosticosFrame"))
            btn_diagnosticos.grid(row=0, column=3, padx=8, pady=8)
            
            btn_tratamientos = ctk.CTkButton(self.nav, text="Tratamientos", command=lambda: self.controller.show_frame("TratamientosFrame"))
            btn_tratamientos.grid(row=0, column=4, padx=8, pady=8)
            
            # Solo mostrar botón de Usuarios si es admin
            if user["rol"] == "admin":
                btn_usuarios = ctk.CTkButton(self.nav, text="Usuarios", command=lambda: self.controller.show_frame("UsuariosFrame"))
                btn_usuarios.grid(row=0, column=5, padx=8, pady=8)

    def logout(self):
        self.controller.current_user = None
        self.controller.show_frame("LoginFrame")

# ---------- Frame: Pacientes CRUD ----------
class PacientesFrame(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        
        # Configurar el estilo de las tablas
        style = ttk.Style()
        style.configure(
            "Treeview",
            font=('Helvetica', 12),
            rowheight=35
        )
        style.configure(
            "Treeview.Heading",
            font=('Helvetica', 13, 'bold')
        )

        top = ctk.CTkFrame(self)
        top.pack(fill="x", pady=(8,6))
        back_btn = ctk.CTkButton(top, text="Volver", command=lambda: controller.show_frame("MainMenuFrame"))
        back_btn.pack(side="left", padx=8)

        btn_add = ctk.CTkButton(top, text="Agregar paciente", command=self.open_add_dialog)
        btn_add.pack(side="right", padx=8)

        cols = ("paciente_id", "numero_identificacion", "nombre", "fecha_nacimiento", "sexo", "telefono")
        container = ctk.CTkFrame(self)
        container.pack(fill="both", expand=True, padx=10, pady=10)

        self.tree = ttk.Treeview(container, columns=cols, show="headings")
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=140, anchor="w")
        self.tree.pack(side="left", fill="both", expand=True)

        vsb = ttk.Scrollbar(container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")

        # doble click para editar mi loco
        self.tree.bind("<Double-1>", self.on_edit)

    def on_show(self):
        self.refresh()

    def refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        rows = db.fetchall("SELECT paciente_id, numero_identificacion, nombre, fecha_nacimiento, sexo, telefono FROM pacientes ORDER BY nombre")
        for r in rows:
            self.tree.insert("", "end", values=r)

    def open_add_dialog(self):
        dlg = PacienteDialog(self, None, self.refresh)
        dlg.grab_set()

    def on_edit(self, event):
        item = self.tree.selection()
        if not item:
            return
        values = self.tree.item(item[0], "values")
        paciente_id = values[0]
        dlg = PacienteDialog(self, paciente_id, self.refresh)
        dlg.grab_set()

class PacienteDialog(tk.Toplevel):
    def __init__(self, parent, paciente_id, on_save):
        super().__init__(parent)
        self.paciente_id = paciente_id
        self.on_save = on_save
        self.title("Paciente")
        self.geometry("500x450")
        self.resizable(False, False)

        frm = ctk.CTkFrame(self)
        frm.pack(fill="both", expand=True, padx=12, pady=12)

        self.entries = {}
        fields = [
            ("numero_identificacion","Número identificación"),
            ("nombre","Nombre"),
            ("fecha_nacimiento","Fecha nacimiento (YYYY-MM-DD)"),
            ("sexo","Sexo (M/F/O)"),
            ("direccion","Dirección"),
            ("telefono","Teléfono")
        ]
        for key,label in fields:
            lbl = ctk.CTkLabel(frm, text=label, anchor="w")
            lbl.pack(fill="x", pady=(8,2))
            ent = ctk.CTkEntry(frm)
            ent.pack(fill="x")
            self.entries[key] = ent

        footer = ctk.CTkFrame(frm)
        footer.pack(fill="x", pady=(12,0))
        save_btn = ctk.CTkButton(footer, text="Guardar", command=self.save)
        save_btn.pack(side="right", padx=6)
        del_btn = ctk.CTkButton(footer, text="Eliminar", fg_color="red", command=self.delete)
        del_btn.pack(side="left", padx=6)

        if paciente_id:
            self.load()

    def load(self):
        r = db.fetchone("SELECT numero_identificacion, nombre, fecha_nacimiento, sexo, direccion, telefono FROM pacientes WHERE paciente_id=%s", (self.paciente_id,))
        if r:
            keys = ["numero_identificacion","nombre","fecha_nacimiento","sexo","direccion","telefono"]
            for k,v in zip(keys, r):
                if v is None:
                    v = ""
                self.entries[k].insert(0, str(v))

    def save(self):
        data = {k: self.entries[k].get().strip() for k in self.entries}
        if not data["nombre"]:
            messagebox.showwarning("Validación", "El nombre es obligatorio")
            return
        if self.paciente_id:
            db.query(
                "UPDATE pacientes SET numero_identificacion=%s, nombre=%s, fecha_nacimiento=%s, sexo=%s, direccion=%s, telefono=%s, updated_at=now() WHERE paciente_id=%s",
                (data["numero_identificacion"] or None, data["nombre"], data["fecha_nacimiento"] or None, data["sexo"] or None, data["direccion"] or None, data["telefono"] or None, self.paciente_id)
            )
        else:
            db.query(
                "INSERT INTO pacientes (numero_identificacion, nombre, fecha_nacimiento, sexo, direccion, telefono) VALUES (%s,%s,%s,%s,%s,%s)",
                (data["numero_identificacion"] or None, data["nombre"], data["fecha_nacimiento"] or None, data["sexo"] or None, data["direccion"] or None, data["telefono"] or None)
            )
        self.on_save()
        self.destroy()

    def delete(self):
        if not self.paciente_id:
            messagebox.showwarning("Info", "No hay paciente a eliminar")
            return
        if messagebox.askyesno("Confirmar", "Eliminar paciente? Esto es irreversible"):
            db.query("DELETE FROM pacientes WHERE paciente_id=%s", (self.paciente_id,))
            self.on_save()
            self.destroy()


    
# ---------- Frame: Catálogos (CRUD completo) ----------
class CatalogosFrame(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        top = ctk.CTkFrame(self)
        top.pack(fill="x", pady=(8,6))
        back_btn = ctk.CTkButton(top, text="Volver", command=lambda: controller.show_frame("MainMenuFrame"))
        back_btn.pack(side="left", padx=8)

        # pestañas para distintos catálogos
        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True, padx=12, pady=12)

        self.views = {}
        self.tab_frames = {}
        
        # Configuración de cada catálogo
        catalogo_config = [
            ("Enfermedades", "enfermedades", ["enfermedad_id", "codigo_icd", "nombre", "gravedad"]),
            ("Signos", "signos_catalogo", ["signo_id", "nombre"]),
            ("Síntomas", "sintomas_catalogo", ["sintoma_id", "nombre"]),
            ("Pruebas Lab", "pruebas_lab_catalogo", ["prueba_lab_id", "codigo", "nombre"]),
            ("Pruebas Post", "pruebas_post_catalogo", ["prueba_post_id", "nombre"])
        ]
        
        for title, table, cols in catalogo_config:
            # Frame principal para cada pestaña
            tab_frame = ctk.CTkFrame(self.tabs)
            self.tabs.add(tab_frame, text=title)
            self.tab_frames[table] = tab_frame
            
            # Barra de botones
            btn_frame = ctk.CTkFrame(tab_frame)
            btn_frame.pack(fill="x", pady=(0,8))
            
            btn_add = ctk.CTkButton(btn_frame, text=f"Agregar {title[:-1]}", 
                                   command=lambda t=table: self.open_add_dialog(t))
            btn_add.pack(side="right", padx=4)
            
            btn_refresh = ctk.CTkButton(btn_frame, text="Actualizar", 
                                      command=lambda t=table: self.refresh_tab(t))
            btn_refresh.pack(side="right", padx=4)

            # Treeview
            container = ctk.CTkFrame(tab_frame)
            container.pack(fill="both", expand=True)
            
            tree = ttk.Treeview(container, columns=cols, show="headings")
            for c in cols:
                tree.heading(c, text=c.replace('_', ' ').title())
                tree.column(c, width=160, anchor="w")
            tree.pack(fill="both", expand=True, side="left")
            
            vsb = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=vsb.set)
            vsb.pack(side="right", fill="y")
            
            # Bind doble click para editar
            tree.bind("<Double-1>", lambda e, t=table: self.on_edit(e, t))
            
            self.views[table] = tree
    
    def on_show(self):
        self.refresh_all_tabs()

    def refresh_all_tabs(self):
        for table in self.views:
            self.refresh_tab(table)
    
    def refresh_tab(self, table):
        tree = self.views[table]
        for i in tree.get_children():
            tree.delete(i)
            
        # Consultas específicas para cada tabla
        queries = {
            "enfermedades": "SELECT enfermedad_id, codigo_icd, nombre, gravedad FROM enfermedades ORDER BY nombre",
            "signos_catalogo": "SELECT signo_id, nombre FROM signos_catalogo ORDER BY nombre",
            "sintomas_catalogo": "SELECT sintoma_id, nombre FROM sintomas_catalogo ORDER BY nombre",
            "pruebas_lab_catalogo": "SELECT prueba_lab_id, codigo, nombre FROM pruebas_lab_catalogo ORDER BY nombre",
            "pruebas_post_catalogo": "SELECT prueba_post_id, nombre FROM pruebas_post_catalogo ORDER BY nombre"
        }
        
        sql = queries.get(table)
        if sql:
            rows = db.fetchall(sql)
            for r in rows:
                tree.insert("", "end", values=r)

    def open_add_dialog(self, table):
        dlg = CatalogoDialog(self, table, None, self.refresh_tab)
        dlg.grab_set()

    def on_edit(self, event, table):
        tree = self.views[table]
        item = tree.selection()
        if not item:
            return
        values = tree.item(item[0], "values")
        item_id = values[0]
        dlg = CatalogoDialog(self, table, item_id, self.refresh_tab)
        dlg.grab_set()

# ---------- Diálogo genérico para catálogos ----------
class CatalogoDialog(tk.Toplevel):
    def __init__(self, parent, table, item_id, on_save):
        super().__init__(parent)
        self.table = table
        self.item_id = item_id
        self.on_save = on_save
        self.title(f"{self.get_table_title()} - {'Editar' if item_id else 'Nuevo'}")
        self.geometry("500x400")
        self.resizable(True, True)

        # Frame principal con scroll
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=12, pady=12)

        # Campos específicos para cada tabla
        self.create_form(main_frame)

        if item_id:
            self.load()

    def get_table_title(self):
        titles = {
            "enfermedades": "Enfermedad",
            "signos_catalogo": "Signo",
            "sintomas_catalogo": "Síntoma",
            "pruebas_lab_catalogo": "Prueba de Laboratorio",
            "pruebas_post_catalogo": "Prueba Post-Mortem"
        }
        return titles.get(self.table, "Elemento")

    def create_form(self, parent):
        self.entries = {}
        
        # Campos comunes para todas las tablas
        if self.table == "enfermedades":
            fields = [
                ("codigo_icd", "Código ICD-10"),
                ("nombre", "Nombre de la Enfermedad *"),
                ("gravedad", "Gravedad (1-10)")
            ]
        elif self.table == "pruebas_lab_catalogo":
            fields = [
                ("codigo", "Código"),
                ("nombre", "Nombre de la Prueba *")
            ]
        else:  # signos_catalogo, sintomas_catalogo, pruebas_post_catalogo
            fields = [
                ("nombre", "Nombre *")
            ]

        for key, label in fields:
            lbl = ctk.CTkLabel(parent, text=label, anchor="w")
            lbl.pack(fill="x", pady=(8,2))
            
            # Campo de texto normal para todos los campos
            ent = ctk.CTkEntry(parent)
            ent.pack(fill="x", pady=(0,8))
            self.entries[key] = ent

        # Botones
        footer = ctk.CTkFrame(parent)
        footer.pack(fill="x", pady=(20,0))
        
        save_btn = ctk.CTkButton(footer, text="Guardar", command=self.save)
        save_btn.pack(side="right", padx=6)
        
        if self.item_id:
            del_btn = ctk.CTkButton(footer, text="Eliminar", fg_color="red", command=self.delete)
            del_btn.pack(side="right", padx=6)

        # Espaciador
        ctk.CTkLabel(parent, text="").pack(pady=10)

    def load(self):
        # Consulta específica para cada tabla
        id_column = self.get_id_column()
        sql = f"SELECT * FROM {self.table} WHERE {id_column} = %s"
        row = db.fetchone(sql, (self.item_id,))
        
        if row:
            # Mapear campos según la tabla
            if self.table == "enfermedades":
                self.entries["codigo_icd"].insert(0, row[1] or "")
                self.entries["nombre"].insert(0, row[2] or "")
                if len(row) > 3 and row[3] is not None:  # gravedad
                    self.entries["gravedad"].insert(0, str(row[3]))
            elif self.table == "pruebas_lab_catalogo":
                self.entries["codigo"].insert(0, row[1] or "")
                self.entries["nombre"].insert(0, row[2] or "")
            else:
                self.entries["nombre"].insert(0, row[1] or "")

    def get_id_column(self):
        # Obtener el nombre de la columna ID para cada tabla
        id_columns = {
            "enfermedades": "enfermedad_id",
            "signos_catalogo": "signo_id",
            "sintomas_catalogo": "sintoma_id",
            "pruebas_lab_catalogo": "prueba_lab_id",
            "pruebas_post_catalogo": "prueba_post_id"
        }
        return id_columns.get(self.table, f"{self.table[:-1]}_id")

    def save(self):
        # Validaciones
        if not self.entries["nombre"].get().strip():
            messagebox.showwarning("Validación", "El nombre es obligatorio")
            return

        # Preparar datos según la tabla
        if self.table == "enfermedades":
            # Validar que gravedad sea numérico si se proporciona
            gravedad_str = self.entries["gravedad"].get().strip()
            gravedad = None
            if gravedad_str:
                try:
                    gravedad = int(gravedad_str)
                    if not (1 <= gravedad <= 10):
                        messagebox.showwarning("Validación", "La gravedad debe ser un número entre 1 y 10")
                        return
                except ValueError:
                    messagebox.showwarning("Validación", "La gravedad debe ser un número entero")
                    return
            
            data = (
                self.entries["codigo_icd"].get().strip() or None,
                self.entries["nombre"].get().strip(),
                gravedad
            )
            if self.item_id:
                sql = "UPDATE enfermedades SET codigo_icd=%s, nombre=%s, gravedad=%s WHERE enfermedad_id=%s"
                db.query(sql, data + (self.item_id,))
            else:
                sql = "INSERT INTO enfermedades (codigo_icd, nombre, gravedad) VALUES (%s, %s, %s)"
                db.query(sql, data)
                
        elif self.table == "pruebas_lab_catalogo":
            data = (
                self.entries["codigo"].get().strip() or None,
                self.entries["nombre"].get().strip()
            )
            if self.item_id:
                sql = "UPDATE pruebas_lab_catalogo SET codigo=%s, nombre=%s WHERE prueba_lab_id=%s"
                db.query(sql, data + (self.item_id,))
            else:
                sql = "INSERT INTO pruebas_lab_catalogo (codigo, nombre) VALUES (%s, %s)"
                db.query(sql, data)
                
        else:  # signos_catalogo, sintomas_catalogo, pruebas_post_catalogo
            data = (self.entries["nombre"].get().strip(),)
            if self.item_id:
                sql = f"UPDATE {self.table} SET nombre=%s WHERE {self.get_id_column()}=%s"
                db.query(sql, data + (self.item_id,))
            else:
                sql = f"INSERT INTO {self.table} (nombre) VALUES (%s)"
                db.query(sql, data)

        self.on_save(self.table)
        messagebox.showinfo("Éxito", f"{self.get_table_title()} guardado correctamente")
        self.destroy()

    def delete(self):
        if not self.item_id:
            messagebox.showwarning("Info", "No hay elemento a eliminar")
            return
        
        if messagebox.askyesno("Confirmar", f"¿Eliminar {self.get_table_title().lower()}? Esta acción no se puede deshacer"):
            id_column = self.get_id_column()
            sql = f"DELETE FROM {self.table} WHERE {id_column}=%s"
            db.query(sql, (self.item_id,))
            self.on_save(self.table)
            self.destroy()

# ---------- Frame: Encuentros, Diagnósticos y Tratamientos (esqueleto) ----------
class EncuentrosFrame(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        top = ctk.CTkFrame(self)
        top.pack(fill="x", pady=(8,6))
        back_btn = ctk.CTkButton(top, text="Volver", command=lambda: controller.show_frame("MainMenuFrame"))
        back_btn.pack(side="left", padx=8)

        search_frame = ctk.CTkFrame(self)
        search_frame.pack(fill="x", padx=12, pady=6)
        self.paciente_search = ctk.CTkEntry(search_frame, placeholder_text="Buscar paciente por nombre o ID")
        self.paciente_search.pack(side="left", fill="x", expand=True, padx=(0,6))
        btn_search = ctk.CTkButton(search_frame, text="Buscar", command=self.search_pacientes)
        btn_search.pack(side="left")

        # Lista resultados pacientes
        self.pac_tree = ttk.Treeview(self, columns=("paciente_id","nombre","fecha_nacimiento"), show="headings", height=6)
        for c in ("paciente_id","nombre","fecha_nacimiento"):
            self.pac_tree.heading(c, text=c)
            self.pac_tree.column(c, width=200)
        self.pac_tree.pack(fill="x", padx=12, pady=6)
        self.pac_tree.bind("<<TreeviewSelect>>", self.on_paciente_select)

        # Panel detalle encuentros
        self.enc_tree = ttk.Treeview(self, columns=("encuentro_id","fecha","tipo_encuentro","motivo"), show="headings", height=8)
        for c in ("encuentro_id","fecha","tipo_encuentro","motivo"):
            self.enc_tree.heading(c, text=c)
            self.enc_tree.column(c, width=220)
        self.enc_tree.pack(fill="both", expand=True, padx=12, pady=6)

        btn_frame = ctk.CTkFrame(self)
        btn_frame.pack(fill="x", padx=12, pady=6)
        ctk.CTkButton(btn_frame, text="Nuevo Encuentro", command=self.create_encuentro).pack(side="left", padx=6)
        ctk.CTkButton(btn_frame, text="Registrar Observación (Signo)", command=self.add_observacion_signo).pack(side="left", padx=6)
        ctk.CTkButton(btn_frame, text="Registrar Observación (Síntoma)", command=self.add_observacion_sintoma).pack(side="left", padx=6)

    def on_show(self):
        # limpiar
        for i in self.pac_tree.get_children():
            self.pac_tree.delete(i)
        for i in self.enc_tree.get_children():
            self.enc_tree.delete(i)

    def search_pacientes(self):
        q = self.paciente_search.get().strip()
        if not q:
            messagebox.showwarning("Validación", "Escribe nombre o id para buscar")
            return
        try:
            pid = int(q)
            rows = db.fetchall("SELECT paciente_id, nombre, fecha_nacimiento FROM pacientes WHERE paciente_id=%s", (pid,))
        except ValueError:
            rows = db.fetchall("SELECT paciente_id, nombre, fecha_nacimiento FROM pacientes WHERE nombre ILIKE %s ORDER BY nombre", (f"%{q}%",))
        for i in self.pac_tree.get_children():
            self.pac_tree.delete(i)
        for r in rows:
            self.pac_tree.insert("", "end", values=r)

    def on_paciente_select(self, event):
        sel = self.pac_tree.selection()
        if not sel:
            return
        paciente_id = self.pac_tree.item(sel[0], "values")[0]
        # cargar encuentros del paciente
        for i in self.enc_tree.get_children():
            self.enc_tree.delete(i)
        rows = db.fetchall("SELECT encuentro_id, fecha, tipo_encuentro, motivo FROM encuentros WHERE paciente_id=%s ORDER BY fecha DESC", (paciente_id,))
        for r in rows:
            self.enc_tree.insert("", "end", values=r)

    def create_encuentro(self):
        sel = self.pac_tree.selection()
        if not sel:
            messagebox.showwarning("Seleccionar", "Selecciona un paciente primero")
            return
        paciente_id = self.pac_tree.item(sel[0], "values")[0]
        dlg = EncuentroDialog(self, paciente_id, self.on_paciente_select_callback)
        dlg.grab_set()

    def on_paciente_select_callback(self):
        # refrescar lista de encuentros
        ev = tk.Event()
        ev.widget = self.pac_tree
        self.on_paciente_select(ev)

    def add_observacion_signo(self):
        sel_enc = self.enc_tree.selection()
        if not sel_enc:
            messagebox.showwarning("Seleccionar", "Selecciona un encuentro")
            return
        encuentro_id = self.enc_tree.item(sel_enc[0], "values")[0]
        dlg = ObservacionSignoDialog(self, encuentro_id, self.on_paciente_select_callback)
        dlg.grab_set()

    def add_observacion_sintoma(self):
        sel_enc = self.enc_tree.selection()
        if not sel_enc:
            messagebox.showwarning("Seleccionar", "Selecciona un encuentro")
            return
        encuentro_id = self.enc_tree.item(sel_enc[0], "values")[0]
        dlg = ObservacionSintomaDialog(self, encuentro_id, self.on_paciente_select_callback)
        dlg.grab_set()

class EncuentroDialog(tk.Toplevel):
    def __init__(self, parent, paciente_id, on_save):
        super().__init__(parent)
        self.paciente_id = paciente_id
        self.on_save = on_save
        self.title("Nuevo Encuentro")
        self.geometry("480x380")

        frm = ctk.CTkFrame(self)
        frm.pack(fill="both", expand=True, padx=12, pady=12)

        self.tipo = ctk.CTkEntry(frm, placeholder_text="Tipo de encuentro (consulta/urgencia/alta)")
        self.tipo.pack(fill="x", pady=6)
        self.motivo = ctk.CTkTextbox(frm, height=120)
        self.motivo.pack(fill="both", pady=6, expand=True)

        btn = ctk.CTkButton(frm, text="Crear", command=self.create)
        btn.pack(pady=8)

    def create(self):
        tipo = self.tipo.get().strip()
        motivo = self.motivo.get("1.0", "end").strip()
        if not tipo:
            messagebox.showwarning("Validación", "Tipo requerido")
            return
        # created_by del usuario actual
        created_by = self.master.controller.current_user["usuario_id"]
        db.query(
            "INSERT INTO encuentros (paciente_id, tipo_encuentro, motivo, created_by) VALUES (%s,%s,%s,%s)",
            (self.paciente_id, tipo, motivo or None, created_by)
        )
        self.on_save()
        self.destroy()

class ObservacionSignoDialog(tk.Toplevel):
    def __init__(self, parent, encuentro_id, on_save):
        super().__init__(parent)
        self.encuentro_id = encuentro_id
        self.on_save = on_save
        self.title("Registrar Observación - Signo")
        self.geometry("480x380")

        frm = ctk.CTkFrame(self)
        frm.pack(fill="both", expand=True, padx=12, pady=12)

        # cargar signos
        signos = db.fetchall("SELECT signo_id, nombre FROM signos_catalogo ORDER BY nombre")
        self.signos_map = {f"{s[1]}": s[0] for s in signos}

        ctk.CTkLabel(frm, text="Signo").pack(anchor="w")
        self.signo_cb = ttk.Combobox(frm, values=list(self.signos_map.keys()))
        self.signo_cb.pack(fill="x", pady=6)

        ctk.CTkLabel(frm, text="Valor (texto)").pack(anchor="w")
        self.valor_texto = ctk.CTkEntry(frm)
        self.valor_texto.pack(fill="x", pady=6)

        ctk.CTkLabel(frm, text="Valor (numérico)").pack(anchor="w")
        self.valor_num = ctk.CTkEntry(frm)
        self.valor_num.pack(fill="x", pady=6)

        ctk.CTkLabel(frm, text="Unidad").pack(anchor="w")
        self.unidad = ctk.CTkEntry(frm)
        self.unidad.pack(fill="x", pady=6)

        btn = ctk.CTkButton(frm, text="Guardar", command=self.save)
        btn.pack(pady=8)

    def save(self):
        sel = self.signo_cb.get()
        if not sel:
            messagebox.showwarning("Validación", "Selecciona un signo")
            return
        signo_id = self.signos_map[sel]
        valor_texto = self.valor_texto.get().strip() or None
        valor_num = self.valor_num.get().strip() or None
        if valor_num:
            try:
                valor_num = float(valor_num)
            except ValueError:
                messagebox.showwarning("Validación", "Valor numérico inválido")
                return
        unidad = self.unidad.get().strip() or None
        recorded_by = self.master.controller.current_user["usuario_id"]
        db.query(
            "INSERT INTO observacion_signos (encuentro_id, signo_id, valor_texto, valor_numerico, unidad, recorded_by) VALUES (%s,%s,%s,%s,%s,%s)",
            (self.encuentro_id, signo_id, valor_texto, valor_num, unidad, recorded_by)
        )
        self.on_save()
        self.destroy()

class ObservacionSintomaDialog(tk.Toplevel):
    def __init__(self, parent, encuentro_id, on_save):
        super().__init__(parent)
        self.encuentro_id = encuentro_id
        self.on_save = on_save
        self.title("Registrar Observación - Síntoma")
        self.geometry("480x420")

        frm = ctk.CTkFrame(self)
        frm.pack(fill="both", expand=True, padx=12, pady=12)

        sintomas = db.fetchall("SELECT sintoma_id, nombre FROM sintomas_catalogo ORDER BY nombre")
        self.sintomas_map = {f"{s[1]}": s[0] for s in sintomas}

        ctk.CTkLabel(frm, text="Síntoma").pack(anchor="w")
        self.sintoma_cb = ttk.Combobox(frm, values=list(self.sintomas_map.keys()))
        self.sintoma_cb.pack(fill="x", pady=6)

        ctk.CTkLabel(frm, text="Severidad (1-5)").pack(anchor="w")
        self.severidad = ctk.CTkEntry(frm)
        self.severidad.pack(fill="x", pady=6)

        ctk.CTkLabel(frm, text="Fecha inicio (YYYY-MM-DD)").pack(anchor="w")
        self.inicio = ctk.CTkEntry(frm)
        self.inicio.pack(fill="x", pady=6)

        ctk.CTkLabel(frm, text="Notas").pack(anchor="w")
        self.notas = ctk.CTkTextbox(frm, height=120)
        self.notas.pack(fill="both", pady=6, expand=True)

        btn = ctk.CTkButton(frm, text="Guardar", command=self.save)
        btn.pack(pady=8)

    def save(self):
        sel = self.sintoma_cb.get()
        if not sel:
            messagebox.showwarning("Validación", "Selecciona un síntoma")
            return
        sintoma_id = self.sintomas_map[sel]
        try:
            sev = int(self.severidad.get().strip()) if self.severidad.get().strip() else None
        except ValueError:
            messagebox.showwarning("Validación", "Severidad inválida")
            return
        inicio_fecha = self.inicio.get().strip() or None
        notas = self.notas.get("1.0", "end").strip() or None
        recorded_by = self.master.controller.current_user["usuario_id"]
        db.query(
            "INSERT INTO observacion_sintomas (encuentro_id, sintoma_id, severidad, inicio_fecha, notas, recorded_by) VALUES (%s,%s,%s,%s,%s,%s)",
            (self.encuentro_id, sintoma_id, sev, inicio_fecha, notas, recorded_by)
        )
        self.on_save()
        self.destroy()

# ---------- Inicio de la app ----------
if __name__ == "__main__":
    app = App()
    app.mainloop()
