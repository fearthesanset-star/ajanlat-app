from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
from jose import jwt, JWTError
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from datetime import datetime, timedelta
import bcrypt
import io
import os

from database import init_db, get_connection, is_postgres

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

SECRET_KEY = os.getenv("SECRET_KEY", "SUPER_SECRET_KEY_CHANGE_THIS_LATER")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24


def db_query(query: str) -> str:
    if is_postgres():
        return query.replace("?", "%s")
    return query


def returning_id() -> str:
    return " RETURNING id" if is_postgres() else ""


def get_inserted_id(cursor):
    if is_postgres():
        return cursor.fetchone()["id"]
    return cursor.lastrowid


def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")[:72]
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    password_bytes = password.encode("utf-8")[:72]
    hashed_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(password_bytes, hashed_bytes)


def create_access_token(user_id: int):
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)

    payload = {
        "sub": str(user_id),
        "exp": expire,
    }

    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user_id(authorization: str = Header(None)) -> int:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization.replace("Bearer ", "")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")

        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")

        return int(user_id)

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


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


@app.get("/")
def root():
    return {"message": "API működik"}


@app.post("/register")
def register(user: UserRegister):
    email = user.email.strip()
    password = hash_password(user.password.strip())

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            db_query("INSERT INTO users (email, password) VALUES (?, ?)"),
            (email, password),
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
        db_query("SELECT * FROM users WHERE email = ?"),
        (email,),
    )

    db_user = cursor.fetchone()
    conn.close()

    if not db_user:
        return {"error": "Hibás email vagy jelszó"}

    if not verify_password(password, db_user["password"]):
        return {"error": "Hibás email vagy jelszó"}

    token = create_access_token(db_user["id"])

    return {
        "message": "Sikeres login",
        "user_id": db_user["id"],
        "access_token": token,
    }


@app.get("/me")
def get_me(current_user_id: int = Depends(get_current_user_id)):
    return {"user_id": current_user_id}


@app.post("/items")
def create_item(item: Item, current_user_id: int = Depends(get_current_user_id)):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(db_query(f"""
        INSERT INTO items (name, type, unit, price, description, user_id)
        VALUES (?, ?, ?, ?, ?, ?)
        {returning_id()}
    """), (
        item.name,
        item.type,
        item.unit,
        item.price,
        item.description,
        current_user_id,
    ))

    item_id = get_inserted_id(cursor)
    conn.commit()
    conn.close()

    return {
        "id": item_id,
        "name": item.name,
        "type": item.type,
        "unit": item.unit,
        "price": item.price,
        "description": item.description,
        "user_id": current_user_id,
    }


@app.get("/items/me")
def get_my_items(current_user_id: int = Depends(get_current_user_id)):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        db_query("SELECT * FROM items WHERE user_id = ? ORDER BY id DESC"),
        (current_user_id,),
    )
    rows = cursor.fetchall()

    conn.close()
    return [dict(row) for row in rows]


@app.delete("/items/{item_id}")
def delete_item(item_id: int, current_user_id: int = Depends(get_current_user_id)):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        db_query("DELETE FROM items WHERE id = ? AND user_id = ?"),
        (item_id, current_user_id),
    )

    conn.commit()

    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Item not found")

    conn.close()
    return {"message": "Item deleted"}


@app.post("/projects")
def create_project(
    name: str,
    valid_until: str = "",
    current_user_id: int = Depends(get_current_user_id),
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(db_query(f"""
        INSERT INTO projects (name, user_id, valid_until)
        VALUES (?, ?, ?)
        {returning_id()}
    """), (name, current_user_id, valid_until))

    project_id = get_inserted_id(cursor)
    conn.commit()
    conn.close()

    return {
        "id": project_id,
        "name": name,
        "user_id": current_user_id,
        "valid_until": valid_until,
    }


@app.get("/projects/me")
def get_my_projects(current_user_id: int = Depends(get_current_user_id)):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        db_query("SELECT * FROM projects WHERE user_id = ? ORDER BY id DESC"),
        (current_user_id,),
    )
    rows = cursor.fetchall()

    conn.close()
    return [dict(row) for row in rows]


@app.post("/projects/{project_id}/add-item/{item_id}")
def add_item_to_project(
    project_id: int,
    item_id: int,
    quantity: float,
    current_user_id: int = Depends(get_current_user_id),
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        db_query("SELECT * FROM projects WHERE id = ? AND user_id = ?"),
        (project_id, current_user_id),
    )
    project = cursor.fetchone()

    if not project:
        conn.close()
        raise HTTPException(status_code=404, detail="Project not found")

    cursor.execute(
        db_query("SELECT * FROM items WHERE id = ? AND user_id = ?"),
        (item_id, current_user_id),
    )
    item = cursor.fetchone()

    if not item:
        conn.close()
        raise HTTPException(status_code=404, detail="Item not found")

    cursor.execute(db_query(f"""
        INSERT INTO project_items (project_id, item_id, quantity)
        VALUES (?, ?, ?)
        {returning_id()}
    """), (project_id, item_id, quantity))

    project_item_id = get_inserted_id(cursor)
    conn.commit()
    conn.close()

    return {
        "id": project_item_id,
        "project_id": project_id,
        "item_id": item_id,
        "quantity": quantity,
    }


@app.get("/projects/{project_id}/items")
def get_project_items(
    project_id: int,
    current_user_id: int = Depends(get_current_user_id),
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        db_query("SELECT * FROM projects WHERE id = ? AND user_id = ?"),
        (project_id, current_user_id),
    )
    project = cursor.fetchone()

    if not project:
        conn.close()
        raise HTTPException(status_code=404, detail="Project not found")

    cursor.execute(db_query("""
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
    """), (project_id,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


@app.get("/projects/{project_id}/total")
def get_project_total(
    project_id: int,
    current_user_id: int = Depends(get_current_user_id),
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        db_query("SELECT * FROM projects WHERE id = ? AND user_id = ?"),
        (project_id, current_user_id),
    )
    project = cursor.fetchone()

    if not project:
        conn.close()
        raise HTTPException(status_code=404, detail="Project not found")

    cursor.execute(db_query("""
        SELECT SUM(project_items.quantity * items.price) AS total
        FROM project_items
        JOIN items ON project_items.item_id = items.id
        WHERE project_items.project_id = ?
    """), (project_id,))

    row = cursor.fetchone()
    conn.close()

    total = row["total"] if row["total"] is not None else 0

    return {
        "project_id": project_id,
        "total": total,
    }


@app.delete("/projects/{project_id}/items/{project_item_id}")
def delete_project_item(
    project_id: int,
    project_item_id: int,
    current_user_id: int = Depends(get_current_user_id),
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        db_query("SELECT * FROM projects WHERE id = ? AND user_id = ?"),
        (project_id, current_user_id),
    )
    project = cursor.fetchone()

    if not project:
        conn.close()
        raise HTTPException(status_code=404, detail="Project not found")

    cursor.execute(db_query("""
        DELETE FROM project_items
        WHERE id = ? AND project_id = ?
    """), (project_item_id, project_id))

    conn.commit()

    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Project item not found")

    conn.close()
    return {"message": "Project item deleted"}


@app.get("/projects/{project_id}/export-pdf")
def export_project_pdf(
    project_id: int,
    current_user_id: int = Depends(get_current_user_id),
):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer)
    styles = getSampleStyleSheet()
    elements = []

    today = datetime.now().strftime("%Y-%m-%d")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        db_query("SELECT * FROM projects WHERE id = ? AND user_id = ?"),
        (project_id, current_user_id),
    )
    project = cursor.fetchone()

    if not project:
        conn.close()
        raise HTTPException(status_code=404, detail="Project not found")

    cursor.execute(db_query("""
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
    """), (project_id,))
    project_items = cursor.fetchall()

    if not project_items:
        conn.close()
        return {"error": "Project has no items"}

    cursor.execute(db_query("""
        SELECT company_name, company_email, company_phone
        FROM user_settings
        WHERE user_id = ?
    """), (current_user_id,))

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

    if project["valid_until"]:
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
            f"{line_total} Ft",
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
            styles["Normal"],
        )
    )
    elements.append(Spacer(1, 10))

    elements.append(
        Paragraph(
            "Az ajánlat a fenti táblázatban részletezett munkákat, anyagokat és kapcsolódó tételeket tartalmazza.",
            styles["Normal"],
        )
    )
    elements.append(Spacer(1, 10))

    elements.append(
        Paragraph(
            f"<b>A teljes kivitelezési költség: {total} Ft.</b>",
            styles["Normal"],
        )
    )
    elements.append(Spacer(1, 10))

    elements.append(
        Paragraph(
            "Amennyiben kérdése merül fel, állunk rendelkezésére.",
            styles["Normal"],
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
            styles["Normal"],
        )
    )

    doc.build(elements)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=project_{project_id}.pdf"},
    )


@app.post("/templates")
def create_template(
    name: str,
    current_user_id: int = Depends(get_current_user_id),
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(db_query(f"""
        INSERT INTO templates (name, user_id)
        VALUES (?, ?)
        {returning_id()}
    """), (name, current_user_id))

    template_id = get_inserted_id(cursor)
    conn.commit()
    conn.close()

    return {
        "id": template_id,
        "name": name,
        "user_id": current_user_id,
    }


@app.get("/templates/me")
def get_my_templates(current_user_id: int = Depends(get_current_user_id)):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        db_query("SELECT * FROM templates WHERE user_id = ? ORDER BY id DESC"),
        (current_user_id,),
    )
    rows = cursor.fetchall()

    conn.close()
    return [dict(row) for row in rows]


@app.post("/templates/{template_id}/items")
def add_item_to_template(
    template_id: int,
    item_id: int,
    default_quantity: float,
    current_user_id: int = Depends(get_current_user_id),
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        db_query("SELECT * FROM templates WHERE id = ? AND user_id = ?"),
        (template_id, current_user_id),
    )
    template = cursor.fetchone()

    if not template:
        conn.close()
        raise HTTPException(status_code=404, detail="Template not found")

    cursor.execute(
        db_query("SELECT * FROM items WHERE id = ? AND user_id = ?"),
        (item_id, current_user_id),
    )
    item = cursor.fetchone()

    if not item:
        conn.close()
        raise HTTPException(status_code=404, detail="Item not found")

    cursor.execute(db_query(f"""
        INSERT INTO template_items (template_id, item_id, default_quantity)
        VALUES (?, ?, ?)
        {returning_id()}
    """), (template_id, item_id, default_quantity))

    template_item_id = get_inserted_id(cursor)
    conn.commit()
    conn.close()

    return {
        "id": template_item_id,
        "template_id": template_id,
        "item_id": item_id,
        "default_quantity": default_quantity,
    }


@app.get("/templates/{template_id}/items")
def get_template_items(
    template_id: int,
    current_user_id: int = Depends(get_current_user_id),
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        db_query("SELECT * FROM templates WHERE id = ? AND user_id = ?"),
        (template_id, current_user_id),
    )
    template = cursor.fetchone()

    if not template:
        conn.close()
        raise HTTPException(status_code=404, detail="Template not found")

    cursor.execute(db_query("""
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
    """), (template_id,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


@app.post("/projects/{project_id}/add-template/{template_id}")
def add_template_to_project(
    project_id: int,
    template_id: int,
    current_user_id: int = Depends(get_current_user_id),
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        db_query("SELECT * FROM projects WHERE id = ? AND user_id = ?"),
        (project_id, current_user_id),
    )
    project = cursor.fetchone()

    if not project:
        conn.close()
        raise HTTPException(status_code=404, detail="Project not found")

    cursor.execute(
        db_query("SELECT * FROM templates WHERE id = ? AND user_id = ?"),
        (template_id, current_user_id),
    )
    template = cursor.fetchone()

    if not template:
        conn.close()
        raise HTTPException(status_code=404, detail="Template not found")

    cursor.execute(
        db_query("SELECT * FROM template_items WHERE template_id = ?"),
        (template_id,),
    )
    template_items = cursor.fetchall()

    added_items = []

    for template_item in template_items:
        cursor.execute(db_query(f"""
            INSERT INTO project_items (project_id, item_id, quantity)
            VALUES (?, ?, ?)
            {returning_id()}
        """), (
            project_id,
            template_item["item_id"],
            template_item["default_quantity"],
        ))

        added_items.append({
            "id": get_inserted_id(cursor),
            "project_id": project_id,
            "item_id": template_item["item_id"],
            "quantity": template_item["default_quantity"],
        })

    conn.commit()
    conn.close()

    return {
        "message": "Template added to project",
        "project_id": project_id,
        "template_id": template_id,
        "added_items": added_items,
    }


@app.delete("/templates/{template_id}/items/{template_item_id}")
def delete_template_item(
    template_id: int,
    template_item_id: int,
    current_user_id: int = Depends(get_current_user_id),
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        db_query("SELECT * FROM templates WHERE id = ? AND user_id = ?"),
        (template_id, current_user_id),
    )
    template = cursor.fetchone()

    if not template:
        conn.close()
        raise HTTPException(status_code=404, detail="Template not found")

    cursor.execute(db_query("""
        DELETE FROM template_items
        WHERE id = ? AND template_id = ?
    """), (template_item_id, template_id))

    conn.commit()

    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Template item not found")

    conn.close()
    return {"message": "Template item deleted"}


@app.put("/templates/{template_id}/items/{template_item_id}")
def update_template_item_quantity(
    template_id: int,
    template_item_id: int,
    default_quantity: float,
    current_user_id: int = Depends(get_current_user_id),
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        db_query("SELECT * FROM templates WHERE id = ? AND user_id = ?"),
        (template_id, current_user_id),
    )
    template = cursor.fetchone()

    if not template:
        conn.close()
        raise HTTPException(status_code=404, detail="Template not found")

    cursor.execute(db_query("""
        UPDATE template_items
        SET default_quantity = ?
        WHERE id = ? AND template_id = ?
    """), (default_quantity, template_item_id, template_id))

    conn.commit()

    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Template item not found")

    cursor.execute(db_query("""
        SELECT * FROM template_items
        WHERE id = ? AND template_id = ?
    """), (template_item_id, template_id))

    updated = cursor.fetchone()
    conn.close()

    return {
        "message": "Template item quantity updated",
        "updated": dict(updated),
    }


@app.post("/items/import")
def import_items(
    file: UploadFile = File(...),
    current_user_id: int = Depends(get_current_user_id),
):
    return {
        "message": "Import temporarily disabled during user-based migration"
    }


@app.put("/settings/company")
def set_company_settings(
    name: str,
    email: str = "",
    phone: str = "",
    current_user_id: int = Depends(get_current_user_id),
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        db_query("SELECT * FROM user_settings WHERE user_id = ?"),
        (current_user_id,),
    )
    existing = cursor.fetchone()

    if existing:
        cursor.execute(db_query("""
            UPDATE user_settings
            SET company_name = ?, company_email = ?, company_phone = ?
            WHERE user_id = ?
        """), (name, email, phone, current_user_id))
    else:
        cursor.execute(db_query("""
            INSERT INTO user_settings (user_id, company_name, company_email, company_phone)
            VALUES (?, ?, ?, ?)
        """), (current_user_id, name, email, phone))

    conn.commit()
    conn.close()

    return {
        "message": "Company settings updated",
        "company_name": name,
        "company_email": email,
        "company_phone": phone,
    }


@app.get("/settings/company/me")
def get_my_company_settings(current_user_id: int = Depends(get_current_user_id)):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(db_query("""
        SELECT company_name, company_email, company_phone
        FROM user_settings
        WHERE user_id = ?
    """), (current_user_id,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return {
            "company_name": "",
            "company_email": "",
            "company_phone": "",
        }

    return {
        "company_name": row["company_name"],
        "company_email": row["company_email"],
        "company_phone": row["company_phone"],
    }


@app.post("/subscribe")
def subscribe(subscriber: Subscriber):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(db_query("""
            INSERT INTO subscribers (email, accepted)
            VALUES (?, ?)
        """), (subscriber.email, int(subscriber.accepted)))
        conn.commit()
    except Exception:
        conn.close()
        return {"error": "Email already exists or invalid"}

    conn.close()
    return {"message": "Subscribed successfully"}





