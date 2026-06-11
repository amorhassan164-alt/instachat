
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request, "page": "campaigns"})


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request, "page": "campaigns"})


@router.get("/settings", response_class=HTMLResponse)
async def settings(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request, "page": "settings"})
