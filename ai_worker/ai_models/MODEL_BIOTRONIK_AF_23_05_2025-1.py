# -*- coding: utf-8 -*-
"""
Created on Thu May  8 10:10:48 2025

@author: larsv
"""

import logging

import xml.etree.ElementTree as ET

import numpy as np

from tensorflow.keras.models import load_model

import os

import soundfile as sf 

import datetime



logger = logging.getLogger(__name__)


class BIOTRONIK_AF:

    def __init__(self):

        current_dir = os.path.dirname(os.path.abspath(__file__))

        model_path = os.path.join(current_dir, 'BIOTRONIK_AF.h5') 

        

        logger.info(f"Tentative de chargement du modèle depuis: {model_path}")

        self.model = load_model(model_path, compile=False)

        logger.info("AI BIOTRONIK AF Model initialisé")

        try:

            logger.info("version de libsndfile: " + {sf.__libsndfile_version__})

        except:

            logger.error("Impossible de récupérer la version de libsndfile")



    async def inference(self, egm_data: bytes) -> dict:

        """Fonction d'inférence pour le modèle BIOTRONIK AF"""

        logger.info("Exécution de l'inférence BIOTRONIK AF")



        # Vérification de la validité de l'entrée

        if not egm_data or not egm_data.strip():

            raise ValueError("Données EGM vides ou invalides")





        # Get raw signals
            #TODO critical -> traceType: either 'TA' or 'Monitorage atrial' 
            # this information is needed and needs to be input!
        episode = BIOTRONIK_AF.extractInfoSVG( egm_data, traceType )

        # Preprocess the signal
            # normalize signal
            # get last 10 seconds or zero_padd untill 10 seconds

        if 'ATrace' in episode:
            
            atrial_signal = BIOTRONIK_AF.normalize( episode['ATrace'] )
            
            atrial_signal = BIOTRONIK_AF.updateTraceLength( atrial_signal )
            
        if 'VTrace' in episode:
            
            ventricular_signal = BIOTRONIK_AF.normalize( episode['VTrace'] )
            
        elif 'VDTrace' in episode:
            
            ventricular_signal = BIOTRONIK_AF.normalize( episode['VDTrace'] )
            
        else:
            ventricular_signal = np.zeros_like( atrial_signal )
 
        ventricular_signal = BIOTRONIK_AF.updateTraceLength( ventricular_signal )
 
 
        input_model = np.stack( ( atrial_signal, ventricular_signal ), axis=1 ).reshape(1, 1280, 2) 
        
        raw_prediction = self.model.predict( input_model )  
        
        confidence = np.max( raw_prediction ) #TODO can be added to output
        
        prediction = np.argmax( raw_prediction, axis=1 )
       
        #TODO UPDATED - overrule prediction
        #if no signal was able to get extracted from the episode
        # overrule the prediction and show error.
        if atrial_signal.size < 1:  
            
            prediction = 3
       
        
        # Correspondance des prédictions numériques aux étiquettes textuelles

        prediction_labels = {

            0: "TA/FA",

            1: "Noise",

            2: "Oversensing",
            
            3: "Error: no signal found" #TODO UPDATED - new classification to show error

        }



        # Conversion en entier avant la correspondance

        if isinstance(prediction, np.ndarray):

            logger.error(f"Type incorrect de prédiction: {type(prediction)} -> {prediction}")



        prediction_text = prediction_labels.get(prediction, "Unknown")

        logger.info(f"Prédiction obtenue: {prediction_text}")



        return {

            "prediction": prediction_text,

            "confidence": 1.0, #TODO can be added if needed, information is provided above

            "model_type": "BIOTRONIK AF",

            "timestamp": str(datetime.datetime.now().isoformat()),

            "details": {}  # Ajout du champ 'details'

        }


    def getFileInfo(fileType, root):
        
        allElements = [elem for elem in root.iter()]
        textElements = []
        textElementsIndices = []
        for i in range(0, len(allElements) ):
            element = allElements[i]
            if element.tag.endswith('text'):
                textElements.append(element)
                textElementsIndices.append(i) 
        textElementsText = [text.text for text in textElements]
        
        if fileType == 'Monitorage atrial': #TODO UPDATED 4 lines below
            if 'Prédétection' in textElementsText: 
                pageSearch = 'Prédétection'
            elif 'Monitorage atrial' in textElementsText:
                pageSearch = 'Monitorage atrial'
        elif fileType == 'TA':
            pageSearch = 'TA'
        elif fileType == 'Commut. Mode':
            pageSearch = 'Commut. Mode'
        elif fileType == 'EGM périodique':
            if 'Normal' in textElementsText:
                pageSearch = 'Normal'
            elif 'Périodique' in textElementsText:
                pageSearch = 'Périodique'
            else:
                print(textElementsText)
                raise ValueError('There is another version of EGM périodique')
                
        return pageSearch, textElements, textElementsText, textElementsIndices, allElements

    def definePacemakerEpisode(root, textElements, pageSearch):
    
        aLead = False
        vLead = False
        vdLead = False
        vgLead = False
        aMarker = False
        vMarker = False
        vdMarker = False
        vgMarker = False
        FF = False
        pageMarks = []
        nBiotronik = 0
        nPagesInterest = 0
        
        i = 0
        acount = 0
        vcount = 0
        vdcount = 0
        vgcount = 0
        for text in textElements:
            
            if text == 'A':
                acount += 1
                aMarker = True
            elif text == 'V':
                vcount += 1
                vMarker = True
            elif text == 'VD':
                vdcount += 1
                vdMarker = True
            elif text == 'VG':
                vgcount += 1
                vgMarker = True
            elif text == 'FF':
                FF = True
            elif text == 'BIOTRONIK':
                nBiotronik += 1
                pageMarks.append(i)
            elif text == pageSearch:
                nPagesInterest += 1
            i += 1
            
        # if count < nBiotronik (n pages) -> only markers no tracing
        if acount > nBiotronik: aLead = True 
        if vcount > nBiotronik: vLead = True 
        if vgcount > nBiotronik: vgLead = True 
        if vdcount > nBiotronik: vdLead = True
        
        return [aLead, vLead, vdLead, vgLead], [aMarker, vMarker, vdMarker, vgMarker], FF, nBiotronik, pageMarks, nPagesInterest

    def findTraceElements(allElements, pageMarksTextElements, nameSpace, nPages, Leads):
        text_count = 0
        pageMarksAllElements = []
        
        #find the 'Biotronik' page indices in all_elements
        for i in range( len( allElements ) ): 
            if allElements[i].tag == f"{{{nameSpace['svg']}}}text": 
                if text_count in pageMarksTextElements:
                    pageMarksAllElements.append(i)
                text_count += 1
        pageMarksAllElements = np.array( pageMarksAllElements ) 
        
        traceElements = []
        for i in range( len( pageMarksAllElements ) ):
    
            if i == ( len( pageMarksAllElements )-1):
                begin = pageMarksAllElements[i]
                end = len( allElements )-1
            else:
                begin = pageMarksAllElements[i]
                end = pageMarksAllElements[i+1]
            
            #find the g elements containing the traces
            gLength = 0
            gElement = []
            for k in range(begin,end):
                if allElements[k].tag.endswith('g'):
                    if len(allElements[k]) > gLength:
                        gLength = len(allElements[k])
                        gElement = allElements[k]
            traceElements.append(gElement)
        
        ALocY = []
        countY = 0
        
        if Leads[0]:
            search = 'A'
        elif Leads[1]:
            search = 'V'
        elif Leads[2]:
            search = 'VD'
        elif Leads[3]:
            search = 'VG'
            
        if nPages > 1:
            for i in range( len( allElements)):
                if allElements[i].tag == f"{{{nameSpace['svg']}}}text": 
                    if allElements[i].text == search and countY < 5:
                        ALocY.append( int( allElements[i].attrib['y']) )
                        countY += 1
            pageHeight = ALocY[3] - ALocY[1]
        else:
            pageHeight = 0
        
        return traceElements, pageHeight

    def getRawTracings(nLeads, Leads, FFSignal, elementG, firstPage, page, pageheight, offsetY):
    
        x = []
        y = []
        
        for i in range(len(elementG)):
            x.append( int( elementG[i].attrib['x1'] ) )
            y.append( int( elementG[i].attrib['y1'] ) )
    
        x = np.array(x)
        y = np.array(y)
    
        indices = np.where(np.diff(np.sign(np.gradient(x))))[0] 
        pageHeight = pageheight
        Traces = [np.empty(0)] * 5
    
        if len(indices) > 0 and indices[0] == 0:
            indices = indices[1:]
    
        if firstPage:
            offset = 5
            offsetPage = 0
            offsetY = y[0]
        else:
            offset = 0
            offsetPage = 1
        
        if len(indices) < 1: #one lead trace on page
        
            Trace1 = y
            Trace1 = (Trace1 - (offsetY + offsetPage*page*pageHeight) )*-1 
            
            leadCombinations = {0: 1, 1: 2, 2: 3, 3: 4}
            
            for lead, index in leadCombinations.items():
                if Leads[lead]:
                    Traces[index] = Trace1[offset:]
                    return Traces, int(x[offset + 2]), offsetY
    
            raise ValueError('There is only one lead but not A, V, VD or VG')
    
        elif len(indices) < 3: #two traces on page
            
            if FFSignal: #one lead trace and one far field trace
            
                FFTrace = y[ :indices[1] ]
                FFTrace = (FFTrace - (offsetY + offsetPage*page*pageHeight) )*-1 
                
                Trace1 = y[ indices[1]: ]
                Trace1 = (Trace1 - (offsetY + 100 + offsetPage*page*pageHeight) )*-1 
                
                leadCombinations = {0: 1, 1: 2, 2: 3, 3: 4}
    
                for lead, index in leadCombinations.items():
                    if Leads[lead]:
                        Traces[0] = FFTrace[offset:]
                        Traces[index] = Trace1[offset:]
                        return Traces, int(x[offset + 2]), offsetY
                            
                raise ValueError('There is only one lead but not A, V, VD or VG')
    
            else: #no far field so two lead traces
        
                Trace1 = y[ :indices[1] ]
                Trace1 = (Trace1 - (offsetY + offsetPage*page*pageHeight) )*-1 
                
                Trace2 = y[ indices[1]: ]
                Trace2 = (Trace2 - (offsetY + 100 + offsetPage*page*pageHeight) )*-1 
                
                leadCombinations = {
                                    (0, 1): (1, 2),  # A V Lead
                                    (0, 2): (1, 3),  # A VD Lead
                                    (0, 3): (1, 4),  # A VG Lead
                                    # (1, 2): (2, 3),  # V VD Lead #bs
                                    # (1, 3): (2, 4),  # V VG Lead #bs
                                    (2, 3): (3, 4),  # VD VG Lead
                                    }
    
                for (lead1, lead2), (idx1, idx2) in leadCombinations.items():
                    if Leads[lead1] and Leads[lead2]:
                        Traces[idx1] = Trace1[offset:]
                        Traces[idx2] = Trace2[offset:]
                        return (Traces, int(x[offset + 2]), offsetY)
                
        else: #there are 3 traces
        
            if FFSignal: #one of the 3 traces is far field signal
    
                FFTrace = y[  : indices[1] ]
                FFTrace = (FFTrace - (offsetY + offsetPage*page*pageHeight) )*-1 # + offsetPage*(148 + 445*page)
                
                Trace1 = y[ indices[1] : indices[3] ]
                Trace1 = (Trace1 - (offsetY + 100 + offsetPage*page*pageHeight) )*-1 #+ offsetPage*(248 + 445*page)
                
                Trace2 = y[ indices[3] : ]
                Trace2 = (Trace2 - (offsetY + 200 + offsetPage*page*pageHeight) )*-1
        
                leadCombinations = {
                                    (0, 1): (1, 2),  # A V Lead
                                    (0, 2): (1, 3),  # A VD Lead
                                    (0, 3): (1, 4),  # A VG Lead
                                    (2, 3): (3, 4),  # VD VG Lead
                                    }
    
                for (lead1, lead2), (idx1, idx2) in leadCombinations.items():
                    if Leads[lead1] and Leads[lead2]:
                        Traces[0] = FFTrace[offset:]
                        Traces[idx1] = Trace1[offset:]
                        Traces[idx2] = Trace2[offset:]
                        return (Traces, int(x[offset + 2]), offsetY) 
                    
            else: #no far field signal, all 3 traces are lead traces -> Always A VD VG leads
            
                Trace1 = y[ : indices[1] ]
                Traces[1] = ( ( Trace1 - (offsetY + offsetPage*page*pageHeight) )*-1 )[offset:]
                
                Trace2 = y[ indices[1] : indices[3] ]
                Traces[3] = ( (Trace2 - (offsetY + 100 + offsetPage*page*pageHeight) )*-1 )[offset:]
    
                Trace3 = y[ indices[3] : ]
                Traces[4] = ( (Trace3 - (offsetY + 200 + offsetPage*page*pageHeight) )*-1 )[offset:]
                
                return (Traces, int(x[offset + 2]), offsetY)

    # function get information from SVG file
    def extractInfoSVG( svgFile, fileType, center = [] ):
        #load the svg file and extract important elements (G and text elements)
        tree = ET.parse(svgFile)
        root = tree.getroot()
        nameSpace = {'svg': root.tag.split('}')[0].strip('{')}
        
        (pageSearch, textElements, textElementsText, textElementsIndices,
         allElements) = BIOTRONIK_AF.getFileInfo(fileType, root)
        
        #explore and define the pacemaker and pacemaker episode
        (Leads, Marker, FFSignal, nPages, 
         pageMarks, nPagesInterest) = BIOTRONIK_AF.definePacemakerEpisode(root,
                                                                     textElementsText,
                                                                     pageSearch)
        nLeads = np.sum(Leads)
        
        episodeInfo = {}
        episodeInfo['NLeads'] = nLeads
        
        if len(center) > 0:
            episodeInfo['Center'] = center
        
        #find the gElements containing the trace information of the leads
        gElements, pageHeight = BIOTRONIK_AF.findTraceElements(allElements, pageMarks, nameSpace, 
                                                          nPages, Leads)
        
        #define the pages to look through
        pagesInterest = np.arange(nPagesInterest)
    
        TracesFinal = [np.empty(0)] * 5 # 5 possible traces: FF, A, V, VD, VG
        offsetY = 0
        
        #look through pages of interest
        for page in pagesInterest:
            if page == pagesInterest[0]:
                firstPage = True
            else:
                firstPage = False
    
            elementG = gElements[page]
            Traces, AStartX, offsetY = BIOTRONIK_AF.getRawTracings(nLeads, 
                                                              Leads,
                                                              FFSignal, 
                                                              elementG, 
                                                              firstPage,
                                                              page,
                                                              pageHeight,
                                                              offsetY)
            
            #update information
            for i in range(5):
                TracesFinal[i] = np.concatenate((TracesFinal[i], Traces[i]))
        
        #return found tracings and markings in episode
        if FFSignal:
            episodeInfo['FFTrace'] = TracesFinal[0]
        if Leads[0]:
            episodeInfo['ATrace'] = TracesFinal[1]
        if Leads[1]:
            episodeInfo['VTrace'] = TracesFinal[2]
        if Leads[2]:
            episodeInfo['VDTrace'] = TracesFinal[3]
        if Leads[3]:
            episodeInfo['VGTrace'] = TracesFinal[4]
        
        return episodeInfo
    
    def normalize(signal):
        # normalize from -1 to 1
        max_signal = np.max( np.abs( signal ) )
        epsilon = 1e-8  # A small value to avoid division by zero
        return signal / (max_signal+epsilon)
    
    def updateTraceLength(signal, fs = 128, min_len = 10):
        if len(signal) < fs*min_len: #signal is shorter than 10 sec
            padding_length = fs*min_len - len(signal)
            padded_signal = np.pad(signal, (padding_length, 0), mode='constant')
            return padded_signal
        
        elif len(signal) > fs*min_len: #signal is longer than 10 sec
            return signal[-(fs*min_len):]
        else:
            return signal #signal is exactly 10 sec


def register_model(registry):

    """Enregistre le modèle dans le registre"""

    try:

        model = BIOTRONIK_AF()

        registry._models["BIOTRONIK_AF"] = {

            "inference_fn": model.inference,

            "manufacturer": "test",

            "episode_types": ["test"],

            "version": "1.0.0"

        }

        logger.info("BIOTRONIK_AF Model enregistré avec succès")

    except Exception as e:

        logger.error(f"Erreur lors de l'enregistrement du BIOTRONIK_AF Model: {str(e)}")