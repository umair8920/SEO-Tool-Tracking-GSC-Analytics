from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging

logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory="templates")

def register_global_exception_handlers(app: FastAPI):
    @app.exception_handler(StarletteHTTPException)
    async def global_http_exception_handler(request: Request, exc: StarletteHTTPException):
        # Log the exception details for internal diagnostics.
        logger.error("HTTPException occurred: %s", exc.detail, exc_info=True)
        
        # Check the Accept header for HTML response preference.
        accept_header = request.headers.get("accept", "")
        if "text/html" in accept_header:
            # Render a friendly HTML error page.
            return templates.TemplateResponse(
                "error.html",
                {
                    "request": request,
                    "message": "Oops! Something went wrong.",
                    "status_code": exc.status_code,
                    # You can choose to hide exc.detail if needed.
                    "detail": exc.detail  
                },
                status_code=exc.status_code
            )
        else:
            # Return a JSON response for API clients.
            return JSONResponse(
                status_code=exc.status_code,
                content={"message": "An error occurred.", "detail": exc.detail}
            )
