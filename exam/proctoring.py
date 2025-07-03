# exam/proctoring.py
from .ai_models import decode_image, compare_face, detect_objects_yolo, detect_movement
import cv2
import numpy as np # Import numpy if not already imported
import traceback # <--- IMPORT ADDED HERE

def process_proctoring(frame_data, registered_face_path, prev_frame_data=None):
    """
    Process a live frame for proctoring:
      - Decode the current frame.
      - Load the candidate's registered face image.
      - Perform face comparison, object detection, and movement analysis.
    Returns a dictionary with keys: 'face_match', 'objects', and 'movement'.
    Ensures boolean values are Python standard bools for JSON serialization.
    """
    current_frame = None
    registered_face_img = None
    face_match_result = False # Default to Python False
    objects_found = []
    movement_status = "normal" # Default status

    print("[DEBUG] process_proctoring started.") # Add debug print #

    # Decode current frame safely
    try:
        current_frame = decode_image(frame_data)
        if current_frame is None:
            print("[ERROR] Failed to decode current frame data in process_proctoring.") #
            # Return early or handle as appropriate, maybe raise an error?
            # For now, let's return default values but log the error.
            return {
                "face_match": face_match_result, # Python bool
                "objects": objects_found,
                "movement": movement_status,
                "error": "Failed to decode current frame"
            }
        # print("[DEBUG] Current frame decoded successfully.")
    except Exception as e:
        print(f"[ERROR] Exception decoding current frame in process_proctoring: {e}") #
        print(traceback.format_exc()) # <--- Uses traceback #
        # Decide how to handle this - return error state?
        return {
            "face_match": face_match_result,
            "objects": objects_found,
            "movement": movement_status,
            "error": f"Exception decoding frame: {e}"
         }

    # Load registered face image safely
    try:
        registered_face_img = cv2.imread(registered_face_path)
        if registered_face_img is None:
            print(f"[WARN] Registered face image not found or could not be read at: {registered_face_path}") #
            # Proceed without face comparison, or return an error state?
            # Let's proceed for now, face_match_result remains False
        # else:
            # print("[DEBUG] Registered face image loaded successfully.")
    except Exception as e:
        print(f"[ERROR] Exception reading registered face image '{registered_face_path}': {e}") #
        print(traceback.format_exc()) # <--- Uses traceback #
        # Proceed without face comparison

    # Perform face comparison only if both images are valid
    if current_frame is not None and registered_face_img is not None:
        try:
            # print("[DEBUG] Comparing faces...")
            # compare_face returns numpy.bool_, convert it here
            numpy_face_match = compare_face(current_frame, registered_face_img)
            face_match_result = bool(numpy_face_match) # *** FIX: Convert numpy.bool_ to Python bool ***
            # print(f"[DEBUG] Face comparison result (Python bool): {face_match_result}")
        except Exception as e:
             print(f"[ERROR] Exception during face comparison: {e}") #
             print(traceback.format_exc()) # <--- Uses traceback #
             # face_match_result remains False

    # Detect objects
    if current_frame is not None:
        try:
            # print("[DEBUG] Detecting objects...")
            objects_found = detect_objects_yolo(current_frame)
            # print(f"[DEBUG] Objects detected: {objects_found}")
        except Exception as e:
             print(f"[ERROR] Exception during object detection: {e}") #
             print(traceback.format_exc()) # <--- Uses traceback #
             # objects_found remains empty list

    # Detect movement
    if current_frame is not None and prev_frame_data:
        prev_frame = None
        try:
            # print("[DEBUG] Decoding previous frame for movement detection...")
            prev_frame = decode_image(prev_frame_data)
            if prev_frame is not None:
                # print("[DEBUG] Detecting movement...")
                movement_status = detect_movement(prev_frame, current_frame)
                # print(f"[DEBUG] Movement status: {movement_status}")
            else:
                 print("[WARN] Failed to decode previous frame data for movement detection.") #
                 movement_status = "unknown" # Indicate failure to check
        except Exception as e:
            print(f"[ERROR] Exception during movement detection: {e}") #
            print(traceback.format_exc()) # <--- Uses traceback #
            movement_status = "error" # Indicate error during check


    print("[DEBUG] process_proctoring finished.") #
    # Return the dictionary with the standard Python boolean
    return {
        "face_match": face_match_result, # This is now a standard Python bool
        "objects": objects_found,
        "movement": movement_status
        # Removed the "error" key unless specifically needed for frontend handling
    }