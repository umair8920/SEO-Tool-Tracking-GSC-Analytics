import os
import logging
import uvicorn
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

# Routes Import
from routes.main import router as main_router
from routes.auth import router as auth_router
from routes.dashboard import router as dashboard_router
from routes.clusters import router as clusters_router
from routes.global_exception_handler import register_global_exception_handlers

# Import the custom Mongo-based session middleware
from mongo_session import MongoSessionMiddleware

# Import your db_client if needed
from db_client import client

# Import the flash helpers
from routes.flash import flash, get_flashed_messages

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)
logger.info("Starting FastAPI with Mongo session...")

# Determine environment: 'development' or 'production'
ENV = os.getenv("ENV", "development")

# Configure OAuth transport security based on environment.
if ENV == "development":
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
else:
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '0'  # Ensure secure transport in production.

# Create FastAPI app instance with custom title and docs URLs.
app = FastAPI(
    title="Apimio Google Console Tracker",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Register the global exception handlers
register_global_exception_handlers(app)

# Custom middleware to override the scheme based on the X-Forwarded-Proto header.
class CustomHTTPSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # If X-Forwarded-Proto header is present, update the request scope scheme.
        forwarded_proto = request.headers.get("X-Forwarded-Proto")
        if forwarded_proto:
            request.scope["scheme"] = forwarded_proto
        response = await call_next(request)
        return response

# Add the custom HTTPS middleware
app.add_middleware(CustomHTTPSMiddleware)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Configure Jinja2 templates (point to your actual templates directory)
templates = Jinja2Templates(directory="templates")

# Add custom Mongo-based session middleware
app.add_middleware(MongoSessionMiddleware)

def render_template(request: Request, template_name: str, context: dict = {}):
    """
    Helper function to render templates.
    It automatically injects flash messages from the session into the context.
    """
    context.update({
        "request": request,
        "flash_messages": get_flashed_messages(request)  # Inject flash messages
    })
    return templates.TemplateResponse(template_name, context)

# Include routers
app.include_router(main_router, prefix="")
app.include_router(auth_router, prefix="/auth")
app.include_router(dashboard_router, prefix="/dashboard")
app.include_router(clusters_router)

# Add a simple health-check endpoint
@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}

# Serve the favicon
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("static/favicon.ico")

@app.get("/check_headers")
async def check_headers(request: Request):
    proto = request.headers.get("X-Forwarded-Proto")
    # Log the header value for debugging purposes.
    print("X-Forwarded-Proto header:", proto)
    return {
        "X-Forwarded-Proto": proto,
        "generated_callback_url": request.url_for("auth_oauth2callback")
    }

# Run uvicorn programmatically with proxy headers enabled
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        reload=(ENV == "development"),
        proxy_headers=True,
        forwarded_allow_ips="*"
    )
