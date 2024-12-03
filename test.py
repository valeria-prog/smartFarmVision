import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# app.py
from flask import Flask, render_template, redirect, url_for, flash, request, session, jsonify
from functools import wraps
import os
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, initialize_app, firestore, auth
import logging
from datetime import datetime
from flask import jsonify, request
import uuid

from deepface import DeepFace

import numpy as np

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here')  

# Initialize Firebase Admin SDK
try:
    cred = credentials.Certificate({
        "type": "service_account",
        "project_id": os.getenv('FIREBASE_PROJECT_ID'),
        "private_key_id": os.getenv('FIREBASE_PRIVATE_KEY_ID'),
        "private_key": os.getenv('FIREBASE_PRIVATE_KEY').replace('\\n', '\n'),
        "client_email": os.getenv('FIREBASE_CLIENT_EMAIL'),
        "client_id": os.getenv('FIREBASE_CLIENT_ID'),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": os.getenv('FIREBASE_CLIENT_CERT_URL')
    })
    
    # Initialize Firebase with a name
    firebase_app = firebase_admin.initialize_app(cred, name='smartfarm')
    
    # Get Firestore and Auth instances
    db = firestore.client(app=firebase_app)
    auth_client = auth.Client(app=firebase_app)
    
    logger.info("Firebase initialized successfully")
    
except Exception as e:
    logger.error(f"Error initializing Firebase: {str(e)}")
    raise

def update_barn_structure(barn_id):
    db.collection('barns').document(barn_id).update({
        'name': 'Subject Area #1',  # En lugar de "Barn #1"
        'current_count': 0,  # Ahora contará subjects en lugar de animals
        'capacity': 10,      # Capacidad máxima de subjects
        'avg_age': 0,
        'avg_weight': 0,
        'health_score': 100,
        'status': 'active',
        'description': 'Area for subject monitoring',
        'updated_at': firestore.SERVER_TIMESTAMP
    })
def assign_subjects_to_areas():
    # Definir las áreas y sus grupos de subjects
    area_assignments = {
        '82AJsQmyI8oUlNXMapYJ': [  # Primera área
            '84b4cd54', 
            'aa02fc99', 
            '99c5b4ed', 
            'bf009e44',
            'a1eb88dd'
        ],
        'FpuAcjxMmnq3YPdSKfhu': [  # Segunda área
            'd7c2617b', 
            'a080792a', 
            '9ca183ea', 
            '233d1c9a', 
            '4c6950fc'
        ]
    }
    
    resultados = {}
    
    for area_id, subject_ids in area_assignments.items():
        # Referencia al área
        area_ref = db.collection('barns').document(area_id)
        
        total_weight = 0
        total_age = 0
        count = 0
        
        # Asignar subjects al área
        for subject_id in subject_ids:
            try:
                # Actualizar el subject con el ID del área
                db.collection('persons').document(subject_id).update({
                    'area_id': area_id,  # Cambiado de barn_id a area_id
                    'assigned_at': firestore.SERVER_TIMESTAMP
                })
                
                # Obtener datos del subject para estadísticas
                subject_doc = db.collection('persons').document(subject_id).get()
                if subject_doc.exists:
                    subject_data = subject_doc.to_dict()
                    if 'latest_measurement' in subject_data:
                        measurement = subject_data['latest_measurement']
                        total_weight += measurement.get('weight', 0)
                        total_age += measurement.get('age', 0)
                        count += 1
                        
            except Exception as e:
                print(f"Error con subject {subject_id}: {e}")
        
        # Actualizar estadísticas del área
        if count > 0:
            area_ref.update({
                'avg_weight': total_weight / count,
                'avg_age': total_age / count,
                'current_count': count,
                'updated_at': firestore.SERVER_TIMESTAMP
            })
        
        resultados[area_id] = {
            'subjects_asignados': count,
            'promedio_peso': total_weight / count if count > 0 else 0,
            'promedio_edad': total_age / count if count > 0 else 0
        }
    
    return resultados

# Para ejecutar y ver resultados
resultados = assign_subjects_to_areas()
for area_id, stats in resultados.items():
    print(f"\nÁrea {area_id}:")
    print(f"- Subjects asignados: {stats['subjects_asignados']}")
    print(f"- Peso promedio: {stats['promedio_peso']:.2f} kg")
    print(f"- Edad promedio: {stats['promedio_edad']:.1f} años")