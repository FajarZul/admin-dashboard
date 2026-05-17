from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pathlib import Path
from dotenv import load_dotenv
import os
import secrets
import httpx

load_dotenv()

app = FastAPI(title="Admin Dashboard", version="1.0")

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")  # DIPERBAIKI
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

security = HTTPBasic()

def get_headers():
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json"
    }

async def query(table: str, params: str = ""):
    url = f"{SUPABASE_URL}/rest/v1/{table}{params}"
    async with httpx.AsyncClient() as client:
        r = await client.get(url, headers=get_headers())
        r.raise_for_status()
        return r.json()

def verify_admin(credentials: HTTPBasicCredentials = Depends(security)):
    is_correct = secrets.compare_digest(credentials.username, ADMIN_USERNAME)
    is_correct_pass = secrets.compare_digest(credentials.password, ADMIN_PASSWORD)
    if not (is_correct and is_correct_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

@app.get("/", response_class=HTMLResponse)
async def root():
    return RedirectResponse(url="/dashboard")

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, username: str = Depends(verify_admin)):
    users = await query("users", "?select=*")
    sites = await query("sites", "?select=*,users(email)")
    total_users = len(users)
    total_sites = len(sites)
    active_sites = sum(1 for s in sites if s.get("site_token"))
    pending_sites = total_sites - active_sites
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "total_users": total_users,
        "total_sites": total_sites,
        "active_sites": active_sites,
        "pending_sites": pending_sites,
        "recent_users": users[:5],
        "recent_sites": sites[:5]
    })

@app.get("/users", response_class=HTMLResponse)
async def list_users(request: Request, username: str = Depends(verify_admin)):
    users = await query("users", "?select=*&order=created_at.desc")
    for user in users:
        sites = await query("sites", f"?select=*&user_id=eq.{user['id']}")
        user["site_count"] = len(sites)
    return templates.TemplateResponse("users.html", {
        "request": request,
        "users": users
    })

@app.get("/user/{user_id}", response_class=HTMLResponse)
async def user_detail(request: Request, user_id: str, username: str = Depends(verify_admin)):
    users = await query("users", f"?select=*&id=eq.{user_id}")
    if not users:
        raise HTTPException(404, "User not found")
    sites = await query("sites", f"?select=*&user_id=eq.{user_id}")
    return templates.TemplateResponse("user_detail.html", {
        "request": request,
        "user": users[0],
        "sites": sites
    })

@app.get("/sites", response_class=HTMLResponse)
async def list_sites(request: Request, username: str = Depends(verify_admin)):
    sites = await query("sites", "?select=*,users(email)&order=created_at.desc")
    return templates.TemplateResponse("sites.html", {
        "request": request,
        "sites": sites
    })

@app.get("/health")
async def health():
    return {"status": "healthy"}