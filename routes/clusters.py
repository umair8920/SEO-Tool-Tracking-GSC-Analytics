# routes/clusters.py

import logging
from datetime import datetime, timedelta, date
from bson.objectid import ObjectId
from urllib.parse import urlparse

import pymongo
import google.oauth2.credentials
from googleapiclient.discovery import build

from pydantic import BaseModel
from typing import List, Optional

from fastapi import APIRouter, Request, Form, Query, status, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from starlette.templating import Jinja2Templates
from routes.flash import flash, get_flashed_messages



from db_client import client

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def check_domain_consistency(cluster_domain: str, link_url: str) -> bool:
    """
    Ensures link_url belongs to cluster_domain.
    For 'sc-domain:apimio.com', it checks if the netloc ends with 'apimio.com'.
    For a URL prefix like 'https://apimio.com/', it compares the scheme and netloc.
    Returns False if any errors occur or if the URLs are improperly formatted.
    """
    if not cluster_domain or not link_url:
        logger.error("Missing cluster_domain or link_url: cluster_domain=%s, link_url=%s", cluster_domain, link_url)
        return False

    try:
        parsed_link = urlparse(link_url)
    except Exception as e:
        logger.error("Error parsing link_url '%s': %s", link_url, e, exc_info=True)
        return False

    if not parsed_link.scheme or not parsed_link.netloc:
        logger.error("Invalid link_url format: %s", link_url)
        return False

    if cluster_domain.startswith("sc-domain:"):
        # Handle domain shorthand, e.g. "sc-domain:apimio.com"
        domain_part = cluster_domain.replace("sc-domain:", "", 1)
        if not domain_part:
            logger.error("Empty domain part in cluster_domain: %s", cluster_domain)
            return False
        return parsed_link.netloc.endswith(domain_part)
    else:
        # Assume cluster_domain is a full URL prefix.
        try:
            parsed_cluster = urlparse(cluster_domain)
        except Exception as e:
            logger.error("Error parsing cluster_domain '%s': %s", cluster_domain, e, exc_info=True)
            return False

        if not parsed_cluster.scheme or not parsed_cluster.netloc:
            logger.error("Invalid cluster_domain format: %s", cluster_domain)
            return False

        same_scheme = (parsed_link.scheme == parsed_cluster.scheme)
        same_host = (parsed_link.netloc == parsed_cluster.netloc)
        return same_scheme and same_host



# -----------------------------------------
# (Cluster routes started here)
# -----------------------------------------
class ClusterCreate(BaseModel):
    clusterName: str
    deviceFilter: Optional[str] = "ALL"
    countryFilter: Optional[str] = "ALL"


class ClustersPayload(BaseModel):
    clusters: List[ClusterCreate]


@router.get("/clusters", response_class=HTMLResponse, name="clusters_list_clusters")
def list_clusters(request: Request):
    """
    Lists all active clusters (deleted=False) for the selected domain.
    """
    if not hasattr(request.state, 'session'):
        logger.error("Session not initialized in request.state")
        raise HTTPException(status_code=500, detail="Session not available")
    if "user_id" not in request.state.session or "selected_site" not in request.state.session:
        flash(request, "Session expired or invalid. Please log in again.", "warning") 
        return RedirectResponse(url=request.url_for("auth_authorize"))
    
    try:
        user_id = request.state.session["user_id"]
        domain = request.state.session["selected_site"]
        db = client["apimio"]
        cluster_docs = list(db.clusters.find({
            "userId": ObjectId(user_id),
            "domain": domain,
            "deleted": False
        }))
    except Exception as e:
        logger.error("Error retrieving clusters: %s", e, exc_info=True)
        flash(request, "Unable to retrieve clusters. Please try again later.", "danger")
        raise HTTPException(status_code=500, detail="Error retrieving clusters.")
    
    try:
        return templates.TemplateResponse("Dashboard/CLusters/list.html", {
            "request": request,
            "clusters": cluster_docs,
            "domain": domain,
            "flash_messages": get_flashed_messages(request)
        })
    except Exception as e:
        logger.error("Error rendering clusters template: %s", e, exc_info=True)
        flash(request, "An unexpected error occurred while loading the page.", "danger")
        raise HTTPException(status_code=500, detail="Error rendering page.")


@router.get("/clusters/new", response_class=HTMLResponse, name="clusters_new_form")
def new_cluster_form(request: Request):
    """
    Renders a form to add new clusters.
    """
    if not hasattr(request.state, 'session'):
        logger.error("Session not available")
        flash(request, "Session not available. Please try again later.", "danger")
        raise HTTPException(status_code=500, detail="Session not available")
    if "user_id" not in request.state.session or "selected_site" not in request.state.session:
        flash(request, "Your session has expired. Please log in again.", "warning")
        return RedirectResponse(url=request.url_for("auth_authorize"))
    
    try:
        domain = request.state.session["selected_site"]
        return templates.TemplateResponse("Dashboard/CLusters/new.html", {
            "request": request,
            "domain": domain,
            "flash_messages": get_flashed_messages(request)
        })
    except Exception as e:
        logger.error("Error rendering new cluster form: %s", e, exc_info=True)
        flash(request, "An error occurred while loading the form. Please try again.", "danger")
        raise HTTPException(status_code=500, detail="Error rendering new cluster form.")



@router.post("/clusters/new-json", name="clusters_new_json")
def new_cluster_json_action(
    request: Request,
    payload: ClustersPayload  # <--- Pydantic model for JSON body
):
    """
    POST /clusters/new-json
    Expects JSON:
    {
      "clusters": [
        {
          "clusterName": "MyCluster",
          "deviceFilter": "MOBILE",
          "countryFilter": "usa,can"
        },
        {
          "clusterName": "AnotherCluster"
        }
      ]
    }
    """
    # 1. Validate session presence
    if "user_id" not in request.state.session or "selected_site" not in request.state.session:
        # If not authenticated or no domain selected, redirect or return error
        return RedirectResponse(url=request.url_for("auth_authorize"))

    user_id = request.state.session["user_id"]
    domain = request.state.session["selected_site"]

    # 2. Setup database reference
    try:
        db = client["apimio"]  # your MongoDB reference
    except Exception as e:
        # Log the error as needed
        return JSONResponse(
            status_code=500,
            content={"detail": "Database connection failed."}
        )

    now = datetime.utcnow()
    created_count = 0

    # 3. Process clusters from payload
    for cluster_data in payload.clusters:
        name_stripped = cluster_data.clusterName.strip()
        if not name_stripped:
            # Skip if clusterName is empty after stripping
            continue

        # Use default values if not provided
        device_filter = cluster_data.deviceFilter or "ALL"
        country_filter = cluster_data.countryFilter or "ALL"

        try:
            # 4. Check for duplicate clusters
            existing = db.clusters.find_one({
                "userId": ObjectId(user_id),
                "domain": domain,
                "clusterName": name_stripped
            })
        except Exception as e:
            # Log the error as needed
            return JSONResponse(
                status_code=500,
                content={"detail": "Error checking existing clusters."}
            )

        if existing:
            if existing.get("deleted"):
                return JSONResponse(
                    status_code=400,
                    content={
                        "detail": f"Cluster '{name_stripped}' is in trash. "
                                  "Please restore or choose a different name."
                    }
                )
            else:
                return JSONResponse(
                    status_code=400,
                    content={
                        "detail": f"Cluster '{name_stripped}' already exists for domain '{domain}'."
                    }
                )

        try:
            # 5. Insert the new cluster document
            db.clusters.insert_one({
                "userId": ObjectId(user_id),
                "domain": domain,
                "clusterName": name_stripped,
                "deviceFilter": device_filter,
                "countryFilter": country_filter,
                "deleted": False,
                "deletedAt": None,
                "createdAt": now,
                "updatedAt": now
            })
            created_count += 1
        except Exception as e:
            # Log the error as needed, continue processing other clusters if desired
            # Alternatively, you might choose to abort and rollback if partial success is not allowed.
            return JSONResponse(
                status_code=500,
                content={"detail": f"Error inserting cluster '{name_stripped}'."}
            )

    # 6. Handle case where no valid clusters were inserted
    if created_count == 0:
        return JSONResponse(
            status_code=400,
            content={"detail": "All cluster names were empty or invalid."}
        )

    # 7. Return success response
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={"detail": f"Created {created_count} cluster(s)."}
    )


@router.get("/clusters/{cluster_id}", response_class=HTMLResponse, name="clusters_show_cluster")
def show_cluster(request: Request, cluster_id: str):
    """
    Shows details of a single cluster (if not deleted) and its associated non-deleted links.
    """
    if not hasattr(request.state, 'session'):
        logger.error("Session not available")
        flash(request, "Session not available. Please try again later.", "danger")
        raise HTTPException(status_code=500, detail="Session not available")
    if "user_id" not in request.state.session:
        flash(request, "Your session has expired. Please log in again.", "warning")
        return RedirectResponse(url=request.url_for("auth_authorize"))
    
    try:
        db = client["apimio"]
        cluster = db.clusters.find_one({"_id": ObjectId(cluster_id), "deleted": False})
        if not cluster:
            flash(request, "The requested cluster was not found or has been deleted.", "danger")
            raise HTTPException(status_code=404, detail="Cluster not found or deleted.")
    except Exception as e:
        logger.error("Error retrieving cluster: %s", e, exc_info=True)
        flash(request, "There was an error retrieving cluster details. Please try again.", "danger")
        raise HTTPException(status_code=500, detail="Error retrieving cluster.")

    try:
        # Fetch non-deleted links for the cluster
        link_docs = list(db.links.find({
            "clusterId": cluster["_id"],
            "deleted": False
        }))
    except Exception as e:
        logger.error("Error retrieving links: %s", e, exc_info=True)
        flash(request, "There was an error retrieving associated links. Please try again.", "danger")
        raise HTTPException(status_code=500, detail="Error retrieving cluster links.")

    try:
        return templates.TemplateResponse("Dashboard/CLusters/detail.html", {
            "request": request,
            "cluster": cluster,
            "links": link_docs,
            "flash_messages": get_flashed_messages(request)
        })
    except Exception as e:
        logger.error("Error rendering cluster detail template: %s", e, exc_info=True)
        flash(request, "An unexpected error occurred while displaying the cluster details.", "danger")
        raise HTTPException(status_code=500, detail="Error rendering cluster detail page.")


@router.get("/clusters/{cluster_id}/edit", response_class=HTMLResponse, name="clusters_edit_cluster_form")
def edit_cluster_form(request: Request, cluster_id: str):
    """
    Renders the edit form for a cluster.
    """
    if not hasattr(request.state, 'session'):
        logger.error("Session not available")
        flash(request, "Session not available. Please try again later.", "danger")
        raise HTTPException(status_code=500, detail="Session not available")
    if "user_id" not in request.state.session:
        flash(request, "Your session has expired. Please log in again.", "warning")
        return RedirectResponse(url=request.url_for("auth_authorize"))
    
    try:
        db = client["apimio"]
        cluster = db.clusters.find_one({"_id": ObjectId(cluster_id)})
        if not cluster:
            flash(request, "The requested cluster was not found.", "danger")
            raise HTTPException(status_code=404, detail="Cluster not found")
        return templates.TemplateResponse("Dashboard/CLusters/edit.html", {
            "request": request,
            "cluster": cluster,
            "flash_messages": get_flashed_messages(request)
        })
    except Exception as e:
        logger.error("Error rendering edit cluster form: %s", e, exc_info=True)
        flash(request, "There was an error retrieving cluster details. Please try again.", "danger")
        raise HTTPException(status_code=500, detail="Error rendering edit cluster form.")


@router.post("/clusters/{cluster_id}/edit", name="clusters_edit_cluster_post")
def edit_cluster_action(
    request: Request,
    cluster_id: str,
    clusterName: str = Form(...),
    deviceFilter: str = Form("ALL"),
    countryFilter: str = Form("ALL")
):
    """
    Updates a cluster's details ensuring no duplicate names exist.
    """
    if not hasattr(request.state, 'session'):
        logger.error("Session not available")
        flash(request, "Session not available. Please try again later.", "danger")
        raise HTTPException(status_code=500, detail="Session not available")
    if "user_id" not in request.state.session:
        flash(request, "Your session has expired. Please log in again.", "warning")
        return RedirectResponse(url=request.url_for("auth_authorize"))
    
    try:
        db = client["apimio"]
        cluster = db.clusters.find_one({"_id": ObjectId(cluster_id)})
        if not cluster:
            flash(request, "The requested cluster was not found.", "danger")
            raise HTTPException(status_code=404, detail="Cluster not found")
    except Exception as e:
        logger.error("Error retrieving cluster for edit: %s", e, exc_info=True)
        flash(request, "Error retrieving cluster. Please try again later.", "danger")
        raise HTTPException(status_code=500, detail="Error retrieving cluster.")
    
    new_name = clusterName.strip()
    new_device = deviceFilter.strip() or "ALL"
    new_country = countryFilter.strip() or "ALL"

    if not new_name:
        flash(request, "Cluster name cannot be empty.", "danger")
        raise HTTPException(status_code=400, detail="Cluster name cannot be empty.")

    try:
        # Check for uniqueness of cluster name for the same user and domain.
        existing = db.clusters.find_one({
            "userId": cluster["userId"],
            "domain": cluster["domain"],
            "clusterName": new_name,
            "_id": {"$ne": cluster["_id"]}
        })
        if existing:
            flash(request, f"A cluster named '{new_name}' already exists for this domain.", "danger")
            raise HTTPException(status_code=400, detail=f"A cluster named '{new_name}' already exists for this domain.")
    except Exception as e:
        logger.error("Error checking cluster uniqueness: %s", e, exc_info=True)
        flash(request, "Error checking cluster uniqueness. Please try again.", "danger")
        raise HTTPException(status_code=500, detail="Error checking cluster uniqueness.")

    try:
        now = datetime.utcnow()
        db.clusters.update_one(
            {"_id": cluster["_id"]},
            {"$set": {
                "clusterName": new_name,
                "deviceFilter": new_device,
                "countryFilter": new_country,
                "updatedAt": now
            }}
        )
        flash(request, "Cluster updated successfully!", "success")
    except Exception as e:
        logger.error("Error updating cluster: %s", e, exc_info=True)
        flash(request, "There was an error updating the cluster. Please try again.", "danger")
        raise HTTPException(status_code=500, detail="Error updating cluster.")
    
    try:
        return RedirectResponse(url=request.url_for("clusters_show_cluster", cluster_id=cluster_id), status_code=303)
    except Exception as e:
        logger.error("Error redirecting after cluster edit: %s", e, exc_info=True)
        flash(request, "Error redirecting after editing cluster.", "danger")
        raise HTTPException(status_code=500, detail="Error redirecting after editing cluster.")


@router.post("/clusters/{cluster_id}/delete", name="clusters_delete_cluster")
def delete_cluster(request: Request, cluster_id: str):
    """
    Soft-deletes a cluster and all its associated links and performance data.
    On success or error, a flash message is set and the user is redirected.
    """
    if not hasattr(request.state, 'session'):
        logger.error("Session not available")
        # Flash error and redirect
        flash(request, "Session not available", "error")
        return RedirectResponse(url=request.url_for("clusters_list_clusters"), status_code=303)
    
    if "user_id" not in request.state.session:
        return RedirectResponse(url=request.url_for("auth_authorize"))
    
    db = client["apimio"]
    
    try:
        cluster = db.clusters.find_one({"_id": ObjectId(cluster_id), "deleted": {"$ne": True}})
        if not cluster:
            flash(request, "Cluster not found or already trashed.", "error")
            return RedirectResponse(url=request.url_for("clusters_list_clusters"), status_code=303)
    except Exception as e:
        logger.error("Error retrieving cluster for deletion: %s", e, exc_info=True)
        flash(request, "Error retrieving cluster for deletion.", "error")
        return RedirectResponse(url=request.url_for("clusters_list_clusters"), status_code=303)
    
    now = datetime.utcnow()
    
    try:
        # Soft-delete the cluster
        db.clusters.update_one(
            {"_id": cluster["_id"]},
            {"$set": {"deleted": True, "deletedAt": now}}
        )
    except Exception as e:
        logger.error("Error marking cluster as trashed: %s", e, exc_info=True)
        flash(request, "Error deleting cluster.", "error")
        return RedirectResponse(url=request.url_for("clusters_list_clusters"), status_code=303)
    
    try:
        # Soft-delete all links under this cluster
        db.links.update_many(
            {"clusterId": cluster["_id"], "deleted": {"$ne": True}},
            {"$set": {"deleted": True, "deletedAt": now}}
        )
    except Exception as e:
        logger.error("Error deleting cluster links: %s", e, exc_info=True)
        flash(request, "Error deleting cluster links.", "error")
        return RedirectResponse(url=request.url_for("clusters_list_clusters"), status_code=303)
    
    try:
        # Soft-delete performance data for the links under this cluster
        link_ids = db.links.find({"clusterId": cluster["_id"]}).distinct("_id")
        db.link_performance.update_many(
            {"linkId": {"$in": link_ids}, "deleted": {"$ne": True}},
            {"$set": {"deleted": True, "deletedAt": now}}
        )
    except Exception as e:
        logger.error("Error deleting cluster performance data: %s", e, exc_info=True)
        flash(request, "Error deleting cluster performance data.", "error")
        return RedirectResponse(url=request.url_for("clusters_list_clusters"), status_code=303)
    
    # On successful deletion
    flash(request, "Cluster deleted successfully.", "success")
    
    try:
        return RedirectResponse(url=request.url_for("clusters_list_clusters"), status_code=303)
    except Exception as e:
        logger.error("Error redirecting after cluster deletion: %s", e, exc_info=True)
        flash(request, "Error redirecting after deletion.", "error")
        return RedirectResponse(url=request.url_for("clusters_list_clusters"), status_code=303)



# -----------------------------------------
# (Links routes started here)
# -----------------------------------------

class LinksPayload(BaseModel):
    links: List[str]

# Dependency for session and user validation
def validate_session(request: Request):
    if not hasattr(request.state, 'session'):
        logger.error("Session not available in request.state")
        raise HTTPException(status_code=500, detail="Session not available")
    if "user_id" not in request.state.session:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return request.state.session

@router.get("/clusters/{cluster_id}/links/add-json", response_class=HTMLResponse, name="clusters_add_links_form_json")
def add_links_form_json(request: Request, cluster_id: str):
    try:
        session = validate_session(request)
    except HTTPException as e:
        flash(request, "Your session has expired. Please log in again.", "warning")
        return RedirectResponse(url=request.url_for("auth_authorize"))

    # Check for Google OAuth credentials in session
    if "credentials" in request.state.session:
        flash(request, "Google OAuth credentials available.", "success")
    else:
        flash(request, "Google OAuth credentials not found. Please log in.", "danger")
        return RedirectResponse(url=request.url_for("auth_authorize"))

    try:
        db = client["apimio"]
        cluster = db.clusters.find_one({"_id": ObjectId(cluster_id), "deleted": False})
    except Exception as e:
        logger.error("Error retrieving cluster: %s", e, exc_info=True)
        flash(request, "Error retrieving cluster. Please try again later.", "danger")
        raise HTTPException(status_code=500, detail="Error retrieving cluster")
    if not cluster:
        flash(request, "The cluster you are trying to add links to does not exist or has been deleted.", "danger")
        raise HTTPException(status_code=404, detail="Cluster not found or deleted")
    try:
        return templates.TemplateResponse("Dashboard/Links/links_add.html", {
            "request": request,
            "cluster": cluster,
            "flash_messages": get_flashed_messages(request)
        })
    except Exception as e:
        logger.error("Error rendering add links template: %s", e, exc_info=True)
        flash(request, "There was an error loading the link creation page. Please try again.", "danger")
        raise HTTPException(status_code=500, detail="Error rendering template")

@router.post("/clusters/{cluster_id}/links/add-json", name="clusters_add_links_json")
def add_links_json_action(
    request: Request,
    cluster_id: str,
    payload: LinksPayload,
    background_tasks: BackgroundTasks,
):
    try:
        session = validate_session(request)
    except HTTPException:
        return RedirectResponse(url=request.url_for("auth_authorize"))

    try:
        db = client["apimio"]
        cluster = db.clusters.find_one({"_id": ObjectId(cluster_id), "deleted": False})
    except Exception as e:
        logger.error("Error retrieving cluster: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error retrieving cluster")
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found or deleted")
    
    if not payload.links:
        return JSONResponse(status_code=400, content={"detail": "No links provided."})
    
    domain = cluster["domain"]
    now = datetime.utcnow()
    created_links_count = 0
    errors = []

    for url in payload.links:
        url = url.strip()
        if not url:
            continue
        try:
            if not check_domain_consistency(domain, url):
                errors.append(f"Link '{url}' does not match domain '{domain}'.")
                continue
        except Exception as e:
            logger.error("Error checking domain consistency for URL '%s': %s", url, e, exc_info=True)
            errors.append(f"Invalid domain check for link '{url}'.")
            continue

        try:
            existing_link = db.links.find_one({
                "clusterId": cluster["_id"],
                "url": url,
                "deleted": {"$ne": True}
            })
        except Exception as e:
            logger.error("Error checking duplicate link '%s': %s", url, e, exc_info=True)
            errors.append(f"Error checking for duplicate link '{url}'.")
            continue

        if existing_link:
            errors.append(f"Link '{url}' already exists in this cluster.")
            continue

        try:
            # Insert the link with an initial status of "processing"
            result = db.links.insert_one({
                "clusterId": cluster["_id"],
                "url": url,
                "deleted": False,
                "deletedAt": None,
                "createdAt": now,
                "updatedAt": now,
                "status": "processing"
            })
            created_links_count += 1
            new_link_doc = db.links.find_one({"_id": result.inserted_id})
            background_tasks.add_task(fetch_3months_gsc_data_for_link, request, new_link_doc, cluster)
        except Exception as e:
            logger.error("Error inserting link '%s': %s", url, e, exc_info=True)
            errors.append(f"Error inserting link '{url}' into database.")
            continue

    response_content = {"detail": f"Added {created_links_count} link(s)."}
    if errors:
        response_content["errors"] = errors
        return JSONResponse(status_code=207, content=response_content)
    return JSONResponse(status_code=201, content=response_content)

def fetch_3months_gsc_data_for_link(request: Request, link_doc: dict, cluster_doc: dict):
    """
    Fetches the last 3 months of data from GSC for the given link,
    applying the device and country filters from cluster_doc.
    Aggregates the data by date and stores results in the link_performance collection.
    Updates the link's status accordingly.
    """
    if not hasattr(request.state, 'session'):
        logger.warning("Session not available; skipping GSC fetch.")
        flash(request, "Session not available; skipping GSC data fetch.", "warning")
        return
    if "credentials" not in request.state.session:
        logger.warning("No credentials in session; skipping GSC fetch.")
        flash(request, "Google Search Console credentials not found. Please reconnect.", "danger")
        client["apimio"].links.update_one(
            {"_id": link_doc["_id"]},
            {"$set": {"status": "error", "updatedAt": datetime.utcnow()}}
        )
        return
    try:
        db = client["apimio"]
        device_filter = cluster_doc.get("deviceFilter")
        country_filter_str = cluster_doc.get("countryFilter", "ALL")
        country_codes = [] if country_filter_str.upper() == "ALL" else [c.strip() for c in country_filter_str.split(",") if c.strip()]
        end_dt = date.today() - timedelta(days=3)
        start_dt = end_dt - timedelta(days=90)
        start_date_str = start_dt.isoformat()
        end_date_str = end_dt.isoformat()
        creds_dict = request.state.session["credentials"]

        # Check that all necessary fields for token refresh are available
        required_keys = ["refresh_token", "token_uri", "client_id", "client_secret"]
        if not all(key in creds_dict for key in required_keys):
            logger.error("Incomplete Google OAuth credentials: missing one of %s", required_keys)
            flash(request, "Incomplete Google OAuth credentials. Please log in again.", "danger")
            db.links.update_one(
                {"_id": link_doc["_id"]},
                {"$set": {"status": "error", "updatedAt": datetime.utcnow()}}
            )
            return

        creds = google.oauth2.credentials.Credentials(**creds_dict)
        service = build("webmasters", "v3", credentials=creds)
    except Exception as e:
        logger.error("Error initializing GSC fetch: %s", e, exc_info=True)
        flash(request, "Error initializing Google Search Console API. Try again later.", "danger")
        db.links.update_one(
            {"_id": link_doc["_id"]},
            {"$set": {"status": "error", "updatedAt": datetime.utcnow()}}
        )
        return

    def query_for_country(country_code=None):
        filters = [{
            "dimension": "page",
            "operator": "equals",
            "expression": link_doc["url"]
        }]
        if device_filter and device_filter.upper() != "ALL":
            filters.append({
                "dimension": "device",
                "operator": "equals",
                "expression": device_filter
            })
        if country_code:
            filters.append({
                "dimension": "country",
                "operator": "equals",
                "expression": country_code
            })
        request_body = {
            "startDate": start_date_str,
            "endDate": end_date_str,
            "dimensions": ["date"],
            "dimensionFilterGroups": [{
                "filters": filters
            }]
        }
        try:
            response = service.searchanalytics().query(
                siteUrl=cluster_doc["domain"],
                body=request_body
            ).execute()
        except Exception as e:
            logger.error("GSC query failed for link %s, country %s: %s", link_doc.get("_id"), country_code or "ALL", e, exc_info=True)
            flash(request, f"Failed to fetch GSC data for {link_doc.get('_id')}.", "danger")
            return []
        return response.get("rows", [])

    all_rows = []
    if not country_codes:
        all_rows = query_for_country(None)
    else:
        for code in country_codes:
            rows = query_for_country(code)
            if rows:
                all_rows.extend(rows)

    aggregated = {}
    for row in all_rows:
        date_val = row["keys"][0]
        clicks = row.get("clicks", 0)
        impressions = row.get("impressions", 0)
        position = row.get("position", 0)
        if date_val not in aggregated:
            aggregated[date_val] = {
                "clicks": 0,
                "impressions": 0,
                "weighted_position_sum": 0
            }
        aggregated[date_val]["clicks"] += clicks
        aggregated[date_val]["impressions"] += impressions
        aggregated[date_val]["weighted_position_sum"] += position * impressions

    now = datetime.utcnow()
    bulk_ops = []
    for date_val, data in aggregated.items():
        total_clicks = data["clicks"]
        total_impressions = data["impressions"]
        aggregated_ctr = total_clicks / total_impressions if total_impressions else 0
        aggregated_position = data["weighted_position_sum"] / total_impressions if total_impressions else 0
        bulk_ops.append(
            pymongo.UpdateOne(
                {"linkId": link_doc["_id"], "date": date_val},
                {
                    "$set": {
                        "clicks": total_clicks,
                        "impressions": total_impressions,
                        "ctr": aggregated_ctr,
                        "position": aggregated_position,
                        "updatedAt": now
                    },
                    "$setOnInsert": {"createdAt": now}
                },
                upsert=True
            )
        )
    if bulk_ops:
        try:
            db.link_performance.bulk_write(bulk_ops)
            logger.info("Aggregated and stored data for %d dates for link %s in cluster %s",
                        len(aggregated), link_doc.get("_id"), cluster_doc.get("_id"))
            flash(request, f"Successfully aggregated and stored data for {len(aggregated)} dates for link {link_doc.get('_id')} in cluster {cluster_doc.get('_id')}", "success")
            # Update link status to complete
            db.links.update_one(
                {"_id": link_doc["_id"]},
                {"$set": {"status": "complete", "updatedAt": datetime.utcnow()}}
            )
        except Exception as e:
            logger.error("Error writing aggregated data for link %s: %s", link_doc.get("_id"), e, exc_info=True)
            flash(request, "Failed to store fetched GSC data. Please try again later.", "danger")
            db.links.update_one(
                {"_id": link_doc["_id"]},
                {"$set": {"status": "error", "updatedAt": datetime.utcnow()}}
            )


@router.post("/clusters/{cluster_id}/links/{link_id}/refresh", name="clusters_refresh_link_gsc")
def refresh_link_gsc(request: Request, cluster_id: str, link_id: str, background_tasks: BackgroundTasks):
    try:
        # Validate session and user
        session = validate_session(request)
    except HTTPException:
        return RedirectResponse(url=request.url_for("auth_authorize"))

    try:
        db = client["apimio"]
        # Retrieve the cluster; ensure it exists and is not deleted.
        cluster = db.clusters.find_one({"_id": ObjectId(cluster_id), "deleted": False})
        if not cluster:
            raise HTTPException(status_code=404, detail="Cluster not found or deleted")
        # Retrieve the link; ensure it exists and is not marked as deleted.
        link_doc = db.links.find_one({"_id": ObjectId(link_id), "deleted": {"$ne": True}})
        if not link_doc:
            raise HTTPException(status_code=404, detail="Link not found or deleted")
    except Exception as e:
        logger.error("Error retrieving cluster or link: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error retrieving cluster or link")

    # Update the link's status to "processing" so the spinner can be displayed.
    db.links.update_one(
        {"_id": link_doc["_id"]},
        {"$set": {"status": "processing", "updatedAt": datetime.utcnow()}}
    )

    # Offload the GSC data fetch to a background task.
    background_tasks.add_task(fetch_3months_gsc_data_for_link, request, link_doc, cluster)

    flash(request, "GSC data refresh initiated.", "info")

    # Redirect to the cluster details page using 303 See Other
    return RedirectResponse(
        url=request.url_for("clusters_show_cluster", cluster_id=cluster_id),
        status_code=303
    )



@router.get("/links/{link_id}/edit", response_class=HTMLResponse, name="clusters_edit_link_form")
def edit_link_form(request: Request, link_id: str):
    """
    GET route to show a form for editing a link's URL.
    """
    if not hasattr(request.state, 'session'):
        logger.error("Session not available in request.state")
        flash(request, "Session not available. Please log in again.", "warning")
        raise HTTPException(status_code=500, detail="Session not available")
    if "user_id" not in request.state.session:
        flash(request, "You need to log in to edit a link.", "warning")
        return RedirectResponse(url=request.url_for("auth_authorize"))
    try:
        db = client["apimio"]
        link_doc = db.links.find_one({"_id": ObjectId(link_id)})
    except Exception as e:
        logger.error("Error retrieving link: %s", e, exc_info=True)
        flash(request, "There was an error retrieving link details. Please try again later.", "danger")
        raise HTTPException(status_code=500, detail="Error retrieving link")
    if not link_doc:
        flash(request, "The requested link does not exist.", "danger")
        raise HTTPException(status_code=404, detail="Link not found")
    try:
        cluster = db.clusters.find_one({"_id": link_doc["clusterId"], "deleted": False})
    except Exception as e:
        logger.error("Error retrieving cluster for link: %s", e, exc_info=True)
        flash(request, "Error retrieving cluster for link.", "danger")
        raise HTTPException(status_code=500, detail="Error retrieving cluster for link")
    if not cluster:
        flash(request, "The associated cluster for this link was deleted.", "danger")
        raise HTTPException(status_code=404, detail="Cluster not found or deleted for this link")
    try:
        return templates.TemplateResponse("Dashboard/Links/link_edit.html", {
            "request": request,
            "link": link_doc,
            "cluster": cluster,
            "flash_messages": get_flashed_messages(request)
        })
    except Exception as e:
        logger.error("Error rendering edit link form: %s", e, exc_info=True)
        flash(request, "An error occurred while loading the edit form. Please try again.", "danger")
        raise HTTPException(status_code=500, detail="Error rendering edit link form")


@router.post("/links/{link_id}/edit", name="clusters_edit_link_action")
def edit_link_action(
    request: Request,
    link_id: str,
    url: str = Form(...)
):
    """
    POST route to update a link's URL, ensuring domain consistency
    and no duplication within the same cluster.
    """
    if not hasattr(request.state, 'session'):
        logger.error("Session not available in request.state")
        flash(request, "Session not available. Please log in again.", "warning")
        raise HTTPException(status_code=500, detail="Session not available")
    if "user_id" not in request.state.session:
        flash(request, "You need to log in to edit a link.", "warning")
        return RedirectResponse(url=request.url_for("auth_authorize"))
    try:
        db = client["apimio"]
        link_doc = db.links.find_one({"_id": ObjectId(link_id)})
    except Exception as e:
        logger.error("Error retrieving link for editing: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error retrieving link for editing")
    if not link_doc:
        flash(request, "The requested link does not exist.", "danger")
        raise HTTPException(status_code=404, detail="Link not found")
    try:
        cluster = db.clusters.find_one({"_id": link_doc["clusterId"], "deleted": False})
    except Exception as e:
        logger.error("Error retrieving cluster for editing: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error retrieving cluster for editing")
    if not cluster:
        flash(request, "The associated cluster for this link was deleted.", "danger")
        raise HTTPException(status_code=404, detail="Cluster not found or deleted for this link")
    
    new_url = url.strip()
    if not new_url:
        flash(request, "The link URL cannot be empty.", "danger")
        raise HTTPException(status_code=400, detail="Link URL cannot be empty")
    try:
        if not check_domain_consistency(cluster["domain"], new_url):
            flash(request, f"Link '{new_url}' does not match the cluster domain '{cluster['domain']}'.", "danger")
            raise HTTPException(status_code=400, detail=f"Link '{new_url}' does not match domain '{cluster['domain']}'")
    except Exception as e:
        logger.error("Error checking domain consistency for link edit: %s", e, exc_info=True)
        flash(request, f"Link '{new_url}' already exists in this cluster.", "danger")
        raise HTTPException(status_code=400, detail="Error checking domain consistency")
    try:
        existing_same = db.links.find_one({
            "_id": {"$ne": link_doc["_id"]},
            "clusterId": cluster["_id"],
            "url": new_url,
            "deleted": {"$ne": True}
        })
    except Exception as e:
        logger.error("Error checking duplicate link during edit: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error checking for duplicate link")
    if existing_same:
        raise HTTPException(status_code=400, detail=f"Link '{new_url}' already exists in this cluster.")
    try:
        db.links.update_one(
            {"_id": link_doc["_id"]},
            {"$set": {
                "url": new_url,
                "updatedAt": datetime.utcnow()
            }}
        )
    except Exception as e:
        logger.error("Error updating link URL: %s", e, exc_info=True)
        flash(request, "An error occurred while updating the link. Please try again.", "danger")
        raise HTTPException(status_code=500, detail="Error updating link URL")
    try:
        flash(request, "Link updated successfully!", "success")
        return RedirectResponse(
            url=request.url_for("clusters_show_cluster", cluster_id=str(cluster["_id"])),
            status_code=303
        )
    except Exception as e:
        logger.error("Error redirecting after editing link: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error redirecting after editing link")


@router.post("/links/{link_id}/delete", name="clusters_delete_link")
def delete_link(request: Request, link_id: str):
    """
    Soft-delete a single link and its performance data.
    Marks the link and its associated performance data as deleted.
    """
    if not hasattr(request.state, 'session'):
        logger.error("Session not available in request.state")
        flash(request, "Session not available. Please log in again.", "warning")
        raise HTTPException(status_code=500, detail="Session not available")
    if "user_id" not in request.state.session:
        flash(request, "You need to log in to delete a link.", "warning")
        return RedirectResponse(url=request.url_for("auth_authorize"))
    try:
        db = client["apimio"]
        link_doc = db.links.find_one({"_id": ObjectId(link_id), "deleted": {"$ne": True}})
    except Exception as e:
        logger.error("Error retrieving link for deletion: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error retrieving link for deletion")
    if not link_doc:
        flash(request, "The requested link was not found or has already been deleted.", "danger")
        raise HTTPException(status_code=404, detail="Link not found or already trashed")
    try:
        cluster_id = link_doc["clusterId"]
    except Exception as e:
        logger.error("Error retrieving cluster ID from link: %s", e, exc_info=True)
        flash(request, "Error retrieving cluster information for this link.", "danger")
        raise HTTPException(status_code=500, detail="Error retrieving cluster ID")
    now = datetime.utcnow()
    try:
        db.links.update_one(
            {"_id": link_doc["_id"]},
            {"$set": {"deleted": True, "deletedAt": now}}
        )
    except Exception as e:
        logger.error("Error marking link as deleted: %s", e, exc_info=True)
        flash(request, "An error occurred while deleting the link. Please try again.", "danger")
        raise HTTPException(status_code=500, detail="Error deleting link")
    try:
        db.link_performance.update_many(
            {"linkId": link_doc["_id"], "deleted": {"$ne": True}},
            {"$set": {"deleted": True, "deletedAt": now}}
        )
    except Exception as e:
        logger.error("Error marking link performance data as deleted: %s", e, exc_info=True)
        flash(request, "Error deleting link performance data. Some data may still be visible.", "warning")
        raise HTTPException(status_code=500, detail="Error deleting link performance data")
    try:
        flash(request, "Link deleted successfully!", "success")
        return RedirectResponse(
            url=request.url_for("clusters_show_cluster", cluster_id=str(cluster_id)),
            status_code=303
        )
    except Exception as e:
        logger.error("Error redirecting after deleting link: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error redirecting after deleting link")


# -----------------------------------------
# (Cluster and Links Performance routes started here)
# -----------------------------------------


@router.get("/links/{link_id}/performance", response_class=HTMLResponse, name="clusters_link_performance")
def link_performance(
    request: Request,
    link_id: str,
    end: str = Query(None),
    start: str = Query(None)
):
    """
    Display aggregated performance data for a link from the local DB.
    Data is already aggregated by date based on the cluster's deviceFilter and multi-countryFilter.
    """
    if not hasattr(request.state, "session") or "user_id" not in request.state.session:
        flash(request, "You need to log in to view link performance.", "warning")
        return RedirectResponse(url=request.url_for("auth_authorize"))
    
    # 1. Parse date range (defaulting to last 3 months if not provided)
    try:
        if not end or not start:
            today = date.today()
            end_date = (today - timedelta(days=3)).isoformat()  # GSC is ~3 days behind
            start_date = (today - timedelta(days=90)).isoformat()
        else:
            end_date = end
            start_date = start
    except Exception as e:
        logger.error("Error parsing date range: %s", e, exc_info=True)
        flash(request, "Invalid date range provided. Please enter a valid range.", "danger")
        raise HTTPException(status_code=400, detail="Invalid date range parameters")
    
    try:
        db = client["apimio"]
        link_doc = db.links.find_one({"_id": ObjectId(link_id)})
        if not link_doc:
            flash(request, "The requested link was not found.", "danger")
            raise HTTPException(status_code=404, detail="Link not found")
    except Exception as e:
        logger.error("Error retrieving link document: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error retrieving link information")
    
    try:
        cluster = db.clusters.find_one({"_id": link_doc["clusterId"]})
        if not cluster:
            flash(request, "No cluster found for this link. It may have been deleted.", "danger")
            raise HTTPException(status_code=404, detail="Cluster not found for this link")
    except Exception as e:
        logger.error("Error retrieving cluster for link: %s", e, exc_info=True)
        flash(request, "An error occurred while retrieving performance data. Please try again.", "danger")
        raise HTTPException(status_code=500, detail="Error retrieving cluster information")
    
    # 2. Build the performance query for aggregated data.
    perf_query = {
        "linkId": link_doc["_id"],
        "date": {"$gte": start_date, "$lte": end_date},
        "deleted": {"$ne": True}
    }
    
    try:
        # 3. Query local DB, sort by date descending (newest first)
        perf_docs = list(db.link_performance.find(perf_query).sort("date", -1))
        if not perf_docs:
         flash(request, "No performance data available for the selected date range.", "info")
    except Exception as e:
        logger.error("Error querying performance data: %s", e, exc_info=True)
        flash(request, "An error occurred while displaying performance data.", "danger")
        raise HTTPException(status_code=500, detail="Error retrieving performance data")
    
    try:
        # 4. Render the performance template
        return templates.TemplateResponse(
            "Dashboard/Performance/link_performance.html",
            {
                "request": request,
                "link": link_doc,
                "cluster": cluster,
                "start_date": start_date,
                "end_date": end_date,
                "perf_data": perf_docs,
                "flash_messages": get_flashed_messages(request)
            }
        )
    except Exception as e:
            logger.error("Error rendering performance template: %s", e, exc_info=True)
            raise HTTPException(status_code=500, detail="Error rendering performance page")


@router.get("/clusters/{cluster_id}/performance", response_class=HTMLResponse, name="clusters_cluster_performance")
def cluster_performance(
    request: Request,
    cluster_id: str,
    end: str = Query(None),
    start: str = Query(None)
):
    """
    Show aggregate performance for all links in this cluster, by date.
    The cluster's deviceFilter and multi-countryFilter have already been applied when
    aggregating link-level data. The user can only select a date range (start, end),
    defaulting to the last 3 months.
    """
    if not hasattr(request.state, "session") or "user_id" not in request.state.session:
        flash(request, "You need to log in to view cluster performance.", "warning")
        return RedirectResponse(url=request.url_for("auth_authorize"))
    
    try:
        db = client["apimio"]
        # Find the cluster (ensure it's not deleted)
        cluster = db.clusters.find_one({"_id": ObjectId(cluster_id), "deleted": False})
        if not cluster:
            flash(request, "The requested cluster was not found or has been deleted.", "danger")
            raise HTTPException(status_code=404, detail="Cluster not found or deleted.")
    except Exception as e:
        logger.error("Error retrieving cluster: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error retrieving cluster information")
    
    # 1. Parse optional date range (defaulting to last 3 months)
    try:
        if not end or not start:
            today = date.today()
            end_date = (today - timedelta(days=3)).isoformat()  # GSC is ~3 days behind
            start_date = (today - timedelta(days=90)).isoformat()
        else:
            end_date = end
            start_date = start
    except Exception as e:
        logger.error("Error parsing date range: %s", e, exc_info=True)
        flash(request, "Invalid date range provided. Please select a valid range.", "danger")
        raise HTTPException(status_code=400, detail="Invalid date range parameters")
    
    try:
        # 2. Gather all link IDs in this cluster
        link_ids = db.links.find({
            "clusterId": cluster["_id"],
            "deleted": False
        }).distinct("_id")
        if not link_ids:
            flash(request, "No links found in this cluster.", "info")
    except Exception as e:
        logger.error("Error retrieving link IDs for cluster: %s", e, exc_info=True)
        flash(request, "An error occurred while retrieving performance data. Please try again.", "danger")
        raise HTTPException(status_code=500, detail="Error retrieving cluster link IDs")
    
    # 3. Build the performance query.
    perf_query = {
        "linkId": {"$in": link_ids},
        "date": {"$gte": start_date, "$lte": end_date},
        "deleted": {"$ne": True}
    }
    
    try:
        # 4. Fetch performance data from the DB
        perf_docs = list(db.link_performance.find(perf_query))
        if not perf_docs:
            flash(request, "No performance data available for the selected date range.", "info")
    except Exception as e:
        logger.error("Error querying performance data: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error retrieving performance data")
    
    # 5. Aggregate performance by date across all links
    aggregated = {}
    try:
        for doc in perf_docs:
            d = doc["date"]
            if d not in aggregated:
                aggregated[d] = {
                    "clicks": 0,
                    "impressions": 0,
                    "weighted_position_sum": 0.0
                }
            clicks = doc.get("clicks", 0)
            impressions = doc.get("impressions", 0)
            position = doc.get("position", 0)
            aggregated[d]["clicks"] += clicks
            aggregated[d]["impressions"] += impressions
            aggregated[d]["weighted_position_sum"] += position * impressions
    except Exception as e:
        logger.error("Error aggregating performance data: %s", e, exc_info=True)
        flash(request, "An error occurred while aggregating performance data.", "danger")
        raise HTTPException(status_code=500, detail="Error aggregating performance data")
    
    # 6. Prepare aggregated result rows
    result_rows = []
    try:
        for d, data in aggregated.items():
            total_clicks = data["clicks"]
            total_impressions = data["impressions"]
            aggregated_ctr = total_clicks / total_impressions if total_impressions else 0
            aggregated_position = data["weighted_position_sum"] / total_impressions if total_impressions else 0
            result_rows.append({
                "date": d,
                "clicks": total_clicks,
                "impressions": total_impressions,
                "ctr": aggregated_ctr,
                "position": aggregated_position
            })
        # Sort results by date descending (newest first)
        result_rows.sort(key=lambda x: x["date"], reverse=True)
    except Exception as e:
        logger.error("Error preparing aggregated results: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error preparing aggregated performance results")
    
    try:
        # 7. Render the cluster performance template
        return templates.TemplateResponse(
            "Dashboard/Performance/cluster_performance.html",
            {
                "request": request,
                "cluster": cluster,
                "start_date": start_date,
                "end_date": end_date,
                "perf_data": result_rows,
                "flash_messages": get_flashed_messages(request)
            }
        )
    except Exception as e:
        logger.error("Error rendering cluster performance template: %s", e, exc_info=True)
        flash(request, "An error occurred while displaying performance data.", "danger")
        raise HTTPException(status_code=500, detail="Error rendering performance page")


# -----------------------------------------
# (Trash routes started here)
# -----------------------------------------


@router.post("/clusters/{cluster_id}/trash", name="clusters_trash_cluster")
def trash_cluster(request: Request, cluster_id: str):
    """
    Moves the cluster to trash (soft-delete).
    Marks the cluster, all its links, and their performance data as deleted=true.
    """
    if not hasattr(request.state, "session") or "user_id" not in request.state.session:
        flash(request, "You must be logged in to perform this action.", "warning")
        return RedirectResponse(url=request.url_for("auth_authorize"))
    try:
        user_id = request.state.session["user_id"]
        db = client["apimio"]
    except Exception as e:
        logger.error("Error accessing session or DB: %s", e, exc_info=True)
        flash(request, "Internal error accessing session or database.", "error")
        return RedirectResponse(url=request.url_for("clusters_list_clusters"), status_code=303)
    
    try:
        cluster = db.clusters.find_one({
            "_id": ObjectId(cluster_id),
            "userId": ObjectId(user_id),
            "deleted": {"$ne": True}
        })
        if not cluster:
            flash(request, "Cluster not found or already trashed.", "error")
            return RedirectResponse(url=request.url_for("clusters_list_clusters"), status_code=303)
    except Exception as e:
        logger.error("Error retrieving cluster: %s", e, exc_info=True)
        flash(request, "Error retrieving cluster.", "error")
        return RedirectResponse(url=request.url_for("clusters_list_clusters"), status_code=303)
    
    now = datetime.utcnow()
    try:
        # Mark cluster as trashed
        db.clusters.update_one(
            {"_id": cluster["_id"]},
            {"$set": {"deleted": True, "deletedAt": now}}
        )
        # Trash all links under this cluster
        db.links.update_many(
            {"clusterId": cluster["_id"], "deleted": {"$ne": True}},
            {"$set": {"deleted": True, "deletedAt": now}}
        )
        # Trash performance data for these links
        link_ids = db.links.find({"clusterId": cluster["_id"]}).distinct("_id")
        db.link_performance.update_many(
            {"linkId": {"$in": link_ids}, "deleted": {"$ne": True}},
            {"$set": {"deleted": True, "deletedAt": now}}
        )
    except Exception as e:
        logger.error("Error trashing cluster and its links: %s", e, exc_info=True)
        flash(request, "Error trashing cluster and its related data.", "error")
        return RedirectResponse(url=request.url_for("clusters_list_clusters"), status_code=303)
    
    try:
        flash(request, "Cluster moved to trash successfully.", "success")
        return RedirectResponse(url=request.url_for("clusters_list_clusters"), status_code=303)
    except Exception as e:
        logger.error("Error redirecting after trashing cluster: %s", e, exc_info=True)
        flash(request, "Error redirecting after trashing cluster.", "error")
        return RedirectResponse(url=request.url_for("clusters_list_clusters"), status_code=303)

@router.post("/clusters/{cluster_id}/restore", name="clusters_restore_cluster")
def restore_cluster(request: Request, cluster_id: str):
    """
    Restores a trashed cluster and all associated links + performance data.
    """
    if not hasattr(request.state, "session") or "user_id" not in request.state.session:
        flash(request, "You need to log in to restore a cluster.", "warning")
        return RedirectResponse(url=request.url_for("auth_authorize"))
    try:
        user_id = request.state.session["user_id"]
        db = client["apimio"]
        cluster = db.clusters.find_one({
            "_id": ObjectId(cluster_id),
            "userId": ObjectId(user_id),
            "deleted": True
        })
        if not cluster:
            flash(request, "The cluster was not found or is not in the trash.", "danger")
            raise HTTPException(status_code=404, detail="Cluster not found or not trashed.")
    except Exception as e:
        logger.error("Error retrieving trashed cluster: %s", e, exc_info=True)
        flash(request, "An error occurred while retrieving the trashed cluster.", "danger")
        raise HTTPException(status_code=500, detail="Error retrieving trashed cluster")
    
    try:
        # Restore cluster
        db.clusters.update_one(
            {"_id": cluster["_id"]},
            {"$set": {"deleted": False, "deletedAt": None}}
        )
        # Restore links
        db.links.update_many(
            {"clusterId": cluster["_id"], "deleted": True},
            {"$set": {"deleted": False, "deletedAt": None}}
        )
        # Restore performance data
        link_ids = db.links.find({"clusterId": cluster["_id"]}).distinct("_id")
        db.link_performance.update_many(
            {"linkId": {"$in": link_ids}, "deleted": True},
            {"$set": {"deleted": False, "deletedAt": None}}
        )
    except Exception as e:
        logger.error("Error restoring cluster: %s", e, exc_info=True)
        flash(request, "An error occurred while restoring the cluster. Please try again.", "danger")
        raise HTTPException(status_code=500, detail="Error restoring cluster")
    
    try:
        flash(request, "Cluster and all associated data successfully restored!", "success")
        return RedirectResponse(url=request.url_for("clusters_show_cluster", cluster_id=cluster_id), status_code=303)
    except Exception as e:
        flash(request, "Cluster restored, but there was an issue redirecting.", "warning")
        logger.error("Error redirecting after restoring cluster: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error redirecting after restoration")

@router.post("/clusters/{cluster_id}/delete-permanently", name="clusters_delete_cluster_permanently")
def delete_cluster_permanently(request: Request, cluster_id: str):
    """
    Physically removes the cluster doc, links, and performance data from DB.
    Typically used after a 30-day grace period or user confirmation.
    """
    if not hasattr(request.state, "session") or "user_id" not in request.state.session:
        flash(request, "You need to log in to delete a cluster permanently.", "warning")
        return RedirectResponse(url=request.url_for("auth_authorize"))
    try:
        user_id = request.state.session["user_id"]
        db = client["apimio"]
        cluster = db.clusters.find_one({
            "_id": ObjectId(cluster_id),
            "userId": ObjectId(user_id),
            "deleted": True
        })
        if not cluster:
            flash(request, "The cluster was not found or is not in the trash.", "danger")
            raise HTTPException(status_code=404, detail="Cluster not found or not in trash.")
    except Exception as e:
        logger.error("Error retrieving trashed cluster: %s", e, exc_info=True)
        flash(request, "An error occurred while retrieving the trashed cluster.", "danger")
        raise HTTPException(status_code=500, detail="Error retrieving trashed cluster")
    
    try:
        link_ids = db.links.find({"clusterId": cluster["_id"]}).distinct("_id")
        # Remove performance data
        db.link_performance.delete_many({"linkId": {"$in": link_ids}})
        # Remove links
        db.links.delete_many({"clusterId": cluster["_id"]})
        # Remove cluster
        db.clusters.delete_one({"_id": cluster["_id"]})
    except Exception as e:
        logger.error("Error permanently deleting cluster: %s", e, exc_info=True)
        flash(request, "An error occurred while permanently deleting the cluster. Please try again.", "danger")
        raise HTTPException(status_code=500, detail="Error deleting cluster permanently")
    
    try:
        flash(request, "Cluster and all associated data have been permanently deleted.", "success")
        return RedirectResponse(url=request.url_for("clusters_list_clusters"), status_code=303)
    except Exception as e:
        logger.error("Error redirecting after permanent deletion of cluster: %s", e, exc_info=True)
        flash(request, "Cluster deleted, but there was an issue redirecting.", "warning")
        raise HTTPException(status_code=500, detail="Error redirecting after deletion")

@router.post("/links/{link_id}/trash", name="clusters_trash_link")
def trash_link(request: Request, link_id: str):
    """
    Moves the link to trash (soft-delete).
    Marks the link and its performance data as deleted=true.
    """
    if not hasattr(request.state, "session") or "user_id" not in request.state.session:
        flash(request, "You need to log in to trash a link.", "warning")
        return RedirectResponse(url=request.url_for("auth_authorize"))
    try:
        user_id = request.state.session["user_id"]
        db = client["apimio"]
        link_doc = db.links.find_one({
            "_id": ObjectId(link_id),
            "deleted": {"$ne": True}
        })
        if not link_doc:
            flash(request, "The link was not found or is already trashed.", "danger")
            raise HTTPException(status_code=404, detail="Link not found or already trashed.")
    except Exception as e:
        logger.error("Error retrieving link for trashing: %s", e, exc_info=True)
        flash(request, "An error occurred while retrieving the link.", "danger")
        raise HTTPException(status_code=500, detail="Error retrieving link for trashing")
    
    try:
        # Ensure the cluster belongs to this user
        cluster = db.clusters.find_one({
            "_id": link_doc["clusterId"],
            "userId": ObjectId(user_id)
        })
        if not cluster:
            flash(request, "You do not have permission to trash this link.", "danger")
            raise HTTPException(status_code=403, detail="This link's cluster does not belong to the current user.")
    except Exception as e:
        logger.error("Error verifying link's cluster: %s", e, exc_info=True)
        flash(request, "An error occurred while verifying the link's cluster.", "danger")
        raise HTTPException(status_code=500, detail="Error verifying link's cluster")
    
    now = datetime.utcnow()
    try:
        # Mark the link as trashed
        db.links.update_one(
            {"_id": link_doc["_id"]},
            {"$set": {"deleted": True, "deletedAt": now}}
        )
        # Trash performance data for this link
        db.link_performance.update_many(
            {"linkId": link_doc["_id"], "deleted": {"$ne": True}},
            {"$set": {"deleted": True, "deletedAt": now}}
        )
    except Exception as e:
        logger.error("Error trashing link and its performance data: %s", e, exc_info=True)
        flash(request, "An error occurred while trashing the link.", "danger")
        raise HTTPException(status_code=500, detail="Error trashing link")
    
    try:
        flash(request, "The link has been moved to trash.", "success")
        return RedirectResponse(
            url=request.url_for("clusters_show_cluster", cluster_id=str(link_doc["clusterId"])),
            status_code=303
        )
    except Exception as e:
        logger.error("Error redirecting after trashing link: %s", e, exc_info=True)
        flash(request, "The link was trashed, but there was an issue redirecting.", "warning")
        raise HTTPException(status_code=500, detail="Error redirecting after trashing link")

@router.post("/links/{link_id}/restore", name="clusters_restore_link")
def restore_link(request: Request, link_id: str):
    """
    Restores a trashed link (deleted=true => deleted=false),
    also restores its performance data.
    """
    if not hasattr(request.state, "session") or "user_id" not in request.state.session:
        flash(request, "You need to log in to restore a link.", "warning")
        return RedirectResponse(url=request.url_for("auth_authorize"))
    try:
        user_id = request.state.session["user_id"]
        db = client["apimio"]
        link_doc = db.links.find_one({
            "_id": ObjectId(link_id),
            "deleted": True
        })
        if not link_doc:
            flash(request, "The link was not found or is not in trash.", "danger")
            raise HTTPException(status_code=404, detail="Link not found or not in trash.")
    except Exception as e:
        logger.error("Error retrieving trashed link: %s", e, exc_info=True)
        flash(request, "An error occurred while retrieving the trashed link.", "danger")
        raise HTTPException(status_code=500, detail="Error retrieving trashed link")
    
    try:
        # Ensure the cluster belongs to this user
        cluster = db.clusters.find_one({
            "_id": link_doc["clusterId"],
            "userId": ObjectId(user_id)
        })
        if not cluster:
            flash(request, "You do not have permission to restore this link.", "danger")
            raise HTTPException(status_code=403, detail="This link's cluster does not belong to the current user.")
    except Exception as e:
        logger.error("Error verifying link's cluster for restore: %s", e, exc_info=True)
        flash(request, "An error occurred while verifying the link's cluster.", "danger")
        raise HTTPException(status_code=500, detail="Error verifying link's cluster")
    
    try:
        # Restore link and its performance data
        db.links.update_one(
            {"_id": link_doc["_id"]},
            {"$set": {"deleted": False, "deletedAt": None}}
        )
        db.link_performance.update_many(
            {"linkId": link_doc["_id"], "deleted": True},
            {"$set": {"deleted": False, "deletedAt": None}}
        )
    except Exception as e:
        logger.error("Error restoring link and its performance data: %s", e, exc_info=True)
        flash(request, "An error occurred while restoring the link.", "danger")
        raise HTTPException(status_code=500, detail="Error restoring link")
    
    try:
        flash(request, "The link has been restored.", "success")
        return RedirectResponse(
            url=request.url_for("clusters_show_cluster", cluster_id=str(link_doc["clusterId"])),
            status_code=303
        )
    except Exception as e:
        logger.error("Error redirecting after restoring link: %s", e, exc_info=True)
        flash(request, "The link was restored, but there was an issue redirecting.", "warning")
        raise HTTPException(status_code=500, detail="Error redirecting after restoring link")

@router.post("/links/{link_id}/delete-permanently", name="clusters_delete_link_permanently")
def delete_link_permanently(request: Request, link_id: str):
    """
    Physically removes the link doc and performance data from DB.
    Typically used after a 30-day grace period or user confirmation.
    """
    if not hasattr(request.state, "session") or "user_id" not in request.state.session:
        flash(request, "You need to log in to delete a link permanently.", "warning")
        return RedirectResponse(url=request.url_for("auth_authorize"))
    try:
        user_id = request.state.session["user_id"]
        db = client["apimio"]
        link_doc = db.links.find_one({
            "_id": ObjectId(link_id),
            "deleted": True
        })
        if not link_doc:
            flash(request, "The link was not found or is not in trash.", "danger")
            raise HTTPException(status_code=404, detail="Link not found or not in trash.")
    except Exception as e:
        logger.error("Error retrieving trashed link for permanent deletion: %s", e, exc_info=True)
        flash(request, "An error occurred while retrieving the trashed link.", "danger")
        raise HTTPException(status_code=500, detail="Error retrieving trashed link")
    
    try:
        # Ensure the cluster belongs to this user
        cluster = db.clusters.find_one({
            "_id": link_doc["clusterId"],
            "userId": ObjectId(user_id)
        })
        if not cluster:
            flash(request, "You do not have permission to delete this link permanently.", "danger")
            raise HTTPException(status_code=403, detail="This link's cluster does not belong to the current user.")
    except Exception as e:
        logger.error("Error verifying cluster for permanent link deletion: %s", e, exc_info=True)
        flash(request, "An error occurred while verifying the link's cluster.", "danger")
        raise HTTPException(status_code=500, detail="Error verifying cluster")
    
    try:
        db.link_performance.delete_many({"linkId": link_doc["_id"]})
        db.links.delete_one({"_id": link_doc["_id"]})
    except Exception as e:
        logger.error("Error deleting link permanently: %s", e, exc_info=True)
        flash(request, "An error occurred while deleting the link permanently.", "danger")
        raise HTTPException(status_code=500, detail="Error deleting link permanently")
    
    try:
        flash(request, "The link has been permanently deleted.", "success")
        return RedirectResponse(url=request.url_for("clusters_list_clusters"), status_code=303)
    except Exception as e:
        logger.error("Error redirecting after permanent link deletion: %s", e, exc_info=True)
        flash(request, "The link was deleted, but there was an issue redirecting.", "warning")
        raise HTTPException(status_code=500, detail="Error redirecting after deletion")

@router.get("/trash/{domain}", response_class=HTMLResponse, name="clusters_view_trash")
def view_trash(request: Request, domain: str):
    """
    Show all trashed clusters and links for this user + domain.
    - Clusters: userId + domain + deleted=True
    - Links: userId + domain + deleted=True (the link's cluster must belong to the same user+domain)
    """
    if not hasattr(request.state, "session") or "user_id" not in request.state.session:
        flash(request, "You need to log in to view trashed items.", "warning")
        return RedirectResponse(url=request.url_for("auth_authorize"))
    try:
        user_id = request.state.session["user_id"]
        db = client["apimio"]
        # Find all clusters for this user and domain
        all_domain_clusters = list(db.clusters.find({
            "userId": ObjectId(user_id),
            "domain": domain
        }, {"_id": 1, "deleted": 1}))
        cluster_ids = [c["_id"] for c in all_domain_clusters]
        trashed_clusters = list(db.clusters.find({
            "userId": ObjectId(user_id),
            "domain": domain,
            "deleted": True
        }))
        trashed_links = []
        if cluster_ids:
            trashed_links = list(db.links.find({
                "clusterId": {"$in": cluster_ids},
                "deleted": True
            }))
    except Exception as e:
        logger.error("Error retrieving trash data: %s", e, exc_info=True)
        flash(request, "No trashed clusters or links found for this domain.", "info")
        raise HTTPException(status_code=500, detail="Error retrieving trash data")
    
    try:
        return templates.TemplateResponse(
            "Dashboard/Trash/trash.html",
            {
                "request": request,
                "trashed_clusters": trashed_clusters,
                "trashed_links": trashed_links,
                "domain": domain,
                "flash_messages": get_flashed_messages(request)
            }
        )
    except Exception as e:
        logger.error("Error rendering trash template: %s", e, exc_info=True)
        flash(request, "An error occurred while retrieving trashed data.", "danger")
        raise HTTPException(status_code=500, detail="Error rendering trash page")
