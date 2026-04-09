from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import StreamingResponse

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

from datetime import datetime
import pandas as pd
import io
import os

from database import init_db, get_connection

app = FastAPI()
init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://ajanlat-frontend-bimqyjq9m-fearthesanset.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

COMPANY_NAME = "Sajat Ceg Kft."

NEXT_ITEM_ID = 1
NEXT_PROJECT_ID = 1
NEXT_PROJECT_ITEM_ID = 1
NEXT_TEMPLATE_ID = 1
NEXT_TEMPLATE_ITEM_ID = 1



# "adatbázis" (MVP)
ITEMS_DB = []
PROJECT_ITEMS_DB = []
TEMPLATES_DB = []
TEMPLATE_ITEMS_DB = []
TEMPLATE_ITEMS_DB = []

# ----- MODEL -----
class Item(BaseModel):
    name: str
    type: str
    unit: str
    price: float
    description: str

# ----- ROOT TESZT -----
@app.get("/")
def root():
    return {"message": "API működik"}

# ----- CREATE ITEM -----
@app.post("/items")
def create_item(item: Item):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO items (name, type, unit, price, description)
        VALUES (?, ?, ?, ?, ?)
    """, (item.name, item.type, item.unit, item.price, item.description))

    conn.commit()
    item_id = cursor.lastrowid
    conn.close()

    return {
        "id": item_id,
        "name": item.name,
        "type": item.type,
        "unit": item.unit,
        "price": item.price,
        "description": item.description
    }

@app.get("/items")
def get_items():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM items")
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]

@app.delete("/items/{item_id}")
def delete_item(item_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM items WHERE id = ?", (item_id,))
    conn.commit()

    if cursor.rowcount == 0:
        conn.close()
        return {"error": "Item not found"}

    conn.close()
    return {"message": "Item deleted"}


@app.post("/projects")
def create_project(name: str):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO projects (name) VALUES (?)",
        (name,)
    )

    conn.commit()
    project_id = cursor.lastrowid
    conn.close()

    return {
        "id": project_id,
        "name": name
    }

@app.post("/projects")
def create_project(name: str):
    global NEXT_PROJECT_ID

    project = {
        "id": NEXT_PROJECT_ID,
        "name": name
    }
    NEXT_PROJECT_ID += 1

    PROJECTS_DB.append(project)
    return project

@app.post("/projects/{project_id}/add-item/{item_id}")
def add_item_to_project(project_id: int, item_id: int, quantity: float):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    project = cursor.fetchone()
    if not project:
        conn.close()
        return {"error": "Project not found"}

    cursor.execute("SELECT * FROM items WHERE id = ?", (item_id,))
    item = cursor.fetchone()
    if not item:
        conn.close()
        return {"error": "Item not found"}

    cursor.execute("""
        INSERT INTO project_items (project_id, item_id, quantity)
        VALUES (?, ?, ?)
    """, (project_id, item_id, quantity))

    conn.commit()
    project_item_id = cursor.lastrowid
    conn.close()

    return {
        "id": project_item_id,
        "project_id": project_id,
        "item_id": item_id,
        "quantity": quantity
    }
@app.get("/projects/{project_id}/items")
def get_project_items(project_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            project_items.id AS project_item_id,
            items.id AS item_id,
            items.name,
            items.type,
            items.unit,
            items.price,
            items.description,
            project_items.quantity
        FROM project_items
        JOIN items ON project_items.item_id = items.id
        WHERE project_items.project_id = ?
    """, (project_id,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]

@app.get("/projects/{project_id}/total")
def get_project_total(project_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT SUM(project_items.quantity * items.price) AS total
        FROM project_items
        JOIN items ON project_items.item_id = items.id
        WHERE project_items.project_id = ?
    """, (project_id,))

    row = cursor.fetchone()
    conn.close()

    total = row["total"] if row["total"] is not None else 0

    return {
        "project_id": project_id,
        "total": total
    }

@app.delete("/projects/{project_id}/items/{project_item_id}")
def delete_project_item(project_id: int, project_item_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM project_items
        WHERE id = ? AND project_id = ?
    """, (project_item_id, project_id))

    conn.commit()

    if cursor.rowcount == 0:
        conn.close()
        return {"error": "Project item not found"}

    conn.close()
    return {"message": "Project item deleted"}

@app.get("/projects/{project_id}/generate-text")
def generate_project_text(project_id: int):
    descriptions = []

    for project_item in PROJECT_ITEMS_DB:
        if project_item["project_id"] == project_id:
            item = next((i for i in ITEMS_DB if i["id"] == project_item["item_id"]), None)

            if item and item["description"]:
                descriptions.append(item["description"])

    if not descriptions:
        return {"text": "Az ajánlat nem tartalmaz tételeket."}

    # Összefűzés
    if len(descriptions) == 1:
        text = f"Az ajánlat tartalmazza a {descriptions[0]}."
    else:
        text = "Az ajánlat tartalmazza a " + ", valamint a ".join(descriptions) + "."

    return {"text": text}


@app.put("/projects/{project_id}/items/{project_item_id}")
def update_project_item_quantity(project_id: int, project_item_id: int, quantity: float):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE project_items
        SET quantity = ?
        WHERE id = ? AND project_id = ?
    """, (quantity, project_item_id, project_id))

    conn.commit()

    if cursor.rowcount == 0:
        conn.close()
        return {"error": "Project item not found"}

    cursor.execute("""
        SELECT * FROM project_items
        WHERE id = ? AND project_id = ?
    """, (project_item_id, project_id))

    updated = cursor.fetchone()
    conn.close()

    return {
        "message": "Quantity updated",
        "updated": dict(updated)
    }

@app.get("/projects/{project_id}/export-pdf")
def export_project_pdf(project_id: int):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer)
    styles = getSampleStyleSheet()

    elements = []

    # dátum
    today = datetime.now().strftime("%Y-%m-%d")

    conn = get_connection()
    cursor = conn.cursor()

    # Projekt keresése
    cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    project = cursor.fetchone()
    if not project:
        conn.close()
        return {"error": "Project not found"}

    # Projekt tételek lekérése
    cursor.execute("""
        SELECT
            project_items.id AS project_item_id,
            items.id AS item_id,
            items.name,
            items.type,
            items.unit,
            items.price,
            items.description,
            project_items.quantity
        FROM project_items
        JOIN items ON project_items.item_id = items.id
        WHERE project_items.project_id = ?
    """, (project_id,))
    project_items = cursor.fetchall()

    if not project_items:
        conn.close()
        return {"error": "Project has no items"}

    # settings / cégnév lekérése
    cursor.execute("SELECT company_name FROM settings WHERE id = 1")
    settings_row = cursor.fetchone()
    current_company_name = settings_row["company_name"] if settings_row else COMPANY_NAME

    conn.close()

    # LOGO
    logo_path = "logo.png"
    if os.path.exists(logo_path):
        img = Image(logo_path, width=120, height=60)
        elements.append(img)
        elements.append(Spacer(1, 10))

    # Cégnév
    elements.append(Paragraph(current_company_name, styles["Title"]))
    elements.append(Spacer(1, 10))

    # Dátum
    elements.append(Paragraph(f"Dátum: {today}", styles["Normal"]))
    elements.append(Spacer(1, 10))

    # Cím
    elements.append(Paragraph(f"Árajánlat - {project['name']}", styles["Heading2"]))
    elements.append(Spacer(1, 20))

    # Tábla fejléc
    table_data = [["Tétel", "Mennyiség", "Egységár", "Összesen"]]

    total = 0

    for item in project_items:
        line_total = item["quantity"] * item["price"]
        total += line_total

        table_data.append([
            item["name"],
            f"{item['quantity']} {item['unit']}",
            f"{item['price']} Ft",
            f"{line_total} Ft"
        ])

    table = Table(table_data)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 20))

    # Végösszeg
    elements.append(Paragraph(f"<b>Végösszeg: {total} Ft</b>", styles["Heading2"]))
    elements.append(Spacer(1, 20))

    # Szöveges ajánlati blokk
    elements.append(Paragraph("Tisztelt Megrendelő!", styles["Normal"]))
    elements.append(Spacer(1, 10))

    elements.append(
        Paragraph(
            f"Az alábbiakban küldjük a(z) <b>{project['name']}</b> projektre vonatkozó árajánlatunkat.",
            styles["Normal"]
        )
    )
    elements.append(Spacer(1, 10))

    elements.append(
        Paragraph(
            "Az ajánlat a fenti táblázatban részletezett munkákat, anyagokat és kapcsolódó tételeket tartalmazza.",
            styles["Normal"]
        )
    )
    elements.append(Spacer(1, 10))

    elements.append(
        Paragraph(
            f"<b>A teljes kivitelezési költség: {total} Ft.</b>",
            styles["Normal"]
        )
    )
    elements.append(Spacer(1, 10))

    elements.append(
        Paragraph(
            "Amennyiben kérdése merül fel, állunk rendelkezésére.",
            styles["Normal"]
        )
    )
    elements.append(Spacer(1, 10))

    elements.append(
        Paragraph(
            f"Üdvözlettel:<br/>{current_company_name}",
            styles["Normal"]
        )
    )

    # PDF elkészítése
    doc.build(elements)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=project_{project_id}.pdf"}
    )

@app.post("/templates")
def create_template(name: str):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO templates (name) VALUES (?)",
        (name,)
    )

    conn.commit()
    template_id = cursor.lastrowid
    conn.close()

    return {
        "id": template_id,
        "name": name
    }


@app.get("/templates")
def get_templates():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM templates")
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]

@app.post("/templates/{template_id}/items")
def add_item_to_template(template_id: int, item_id: int, default_quantity: float):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM templates WHERE id = ?", (template_id,))
    template = cursor.fetchone()
    if not template:
        conn.close()
        return {"error": "Template not found"}

    cursor.execute("SELECT * FROM items WHERE id = ?", (item_id,))
    item = cursor.fetchone()
    if not item:
        conn.close()
        return {"error": "Item not found"}

    cursor.execute("""
        INSERT INTO template_items (template_id, item_id, default_quantity)
        VALUES (?, ?, ?)
    """, (template_id, item_id, default_quantity))

    conn.commit()
    template_item_id = cursor.lastrowid
    conn.close()

    return {
        "id": template_item_id,
        "template_id": template_id,
        "item_id": item_id,
        "default_quantity": default_quantity
    }

    @app.get("/templates/{template_id}/items")
    def get_template_items(template_id: int):
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                template_items.id AS template_item_id,
                items.id AS item_id,
                items.name,
                items.type,
                items.unit,
                items.price,
                items.description,
                template_items.default_quantity
            FROM template_items
            JOIN items ON template_items.item_id = items.id
            WHERE template_items.template_id = ?
        """, (template_id,))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    @app.post("/projects/{project_id}/add-template/{template_id}")
    def add_template_to_project(project_id: int, template_id: int):
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        project = cursor.fetchone()
        if not project:
            conn.close()
            return {"error": "Project not found"}

        cursor.execute("SELECT * FROM templates WHERE id = ?", (template_id,))
        template = cursor.fetchone()
        if not template:
            conn.close()
            return {"error": "Template not found"}

        cursor.execute("""
            SELECT * FROM template_items
            WHERE template_id = ?
        """, (template_id,))
        template_items = cursor.fetchall()

        added_items = []

        for template_item in template_items:
            cursor.execute("""
                INSERT INTO project_items (project_id, item_id, quantity)
                VALUES (?, ?, ?)
            """, (
                project_id,
                template_item["item_id"],
                template_item["default_quantity"]
            ))

            added_items.append({
                "id": cursor.lastrowid,
                "project_id": project_id,
                "item_id": template_item["item_id"],
                "quantity": template_item["default_quantity"]
            })

        conn.commit()
        conn.close()

        return {
            "message": "Template added to project",
            "project_id": project_id,
            "template_id": template_id,
            "added_items": added_items
        }

@app.delete("/templates/{template_id}/items/{template_item_id}")
def delete_template_item(template_id: int, template_item_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM template_items
        WHERE id = ? AND template_id = ?
    """, (template_item_id, template_id))

    conn.commit()

    if cursor.rowcount == 0:
        conn.close()
        return {"error": "Template item not found"}

    conn.close()
    return {"message": "Template item deleted"}

@app.put("/templates/{template_id}/items/{template_item_id}")
def update_template_item_quantity(template_id: int, template_item_id: int, default_quantity: float):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE template_items
        SET default_quantity = ?
        WHERE id = ? AND template_id = ?
    """, (default_quantity, template_item_id, template_id))

    conn.commit()

    if cursor.rowcount == 0:
        conn.close()
        return {"error": "Template item not found"}

    cursor.execute("""
        SELECT * FROM template_items
        WHERE id = ? AND template_id = ?
    """, (template_item_id, template_id))

    updated = cursor.fetchone()
    conn.close()

    return {
        "message": "Template item quantity updated",
        "updated": dict(updated)
    }

from fastapi import UploadFile, File
import pandas as pd
import io

@app.post("/items/import")
def import_items(file: UploadFile = File(...)):
    errors = []
    imported_count = 0
    imported_items = []

    try:
        file_content = file.file.read()

        if file.filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(file_content))
        elif file.filename.endswith(".xlsx"):
            df = pd.read_excel(io.BytesIO(file_content))
        else:
            return {"error": "Only .csv and .xlsx files are supported"}

    except Exception as e:
        return {
            "error": "File could not be read",
            "details": str(e)
        }

    required_columns = ["name", "type", "unit", "price", "description"]

    for col in required_columns:
        if col not in df.columns:
            return {"error": f"Missing required column: {col}"}

    for index, row in df.iterrows():
        try:
            name = str(row["name"]).strip()
            item_type = str(row["type"]).strip()
            unit = str(row["unit"]).strip()
            description = str(row["description"]).strip()

            if pd.isna(row["price"]):
                raise ValueError("price is missing")

            price = float(row["price"])

            if not name:
                raise ValueError("name is empty")

            new_item = {
                "id": len(ITEMS_DB) + 1,
                "name": name,
                "type": item_type,
                "unit": unit,
                "price": price,
                "description": description
            }

            ITEMS_DB.append(new_item)
            imported_items.append(new_item)
            imported_count += 1

        except Exception as e:
            errors.append({
                "row": int(index) + 2,
                "error": str(e)
            })

    return {
        "message": "Import finished",
        "imported": imported_count,
        "errors": errors,
        "items": imported_items
    }
@app.put("/settings/company-name")
def set_company_name(name: str):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE settings
        SET company_name = ?
        WHERE id = 1
    """, (name,))

    conn.commit()

    cursor.execute("SELECT company_name FROM settings WHERE id = 1")
    row = cursor.fetchone()
    conn.close()

    return {
        "message": "Company name updated",
        "company_name": row["company_name"]
    }
@app.get("/settings/company-name")
def get_company_name():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT company_name FROM settings WHERE id = 1")
    row = cursor.fetchone()
    conn.close()

    return {
        "company_name": row["company_name"]
    }

@app.post("/projects/{project_id}/add-template/{template_id}")
def add_template_to_project(project_id: int, template_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    project = cursor.fetchone()
    if not project:
        conn.close()
        return {"error": "Project not found"}

    cursor.execute("SELECT * FROM templates WHERE id = ?", (template_id,))
    template = cursor.fetchone()
    if not template:
        conn.close()
        return {"error": "Template not found"}

    cursor.execute("""
        SELECT * FROM template_items
        WHERE template_id = ?
    """, (template_id,))
    template_items = cursor.fetchall()

    added_items = []

    for template_item in template_items:
        cursor.execute("""
            INSERT INTO project_items (project_id, item_id, quantity)
            VALUES (?, ?, ?)
        """, (
            project_id,
            template_item["item_id"],
            template_item["default_quantity"]
        ))

        added_items.append({
            "id": cursor.lastrowid,
            "project_id": project_id,
            "item_id": template_item["item_id"],
            "quantity": template_item["default_quantity"]
        })

    conn.commit()
    conn.close()

    return {
        "message": "Template added to project",
        "project_id": project_id,
        "template_id": template_id,
        "added_items": added_items
    }