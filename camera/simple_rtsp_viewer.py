import cv2
import os
import time
from datetime import datetime

# Create directory for saved frames
output_dir = "rtsp_frames"
os.makedirs(output_dir, exist_ok=True)

# Replace with your actual RTSP URL
rtsp_url = "rtsp://admin:Fidelis12@103.21.79.245:554/Streaming/Channels/101"

# Try with a different channel if the original doesn't work
alternative_urls = [
    "rtsp://admin:Fidelis12@103.21.79.245:554/Streaming/Channels/401",
    "rtsp://admin:Fidelis12@103.21.79.245:554/Streaming/Channels/102",
    "rtsp://admin:Fidelis12@103.21.79.245:554/Streaming/Channels/201"
]

def test_rtsp_url(url):
    print(f"Trying to connect to: {url}")
    
    # Try with FFMPEG backend first
    video = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    
    # Set buffer size to 1 to reduce latency
    video.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    
    if not video.isOpened():
        print(f"Failed to open stream with FFMPEG backend: {url}")
        # Try with default backend
        video = cv2.VideoCapture(url)
        
        if not video.isOpened():
            print(f"Failed to open stream with default backend: {url}")
            return False
    
    # Read a test frame
    ret, frame = video.read()
    if not ret:
        print(f"Connected but failed to read frame from: {url}")
        video.release()
        return False
    
    print(f"Successfully connected to: {url}")
    print(f"Frame size: {frame.shape[1]}x{frame.shape[0]}")
    
    # Save the test frame
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    test_frame_path = os.path.join(output_dir, f"test_frame_{timestamp}.jpg")
    cv2.imwrite(test_frame_path, frame)
    print(f"Test frame saved to: {test_frame_path}")
    
    # Capture and save frames
    frame_count = 0
    max_frames = 30  # Capture 30 frames
    start_time = time.time()
    
    while frame_count < max_frames:
        ret, frame = video.read()
        
        if not ret:
            print("Frame read error, retrying...")
            time.sleep(0.5)
            continue
        
        # Save frame every second
        current_time = time.time()
        if current_time - start_time >= 1.0:
            frame_count += 1
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            frame_path = os.path.join(output_dir, f"frame_{frame_count}_{timestamp}.jpg")
            cv2.imwrite(frame_path, frame)
            print(f"Saved frame {frame_count} to: {frame_path}")
            start_time = current_time
    
    video.release()
    print(f"Captured {frame_count} frames from {url}")
    return True

# Try the main URL first
success = test_rtsp_url(rtsp_url)

# If main URL fails, try alternatives
if not success:
    print("\nTrying alternative URLs...")
    for alt_url in alternative_urls:
        if test_rtsp_url(alt_url):
            break
        print("\n")  # Add spacing between attempts
