const express = require('express');
const cors = require('cors');
const { proxy, scriptUrl } = require('rtsp-relay')(
  {
    // RTSP options
    rtsp: {
      transport: 'tcp', // 'tcp' or 'udp'
      retry: { // Retry options for RTSP connections
        maxTimeout: 10000, // Max time to wait before giving up
        maxRetries: 5, // Max number of retries
      },
      bufferSize: 1024 * 1024, // 1MB buffer size
    },
    // WebRTC options
    webrtc: {
      iceServers: [
        { urls: 'stun:stun.l.google.com:19302' },
      ],
    },
    // Debug options
    debug: false, // Set to true to enable debug logs
  }
);

const app = express();
app.use(cors());
app.use(express.json());

// Serve the client script
app.get('/rtsp-relay.js', (req, res) => {
  res.sendFile(scriptUrl);
});

// Serve a simple test page
app.get('/', (req, res) => {
  res.send(`
    <html>
      <head>
        <title>RTSP WebRTC Proxy</title>
        <style>
          body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
          h1 { color: #333; }
          video { width: 100%; background: #000; }
          .stream-container { margin-top: 20px; }
          .info { background: #f5f5f5; padding: 10px; border-radius: 4px; margin-top: 20px; }
        </style>
      </head>
      <body>
        <h1>RTSP WebRTC Proxy</h1>
        <div class="stream-container">
          <video id="video" autoplay controls playsinline></video>
        </div>
        <div class="info">
          <p>This page demonstrates the RTSP to WebRTC proxy. Use the following format to view a stream:</p>
          <code>/stream?url=rtsp://username:password@camera-ip:port/path</code>
        </div>
        
        <script src="/rtsp-relay.js"></script>
        <script>
          const urlParams = new URLSearchParams(window.location.search);
          const streamId = urlParams.get('stream') || 'test';
          
          loadPlayer({
            videoEl: document.getElementById('video'),
            pathname: streamId,
            secure: false,
            onDisconnect: () => console.log('Disconnected from stream'),
          });
        </script>
      </body>
    </html>
  `);
});

// Handle stream requests
app.post('/api/create-stream', (req, res) => {
  try {
    const { streamId, rtspUrl } = req.body;
    
    if (!streamId || !rtspUrl) {
      return res.status(400).json({ error: 'Missing streamId or rtspUrl' });
    }
    
    // Create a handler for this stream
    const handler = proxy({
      url: rtspUrl,
      // Additional options if needed
      verbose: true,
      additionalFlags: [
        '-q', '1',
        '-rtsp_transport', 'tcp',
        '-stimeout', '5000000',
        '-analyzeduration', '5000000',
        '-probesize', '5000000',
        '-r', '30'
      ],
      ffmpegPath: null, // Let it auto-detect
    });
    
    console.log(`Created stream: ${streamId} for URL: ${rtspUrl}`);
    
    // Store the handler in the app for later use
    app.get(`/stream/${streamId}`, handler);
    
    return res.json({ 
      success: true, 
      message: 'Stream created successfully',
      streamUrl: `/stream/${streamId}`,
      viewUrl: `/?stream=${streamId}`
    });
  } catch (error) {
    console.error('Error creating stream:', error);
    return res.status(500).json({ error: 'Failed to create stream', details: error.message });
  }
});

// List active streams
const activeStreams = new Map();

app.get('/api/streams', (req, res) => {
  const streams = Array.from(activeStreams.entries()).map(([id, url]) => ({
    id,
    url: url.replace(/\/\/.*?:.*?@/, '//***:***@') // Hide credentials in the response
  }));
  
  res.json({ streams });
});

// Start the server
const PORT = process.env.PORT || 3001;
app.listen(PORT, () => {
  console.log(`RTSP Proxy Server running on port ${PORT}`);
  console.log(`Access the test page at http://localhost:${PORT}`);
});

// Handle WebSocket connections for the streams
const server = require('http').createServer(app);
const wsServer = require('ws').Server;

const wss = new wsServer({ server });

wss.on('connection', (ws, req) => {
  console.log('WebSocket connection established');
  
  ws.on('message', (message) => {
    try {
      const data = JSON.parse(message);
      
      if (data.action === 'create-stream') {
        // Store the stream in our active streams map
        activeStreams.set(data.streamId, data.rtspUrl);
        
        // Create a handler for this stream if it doesn't exist
        if (!app._router.stack.some(r => r.route && r.route.path === `/stream/${data.streamId}`)) {
          const handler = proxy({
            url: data.rtspUrl,
            verbose: true,
            additionalFlags: [
              '-q', '1',
              '-rtsp_transport', 'tcp',
              '-stimeout', '5000000',
              '-analyzeduration', '5000000',
              '-probesize', '5000000',
              '-r', '30'
            ],
          });
          
          app.get(`/stream/${data.streamId}`, handler);
        }
        
        ws.send(JSON.stringify({
          action: 'stream-created',
          streamId: data.streamId,
          success: true
        }));
      }
    } catch (error) {
      console.error('Error processing WebSocket message:', error);
      ws.send(JSON.stringify({ error: 'Failed to process message' }));
    }
  });
  
  ws.on('close', () => {
    console.log('WebSocket connection closed');
  });
});

server.listen(3002, () => {
  console.log('WebSocket server running on port 3002');
});
