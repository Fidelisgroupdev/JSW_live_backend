import cv2
import numpy as np

# Print OpenCV version
print(f"OpenCV Version: {cv2.__version__}")

# Create a simple test image
test_image = np.zeros((300, 300, 3), dtype=np.uint8)
test_image[:] = (0, 0, 255)  # Red color

# Try to encode the image to JPEG
success, encoded_img = cv2.imencode('.jpg', test_image)
print(f"Image encoding successful: {success}")

# Try to create a VideoCapture object (without connecting)
cap = cv2.VideoCapture()
print(f"VideoCapture created: {cap is not None}")

# Check available backends
backends = [
    ("FFMPEG", cv2.CAP_FFMPEG),
    ("MSMF", cv2.CAP_MSMF),
    ("DSHOW", cv2.CAP_DSHOW),
    ("GSTREAMER", cv2.CAP_GSTREAMER if hasattr(cv2, 'CAP_GSTREAMER') else None)
]

print("Available backends:")
for name, backend in backends:
    if backend is not None:
        print(f"- {name}: {backend}")

print("Test complete!")
