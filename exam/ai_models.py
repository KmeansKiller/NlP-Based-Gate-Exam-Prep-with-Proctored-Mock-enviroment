import cv2
import numpy as np
import face_recognition
import base64
import os

# Define paths for YOLO files
YOLO_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "yolo", "yolov3.cfg")
YOLO_WEIGHTS_PATH = os.path.join(os.path.dirname(__file__), "yolo", "yolov3.weights")
YOLO_NAMES_PATH = os.path.join(os.path.dirname(__file__), "yolo", "coco.names")

# Load class names from coco.names
with open(YOLO_NAMES_PATH, "r") as f:
    YOLO_CLASSES = [line.strip() for line in f.readlines()]

# Initialize YOLO network using OpenCV DNN
net = cv2.dnn.readNet(YOLO_WEIGHTS_PATH, YOLO_CONFIG_PATH)
layer_names = net.getLayerNames()
output_layers = [layer_names[i - 1] for i in net.getUnconnectedOutLayers().flatten()]

def decode_image(frame_data):
    """Decode a base64-encoded image to an OpenCV image."""
    if "," in frame_data:
        frame_data = frame_data.split(",")[1]
    img_data = base64.b64decode(frame_data)
    np_arr = np.frombuffer(img_data, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    return img

def compare_face(live_frame, registered_face_img):
    """Compare a live frame with the registered face image."""
    try:
        live_encodings = face_recognition.face_encodings(live_frame)
        registered_encodings = face_recognition.face_encodings(registered_face_img)
        if live_encodings and registered_encodings:
            results = face_recognition.compare_faces([registered_encodings[0]], live_encodings[0])
            return results[0]
    except Exception as e:
        print("Face recognition error:", e)
    return False

def detect_objects_yolo(frame):
    """Detect objects in a frame using YOLOv3."""
    height, width = frame.shape[:2]
    blob = cv2.dnn.blobFromImage(frame, 1/255.0, (416, 416), swapRB=True, crop=False)
    net.setInput(blob)
    outs = net.forward(output_layers)
    
    class_ids = []
    confidences = []
    boxes = []
    conf_threshold = 0.5
    nms_threshold = 0.4
    
    for out in outs:
        for detection in out:
            scores = detection[5:]
            class_id = np.argmax(scores)
            confidence = scores[class_id]
            if confidence > conf_threshold:
                center_x = int(detection[0] * width)
                center_y = int(detection[1] * height)
                w = int(detection[2] * width)
                h = int(detection[3] * height)
                x = int(center_x - w/2)
                y = int(center_y - h/2)
                boxes.append([x, y, w, h])
                confidences.append(float(confidence))
                class_ids.append(class_id)
    indices = cv2.dnn.NMSBoxes(boxes, confidences, conf_threshold, nms_threshold)
    detected_objects = []
    for i in indices:
        i = i[0] if isinstance(i, (list, tuple, np.ndarray)) else i
        detected_objects.append(YOLO_CLASSES[class_ids[i]])
    return detected_objects

def detect_movement(prev_frame, current_frame):
    """Detect movement between two frames using simple frame differencing."""
    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
    current_gray = cv2.cvtColor(current_frame, cv2.COLOR_BGR2GRAY)
    diff = cv2.absdiff(prev_gray, current_gray)
    movement_score = np.sum(diff) / (diff.shape[0] * diff.shape[1])
    threshold = 20  # Experimentally determined threshold
    return "suspicious" if movement_score > threshold else "normal"
