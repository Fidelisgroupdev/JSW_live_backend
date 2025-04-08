import cv2
import time
import sys

def test_rtsp_connection(rtsp_url):
    print(f"Testing connection to: {rtsp_url}")
    print(f"OpenCV version: {cv2.__version__}")
    
    # Try with TCP transport parameter in URL
    if '?' not in rtsp_url:
        test_url = f"{rtsp_url}?rtsp_transport=tcp"
        print(f"Using URL with TCP transport: {test_url}")
    else:
        test_url = rtsp_url
        print(f"Using original URL: {test_url}")
    
    # Create VideoCapture
    cap = cv2.VideoCapture(test_url)
    
    # Try to set buffer size
    try:
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 3)
        print("Buffer size set to 3")
    except Exception as e:
        print(f"Error setting buffer size: {str(e)}")
    
    # Check if connection was successful
    if not cap.isOpened():
        print("Failed to open RTSP stream with TCP transport")
        
        # Try without transport parameter if it was added
        if '?' in test_url and test_url != rtsp_url:
            print("Trying without transport parameter...")
            cap = cv2.VideoCapture(rtsp_url)
            
            if not cap.isOpened():
                print("Failed to open RTSP stream without transport parameter")
                return False
            else:
                print("Successfully connected without transport parameter")
        else:
            return False
    else:
        print("Successfully connected with transport parameter")
    
    # Try to read a frame
    print("Attempting to read frames...")
    frames_read = 0
    start_time = time.time()
    
    for _ in range(5):  # Try to read 5 frames
        ret, frame = cap.read()
        
        if ret:
            frames_read += 1
            height, width = frame.shape[:2]
            print(f"Read frame {frames_read}: {width}x{height}")
        else:
            print(f"Failed to read frame {frames_read + 1}")
        
        time.sleep(0.5)  # Wait between frame reads
    
    # Release the capture
    cap.release()
    
    elapsed = time.time() - start_time
    fps = frames_read / elapsed if elapsed > 0 else 0
    
    print(f"Test completed: Read {frames_read} frames in {elapsed:.2f} seconds ({fps:.2f} FPS)")
    return frames_read > 0

if __name__ == "__main__":
    # Use command line argument or default test URL
    rtsp_url = sys.argv[1] if len(sys.argv) > 1 else "rtsp://wowzaec2demo.streamlock.net/vod/mp4:BigBuckBunny_115k.mp4"
    
    success = test_rtsp_connection(rtsp_url)
    print(f"RTSP connection test {'PASSED' if success else 'FAILED'}")
    sys.exit(0 if success else 1)
