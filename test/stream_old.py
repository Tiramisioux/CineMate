import logging
from flask import Flask, render_template, jsonify, request
import redis
import os


class Stream:
    def __init__(self, redis_host='localhost', redis_port=6379, redis_db=0, stream_url="http://cinepi.local:8000/stream"):
        self.app = Flask(__name__)
        self.redis_controller = self.RedisController(redis_host, redis_port, redis_db)
        self.stream_url = stream_url
        
        # Set the absolute path to the templates folder
        template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
        self.app.template_folder = template_dir

        # Fetch current values from Redis and set them in RedisController instance
        self.set_initial_values()

        # Routes
        self.app.add_url_rule('/', 'index', self.index)
        self.app.add_url_rule('/iso_value', 'get_iso_value', self.get_iso_value)
        self.app.add_url_rule('/shutter_a_value', 'get_shutter_a_value', self.get_shutter_a_value)
        self.app.add_url_rule('/fps_value', 'get_fps_value', self.get_fps_value)
        self.app.add_url_rule('/set_iso', 'set_iso_value', self.set_iso_value, methods=['POST'])
        self.app.add_url_rule('/set_shutter_a', 'set_shutter_a_value', self.set_shutter_a_value, methods=['POST'])
        self.app.add_url_rule('/set_fps', 'set_fps_value', self.set_fps_value, methods=['POST'])

    class RedisController:
        def __init__(self, redis_host, redis_port, redis_db):
            self.redis_conn = redis.StrictRedis(host=redis_host, port=redis_port, db=redis_db)

        def get_value(self, key):
            return self.redis_conn.get(key).decode('utf-8') if self.redis_conn.exists(key) else None

        def set_value(self, key, value):
            self.redis_conn.set(key, value)

        def publish_message(self, channel, message):
            self.redis_conn.publish(channel, message)
    
    def set_initial_values(self):
        # Fetch current values from Redis and set them in RedisController instance
        iso_value = self.redis_controller.get_value("iso")
        if iso_value:
            self.redis_controller.set_value("iso", iso_value)

        shutter_a_value = self.redis_controller.get_value("shutter_a")
        if shutter_a_value:
            self.redis_controller.set_value("shutter_a", shutter_a_value)

        fps_value = self.redis_controller.get_value("fps")
        if fps_value:
            self.redis_controller.set_value("fps", fps_value)

    def index(self):
        # Fetch current values from Redis
        iso_value = self.redis_controller.get_value("iso")
        shutter_a_value = self.redis_controller.get_value("shutter_a")
        fps_value = self.redis_controller.get_value("fps")
        
        # Initialize dynamic data with default values or fetched values
        dynamic_data = {
            "iso": iso_value if iso_value else "Initializing...",
            "shutter_a": shutter_a_value if shutter_a_value else "Initializing...",
            "fps": fps_value if fps_value else "Initializing..."
        }
        
        # Render the template with dynamic data and stream_url
        return render_template('template.html', stream_url=self.stream_url, dynamic_data=dynamic_data)

    def get_iso_value(self):
        iso_value = self.redis_controller.get_value("iso")  # Fetch ISO value from Redis
        return jsonify({"iso": iso_value})

    def get_shutter_a_value(self):
        shutter_a_value = self.redis_controller.get_value("shutter_a")  # Fetch Shutter Angle value from Redis
        return jsonify({"shutter_a": shutter_a_value})

    def get_fps_value(self):
        fps_value = self.redis_controller.get_value("fps")  # Fetch FPS value from Redis
        return jsonify({"fps": fps_value})

    def set_iso_value(self):
        iso = request.json.get('iso')
        if iso:
            self.redis_controller.set_value("iso", iso)
            self.redis_controller.publish_message("cp_controls", "iso")  # Publish ISO value to 'cp_controls'
            return jsonify({"status": "success", "iso": iso})
        else:
            return jsonify({"status": "error", "message": "ISO value not provided"})

    def set_shutter_a_value(self):
        shutter_a = request.json.get('shutter_a')
        if shutter_a:
            self.redis_controller.set_value("shutter_a", shutter_a)
            self.redis_controller.publish_message("cp_controls", "shutter_a")  # Publish Shutter Angle value
            return jsonify({"status": "success", "shutter_a": shutter_a})
        else:
            return jsonify({"status": "error", "message": "Shutter Angle value not provided"})

    def set_fps_value(self):
        fps = request.json.get('fps')
        if fps:
            self.redis_controller.set_value("fps", fps)
            self.redis_controller.publish_message("cp_controls", "fps")  # Publish FPS value
            return jsonify({"status": "success", "fps": fps})
        else:
            return jsonify({"status": "error", "message": "FPS value not provided"})

    def run(self, host='0.0.0.0', port=5000):
        # Adjust Flask's internal log level to ERROR (or higher) to mute INFO messages
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)
        
        self.app.run(host=host, port=port)

# # Start the server
# if __name__ == '__main__':
#     stream = Stream()
#     stream.run()
