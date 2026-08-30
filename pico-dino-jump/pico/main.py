# Pico Dino Jump
#
# A Chrome-style endless runner for the Raspberry Pi Pico 2 W + SSD1306
# OLED (128x64, I2C), controlled remotely by arrow key presses forwarded
# from a PC over USB serial (see host/keyboard_controller.py).
#
# Upload this file as main.py (alongside ssd1306.py) so it runs
# automatically when the Pico boots.

import machine
import random
import select
import sys
import utime

import ssd1306

# ---------------------------------------------------------------------------
# Configuration - adjust to match your wiring / preferred difficulty
# ---------------------------------------------------------------------------
I2C_ID = 0
SDA_PIN = 0
SCL_PIN = 1
I2C_FREQ = 400000
OLED_WIDTH = 128
OLED_HEIGHT = 64
OLED_ADDR = 0x3C

# Set to a GPIO number (e.g. 16) to enable an optional physical jump
# button (wired to that pin and GND). Leave as None to use only the
# keyboard controller.
PHYSICAL_BUTTON_PIN = None

GROUND_Y = 54
DINO_X = 10
STAND_W, STAND_H = 14, 16
DUCK_W, DUCK_H = 22, 8

GRAVITY = 2.2
JUMP_VELOCITY = -13.5

FRAME_DELAY_MS = 30

# ---------------------------------------------------------------------------
# Hardware setup
# ---------------------------------------------------------------------------
i2c = machine.I2C(
    I2C_ID, sda=machine.Pin(SDA_PIN), scl=machine.Pin(SCL_PIN), freq=I2C_FREQ
)
oled = ssd1306.SSD1306_I2C(OLED_WIDTH, OLED_HEIGHT, i2c, addr=OLED_ADDR)

button = None
if PHYSICAL_BUTTON_PIN is not None:
    button = machine.Pin(PHYSICAL_BUTTON_PIN, machine.Pin.IN, machine.Pin.PULL_UP)

poll = select.poll()
poll.register(sys.stdin, select.POLLIN)


def read_serial_commands():
    """Non-blocking read of any command bytes sent by the PC controller."""
    commands = []
    while poll.poll(0):
        ch = sys.stdin.read(1)
        if ch:
            commands.append(ch)
        else:
            break
    return commands


def rects_overlap(x1, y1, w1, h1, x2, y2, w2, h2):
    return x1 < x2 + w2 and x1 + w1 > x2 and y1 < y2 + h2 and y1 + h1 > y2


# ---------------------------------------------------------------------------
# Dino
# ---------------------------------------------------------------------------
class Dino:
    def __init__(self):
        self.reset()

    def reset(self):
        self.y = float(GROUND_Y - STAND_H)
        self.vel_y = 0.0
        self.on_ground = True
        self.ducking = False
        self.anim_frame = 0

    @property
    def width(self):
        return DUCK_W if self.ducking else STAND_W

    @property
    def height(self):
        return DUCK_H if self.ducking else STAND_H

    @property
    def top(self):
        return GROUND_Y - self.height if self.on_ground else int(self.y)

    def jump(self):
        if self.on_ground:
            self.ducking = False
            self.vel_y = JUMP_VELOCITY
            self.on_ground = False

    def duck(self, active):
        if self.on_ground:
            self.ducking = active

    def update(self):
        if not self.on_ground:
            self.vel_y += GRAVITY
            self.y += self.vel_y
            floor = GROUND_Y - self.height
            if self.y >= floor:
                self.y = float(floor)
                self.vel_y = 0.0
                self.on_ground = True
        self.anim_frame = (self.anim_frame + 1) % 20

    def draw(self, oled):
        y = self.top
        w = self.width
        h = self.height
        oled.fill_rect(DINO_X, y, w, h, 1)
        # simple running-legs animation while on the ground
        if self.on_ground and not self.ducking:
            if (self.anim_frame // 10) == 0:
                oled.fill_rect(DINO_X + 1, GROUND_Y - 3, 2, 3, 0)
            else:
                oled.fill_rect(DINO_X + w - 3, GROUND_Y - 3, 2, 3, 0)


# ---------------------------------------------------------------------------
# Obstacles
# ---------------------------------------------------------------------------
class Cactus:
    def __init__(self, x):
        self.x = float(x)
        self.h = random.choice((8, 12, 16))
        self.w = 6

    @property
    def y(self):
        return GROUND_Y - self.h

    def update(self, speed):
        self.x -= speed

    def offscreen(self):
        return self.x + self.w < 0

    def draw(self, oled):
        oled.fill_rect(int(self.x), self.y, self.w, self.h, 1)

    def collides(self, dino):
        return rects_overlap(
            DINO_X, dino.top, dino.width, dino.height, int(self.x), self.y, self.w, self.h
        )


class Bird:
    """Flies at standing head-height - must be ducked under, not jumped over."""

    def __init__(self, x):
        self.x = float(x)
        self.w = 10
        self.h = 6
        self.y = GROUND_Y - STAND_H + 2
        self.anim_frame = 0

    def update(self, speed):
        self.x -= speed
        self.anim_frame = (self.anim_frame + 1) % 20

    def offscreen(self):
        return self.x + self.w < 0

    def draw(self, oled):
        flap = (self.anim_frame // 10) == 0
        h = self.h if flap else self.h - 2
        oled.fill_rect(int(self.x), self.y, self.w, h, 1)

    def collides(self, dino):
        return rects_overlap(
            DINO_X, dino.top, dino.width, dino.height, int(self.x), self.y, self.w, self.h
        )


# ---------------------------------------------------------------------------
# Game loop
# ---------------------------------------------------------------------------
def draw_ground(scroll):
    for gx in range(int(scroll), OLED_WIDTH, 8):
        oled.fill_rect(gx, GROUND_Y, 4, 1, 1)


def game_loop():
    dino = Dino()
    obstacles = []
    state = "START"
    score = 0
    speed = 3.0
    spawn_timer = 0
    ground_scroll = 0.0

    while True:
        commands = read_serial_commands()
        jump_pressed = False
        for ch in commands:
            if ch in ("U", "u"):
                jump_pressed = True
            elif ch == "D":
                dino.duck(True)
            elif ch == "d":
                dino.duck(False)

        if button is not None and button.value() == 0:
            jump_pressed = True

        if jump_pressed:
            if state == "START":
                state = "RUNNING"
            elif state == "RUNNING":
                dino.jump()
            elif state == "GAME_OVER":
                dino.reset()
                obstacles = []
                state = "RUNNING"
                score = 0
                speed = 3.0
                spawn_timer = 0

        oled.fill(0)

        if state == "START":
            oled.text("DINO JUMP", 24, 20)
            oled.text("Press UP", 28, 36)
            oled.text("to start", 28, 46)
        else:
            if state == "RUNNING":
                dino.update()

                spawn_timer -= 1
                if spawn_timer <= 0:
                    if random.random() < 0.7:
                        obstacles.append(Cactus(OLED_WIDTH))
                    else:
                        obstacles.append(Bird(OLED_WIDTH))
                    spawn_timer = random.randint(35, 70)

                for obs in obstacles:
                    obs.update(speed)
                obstacles = [o for o in obstacles if not o.offscreen()]

                for obs in obstacles:
                    if obs.collides(dino):
                        state = "GAME_OVER"
                        break

                score += 1
                if score % 300 == 0:
                    speed = min(speed + 0.5, 9.0)

            ground_scroll = (ground_scroll - speed) % 8
            draw_ground(ground_scroll)

            dino.draw(oled)
            for obs in obstacles:
                obs.draw(oled)

            oled.text(str(score // 5), 92, 0)

            if state == "GAME_OVER":
                oled.text("GAME OVER", 26, 24)
                oled.text("UP=restart", 20, 36)

        oled.show()
        utime.sleep_ms(FRAME_DELAY_MS)


game_loop()
