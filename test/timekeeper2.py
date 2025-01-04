import logging
import threading
import time
import json
import sys
import redis
from collections import deque

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler("timekeeper_results.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class RedisController:
    def __init__(self):
        self.redis_client = redis.StrictRedis(host='localhost', port=6379, db=0)
    
    def get_value(self, key):
        value = self.redis_client.get(key)
        return float(value) if value else None

    def set_value(self, key, value):
        try:
            self.redis_client.set(key, value)
        except Exception as e:
            logger.error(f"Failed to set Redis key '{key}' to value '{value}': {e}")

class TimeMonitor:
    def __init__(self, redis_controller, target_framerate=24.0):
        self.redis_controller = redis_controller
        self.target_framerate = target_framerate
        self.total_frames = 0
        self.start_time = time.time()
        self.cumulative_error = 0.0  # Track cumulative error
        self.frame_rate_window = deque(maxlen=100)  # Last 100 frame rates
        self.lower_bound = None
        self.upper_bound = None
        self.use_lower_value = True  # Start with the lower bound

        self.listener_thread = threading.Thread(target=self.listen)
        self.listener_thread.daemon = True
        self.listener_thread.start()

        self.find_optimal_bounds_thread = threading.Thread(target=self.find_optimal_bounds)
        self.find_optimal_bounds_thread.daemon = True
        self.find_optimal_bounds_thread.start()

    def listen(self):
        pubsub = self.redis_controller.redis_client.pubsub()
        pubsub.subscribe('cp_stats')

        while True:
            for message in pubsub.listen():
                if message['type'] == 'message':
                    try:
                        stats_data = json.loads(message['data'].decode('utf-8').strip())
                        framerate = stats_data.get('framerate', None)
                        if framerate is not None and framerate > 0:
                            self.total_frames += 1
                            deviation = framerate - self.target_framerate
                            self.cumulative_error += deviation

                            # Add frame rate to the rolling window
                            self.frame_rate_window.append(framerate)
                            recent_average_fps = sum(self.frame_rate_window) / len(self.frame_rate_window)

                            # Calculate elapsed time and effective FPS
                            elapsed_time = time.time() - self.start_time
                            effective_fps = self.total_frames / elapsed_time if elapsed_time > 0 else 0

                            logger.info(f"Current Frame Rate: {framerate:.6f} FPS | Effective FPS: {effective_fps:.6f} | Cumulative Error: {self.cumulative_error:.6f} | Recent Average FPS (Last 100): {recent_average_fps:.6f}")

                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse JSON data: {e}")

    def find_optimal_bounds(self):
        step = 0.001
        margin = 0.010
        lower_fps = self.target_framerate - margin
        upper_fps = self.target_framerate + margin

        optimal_lower = None
        optimal_upper = None

        while not (optimal_lower and optimal_upper):
            for fps in [round(lower_fps + step * i, 3) for i in range(int((upper_fps - lower_fps) / step) + 1)]:
                try:
                    self.redis_controller.set_value('fps', fps)
                    self.redis_controller.redis_client.publish('cp_controls', 'fps')
                    logger.info(f"Testing FPS: {fps:.3f}")
                    time.sleep(5)  # Allow for 100 frames

                    if len(self.frame_rate_window) == self.frame_rate_window.maxlen:
                        recent_average_fps = sum(self.frame_rate_window) / len(self.frame_rate_window)

                        logger.info(f"Tested FPS: {fps:.3f} | Recent Average FPS: {recent_average_fps:.6f}")

                        if recent_average_fps < self.target_framerate and (optimal_lower is None or (recent_average_fps > self.target_framerate - 0.001 and recent_average_fps > optimal_lower)):
                            optimal_lower = fps
                            logger.info(f"New Optimal Lower FPS: {optimal_lower:.3f}")
                        elif recent_average_fps > self.target_framerate and (optimal_upper is None or (recent_average_fps < self.target_framerate + 0.001 and recent_average_fps < optimal_upper)):
                            optimal_upper = fps
                            logger.info(f"New Optimal Upper FPS: {optimal_upper:.3f}")

                except Exception as e:
                    logger.error(f"Error during FPS testing for {fps:.3f}: {e}")

            if optimal_lower and optimal_upper:
                self.lower_bound = optimal_lower
                self.upper_bound = optimal_upper
                self.cumulative_error = 0  # Reset accumulated error
                logger.info(f"Optimal Bounds Found: Lower FPS={self.lower_bound:.3f} (Avg FPS={sum(self.frame_rate_window) / len(self.frame_rate_window):.6f}), Upper FPS={self.upper_bound:.3f} (Avg FPS={sum(self.frame_rate_window) / len(self.frame_rate_window):.6f})")
                self.start_flip_switch_mechanism()
                return

    def start_flip_switch_mechanism(self):
        error_threshold = 0.001  # Threshold for accumulated error to trigger a switch
        monitoring_interval = 0.1  # Check every 0.5 seconds

        while True:
            try:
                # Determine current FPS based on flip state
                current_fps = self.lower_bound if self.use_lower_value else self.upper_bound
                self.redis_controller.set_value('fps', current_fps)
                self.redis_controller.redis_client.publish('cp_controls', 'fps')
                logger.info(f"Switching FPS to: {current_fps:.3f}")

                # Monitor and switch based on cumulative error
                accumulated_error_start = self.cumulative_error
                time.sleep(monitoring_interval * 1)  # Wait for 10 intervals

                # Calculate the difference in accumulated error
                accumulated_error_diff = self.cumulative_error - accumulated_error_start
                logger.info(f"Accumulated Error Change: {accumulated_error_diff:.6f}")

                # Flip only if the accumulated error shows significant correction need
                if abs(self.cumulative_error) > error_threshold or accumulated_error_diff > 0:
                    self.use_lower_value = not self.use_lower_value  # Flip the switch
                    logger.info(f"Flipping FPS switch. New State: {'Lower' if self.use_lower_value else 'Upper'}")
                    #self.cumulative_error = 0  # Reset accumulated error after switching

            except Exception as e:
                logger.error(f"Error in flip switch mechanism: {e}")

    def stop(self):
        self.listener_thread.join()
        self.find_optimal_bounds_thread.join()
        logger.info("TimeMonitor stopped.")

def main():
    redis_controller = RedisController()
    time_monitor = TimeMonitor(redis_controller, target_framerate=24.0)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        time_monitor.stop()
        print("\nMonitoring stopped.")
        logger.info("Monitoring stopped by user.")

if __name__ == "__main__":
    main()
