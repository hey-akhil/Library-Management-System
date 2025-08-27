from fastapi import FastAPI, Request, HTTPException, Form, Depends, Response, Cookie
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import psycopg2
from flask import request
from psycopg2.extras import RealDictCursor
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordRequestForm
from datetime import datetime

app = FastAPI(title="Library Management System")

# Mount static files (CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="templates")

# Password hashing setup
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

# DB helper for PostgreSQL
def get_db_connection():
    conn = psycopg2.connect(
        host="localhost",
        database="library_db",
        user="admin",
        password="admin",
        cursor_factory=RealDictCursor
    )
    return conn

# Helper to get user with role by id
def get_user_with_role(user_id: str):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, username, full_name, email, role FROM users WHERE id = %s", (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    return user

# -------------------------------
# Register Routes
# -------------------------------

@app.get("/register", response_class=HTMLResponse)
def register_form(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register")
def register_user(
    username: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(None),
    email: str = Form(None)
):
    conn = get_db_connection()
    cur = conn.cursor()
    hashed_pw = hash_password(password)

    try:
        cur.execute(
            "INSERT INTO users (username, hashed_password, full_name, email) VALUES (%s, %s, %s, %s)",
            (username, hashed_pw, full_name, email)
        )
        conn.commit()
    except psycopg2.IntegrityError:
        conn.rollback()
        cur.close()
        conn.close()
        return templates.TemplateResponse("register.html", {
            "request": Request,
            "error": "Username or email already exists"
        })
    cur.close()
    conn.close()

    return RedirectResponse(url="/login", status_code=302)

# -------------------------------
# Login Routes
# -------------------------------

@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login(response: Response, form_data: OAuth2PasswordRequestForm = Depends()):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username = %s", (form_data.username,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if not user or not verify_password(form_data.password, user['hashed_password']):
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    # Redirect based on role
    if user.get("role") == "admin":
        redirect_url = "/admin"
    else:
        redirect_url = "/home"

    response = RedirectResponse(url=redirect_url, status_code=302)
    response.set_cookie(key="user_id", expires= "3600" , value=str(user["id"]))
    return response

# -------------------------------
# Homepage – Requires login
# -------------------------------
@app.get("/home", response_class=HTMLResponse)
def homepage(request: Request, user_id: str = Cookie(None)):
    if not user_id:
        return RedirectResponse(url="/login", status_code=302)

    user = get_user_with_role(user_id)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    conn = get_db_connection()
    cur = conn.cursor()

    # Fetch books
    cur.execute("SELECT * FROM books ORDER BY id;")
    books = cur.fetchall()

    cur.close()
    conn.close()

    return templates.TemplateResponse("homepage.html", {
        "request": request,
        "user": user,
        "books": books
    })

# -------------------------------
# Logout
# -------------------------------
@app.get("/logout")
def logout(response: Response):
    response.delete_cookie(key="user_id")
    return RedirectResponse(url="/login", status_code=302)

# -------------------------------
# Books List with Issue Button
# -------------------------------
@app.get("/books", response_class=HTMLResponse)
def read_books(request: Request, user_id: str = Cookie(None)):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM books ORDER BY id;")
    books = cur.fetchall()

    cur.execute("""SELECT * FROM users WHERE id = %s """, user_id)
    user = cur.fetchone()

    issued_book_ids = []
    if user_id:
        cur.execute("""
            SELECT book_id FROM issued_books WHERE user_id = %s AND return_date IS NULL
        """, user_id)
        issued_books = cur.fetchall()
        issued_book_ids = [b['book_id'] for b in issued_books]

    cur.close()
    conn.close()

    return templates.TemplateResponse("book_lists.html", {
        "request": request,
        "books": books,
        "user": user,
        "issued_book_ids": issued_book_ids
    })

# -------------------------------
# Book by ID (for details)
# -------------------------------
@app.get("/books/{book_id}")
def read_book(book_id: int, request: Request):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM books WHERE id = %s;", (book_id,))
    book = cur.fetchone()
    cur.close()
    conn.close()

    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")

    accept_header = request.headers.get("accept", "")
    if "text/html" in accept_header:
        return templates.TemplateResponse("book_detail.html", {"request": request, "book": book})
    else:
        return JSONResponse(content={"book": book})

# -------------------------------
# Issue Book Endpoint (POST)
# -------------------------------
@app.post("/issue-book")
def issue_book(book_id: int = Form(...), user_id: str = Cookie(None)):
    if not user_id:
        return RedirectResponse(url="/login", status_code=302)

    conn = get_db_connection()
    cur = conn.cursor()

    # Check if book exists and copies available
    cur.execute("SELECT copies_available FROM books WHERE id = %s", (book_id,))
    book = cur.fetchone()
    if not book:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Book not found")

    if book['copies_available'] <= 0:
        cur.close()
        conn.close()
        raise HTTPException(status_code=400, detail="No copies available")

    # Check if user already issued this book and hasn't returned
    cur.execute("""
        SELECT * FROM issued_books 
        WHERE user_id = %s AND book_id = %s AND return_date IS NULL
    """, (user_id, book_id))
    existing_issue = cur.fetchone()
    if existing_issue:
        cur.close()
        conn.close()
        raise HTTPException(status_code=400, detail="You already issued this book")

    # Issue book: insert into issued_books
    cur.execute("""
        INSERT INTO issued_books (user_id, book_id)
        VALUES (%s, %s)
    """, (user_id, book_id))

    # Decrement copies_available in books table
    cur.execute("""
        UPDATE books SET copies_available = copies_available - 1 WHERE id = %s
    """, (book_id,))

    conn.commit()
    cur.close()
    conn.close()

    return RedirectResponse(url="/books", status_code=303)

# -------------------------------
# Return Book Endpoint (POST)
# -------------------------------
@app.post("/return-book")
def return_book(book_id: int = Form(...), user_id: str = Cookie(None)):
    if not user_id:
        return RedirectResponse(url="/login", status_code=302)

    conn = get_db_connection()
    cur = conn.cursor()

    # Check if user has issued this book and not returned yet
    cur.execute("""
        SELECT * FROM issued_books 
        WHERE user_id = %s AND book_id = %s AND return_date IS NULL
    """, (user_id, book_id))
    issue_record = cur.fetchone()

    if not issue_record:
        cur.close()
        conn.close()
        raise HTTPException(status_code=400, detail="You have not issued this book")

    # Mark as returned
    cur.execute("""
        UPDATE issued_books 
        SET return_date = %s 
        WHERE user_id = %s AND book_id = %s AND return_date IS NULL
    """, (datetime.now(), user_id, book_id))

    # Increment copies available
    cur.execute("""
        UPDATE books SET copies_available = copies_available + 1 WHERE id = %s
    """, (book_id,))

    conn.commit()
    cur.close()
    conn.close()

    return RedirectResponse(url="/my-issued-books", status_code=303)  # Redirect to issued books page

# -------------------------------
# My Issued Books Page
# -------------------------------
@app.get("/my-issued-books", response_class=HTMLResponse)
def my_issued_books(request: Request, user_id: str = Cookie(None)):
    if not user_id:
        return RedirectResponse(url="/login", status_code=302)

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""SELECT * FROM users WHERE id = %s """, user_id)
    user = cur.fetchone()

    # Fetch issued books for this user that are not returned
    cur.execute("""
        SELECT ib.id as issue_id, b.id as book_id, b.title, b.author, ib.issue_date
        FROM issued_books ib
        JOIN books b ON ib.book_id = b.id
        WHERE ib.user_id = %s AND ib.return_date IS NULL
        ORDER BY ib.issue_date DESC
    """, (user_id,))
    issued_books = cur.fetchall()

    cur.close()
    conn.close()

    return templates.TemplateResponse("my_issued_books.html", {
        "request": request,
        "user":  user,
        "issued_books": issued_books
    })


# GET form to add a new book
@app.get("/add-book", response_class=HTMLResponse)
def add_book_form(request: Request, user_id: str = Cookie(None)):
    if not user_id:
        return RedirectResponse(url="/login", status_code=302)

    user = get_user_with_role(user_id)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    return templates.TemplateResponse("add_book.html", {
        "request": request,
        "user": user
    })


# -------------------------------
# POST to submit new book
# -------------------------------

@app.post("/add-book")
def add_book(
    title: str = Form(...),
    author: str = Form(...),
    published_year: int = Form(...),
    copies_available: int = Form(...),
    user_id: str = Cookie(None)
):
    if not user_id:
        return RedirectResponse(url="/login", status_code=302)

    user = get_user_with_role(user_id)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO books (title, author, published_year, copies_available)
            VALUES (%s, %s, %s, %s)
        """, (title, author, published_year, copies_available))
        conn.commit()
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        return templates.TemplateResponse("add_book.html", {
            "request": request,
            "user": user,
            "error": f"Error adding book: {e}"
        })

    cur.close()
    conn.close()

    return RedirectResponse(url="/admin/books", status_code=302)


# -------------------------------
# Update Profile
# -------------------------------
@app.get("/profile", response_class=HTMLResponse)
def get_profile(request: Request, user_id: str = Cookie(None)):

    if not user_id:
        return RedirectResponse(url="/login", status_code=302)

    user = get_user_with_role(user_id)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse("profile.html", {"request": request, "user": user})


@app.post("/profile")
def update_profile(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(None),
    user_id: str = Cookie(None)
):
    if not user_id:
        return RedirectResponse(url="/login", status_code=302)

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        if password:
            hashed_pw = hash_password(password)
            cur.execute("""
                UPDATE users SET full_name = %s, email = %s, hashed_password = %s WHERE id = %s
            """, (full_name, email, hashed_pw, user_id))
        else:
            cur.execute("""
                UPDATE users SET full_name = %s, email = %s WHERE id = %s
            """, (full_name, email, user_id))

        conn.commit()
        message = "Profile updated successfully."
    except Exception as e:
        conn.rollback()
        message = "Failed to update profile."
    finally:
        cur.execute("SELECT id, username, full_name, email, role FROM users WHERE id = %s", (user_id,))
        user = cur.fetchone()
        cur.close()
        conn.close()

    return templates.TemplateResponse("profile.html", {
        "request": request,
        "user": user,
        "success": message if "successfully" in message else None,
        "error": None if "successfully" in message else message
    })

# POST: handle delete request
@app.post("/admin/books/delete", response_class=HTMLResponse)
def delete_book(
    request: Request,
    book_id: int = Form(...),
    user_id: str = Cookie(None)
):
    user = get_user_with_role(user_id)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM books WHERE id = %s", (book_id,))
    conn.commit()
    cur.close()
    conn.close()

    return RedirectResponse(url="/admin/books", status_code=303)
# -------------------------------
# Admin Dashboard
# -------------------------------
@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request, user_id: str = Cookie(None)):
    if not user_id:
        return RedirectResponse(url="/login")

    user = get_user_with_role(user_id)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    conn = get_db_connection()
    cur = conn.cursor()

    # Fetch counts
    cur.execute("SELECT COUNT(*) FROM users")
    total_users = cur.fetchone()["count"]

    cur.execute("SELECT COUNT(*) FROM books")
    total_books = cur.fetchone()["count"]

    cur.execute("SELECT COUNT(*) FROM issued_books WHERE return_date IS NULL")
    total_issued = cur.fetchone()["count"]

    cur.close()
    conn.close()

    return templates.TemplateResponse("admin.html", {
        "request": request,
        "user": user,
        "total_users": total_users,
        "total_books": total_books,
        "total_issued": total_issued
    })

# GET: show list of books with edit/delete buttons
@app.get("/admin/books", response_class=HTMLResponse)
def manage_books(request: Request, user_id: str = Cookie(None)):
    user = get_user_with_role(user_id)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM books ORDER BY id;")
    books = cur.fetchall()
    cur.close()
    conn.close()

    return templates.TemplateResponse("admin_manage_books.html", {
        "request": request,
        "user": user,
        "books": books
    })

# POST: handle edit form submission
@app.post("/admin/books/edit", response_class=HTMLResponse)
def edit_book(
    request: Request,
    book_id: int = Form(...),
    title: str = Form(...),
    author: str = Form(...),
    published_year: int = Form(...),
    copies_available: int = Form(...),
    user_id: str = Cookie(None)
):
    user = get_user_with_role(user_id)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE books
        SET title = %s, author = %s, published_year = %s, copies_available = %s
        WHERE id = %s
    """, (title, author, published_year, copies_available, book_id))
    conn.commit()
    cur.close()
    conn.close()

    return RedirectResponse(url="/admin/books", status_code=303)


# -------------------------------
# Manage users
# -------------------------------
# GET: Show user list with edit/delete options
@app.get("/admin/users", response_class=HTMLResponse)
def manage_users(request: Request, user_id: str = Cookie(None)):
    user = get_user_with_role(user_id)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, username, full_name, email, role, created_at FROM users ORDER BY id;")
    users = cur.fetchall()
    cur.close()
    conn.close()

    return templates.TemplateResponse("admin_manage_users.html", {
        "request": request,
        "user": user,
        "users": users
    })

# POST: Edit user details
@app.post("/admin/users/edit", response_class=HTMLResponse)
def edit_user(
    request: Request,
    user_id_form: int = Form(...),
    full_name: str = Form(...),
    email: str = Form(...),
    role: str = Form(...),
    current_user_id: str = Cookie(None)
):
    current_user = get_user_with_role(current_user_id)
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE users
        SET full_name = %s, email = %s, role = %s
        WHERE id = %s
    """, (full_name, email, role, user_id_form))
    conn.commit()
    cur.close()
    conn.close()

    return RedirectResponse(url="/admin/users", status_code=303)

# POST: Delete user
@app.post("/admin/users/delete", response_class=HTMLResponse)
def delete_user(
    user_id_form: int = Form(...),
    current_user_id: str = Cookie(None)
):
    current_user = get_user_with_role(current_user_id)
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id = %s", (user_id_form,))
    conn.commit()
    cur.close()
    conn.close()
    return RedirectResponse(url="/admin/users", status_code=303)

