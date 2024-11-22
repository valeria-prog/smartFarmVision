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
import cv2
import numpy as np
import base64
from PIL import Image
import io

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

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/test_firebase')
def test_firebase():
    try:
        # Test database connection
        test_ref = db.collection('test').document('test')
        test_ref.set({'test': 'connection successful'})
        return 'Firebase connection successful!'
    except Exception as e:
        return f'Firebase connection failed: {str(e)}'
# Routes
@app.route('/')
def start():
    """Landing page route"""
    return render_template('start.html')

# Rutas de autenticación
@app.route('/auth')
def auth():
    """Ruta de la página de autenticación"""
    # Si el usuario ya está logueado, redirigir al dashboard
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('auth.html')

# Update the login route to use auth_client
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handle login"""
    if request.method == 'GET':
        return redirect(url_for('auth'))
        
    try:
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not email or not password:
            flash('Por favor ingrese email y contraseña.', 'error')
            return redirect(url_for('auth'))

        try:
            # Use auth_client instead of auth
            user = auth_client.get_user_by_email(email)
            
            session['user_id'] = user.uid
            session['email'] = user.email
            
            # Aquí normalmente verificarías la contraseña con Firebase Auth
            # Por ahora, solo verificamos que el usuario existe
            
            # Crear sesión del usuario
            session['user_id'] = user.uid
            session['email'] = user.email
            
            # Obtener datos adicionales del usuario
            user_doc = db.collection('users').document(user.uid).get()
            if user_doc.exists:
                user_data = user_doc.to_dict()
                session['farm_name'] = user_data.get('farm_name')
                session['first_name'] = user_data.get('first_name')
                
                # Actualizar último login
                db.collection('users').document(user.uid).update({
                    'last_login': firestore.SERVER_TIMESTAMP,
                    'login_count': firestore.Increment(1)
                })
            
            # Log del evento
            logging.info(f"Usuario logueado exitosamente: {user.uid}")
            
            flash('¡Bienvenido de vuelta!', 'success')
            return redirect(url_for('dashboard'))
            
        except firebase_admin.auth.UserNotFoundError:
            flash('Email o contraseña incorrectos.', 'error')
            logging.warning(f"Intento de login fallido para email: {email}")
            return redirect(url_for('auth'))
            
    except Exception as e:
        logging.error(f"Error en login: {str(e)}")
        flash('Error al iniciar sesión. Por favor intente nuevamente.', 'error')
        return redirect(url_for('auth'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    """Manejar el registro de nuevos usuarios"""
    if request.method == 'GET':
        return redirect(url_for('auth'))
        
    try:
        # Log de inicio del proceso
        logging.info("Iniciando proceso de registro")
        
        # Obtener datos del formulario
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm-password')
        first_name = request.form.get('first-name')
        last_name = request.form.get('last-name')
        farm_name = request.form.get('farm-name')
        
        # Log de datos recibidos (sin la contraseña por seguridad)
        logging.info(f"Datos recibidos: email={email}, first_name={first_name}, last_name={last_name}, farm_name={farm_name}")
        
        # Validaciones básicas
        if not all([email, password, confirm_password, first_name, last_name, farm_name]):
            missing_fields = [field for field, value in {
                'email': email,
                'password': password,
                'confirm_password': confirm_password,
                'first_name': first_name,
                'last_name': last_name,
                'farm_name': farm_name
            }.items() if not value]
            logging.warning(f"Campos faltantes en el formulario: {missing_fields}")
            flash('Por favor complete todos los campos requeridos.', 'error')
            return redirect(url_for('auth'))
            
        if password != confirm_password:
            logging.warning("Las contraseñas no coinciden")
            flash('Las contraseñas no coinciden.', 'error')
            return redirect(url_for('auth'))
            
        if len(password) < 6:
            logging.warning("Contraseña demasiado corta")
            flash('La contraseña debe tener al menos 6 caracteres.', 'error')
            return redirect(url_for('auth'))

        try:
            # Create new user using auth_client instead of auth
            logging.info("Creando usuario en Firebase Auth...")
            user = auth_client.create_user(
                email=email,
                password=password,
                display_name=f"{first_name} {last_name}"
            )
            logging.info(f"Usuario creado en Auth con ID: {user.uid}")
            
            # Crear documento del usuario en Firestore
            user_data = {
                'first_name': first_name,
                'last_name': last_name,
                'email': email,
                'farm_name': farm_name,
                'created_at': firestore.SERVER_TIMESTAMP,
                'last_login': firestore.SERVER_TIMESTAMP,
                'login_count': 0,
                'status': 'active',
                'user_type': 'farm_owner',
                'settings': {
                    'notifications_enabled': True,
                    'language': 'es'
                }
            }
            
            # Crear el documento del usuario
            logging.info(f"Creando documento de usuario en Firestore para ID: {user.uid}")
            db.collection('users').document(user.uid).set(user_data)
            logging.info("Documento de usuario creado exitosamente")
            
            # Crear documento para la granja
            farm_data = {
                'name': farm_name,
                'owner_id': user.uid,
                'created_at': firestore.SERVER_TIMESTAMP,
                'status': 'active',
                'location': '',
                'size': '',
                'type': '',
                'animals_count': 0,
                'barns_count': 0
            }
            
            # Añadir la granja
            logging.info("Creando documento de granja en Firestore...")
            farm_ref = db.collection('farms').add(farm_data)
            farm_id = farm_ref[1].id
            logging.info(f"Granja creada con ID: {farm_id}")
            
            # Actualizar el usuario con el ID de la granja
            logging.info("Actualizando documento de usuario con ID de granja...")
            db.collection('users').document(user.uid).update({
                'farm_id': farm_id
            })
            logging.info("Documento de usuario actualizado con ID de granja")

            # Crear estructura inicial de la granja
            logging.info("Creando estructura inicial de la granja...")
            
            # Crear colección de corrales
            initial_barn = {
                'name': 'Corral Principal',
                'capacity': 100,
                'current_count': 0,
                'farm_id': farm_id,
                'created_at': firestore.SERVER_TIMESTAMP,
                'status': 'active'
            }
            barn_ref = db.collection('barns').add(initial_barn)
            barn_id = barn_ref[1].id
            logging.info(f"Corral inicial creado con ID: {barn_id}")

            # Crear colección de configuraciones de la granja
            farm_settings = {
                'farm_id': farm_id,
                'notification_preferences': {
                    'email_alerts': True,
                    'sms_alerts': False
                },
                'monitoring_settings': {
                    'temperature_alerts': True,
                    'weight_alerts': True,
                    'health_alerts': True
                },
                'created_at': firestore.SERVER_TIMESTAMP
            }
            db.collection('farm_settings').document(farm_id).set(farm_settings)
            logging.info("Configuraciones de granja creadas")
            
            # Verificación final de la creación de datos
            verify_user = db.collection('users').document(user.uid).get()
            verify_farm = db.collection('farms').document(farm_id).get()
            
            if verify_user.exists and verify_farm.exists:
                logging.info("Verificación exitosa: Todos los documentos fueron creados correctamente")
                flash('¡Cuenta creada exitosamente! Por favor inicie sesión.', 'success')
            else:
                logging.error("Verificación falló: Algunos documentos no fueron creados")
                flash('La cuenta fue creada pero algunos datos no se guardaron correctamente.', 'warning')
            
            return redirect(url_for('auth'))
            
        except Exception as e:
            logging.error(f"Error durante el proceso de registro: {str(e)}")
            if 'EMAIL_EXISTS' in str(e):
                flash('Este email ya está registrado. Por favor inicie sesión.', 'error')
            else:
                flash('Error al crear la cuenta. Por favor intente nuevamente.', 'error')
            return redirect(url_for('auth'))
            
    except Exception as e:
        logging.error(f"Error general en signup: {str(e)}")
        flash('Error al crear la cuenta. Por favor intente nuevamente.', 'error')
        return redirect(url_for('auth'))

# Ruta de prueba para verificar la estructura de datos
@app.route('/verify_data/<user_id>')
def verify_data(user_id):
    try:
        # Verificar usuario
        user_doc = db.collection('users').document(user_id).get()
        user_data = user_doc.to_dict() if user_doc.exists else None
        
        # Verificar granja
        farm_id = user_data.get('farm_id') if user_data else None
        farm_doc = db.collection('farms').document(farm_id).get() if farm_id else None
        farm_data = farm_doc.to_dict() if farm_doc and farm_doc.exists else None
        
        # Verificar corrales
        barns = []
        if farm_id:
            barn_docs = db.collection('barns').where('farm_id', '==', farm_id).stream()
            barns = [{'id': doc.id, **doc.to_dict()} for doc in barn_docs]
            
        # Verificar configuraciones
        settings_doc = db.collection('farm_settings').document(farm_id).get() if farm_id else None
        settings_data = settings_doc.to_dict() if settings_doc and settings_doc.exists else None
        
        return {
            'user': user_data,
            'farm': farm_data,
            'barns': barns,
            'settings': settings_data
        }
        
    except Exception as e:
        return {'error': str(e)}

@app.route('/logout')
def logout():
    """Manejar el cierre de sesión"""
    try:
        # Si hay un usuario logueado, registrar el momento del logout
        if 'user_id' in session:
            user_id = session['user_id']
            db.collection('users').document(user_id).update({
                'last_logout': firestore.SERVER_TIMESTAMP
            })
            
        # Limpiar la sesión
        session.clear()
        flash('Has cerrado sesión exitosamente.', 'info')
        
    except Exception as e:
        logging.error(f"Error en logout: {str(e)}")
        flash('Error al cerrar sesión.', 'error')
        
    return redirect(url_for('start'))

# Función auxiliar para verificar si el usuario está logueado
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor inicie sesión para acceder a esta página.', 'warning')
            return redirect(url_for('auth'))
        return f(*args, **kwargs)
    return decorated_function
#######################################################DASHBOARD#######################################################
@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard page route"""
    try:
        user_id = session.get('user_id')
        user_doc = db.collection('users').document(user_id).get()
        
        if not user_doc.exists:
            flash('User data not found.', 'error')
            return redirect(url_for('logout'))
            
        user_data = user_doc.to_dict()

        # Get farm data
        farm_id = user_data.get('farm_id')
        farm_doc = db.collection('farms').document(farm_id).get()
        farm_data = farm_doc.to_dict() if farm_doc.exists else {}
        
        # Get barns data
        barns_ref = db.collection('barns').where('farm_id', '==', farm_id).stream()
        barns = []
        total_animals = 0
        
        for barn in barns_ref:
            barn_data = barn.to_dict()
            barn_data['id'] = barn.id
            
            # Calculate stats for each barn
            total_animals += barn_data.get('current_count', 0)
            
            # Add calculated fields (you can modify these based on your needs)
            barn_data.update({
                'avg_weight': barn_data.get('avg_weight', 0),
                'avg_age': barn_data.get('avg_age', 0),
                'health_score': barn_data.get('health_score', 0),
                'status': barn_data.get('status', 'active')
            })
            
            barns.append(barn_data)
        
        # Get alerts
        alerts_ref = db.collection('alerts').where('farm_id', '==', farm_id)\
                      .where('status', '==', 'active').stream()
        active_alerts = len(list(alerts_ref))
        
        # Calculate overall farm statistics
        farm_stats = {
            'total_animals': total_animals,
            'avg_weight': sum(b.get('avg_weight', 0) for b in barns) / len(barns) if barns else 0,
            'health_score': sum(b.get('health_score', 0) for b in barns) / len(barns) if barns else 0,
            'active_alerts': active_alerts
        }
        
        # Get historical data for comparison
        last_week_stats = {  # You would actually fetch this from historical data
            'total_animals': farm_stats['total_animals'] - 123,  # Example change
            'avg_weight': farm_stats['avg_weight'] + 2.3,  # Example change
            'health_score': farm_stats['health_score'] - 5,  # Example change
        }
        
        # Calculate changes
        changes = {
            'animals_change': farm_stats['total_animals'] - last_week_stats['total_animals'],
            'weight_change': farm_stats['avg_weight'] - last_week_stats['avg_weight'],
            'health_change': farm_stats['health_score'] - last_week_stats['health_score'],
        }
        
        return render_template('dashboard.html', 
                             user=user_data,
                             farm=farm_data,
                             barns=barns,
                             stats=farm_stats,
                             changes=changes)
                             
    except Exception as e:
        logger.error(f"Dashboard error: {str(e)}")
        flash('Error loading dashboard.', 'error')
        return redirect(url_for('start'))
    
@app.route('/initialize_farm_data')
@login_required
def initialize_farm_data():
    """Initialize farm data structure"""
    try:
        user_id = session.get('user_id')
        user_doc = db.collection('users').document(user_id).get()
        farm_id = user_doc.to_dict().get('farm_id')
        
        # Initialize barns with some data
        barns_data = [
            {
                'name': 'Barn A',
                'capacity': 100,
                'current_count': 80,
                'farm_id': farm_id,
                'avg_weight': 75.4,
                'avg_age': 12,
                'health_score': 94,
                'status': 'active',
                'created_at': firestore.SERVER_TIMESTAMP
            },
            {
                'name': 'Barn B',
                'capacity': 150,
                'current_count': 120,
                'farm_id': farm_id,
                'avg_weight': 68.2,
                'avg_age': 8,
                'health_score': 88,
                'status': 'active',
                'created_at': firestore.SERVER_TIMESTAMP
            }
        ]
        
        # Add barns
        for barn_data in barns_data:
            db.collection('barns').add(barn_data)
            
        # Initialize some alerts
        alerts_data = [
            {
                'farm_id': farm_id,
                'type': 'health',
                'severity': 'high',
                'message': 'Health check required in Barn A',
                'status': 'active',
                'created_at': firestore.SERVER_TIMESTAMP
            },
            {
                'farm_id': farm_id,
                'type': 'weight',
                'severity': 'medium',
                'message': 'Weight below threshold in Barn B',
                'status': 'active',
                'created_at': firestore.SERVER_TIMESTAMP
            }
        ]
        
        # Add alerts
        for alert_data in alerts_data:
            db.collection('alerts').add(alert_data)
            
        return jsonify({'message': 'Farm data initialized successfully'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Barn Management Routes
@app.route('/api/barns', methods=['GET'])
@login_required
def get_barns_data():
    try:
        user_id = session.get('user_id')
        user_doc = db.collection('users').document(user_id).get()
        farm_id = user_doc.to_dict().get('farm_id')

        # Fetch barns
        barns_ref = db.collection('barns').where('farm_id', '==', farm_id).where('status', '!=', 'deleted').stream()
        barns = []
        for barn in barns_ref:
            barn_data = barn.to_dict()
            barn_data['id'] = barn.id

            # Calculate additional insights
            barn_data['avg_age'] = barn_data.get('avg_age', 0)  # Replace with your calculation logic
            barn_data['health_score'] = barn_data.get('health_score', 0)  # Replace with actual calculation
            barn_data['alerts'] = barn_data.get('alerts', 0)  # Count of active alerts for this barn
            barn_data['avg_weight'] = barn_data.get('avg_weight', 0)  # Replace with actual data
            barn_data['avg_length'] = barn_data.get('avg_length', 0)  # Replace with actual data

            barns.append(barn_data)

        # Calculate stats (optional, already done previously)
        total_barns = len(barns)
        total_capacity = sum(barn.get('capacity', 0) for barn in barns)
        total_current_count = sum(barn.get('current_count', 0) for barn in barns)
        active_alerts_ref = db.collection('alerts').where('farm_id', '==', farm_id).where('status', '==', 'active').stream()
        active_alerts = len(list(active_alerts_ref))

        average_occupancy = (total_current_count / total_capacity * 100) if total_capacity > 0 else 0

        return jsonify({
            'success': True,
            'barns': barns,
            'total_barns': total_barns,
            'total_capacity': total_capacity,
            'average_occupancy': average_occupancy,
            'active_alerts': active_alerts
        })
    except Exception as e:
        logger.error(f"Error fetching barns data: {str(e)}")
        return jsonify({'error': 'Failed to fetch barns data'}), 500



@app.route('/api/barns/<barn_id>', methods=['GET'])
@login_required
def get_barn(barn_id):
    """Get specific barn details"""
    try:
        user_id = session.get('user_id')
        user_doc = db.collection('users').document(user_id).get()
        farm_id = user_doc.to_dict().get('farm_id')
        
        barn_doc = db.collection('barns').document(barn_id).get()
        
        if not barn_doc.exists:
            return jsonify({'error': 'Barn not found'}), 404
            
        barn_data = barn_doc.to_dict()
        
        # Verify barn belongs to user's farm
        if barn_data.get('farm_id') != farm_id:
            return jsonify({'error': 'Unauthorized access'}), 403
            
        return jsonify({
            'id': barn_doc.id,
            **barn_data
        })
        
    except Exception as e:
        logger.error(f"Error fetching barn details: {str(e)}")
        return jsonify({'error': 'Failed to fetch barn details'}), 500

@app.route('/api/barns', methods=['POST'])
@login_required
def create_barn():
    """Create a new barn"""
    try:
        user_id = session.get('user_id')
        user_doc = db.collection('users').document(user_id).get()
        farm_id = user_doc.to_dict().get('farm_id')
        
        # Handle both JSON and form data
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form
        
        # Validate required fields
        required_fields = ['name', 'capacity']
        if not all(field in data for field in required_fields):
            flash('Missing required fields', 'error')
            return redirect(url_for('barns_page')) if not request.is_json else jsonify({'error': 'Missing required fields'}), 400
            
        # Create barn document
        barn_data = {
            'name': data['name'],
            'capacity': int(data['capacity']),
            'current_count': 0,
            'farm_id': farm_id,
            'avg_weight': 0,
            'avg_age': 0,
            'health_score': 100,
            'status': 'active',
            'created_at': firestore.SERVER_TIMESTAMP,
            'updated_at': firestore.SERVER_TIMESTAMP,
            'created_by': user_id,
            'description': data.get('description', '')
        }
        
        # Add optional fields if provided
        optional_fields = ['location', 'barn_type']
        for field in optional_fields:
            if field in data:
                barn_data[field] = data[field]
                
        # Add the barn to Firestore
        new_barn = db.collection('barns').add(barn_data)
        barn_id = new_barn[1].id
        
        # Update farm's barn count
        db.collection('farms').document(farm_id).update({
            'barns_count': firestore.Increment(1)
        })
        
        flash('Barn created successfully!', 'success')
        
        # Return appropriate response based on request type
        if request.is_json:
            return jsonify({
                'message': 'Barn created successfully',
                'barn_id': barn_id
            }), 201
        else:
            return redirect(url_for('barns_page'))
        
    except Exception as e:
        logger.error(f"Error creating barn: {str(e)}")
        flash('Error creating barn: ' + str(e), 'error')
        if request.is_json:
            return jsonify({'error': 'Failed to create barn'}), 500
        else:
            return redirect(url_for('barns_page'))

@app.route('/api/barns/<barn_id>', methods=['PUT'])
@login_required
def edit_barn(barn_id):
    """Edit barn details"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401

        # Fetch barn
        barn_ref = db.collection('barns').document(barn_id)
        barn_doc = barn_ref.get()
        if not barn_doc.exists:
            return jsonify({'error': 'Barn not found'}), 404

        # Update barn with new data
        data = request.get_json()
        barn_ref.update(data)

        return jsonify({'success': True, 'message': 'Barn updated successfully!'})
    except Exception as e:
        logger.error(f"Error editing barn {barn_id}: {str(e)}")
        return jsonify({'error': 'Failed to edit barn', 'message': str(e)}), 500


@app.route('/api/barns/<barn_id>', methods=['DELETE'])
@login_required
def delete_barn(barn_id):
    """Delete a barn"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401

        # Check if the barn exists
        barn_ref = db.collection('barns').document(barn_id)
        barn_doc = barn_ref.get()
        if not barn_doc.exists:
            return jsonify({'error': 'Barn not found'}), 404

        # Soft delete: Update the status to 'deleted'
        barn_ref.update({'status': 'deleted'})

        return jsonify({'success': True, 'message': 'Barn deleted successfully!'})
    except Exception as e:
        logger.error(f"Error deleting barn {barn_id}: {str(e)}")
        return jsonify({'error': 'Failed to delete barn', 'message': str(e)}), 500

# Route to update barn metrics
@app.route('/api/barns/<barn_id>/metrics', methods=['POST'])
@login_required
def update_barn_metrics(barn_id):
    """Update barn metrics (animal count, weight, health, etc.)"""
    try:
        user_id = session.get('user_id')
        user_doc = db.collection('users').document(user_id).get()
        farm_id = user_doc.to_dict().get('farm_id')
        
        # Verify barn exists and belongs to user's farm
        barn_doc = db.collection('barns').document(barn_id).get()
        if not barn_doc.exists:
            return jsonify({'error': 'Barn not found'}), 404
            
        barn_data = barn_doc.to_dict()
        if barn_data.get('farm_id') != farm_id:
            return jsonify({'error': 'Unauthorized access'}), 403
            
        data = request.get_json()
        
        # Validate metrics data
        metrics = ['current_count', 'avg_weight', 'avg_age', 'health_score']
        update_data = {
            'updated_at': firestore.SERVER_TIMESTAMP,
            'updated_by': user_id
        }
        
        for metric in metrics:
            if metric in data:
                if not isinstance(data[metric], (int, float)):
                    return jsonify({'error': f'Invalid value for {metric}'}), 400
                update_data[metric] = data[metric]
                
        # Update the barn metrics
        db.collection('barns').document(barn_id).update(update_data)
        
        # Create metrics history record
        metrics_history = {
            'barn_id': barn_id,
            'farm_id': farm_id,
            'timestamp': firestore.SERVER_TIMESTAMP,
            'recorded_by': user_id,
            **{k: v for k, v in update_data.items() if k in metrics}
        }
        
        db.collection('barn_metrics_history').add(metrics_history)
        
        return jsonify({'message': 'Barn metrics updated successfully'})
        
    except Exception as e:
        logger.error(f"Error updating barn metrics: {str(e)}")
        return jsonify({'error': 'Failed to update barn metrics'}), 500

@app.route('/api/barns/weight-history')
@login_required
def get_weight_history():
    try:
        user_id = session.get('user_id')
        user_doc = db.collection('users').document(user_id).get()
        farm_id = user_doc.to_dict().get('farm_id')
        
        # Get the last 6 months of weight data from barn_metrics_history
        history_ref = db.collection('barn_metrics_history')\
                       .where('farm_id', '==', farm_id)\
                       .order_by('timestamp', direction=firestore.Query.DESCENDING)\
                       .limit(6)\
                       .stream()
                       
        history_data = []
        for doc in history_ref:
            data = doc.to_dict()
            history_data.append({
                'timestamp': data.get('timestamp'),
                'avg_weight': data.get('avg_weight', 0)
            })
            
        # Sort by timestamp
        history_data.sort(key=lambda x: x['timestamp'])
        
        return jsonify({
            'history': history_data
        })
        
    except Exception as e:
        logger.error(f"Error fetching weight history: {str(e)}")
        return jsonify({'error': 'Failed to fetch weight history'}), 500

##animals
# Add these routes to your app.py

@app.route('/api/animals', methods=['GET'])
@login_required
def get_animals():
    """Get all animals for the user's farm"""
    try:
        user_id = session.get('user_id')
        user_doc = db.collection('users').document(user_id).get()
        farm_id = user_doc.to_dict().get('farm_id')
        
        # Get query parameters for filtering
        barn_id = request.args.get('barn_id')
        status = request.args.get('status', 'active')
        
        # Create base query
        query = db.collection('animals').where('farm_id', '==', farm_id)
        
        # Add filters if provided
        if barn_id:
            query = query.where('barn_id', '==', barn_id)
        if status:
            query = query.where('status', '==', status)
            
        animals = [{
            'id': doc.id,
            **doc.to_dict()
        } for doc in query.stream()]
        
        return jsonify({'animals': animals})
        
    except Exception as e:
        logger.error(f"Error fetching animals: {str(e)}")
        return jsonify({'error': 'Failed to fetch animals'}), 500

@app.route('/api/animals', methods=['POST'])
@login_required
def add_animal():
    """Add a new animal"""
    try:
        user_id = session.get('user_id')
        user_doc = db.collection('users').document(user_id).get()
        farm_id = user_doc.to_dict().get('farm_id')
        
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['barn_id', 'tag_number', 'birth_date', 'species']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400
            
        # Verify barn belongs to farm
        barn_doc = db.collection('barns').document(data['barn_id']).get()
        if not barn_doc.exists or barn_doc.to_dict().get('farm_id') != farm_id:
            return jsonify({'error': 'Invalid barn ID'}), 400
            
        # Create animal document
        animal_data = {
            'farm_id': farm_id,
            'barn_id': data['barn_id'],
            'tag_number': data['tag_number'],
            'birth_date': data['birth_date'],
            'species': data['species'],
            'status': 'active',
            'health_status': 'healthy',
            'created_at': firestore.SERVER_TIMESTAMP,
            'created_by': user_id,
            'weight_history': [],
            'health_history': [],
            'notes': []
        }
        
        # Add optional fields
        optional_fields = ['breed', 'gender', 'color', 'notes']
        for field in optional_fields:
            if field in data:
                animal_data[field] = data[field]
                
        # Add the animal
        new_animal = db.collection('animals').add(animal_data)
        
        # Update barn count
        db.collection('barns').document(data['barn_id']).update({
            'current_count': firestore.Increment(1)
        })
        
        return jsonify({
            'message': 'Animal added successfully',
            'animal_id': new_animal[1].id
        }), 201
        
    except Exception as e:
        logger.error(f"Error adding animal: {str(e)}")
        return jsonify({'error': 'Failed to add animal'}), 500

@app.route('/api/animals/<animal_id>/weight', methods=['POST'])
@login_required
def add_weight_record(animal_id):
    """Add a weight record for an animal"""
    try:
        user_id = session.get('user_id')
        data = request.get_json()
        
        if 'weight' not in data:
            return jsonify({'error': 'Weight is required'}), 400
            
        weight_record = {
            'weight': float(data['weight']),
            'date': firestore.SERVER_TIMESTAMP,
            'recorded_by': user_id
        }
        
        # Add notes if provided
        if 'notes' in data:
            weight_record['notes'] = data['notes']
            
        # Update animal document
        animal_ref = db.collection('animals').document(animal_id)
        animal_ref.update({
            'current_weight': float(data['weight']),
            'weight_history': firestore.ArrayUnion([weight_record])
        })
        
        return jsonify({'message': 'Weight record added successfully'})
        
    except Exception as e:
        logger.error(f"Error adding weight record: {str(e)}")
        return jsonify({'error': 'Failed to add weight record'}), 500

@app.route('/api/animals/<animal_id>/health', methods=['POST'])
@login_required
def add_health_record(animal_id):
    """Add a health record for an animal"""
    try:
        user_id = session.get('user_id')
        data = request.get_json()
        
        required_fields = ['status', 'description']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400
            
        health_record = {
            'status': data['status'],
            'description': data['description'],
            'date': firestore.SERVER_TIMESTAMP,
            'recorded_by': user_id
        }
        
        # Add treatment if provided
        if 'treatment' in data:
            health_record['treatment'] = data['treatment']
            
        # Update animal document
        animal_ref = db.collection('animals').document(animal_id)
        animal_ref.update({
            'health_status': data['status'],
            'health_history': firestore.ArrayUnion([health_record])
        })
        
        return jsonify({'message': 'Health record added successfully'})
        
    except Exception as e:
        logger.error(f"Error adding health record: {str(e)}")
        return jsonify({'error': 'Failed to add health record'}), 500

@app.route('/api/animals/<animal_id>/transfer', methods=['POST'])
@login_required
def transfer_animal(animal_id):
    """Transfer animal to different barn"""
    try:
        user_id = session.get('user_id')
        user_doc = db.collection('users').document(user_id).get()
        farm_id = user_doc.to_dict().get('farm_id')
        
        data = request.get_json()
        
        if 'new_barn_id' not in data:
            return jsonify({'error': 'New barn ID is required'}), 400
            
        # Verify new barn belongs to farm
        new_barn_doc = db.collection('barns').document(data['new_barn_id']).get()
        if not new_barn_doc.exists or new_barn_doc.to_dict().get('farm_id') != farm_id:
            return jsonify({'error': 'Invalid barn ID'}), 400
            
        # Get animal current barn
        animal_doc = db.collection('animals').document(animal_id).get()
        if not animal_doc.exists:
            return jsonify({'error': 'Animal not found'}), 404
            
        old_barn_id = animal_doc.to_dict().get('barn_id')
        
        # Update animal's barn
        animal_doc.reference.update({
            'barn_id': data['new_barn_id'],
            'transfer_history': firestore.ArrayUnion([{
                'from_barn': old_barn_id,
                'to_barn': data['new_barn_id'],
                'date': firestore.SERVER_TIMESTAMP,
                'transferred_by': user_id,
                'notes': data.get('notes', '')
            }])
        })
        
        # Update barn counts
        db.collection('barns').document(old_barn_id).update({
            'current_count': firestore.Increment(-1)
        })
        
        db.collection('barns').document(data['new_barn_id']).update({
            'current_count': firestore.Increment(1)
        })
        
        return jsonify({'message': 'Animal transferred successfully'})
        
    except Exception as e:
        logger.error(f"Error transferring animal: {str(e)}")
        return jsonify({'error': 'Failed to transfer animal'}), 500

#############################
#@app.route('/barns')
#@login_required
#def barns_page():
    """Barns listing page"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('auth'))
            
        user_doc = db.collection('users').document(user_id).get()
        if not user_doc.exists:
            flash('User data not found.', 'error')
            return redirect(url_for('logout'))
            
        user_data = user_doc.to_dict()
        farm_id = user_data.get('farm_id')

        # Get all barns for the farm
        barns_ref = db.collection('barns')\
                     .where('farm_id', '==', farm_id)\
                     .where('status', '!=', 'deleted')\
                     .stream()
                     
        barns = []
        total_animals = 0
        total_capacity = 0
        
        for barn in barns_ref:
            barn_data = barn.to_dict()
            barn_data['id'] = barn.id
            
            # Update totals
            total_animals += barn_data.get('current_count', 0)
            total_capacity += barn_data.get('capacity', 0)
            
            # Get animal count trends (you would normally calculate this from historical data)
            current_count = barn_data.get('current_count', 0)
            last_week_count = current_count - 2  # Example change
            
            barn_data['count_change'] = current_count - last_week_count
            barns.append(barn_data)

        # Get active alerts count
        alerts_ref = db.collection('alerts')\
                      .where('farm_id', '==', farm_id)\
                      .where('status', '==', 'active')\
                      .stream()
        active_alerts = len(list(alerts_ref))

        return render_template('barns.html',
                             user=user_data,
                             barns=barns,
                             total_animals=total_animals,
                             total_capacity=total_capacity,
                             active_alerts=active_alerts)

    except Exception as e:
        logger.error(f"Error loading barns page: {str(e)}")
        flash('Error loading barns.', 'error')
        return redirect(url_for('dashboard'))

@app.route('/barn/<barn_id>')
@login_required
def barn_details(barn_id):
    """Barn details page"""
    try:
        user_id = session.get('user_id')
        user_doc = db.collection('users').document(user_id).get()
        farm_id = user_doc.to_dict().get('farm_id')
        
        # Get barn details
        barn_doc = db.collection('barns').document(barn_id).get()
        if not barn_doc.exists:
            flash('Barn not found.', 'error')
            return redirect(url_for('barns_page'))
            
        barn_data = barn_doc.to_dict()
        if barn_data.get('farm_id') != farm_id:
            flash('Unauthorized access.', 'error')
            return redirect(url_for('barns_page'))
            
        barn_data['id'] = barn_id
        
        # Get animals in this barn
        animals_ref = db.collection('animals')\
                       .where('barn_id', '==', barn_id)\
                       .where('status', '==', 'active')\
                       .stream()
                       
        animals = [{
            'id': animal.id,
            **animal.to_dict()
        } for animal in animals_ref]
        
        # Get recent activity
        activities = db.collection('barn_activities')\
                      .where('barn_id', '==', barn_id)\
                      .order_by('timestamp', direction=firestore.Query.DESCENDING)\
                      .limit(5)\
                      .stream()
                      
        recent_activities = [{
            'id': activity.id,
            **activity.to_dict()
        } for activity in activities]
        
        return render_template('barn_details.html', 
                             barn=barn_data, 
                             animals=animals,
                             activities=recent_activities)
                             
    except Exception as e:
        logger.error(f"Error loading barn details: {str(e)}")
        flash('Error loading barn details.', 'error')
        return redirect(url_for('barns_page'))

@app.route('/animal/<animal_id>')
@login_required
def animal_details(animal_id):
    """Animal details page"""
    try:
        user_id = session.get('user_id')
        user_doc = db.collection('users').document(user_id).get()
        farm_id = user_doc.to_dict().get('farm_id')
        
        # Get animal details
        animal_doc = db.collection('animals').document(animal_id).get()
        if not animal_doc.exists:
            flash('Animal not found.', 'error')
            return redirect(url_for('barns_page'))
            
        animal_data = animal_doc.to_dict()
        
        # Verify animal belongs to user's farm
        barn_doc = db.collection('barns').document(animal_data['barn_id']).get()
        if not barn_doc.exists or barn_doc.to_dict().get('farm_id') != farm_id:
            flash('Unauthorized access.', 'error')
            return redirect(url_for('barns_page'))
            
        animal_data['id'] = animal_id
        
        # Get barn details
        barn_data = barn_doc.to_dict()
        barn_data['id'] = animal_data['barn_id']
        
        # Get activity timeline
        activities = db.collection('animal_activities')\
                      .where('animal_id', '==', animal_id)\
                      .order_by('timestamp', direction=firestore.Query.DESCENDING)\
                      .limit(5)\
                      .stream()
                      
        timeline = [{
            'id': activity.id,
            **activity.to_dict()
        } for activity in activities]
        
        return render_template('animal_detail.html', 
                             animal=animal_data,
                             barn=barn_data,
                             timeline=timeline)
                             
    except Exception as e:
        logger.error(f"Error loading animal details: {str(e)}")
        flash('Error loading animal details.', 'error')
        return redirect(url_for('barns_page'))
    
###barn
@app.route('/barns')
@login_required
def barns_page():
    return render_template('barns.html')

# Add these routes to your app.py
@app.route('/analytics')
@login_required
def analytics():
    return render_template('analytics.html')  # Create this template

@app.route('/alerts')
@login_required
def alerts():
    return render_template('alerts.html')  # Create this template

@app.route('/settings')
@login_required
def settings():
    return render_template('settings.html')  # Create this template

@app.route('/live')
@login_required
def live():
    return render_template('live.html')

# Update error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {str(error)}")
    db.session.rollback()  # If you're using SQLAlchemy
    return render_template('errors/500.html'), 500

###########faceid
class PersonRecognitionSystem:
    def __init__(self):
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        self.db_folder = "face_database"
        if not os.path.exists(self.db_folder):
            os.makedirs(self.db_folder)

    def generate_person_id(self):
        return str(uuid.uuid4())[:8]  # ID corto y único

    def save_face_embedding(self, face_image, person_id):
        # Generar embedding facial usando DeepFace
        embedding = DeepFace.represent(face_image, model_name="VGG-Face", enforce_detection=False)
        
        # Guardar embedding en Firebase
        db.collection('face_embeddings').document(person_id).set({
            'embedding': embedding[0]['embedding'],
            'created_at': firestore.SERVER_TIMESTAMP
        })

        return embedding[0]['embedding']

    def find_similar_face(self, face_image):
        try:
            # Obtener embedding de la cara actual
            current_embedding = DeepFace.represent(face_image, model_name="VGG-Face", enforce_detection=False)
            
            # Obtener todos los embeddings guardados
            embeddings_ref = db.collection('face_embeddings').stream()
            
            for doc in embeddings_ref:
                stored_embedding = doc.to_dict()['embedding']
                # Comparar usando DeepFace
                result = DeepFace.verify(
                    img1_path=face_image,
                    img2_path=stored_embedding,
                    model_name="VGG-Face",
                    distance_metric="cosine"
                )
                
                if result["verified"]:
                    return doc.id  # Retorna el ID de la persona si hay match
                    
            return None  # No se encontró match
            
        except Exception as e:
            logger.error(f"Error in face comparison: {str(e)}")
            return None

    def process_frame(self, image_data):
        try:
            # Convertir base64 a imagen
            image_bytes = base64.b64decode(image_data.split(',')[1])
            nparr = np.frombuffer(image_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            # Detectar rostro
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(30, 30))

            if len(faces) == 0:
                return {
                    'success': False,
                    'error': 'No face detected'
                }

            x, y, w, h = faces[0]
            face = frame[y:y+h, x:x+w]

            # Buscar persona existente
            person_id = self.find_similar_face(face)
            is_new_person = person_id is None

            # Si es nueva persona, crear ID y guardar
            if is_new_person:
                person_id = self.generate_person_id()
                self.save_face_embedding(face, person_id)
                
                # Crear documento de persona en Firebase
                db.collection('persons').document(person_id).set({
                    'created_at': firestore.SERVER_TIMESTAMP,
                    'measurements_count': 0,
                    'last_seen': firestore.SERVER_TIMESTAMP
                })

            # Analizar edad y emoción
            analysis = DeepFace.analyze(face, actions=['age', 'emotion'], enforce_detection=False)[0]

            results = {
                'success': True,
                'person_id': person_id,
                'is_new_person': is_new_person,
                'age': analysis['age'],
                'emotion': analysis['dominant_emotion'],
                'emotion_confidence': max(analysis['emotion'].values()) / 100,
                'face_location': {
                    'x': int(x),
                    'y': int(y),
                    'width': int(w),
                    'height': int(h)
                },
                'timestamp': datetime.now().isoformat()
            }

            return results

        except Exception as e:
            logger.error(f"Error processing frame: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def save_measurement(self, data):
        try:
            person_id = data['person_id']
            
            # Crear documento de medición
            measurement_data = {
                'person_id': person_id,
                'timestamp': firestore.SERVER_TIMESTAMP,
                'age': data['age'],
                'emotion': data['emotion'],
                'emotion_confidence': data['emotion_confidence'],
                'barn_id': '1',  # Por ahora hardcoded
                # Aquí agregaremos weight, length, width cuando los tengamos
            }

            # Guardar medición
            measurement_ref = db.collection('measurements').add(measurement_data)

            # Actualizar documento de la persona
            person_ref = db.collection('persons').document(person_id)
            person_ref.update({
                'last_seen': firestore.SERVER_TIMESTAMP,
                'measurements_count': firestore.Increment(1),
                'last_measurement': measurement_data
            })

            return True, measurement_ref[1].id

        except Exception as e:
            logger.error(f"Error saving measurement: {str(e)}")
            return False, str(e)

# Inicializar sistema
recognition_system = PersonRecognitionSystem()

@app.route('/api/process-frame', methods=['POST'])
def process_frame():
    try:
        data = request.json
        image_data = data.get('image')

        if not image_data:
            return jsonify({'success': False, 'error': 'No image data provided'}), 400

        results = recognition_system.process_frame(image_data)
        return jsonify(results)

    except Exception as e:
        logger.error(f"Error in process_frame: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/save-measurement', methods=['POST'])
def save_measurement():
    try:
        data = request.json
        success, result = recognition_system.save_measurement(data)

        if success:
            return jsonify({
                'success': True,
                'measurement_id': result
            })
        else:
            return jsonify({
                'success': False,
                'error': result
            }), 500

    except Exception as e:
        logger.error(f"Error saving measurement: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


###########
class FaceAnalyzer:
    def __init__(self):
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

    def process_image(self, image_data):
        try:
            # Convertir base64 a imagen
            image_bytes = base64.b64decode(image_data.split(',')[1])
            nparr = np.frombuffer(image_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            # Convertir a escala de grises para detección facial
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Detectar rostros
            faces = self.face_cascade.detectMultiScale(
                gray, 
                scaleFactor=1.1, 
                minNeighbors=5, 
                minSize=(30, 30)
            )

            if len(faces) == 0:
                return {
                    'success': False,
                    'error': 'No face detected'
                }

            # Procesar el primer rostro encontrado
            x, y, w, h = faces[0]
            face = frame[y:y+h, x:x+w]

            # Analizar con DeepFace
            analysis = DeepFace.analyze(
                face, 
                actions=['age', 'emotion'], 
                enforce_detection=False
            )[0]

            # Extraer resultados
            results = {
                'success': True,
                'age': analysis['age'],
                'emotion': analysis['dominant_emotion'],
                'emotion_confidence': max(analysis['emotion'].values()) / 100,
                'face_location': {
                    'x': int(x),
                    'y': int(y),
                    'width': int(w),
                    'height': int(h)
                },
                'timestamp': datetime.now().isoformat()
            }

            return results

        except Exception as e:
            logger.error(f"Error processing image: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

# Inicializar analizador facial
face_analyzer = FaceAnalyzer()

@app.route('/live-monitoring')
def live_monitoring():
    return render_template('live.html')



if __name__ == '__main__':
    app.run(debug=True)