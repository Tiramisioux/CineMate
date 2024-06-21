from flask import Flask, render_template_string, jsonify, request
import redis

app = Flask(__name__)

# Redis configuration
redis_host = 'localhost'
redis_port = 6379
redis_db = 0

# Example Redis controller class (adjust based on your actual implementation)
class RedisController:
    def __init__(self):
        self.redis_conn = redis.StrictRedis(host=redis_host, port=redis_port, db=redis_db)

    def get_value(self, key):
        return self.redis_conn.get(key).decode('utf-8') if self.redis_conn.exists(key) else None

    def set_value(self, key, value):
        self.redis_conn.set(key, value)

    def publish_message(self, channel, message):
        self.redis_conn.publish(channel, message)

# Mock RedisController instance (replace with your actual initialization logic)
redis_controller = RedisController()

# Your MJPEG stream URL
stream_url = "http://cinepi.local:8000/stream"

# HTML template with dynamic data overlay and dropdown menu
html_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MJPEG Stream with Overlay</title>
    <style>
        body {
            margin: 0;
            padding: 0;
            font-family: 'Arial', sans-serif; /* Set custom font family */
        }
        .top-bar {
            background-color: black;
            color: #fff;
            padding: 10px;
            display: flex;
            justify-content: space-between;
            align-items: left;
        }
        .top-bar select {
            margin-left: 10px;
            padding: 8px;
            font-size: 16px;
            border: none;
            background-color: #111;
            color: #fff;
            border-radius: 5px;
            cursor: pointer;
        }
        .top-bar select:focus {
            outline: none;
        }
        #stream-container {
            background-color: black;
            position: relative;
            width: 100%; /* Adjust width as needed */
            height: 0;
            padding-bottom: 56.25%; /* 16:9 aspect ratio */
            overflow: hidden;
            margin: auto;
        }
        #stream {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            object-fit: contain; /* Ensure the stream fits within its container */
        }
        #overlay {
            display: none; /* Hide the overlay initially */
            position: absolute;
            top: 10px;
            left: 10px;
            color: #fff;
            font-size: 24px;
            background: rgba(0, 0, 0, 0.5);
            padding: 10px;
            border-radius: 10px;
            cursor: pointer; /* Change cursor to pointer for better UX */
        }
        #iso-dropdown, #shutter-dropdown, #fps-dropdown {
            display: none;
            position: absolute;
            top: 50px;
            left: 10px;
            background: rgba(0, 0, 0, 0.8);
            padding: 10px;
            border-radius: 5px;
            z-index: 1000;
        }
        #iso-dropdown.show, #shutter-dropdown.show, #fps-dropdown.show {
            display: block;
        }
        #iso-dropdown select, #shutter-dropdown select, #fps-dropdown select {
            width: 100%;
            padding: 8px;
            font-size: 16px;
            border: none;
            background-color: #333;
            color: #fff;
            border-radius: 5px;
            cursor: pointer;
        }
    </style>
</head>
<body>
    <div class="top-bar">
        <div>ISO:
            <select id="iso-select">
                <option value="100">100</option>
                <option value="400">400</option>
                <option value="800">800</option>
                <option value="1600">1600</option>
            </select>
        </div>
        <div>Shutter Angle:
            <select id="shutter-speed-select">
                <option value="45">45</option>
                <option value="135">135</option>
                <option value="172.8">172.8</option>
                <option value="180">180</option>
                <option value="225">225</option>
                <option value="275">275</option>
                <option value="360">360</option>
            </select>
        </div>
        <div>FPS:
            <select id="fps-select">
                <option value="1">1</option>
                <option value="10">10</option>
                <option value="20">20</option>
                <option value="30">30</option>
                <option value="40">40</option>
                <option value="50">50</option>
            </select>
        </div>
    </div>
    <div id="stream-container">
        <img id="stream" src="{{ stream_url }}" alt="Stream">
    </div>
    <div id="overlay">ISO: {{ dynamic_data.iso }} | Shutter Angle: {{ dynamic_data.shutter_a }} | FPS: {{ dynamic_data.fps }}</div>
    <div id="iso-dropdown">
        <select>
            <option value="100">100</option>
            <option value="400">400</option>
            <option value="800">800</option>
            <option value="1600">1600</option>
        </select>
    </div>
    <div id="shutter-dropdown">
        <select>
            <option value="45">45</option>
            <option value="135">135</option>
            <option value="172.8">172.8</option>
            <option value="180">180</option>
            <option value="225">225</option>
            <option value="275">275</option>
            <option value="360">360</option>
        </select>
    </div>
    <div id="fps-dropdown">
        <select>
            <option value="1">1</option>
            <option value="10">10</option>
            <option value="20">20</option>
            <option value="30">30</option>
            <option value="40">40</option>
            <option value="50">50</option>
        </select>
    </div>
    <button id="fullscreen-btn">Enter Fullscreen</button>
    <script>
        function fetchISO() {
            // Replace '/iso_value' with your actual endpoint to fetch ISO value
            fetch('/iso_value')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('overlay').innerText = `ISO: ${data.iso} | Shutter Angle: ${getCurrentShutterSpeed()} | FPS: ${getCurrentFPS()}`;
                })
                .catch(error => {
                    console.error('Error fetching ISO value:', error);
                });
        }

        function fetchShutterSpeed() {
            // Replace '/shutter_a_value' with your actual endpoint to fetch Shutter Angle value
            fetch('/shutter_a_value')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('overlay').innerText = `ISO: ${getCurrentISO()} | Shutter Angle: ${data.shutter_a} | FPS: ${getCurrentFPS()}`;
                })
                .catch(error => {
                    console.error('Error fetching Shutter Angle value:', error);
                });
        }

        function fetchFPS() {
            // Replace '/fps_value' with your actual endpoint to fetch FPS value
            fetch('/fps_value')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('overlay').innerText = `ISO: ${getCurrentISO()} | Shutter Angle: ${getCurrentShutterSpeed()} | FPS: ${data.fps}`;
                })
                .catch(error => {
                    console.error('Error fetching FPS value:', error);
                });
        }

        function getCurrentISO() {
            const overlayText = document.getElementById('overlay').innerText;
            return overlayText.split(' | ')[0].split(': ')[1];
        }

        function getCurrentShutterSpeed() {
            const overlayText = document.getElementById('overlay').innerText;
            return overlayText.split(' | ')[1].split(': ')[1];
        }

        function getCurrentFPS() {
            const overlayText = document.getElementById('overlay').innerText;
            return overlayText.split(' | ')[2].split(': ')[1];
        }

        // Fetch ISO value initially and set interval to update every 1 second
        fetchISO();
        setInterval(fetchISO, 1000); // Update ISO every 1 second

        // Fetch Shutter Angle value initially and set interval to update every 1 second
        fetchShutterSpeed();
        setInterval(fetchShutterSpeed, 1000); // Update Shutter Angle every 1 second

        // Fetch FPS value initially and set interval to update every 1 second
        fetchFPS();
        setInterval(fetchFPS, 1000); // Update FPS every 1 second

        // Add event listener for clicking on overlay to show dropdown
        document.getElementById('overlay').addEventListener('click', function() {
            document.getElementById('iso-dropdown').classList.toggle('show');
            document.getElementById('shutter-dropdown').classList.remove('show');
            document.getElementById('fps-dropdown').classList.remove('show');
        });

        // Add event listener for selecting ISO from dropdown
        document.getElementById('iso-select').addEventListener('change', function() {
            const selectedIso = this.value;
            fetch('/set_iso', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ iso: selectedIso }),
            })
            .then(response => response.json())
            .then(data => {
                console.log('ISO set successfully:', data);
                // Optionally update UI or provide feedback
            })
            .catch(error => {
                console.error('Error setting ISO:', error);
                // Handle error as needed
            });
        });

        // Add event listener for selecting Shutter Angle from dropdown
        document.getElementById('shutter-speed-select').addEventListener('change', function() {
            const selectedShutterSpeed = this.value;
            fetch('/set_shutter_a', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ shutter_a: selectedShutterSpeed }),
            })
            .then(response => response.json())
            .then(data => {
                console.log('Shutter Angle set successfully:', data);
                // Optionally update UI or provide feedback
                })
            .catch(error => {
                console.error('Error setting Shutter Angle:', error);
                // Handle error as needed
            });
        });

        // Add event listener for selecting FPS from dropdown
        document.getElementById('fps-select').addEventListener('change', function() {
            const selectedFPS = this.value;
            fetch('/set_fps', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ fps: selectedFPS }),
            })
            .then(response => response.json())
            .then(data => {
                console.log('FPS set successfully:', data);
                // Optionally update UI or provide feedback
            })
            .catch(error => {
                console.error('Error setting FPS:', error);
                // Handle error as needed
            });
        });

        // Function to toggle full-screen mode
        function toggleFullScreen() {
            const elem = document.documentElement;

            if (!document.fullscreenElement && !document.webkitFullscreenElement && !document.msFullscreenElement) {
                // Enter full-screen mode
                if (elem.requestFullscreen) {
                    elem.requestFullscreen().catch(err => {
                        console.error('Error attempting to enable full-screen mode:', err.message);
                    });
                } else if (elem.webkitRequestFullscreen) { /* Safari */
                    elem.webkitRequestFullscreen(Element.ALLOW_KEYBOARD_INPUT).catch(err => {
                        console.error('Error attempting to enable full-screen mode:', err.message);
                    });
                } else if (elem.msRequestFullscreen) { /* IE11 */
                    elem.msRequestFullscreen().catch(err => {
                        console.error('Error attempting to enable full-screen mode:', err.message);
                    });
                }
            } else {
                // Exit full-screen mode
                if (document.exitFullscreen) {
                    document.exitFullscreen().catch(err => {
                        console.error('Error attempting to exit full-screen mode:', err.message);
                    });
                } else if (document.webkitExitFullscreen) { /* Safari */
                    document.webkitExitFullscreen().catch(err => {
                        console.error('Error attempting to exit full-screen mode:', err.message);
                    });
                } else if (document.msExitFullscreen) { /* IE11 */
                    document.msExitFullscreen().catch(err => {
                        console.error('Error attempting to exit full-screen mode:', err.message);
                    });
                }
            }
        }

        // Add event listener for full-screen button
        document.getElementById('fullscreen-btn').addEventListener('click', function() {
            toggleFullScreen();
            updateFullscreenButton(); // Update button text immediately after click
        });

        // Detect changes in full-screen state and update button text accordingly
        document.addEventListener('fullscreenchange', updateFullscreenButton);
        document.addEventListener('webkitfullscreenchange', updateFullscreenButton);
        document.addEventListener('msfullscreenchange', updateFullscreenButton);

        function updateFullscreenButton() {
            const isInFullScreen = (document.fullscreenElement || document.webkitFullscreenElement || document.msFullscreenElement) !== null;
            const fullscreenBtn = document.getElementById('fullscreen-btn');

            if (isInFullScreen) {
                fullscreenBtn.textContent = 'Exit Fullscreen';
            } else {
                fullscreenBtn.textContent = 'Enter Fullscreen';
            }
        }
        
        // Detect touchstart to initiate full-screen on iOS
        document.getElementById('fullscreen-btn').addEventListener('touchstart', function(event) {
            event.preventDefault(); // Prevent the default behavior
            toggleFullScreen();
            updateFullscreenButton(); // Update button text immediately after touch
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    dynamic_data = {
        "iso": "Initializing...",  # Initial data for ISO (replace with actual initialization logic)
        "shutter_a": "Initializing...",  # Initial data for shutter angle
        "fps": "Initializing..."  # Initial data for FPS
    }
    return render_template_string(html_template, stream_url=stream_url, dynamic_data=dynamic_data)

@app.route('/iso_value')
def get_iso_value():
    iso_value = redis_controller.get_value("iso")  # Fetch ISO value from Redis (adjust based on your implementation)
    return jsonify({"iso": iso_value})

@app.route('/shutter_a_value')
def get_shutter_a_value():
    shutter_a_value = redis_controller.get_value("shutter_a")  # Fetch Shutter Angle value from Redis
    return jsonify({"shutter_a": shutter_a_value})

@app.route('/fps_value')
def get_fps_value():
    fps_value = redis_controller.get_value("fps")  # Fetch FPS value from Redis
    return jsonify({"fps": fps_value})

@app.route('/set_iso', methods=['POST'])
def set_iso_value():
    iso = request.json.get('iso')
    if iso:
        redis_controller.set_value("iso", iso)
        redis_controller.publish_message("cp_controls", "iso")  # Publish ISO value to 'cp_controls'
        return jsonify({"status": "success", "iso": iso})
    else:
        return jsonify({"status": "error", "message": "ISO value not provided"})

@app.route('/set_shutter_a', methods=['POST'])
def set_shutter_a_value():
    shutter_a = request.json.get('shutter_a')
    if shutter_a:
        redis_controller.set_value("shutter_a", shutter_a)
        redis_controller.publish_message("cp_controls", "shutter_a")  # Publish Shutter Angle value
        return jsonify({"status": "success", "shutter_a": shutter_a})
    else:
        return jsonify({"status": "error", "message": "Shutter Angle value not provided"})

@app.route('/set_fps', methods=['POST'])
def set_fps_value():
    fps = request.json.get('fps')
    if fps:
        redis_controller.set_value("fps", fps)
        redis_controller.publish_message("cp_controls", "fps")  # Publish FPS value
        return jsonify({"status": "success", "fps": fps})
    else:
        return jsonify({"status": "error", "message": "FPS value not provided"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
           
