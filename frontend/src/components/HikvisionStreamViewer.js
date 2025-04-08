import React, { useState, useEffect, useRef } from 'react';
import './HikvisionStreamViewer.css';

const HikvisionStreamViewer = ({ 
  rtspUrl, 
  cameraName, 
  resolution = 'medium',
  targetFps = 25, // Default to 25 if not provided
  onError,
  onSuccess
}) => {
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('idle');
  const [debugInfo, setDebugInfo] = useState('');
  const [streamStats, setStreamStats] = useState(null);
  const imgRef = useRef(null);
  const intervalRef = useRef(null);
  const retryCountRef = useRef(0);
  const maxRetries = 5;
  const canvasRef = useRef(null); // Ref for the canvas
  const [isDrawing, setIsDrawing] = useState(false); // State for drawing status
  const [linePoints, setLinePoints] = useState({ start: null, end: null }); // State for line coordinates
  const [relativeLinePoints, setRelativeLinePoints] = useState({ start: null, end: null }); // State for relative line coordinates
  const API_BASE_URL = 'http://127.0.0.1:8000/api/rtsp'; // Adjust if your Django API is elsewhere

  useEffect(() => {
    // Clean up on unmount
    return () => {
      stopStream();
    };
  }, []);

  useEffect(() => {
    // Auto-start streaming if rtspUrl is provided
    if (rtspUrl) {
      startStream();
    } else {
      stopStream();
    }
  }, [rtspUrl, resolution, targetFps]); // Restart stream when settings change

  const startStream = () => {
    if (!rtspUrl) {
      const errorMsg = 'No RTSP URL provided';
      setError(errorMsg);
      if (onError) onError(errorMsg);
      return;
    }

    setIsStreaming(true);
    setStatus('connecting');
    setError('');
    setDebugInfo(`Connecting to stream: ${rtspUrl} with resolution: ${resolution}`);
    retryCountRef.current = 0;

    // Start fetching frames
    fetchFrame();

    // Set up interval for continuous fetching
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
    }
    const targetInterval = targetFps > 0 ? 1000 / targetFps : 100; // Default to 10fps if targetFps is invalid
    intervalRef.current = setInterval(fetchFrame, targetInterval); // Use targetFps to set interval
  };

  const stopStream = () => {
    setIsStreaming(false);
    setStatus('idle');
    setStreamStats(null);
    
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    
    if (imgRef.current) {
      imgRef.current.src = '';
    }
  };

  const fetchFrame = async () => {
    if (!isStreaming || !rtspUrl) return;

    try {
      // Build URL with appropriate parameters
      let url = `/api/camera/frame/?url=${encodeURIComponent(rtspUrl)}&resolution=${resolution}`;
      
      setDebugInfo(`Fetching frame from: ${url}`);
      
      const response = await fetch(url, {
        method: 'GET',
        headers: {
          'Accept': 'application/json',
          'Cache-Control': 'no-cache'
        }
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Server responded with status: ${response.status}. ${errorText}`);
      }
      
      const data = await response.json();
      
      if (data.success && data.frame) {
        if (imgRef.current) {
          imgRef.current.src = `data:image/jpeg;base64,${data.frame}`;
        }
        
        if (status !== 'streaming') {
          setStatus('streaming');
          if (onSuccess) onSuccess();
        }
        
        // Reset retry count on success
        retryCountRef.current = 0;
        
        // Update stats if available
        if (data.status) {
          setStreamStats(data.status);
        }
        
        // Clear any previous errors
        if (error) {
          setError('');
          if (onError) onError('');
        }
      } else {
        // Handle API error response
        const errorMsg = data.error || 'Failed to get frame from stream';
        console.error(errorMsg);
        setDebugInfo(`API Error: ${errorMsg}`);
        
        // If we have detailed error information, log it
        if (data.error_details) {
          console.error('Error details:', data.error_details);
          setDebugInfo(`Error details: ${JSON.stringify(data.error_details)}`);
        }
        
        retryCountRef.current++;
        if (retryCountRef.current > maxRetries) {
          handleStreamError(errorMsg);
        }
      }
    } catch (error) {
      console.error('Error fetching frame:', error);
      setDebugInfo(`Fetch Error: ${error.message}`);
      
      retryCountRef.current++;
      if (retryCountRef.current > maxRetries) {
        handleStreamError(error.message);
      }
    }
  };

  const handleStreamError = (errorMsg) => {
    setError(errorMsg);
    setStatus('error');
    setDebugInfo(`Max retries (${maxRetries}) reached. Stream failed.`);
    
    // Notify parent component of error
    if (onError) {
      onError(errorMsg);
    }
  };

  // Try direct MJPEG stream as fallback
  const tryMjpegStream = () => {
    if (!rtspUrl) return;
    
    setStatus('connecting');
    setDebugInfo('Trying MJPEG stream as fallback');
    
    // Use the MJPEG endpoint
    const mjpegUrl = `/api/camera/mjpeg/?url=${encodeURIComponent(rtspUrl)}&resolution=${resolution}`;
    
    if (imgRef.current) {
      imgRef.current.src = mjpegUrl;
      setStatus('streaming');
      if (onSuccess) onSuccess();
    }
  };

  // Change resolution and restart stream
  const changeResolution = (newResolution) => {
    if (resolution !== newResolution) {
      stopStream();
      // Parent component should handle this via props
    }
  };
  
  // Format FPS with 1 decimal place
  const formatFps = (fps) => {
    return fps ? fps.toFixed(1) : '0.0';
  };

  // Drawing Logic
  const getMousePos = (canvas, evt) => {
    const rect = canvas.getBoundingClientRect();
    return {
      x: evt.clientX - rect.left,
      y: evt.clientY - rect.top
    };
  };

  const drawLine = (ctx, start, end) => {
    if (!start || !end) return;
    ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height); // Clear previous line
    ctx.beginPath();
    ctx.moveTo(start.x, start.y);
    ctx.lineTo(end.x, end.y);
    ctx.strokeStyle = 'red'; // Line color
    ctx.lineWidth = 2; // Line width
    ctx.stroke();
  };

  const handleMouseDown = (event) => {
    if (!canvasRef.current) return;
    const pos = getMousePos(canvasRef.current, event);
    setLinePoints({ start: pos, end: pos }); // Start and end at the same point initially
    setIsDrawing(true);
  };

  const handleMouseMove = (event) => {
    if (!isDrawing || !canvasRef.current) return;
    const pos = getMousePos(canvasRef.current, event);
    setLinePoints(prev => ({ ...prev, end: pos })); // Update end point
    const ctx = canvasRef.current.getContext('2d');
    drawLine(ctx, linePoints.start, pos); // Draw dynamically
  };

  const handleMouseUp = (event) => {
    if (!isDrawing || !canvasRef.current) return;
    const pos = getMousePos(canvasRef.current, event);
    setLinePoints(prev => ({ ...prev, end: pos })); // Final end point
    setIsDrawing(false);
    const ctx = canvasRef.current.getContext('2d');
    drawLine(ctx, linePoints.start, pos); // Draw the final line
    console.log('Line drawn:', linePoints.start, pos); // Log the final points
    // TODO: Send linePoints to backend if needed for counting
  };

  // Effect to draw the line when points change or canvas is ready
  useEffect(() => {
    const canvas = canvasRef.current;
    if (canvas && linePoints.start && linePoints.end) {
      const ctx = canvas.getContext('2d');
      // Ensure canvas dimensions match image dimensions
      if (imgRef.current) {
        canvas.width = imgRef.current.clientWidth;
        canvas.height = imgRef.current.clientHeight;
      }
      drawLine(ctx, linePoints.start, linePoints.end);
    } else if (canvas) {
       // Clear canvas if no line is defined
       const ctx = canvas.getContext('2d');
       ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
  }, [linePoints, imgRef]); // Redraw when points or image changes

  const getRelativeCoords = (absX, absY, image) => {
    if (!image || !image.naturalWidth || !image.naturalHeight) return null;
    return {
      x: absX / image.clientWidth, // Use clientWidth for displayed size
      y: absY / image.clientHeight, // Use clientHeight for displayed size
    };
  };

  const getAbsoluteCoords = (relX, relY, image) => {
      if (!image || !image.clientWidth || !image.clientHeight) return null;
      return {
          x: relX * image.clientWidth,
          y: relY * image.clientHeight,
      };
  };

  const drawLineOnCanvas = (ctx, absStart, absEnd) => {
    if (!absStart || !absEnd) return;
    ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height); // Clear previous line
    ctx.beginPath();
    ctx.moveTo(absStart.x, absStart.y);
    ctx.lineTo(absEnd.x, absEnd.y);
    ctx.strokeStyle = 'red'; // Line color
    ctx.lineWidth = 2; // Line width
    ctx.stroke();
  };

  const handleMouseDownRelative = (event) => {
    if (!canvasRef.current) return;
    const pos = getMousePos(canvasRef.current, event);
    const relPos = getRelativeCoords(pos.x, pos.y, imgRef.current);
    if (!relPos) return;

    setRelativeLinePoints({ start: relPos, end: relPos }); // Store relative points
    setIsDrawing(true);
    // Draw initial dot
    const ctx = canvasRef.current.getContext('2d');
    drawLineOnCanvas(ctx, pos, pos);
  };

  const handleMouseMoveRelative = (event) => {
    if (!isDrawing || !canvasRef.current) return;
    const pos = getMousePos(canvasRef.current, event);
    const relPos = getRelativeCoords(pos.x, pos.y, imgRef.current);
     if (!relPos) return;

    setRelativeLinePoints(prev => ({ ...prev, end: relPos })); // Update relative end point

    // Draw based on absolute coordinates
    const ctx = canvasRef.current.getContext('2d');
    const absStart = getAbsoluteCoords(relativeLinePoints.start.x, relativeLinePoints.start.y, imgRef.current);
    if(absStart){
        drawLineOnCanvas(ctx, absStart, pos); // Draw dynamically using absolute coords
    }
  };

  const handleMouseUpRelative = (event) => {
    if (!isDrawing || !canvasRef.current) return;
    const pos = getMousePos(canvasRef.current, event);
    const relPos = getRelativeCoords(pos.x, pos.y, imgRef.current);
    if (!relPos) {
        setIsDrawing(false);
        return;
    }

    const finalRelativePoints = { start: relativeLinePoints.start, end: relPos };
    setRelativeLinePoints(finalRelativePoints); // Store final relative points
    setIsDrawing(false);

    // Draw final line based on absolute coordinates
    const ctx = canvasRef.current.getContext('2d');
    const absStart = getAbsoluteCoords(finalRelativePoints.start.x, finalRelativePoints.start.y, imgRef.current);
     if(absStart){
        drawLineOnCanvas(ctx, absStart, pos);
        console.log('Line drawn (relative):', finalRelativePoints);
     }
  };

  const saveLine = async () => {
    if (!rtspUrl || !relativeLinePoints.start || !relativeLinePoints.end) {
      setError('Cannot save line: RTSP URL or line points are missing.');
      return;
    }
    setError(null);

    try {
      console.log(`Saving line for stream ${rtspUrl}:`, relativeLinePoints);
      // *** Placeholder: Replace with actual API call ***
      const response = await fetch(`${API_BASE_URL}/line/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          start_x: relativeLinePoints.start.x,
          start_y: relativeLinePoints.start.y,
          end_x: relativeLinePoints.end.x,
          end_y: relativeLinePoints.end.y,
        })
      });

      // Assuming backend responds with success message or confirmation
      console.log('Save line response:', response);
      console.log('Line saved successfully!');

    } catch (apiError) {
      console.error('Error saving line:', apiError);
      let message = 'Failed to save line.';
       if (apiError.response) {
           message += ` Server responded with ${apiError.response.status}: ${JSON.stringify(apiError.response.data)}`;
       } else {
           message += ' Check backend connection or API endpoint.';
       }
      setError(message);
    }
  };

  const fetchLine = async () => {
      if (!rtspUrl) return;
      try {
          console.log(`Fetching line for stream ${rtspUrl}`);
          // *** Placeholder: Replace with actual API call ***
          const response = await fetch(`${API_BASE_URL}/line/`);
          if (response.ok) {
              const data = await response.json();
              console.log('Fetched line data:', data);
              setRelativeLinePoints({
                  start: { x: data.start_x, y: data.start_y },
                  end: { x: data.end_x, y: data.end_y },
              });
          } else {
              console.log(`No saved line found for stream ${rtspUrl}`);
              // Ensure line is cleared if nothing is fetched
              setRelativeLinePoints({ start: null, end: null });
          }
      } catch (fetchError) {
          if (fetchError.response && fetchError.response.status === 404) {
              console.log(`No saved line found for stream ${rtspUrl} (404).`);
              setRelativeLinePoints({ start: null, end: null }); // Clear line if not found
          } else {
              console.error('Error fetching line:', fetchError);
              // Avoid setting error state here to not conflict with stream errors
              // setError('Failed to fetch saved line.');
          }
      }
  };

  return (
    <div className="hikvision-stream-viewer">
      <div className="stream-header">
        <h3>{cameraName || 'RTSP Stream'}</h3>
        
        <div className="stream-controls">
          <div className="resolution-controls">
            <button 
              className={`resolution-btn ${resolution === 'low' ? 'active' : ''}`} 
              onClick={() => changeResolution('low')}
              title="640x360"
            >
              Low
            </button>
            <button 
              className={`resolution-btn ${resolution === 'medium' ? 'active' : ''}`} 
              onClick={() => changeResolution('medium')}
              title="1280x720"
            >
              Medium
            </button>
            <button 
              className={`resolution-btn ${resolution === 'high' ? 'active' : ''}`} 
              onClick={() => changeResolution('high')}
              title="1920x1080"
            >
              High
            </button>
          </div>
        </div>
      </div>

      <div className="stream-container">
        {status === 'connecting' && (
          <div className="stream-loading">
            <div className="spinner"></div>
            <p>Connecting to stream...</p>
          </div>
        )}

        {status === 'error' && (
          <div className="stream-error">
            <span className="material-icons">error</span>
            <p>{error || 'Failed to connect to stream'}</p>
            <button onClick={startStream}>Retry</button>
            <button onClick={tryMjpegStream}>Try MJPEG</button>
          </div>
        )}

        <div
          className="stream-image-container"
          onMouseDown={handleMouseDownRelative}
          onMouseMove={handleMouseMoveRelative}
          onMouseUp={handleMouseUpRelative}
          onMouseLeave={() => setIsDrawing(false)} // Stop drawing if mouse leaves the area
        >
          <img 
            ref={imgRef} 
            className={status === 'streaming' ? 'visible' : 'hidden'} 
            alt="RTSP Stream" 
            onError={(e) => {
              console.error('Image load error:', e);
              if (status === 'streaming') {
                handleStreamError('Failed to display stream image');
              }
            }}
          />
          {/* Canvas Overlay */}
          <canvas
            ref={canvasRef}
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              pointerEvents: 'none', // Let mouse events pass through to the underlying Box initially
                                      // Events are handled by the parent Box
            }}
          />
        </div>
        
        {streamStats && status === 'streaming' && (
          <div className="stream-stats">
            <div className="stats-item">
              <span className="stats-label">FPS:</span>
              <span className="stats-value">{formatFps(streamStats.fps)}</span>
            </div>
            <div className="stats-item">
              <span className="stats-label">Frames:</span>
              <span className="stats-value">{streamStats.frame_count}</span>
            </div>
            <div className="stats-item">
              <span className="stats-label">Dropped:</span>
              <span className="stats-value">{streamStats.dropped_frames}</span>
            </div>
          </div>
        )}
      </div>
      
      {/* Debug information */}
      <div className="debug-info">
        <details>
          <summary>Debug Info</summary>
          <p>Status: {status}</p>
          <p>Resolution: {resolution}</p>
          <p>Error: {error}</p>
          <p>RTSP URL: {rtspUrl}</p>
          <p>Info: {debugInfo}</p>
          {streamStats && (
            <>
              <p>FPS: {formatFps(streamStats.fps)}</p>
              <p>Frame Count: {streamStats.frame_count}</p>
              <p>Dropped Frames: {streamStats.dropped_frames}</p>
              {streamStats.error_message && (
                <p>Error: {streamStats.error_message}</p>
              )}
            </>
          )}
        </details>
      </div>
      {/* Buttons for Line Management - Show only when stream is active */}
      {status === 'streaming' && (
          <div className="line-controls">
              {relativeLinePoints.start && relativeLinePoints.end && (
                  <button
                      onClick={() => setRelativeLinePoints({ start: null, end: null })}
                  >
                      Clear Line
                  </button>
              )}
              {relativeLinePoints.start && relativeLinePoints.end && (
                  <button
                      onClick={saveLine}
                  >
                      Save Line
                  </button>
              )}
          </div>
      )}
    </div>
  );
};

export default HikvisionStreamViewer;
