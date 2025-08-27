<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"/>
</head>
<body class="bg-light text-dark">

<div class="container py-5">

  <h1 class="mb-4">📚 Library Management System – FastAPI</h1>

  <p>A web-based Library Management System built using <strong>FastAPI</strong>, <strong>Jinja2</strong>, and <strong>PostgreSQL</strong>.</p>

  <ul>
    <li><strong>Admin</strong> – manage books and users</li>
    <li><strong>User</strong> – issue/return books, view profile</li>
  </ul>

  <hr/>

  <h3>🚀 Features</h3>
  <ul>
    <li>🔐 User registration & login (hashed passwords)</li>
    <li>👥 Role-based access control (<code>admin</code>, <code>user</code>)</li>
    <li>📚 Manage books (CRUD for admin, issue/return for users)</li>
    <li>🧾 View issued books</li>
    <li>🙋‍♂️ Profile view & update</li>
    <li>🍪 Cookie-based session handling</li>
    <li>🎨 HTML templates using Jinja2 + Bootstrap</li>
  </ul>

  <h3>🛠️ Tech Stack</h3>
  <ul>
    <li><strong>Backend:</strong> FastAPI</li>
    <li><strong>Frontend:</strong> HTML (Jinja2 templates), Bootstrap</li>
    <li><strong>Database:</strong> PostgreSQL</li>
    <li><strong>Driver:</strong> psycopg2</li>
    <li><strong>Authentication:</strong> OAuth2 + Cookies</li>
  </ul>

  <h3>🗂️ Project Structure</h3>
  <pre><code>.
├── main.py
├── templates/
│   ├── login.html
│   ├── register.html
│   ├── homepage.html
│   ├── navbar.html
│   ├── profile.html
│   ├── admin.html
│   ├── books/
│   │   ├── manage_books.html
│   │   ├── add_book.html
│   │   └── edit_book.html
│   └── users/
│       ├── manage_users.html
│       └── edit_user.html
├── static/
├── requirements.txt
└── README.md
  </code></pre>

  <h3>🧑‍💻 Setup Instructions</h3>

  <h5>1. Clone the repo</h5>
  <pre><code>git clone https://github.com/your-username/library-management-fastapi.git
cd library-management-fastapi</code></pre>

  <h5>2. Create & activate virtual environment</h5>
  <pre><code>python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows</code></pre>

  <h5>3. Install dependencies</h5>
  <pre><code>pip install -r requirements.txt</code></pre>

  <h5>4. Setup PostgreSQL database</h5>
  <pre><code>CREATE DATABASE library_db;

-- users table
CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  username VARCHAR(100) UNIQUE NOT NULL,
  hashed_password TEXT NOT NULL,
  full_name VARCHAR(255),
  email VARCHAR(255) UNIQUE,
  role VARCHAR(10) DEFAULT 'user'
);

-- books table
CREATE TABLE books (
  id SERIAL PRIMARY KEY,
  title TEXT NOT NULL,
  author TEXT NOT NULL,
  published_year INTEGER,
  copies_available INTEGER DEFAULT 1
);

-- issued_books table
CREATE TABLE issued_books (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id),
  book_id INTEGER REFERENCES books(id),
  issue_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  return_date TIMESTAMP
);</code></pre>

  <h5>5. Update DB credentials</h5>
  <p>In <code>main.py</code>:</p>
  <pre><code>conn = psycopg2.connect(
    host="localhost",
    database="library_db",
    user="your_db_user",
    password="your_db_password",
    cursor_factory=RealDictCursor
)</code></pre>

  <h5>6. Run the application</h5>
  <pre><code>uvicorn main:app --reload</code></pre>

  <p>Visit <a href="http://localhost:8000" target="_blank">http://localhost:8000</a></p>

  <h3>🧪 Test User Roles</h3>
  <ul>
    <li><strong>Admin</strong>: Can access <code>/admin</code>, manage books and users</li>
    <li><strong>User</strong>: Can issue/return books and manage profile</li>
  </ul>

  <h3>📌 Notes</h3>
  <ul>
    <li>Passwords are securely hashed using <code>bcrypt</code></li>
    <li>Session is managed via HTTP cookies</li>
    <li>Admin routes are protected via role checks</li>
  </ul>

  <h3>📃 License</h3>
  <p>This project is for educational purposes. Feel free to customize it for your needs.</p>
</div>

</body>
</html>
