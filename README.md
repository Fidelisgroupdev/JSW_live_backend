# CementTrack - JSW Live Backend & Frontend

This project consists of a Django backend, a React frontend, and a Node.js RTSP proxy server for managing and viewing Hikvision camera streams for cement bag counting and analytics.

## Prerequisites

*   **Python:** Version 3.8 or higher. [Download Python](https://www.python.org/downloads/)
*   **Node.js:** Version 16 or higher (which includes npm). [Download Node.js](https://nodejs.org/)
*   **Git:** For cloning the repository (if applicable). [Download Git](https://git-scm.com/)

## Setup Instructions

1.  **Clone the Repository (if necessary):**
    ```bash
    git clone https://github.com/Fidelisgroupdev/JSW_live_backend.git
    cd JSW_live_backend
    ```

2.  **Backend Setup (Django):**
    *   Navigate to the project root directory (`d:\jsw_project_django` or wherever you cloned it).
    *   Create and activate a Python virtual environment:
        ```bash
        # Windows
        python -m venv venv
        .\venv\Scripts\activate

        # macOS/Linux
        python3 -m venv venv
        source venv/bin/activate
        ```
    *   Install Python dependencies:
        ```bash
        pip install -r requirements.txt
        ```
    *   Apply database migrations:
        ```bash
        python manage.py migrate
        ```
    *   *(Optional)* Create a Django superuser (for accessing the admin panel):
        ```bash
        python manage.py createsuperuser
        ```

3.  **Frontend Setup (React):**
    *   Navigate to the `frontend` directory:
        ```bash
        cd frontend
        ```
    *   Install Node.js dependencies:
        ```bash
        npm install
        ```
    *   Return to the project root directory:
        ```bash
        cd ..
        ```

4.  **RTSP Proxy Setup (Node.js):**
    *   Navigate to the `rtsp_proxy_server` directory:
        ```bash
        cd rtsp_proxy_server
        ```
    *   Install Node.js dependencies:
        ```bash
        npm install
        ```
    *   Return to the project root directory:
        ```bash
        cd ..
        ```

## Running the Application

You need to run three separate processes, ideally in different terminal windows/tabs, from the project root directory (`d:\jsw_project_django`). Make sure your virtual environment is activated for the Django backend.

1.  **Run the Django Backend Server:**
    *   Ensure your Python virtual environment (`venv`) is activated.
    *   From the project root directory:
        ```bash
        python manage.py runserver
        ```
    *   This typically runs on `http://127.0.0.1:8000/`.

2.  **Run the React Frontend Development Server:**
    *   Navigate to the `frontend` directory:
        ```bash
        cd frontend
        ```
    *   Start the development server:
        ```bash
        npm start
        ```
    *   This usually opens the application automatically in your browser, typically at `http://localhost:3000/`.

3.  **Run the Node.js RTSP Proxy Server:**
    *   Navigate to the `rtsp_proxy_server` directory:
        ```bash
        cd rtsp_proxy_server
        ```
    *   Start the proxy server:
        ```bash
        node server.js
        ```
    *   This server listens for WebSocket connections (typically on port 9999, but check `server.js` if needed) to proxy RTSP streams.

## Accessing the Application

*   Open your web browser and navigate to the URL provided by the React frontend development server (usually `http://localhost:3000/`).
*   The frontend will interact with the Django backend API (running on port 8000) and the Node.js RTSP proxy (running on port 9999) as needed.

## Example Hikvision RTSP URLs (Camera at 103.21.79.245)

These are example URLs based on common Hikvision conventions and user input. Credentials and specific channel availability may vary.

*   **Main Stream (H.264/H.265):** `rtsp://admin:Fidelis12@103.21.79.245:554/Streaming/Channels/101`
*   **Sub Stream (H.264/H.265):** `rtsp://admin:Fidelis12@103.21.79.245:554/Streaming/Channels/102`
*   **Third Stream (User Provided):** `rtsp://admin:Fidelis12@103.21.79.245:554/Streaming/Channels/302`
*   **Third Stream (Common Convention):** `rtsp://admin:Fidelis12@103.21.79.245:554/Streaming/Channels/301`
*   **HEVC/H.265 Main Stream:** `rtsp://admin:Fidelis12@103.21.79.245:554/Streaming/Channels/401`
*   **HEVC/H.265 Sub Stream:** `rtsp://admin:Fidelis12@103.21.79.245:554/Streaming/Channels/402`
*   **(Other potential channels based on previous user input, purpose may vary):**
    *   `rtsp://admin:Fidelis12@103.21.79.245:554/Streaming/Channels/201`
    *   `rtsp://admin:Fidelis12@103.21.79.245:554/Streaming/Channels/501`
    *   `rtsp://admin:Fidelis12@103.21.79.245:554/Streaming/Channels/601`
    *   `rtsp://admin:Fidelis12@103.21.79.245:554/Streaming/Channels/701`

**Note:** Channel 101/102 are typically standard H.264/H.265, while 401/402 are often specifically for H.265/HEVC. The user provided channel 302 for the third stream at this IP; the standard third stream is often 301. Other channel purposes may vary based on camera model and configuration.
