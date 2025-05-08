import logging
import uuid
from datetime import *

import firebase_admin
from firebase_admin import firestore
from google.cloud.firestore_v1 import FieldFilter
import os
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


_table_users = 'vendo_users'
_table_organizations = 'vendo_organizations'
_table_active_jobs = 'vendo_active_jobs'
_table_job_history = 'vendo_job_history'
_table_connections = 'vendo_connections'
_table_usage = 'vendo_usage'

print("⚡ inside firebase_client")

def get_firestore_client():
    if not firebase_admin._apps:
        app = firebase_admin.initialize_app(options={
            'databaseURL': os.getenv('FIREBASE_DB_URL')
        })
    else:
        app = firebase_admin.get_app()
    return firestore.client(app)

def get_organization(organization_id):
    client = get_firestore_client()
    result = client.collection(_table_organizations).document(organization_id).get()
    if result.exists:
        return result.to_dict()
    return None


def get_connection(connection_id: str):
    client = get_firestore_client()
    result = client.collection(_table_connections).document(connection_id).get()
    if result.exists:
        return result.to_dict()
    return None

 
