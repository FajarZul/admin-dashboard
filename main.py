from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from supabase import acreate_client, AsyncClient
from pathlib import Path
import os
import secrets

app = FastAPI(title="Admin Dashboard", version="1.0")

# Path absolut untuk templates
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Koneksi Supabase
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise Exception(f"Missing vars - URL:{bool(SUPABASE_URL)} KEY:{bool(SUPABASE_SERVICE_KEY)}")

# Admin credentials
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

# Security
security = HTTPBasic()

# Supabase client (lazy init, dibuat per request)
async def get_supabase() -> AsyncClient:
    return await acreate_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

def verify_admin(credentials: HTTPBasicCredentials = Depends(security)):
    """Verifikasi username & password admin"""
    is_correct = secrets.compare_digest(credentials.username, ADMIN_USERNAME)
    is_correct_pass = secrets.compare_digest(credentials.password, ADMIN_PASSWORD)
    if not (is_correct and is_correct_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# ========== ROUTES ==========

@app.get("/", response_class=HTMLResponse)
async def root():
    return RedirectResponse(url="/dashboard")

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, username: str = Depends(verify_admin)):
    sb = await get_supabase()
    users = await sb.table("users").select("*").execute()
    sites = await sb.table("sites").select("*, users(email)").execute()

    total_users = len(users.data)
    total_sites = len(sites.data)
    active_sites = sum(1 for site in sites.data if site.get("site_token"))
    pending_sites = total_sites - active_sites

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "total_users": total_users,
        "total_sites": total_sites,
        "active_sites": active_sites,
        "pending_sites": pending_sites,
        "recent_users": users.data[:5],
        "recent_sites": sites.data[:5]
    })

@app.get("/users", response_class=HTMLResponse)
async def list_users(request: Request, username: str = Depends(verify_admin)):
    sb = await get_supabase()
    users = await sb.table("users").select("*").order("created_at", desc=True).execute()

    for user in users.data:
        sites = await sb.table("sites").select("*").eq("user_id", user["id"]).execute()
        user["site_count"] = len(sites.data)

    return templates.TemplateResponse("users.html", {
        "request": request,
        "users": users.data
    })

@app.get("/user/{user_id}", response_class=HTMLResponse)
async def user_detail(request: Request, user_id: str, username: str = Depends(verify_admin)):
    sb = await get_supabase()
    user = await sb.table("users").select("*").eq("id", user_id).execute()
    if not user.data:
        raise HTTPException(404, "User not found")

    sites = await sb.table("sites").select("*").eq("user_id", user_id).execute()

    return templates.TemplateResponse("user_detail.html", {
        "request": request,
        "user": user.data[0],
        "sites": sites.data
    })

@app.get("/sites", response_class=HTMLResponse)
async def list_sites(request: Request, username: str = Depends(verify_admin)):
    sb = await get_supabase()
    sites = await sb.table("sites").select("*, users(email)").order("created_at", desc=True).execute()

    return templates.TemplateResponse("sites.html", {
        "request": request,
        "sites": sites.data
    })

@app.get("/health")
async def health():
    return {"status": "healthy"}