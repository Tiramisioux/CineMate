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
        self.redis_client.set(key, value)
        self.redis_client.publish('cp_controls', key)

class TimeMonitor:
    def __init__(self, redis_controller, target_framerate=24.0):
        self.redis_controller = redis_controller
        self.target_framerate = target_framerate
        self.total_frames = 0
        self.start_time = time.time()
        self.cumulative_error = 0.0  # Track cumulative error
        self.frame_rate_window = deque(maxlen=100)  # Track the last 100 frame rates
        self.total_frame_rate_sum = 0.0  # Sum of all frame rates since start
        self.flip_fps_values = [23.975, 23.976]  # Alternating FPS values
        self.current_flip_index = 0

        self.listener_thread = threading.Thread(target=self.listen)
        self.listener_thread.daemon = True
        self.listener_thread.start()

        self.flip_thread = threading.Thread(target=self.manage_fps)
        self.flip_thread.daemon = True
        self.flip_thread.start()

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
                            self.total_frame_rate_sum += framerate
                            deviation = framerate - self.target_framerate
                            self.cumulative_error += deviation
                            self.frame_rate_window.append(framerate)

                            # Calculate elapsed time and effective FPS
                            elapsed_time = time.time() - self.start_time
                            effective_fps = self.total_frames / elapsed_time if elapsed_time > 0 else 0

                            # Calculate average frame rate of the last 100 frames
                            recent_average_fps = sum(self.frame_rate_window) / len(self.frame_rate_window) if len(self.frame_rate_window) > 0 else 0

                            # Calculate average frame rate of all frames since start
                            overall_average_fps = self.total_frame_rate_sum / self.total_frames if self.total_frames > 0 else 0

                            logger.info(f"Current Frame Rate: {framerate:.6f} FPS | Effective FPS: {effective_fps:.6f} | Cumulative Error: {self.cumulative_error:.6f} | Recent Average FPS (Last 100): {recent_average_fps:.6f} | Overall Average FPS: {overall_average_fps:.6f}")

                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse JSON data: {e}")

    def manage_fps(self):
        last_cumulative_error = 0.0
        error_rate_smoothing = deque(maxlen=10)  # Smooth the error rate over the last 10 iterations

        while True:
            try:
                # Set the current FPS value in Redis
                current_fps = self.flip_fps_values[self.current_flip_index]
                self.redis_controller.set_value('fps', current_fps)
                logger.info(f"Set Redis FPS to {current_fps:.3f}")

                # Calculate recent average FPS
                recent_average_fps = sum(self.frame_rate_window) / len(self.frame_rate_window) if len(self.frame_rate_window) > 0 else 0

                # Calculate expected correction per frame
                expected_correction_per_frame = (current_fps - self.target_framerate) / current_fps

                # Estimate frames needed to correct current error
                if expected_correction_per_frame != 0:
                    frames_needed = abs(self.cumulative_error / expected_correction_per_frame)
                else:
                    frames_needed = 100  # Default to 100 frames if correction per frame is zero (unlikely case)

                # Convert frames needed to time (in seconds) based on current FPS
                hold_time = frames_needed / current_fps

                # Adjust hold time based on recent FPS trends and error rate
                if recent_average_fps < self.target_framerate:
                    hold_time *= 1.1  # Extend hold time if recent FPS is below target
                elif recent_average_fps > self.target_framerate:
                    hold_time *= 0.9  # Shorten hold time if recent FPS is above target

                # Calculate error rate and smooth it
                error_rate = (self.cumulative_error - last_cumulative_error) / max(1, hold_time)
                error_rate_smoothing.append(error_rate)
                smoothed_error_rate = sum(error_rate_smoothing) / len(error_rate_smoothing)

                if smoothed_error_rate > 0:
                    hold_time *= 0.95  # Reduce hold time slightly if error is increasing
                elif smoothed_error_rate < 0:
                    hold_time *= 1.05  # Increase hold time slightly if error is decreasing

                # Cap hold time to a reasonable range
                hold_time = max(1, min(10, hold_time))

                logger.info(
                    f"Holding FPS {current_fps:.3f} for {hold_time:.2f} seconds | "
                    f"Cumulative Error: {self.cumulative_error:.6f} | Expected Correction/Frame: {expected_correction_per_frame:.6f} | "
                    f"Recent Average FPS: {recent_average_fps:.6f} | Smoothed Error Rate: {smoothed_error_rate:.6f}"
                )

                # Update last cumulative error
                last_cumulative_error = self.cumulative_error

                # Wait for the calculated hold time
                time.sleep(hold_time)

                # Switch FPS values
                self.current_flip_index = (self.current_flip_index + 1) % len(self.flip_fps_values)
            except Exception as e:
                logger.error(f"Exception in manage_fps: {e}")

    def stop(self):
        self.listener_thread.join()
        self.flip_thread.join()
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
