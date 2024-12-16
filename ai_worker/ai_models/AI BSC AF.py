import logging
from lxml import etree
import numpy as np
from scipy.interpolate import interp1d
import matplotlib.pyplot as plt
from tensorflow.keras.models import load_model
import librosa
import os

logger = logging.getLogger(__name__)

class AIBSCModel:
    def __init__(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(current_dir, 'AImodel_BSC_AF.h5')
        
        logger.info(f"Tentative de chargement du modèle depuis: {model_path}")
        self.model = load_model(model_path, compile=False)
        logger.info("AIBSCModel initialisé")

    async def inference(self, egm_data: bytes) -> dict:
        """Fonction d'inférence pour le modèle AI BSC AF"""
        logger.info("Exécution de l'inférence AI BSC AF")

        # Parse the XML content of the SVG file
        tree = etree.fromstring(egm_data)

        # Find the polyline with the stroke color #396BA5
        ra_signal = []

        # Look for all 'polyline' elements in the SVG that have a 'stroke' attribute set to '#396BA5'
        for polyline in tree.findall(".//{http://www.w3.org/2000/svg}polyline"):
            stroke = polyline.get('stroke')
            if stroke == '#396BA5':  # Blue signal color code
                points = polyline.get('points')  # Extract the points attribute
                ra_signal.extend(points.split())  # Split the points by space and add to the list

        # Initialize lists for RAt (X values) and RA (Y values)
        RAt = []
        RA = []

        # Loop over each pair and split into X (RAt) and Y (RA)
        for pair in ra_signal:
            x, y = map(float, pair.split(','))  # Split on comma and convert to float
            RAt.append(x)
            RA.append(y)

        # Convert to numpy arrays
        RAt = np.array(RAt)
        RAt = RAt * 10
        RA = np.array(RA)

        # Step 1: Shift RAt so it starts from 1
        RAt_shifted = RAt - RAt[0] + 1

        # Step 2: Interpolate the RA signal
        # Define the new X values from 1 to the last value of the shifted RAt
        X1_new = np.arange(1, int(RAt_shifted[-1]) + 1)

        # Perform the interpolation using 'linear' method
        interpolator = interp1d(RAt_shifted, RA, kind='linear', fill_value="extrapolate")

        # Calculate the interpolated signal at the new X1 values
        Y1_new = interpolator(X1_new)

        # Step 1: Extract the first 10000 points
        X1_new_10000 = X1_new[:9995]
        Y1_new_10000 = Y1_new[:9995]

        # Step 2: Normalize the Y values (Y1_new_10000) from 0 to 1
        ra_signal_array = (Y1_new_10000 - np.min(Y1_new_10000)) / (np.max(Y1_new_10000) - np.min(Y1_new_10000))

        # Preprocess the signal
        preprocessed_signal = self.preprocess_single_episode(ra_signal_array)

        # Make a prediction with the loaded model
        prediction = (self.model.predict(preprocessed_signal) > 0.5).astype("int32")

        return {
            "prediction": int(prediction[0][0]),
            "confidence": 1.0,
            "model_type": "AI BSC AF",
            "timestamp": "2024-03-21",
            "details": {}  # Ajout du champ 'details'
        }

    def preprocess_single_episode(self, ra_signal1, sr=1000, n_fft=256, hop_length=128):
        """Preprocess and convert a single episode signal to a spectrogram"""
        S = librosa.stft(ra_signal1, n_fft=n_fft, hop_length=hop_length)
        S_db = librosa.amplitude_to_db(np.abs(S))
        S_db_expanded = np.expand_dims(S_db, axis=-1)
        S_db_expanded = np.expand_dims(S_db_expanded, axis=0)
        return S_db_expanded

def register_model(registry):
    """Enregistre le modèle dans le registre"""
    try:
        model = AIBSCModel()
        registry._models["ai_bsc_af"] = {
            "inference_fn": model.inference,
            "manufacturer": "test",
            "episode_types": ["test"],
            "version": "1.0.0"
        }
        logger.info("AIBSCModel enregistré avec succès")
    except Exception as e:
        logger.error(f"Erreur lors de l'enregistrement du AIBSCModel: {str(e)}")