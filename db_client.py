import os
import logging
import warnings
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv

# Ignore specific warnings.
warnings.filterwarnings(
    "ignore",
    message="file_cache is only supported with oauth2client<4.0.0"
)

# Configure logging for the module.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger('werkzeug').setLevel(logging.WARNING)

# Load environment variables from .env file.
load_dotenv()

# Retrieve the MongoDB URI from environment variables.
uri = os.getenv("MONGODB_URI")
if not uri:
    logger.error("MONGODB_URI environment variable not set.")
    raise EnvironmentError("MONGODB_URI environment variable not set.")

client = None
try:
    # Initialize the MongoDB client with the server API version.
    client = MongoClient(uri, server_api=ServerApi('1'))
    # Ping the server to verify a successful connection.
    client.admin.command('ping')
    logger.info("Pinged your MongoDB deployment. Connected successfully!")
    
    # Access the target database.
    db = client['apimio']
    # Access the 'link_performance' collection.
    collection = db.link_performance

    # Create a compound index on (linkId, date, deleted).
    index_name = collection.create_index([
        ("linkId", 1),
        ("date", 1),
        ("deleted", 1)
    ])
    logger.info("Index created successfully on (linkId, date, deleted): %s", index_name)

except Exception as e:
    logger.error("Error connecting to MongoDB: %s", e, exc_info=True)
    raise e
