     
// Estado del sistema
const state = {
    isActive: false,
    isProcessing: false,
    isCooldown: false,
    countdownActive: false
};

// Referencias DOM
const elements = {
    video: document.getElementById('videoFeed'),
    overlay: document.getElementById('overlay'),
    startButton: document.getElementById('startButton'),
    stopButton: document.getElementById('stopButton'),
    processingIndicator: document.getElementById('processingIndicator'),
    countdownIndicator: document.getElementById('countdownIndicator'),
    cooldownIndicator: document.getElementById('cooldownIndicator'),
    faceStatus: document.getElementById('faceStatus'),
    countdownValue: document.getElementById('countdownValue'),
    // Valores de medición
    subjectId: document.getElementById('subjectId'),
    lastUpdate: document.getElementById('lastUpdate'),
    ageValue: document.getElementById('ageValue'),
    emotionValue: document.getElementById('emotionValue')
};

const ctx = elements.overlay.getContext('2d');

// Configuración
const CONFIG = {
    COUNTDOWN_TIME: 5,
    COOLDOWN_TIME: 10,
    CHECK_INTERVAL: 500
};

// Funciones principales
async function startCamera() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ 
            video: { width: 1280, height: 720 } 
        });
        elements.video.srcObject = stream;
        await elements.video.play();
        
        elements.startButton.classList.add('hidden');
        elements.stopButton.classList.remove('hidden');
        state.isActive = true;
        
        // Iniciar monitoreo de rostros
        startFaceMonitoring();
    } catch (error) {
        console.error('Error accessing camera:', error);
        alert('Error accessing camera. Please check permissions.');
    }
}

function stopCamera() {
    if (elements.video.srcObject) {
        elements.video.srcObject.getTracks().forEach(track => track.stop());
        elements.video.srcObject = null;
    }
    
    elements.startButton.classList.remove('hidden');
    elements.stopButton.classList.add('hidden');
    state.isActive = false;
    
    // Limpiar estado e indicadores
    resetState();
}

function resetState() {
    state.isProcessing = false;
    state.isCooldown = false;
    state.countdownActive = false;
    
    elements.processingIndicator.classList.add('hidden');
    elements.countdownIndicator.classList.add('hidden');
    elements.cooldownIndicator.classList.add('hidden');
    elements.faceStatus.classList.add('hidden');
    
    ctx.clearRect(0, 0, elements.overlay.width, elements.overlay.height);
}

async function startFaceMonitoring() {
    while (state.isActive) {
        if (!state.isProcessing && !state.isCooldown && !state.countdownActive) {
            const faceCheck = await checkFaces();
            
            if (faceCheck.success) {
                elements.faceStatus.classList.add('hidden');
                startCountdown();
            } else {
                elements.faceStatus.classList.remove('hidden');
            }
        }
        await new Promise(resolve => setTimeout(resolve, CONFIG.CHECK_INTERVAL));
    }
}

function startCountdown() {
    state.countdownActive = true;
    let count = CONFIG.COUNTDOWN_TIME;
    
    elements.countdownIndicator.classList.remove('hidden');
    elements.countdownValue.textContent = count;
    
    const countdownInterval = setInterval(() => {
        count--;
        elements.countdownValue.textContent = count;
        
        if (count === 0) {
            clearInterval(countdownInterval);
            elements.countdownIndicator.classList.add('hidden');
            state.countdownActive = false;
            captureAndProcess();
        }
    }, 1000);
}

async function checkFaces() {
    try {
        const imageData = captureFrame();
        const response = await fetch('/api/process-frame', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                image: imageData,
                check_only: true 
            })
        });
        
        return await response.json();
    } catch (error) {
        console.error('Error checking faces:', error);
        return { success: false, error: 'Error checking faces' };
    }
}

function captureFrame() {
    const canvas = document.createElement('canvas');
    canvas.width = elements.video.videoWidth;
    canvas.height = elements.video.videoHeight;
    const context = canvas.getContext('2d');
    context.drawImage(elements.video, 0, 0);
    return canvas.toDataURL('image/jpeg');
}

async function captureAndProcess() {
    if (state.isProcessing) return;
    
    try {
        state.isProcessing = true;
        elements.processingIndicator.classList.remove('hidden');
        
        // Capturar imagen
        const imageData = captureFrame();
        
        // Procesar imagen para análisis facial
        const response = await fetch('/api/process-frame', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image: imageData })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Actualizar UI con datos del análisis facial
            updateUI(data);
            
            // Calcular medidas simuladas (esto se reemplazará con tus cálculos reales)
            const measurements = calculateMeasurements(data.face_location);
            
            // Combinar datos de análisis facial con medidas físicas
            const measurementData = {
                person_id: data.person_id,
                is_new_person: data.is_new_person,
                age: data.age,
                emotion: data.emotion,
                emotion_confidence: data.emotion_confidence,
                weight: measurements.weight,
                height: measurements.height,
                width: measurements.width,
                face_location: data.face_location,
                timestamp: new Date().toISOString()
            };
            
            // Guardar medición completa
            const saveResponse = await fetch('/api/save-measurement', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(measurementData)
            });
            
            const saveResult = await saveResponse.json();
            
            if (saveResult.success) {
                showNotification('Measurement saved successfully', 'success');
            } else {
                throw new Error(saveResult.error);
            }
            
            // Iniciar período de cooldown
            startCooldown();
        }
    } catch (error) {
        console.error('Error in capture and process:', error);
        showNotification('Error processing measurement', 'error');
    } finally {
        state.isProcessing = false;
        elements.processingIndicator.classList.add('hidden');
    }
}


// Función para calcular mediciones basadas en el tamaño del rostro
// Esta es una función de ejemplo - deberás implementar tus propios cálculos
function calculateMeasurements(faceLocation) {
    if (!faceLocation) return { weight: 0, height: 0, width: 0 };
    
    // Estos cálculos son ejemplos y deberán ser reemplazados con tu lógica real
    const faceWidth = faceLocation.width;
    const faceHeight = faceLocation.height;
    
    // Ejemplo de cálculos simulados basados en las dimensiones del rostro
    const estimatedHeight = faceHeight * 7.5; // Factor de proporción ejemplo
    const estimatedWidth = faceWidth * 3;     // Factor de proporción ejemplo
    const estimatedWeight = (estimatedHeight * estimatedWidth) / 400; // Fórmula ejemplo
    
    return {
        weight: Math.round(estimatedWeight * 10) / 10, // Redondear a 1 decimal
        height: Math.round(estimatedHeight),
        width: Math.round(estimatedWidth)
    };
}

// Función para mostrar notificaciones
function showNotification(message, type = 'success') {
    const notification = document.createElement('div');
    notification.className = `fixed bottom-4 right-4 p-4 rounded-lg ${
        type === 'success' ? 'bg-green-500' : 'bg-red-500'
    } text-white shadow-lg transform transition-transform duration-300 ease-in-out`;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.remove();
    }, 3000);
}

function updateUI(data) {
    elements.subjectId.textContent = data.person_id;
    elements.lastUpdate.textContent = new Date().toLocaleTimeString();
    elements.ageValue.textContent = Math.round(data.age);
    elements.emotionValue.textContent = data.emotion;
    
    if (data.face_location) {
        drawFaceBox(data.face_location);
    }
}

function drawFaceBox(location) {
    ctx.clearRect(0, 0, elements.overlay.width, elements.overlay.height);
    ctx.strokeStyle = '#00ff00';
    ctx.lineWidth = 2;
    ctx.strokeRect(location.x, location.y, location.width, location.height);
}

async function saveMeasurement(data) {
    try {
        await fetch('/api/save-measurement', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
    } catch (error) {
        console.error('Error saving measurement:', error);
    }
}

function startCooldown() {
    state.isCooldown = true;
    elements.cooldownIndicator.classList.remove('hidden');
    
    setTimeout(() => {
        state.isCooldown = false;
        elements.cooldownIndicator.classList.add('hidden');
    }, CONFIG.COOLDOWN_TIME * 1000);
}

// Event Listeners
elements.startButton.addEventListener('click', startCamera);
elements.stopButton.addEventListener('click', stopCamera);

// Cleanup
window.addEventListener('beforeunload', stopCamera);