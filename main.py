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
        "https://ajanlat-frontend.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

COMPANY_NAME = "Sajat Ceg Kft."


class UserRegister(BaseModel):
    email: str
    password: str


class UserLogin(BaseModel):
    email: str
    password: str


class Subscriber(BaseModel):
    email: str
    accepted: bool


class Item(BaseModel):
    name: str
    type: str
    unit: str
    price: float
    description: str
    user_id: int


@app.get("/")
def root():
    return {"message": "API működik"}


@app.post("/register")
def register(user: UserRegister):
    email = user.email.strip()
    password = user.password.strip()

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO users (email, password) VALUES (?, ?)",
            (email, password)
        )
        conn.commit()
    except Exception:
        conn.close()
        return {"error": "Email már létezik"}

    conn.close()
    return {"message": "Sikeres regisztráció"}


@app.post("/login")
def login(user: UserLogin):
    email = user.email.strip()
    password = user.password.strip()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM users WHERE email = ? AND password = ?",
        (email, password)
    )

    db_user = cursor.fetchone()
    conn.close()

    if not db_user:
        return {"error": "Hibás email vagy jelszó"}

    return {
        "message": "Sikeres login",
        "user_id": db_user["id"]
    }


@app.get("/debug-users")
def debug_users():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, email FROM users")
    users = cursor.fetchall()

    conn.close()
    return [dict(user) for user in users]


@app.post("/items")
def create_item(item: Item):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO items (name, type, unit, price, description, user_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        item.name,
        item.type,
        item.unit,
        item.price,
        item.description,
        item.user_id
    ))

    conn.commit()
    item_id = cursor.lastrowid
    conn.close()

    return {
        "id": item_id,
        "name": item.name,
        "type": item.type,
        "unit": item.unit,
        "price": item.price,
        "description": item.description,
        "user_id": item.user_id
    }


@app.get("/items/{user_id}")
def get_items(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM items WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()

    conn.close()
    return [dict(row) for row in rows]


@app.delete("/items/{item_id}")
def delete_item(item_id: int, user_id: int = None):
    conn = get_connection()
    cursor = conn.cursor()

    if user_id is not None:
        cursor.execute("DELETE FROM items WHERE id = ? AND user_id = ?", (item_id, user_id))
    else:
        cursor.execute("DELETE FROM items WHERE id = ?", (item_id,))

    conn.commit()

    if cursor.rowcount == 0:
        conn.close()
        return {"error": "Item not found"}

    conn.close()
    return {"message": "Item deleted"}


@app.post("/projects")
def create_project(name: str, user_id: int, valid_until: str = ""):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO projects (name, user_id, valid_until) VALUES (?, ?, ?)",
        (name, user_id, valid_until)
    )

    conn.commit()
    project_id = cursor.lastrowid
    conn.close()

    return {
        "id": project_id,
        "name": name,
        "user_id": user_id,
        "valid_until": valid_until
    }


@app.get("/projects/user/{user_id}")
def get_projects_for_user(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM projects WHERE user_id = ? ORDER BY id DESC", (user_id,))
    rows = cursor.fetchall()

    conn.close()
    return [dict(row) for row in rows]


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

    if project["user_id"] is not None and item["user_id"] is not None:
        if project["user_id"] != item["user_id"]:
            conn.close()
            return {"error": "Item does not belong to this user"}

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


@app.get("/projects/{project_id}/export-pdf")
def export_project_pdf(project_id: int):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer)
    styles = getSampleStyleSheet()
    elements = []

    today = datetime.now().strftime("%Y-%m-%d")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
    project = cursor.fetchone()
    if not project:
        conn.close()
        return {"error": "Project not found"}

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

    cursor.execute("SELECT company_name, company_email, company_phone FROM settings WHERE id = 1")
    settings_row = cursor.fetchone()

    current_company_name = settings_row["company_name"] if settings_row else COMPANY_NAME
    current_company_email = settings_row["company_email"] if settings_row else ""
    current_company_phone = settings_row["company_phone"] if settings_row else ""

    conn.close()

    logo_path = "logo.png"
    if os.path.exists(logo_path):
        img = Image(logo_path, width=120, height=60)
        elements.append(img)
        elements.append(Spacer(1, 10))

    elements.append(Paragraph(current_company_name, styles["Title"]))
    elements.append(Spacer(1, 10))

    elements.append(Paragraph(f"Dátum: {today}", styles["Normal"]))
    elements.append(Spacer(1, 10))

    if "valid_until" in project.keys() and project["valid_until"]:
        elements.append(Paragraph(f"Ajánlat érvényes: {project['valid_until']}", styles["Normal"]))
        elements.append(Spacer(1, 10))

    elements.append(Paragraph(f"Árajánlat - {project['name']}", styles["Heading2"]))
    elements.append(Spacer(1, 20))

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

    elements.append(Paragraph(f"<b>Végösszeg: {total} Ft</b>", styles["Heading2"]))
    elements.append(Spacer(1, 20))

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

    if current_company_email:
        elements.append(Paragraph(f"Email: {current_company_email}", styles["Normal"]))

    if current_company_phone:
        elements.append(Paragraph(f"Telefon: {current_company_phone}", styles["Normal"]))

    elements.append(Spacer(1, 10))

    elements.append(
        Paragraph(
            f"Üdvözlettel:<br/>{current_company_name}",
            styles["Normal"]
        )
    )

    doc.build(elements)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=project_{project_id}.pdf"}
    )


@app.post("/templates")
def create_template(name: str, user_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO templates (name, user_id)
        VALUES (?, ?)
    """, (name, user_id))

    conn.commit()
    template_id = cursor.lastrowid
    conn.close()

    return {
        "id": template_id,
        "name": name,
        "user_id": user_id
    }


@app.get("/templates/{user_id}")
def get_templates(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM templates WHERE user_id = ?", (user_id,))
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

    if template["user_id"] is not None and item["user_id"] is not None:
        if template["user_id"] != item["user_id"]:
            conn.close()
            return {"error": "Item does not belong to this user"}

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

    if project["user_id"] is not None and template["user_id"] is not None:
        if project["user_id"] != template["user_id"]:
            conn.close()
            return {"error": "Template does not belong to this user"}

    cursor.execute("SELECT * FROM template_items WHERE template_id = ?", (template_id,))
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


@app.post("/items/import")
def import_items(file: UploadFile = File(...)):
    return {
        "message": "Import temporarily disabled during user-based migration"
    }


@app.put("/settings/company")
def set_company_settings(name: str, email: str = "", phone: str = ""):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE settings
        SET company_name = ?, company_email = ?, company_phone = ?
        WHERE id = 1
    """, (name, email, phone))

    conn.commit()

    cursor.execute("SELECT company_name, company_email, company_phone FROM settings WHERE id = 1")
    row = cursor.fetchone()
    conn.close()

    return {
        "message": "Company settings updated",
        "company_name": row["company_name"],
        "company_email": row["company_email"],
        "company_phone": row["company_phone"]
    }


@app.get("/settings/company")
def get_company_settings():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT company_name, company_email, company_phone FROM settings WHERE id = 1")
    row = cursor.fetchone()
    conn.close()

    return {
        "company_name": row["company_name"] if row else COMPANY_NAME,
        "company_email": row["company_email"] if row else "",
        "company_phone": row["company_phone"] if row else ""
    }


@app.post("/subscribe")
def subscribe(subscriber: Subscriber):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO subscribers (email, accepted)
            VALUES (?, ?)
        """, (subscriber.email, int(subscriber.accepted)))
        conn.commit()
    except Exception:
        conn.close()
        return {"error": "Email already exists or invalid"}

    conn.close()
    return {"message": "Subscribed successfully"}


@app.get("/subscribers")
def get_subscribers():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM subscribers ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


@app.get("/fix-db")
def fix_db():
    init_db()
    return {"message": "DB updated"}




