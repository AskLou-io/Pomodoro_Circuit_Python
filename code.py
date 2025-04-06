import board
import busio
import displayio
import terminalio
import time
import math
import digitalio
import gc9a01
import array
import analogio  # For onboard microphone
from adafruit_display_text import label
from adafruit_display_shapes.circle import Circle
from fourwire import FourWire  # Updated import per deprecation notice

# Release any displays
displayio.release_displays()

# Define pins
tft_dc = board.D3
tft_cs = board.D1
tft_bl = board.D6

# Set up SPI display
spi = busio.SPI(clock=board.SCK, MOSI=board.MOSI)
display_bus = FourWire(spi, command=tft_dc, chip_select=tft_cs)
display = gc9a01.GC9A01(display_bus, width=240, height=240, rotation=0)

# Backlight
backlight = digitalio.DigitalInOut(tft_bl)
backlight.direction = digitalio.Direction.OUTPUT
backlight.value = True

# --- Onboard microphone setup ---
# Using AnalogIn on board.A0 for XIAO ESP32-S3 Sense onboard mic.
mic = analogio.AnalogIn(board.A0)
# You might need to adjust the threshold value after testing
LOUD_THRESHOLD = 30000

def detect_loud_sound():
    """
    Returns True if the microphone analog reading exceeds the threshold.
    """
    try:
        # Read the analog value (0 - 65535)
        value = mic.value
        return value > LOUD_THRESHOLD
    except Exception as e:
        print("Microphone error:", e)
        return False

# Create root display groups
main_group = displayio.Group()
background_group = displayio.Group()
foreground_group = displayio.Group()
main_group.append(background_group)
main_group.append(foreground_group)
display.root_group = main_group

# Create background circle
circle_bg = Circle(120, 120, 100, outline=0x444444)
background_group.append(circle_bg)

# Session types
WORK = "WORK"
BREAK = "BREAK"
LONG_BREAK = "LONG"

session_durations = {
    WORK: 25 * 60,
    BREAK: 5 * 60,
    LONG_BREAK: 15 * 60,
}

# Session cycle is only used for timer rollover if you want an automatic cycle.
# You can modify this behavior as needed.
session_cycle = [WORK, BREAK] * 3 + [WORK, LONG_BREAK]

# UI Labels
session_label = label.Label(terminalio.FONT, text="", color=0xFFFFFF, scale=2)
session_label.x = 90
session_label.y = 80
foreground_group.append(session_label)

timer_label = label.Label(terminalio.FONT, text="", color=0xFFFFFF, scale=3)
timer_label.x = 75
timer_label.y = 120
foreground_group.append(timer_label)

# Optional: Remove status label since you only want voice commands.
# status_label = label.Label(terminalio.FONT, text="", color=0xFFFFFF)
# status_label.x = 80
# status_label.y = 160
# foreground_group.append(status_label)

# Pre-create arc segments for performance
arc_segments = []
arc_radius = 95
total_steps = 120  # Reduced for performance
arc_color_work = 0x00FF00
arc_color_break = 0x00BFFF

for i in range(total_steps):
    angle = math.radians(i * (360 / total_steps))
    x = int(120 + arc_radius * math.cos(angle))
    y = int(120 + arc_radius * math.sin(angle))
    pixel = Circle(x, y, 2, fill=0x000000, outline=0x000000)
    foreground_group.append(pixel)
    arc_segments.append(pixel)

def update_progress_arc(percentage, session_type):
    steps = int(percentage * total_steps)
    
    # Choose arc color based on session type
    active_color = arc_color_work if session_type == WORK else arc_color_break
    
    for i, segment in enumerate(arc_segments):
        segment.fill = active_color if i < steps else 0x000000

def format_time(seconds):
    m = seconds // 60
    s = seconds % 60
    return f"{m:02}:{s:02}"

# --- Voice Commands ---
# Commands: "start timer", "pause timer", "start short break", "start long break"
voice_commands = ["start timer", "pause timer", "start short break", "start long break"]
voice_index = 0

def simulate_voice_command():
    global voice_index, current_session, session_seconds, session_start, timer_active
    command = voice_commands[voice_index]
    print(f"Voice Command Detected: {command}")
    
    if command == "start timer":
        timer_active = True
        # If starting timer, use current session or default to WORK if not set.
        if current_session not in [WORK, BREAK, LONG_BREAK]:
            current_session = WORK
            session_seconds = session_durations[WORK]
        session_start = time.monotonic()
    elif command == "pause timer":
        timer_active = False
    elif command == "start short break":
        current_session = BREAK
        session_seconds = session_durations[BREAK]
        timer_active = True
        session_start = time.monotonic()
    elif command == "start long break":
        current_session = LONG_BREAK
        session_seconds = session_durations[LONG_BREAK]
        timer_active = True
        session_start = time.monotonic()
    
    # Cycle to the next command for testing/demo purposes.
    voice_index = (voice_index + 1) % len(voice_commands)

# Initial session settings
session_index = 0
current_session = WORK  # default session
session_seconds = session_durations[current_session]
timer_active = False  # Timer is paused until a voice command starts it
session_start = time.monotonic()

update_progress_arc(0, current_session)

# For debouncing the voice command trigger
last_sound_time = time.monotonic()

# Display version label (optional)
version_label = label.Label(terminalio.FONT, text="v1.2", color=0x888888)
version_label.x = 5
version_label.y = 5
foreground_group.append(version_label)

# Main loop
last_second = -1

while True:
    now = time.monotonic()
    
    # Check for loud sound to trigger a voice command.
    # We check at least 1 second apart to debounce.
    if detect_loud_sound() and (now - last_sound_time) > 1.0:
        simulate_voice_command()
        last_sound_time = now

    if timer_active:
        elapsed = int(now - session_start)
        remaining = session_seconds - elapsed
        
        if remaining <= 0:
            # Timer finished, automatically move to next session in cycle
            session_index = (session_index + 1) % len(session_cycle)
            current_session = session_cycle[session_index]
            session_seconds = session_durations[current_session]
            session_start = now
            remaining = session_seconds
    else:
        # Timer paused: keep the remaining time static
        elapsed = int(now - session_start)
        remaining = session_seconds - elapsed

    # Update display only if the second has changed
    current_second = int(remaining)
    if current_second != last_second:
        session_label.text = current_session
        timer_label.text = format_time(remaining)
        update_progress_arc(1.0 - (remaining / session_seconds), current_session)
        last_second = current_second

    time.sleep(0.1)
