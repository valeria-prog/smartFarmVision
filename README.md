# SmartFarmVision

## Description  
SmartFarmVision is an AI-driven application designed to automate livestock identification and weight estimation using computer vision techniques. The current phase simulates livestock using human subjects for data collection and model validation. The project leverages advanced AI technologies such as a **VGG model** for subject identification, **DeepFace** for age and emotion analysis, and **MediaPipe** for height detection. Additionally, a custom-built **Arduino-based scale** captures real-time weight data.

---

## Core Technologies:
- **Python**: Main programming language for backend development.
- **Flask**: Lightweight web framework for serving the application.
- **Firebase**: Real-time database management and authentication.
- **OpenCV**: Image processing and feature extraction.
- **TensorFlow/Keras**: Framework for building and training machine learning models.
- **Tailwind CSS**: For designing a modern, responsive web interface.

---

## Specialized Libraries and Models:
### VGG Model (Visual Geometry Group)  
- **Function**: Classifies subjects based on image data.  
- **Architecture**: Deep convolutional neural network (CNN) for feature extraction.  
- **Usage**: Trained on human images to simulate livestock identification, leveraging transfer learning for accurate recognition.

### DeepFace  
- **Function**: Predicts age and emotion from facial images.  
- **Integration**: Provides contextual data (age, emotion) to enhance identification accuracy and weight estimation.

### MediaPipe  
- **Function**: Detects body landmarks and calculates height from images.  
- **Usage**: Supplies body metrics crucial for weight estimation models.

---

## Hardware Integration:
### Custom-Built Scale (Arduino-Based)  
- **Arduino IDE**: Used to program the microcontroller.  
- **Components**: Load cells, HX711 weight sensor module, and Arduino board.  
- **Functionality**:  
  - Captures real-time weight data.  
  - Sends data to the Flask application via serial communication.  
- **Workflow**:  
  - The Arduino processes load cell data through the HX711 module and transmits it to the main application.  
  - The weight data is combined with visual inputs for a comprehensive analysis.

---

## Features:
1. **Automated Identification (VGG Model)**  
   - Classifies subjects using image data and deep feature extraction.  
   - Provides accurate recognition in simulated livestock scenarios.

2. **Weight Estimation**  
   - Combines visual metrics (height, body proportions) with real-time weight data from the custom-built scale.  
   - Regression models predict weight based on combined inputs.

3. **Age and Emotion Analysis**  
   - Utilizes DeepFace to analyze facial features and predict age and emotional state.  

4. **Data Visualization Dashboard**  
   - Displays identification results, estimated weight, age, and emotional state.  
   - Provides real-time updates with dynamic charts and metrics.

5. **Web-Based Interface**  
   - Built with Tailwind CSS for a clean, responsive user experience.  
   - Allows easy data input, image uploads, and result viewing.

---

## Project Structure:
```plaintext
smartFarmVision-main/
│
├── app.py                # Main application script
├── requirements.txt      # Project dependencies
├── templates/            # HTML templates styled with Tailwind CSS
│   └── index.html
│
├── static/               # Static files (Tailwind CSS, JavaScript)
│   └── main.css
│
└── firebase-adminsdk.json # Firebase configuration file
