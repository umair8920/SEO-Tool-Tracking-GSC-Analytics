import logging
from datetime import datetime
from bson import ObjectId

import google.oauth2.credentials
from googleapiclient.discovery import build

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.templating import Jinja2Templates
from routes.flash import flash, get_flashed_messages

from db_client import client

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="templates")

API_SERVICE_NAME = 'webmasters'
API_VERSION = 'v3'

@router.get("/properties", name="dashboard_sites_list", response_class=HTMLResponse)
def sites_list(request: Request):
    """
    Renders the local domain properties after syncing from Google Search Console.
    """
    # Ensure session is available
    if not hasattr(request.state, 'session'):
        logger.error("Session not initialized in request.state")
        flash(request, "Session not available.", "danger")
        raise HTTPException(status_code=500, detail="Session not available")

    # Check required session data
    if 'credentials' not in request.state.session or 'user_id' not in request.state.session:
        flash(request, "Authentication required. Please log in.", "warning")
        return RedirectResponse(url=request.url_for("auth_authorize"))

    try:
        creds_dict = request.state.session['credentials']
        # Convert expiry from ISO string to datetime, if needed
        if 'expiry' in creds_dict and isinstance(creds_dict['expiry'], str):
            creds_dict['expiry'] = datetime.fromisoformat(creds_dict['expiry'])
        creds = google.oauth2.credentials.Credentials(**creds_dict)
    except Exception as e:
        logger.error("Error processing credentials from session: %s", e, exc_info=True)
        flash(request, "Error processing credentials.", "danger")
        raise HTTPException(status_code=500, detail="Error processing credentials.")

    try:
        service = build(API_SERVICE_NAME, API_VERSION, credentials=creds, cache_discovery=False)
    except Exception as e:
        logger.error("Error building Google service: %s", e, exc_info=True)
        flash(request, "Error connecting to Google Search Console.", "danger")
        raise HTTPException(status_code=502, detail="Error connecting to Google service.")

    try:
        # 1. Fetch the list of sites from GSC
        response = service.sites().list().execute()
        site_entries = response.get('siteEntry', [])
    except Exception as e:
        logger.error("Error fetching site list from Google: %s", e, exc_info=True)
        flash(request, "Error fetching site list from Google.", "danger")
        raise HTTPException(status_code=502, detail="Error fetching site list from Google.")

    # 2. Build a set of siteUrls from GSC
    gsc_site_urls = {site.get('siteUrl') for site in site_entries if site.get('siteUrl')}

    # 3. Fetch local domain data from the database
    user_id = request.state.session["user_id"]
    db = client["apimio"]
    domain_coll = db["domain_properties"]
    try:
        local_domains = list(domain_coll.find({"userId": ObjectId(user_id)}))
        local_site_urls = {doc.get("siteUrl") for doc in local_domains if doc.get("siteUrl")}
    except Exception as e:
        logger.error("Error fetching local domains: %s", e, exc_info=True)
        flash(request, "Error accessing local domain properties.", "danger")
        raise HTTPException(status_code=500, detail="Error accessing local domain properties.")

    now = datetime.utcnow()
    # 4. Upsert each site from GSC with active=True
    for site in site_entries:
        site_url = site.get('siteUrl')
        if not site_url:
            continue
        perm_level = site.get('permissionLevel', 'N/A')
        try:
            domain_coll.update_one(
                {"userId": ObjectId(user_id), "siteUrl": site_url},
                {
                    "$set": {
                        "updatedAt": now,
                        "active": True,
                        "permissionLevel": perm_level
                    },
                    "$setOnInsert": {"createdAt": now}
                },
                upsert=True
            )
        except Exception as e:
            logger.error("Error upserting site %s: %s", site_url, e, exc_info=True)

    # 5. Mark removed sites as inactive
    removed_sites = local_site_urls - gsc_site_urls
    if removed_sites:
        try:
            domain_coll.update_many(
                {"userId": ObjectId(user_id), "siteUrl": {"$in": list(removed_sites)}},
                {"$set": {"active": False, "updatedAt": now, "permissionLevel": "N/A"}}
            )
        except Exception as e:
            logger.error("Error marking removed sites as inactive: %s", e, exc_info=True)

    # 6. Re-fetch updated local domains
    try:
        local_domains = list(domain_coll.find({"userId": ObjectId(user_id)}))
    except Exception as e:
        logger.error("Error re-fetching local domains: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error re-accessing local domain properties.")

    # 7. Render the template with the local domains
    try:
        return templates.TemplateResponse("sites.html", {
            "request": request,
            "local_domains": local_domains,
            "flash_messages": get_flashed_messages(request)
        })
    except Exception as e:
        logger.error("Error rendering template: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error rendering page.")

@router.post("/properties/select", name="dashboard_select_site")
def select_site(request: Request, site_url: str = Form(...)):
    """
    Stores the selected site in the session and updates the domain properties in the database.
    """
    if not hasattr(request.state, 'session'):
        logger.error("Session not initialized in request.state")
        flash(request, "Session not available.", "danger")
        raise HTTPException(status_code=500, detail="Session not available")

    chosen_site = site_url
    if not chosen_site:
        flash(request, "Please select a site.", "warning")
        return RedirectResponse(url=request.url_for("dashboard_sites_list"))

    try:
        request.state.session['selected_site'] = chosen_site
        flash(request, f"Site {chosen_site} selected successfully!", "success")
    except Exception as e:
        logger.error("Error storing selected site in session: %s", e, exc_info=True)
        flash(request, "Error storing selected site.", "danger")
        raise HTTPException(status_code=500, detail="Error storing selected site.")

    logger.info("User selected site: %s", chosen_site)
    user_id = request.state.session.get("user_id")
    if user_id:
        db = client["apimio"]
        domain_coll = db["domain_properties"]
        now = datetime.utcnow()
        try:
            domain_coll.update_one(
                {"userId": ObjectId(user_id), "siteUrl": chosen_site},
                {
                    "$set": {"updatedAt": now, "active": True},
                    "$setOnInsert": {"userId": ObjectId(user_id), "siteUrl": chosen_site, "createdAt": now}
                },
                upsert=True
            )
        except Exception as e:
            logger.error("Error updating domain for site %s: %s", chosen_site, e, exc_info=True)
            flash(request, "Error updating domain information.", "danger")
            raise HTTPException(status_code=500, detail="Error updating domain information.")
    else:
        logger.warning("No user_id in session; cannot update domain in database.")

    # Redirect to the clusters list page
    try:
        return RedirectResponse(url=request.url_for("clusters_list_clusters"), status_code=303)
    except Exception as e:
        logger.error("Error during redirection: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error during redirection.")
