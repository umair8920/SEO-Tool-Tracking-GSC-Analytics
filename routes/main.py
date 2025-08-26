import logging
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from starlette.templating import Jinja2Templates
from routes.flash import flash, get_flashed_messages

router = APIRouter()
logger = logging.getLogger(__name__)

templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    logger.info("Rendering index page from main route")
    try:
        # Renders index.html using the 'templates' object
        return templates.TemplateResponse(
    "index.html", 
    {"request": request, "flash_messages": get_flashed_messages(request)}
)

    except Exception as e:
        logger.error("Error rendering index page: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="An error occurred while rendering the page")
