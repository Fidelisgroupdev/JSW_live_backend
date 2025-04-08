const express = require('express');
const cors = require('cors');
const { spawn } = require('child_process');
const WebSocket = require('ws');
const http = require('http');
const path = require('path');
const fs = require('fs');

// Check if ffmpeg is installed
const checkFFmpeg = () => {
  try {
    const ffmpeg = spawn('ffmpeg', ['-version']);
    ffmpeg.on('error', (err) => {
      console.error('FFmpeg is not installed or not in PATH. Please install FFmpeg.');
      process.exit(1);
    });
    return true;
  } catch (error) {
    console.error('Error checking FFmpeg:', error);
    process.exit(1);
  }
};

checkFFmpeg();

const app = express();
app.use(cors());
app.use(express.json());

// Create HTTP server
const server = http.createServer(app);

// Active streams storage
const activeStreams = new Map();

// WebSocket server
const wss = new WebSocket.Server({ server });

// Serve static files
app.use(express.static(path.join(__dirname, 'public')));

// Create public directory if it doesn't exist
const publicDir = path.join(__dirname, 'public');
if (!fs.existsSync(publicDir)) {
  fs.mkdirSync(publicDir);
}

// Serve a simple test page
app.get('/', (req, res) => {
  res.send(`
    <html>
      <head>
        <title>Hikvision RTSP Viewer</title>
        <style>
          body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
          h1 { color: #333; }
          video { width: 100%; background: #000; }
          .stream-container { margin-top: 20px; }
          .info { background: #f5f5f5; padding: 10px; border-radius: 4px; margin-top: 20px; }
          form { margin-top: 20px; }
          input[type="text"] { width: 100%; padding: 8px; margin-bottom: 10px; }
          button { padding: 8px 16px; background: #007bff; color: white; border: none; cursor: pointer; }
          .status { margin-top: 10px; font-weight: bold; }
        </style>
      </head>
      <body>
        <h1>Hikvision RTSP Viewer</h1>
        
        <form id="streamForm">
          <div>
            <label for="rtspUrl">RTSP URL:</label>
            <input type="text" id="rtspUrl" value="rtsp://admin:Fidelis12@103.21.79.245:554/Streaming/Channels/101" required>
          </div>
          <div>
            <label for="streamName">Stream Name:</label>
            <input type="text" id="streamName" value="hikvision_camera" required>
          </div>
          <button type="submit">Start Stream</button>
        </form>
        
        <div class="status" id="status"></div>
        
        <div class="stream-container">
          <video id="videoPlayer" controls autoplay muted></video>
        </div>
        
        <div class="info">
          <p>For Hikvision cameras, use one of these formats:</p>
          <ul>
            <li>NVR Channels: <code>rtsp://username:password@ip:554/Streaming/Channels/101</code></li>
            <li>Direct Camera: <code>rtsp://username:password@ip:554/D1</code></li>
          </ul>
        </div>
        
        <script>
          const form = document.getElementById('streamForm');
          const videoPlayer = document.getElementById('videoPlayer');
          const statusEl = document.getElementById('status');
          
          form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const rtspUrl = document.getElementById('rtspUrl').value;
            const streamName = document.getElementById('streamName').value;
            
            statusEl.textContent = 'Starting stream...';
            
            try {
              const response = await fetch('/api/start-stream', {
                method: 'POST',
                headers: {
                  'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                  rtspUrl,
                  streamName
                })
              });
              
              const data = await response.json();
              
              if (data.success) {
                statusEl.textContent = 'Stream started successfully. Loading video...';
                
                // Set up HLS player
                videoPlayer.src = data.hlsUrl;
                videoPlayer.load();
                videoPlayer.play().catch(err => {
                  console.error('Error playing video:', err);
                  statusEl.textContent = 'Error playing video. Check console for details.';
                });
              } else {
                statusEl.textContent = 'Error: ' + data.error;
              }
            } catch (error) {
              console.error('Error starting stream:', error);
              statusEl.textContent = 'Error starting stream. Check console for details.';
            }
          });
        </script>
      </body>
    </html>
  `);
});

// Start a stream and convert to HLS
app.post('/api/start-stream', (req, res) => {
  try {
    const { rtspUrl, streamName } = req.body;
    
    if (!rtspUrl || !streamName) {
      return res.status(400).json({ success: false, error: 'Missing rtspUrl or streamName' });
    }
    
    // Create output directory for this stream
    const streamDir = path.join(publicDir, streamName);
    if (!fs.existsSync(streamDir)) {
      fs.mkdirSync(streamDir);
    }
    
    // Kill any existing process for this stream
    if (activeStreams.has(streamName)) {
      const existingProcess = activeStreams.get(streamName);
      existingProcess.kill('SIGTERM');
      activeStreams.delete(streamName);
    }
    
    // Output file paths
    const m3u8File = path.join(streamName, 'playlist.m3u8');
    const m3u8Path = path.join(publicDir, m3u8File);
    
    console.log(`Starting stream for ${rtspUrl} to ${m3u8Path}`);
    
    // FFmpeg command to convert RTSP to HLS
    const ffmpeg = spawn('ffmpeg', [
      '-rtsp_transport', 'tcp',
      '-i', rtspUrl,
      '-c:v', 'copy',
      '-c:a', 'aac',
      '-hls_time', '2',
      '-hls_list_size', '3',
      '-hls_flags', 'delete_segments',
      '-f', 'hls',
      m3u8Path
    ]);
    
    // Store the process
    activeStreams.set(streamName, ffmpeg);
    
    // Log output
    ffmpeg.stdout.on('data', (data) => {
      console.log(`FFmpeg stdout: ${data}`);
    });
    
    ffmpeg.stderr.on('data', (data) => {
      console.log(`FFmpeg stderr: ${data}`);
    });
    
    ffmpeg.on('close', (code) => {
      console.log(`FFmpeg process exited with code ${code}`);
      activeStreams.delete(streamName);
    });
    
    // Return success with the HLS URL
    return res.json({
      success: true,
      hlsUrl: `/${m3u8File}`,
      message: 'Stream started successfully'
    });
    
  } catch (error) {
    console.error('Error starting stream:', error);
    return res.status(500).json({
      success: false,
      error: error.message
    });
  }
});

// Stop a stream
app.post('/api/stop-stream', (req, res) => {
  try {
    const { streamName } = req.body;
    
    if (!streamName) {
      return res.status(400).json({ success: false, error: 'Missing streamName' });
    }
    
    if (activeStreams.has(streamName)) {
      const process = activeStreams.get(streamName);
      process.kill('SIGTERM');
      activeStreams.delete(streamName);
      
      return res.json({
        success: true,
        message: 'Stream stopped successfully'
      });
    } else {
      return res.status(404).json({
        success: false,
        error: 'Stream not found'
      });
    }
  } catch (error) {
    console.error('Error stopping stream:', error);
    return res.status(500).json({
      success: false,
      error: error.message
    });
  }
});

// List all active streams
app.get('/api/streams', (req, res) => {
  const streams = Array.from(activeStreams.keys()).map(name => ({
    name,
    hlsUrl: `/${path.join(name, 'playlist.m3u8')}`
  }));
  
  res.json({ streams });
});

// Start the server
const PORT = process.env.PORT || 3001;
server.listen(PORT, () => {
  console.log(`Hikvision RTSP Server running on port ${PORT}`);
  console.log(`Access the test page at http://localhost:${PORT}`);
});
