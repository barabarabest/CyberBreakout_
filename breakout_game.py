#!/usr/bin/env python3
"""
================================================================================
CYBERPUNK BREAKOUT (CASSE-BRIQUE) - PRODUCTION GAME ENGINE
================================================================================
A complete, self-contained arcade Breakout experience built with Pygame.

Features:
- 20 progressive difficulty levels (Standard, Reinforced, Moving, Iron, Regenerating).
- Randomized Power-up system (25% drop rate: Multi-Ball, Piercing Ball, Extended Paddle).
- Built-in Procedural Audio Synthesizer (16-bit PCM mono via math & array, zero external WAV files).
- Substep continuous collision detection & anti-tunneling physics.
- Persistent High Score tracking saved automatically to highscore.json.
- Cyberpunk Neon Vector visual aesthetic with glowing trails, dynamic particles,
  floating combat text, and animated synthwave background grid.
- Dual control support: Mouse follower and Keyboard (Arrows / A-D).
================================================================================
"""

import sys
import os
import math
import time
import json
import random
import array
from collections import deque

# Suppress Pygame welcome message
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
import pygame

# ==============================================================================
# 1. ENGINE CONSTANTS & PALETTE
# ==============================================================================
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60
HUD_HEIGHT = 44

# Cyberpunk Neon Color Palette (RGB)
COLOR_BG_DARK       = (10, 10, 20)
COLOR_BG_GRID       = (22, 26, 48)
COLOR_HUD_BG        = (8, 8, 16)
COLOR_HUD_LINE      = (0, 255, 242)

COLOR_NEON_CYAN     = (0, 255, 242)
COLOR_NEON_MAGENTA  = (255, 0, 128)
COLOR_NEON_YELLOW   = (255, 230, 0)
COLOR_NEON_GREEN    = (57, 255, 20)
COLOR_NEON_ORANGE   = (255, 110, 0)
COLOR_NEON_PURPLE   = (180, 50, 255)
COLOR_NEON_BLUE     = (30, 144, 255)
COLOR_NEON_RED      = (255, 30, 60)

COLOR_IRON_BASE     = (130, 140, 160)
COLOR_IRON_BORDER   = (190, 205, 225)
COLOR_IRON_GLOW     = (80, 100, 130)

COLOR_REGEN_BASE    = (0, 210, 150)
COLOR_REGEN_GLOW    = (0, 255, 180)

COLOR_WHITE         = (255, 255, 255)
COLOR_GRAY          = (120, 120, 140)
COLOR_BLACK         = (0, 0, 0)

# Progression Constants
BASE_BALL_SPEED_PPS = 400.0  # Base ball speed in px/sec at 1.0x
BASE_BALL_SPEED     = BASE_BALL_SPEED_PPS / 60.0  # px/frame (400 px/s at 60 FPS)
SPEED_INCREMENT     = 0.045
BASE_PADDLE_WIDTH   = 115.0
PADDLE_DECAY_RATE   = 0.015
PADDLE_SPEED_KEYS   = 700.0  # px/sec for keyboard control
POWERUP_DROP_CHANCE = 0.25
POWERUP_FALL_SPEED  = 170.0  # px/sec
EXTENDED_PADDLE_DUR = 12.0   # seconds
REGEN_COOLDOWN      = 5.0    # seconds to regenerate 1 HP

HIGH_SCORE_FILE     = "highscore.json"


# ==============================================================================
# 2. PROCEDURAL SOUND SYNTHESIZER
# ==============================================================================
class ProceduralAudio:
    """
    Self-contained 16-bit PCM procedural sound effects synthesizer.
    Generates sound buffers purely using Python standard library (math & array).
    Requires zero external .wav or .mp3 files. Fails gracefully if no audio device.
    """
    SAMPLE_RATE = 44100

    def __init__(self):
        self.enabled = False
        self.sounds = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=self.SAMPLE_RATE, size=-16, channels=1, buffer=512)
            self.enabled = True
            self._generate_all_sounds()
        except Exception as err:
            print(f"[Audio] Mixer init failed or audio unavailable: {err}. Running in silent mode.")
            self.enabled = False

    def _generate_all_sounds(self):
        """Pre-computes all sound waveforms at launch for zero-latency playback."""
        self.sounds['hit_paddle']     = self._synth_paddle_bounce()
        self.sounds['hit_brick']      = self._synth_brick_hit()
        self.sounds['break_brick']    = self._synth_brick_break()
        self.sounds['hit_iron']       = self._synth_iron_ping()
        self.sounds['powerup_spawn']  = self._synth_powerup_spawn()
        self.sounds['powerup_get']    = self._synth_powerup_collect()
        self.sounds['lose_life']      = self._synth_lose_life()
        self.sounds['stage_clear']    = self._synth_stage_clear()
        self.sounds['game_over']      = self._synth_game_over()
        self.sounds['laser_pierce']   = self._synth_pierce_cut()
        self.sounds['bomb_blast']     = self._synth_bomb_blast()
        self.sounds['bottle_shatter'] = self._synth_bottle_shatter()
        self.sounds['life_gain']      = self._synth_life_gain()

    def play(self, name: str):
        if not self.enabled or name not in self.sounds:
            return
        snd = self.sounds.get(name)
        if snd:
            try:
                snd.play()
            except Exception:
                pass

    def _create_sound(self, samples: array.array) -> pygame.mixer.Sound:
        return pygame.mixer.Sound(buffer=samples)

    def _synth_paddle_bounce(self) -> pygame.mixer.Sound:
        """Upward synth blip (320Hz -> 540Hz, 0.08s)."""
        duration = 0.08
        n_samples = int(self.SAMPLE_RATE * duration)
        buf = array.array('h')
        for i in range(n_samples):
            t = i / self.SAMPLE_RATE
            freq = 320.0 + (540.0 - 320.0) * (t / duration)
            env = math.exp(-t * 35.0)
            val = math.sin(2.0 * math.pi * freq * t)
            buf.append(int(32767.0 * 0.45 * val * env))
        return self._create_sound(buf)

    def _synth_brick_hit(self) -> pygame.mixer.Sound:
        """Crisp neon click/blip (650Hz, fast exponential decay, 0.06s)."""
        duration = 0.06
        n_samples = int(self.SAMPLE_RATE * duration)
        buf = array.array('h')
        for i in range(n_samples):
            t = i / self.SAMPLE_RATE
            env = math.exp(-t * 60.0)
            val = 0.7 * math.sin(2.0 * math.pi * 650.0 * t) + 0.3 * math.sin(2.0 * math.pi * 1300.0 * t)
            buf.append(int(32767.0 * 0.5 * val * env))
        return self._create_sound(buf)

    def _synth_brick_break(self) -> pygame.mixer.Sound:
        """Resonant frequency dive with cyber crackle (450Hz -> 90Hz, 0.16s)."""
        duration = 0.16
        n_samples = int(self.SAMPLE_RATE * duration)
        buf = array.array('h')
        for i in range(n_samples):
            t = i / self.SAMPLE_RATE
            p = t / duration
            freq = 450.0 * (1.0 - p) + 90.0 * p
            noise = (random.random() * 2.0 - 1.0) * 0.25 * (1.0 - p)
            wave = math.sin(2.0 * math.pi * freq * t) + noise
            env = math.exp(-t * 18.0)
            buf.append(int(32767.0 * 0.55 * wave * env))
        return self._create_sound(buf)

    def _synth_iron_ping(self) -> pygame.mixer.Sound:
        """Metallic resonant ring (1200Hz + 2400Hz harmonics, 0.12s)."""
        duration = 0.12
        n_samples = int(self.SAMPLE_RATE * duration)
        buf = array.array('h')
        for i in range(n_samples):
            t = i / self.SAMPLE_RATE
            env = math.exp(-t * 28.0)
            val = 0.6 * math.sin(2.0 * math.pi * 1200.0 * t) + 0.4 * math.sin(2.0 * math.pi * 2400.0 * t)
            buf.append(int(32767.0 * 0.45 * val * env))
        return self._create_sound(buf)

    def _synth_powerup_spawn(self) -> pygame.mixer.Sound:
        """Futuristic twin sparkle tone (523Hz -> 784Hz, 0.12s)."""
        duration = 0.12
        n_samples = int(self.SAMPLE_RATE * duration)
        buf = array.array('h')
        for i in range(n_samples):
            t = i / self.SAMPLE_RATE
            freq = 523.25 + 260.0 * (t / duration)
            env = math.sin(math.pi * (t / duration))
            val = math.sin(2.0 * math.pi * freq * t)
            buf.append(int(32767.0 * 0.35 * val * env))
        return self._create_sound(buf)

    def _synth_powerup_collect(self) -> pygame.mixer.Sound:
        """Ascending four-tone cyber arpeggio (C5-E5-G5-C6, 0.28s)."""
        duration = 0.28
        n_samples = int(self.SAMPLE_RATE * duration)
        buf = array.array('h')
        notes = [523.25, 659.25, 783.99, 1046.50]
        sub_dur = duration / len(notes)
        for i in range(n_samples):
            t = i / self.SAMPLE_RATE
            idx = min(len(notes) - 1, int(t / sub_dur))
            local_t = t - (idx * sub_dur)
            freq = notes[idx]
            env = math.exp(-local_t * 15.0)
            val = 0.8 * math.sin(2.0 * math.pi * freq * local_t) + 0.2 * math.sin(4.0 * math.pi * freq * local_t)
            buf.append(int(32767.0 * 0.5 * val * env))
        return self._create_sound(buf)

    def _synth_lose_life(self) -> pygame.mixer.Sound:
        """Descending sad square/saw slide (380Hz -> 70Hz, 0.35s)."""
        duration = 0.35
        n_samples = int(self.SAMPLE_RATE * duration)
        buf = array.array('h')
        for i in range(n_samples):
            t = i / self.SAMPLE_RATE
            p = t / duration
            freq = 380.0 * (1.0 - p) + 70.0 * p
            env = (1.0 - p) ** 1.5
            val = 1.0 if math.sin(2.0 * math.pi * freq * t) > 0 else -1.0
            buf.append(int(32767.0 * 0.35 * val * env))
        return self._create_sound(buf)

    def _synth_stage_clear(self) -> pygame.mixer.Sound:
        """Triumphant cyberpunk arpeggio fanfare (0.45s)."""
        duration = 0.45
        n_samples = int(self.SAMPLE_RATE * duration)
        buf = array.array('h')
        chords = [440.0, 554.37, 659.25, 880.0, 1108.73]
        sub_dur = duration / len(chords)
        for i in range(n_samples):
            t = i / self.SAMPLE_RATE
            idx = min(len(chords) - 1, int(t / sub_dur))
            local_t = t - (idx * sub_dur)
            freq = chords[idx]
            env = math.exp(-local_t * 8.0)
            val = math.sin(2.0 * math.pi * freq * local_t)
            buf.append(int(32767.0 * 0.45 * val * env))
        return self._create_sound(buf)

    def _synth_game_over(self) -> pygame.mixer.Sound:
        """Gloomy retro 8-bit game over arpeggio (0.55s)."""
        duration = 0.55
        n_samples = int(self.SAMPLE_RATE * duration)
        buf = array.array('h')
        notes = [392.0, 369.99, 349.23, 311.13, 220.0]
        sub_dur = duration / len(notes)
        for i in range(n_samples):
            t = i / self.SAMPLE_RATE
            idx = min(len(notes) - 1, int(t / sub_dur))
            local_t = t - (idx * sub_dur)
            freq = notes[idx]
            env = (1.0 - (local_t / sub_dur)) * 0.8
            val = 1.0 if math.sin(2.0 * math.pi * freq * local_t) > 0 else -1.0
            buf.append(int(32767.0 * 0.3 * val * env))
        return self._create_sound(buf)

    def _synth_pierce_cut(self) -> pygame.mixer.Sound:
        """Laser plasma piercing slice (880Hz down-sweep with phase modulation, 0.08s)."""
        duration = 0.08
        n_samples = int(self.SAMPLE_RATE * duration)
        buf = array.array('h')
        for i in range(n_samples):
            t = i / self.SAMPLE_RATE
            freq = 900.0 - 450.0 * (t / duration)
            env = math.exp(-t * 25.0)
            val = math.sin(2.0 * math.pi * freq * t + math.sin(2.0 * math.pi * 120.0 * t))
            buf.append(int(32767.0 * 0.45 * val * env))
        return self._create_sound(buf)

    def _synth_bomb_blast(self) -> pygame.mixer.Sound:
        """Deep tactical explosion blast (0.35s)."""
        duration = 0.35
        n_samples = int(self.SAMPLE_RATE * duration)
        buf = array.array('h')
        for i in range(n_samples):
            t = i / self.SAMPLE_RATE
            p = t / duration
            freq = 180.0 * (1.0 - p) + 30.0 * p
            noise = (random.random() * 2.0 - 1.0) * 0.75 * (1.0 - p)
            wave = 0.6 * math.sin(2.0 * math.pi * freq * t) + noise
            env = math.exp(-t * 8.0)
            buf.append(int(32767.0 * 0.65 * wave * env))
        return self._create_sound(buf)

    def _synth_bottle_shatter(self) -> pygame.mixer.Sound:
        """Glass bottle shattering crash (0.2s)."""
        duration = 0.20
        n_samples = int(self.SAMPLE_RATE * duration)
        buf = array.array('h')
        for i in range(n_samples):
            t = i / self.SAMPLE_RATE
            env = math.exp(-t * 22.0)
            val = 0.5 * math.sin(2.0 * math.pi * 1800.0 * t) + (random.random() * 2.0 - 1.0) * 0.5
            buf.append(int(32767.0 * 0.5 * val * env))
        return self._create_sound(buf)

    def _synth_life_gain(self) -> pygame.mixer.Sound:
        """Cheerful 1-UP chime (0.3s)."""
        duration = 0.30
        n_samples = int(self.SAMPLE_RATE * duration)
        buf = array.array('h')
        notes = [330.0, 392.0, 659.25, 523.25, 587.33, 783.99]
        sub_dur = duration / len(notes)
        for i in range(n_samples):
            t = i / self.SAMPLE_RATE
            idx = min(len(notes) - 1, int(t / sub_dur))
            local_t = t - (idx * sub_dur)
            freq = notes[idx]
            env = math.exp(-local_t * 12.0)
            val = math.sin(2.0 * math.pi * freq * local_t)
            buf.append(int(32767.0 * 0.45 * val * env))
        return self._create_sound(buf)


# ==============================================================================
# 3. DATA PERSISTENCE (HIGH SCORE)
# ==============================================================================
class HighScoreManager:
    """Manages reading and writing high score data into highscore.json."""
    def __init__(self, filepath: str = HIGH_SCORE_FILE):
        self.filepath = filepath
        self.high_score = 0
        self.highest_level = 1
        self.load()

    def load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.high_score = int(data.get("high_score", 0))
                    self.highest_level = int(data.get("highest_level", 1))
            except Exception as err:
                print(f"[HighScore] Error loading high score: {err}. Starting fresh.")
                self.high_score = 0
                self.highest_level = 1
        else:
            self.save()

    def update(self, score: int, level: int) -> bool:
        """Returns True if a new high score was reached."""
        is_new_record = False
        if score > self.high_score:
            self.high_score = score
            is_new_record = True
        if level > self.highest_level:
            self.highest_level = level
        if is_new_record:
            self.save()
        return is_new_record

    def save(self):
        try:
            payload = {
                "high_score": self.high_score,
                "highest_level": self.highest_level,
                "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(payload, f, indent=2)
        except Exception as err:
            print(f"[HighScore] Failed to save high score: {err}")


# ==============================================================================
# 4. PARTICLE & FLOATING COMBAT TEXT SYSTEM
# ==============================================================================
class Particle:
    __slots__ = ('x', 'y', 'vx', 'vy', 'color', 'life', 'max_life', 'size')

    def __init__(self, x: float, y: float, vx: float, vy: float, color: tuple, life: float, size: float):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.color = color
        self.life = life
        self.max_life = life
        self.size = size

    def update(self, dt: float) -> bool:
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.life -= dt
        return self.life > 0.0

    def draw(self, surface: pygame.Surface):
        if self.life <= 0:
            return
        ratio = max(0.0, min(1.0, self.life / self.max_life))
        cur_size = max(1, int(self.size * ratio))
        # Fade color
        alpha_color = (
            int(self.color[0] * ratio),
            int(self.color[1] * ratio),
            int(self.color[2] * ratio)
        )
        pygame.draw.circle(surface, alpha_color, (int(self.x), int(self.y)), cur_size)


class FloatingText:
    __slots__ = ('text', 'x', 'y', 'vy', 'color', 'life', 'max_life', 'font')

    def __init__(self, text: str, x: float, y: float, color: tuple, font: pygame.font.Font, life: float = 0.8):
        self.text = text
        self.x = x
        self.y = y
        self.vy = -45.0
        self.color = color
        self.life = life
        self.max_life = life
        self.font = font

    def update(self, dt: float) -> bool:
        self.y += self.vy * dt
        self.life -= dt
        return self.life > 0.0

    def draw(self, surface: pygame.Surface):
        if self.life <= 0:
            return
        ratio = max(0.0, min(1.0, self.life / self.max_life))
        alpha = int(255 * ratio)
        txt_surf = self.font.render(self.text, True, self.color)
        txt_surf.set_alpha(alpha)
        rect = txt_surf.get_rect(center=(int(self.x), int(self.y)))
        surface.blit(txt_surf, rect)


class ParticleManager:
    """Manages particle bursts, spark effects, and floating score texts."""
    def __init__(self):
        self.particles = []
        self.floating_texts = []

    def spawn_brick_burst(self, cx: float, cy: float, color: tuple, count: int = 16):
        for _ in range(count):
            angle = random.uniform(0.0, 2.0 * math.pi)
            speed = random.uniform(50.0, 260.0)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed
            life = random.uniform(0.3, 0.65)
            size = random.uniform(2.5, 4.5)
            self.particles.append(Particle(cx, cy, vx, vy, color, life, size))

    def spawn_paddle_sparks(self, cx: float, cy: float, count: int = 8):
        for _ in range(count):
            angle = random.uniform(-math.pi * 0.85, -math.pi * 0.15)
            speed = random.uniform(80.0, 220.0)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed
            life = random.uniform(0.2, 0.4)
            size = random.uniform(2.0, 3.5)
            self.particles.append(Particle(cx, cy, vx, vy, COLOR_NEON_CYAN, life, size))

    def add_floating_text(self, text: str, x: float, y: float, color: tuple, font: pygame.font.Font):
        self.floating_texts.append(FloatingText(text, x, y, color, font))

    def update(self, dt: float):
        self.particles = [p for p in self.particles if p.update(dt)]
        self.floating_texts = [t for t in self.floating_texts if t.update(dt)]

    def draw(self, surface: pygame.Surface):
        for p in self.particles:
            p.draw(surface)
        for t in self.floating_texts:
            t.draw(surface)

# ==============================================================================
# 5. POWER-UP SYSTEM & HAZARDS
# ==============================================================================
class PowerUpType:
    MULTI_2         = "MULTI_2"
    GUN             = "GUN"
    FIRE_SHIELD     = "FIRE_SHIELD"
    MULTI_10        = "MULTI_10"
    MULTI_100       = "MULTI_100"
    PIERCING_BALL   = "PIERCING_BALL"
    EXTENDED_PADDLE = "EXTENDED_PADDLE"
    PADDLE_FULL     = "PADDLE_FULL"
    EXTRA_LIFE      = "EXTRA_LIFE"
    BOMB_3X3        = "BOMB_3X3"


class PowerUp:
    WIDTH = 46
    HEIGHT = 24

    def __init__(self, x: float, y: float, ptype: str):
        self.x = x
        self.y = y
        self.ptype = ptype
        self.vy = POWERUP_FALL_SPEED
        self.rect = pygame.Rect(int(x - self.WIDTH / 2), int(y - self.HEIGHT / 2), self.WIDTH, self.HEIGHT)
        self.alive = True
        self.pulse = 0.0

        if self.ptype == PowerUpType.MULTI_2:
            self.color = COLOR_NEON_GREEN
            self.label = "x2"
        elif self.ptype == PowerUpType.MULTI_10:
            self.color = COLOR_NEON_YELLOW
            self.label = "x10"
        elif self.ptype == PowerUpType.MULTI_100:
            self.color = (255, 215, 0)
            self.label = "x100"
        elif self.ptype == PowerUpType.PIERCING_BALL:
            self.color = COLOR_NEON_ORANGE
            self.label = "PIERCE"
        elif self.ptype == PowerUpType.PADDLE_FULL:
            self.color = COLOR_WHITE
            self.label = "GIGA"
        elif self.ptype == PowerUpType.EXTRA_LIFE:
            self.color = (255, 50, 140)
            self.label = "+LIFE"
        elif self.ptype == PowerUpType.BOMB_3X3:
            self.color = (255, 40, 40)
            self.label = "BOMB"
        elif self.ptype == PowerUpType.GUN:
            self.color = (255, 100, 50)
            self.label = "GUN"
        elif self.ptype == PowerUpType.FIRE_SHIELD:
            self.color = (0, 220, 255)
            self.label = "SHIELD"
        else:
            self.color = COLOR_NEON_CYAN
            self.label = "WIDE"

    def update(self, dt: float):
        self.y += self.vy * dt
        self.pulse += dt * 6.0
        self.rect.center = (int(self.x), int(self.y))
        if self.y - self.HEIGHT > SCREEN_HEIGHT:
            self.alive = False

    def draw(self, surface: pygame.Surface, font: pygame.font.Font):
        pulse_val = math.sin(self.pulse) * 2.0
        r = self.rect.inflate(int(pulse_val), int(pulse_val))

        # Capsule outer glow
        glow_rect = r.inflate(5, 5)
        pygame.draw.rect(surface, (self.color[0] // 3, self.color[1] // 3, self.color[2] // 3), glow_rect, border_radius=11)
        # Capsule body
        pygame.draw.rect(surface, COLOR_HUD_BG, r, border_radius=10)
        pygame.draw.rect(surface, self.color, r, width=2, border_radius=10)

        # Draw Large Prominent Icon / Label inside capsule
        cx, cy = r.center
        if self.ptype in (PowerUpType.MULTI_2, PowerUpType.MULTI_10, PowerUpType.MULTI_100):
            # Ball multipliers retain text label (x2, x10, x100)
            txt = font.render(self.label, True, self.color)
            t_rect = txt.get_rect(center=r.center)
            surface.blit(txt, t_rect)

        elif self.ptype == PowerUpType.EXTRA_LIFE:
            # Large Cyber Heart Icon
            hx, hy = cx, cy - 2
            pygame.draw.circle(surface, (255, 50, 140), (hx - 4, hy), 4)
            pygame.draw.circle(surface, (255, 50, 140), (hx + 4, hy), 4)
            pygame.draw.polygon(surface, (255, 50, 140), [(hx - 8, hy + 1), (hx + 8, hy + 1), (hx, hy + 9)])
            pygame.draw.circle(surface, COLOR_WHITE, (hx - 4, hy - 1), 1)

        elif self.ptype == PowerUpType.GUN:
            # Large Dual Laser Blaster Icon
            gx, gy = cx, cy
            # Left barrel & glowing tip
            pygame.draw.rect(surface, (255, 100, 50), (gx - 8, gy - 7, 4, 14), border_radius=1)
            pygame.draw.circle(surface, COLOR_WHITE, (gx - 6, gy - 7), 2)
            # Right barrel & glowing tip
            pygame.draw.rect(surface, (255, 100, 50), (gx + 4, gy - 7, 4, 14), border_radius=1)
            pygame.draw.circle(surface, COLOR_WHITE, (gx + 6, gy - 7), 2)
            # Cross connector
            pygame.draw.rect(surface, (255, 170, 80), (gx - 6, gy + 2, 12, 4), border_radius=1)

        elif self.ptype == PowerUpType.FIRE_SHIELD:
            # Large Energy Armor Shield Icon
            sx, sy = cx, cy
            shield_pts = [
                (sx, sy - 9), (sx + 8, sy - 6), (sx + 7, sy + 3),
                (sx, sy + 9), (sx - 7, sy + 3), (sx - 8, sy - 6)
            ]
            pygame.draw.polygon(surface, (0, 220, 255), shield_pts)
            pygame.draw.polygon(surface, COLOR_WHITE, shield_pts, width=1)
            pygame.draw.circle(surface, COLOR_WHITE, (sx, sy), 2)

        elif self.ptype == PowerUpType.PIERCING_BALL:
            # Large Piercing Spearhead / Drill Icon
            px, py = cx, cy
            pygame.draw.polygon(surface, (255, 140, 0), [
                (px, py - 9), (px + 8, py), (px + 3, py),
                (px + 3, py + 8), (px - 3, py + 8), (px - 3, py),
                (px - 8, py)
            ])
            pygame.draw.polygon(surface, COLOR_WHITE, [
                (px, py - 6), (px + 4, py - 1), (px - 4, py - 1)
            ])

        elif self.ptype == PowerUpType.EXTENDED_PADDLE:
            # Large Horizontal Expand Arrows Icon
            ex, ey = cx, cy
            # Left arrow
            pygame.draw.polygon(surface, COLOR_NEON_CYAN, [
                (ex - 12, ey), (ex - 6, ey - 5), (ex - 6, ey + 5)
            ])
            # Center paddle bar
            pygame.draw.rect(surface, COLOR_WHITE, (ex - 5, ey - 3, 10, 6), border_radius=2)
            # Right arrow
            pygame.draw.polygon(surface, COLOR_NEON_CYAN, [
                (ex + 12, ey), (ex + 6, ey - 5), (ex + 6, ey + 5)
            ])

        elif self.ptype == PowerUpType.PADDLE_FULL:
            # Large Giga Full-Screen Boundary Bracket Icon
            gx, gy = cx, cy
            # Boundary posts
            pygame.draw.line(surface, COLOR_WHITE, (gx - 13, gy - 7), (gx - 13, gy + 7), 2)
            pygame.draw.line(surface, COLOR_WHITE, (gx + 13, gy - 7), (gx + 13, gy + 7), 2)
            # Expand arrows & core bar
            pygame.draw.polygon(surface, COLOR_NEON_CYAN, [
                (gx - 11, gy), (gx - 6, gy - 4), (gx - 6, gy + 4)
            ])
            pygame.draw.rect(surface, COLOR_WHITE, (gx - 4, gy - 2, 8, 4), border_radius=1)
            pygame.draw.polygon(surface, COLOR_NEON_CYAN, [
                (gx + 11, gy), (gx + 6, gy - 4), (gx + 6, gy + 4)
            ])

        elif self.ptype == PowerUpType.BOMB_3X3:
            # Large Tactical Bomb with Fuse Icon
            bx, by = cx, cy
            # Round bomb body & highlight
            pygame.draw.circle(surface, (255, 40, 40), (bx - 1, by + 2), 7)
            pygame.draw.circle(surface, (255, 130, 130), (bx - 3, by), 2)
            # Collar & fuse
            pygame.draw.rect(surface, (180, 180, 180), (bx - 3, by - 6, 4, 3))
            pygame.draw.line(surface, (255, 230, 0), (bx - 1, by - 6), (bx + 4, by - 9), 2)
            # Sparking ember
            pygame.draw.circle(surface, COLOR_WHITE, (bx + 4, by - 9), 2)

        else:
            txt = font.render(self.label, True, self.color)
            t_rect = txt.get_rect(center=r.center)
            surface.blit(txt, t_rect)


class HazardBottle:
    """Lethal falling hazard bottle in levels 19 & 20."""
    RADIUS = 7.0

    def __init__(self, x: float, y: float):
        self.x = float(x)
        self.y = float(y)
        self.vy = 130.0  # px/sec
        self.alive = True
        self.pulse = 0.0

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x - self.RADIUS), int(self.y - self.RADIUS), int(self.RADIUS * 2), int(self.RADIUS * 2))

    def update(self, dt: float) -> bool:
        self.y += self.vy * dt
        self.pulse += dt * 8.0
        if self.y - self.RADIUS > SCREEN_HEIGHT:
            self.alive = False
            return False  # Reached floor!
        return True

    def draw(self, surface: pygame.Surface, font: pygame.font.Font):
        pulse_r = self.RADIUS + 2.0 + math.sin(self.pulse) * 1.5
        pos = (int(self.x), int(self.y))
        pygame.draw.circle(surface, (255, 20, 60), pos, int(pulse_r) + 2)
        pygame.draw.circle(surface, (180, 0, 220), pos, int(pulse_r))
        pygame.draw.circle(surface, COLOR_WHITE, pos, int(self.RADIUS * 0.5))
        # Biohazard/Hazard cross line
        pygame.draw.line(surface, COLOR_BLACK, (pos[0] - 3, pos[1] - 3), (pos[0] + 3, pos[1] + 3), 2)
        pygame.draw.line(surface, COLOR_BLACK, (pos[0] - 3, pos[1] + 3), (pos[0] + 3, pos[1] - 3), 2)


# ==============================================================================
# 6. BRICK HIERARCHY (STANDARD, REINFORCED, MOVING, UNBREAKABLE, REGENERATING)
# ==============================================================================

class Bullet:
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
        self.vy = -600.0
        self.alive = True
        self.rect = pygame.Rect(int(x) - 2, int(y) - 6, 4, 12)

    def update(self, dt: float):
        self.y += self.vy * dt
        self.rect.y = int(self.y)
        if self.y < 0:
            self.alive = False

    def draw(self, surface: pygame.Surface):
        if self.alive:
            pygame.draw.rect(surface, (255, 100, 50), self.rect, border_radius=2)
            pygame.draw.rect(surface, (255, 255, 255), self.rect.inflate(-2, -2), border_radius=1)

class BrickType:
    STANDARD        = "STANDARD"
    REINFORCED      = "REINFORCED"
    MOVING          = "MOVING"
    UNBREAKABLE     = "UNBREAKABLE"
    REGENERATING    = "REGENERATING"
    SCENERY_BARRIER = "SCENERY_BARRIER"


class Brick:
    def __init__(self, x: float, y: float, width: float, height: float, btype: str, max_hp: int = 1,
                 color: tuple = COLOR_NEON_CYAN, move_speed: float = 0.0, move_min_x: float = 0, move_max_x: float = 800):
        self.x = float(x)
        self.y = float(y)
        self.width = float(width)
        self.height = float(height)
        self.btype = btype
        self.max_hp = max_hp
        self.hp = max_hp
        self.base_color = color
        self.rect = pygame.Rect(int(self.x), int(self.y), int(self.width), int(self.height))

        # Moving Brick Attributes
        self.move_speed = move_speed
        self.move_min_x = move_min_x
        self.move_max_x = move_max_x

        # Regenerating Brick Attributes
        self.time_since_hit = 0.0
        self.regen_flash_timer = 0.0

        # Rainbow Regenerator status (Level 20)
        self.is_rainbow = False

        # Animation sheen
        self.flash_timer = 0.0

    @property
    def is_unbreakable(self) -> bool:
        return self.btype in (BrickType.UNBREAKABLE, BrickType.SCENERY_BARRIER)

    @property
    def is_scenery(self) -> bool:
        return self.btype == BrickType.SCENERY_BARRIER

    @property
    def is_alive(self) -> bool:
        return self.is_unbreakable or self.hp > 0

    def hit(self, damage: int = 1) -> bool:
        """Damages the brick. Returns True if destroyed."""
        if self.is_unbreakable:
            self.flash_timer = 0.1
            return False

        self.hp -= damage
        self.flash_timer = 0.12
        self.time_since_hit = 0.0

        if self.hp <= 0:
            self.hp = 0
            return True
        return False

    def update(self, dt: float):
        if self.flash_timer > 0.0:
            self.flash_timer = max(0.0, self.flash_timer - dt)

        # Handle Moving Bricks (Horizontal oscillation)
        if self.btype == BrickType.MOVING and self.move_speed != 0.0:
            self.x += self.move_speed * dt
            if self.x <= self.move_min_x:
                self.x = self.move_min_x
                self.move_speed = abs(self.move_speed)
            elif self.x + self.width >= self.move_max_x:
                self.x = self.move_max_x - self.width
                self.move_speed = -abs(self.move_speed)
            self.rect.x = int(self.x)

        # Handle Regenerating Bricks
        if self.btype == BrickType.REGENERATING and self.hp > 0 and self.hp < self.max_hp:
            self.time_since_hit += dt
            if self.time_since_hit >= REGEN_COOLDOWN:
                self.hp = min(self.max_hp, self.hp + 1)
                self.time_since_hit = 0.0
                self.regen_flash_timer = 0.35

        if self.regen_flash_timer > 0.0:
            self.regen_flash_timer = max(0.0, self.regen_flash_timer - dt)

    def draw(self, surface: pygame.Surface):
        if not self.is_alive:
            return

        # Special rendering for permanent industrial scenery barrier (unmistakable from destructible bricks)
        if self.btype == BrickType.SCENERY_BARRIER:
            bg_rect = self.rect
            # 1. Dark structural carbon-steel base
            pygame.draw.rect(surface, (18, 22, 32), bg_rect, border_radius=2)

            # 2. Diagonal industrial hazard caution stripes (/// /// ///)
            stripe_clip = surface.get_clip()
            surface.set_clip(bg_rect)
            stripe_color = (255, 195, 20) if self.flash_timer <= 0 else COLOR_WHITE
            for sx in range(bg_rect.left - bg_rect.height, bg_rect.right + bg_rect.height, 10):
                p1 = (sx, bg_rect.bottom)
                p2 = (sx + bg_rect.height, bg_rect.top)
                pygame.draw.line(surface, stripe_color, p1, p2, 4)
            surface.set_clip(stripe_clip)

            # 3. Outer titanium metal frame
            frame_color = (135, 150, 175) if self.flash_timer <= 0 else COLOR_WHITE
            pygame.draw.rect(surface, frame_color, bg_rect, width=1, border_radius=2)

            # 4. Heavy metallic end brackets with mounting bolts/rivets
            bracket_w = 6
            l_bracket = pygame.Rect(bg_rect.left, bg_rect.top, bracket_w, bg_rect.height)
            r_bracket = pygame.Rect(bg_rect.right - bracket_w, bg_rect.top, bracket_w, bg_rect.height)
            pygame.draw.rect(surface, (45, 52, 68), l_bracket)
            pygame.draw.rect(surface, frame_color, l_bracket, width=1)
            pygame.draw.rect(surface, (45, 52, 68), r_bracket)
            pygame.draw.rect(surface, frame_color, r_bracket, width=1)

            # Cyan mounting bolts/rivets
            pygame.draw.circle(surface, COLOR_NEON_CYAN, (bg_rect.left + 3, bg_rect.centery), 2)
            pygame.draw.circle(surface, COLOR_NEON_CYAN, (bg_rect.right - 4, bg_rect.centery), 2)

            # 5. Top and bottom cyber rail guides
            pygame.draw.line(surface, (170, 190, 220), (bg_rect.left, bg_rect.top), (bg_rect.right, bg_rect.top), 1)
            pygame.draw.line(surface, (85, 100, 125), (bg_rect.left, bg_rect.bottom - 1), (bg_rect.right, bg_rect.bottom - 1), 1)
            return

        # Determine draw color based on brick type and HP
        if getattr(self, 'is_rainbow', False):
            t = time.time() * 8.0
            r = int((math.sin(t) + 1.0) * 127.5)
            g = int((math.sin(t + 2.094) + 1.0) * 127.5)
            b = int((math.sin(t + 4.188) + 1.0) * 127.5)
            color = (r, g, b)
            border_color = COLOR_WHITE
        elif self.is_unbreakable:
            color = COLOR_IRON_BASE
            border_color = COLOR_IRON_BORDER
        elif self.btype == BrickType.REGENERATING:
            # Pulsing emerald
            color = COLOR_REGEN_BASE
            border_color = COLOR_REGEN_GLOW
            if self.regen_flash_timer > 0.0:
                color = COLOR_WHITE
        elif self.btype == BrickType.REINFORCED:
            # Dynamic color gradient by remaining HP
            if self.hp >= 3:
                color = COLOR_NEON_PURPLE
                border_color = COLOR_NEON_CYAN
            elif self.hp == 2:
                color = COLOR_NEON_YELLOW
                border_color = COLOR_NEON_ORANGE
            else:
                color = COLOR_NEON_MAGENTA
                border_color = COLOR_WHITE
        else:
            color = self.base_color
            border_color = COLOR_WHITE

        # Flash on hit
        if self.flash_timer > 0.0:
            color = COLOR_WHITE
            border_color = COLOR_NEON_CYAN

        # Background body
        pygame.draw.rect(surface, color, self.rect, border_radius=4)

        if getattr(self, 'max_hp', 1) > 1 and self.hp < getattr(self, 'max_hp', 1):
            # High-contrast dual-stroke shattered neon cracks
            crack_dark = (15, 18, 28)
            crack_light = (240, 245, 255)
            import random as crack_rnd
            old_state = crack_rnd.getstate()
            crack_rnd.seed(int(self.x * 101 + self.y * 37))
            damage_count = self.max_hp - self.hp
            for d in range(damage_count):
                sx = self.rect.left + (d + 1) * (self.rect.width / (damage_count + 1))
                pts = [(sx, self.rect.top)]
                curr_x, curr_y = sx, float(self.rect.top)
                while curr_y < self.rect.bottom:
                    curr_y += crack_rnd.uniform(3.5, 6.5)
                    curr_x += crack_rnd.uniform(-6.0, 6.0)
                    curr_x = max(float(self.rect.left + 2), min(float(self.rect.right - 2), curr_x))
                    pts.append((curr_x, min(float(self.rect.bottom), curr_y)))
                if len(pts) >= 2:
                    pygame.draw.lines(surface, crack_dark, False, pts, 3)
                    pygame.draw.lines(surface, crack_light, False, pts, 1)
            crack_rnd.setstate(old_state)
        # Inner specular highlight / cyber trim
        inner_top = pygame.Rect(self.rect.x + 2, self.rect.y + 2, self.rect.width - 4, 3)
        highlight = (
            min(255, color[0] + 70),
            min(255, color[1] + 70),
            min(255, color[2] + 70)
        )
        pygame.draw.rect(surface, highlight, inner_top, border_radius=2)

        # Border
        pygame.draw.rect(surface, border_color, self.rect, width=1, border_radius=4)

        # Iron decorative circuit cross
        if self.is_unbreakable:
            cx, cy = self.rect.centerx, self.rect.centery
            pygame.draw.line(surface, COLOR_IRON_GLOW, (self.rect.left + 5, cy), (self.rect.right - 5, cy), 1)
            pygame.draw.line(surface, COLOR_IRON_GLOW, (cx, self.rect.top + 3), (cx, self.rect.bottom - 3), 1)


# ==============================================================================
# 7. PADDLE (VARIABLE WIDTH, MOUSE & KEYBOARD DUAL CONTROL, EXTENSION GAUGE)
# ==============================================================================
class Paddle:
    HEIGHT = 16
    Y_POS = 550

    def __init__(self):
        self.base_width = BASE_PADDLE_WIDTH
        self.width = self.base_width
        self.x = (SCREEN_WIDTH - self.width) / 2.0
        self.y = float(self.Y_POS)
        self.rect = pygame.Rect(int(self.x), int(self.y), int(self.width), self.HEIGHT)
        self.extended_timer = 0.0
        self.is_extended = False
        self.is_giga = False
        self.gun_timer = 0.0
        self.gun_ammo = 0
        self.fire_shield_timer = 0.0
        self.swing_timer = 0.0
        self.swing_duration = 0.25
        self.swing_dir = 0

    def reset_for_level(self, level: int):
        """Calculates level-based paddle width scaling (-1.5% each level)."""
        scale = (1.0 - PADDLE_DECAY_RATE) ** (level - 1)
        self.base_width = max(55.0, BASE_PADDLE_WIDTH * scale)
        self.extended_timer = 0.0
        self.is_extended = False
        self.is_giga = False
        self.gun_timer = 0.0
        self.gun_ammo = 0
        self.fire_shield_timer = 0.0
        self.swing_timer = 0.0
        self.swing_duration = 0.25
        self.swing_dir = 0
        self._recompute_width()
        self.x = (SCREEN_WIDTH - self.width) / 2.0
        self.rect = pygame.Rect(int(self.x), int(self.y), int(self.width), self.HEIGHT)

    def apply_powerup_extended(self):
        self.extended_timer = EXTENDED_PADDLE_DUR
        self.is_extended = True
        self.is_giga = False
        self.gun_timer = 0.0
        self.gun_ammo = 0
        self.fire_shield_timer = 0.0
        self.swing_timer = 0.0
        self.swing_duration = 0.25
        self.swing_dir = 0
        self._recompute_width()

    def apply_powerup_giga(self):
        self.extended_timer = EXTENDED_PADDLE_DUR
        self.is_extended = True
        self.is_giga = True
        self._recompute_width()

    def _recompute_width(self):
        old_center = self.x + self.width / 2.0
        if self.extended_timer > 0.0:
            if getattr(self, 'is_giga', False):
                self.width = float(SCREEN_WIDTH)
                self.x = 0.0
                self.is_extended = True
            else:
                self.width = round(self.base_width * 1.4)
                self.is_extended = True
                self.x = old_center - self.width / 2.0
        else:
            self.width = round(self.base_width)
            self.is_extended = False
            self.is_giga = False
            self.x = old_center - self.width / 2.0
        self.x = max(0.0, min(SCREEN_WIDTH - self.width, self.x))
        self.rect.width = int(self.width)
        self.rect.x = int(self.x)

    def update(self, dt: float, keys, mouse_dx: int, mouse_x: int, mouse_moved: bool, mouse_pressed: bool = False, can_follow_mouse: bool = True):
        # Update powerup & swing timers
        if getattr(self, 'gun_timer', 0.0) > 0.0:
            self.gun_timer = max(0.0, self.gun_timer - dt)
            if self.gun_timer <= 0.0:
                self.gun_ammo = 0
        if getattr(self, 'fire_shield_timer', 0.0) > 0.0:
            self.fire_shield_timer = max(0.0, self.fire_shield_timer - dt)
        if getattr(self, 'swing_timer', 0.0) > 0.0:
            self.swing_timer = max(0.0, self.swing_timer - dt)
            if self.swing_timer <= 0.0:
                self.swing_dir = 0

        if self.extended_timer > 0.0:
            self.extended_timer = max(0.0, self.extended_timer - dt)
            if self.extended_timer <= 0.0:
                self._recompute_width()

        # Keyboard movement takes priority if active, else mouse/touch follower
        kb_dx = 0.0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            kb_dx -= PADDLE_SPEED_KEYS * dt
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            kb_dx += PADDLE_SPEED_KEYS * dt

        if kb_dx != 0.0:
            self.x += kb_dx
        elif can_follow_mouse and (mouse_moved or mouse_pressed):
            self.x = mouse_x - (self.width / 2.0)

        # Clamping
        self.x = max(0.0, min(SCREEN_WIDTH - self.width, self.x))
        self.rect.x = int(self.x)
        self.rect.width = int(self.width)

    def draw(self, surface: pygame.Surface):
        # 1. Outer Glow Color Determination
        if getattr(self, 'is_giga', False):
            glow_color = COLOR_WHITE
        elif self.is_extended:
            glow_color = COLOR_NEON_YELLOW
        elif getattr(self, 'gun_timer', 0.0) > 0.0 and getattr(self, 'gun_ammo', 0) > 0:
            glow_color = (255, 100, 50)
        elif getattr(self, 'fire_shield_timer', 0.0) > 0.0:
            glow_color = (0, 230, 255)
        elif getattr(self, 'swing_timer', 0.0) > 0.0:
            glow_color = COLOR_NEON_YELLOW
        else:
            glow_color = COLOR_NEON_CYAN

        # 2. Dynamic Tilt Calculation during Swing
        # Left click (swing_dir == -1): left side lifts UP
        # Right click (swing_dir == 1): right side lifts UP
        dy_l = 0.0
        dy_r = 0.0
        if getattr(self, 'swing_timer', 0.0) > 0.0 and getattr(self, 'swing_duration', 0.25) > 0:
            prog = math.sin(math.pi * (1.0 - self.swing_timer / self.swing_duration))
            tilt_h = 14.0 * prog
            if self.swing_dir == -1:
                dy_l = -tilt_h
                dy_r = tilt_h * 0.4
            elif self.swing_dir == 1:
                dy_l = tilt_h * 0.4
                dy_r = -tilt_h

        # Polygon coordinates
        p_tl = (self.x, self.y + dy_l)
        p_tr = (self.x + self.width, self.y + dy_r)
        p_br = (self.x + self.width, self.y + self.HEIGHT + dy_r)
        p_bl = (self.x, self.y + self.HEIGHT + dy_l)
        pts = [p_tl, p_tr, p_br, p_bl]

        # 3. Reinforced Armor Energy Shell (Pulsing Electric Cyan/Blue Aura)
        if getattr(self, 'fire_shield_timer', 0.0) > 0.0:
            pulse = (math.sin(time.time() * 14.0) + 1.0) / 2.0  # Fast electric flicker
            exp = 4.0 + 3.0 * pulse  # 4px to 7px expansion
            
            # Outer electric cyan barrier polygon
            b_tl = (p_tl[0] - exp, p_tl[1] - exp)
            b_tr = (p_tr[0] + exp, p_tr[1] - exp)
            b_br = (p_br[0] + exp, p_br[1] + exp)
            b_bl = (p_bl[0] - exp, p_bl[1] + exp)
            barrier_pts = [b_tl, b_tr, b_br, b_bl]
            
            # Semi-transparent electric blue aura fill
            aura_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            pygame.draw.polygon(aura_surf, (0, 180, 255, int(60 + 70 * pulse)), barrier_pts)
            pygame.draw.polygon(aura_surf, (160, 245, 255, int(160 + 95 * pulse)), barrier_pts, width=2)
            surface.blit(aura_surf, (0, 0))
            
            # Reinforced top armor energy plate
            plate_y_l = p_tl[1] - 3
            plate_y_r = p_tr[1] - 3
            pygame.draw.line(surface, (0, 255, 240), (p_tl[0] - 2, plate_y_l), (p_tr[0] + 2, plate_y_r), 3)
            pygame.draw.line(surface, COLOR_WHITE, (p_tl[0] + 4, plate_y_l), (p_tr[0] - 4, plate_y_r), 1)
            
            # Reinforced corner bolts/nodes
            pygame.draw.circle(surface, (0, 255, 255), (int(p_tl[0] - 2), int(plate_y_l)), 3)
            pygame.draw.circle(surface, (0, 255, 255), (int(p_tr[0] + 2), int(plate_y_r)), 3)
            pygame.draw.circle(surface, COLOR_WHITE, (int(p_tl[0] - 2), int(plate_y_l)), 1)
            pygame.draw.circle(surface, COLOR_WHITE, (int(p_tr[0] + 2), int(plate_y_r)), 1)

        # 4. Draw paddle body with tilt
        glow_col = (glow_color[0] // 4, glow_color[1] // 4, glow_color[2] // 4)
        pygame.draw.polygon(surface, glow_col, pts)
        pygame.draw.polygon(surface, COLOR_HUD_BG, pts)

        # Core energy bar
        c_tl = (self.x + 4, self.y + dy_l + 4)
        c_tr = (self.x + self.width - 4, self.y + dy_r + 4)
        c_br = (self.x + self.width - 4, self.y + self.HEIGHT + dy_r - 4)
        c_bl = (self.x + 4, self.y + self.HEIGHT + dy_l - 4)
        pygame.draw.polygon(surface, glow_color, [c_tl, c_tr, c_br, c_bl])
        pygame.draw.polygon(surface, COLOR_WHITE, pts, width=1)

        # Highlight swinging blade edge
        if getattr(self, 'swing_timer', 0.0) > 0.0:
            if self.swing_dir == -1:
                # Left tip swing streak
                pygame.draw.line(surface, COLOR_NEON_YELLOW, p_bl, p_tl, 3)
                pygame.draw.line(surface, COLOR_WHITE, p_tl, (self.x + self.width * 0.5, self.y + dy_l * 0.5 + dy_r * 0.5), 3)
            elif self.swing_dir == 1:
                # Right tip swing streak
                pygame.draw.line(surface, COLOR_NEON_YELLOW, p_br, p_tr, 3)
                pygame.draw.line(surface, COLOR_WHITE, (self.x + self.width * 0.5, self.y + dy_l * 0.5 + dy_r * 0.5), p_tr, 3)

        # Side neon caps
        pygame.draw.circle(surface, COLOR_NEON_MAGENTA, (int(self.x + 2), int(self.y + dy_l + self.HEIGHT / 2)), 3)
        pygame.draw.circle(surface, COLOR_NEON_MAGENTA, (int(self.x + self.width - 2), int(self.y + dy_r + self.HEIGHT / 2)), 3)

        # 4. Mounted Laser Blaster Cannons (if Gun Power-Up is active)
        if getattr(self, 'gun_timer', 0.0) > 0.0 and getattr(self, 'gun_ammo', 0) > 0:
            c_left_x = self.x + 8
            c_right_x = self.x + self.width - 8
            pygame.draw.rect(surface, (255, 100, 50), (int(c_left_x - 3), int(self.y - 7), 6, 9), border_radius=2)
            pygame.draw.rect(surface, (255, 100, 50), (int(c_right_x - 3), int(self.y - 7), 6, 9), border_radius=2)
            pygame.draw.circle(surface, COLOR_NEON_YELLOW, (int(c_left_x), int(self.y - 7)), 3)
            pygame.draw.circle(surface, COLOR_NEON_YELLOW, (int(c_right_x), int(self.y - 7)), 3)
            # Ammo pip indicators
            for a in range(self.gun_ammo):
                pip_x = self.x + self.width / 2.0 + (a - (self.gun_ammo - 1) / 2.0) * 12
                pygame.draw.circle(surface, (255, 80, 40), (int(pip_x), int(self.y - 12)), 4)
                pygame.draw.circle(surface, COLOR_NEON_YELLOW, (int(pip_x), int(self.y - 12)), 2)

# ==============================================================================
# 8. BALL (ANTI-TUNNELING SUBSTEP PHYSICS, PIERCING LOGIC, NEON TRAILS)
# ==============================================================================
class Ball:
    RADIUS = 6.5

    def __init__(self, x: float, y: float, vx: float, vy: float, base_speed: float):
        self.x = float(x)
        self.y = float(y)
        self.vx = float(vx)
        self.vy = float(vy)
        self.base_speed = float(base_speed)
        self.target_speed = float(base_speed)
        self.pierce_count = 0  # Piercing power-up charges (up to 2)
        self.alive = True
        self.attached = False  # Attached to paddle before launch
        self.is_smashed = False

        # Trail effect
        self.trail = deque(maxlen=8)

        # Normalize velocity to target speed
        self._normalize_speed()

    def _normalize_speed(self):
        curr = math.hypot(self.vx, self.vy)
        if curr > 0.001:
            self.vx = (self.vx / curr) * self.target_speed
            self.vy = (self.vy / curr) * self.target_speed
        else:
            self.vx = 0.0
            self.vy = -self.target_speed

    def grant_pierce(self):
        self.pierce_count = 2

    def update_attached(self, paddle: Paddle):
        self.x = paddle.x + paddle.width / 2.0
        self.y = paddle.y - self.RADIUS - 1
        self.trail.clear()

    def launch(self, speed: float):
        self.base_speed = float(speed)
        self.target_speed = float(speed)
        self.is_smashed = False
        self.attached = False
        angle = random.uniform(-math.pi * 0.35, -math.pi * 0.15)
        if random.random() < 0.5:
            angle = -math.pi - angle
        self.vx = math.cos(angle) * self.target_speed
        self.vy = math.sin(angle) * self.target_speed

    def update_physics(self, dt: float, paddle: Paddle, bricks: list, audio: ProceduralAudio,
                       particles: ParticleManager, powerups: list, score_ref: list) -> bool:
        """
        Anti-Tunneling Continuous Physics Step:
        Divides frame delta into substeps to prevent tunneling at high velocity.
        Separates X and Y collision checking for exact reflection normals.
        """
        if self.attached or not self.alive:
            return False

        # Store trail position
        self.trail.append((self.x, self.y, self.pierce_count > 0))

        # Calculate substeps & frame displacement
        # target_speed is in pixels per frame at 60 FPS
        time_factor = dt * 60.0  # normalize frame delta for lag compensation
        frame_dist = self.target_speed * time_factor
        substeps = max(1, math.ceil(frame_dist / 4.0))

        for _ in range(substeps):
            if not self.alive:
                break
            step_x = (self.vx / substeps) * time_factor
            step_y = (self.vy / substeps) * time_factor

            # -----------------
            # 1. MOVE X
            # -----------------
            self.x += step_x

            # Wall Collisions (Left & Right)
            if self.x - self.RADIUS <= 0:
                self.x = self.RADIUS
                self.vx = abs(self.vx)
                audio.play('hit_paddle')
                if getattr(self, 'is_smashed', False):
                    self.is_smashed = False
                    self.target_speed = self.base_speed
                    self._normalize_speed()
            elif self.x + self.RADIUS >= SCREEN_WIDTH:
                self.x = SCREEN_WIDTH - self.RADIUS
                self.vx = -abs(self.vx)
                audio.play('hit_paddle')
                if getattr(self, 'is_smashed', False):
                    self.is_smashed = False
                    self.target_speed = self.base_speed
                    self._normalize_speed()

            # Brick Collisions on X Axis
            ball_rect = pygame.Rect(
                int(self.x - self.RADIUS), int(self.y - self.RADIUS),
                int(self.RADIUS * 2), int(self.RADIUS * 2)
            )
            for brick in bricks:
                if brick.is_alive and ball_rect.colliderect(brick.rect):
                    self._handle_brick_collision(brick, 'X', audio, particles, powerups, score_ref)
                    if self.pierce_count == 0 or brick.is_unbreakable:
                        break  # Stop resolving X further this sub-step if reflected

            # -----------------
            # 2. MOVE Y
            # -----------------
            self.y += step_y

            # Wall Collision (Top)
            if self.y - self.RADIUS <= HUD_HEIGHT:
                self.y = HUD_HEIGHT + self.RADIUS
                self.vy = abs(self.vy)
                audio.play('hit_paddle')
                if getattr(self, 'is_smashed', False):
                    self.is_smashed = False
                    self.target_speed = self.base_speed
                    self._normalize_speed()

            # Bottom Out of Bounds (Loss of Ball)
            if self.y - self.RADIUS > SCREEN_HEIGHT:
                self.alive = False
                return False

            # Paddle Collision
            ball_rect = pygame.Rect(
                int(self.x - self.RADIUS), int(self.y - self.RADIUS),
                int(self.RADIUS * 2), int(self.RADIUS * 2)
            )
            is_hit = False
            if self.vy > 0:
                if ball_rect.colliderect(paddle.rect):
                    is_hit = True
                elif getattr(paddle, 'swing_timer', 0.0) > 0.0:
                    tilt_rect = paddle.rect.inflate(10, 20)
                    if ball_rect.colliderect(tilt_hit_rect if 'tilt_hit_rect' in locals() else tilt_rect):
                        is_hit = True

            if is_hit:
                # Ensure ball was above paddle
                if self.y <= paddle.y + paddle.HEIGHT / 2 + 10:
                    self.y = paddle.y - self.RADIUS - 1
                    # Dynamic reflection angle based on hit location
                    rel_offset = (self.x - (paddle.x + paddle.width / 2.0)) / (paddle.width / 2.0)
                    rel_offset = max(-0.85, min(0.85, rel_offset))

                    max_angle = math.radians(62.0)
                    bounce_angle = rel_offset * max_angle

                    if getattr(paddle, 'swing_timer', 0.0) > 0.0:
                        # Directional Batting:
                        # Left Click (swing_dir == -1): Left side tilts up, GUARANTEED bounce to the RIGHT (> 0)
                        # Right Click (swing_dir == 1): Right side tilts up, GUARANTEED bounce to the LEFT (< 0)
                        if paddle.swing_dir == -1:
                            deg = 46.0 - rel_offset * 14.0
                            deg = min(66.0, max(28.0, deg))
                            bounce_angle = math.radians(deg)
                            txt_label = "RIGHT SMASH! >>"
                        else:
                            deg = 46.0 + rel_offset * 14.0
                            deg = min(66.0, max(28.0, deg))
                            bounce_angle = -math.radians(deg)
                            txt_label = "<< LEFT SMASH!"

                        self.target_speed = self.base_speed * 1.35
                        self.is_smashed = True
                        particles.add_floating_text(txt_label, self.x, self.y - 15, COLOR_NEON_YELLOW, pygame.font.Font(None, 24))
                        particles.spawn_paddle_sparks(self.x, self.y, count=16)
                    else:
                        self.target_speed = self.base_speed
                        self.is_smashed = False
                        particles.spawn_paddle_sparks(self.x, self.y, count=9)

                    self.vx = self.target_speed * math.sin(bounce_angle)
                    self.vy = -abs(self.target_speed * math.cos(bounce_angle))

                    min_vy = self.target_speed * 0.35
                    if abs(self.vy) < min_vy:
                        self.vy = -min_vy
                        self._normalize_speed()

                    audio.play('hit_paddle')

            # Brick Collisions on Y Axis
            ball_rect = pygame.Rect(
                int(self.x - self.RADIUS), int(self.y - self.RADIUS),
                int(self.RADIUS * 2), int(self.RADIUS * 2)
            )
            for brick in bricks:
                if brick.is_alive and ball_rect.colliderect(brick.rect):
                    self._handle_brick_collision(brick, 'Y', audio, particles, powerups, score_ref)
                    if self.pierce_count == 0 or brick.is_unbreakable:
                        break

        return True

    def _handle_brick_collision(self, brick: Brick, axis: str, audio: ProceduralAudio,
                                particles: ParticleManager, powerups: list, score_ref: list):
        if getattr(self, 'is_smashed', False):
            self.is_smashed = False
            self.target_speed = self.base_speed
            self._normalize_speed()
        # Unbreakable Iron Blocks & Scenery Barriers always deflect and cannot be pierced
        if brick.is_unbreakable:
            audio.play('hit_iron')
            burst_color = (255, 195, 20) if getattr(brick, 'is_scenery', False) else COLOR_IRON_BORDER
            particles.spawn_brick_burst(self.x, self.y, burst_color, count=7)
            if axis == 'X':
                if self.vx > 0:
                    self.x = brick.rect.left - self.RADIUS
                    self.vx = -abs(self.vx)
                else:
                    self.x = brick.rect.right + self.RADIUS
                    self.vx = abs(self.vx)
            else:
                if self.vy > 0:
                    self.y = brick.rect.top - self.RADIUS
                    self.vy = -abs(self.vy)
                else:
                    self.y = brick.rect.bottom + self.RADIUS
                    self.vy = abs(self.vy)
            return

        # Destructible Brick Hit
        if self.pierce_count > 0:
            # Piercing Ball mechanic: cuts through up to 2 bricks without reflecting!
            self.pierce_count -= 1
            audio.play('laser_pierce')
            particles.spawn_brick_burst(brick.rect.centerx, brick.rect.centery, COLOR_NEON_ORANGE, count=14)
            destroyed = brick.hit(damage=1)
        else:
            # Standard bounce collision
            if axis == 'X':
                if self.vx > 0:
                    self.x = brick.rect.left - self.RADIUS
                    self.vx = -abs(self.vx)
                else:
                    self.x = brick.rect.right + self.RADIUS
                    self.vx = abs(self.vx)
            else:
                if self.vy > 0:
                    self.y = brick.rect.top - self.RADIUS
                    self.vy = -abs(self.vy)
                else:
                    self.y = brick.rect.bottom + self.RADIUS
                    self.vy = abs(self.vy)
            destroyed = brick.hit(damage=1)

        if destroyed:
            audio.play('break_brick')
            points = 100 * (1 if brick.btype == BrickType.STANDARD else 2)
            score_ref[0] += points
            particles.spawn_brick_burst(brick.rect.centerx, brick.rect.centery, brick.base_color, count=18)
            particles.add_floating_text(f"+{points}", brick.rect.centerx, brick.rect.centery, COLOR_NEON_YELLOW,
                                        pygame.font.Font(None, 24))

            # 25% Chance to spawn a Power-Up
            if random.random() < POWERUP_DROP_CHANCE:
                cat = random.random()
                if cat < 0.32:
                    # Multi-ball pool (10% x100, 25% x10, 65% x2)
                    m_roll = random.random()
                    if m_roll < 0.10:
                        ptype = PowerUpType.MULTI_100
                    elif m_roll < 0.35:
                        ptype = PowerUpType.MULTI_10
                    else:
                        ptype = PowerUpType.MULTI_2
                elif cat < 0.57:
                    # Paddle pool (10% Giga full-screen, 90% Extended)
                    p_roll = random.random()
                    if p_roll < 0.10:
                        ptype = PowerUpType.PADDLE_FULL
                    else:
                        ptype = PowerUpType.EXTENDED_PADDLE
                elif cat < 0.75:
                    ptype = PowerUpType.PIERCING_BALL
                elif cat < 0.80:
                    ptype = PowerUpType.BOMB_3X3
                elif cat < 0.88:
                    ptype = PowerUpType.GUN
                elif cat < 0.96:
                    ptype = PowerUpType.FIRE_SHIELD
                else:
                    ptype = PowerUpType.EXTRA_LIFE

                powerups.append(PowerUp(brick.rect.centerx, brick.rect.centery, ptype))
                audio.play('powerup_spawn')
        else:
            audio.play('hit_brick')
            score_ref[0] += 25
            particles.spawn_brick_burst(self.x, self.y, brick.base_color, count=5)

    def draw(self, surface: pygame.Surface):
        # Draw Motion Trail
        t_len = len(self.trail)
        for i, (tx, ty, is_pierce) in enumerate(self.trail):
            alpha_factor = (i + 1) / (t_len + 1)
            t_radius = max(1, int(self.RADIUS * alpha_factor * 0.8))
            t_color = COLOR_NEON_ORANGE if is_pierce else COLOR_NEON_CYAN
            blend_color = (
                int(t_color[0] * alpha_factor * 0.6),
                int(t_color[1] * alpha_factor * 0.6),
                int(t_color[2] * alpha_factor * 0.6)
            )
            pygame.draw.circle(surface, blend_color, (int(tx), int(ty)), t_radius)

        # Core Ball
        pos = (int(self.x), int(self.y))
        if self.pierce_count > 0:
            # Flaming / Plasma Piercing Aura
            pygame.draw.circle(surface, COLOR_NEON_ORANGE, pos, int(self.RADIUS + 3))
            pygame.draw.circle(surface, COLOR_NEON_YELLOW, pos, int(self.RADIUS))
            pygame.draw.circle(surface, COLOR_WHITE, pos, int(self.RADIUS * 0.5))
        else:
            # Neon Cyan Aura
            pygame.draw.circle(surface, (0, 160, 180), pos, int(self.RADIUS + 2))
            pygame.draw.circle(surface, COLOR_NEON_CYAN, pos, int(self.RADIUS))
            pygame.draw.circle(surface, COLOR_WHITE, pos, int(self.RADIUS * 0.5))


# ==============================================================================
# 9. 20-LEVEL PROGRESSION HIERARCHY
# ==============================================================================
class LevelBuilder:
    """
    Constructs the 20 level brick layouts according to progression specifications:
    - Levels 1–5: Standard Bricks (1-Hit) in grid, pyramid, pillars, diamond, invader.
    - Levels 6–10: Reinforced Bricks (2–3 Hits, color changes with HP).
    - Levels 11–15: Moving Bricks (Horizontal sliding rows bouncing off margins).
    - Levels 16–20: Unbreakable Iron Bricks + Regenerating Bricks + highest speeds.
      * Level 20 is 'The Cyber Nexus': fully beatable with open access to all targets.
    """
    BW = 56
    BH = 18
    PAD_X = 6
    PAD_Y = 6
    START_Y = 65

    @classmethod
    def get_layout(cls, level_num: int) -> list:
        method_name = f"_level_{level_num}"
        builder = getattr(cls, method_name, cls._level_1)
        return builder()

    @classmethod
    def _create_grid_from_chars(cls, lines: list, mapping: dict, offset_y: int = 65) -> list:
        bricks = []
        mapping = dict(mapping)
        if '#' not in mapping:
            mapping['#'] = {'type': BrickType.SCENERY_BARRIER, 'hp': 999}
        if '2' not in mapping:
            mapping['2'] = {'type': BrickType.REINFORCED, 'hp': 2, 'color': COLOR_NEON_YELLOW}
        if '3' not in mapping:
            mapping['3'] = {'type': BrickType.REINFORCED, 'hp': 3, 'color': COLOR_NEON_PURPLE}
        cols = max(len(line) for line in lines)
        total_w = cols * cls.BW + (cols - 1) * cls.PAD_X
        start_x = (SCREEN_WIDTH - total_w) // 2

        for r_idx, line in enumerate(lines):
            for c_idx, ch in enumerate(line):
                if ch in mapping and mapping[ch] is not None:
                    info = mapping[ch]
                    bx = start_x + c_idx * (cls.BW + cls.PAD_X)
                    by = offset_y + r_idx * (cls.BH + cls.PAD_Y)
                    btype = info.get('type', BrickType.STANDARD)
                    hp = info.get('hp', 1)
                    col = info.get('color', COLOR_NEON_CYAN)
                    spd = info.get('speed', 0.0)
                    min_x = info.get('min_x', 30)
                    max_x = info.get('max_x', SCREEN_WIDTH - 30)
                    bricks.append(Brick(bx, by, cls.BW, cls.BH, btype, hp, col, spd, min_x, max_x))
        return bricks

    # ----------------- LEVELS 1 - 5: STANDARD 1-HIT BRICKS -----------------
    @classmethod
    def _level_1(cls) -> list:
        """Level 1: Neon Grid (Simple welcoming layout)."""
        lines = [
            "CCCCCCCCCCC",
            "MMMMM2MMMMM",
            "YYYYYYYYYYY",
            "GGGGGGGGGGG",
        ]
        mapping = {
            'C': {'color': COLOR_NEON_CYAN},
            '2': {'type': BrickType.REINFORCED, 'hp': 2, 'color': COLOR_NEON_PURPLE},
            'M': {'color': COLOR_NEON_MAGENTA},
            '3': {'type': BrickType.REINFORCED, 'hp': 3, 'color': COLOR_NEON_PURPLE},
            'Y': {'color': COLOR_NEON_YELLOW},
            'G': {'color': COLOR_NEON_GREEN},
        }
        return cls._create_grid_from_chars(lines, mapping)

    @classmethod
    def _level_2(cls) -> list:
        """Level 2: Neon Inverted Pyramid."""
        lines = [
            "CCCCCCCCCCC",
            " MMMMMMMMM ",
            "  YYY3YYY  ",
            "   GGGGG   ",
            "    CCC    ",
            "     M     ",
        ]
        mapping = {
            'C': {'color': COLOR_NEON_CYAN},
            'M': {'color': COLOR_NEON_MAGENTA},
            'Y': {'color': COLOR_NEON_YELLOW},
            'G': {'color': COLOR_NEON_GREEN},
        }
        return cls._create_grid_from_chars(lines, mapping)

    @classmethod
    def _level_3(cls) -> list:
        """Level 3: Castle Battlement (3 Scenery Barrier Rails)."""
        lines = [
            "C C C C C C",
            "MMMMM3MMMMM",
            "YY   Y   YY",
            "GG # G # GG",
            "CC   #   CC",
            "MM   M   MM",
        ]
        mapping = {
            'C': {'color': COLOR_NEON_CYAN},
            'M': {'color': COLOR_NEON_MAGENTA},
            'Y': {'color': COLOR_NEON_YELLOW},
            'G': {'color': COLOR_NEON_GREEN},
        }
        return cls._create_grid_from_chars(lines, mapping)

    @classmethod
    def _level_4(cls) -> list:
        """Level 4: Diamond Matrix (4 Scenery Barrier Pins)."""
        lines = [
            "#    C    #",
            "    MMM    ",
            "   YYYYY   ",
            "  GGG3GGG  ",
            "   YYYYY   ",
            "    MMM    ",
            "#    C    #",
        ]
        mapping = {
            'C': {'color': COLOR_NEON_CYAN},
            'M': {'color': COLOR_NEON_MAGENTA},
            'Y': {'color': COLOR_NEON_YELLOW},
            'G': {'color': COLOR_NEON_GREEN},
        }
        return cls._create_grid_from_chars(lines, mapping)

    @classmethod
    def _level_5(cls) -> list:
        """Level 5: Space Invader (4 Scenery Barrier Corner Anchors)."""
        lines = [
            "# C     C #",
            "   C   C   ",
            "  CCCCCCC  ",
            " CC CCC CC ",
            " CCCC3CCCC ",
            "C CCCCCCC C",
            "# C     C #",
            "   CC CC   ",
        ]
        mapping = {
            'C': {'color': COLOR_NEON_CYAN},
        }
        return cls._create_grid_from_chars(lines, mapping, offset_y=60)

    # ----------------- LEVELS 6 - 10: REINFORCED MULTI-HIT BRICKS -----------------
    @classmethod
    def _level_6(cls) -> list:
        """Level 6: Shield Barrier (5 Scenery Barrier Rails)."""
        lines = [
            "22222222222",
            "21111111112",
            "#111 # 111#",
            "22 # 2 # 22",
        ]
        mapping = {
            '1': {'type': BrickType.STANDARD, 'hp': 1, 'color': COLOR_NEON_CYAN},
            '2': {'type': BrickType.REINFORCED, 'hp': 2, 'color': COLOR_NEON_YELLOW},
        }
        return cls._create_grid_from_chars(lines, mapping)

    @classmethod
    def _level_7(cls) -> list:
        """Level 7: The Citadel (6 Scenery Barrier Turret Rails)."""
        lines = [
            "# 1111111 #",
            "12222222221",
            "#233333332#",
            "12333333321",
            "#122222221#",
            "  1111111  ",
        ]
        mapping = {
            '1': {'type': BrickType.STANDARD, 'hp': 1, 'color': COLOR_NEON_CYAN},
            '2': {'type': BrickType.REINFORCED, 'hp': 2, 'color': COLOR_NEON_YELLOW},
            '3': {'type': BrickType.REINFORCED, 'hp': 3, 'color': COLOR_NEON_PURPLE},
        }
        return cls._create_grid_from_chars(lines, mapping)

    @classmethod
    def _level_8(cls) -> list:
        """Level 8: Checkered Barricade (7 Scenery Barrier Hubs)."""
        lines = [
            "#232323232#",
            "2 2323232 2",
            "23 # 3 # 32",
            "3232 # 2323",
            "#232323232#",
        ]
        mapping = {
            '2': {'type': BrickType.REINFORCED, 'hp': 2, 'color': COLOR_NEON_YELLOW},
            '3': {'type': BrickType.REINFORCED, 'hp': 3, 'color': COLOR_NEON_PURPLE},
        }
        return cls._create_grid_from_chars(lines, mapping)

    @classmethod
    def _level_9(cls) -> list:
        """Level 9: Double Helix (7 Scenery Barrier Spine & Anchors)."""
        lines = [
            "3   222   3",
            " 3 2 # 2 3 ",
            " #3     3# ",
            " 2 3 # 3 2 ",
            "2   333   2",
            " # 3 # 3 # ",
            "  3     3  ",
        ]
        mapping = {
            '2': {'type': BrickType.REINFORCED, 'hp': 2, 'color': COLOR_NEON_YELLOW},
            '3': {'type': BrickType.REINFORCED, 'hp': 3, 'color': COLOR_NEON_PURPLE},
        }
        return cls._create_grid_from_chars(lines, mapping)

    @classmethod
    def _level_10(cls) -> list:
        """Level 10: Fortress Gate (8 Scenery Barrier Portcullis & Flankers)."""
        lines = [
            "#33     33#",
            "333 222 333",
            "#33#212#33#",
            "222 212 222",
            " 2 #111# 2 ",
            "    111    ",
        ]
        mapping = {
            '1': {'type': BrickType.STANDARD, 'hp': 1, 'color': COLOR_NEON_GREEN},
            '2': {'type': BrickType.REINFORCED, 'hp': 2, 'color': COLOR_NEON_YELLOW},
            '3': {'type': BrickType.REINFORCED, 'hp': 3, 'color': COLOR_NEON_PURPLE},
        }
        return cls._create_grid_from_chars(lines, mapping)

    # ----------------- LEVELS 11 - 15: MOVING BRICKS -----------------
    @classmethod
    def _level_11(cls) -> list:
        """Level 11: Sliding Horizons (8 Scenery Barrier Rails)."""
        bricks = []
        # Stationary Top Row
        for i in range(11):
            bx = 60 + i * (cls.BW + cls.PAD_X)
            bricks.append(Brick(bx, 65, cls.BW, cls.BH, BrickType.STANDARD, 1, COLOR_NEON_CYAN))

        # Row 1 moving right
        for i in range(6):
            bx = 120 + i * (cls.BW + 20)
            bricks.append(Brick(bx, 100, cls.BW, cls.BH, BrickType.MOVING, 1, COLOR_NEON_MAGENTA,
                                move_speed=90.0, move_min_x=40, move_max_x=SCREEN_WIDTH - 40))

        # Row 2 moving left
        for i in range(6):
            bx = 150 + i * (cls.BW + 20)
            bricks.append(Brick(bx, 135, cls.BW, cls.BH, BrickType.MOVING, 1, COLOR_NEON_YELLOW,
                                move_speed=-90.0, move_min_x=40, move_max_x=SCREEN_WIDTH - 40))

        # 8 Stationary Scenery Barrier Rails (4 margin + 4 central deflector baffles)
        bricks.append(Brick(35, 100, cls.BW, cls.BH, BrickType.SCENERY_BARRIER))
        bricks.append(Brick(35, 135, cls.BW, cls.BH, BrickType.SCENERY_BARRIER))
        bricks.append(Brick(SCREEN_WIDTH - 35 - cls.BW, 100, cls.BW, cls.BH, BrickType.SCENERY_BARRIER))
        bricks.append(Brick(SCREEN_WIDTH - 35 - cls.BW, 135, cls.BW, cls.BH, BrickType.SCENERY_BARRIER))
        bricks.append(Brick(260, 100, cls.BW, cls.BH, BrickType.SCENERY_BARRIER))
        bricks.append(Brick(480, 100, cls.BW, cls.BH, BrickType.SCENERY_BARRIER))
        bricks.append(Brick(200, 135, cls.BW, cls.BH, BrickType.SCENERY_BARRIER))
        bricks.append(Brick(540, 135, cls.BW, cls.BH, BrickType.SCENERY_BARRIER))

        # Stationary Bottom Row
        for i in range(11):
            bx = 60 + i * (cls.BW + cls.PAD_X)
            bricks.append(Brick(bx, 170, cls.BW, cls.BH, BrickType.STANDARD, 1, COLOR_NEON_GREEN))

        return bricks

    @classmethod
    def _level_12(cls) -> list:
        """Level 12: Conveyor Matrix (10 Scenery Barrier Rails)."""
        bricks = []
        speeds = [80.0, -100.0, 80.0]
        colors = [COLOR_NEON_CYAN, COLOR_NEON_YELLOW, COLOR_NEON_MAGENTA]
        for r in range(3):
            by = 70 + r * 35
            for c in range(6):
                bx = 90 + c * (cls.BW + 30)
                bricks.append(Brick(bx, by, cls.BW, cls.BH, BrickType.MOVING, 1, colors[r],
                                    move_speed=speeds[r], move_min_x=30, move_max_x=SCREEN_WIDTH - 30))

        # 10 Stationary Barrier Rails (4 margin + 6 internal deflector chicanes)
        bricks.append(Brick(35, 80, cls.BW, cls.BH, BrickType.SCENERY_BARRIER))
        bricks.append(Brick(35, 140, cls.BW, cls.BH, BrickType.SCENERY_BARRIER))
        bricks.append(Brick(SCREEN_WIDTH - 35 - cls.BW, 80, cls.BW, cls.BH, BrickType.SCENERY_BARRIER))
        bricks.append(Brick(SCREEN_WIDTH - 35 - cls.BW, 140, cls.BW, cls.BH, BrickType.SCENERY_BARRIER))
        bricks.append(Brick(180, 92, cls.BW, cls.BH, BrickType.SCENERY_BARRIER))
        bricks.append(Brick(400, 92, cls.BW, cls.BH, BrickType.SCENERY_BARRIER))
        bricks.append(Brick(620, 92, cls.BW, cls.BH, BrickType.SCENERY_BARRIER))
        bricks.append(Brick(290, 127, cls.BW, cls.BH, BrickType.SCENERY_BARRIER))
        bricks.append(Brick(510, 127, cls.BW, cls.BH, BrickType.SCENERY_BARRIER))
        bricks.append(Brick(400, 162, cls.BW, cls.BH, BrickType.SCENERY_BARRIER))

        # Backing stationary row
        for i in range(10):
            bx = 85 + i * (cls.BW + cls.PAD_X)
            bricks.append(Brick(bx, 195, cls.BW, cls.BH, BrickType.STANDARD, 1, COLOR_NEON_BLUE))
        return bricks

    @classmethod
    def _level_13(cls) -> list:
        """Level 13: Orbital Flankers (10 Scenery Barrier Rails)."""
        bricks = []
        # Static center 2-hit block
        for r in range(4):
            for c in range(5):
                bx = 245 + c * (cls.BW + cls.PAD_X)
                by = 80 + r * (cls.BH + cls.PAD_Y)
                bricks.append(Brick(bx, by, cls.BW, cls.BH, BrickType.REINFORCED, 2, COLOR_NEON_YELLOW))

        # 10 Scenery Barriers: 4 bunker canopy + 6 wing deflector guides
        canopy_xs = [245, 311, 443, 509]
        for cx in canopy_xs:
            bricks.append(Brick(cx, 55, cls.BW, cls.BH, BrickType.SCENERY_BARRIER))

        for r in range(3):
            by = 75 + r * 28
            bricks.append(Brick(145, by, cls.BW, cls.BH, BrickType.SCENERY_BARRIER))
            bricks.append(Brick(SCREEN_WIDTH - 145 - cls.BW, by, cls.BW, cls.BH, BrickType.SCENERY_BARRIER))

        # Left moving wing
        for r in range(3):
            by = 75 + r * 28
            bricks.append(Brick(50, by, cls.BW, cls.BH, BrickType.MOVING, 1, COLOR_NEON_CYAN,
                                move_speed=110.0, move_min_x=20, move_max_x=130))

        # Right moving wing
        for r in range(3):
            by = 75 + r * 28
            bricks.append(Brick(650, by, cls.BW, cls.BH, BrickType.MOVING, 1, COLOR_NEON_MAGENTA,
                                move_speed=-110.0, move_min_x=SCREEN_WIDTH - 130 - cls.BW, move_max_x=SCREEN_WIDTH - 20))
        return bricks

    @classmethod
    def _level_14(cls) -> list:
        """Level 14: Kinetic Slalom (11 Scenery Barrier Rails)."""
        bricks = []
        # 11 Slalom Deflector Barriers creating a pinball chicane course
        barrier_positions = [
            (30, 70), (SCREEN_WIDTH - 30 - cls.BW, 70),
            (220, 86), (400, 86), (580, 86),
            (120, 118), (SCREEN_WIDTH - 120 - cls.BW, 118), (400, 118),
            (30, 150), (SCREEN_WIDTH - 30 - cls.BW, 150), (400, 150)
        ]
        for bx, by in barrier_positions:
            bricks.append(Brick(bx, by, cls.BW, cls.BH, BrickType.SCENERY_BARRIER))

        for r in range(4):
            by = 70 + r * 32
            spd = 130.0 if r % 2 == 0 else -130.0
            col = COLOR_NEON_GREEN if r % 2 == 0 else COLOR_NEON_ORANGE
            for c in range(5):
                bx = 80 + c * (cls.BW + 60)
                bricks.append(Brick(bx, by, cls.BW, cls.BH, BrickType.MOVING, 1, col,
                                    move_speed=spd, move_min_x=25, move_max_x=SCREEN_WIDTH - 25))
        return bricks

    @classmethod
    def _level_15(cls) -> list:
        """Level 15: Kinetic Armored Division (12 Scenery Barrier Spaced-Armor Plates)."""
        bricks = []
        # 12 Scenery Barriers: 4 margin + 6 frontal spaced-armor blast plates + 2 top canopy
        bricks.append(Brick(30, 95, cls.BW, cls.BH, BrickType.SCENERY_BARRIER))
        bricks.append(Brick(30, 131, cls.BW, cls.BH, BrickType.SCENERY_BARRIER))
        bricks.append(Brick(SCREEN_WIDTH - 30 - cls.BW, 95, cls.BW, cls.BH, BrickType.SCENERY_BARRIER))
        bricks.append(Brick(SCREEN_WIDTH - 30 - cls.BW, 131, cls.BW, cls.BH, BrickType.SCENERY_BARRIER))
        bricks.append(Brick(50, 60, cls.BW, cls.BH, BrickType.SCENERY_BARRIER))
        bricks.append(Brick(SCREEN_WIDTH - 50 - cls.BW, 60, cls.BW, cls.BH, BrickType.SCENERY_BARRIER))

        # 6 Frontal spaced armor plates defending the heavy moving tanks from direct frontal ball swarms
        for i in range(6):
            bx = 100 + i * (cls.BW + 35)
            bricks.append(Brick(bx, 138, cls.BW, cls.BH, BrickType.SCENERY_BARRIER))

        # Stationary top anchor
        for c in range(11):
            bx = 60 + c * (cls.BW + cls.PAD_X)
            bricks.append(Brick(bx, 60, cls.BW, cls.BH, BrickType.REINFORCED, 2, COLOR_NEON_PURPLE))

        # 2 rows of 2-HP moving heavy tanks
        for r in range(2):
            by = 95 + r * 36
            spd = 95.0 if r == 0 else -95.0
            for c in range(6):
                bx = 100 + c * (cls.BW + 35)
                bricks.append(Brick(bx, by, cls.BW, cls.BH, BrickType.MOVING, 2, COLOR_NEON_YELLOW,
                                    move_speed=spd, move_min_x=30, move_max_x=SCREEN_WIDTH - 30))

        # Bottom 1-hit row
        for c in range(11):
            bx = 60 + c * (cls.BW + cls.PAD_X)
            bricks.append(Brick(bx, 175, cls.BW, cls.BH, BrickType.STANDARD, 1, COLOR_NEON_CYAN))
        return bricks

    # ----------------- LEVELS 16 - 20: UNBREAKABLE IRON + REGENERATING + ANTI-SUPERNOVA -----------------
    @classmethod
    def _level_16(cls) -> list:
        """Level 16: Iron Bastion & Regenerating Sanctum (14 Scenery Barriers, Anti-Supernova Blast Shield)."""
        lines = [
            "# I R R I #",
            "I # 2 2 # I",
            "# I R R I #",
            "##  222  ##",
            "# 1 # # 1 #",
        ]
        mapping = {
            'I': {'type': BrickType.UNBREAKABLE, 'color': COLOR_IRON_BASE},
            'R': {'type': BrickType.REGENERATING, 'hp': 2, 'color': COLOR_REGEN_BASE},
            '2': {'type': BrickType.REINFORCED, 'hp': 2, 'color': COLOR_NEON_YELLOW},
            '1': {'type': BrickType.STANDARD, 'hp': 1, 'color': COLOR_NEON_CYAN},
        }
        return cls._create_grid_from_chars(lines, mapping, offset_y=65)

    @classmethod
    def _level_17(cls) -> list:
        """Level 17: Pinball Bumpers & Kinetic Baffles (16 Scenery Barriers, Deflecting Supernova Swarms)."""
        lines = [
            "# I     I #",
            " # 2 # 2 # ",
            "# # RRR # #",
            " # 2 # 2 # ",
            "# I     I #",
            " # 1 1 1 # ",
        ]
        mapping = {
            'I': {'type': BrickType.UNBREAKABLE, 'color': COLOR_IRON_BASE},
            'R': {'type': BrickType.REGENERATING, 'hp': 2, 'color': COLOR_REGEN_BASE},
            '2': {'type': BrickType.REINFORCED, 'hp': 2, 'color': COLOR_NEON_YELLOW},
            '1': {'type': BrickType.STANDARD, 'hp': 1, 'color': COLOR_NEON_GREEN},
        }
        return cls._create_grid_from_chars(lines, mapping, offset_y=60)

    @classmethod
    def _level_18(cls) -> list:
        """Level 18: Cyber Labyrinth Fortress (19 Scenery Barriers, Multi-Tier Blast Deflectors)."""
        lines = [
            "## I R I ##",
            "I R #I# R I",
            "# 2 R#R 2 #",
            "## 2# #2 ##",
            "# # 111 # #",
        ]
        mapping = {
            'I': {'type': BrickType.UNBREAKABLE, 'color': COLOR_IRON_BASE},
            'R': {'type': BrickType.REGENERATING, 'hp': 2, 'color': COLOR_REGEN_BASE},
            '2': {'type': BrickType.REINFORCED, 'hp': 2, 'color': COLOR_NEON_YELLOW},
            '1': {'type': BrickType.STANDARD, 'hp': 1, 'color': COLOR_NEON_CYAN},
        }
        return cls._create_grid_from_chars(lines, mapping, offset_y=60)

    @classmethod
    def _level_19(cls) -> list:
        """Level 19: Iron Sentinels & Anti-Blast Bunkers (23 Scenery Barriers, Heavy Frontal Anti-Supernova Wall)."""
        bricks = []
        # Regenerating Stationary Target Grid protected by Heavy Frontal Bunker Wall
        lines = [
            "# # RRR # #",
            "# I 222 I #",
            "# # RRR # #",
            "### ### ###",
            "# 11   11 #",
        ]
        mapping = {
            'R': {'type': BrickType.REGENERATING, 'hp': 2, 'color': COLOR_REGEN_BASE},
            '2': {'type': BrickType.REINFORCED, 'hp': 2, 'color': COLOR_NEON_YELLOW},
            'I': {'type': BrickType.UNBREAKABLE, 'color': COLOR_IRON_BASE},
            '1': {'type': BrickType.STANDARD, 'hp': 1, 'color': COLOR_NEON_MAGENTA},
        }
        bricks.extend(cls._create_grid_from_chars(lines, mapping, offset_y=60))

        # 2 Moving Iron Sentinels sweeping the mid-level corridor
        b1 = Brick(120, 185, cls.BW, cls.BH, BrickType.UNBREAKABLE, 1, COLOR_IRON_BASE,
                   move_speed=120.0, move_min_x=50, move_max_x=SCREEN_WIDTH - 50)
        bricks.append(b1)

        b2 = Brick(520, 215, cls.BW, cls.BH, BrickType.UNBREAKABLE, 1, COLOR_IRON_BASE,
                   move_speed=-120.0, move_min_x=50, move_max_x=SCREEN_WIDTH - 50)
        bricks.append(b2)

        # 2 Stationary sentinel guide barrier rails at margins
        bricks.append(Brick(25, 185, cls.BW, cls.BH, BrickType.SCENERY_BARRIER))
        bricks.append(Brick(SCREEN_WIDTH - 25 - cls.BW, 215, cls.BW, cls.BH, BrickType.SCENERY_BARRIER))

        return bricks

    @classmethod
    def _level_20(cls) -> list:
        """
        Level 20: 'The Cyber Nexus - Citadel Blast Shield Array' (Final Master Stage).
        Protected by 26 permanent industrial hazard scenery barriers forming a multi-layer fortress canopy
        and frontal blast baffle ('## ##### ##') specifically engineered to absorb and deflect the 100-ball supernova!
        Guaranteed 100% beatable through narrow ballistic funnels and flanking apertures.
        """
        lines = [
            "###  #  ###",
            "# I 3R3 I #",
            "##  323  ##",
            "# I R3R I #",
            "## ##### ##",
            "# 1     1 #",
        ]
        mapping = {
            'I': {'type': BrickType.UNBREAKABLE, 'color': COLOR_IRON_BASE},
            'R': {'type': BrickType.REGENERATING, 'hp': 2, 'color': COLOR_REGEN_BASE},
            '3': {'type': BrickType.REINFORCED, 'hp': 3, 'color': COLOR_NEON_PURPLE},
            '2': {'type': BrickType.REINFORCED, 'hp': 2, 'color': COLOR_NEON_YELLOW},
            '1': {'type': BrickType.STANDARD, 'hp': 1, 'color': COLOR_NEON_CYAN},
        }
        return cls._create_grid_from_chars(lines, mapping, offset_y=60)


# ==============================================================================
# 10. GAME ENGINE & STATE MACHINE
# ==============================================================================
class GameState:
    START           = "START"
    READY           = "READY"
    PLAYING         = "PLAYING"
    STAGE_CLEAR     = "STAGE_CLEAR"
    GAME_OVER       = "GAME_OVER"
    VICTORY         = "VICTORY"
    PAUSED          = "PAUSED"


class BreakoutGame:
    TOTAL_LEVELS = 20
    INITIAL_LIVES = 3

    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Cyberpunk Breakout (Casse-Brique)")
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()
        self.running = True

        # Systems
        self.audio = ProceduralAudio()
        self.high_score_mgr = HighScoreManager()
        self.particles = ParticleManager()

        # Fonts
        self.font_title = pygame.font.Font(None, 62)
        self.font_large = pygame.font.Font(None, 44)
        self.font_medium = pygame.font.Font(None, 28)
        self.font_small = pygame.font.Font(None, 20)

        # Game State
        self.state = GameState.START
        self.prev_state = GameState.START
        self.current_level = 1
        self.score = [0]  # List ref for mutable updates in collision callbacks
        self.lives = self.INITIAL_LIVES
        self.state_timer = 0.0
        self.is_new_high_score = False
        self.speed_multiplier = 1.0  # Real-time speed scale (0.5x to 4.0x)

        # Entities
        self.paddle = Paddle()
        self.balls = []
        self.bricks = []
        self.powerups = []
        self.hazard_bottles = []
        self.bullets = []

        # Tactical Bomb Charges
        self.bomb_charges = 0

        # Dynamic Difficulty & Timers
        self.shuffle_timer = 0.0
        self.bottle_timer = 0.0

        # Level 20 Rainbow Regenerator
        self.rainbow_brick = None
        self.rainbow_timer = 0.0
        self.rainbow_state = "WAIT_CHOOSE"
        self.rainbow_beam = None  # (start_pos, end_pos, timer)
        self.level_initial_destructible = 0

        # Background grid animation
        self.grid_scroll = 0.0

        # On-screen touch buttons for mobile (faint in top corners)
        self.btn_left_rect = pygame.Rect(8, HUD_HEIGHT + 6, 90, 64)
        self.btn_right_rect = pygame.Rect(SCREEN_WIDTH - 98, HUD_HEIGHT + 6, 90, 64)
        self._last_corner_action_time = 0.0

    def fire_gun(self) -> bool:
        """Fires blaster laser shot from paddle when gun power-up is active."""
        if getattr(self.paddle, 'gun_timer', 0.0) > 0.0 and getattr(self.paddle, 'gun_ammo', 0) > 0:
            self.paddle.gun_ammo -= 1
            bx = self.paddle.x + self.paddle.width / 2.0
            by = self.paddle.y - 6
            self.bullets.append(Bullet(bx, by))
            self.audio.play('laser_pierce')
            self.particles.spawn_paddle_sparks(bx, by, count=10)
            if self.paddle.gun_ammo <= 0:
                self.paddle.gun_timer = 0.0
            return True
        return False

    def adjust_speed(self, delta_step: int):
        multipliers = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0, 4.0]
        cur_idx = 2
        for i, m in enumerate(multipliers):
            if abs(m - self.speed_multiplier) < 0.05:
                cur_idx = i
                break
        new_idx = max(0, min(len(multipliers) - 1, cur_idx + delta_step))
        self.speed_multiplier = multipliers[new_idx]
        current_base = BASE_BALL_SPEED * (1.0 + SPEED_INCREMENT * (self.current_level - 1)) * self.speed_multiplier
        for b in self.balls:
            b.target_speed = current_base
            b._normalize_speed()
        self.particles.add_floating_text(
            f"SPEED: {self.speed_multiplier}x ({current_base * 60:.0f} px/s)",
            SCREEN_WIDTH // 2, HUD_HEIGHT + 30, COLOR_NEON_YELLOW, self.font_medium
        )

    def start_new_game(self):
        self.score[0] = 0
        self.lives = self.INITIAL_LIVES
        self.current_level = 1
        self.is_new_high_score = False
        self.bomb_charges = 0
        self.load_level(self.current_level)

    def load_level(self, level_num: int):
        self.current_level = level_num
        self.bricks = LevelBuilder.get_layout(level_num)
        self.level_initial_destructible = sum(1 for b in self.bricks if not b.is_unbreakable)
        self.powerups.clear()
        self.bullets.clear()
        self.hazard_bottles.clear()
        self.bottle_timer = 0.0
        self.shuffle_timer = 0.0
        self.rainbow_brick = None
        self.rainbow_timer = 0.0
        self.rainbow_state = "WAIT_CHOOSE"
        self.rainbow_beam = None
        self.paddle.reset_for_level(level_num)

        # Spawn initial ball attached to paddle
        ball_speed = BASE_BALL_SPEED * (1.0 + SPEED_INCREMENT * (level_num - 1)) * self.speed_multiplier
        self.balls = [Ball(self.paddle.x + self.paddle.width / 2.0, self.paddle.y - 8, 0, -ball_speed, ball_speed)]
        self.balls[0].attached = True

        self.state = GameState.STAGE_CLEAR
        self.state_timer = 1.4  # Stage introduction splash duration

    def launch_ball(self):
        ball_speed = BASE_BALL_SPEED * (1.0 + SPEED_INCREMENT * (self.current_level - 1)) * self.speed_multiplier
        for ball in self.balls:
            if ball.attached:
                ball.launch(ball_speed)
                self.audio.play('hit_paddle')
        self.state = GameState.PLAYING

    def handle_ball_loss(self):
        """Called when all active balls have fallen below screen height."""
        self.lives -= 1
        self.audio.play('lose_life')

        if self.lives <= 0:
            # Game Over
            self.state = GameState.GAME_OVER
            self.state_timer = 1.0
            self.audio.play('game_over')
            self.is_new_high_score = self.high_score_mgr.update(self.score[0], self.current_level)
        else:
            # Reset ball onto paddle
            self.paddle.extended_timer = 0.0
            self.paddle._recompute_width()
            ball_speed = BASE_BALL_SPEED * (1.0 + SPEED_INCREMENT * (self.current_level - 1)) * self.speed_multiplier
            new_ball = Ball(self.paddle.x + self.paddle.width / 2.0, self.paddle.y - 8, 0, -ball_speed, ball_speed)
            new_ball.attached = True
            self.balls = [new_ball]
            self.powerups.clear()
            self.bullets.clear()
            self.state = GameState.READY

    def check_level_completion(self):
        """Level is complete when all destructible bricks are cleared."""
        destructible_alive = any(b.is_alive and not b.is_unbreakable for b in self.bricks)
        if not destructible_alive:
            self.audio.play('stage_clear')
            self.score[0] += 500 * self.current_level  # Level clear bonus
            if self.current_level >= self.TOTAL_LEVELS:
                self.state = GameState.VICTORY
                self.is_new_high_score = self.high_score_mgr.update(self.score[0], self.current_level)
            else:
                self.load_level(self.current_level + 1)

    # ==========================================================================
    # UPDATE LOOP
    # ==========================================================================
    def update(self, dt: float):
        self.grid_scroll = (self.grid_scroll + dt * 25.0) % 30.0
        self.particles.update(dt)
        for bullet in getattr(self, 'bullets', []):
            bullet.update(dt)
        if hasattr(self, 'bullets'):
            self.bullets = [b for b in self.bullets if b.alive]

        for bullet in getattr(self, 'bullets', []):
            if not bullet.alive: continue
            for b in self.bricks:
                if b.is_alive and not b.is_unbreakable and bullet.rect.colliderect(b.rect):
                    destroyed = b.hit(1)
                    bullet.alive = False
                    self.particles.spawn_brick_burst(b.rect.centerx, b.rect.centery, COLOR_NEON_YELLOW, count=8)
                    if destroyed:
                        self.score[0] += 100 * (1 if b.btype == BrickType.STANDARD else 2)
                        self.audio.play('break_brick')
                    else:
                        self.audio.play('hit_brick')
                    break

        # Key state & Mouse status
        keys = pygame.key.get_pressed()
        mouse_dx, mouse_dy = pygame.mouse.get_rel()
        mouse_x, mouse_y = pygame.mouse.get_pos()
        mouse_moved = (mouse_dx != 0 or mouse_dy != 0)
        mouse_pressed = pygame.mouse.get_pressed()[0]
        can_follow_mouse = not (self.btn_left_rect.collidepoint(mouse_x, mouse_y) or
                                self.btn_right_rect.collidepoint(mouse_x, mouse_y))

        # Paddle update
        if self.state in (GameState.READY, GameState.PLAYING):
            self.paddle.update(dt, keys, mouse_dx, mouse_x, mouse_moved, mouse_pressed, can_follow_mouse)

        # Bricks update
        if self.state == GameState.PLAYING:
            for brick in self.bricks:
                if brick.is_alive:
                    brick.update(dt)

        # Ball update
        if self.state == GameState.READY:
            for ball in self.balls:
                if ball.attached:
                    ball.update_attached(self.paddle)

        elif self.state == GameState.PLAYING:
            for ball in self.balls:
                ball.update_physics(dt, self.paddle, self.bricks, self.audio,
                                    self.particles, self.powerups, self.score)

            # Clean up dead balls (Phase 2 Loop 2: Object Lifecycle & Memory Cleanup)
            self.balls = [b for b in self.balls if b.alive]
            if len(self.balls) == 0:
                self.handle_ball_loss()
                return

            # Check level completion
            self.check_level_completion()

            # Power-ups update & paddle collection
            for p in self.powerups:
                p.update(dt)
                if p.alive and p.rect.colliderect(self.paddle.rect):
                    p.alive = False
                    self.audio.play('powerup_get')
                    self.particles.spawn_paddle_sparks(p.x, p.y, count=12)

                    if p.ptype == PowerUpType.MULTI_2:
                        # Duplicate all active balls (1 -> 2, 2 -> 4, etc.)
                        ball_speed = BASE_BALL_SPEED * (1.0 + SPEED_INCREMENT * (self.current_level - 1)) * self.speed_multiplier
                        current_active = list(self.balls)
                        new_clones = []
                        for b in current_active:
                            if len(self.balls) + len(new_clones) >= 120:
                                break
                            base_angle = math.atan2(b.vy, b.vx) if (b.vx != 0 or b.vy != 0) else -math.pi / 2
                            diverge = random.choice([-0.35, 0.35]) + random.uniform(-0.1, 0.1)
                            new_angle = base_angle + diverge
                            if math.sin(new_angle) > -0.2:
                                n_vy = -abs(math.sin(new_angle)) * ball_speed
                                n_vx = math.cos(new_angle) * ball_speed
                            else:
                                n_vx = math.cos(new_angle) * ball_speed
                                n_vy = math.sin(new_angle) * ball_speed
                            clone = Ball(b.x, b.y, n_vx, n_vy, ball_speed)
                            clone.attached = False
                            clone.pierce_count = b.pierce_count
                            new_clones.append(clone)
                        self.balls.extend(new_clones)
                        self.particles.add_floating_text(
                            "MULTI-BALL x2!", self.paddle.rect.centerx,
                            self.paddle.rect.top - 15, COLOR_NEON_GREEN, self.font_medium
                        )

                    elif p.ptype == PowerUpType.MULTI_10:
                        # 10x ball multiplier (spawn 9 clones per ball, capped at 120)
                        ball_speed = BASE_BALL_SPEED * (1.0 + SPEED_INCREMENT * (self.current_level - 1)) * self.speed_multiplier
                        current_active = list(self.balls)
                        new_clones = []
                        for b in current_active:
                            for _ in range(9):
                                if len(self.balls) + len(new_clones) >= 120:
                                    break
                                angle = random.uniform(-math.pi * 0.85, -math.pi * 0.15)
                                vx = math.cos(angle) * ball_speed
                                vy = math.sin(angle) * ball_speed
                                clone = Ball(b.x, b.y, vx, vy, ball_speed)
                                clone.attached = False
                                clone.pierce_count = b.pierce_count
                                new_clones.append(clone)
                        self.balls.extend(new_clones)
                        self.particles.add_floating_text(
                            "MULTI-BALL x10 FRENZY!", self.paddle.rect.centerx,
                            self.paddle.rect.top - 15, COLOR_NEON_YELLOW, self.font_medium
                        )

                    elif p.ptype == PowerUpType.MULTI_100:
                        # 100x ball supernova: radiates in ALL 360° directions from CURRENT ball(s)
                        # Does NOT launch from the paddle, preventing an upward rush that wipes the level instantly
                        ball_speed = BASE_BALL_SPEED * (1.0 + SPEED_INCREMENT * (self.current_level - 1)) * self.speed_multiplier
                        current_active = [b for b in self.balls if b.alive]
                        if not current_active:
                            current_active = [Ball(self.paddle.rect.centerx, self.paddle.rect.top - 12, 0, -ball_speed, ball_speed)]
                            self.balls.append(current_active[0])

                        total_to_spawn = 100
                        balls_per_parent = max(1, total_to_spawn // len(current_active))
                        new_clones = []

                        for parent in current_active:
                            self.particles.spawn_brick_burst(parent.x, parent.y, (255, 215, 0), count=25)
                            for i in range(balls_per_parent):
                                if len(self.balls) + len(new_clones) >= 128:
                                    break
                                # Distribute evenly around full 360-degree circle (0 to 2*pi)
                                angle = (i / balls_per_parent) * 2.0 * math.pi + random.uniform(-0.06, 0.06)
                                speed_variation = ball_speed * random.uniform(0.90, 1.10)
                                vx = math.cos(angle) * speed_variation
                                vy = math.sin(angle) * speed_variation

                                # Prevent pure horizontal trajectory deadlock
                                if abs(vy) < ball_speed * 0.2:
                                    vy = math.copysign(ball_speed * 0.2, vy if vy != 0 else 1.0)

                                clone = Ball(parent.x, parent.y, vx, vy, ball_speed)
                                clone.attached = False
                                clone.pierce_count = parent.pierce_count
                                new_clones.append(clone)

                        self.balls.extend(new_clones)
                        self.particles.add_floating_text(
                            "*** 360° OMNIDIRECTIONAL SUPERNOVA! ***", SCREEN_WIDTH // 2,
                            SCREEN_HEIGHT // 2, (255, 215, 0), self.font_large
                        )

                    elif p.ptype == PowerUpType.PIERCING_BALL:
                        for b in self.balls:
                            b.grant_pierce()
                        self.particles.add_floating_text(
                            "PIERCING BALL!", self.paddle.rect.centerx,
                            self.paddle.rect.top - 15, COLOR_NEON_ORANGE, self.font_medium
                        )

                    elif p.ptype == PowerUpType.EXTENDED_PADDLE:
                        self.paddle.apply_powerup_extended()
                        self.particles.add_floating_text(
                            "EXPAND PADDLE!", self.paddle.rect.centerx,
                            self.paddle.rect.top - 15, COLOR_NEON_CYAN, self.font_medium
                        )

                    elif p.ptype == PowerUpType.PADDLE_FULL:
                        self.paddle.apply_powerup_giga()
                        self.particles.add_floating_text(
                            "*** GIGA FULL-SCREEN PADDLE! ***", SCREEN_WIDTH // 2,
                            self.paddle.rect.top - 20, COLOR_WHITE, self.font_large
                        )

                    elif p.ptype == PowerUpType.EXTRA_LIFE:
                        self.lives += 1
                        self.audio.play('life_gain')
                        self.particles.add_floating_text(
                            f"+1 EXTRA LIFE! ({self.lives} LIVES)", self.paddle.rect.centerx,
                            self.paddle.rect.top - 15, (255, 50, 140), self.font_medium
                        )

                    elif p.ptype == PowerUpType.BOMB_3X3:
                        self.bomb_charges += 1
                        self.particles.add_floating_text(
                            f"TACTICAL BOMB ARMED! ({self.bomb_charges} READY)", self.paddle.rect.centerx,
                            self.paddle.rect.top - 15, (255, 40, 40), self.font_medium
                        )

                    elif p.ptype == PowerUpType.GUN:
                        self.paddle.gun_timer = 4.0
                        self.paddle.gun_ammo = 3
                        self.particles.add_floating_text(
                            "BLASTER ARMED! (3 SHOTS / 4s)", self.paddle.rect.centerx,
                            self.paddle.rect.top - 15, (255, 100, 50), self.font_medium
                        )

                    elif p.ptype == PowerUpType.FIRE_SHIELD:
                        self.paddle.fire_shield_timer = 7.0
                        self.particles.add_floating_text(
                            "ARMOR SHIELD! (7s)", self.paddle.rect.centerx,
                            self.paddle.rect.top - 15, (0, 220, 255), self.font_medium
                        )

            # Memory cleanup for dropped power-ups
            self.powerups = [p for p in self.powerups if p.alive]

            # Dynamic Level Hazards & Gimmicks
            self.update_hazard_bottles(dt)
            self.check_matrix_shuffle(dt)
            self.update_rainbow_mechanic(dt)

        elif self.state == GameState.STAGE_CLEAR:
            self.state_timer -= dt
            if self.state_timer <= 0.0:
                self.state = GameState.READY

    # ==========================================================================
    # LEVEL MECHANICS & DYNAMIC HAZARDS
    # ==========================================================================
    def update_hazard_bottles(self, dt: float):
        """Levels 19 & 20: Lethal hazard bottle drops every 30 seconds."""
        if self.current_level not in (19, 20) or self.state != GameState.PLAYING:
            return

        self.bottle_timer += dt
        if self.bottle_timer >= 30.0:
            self.bottle_timer = 0.0
            alive_bricks = [b for b in self.bricks if b.is_alive]
            if alive_bricks:
                target = random.choice(alive_bricks)
                bx, by = target.rect.centerx, target.rect.centery
            else:
                bx, by = random.randint(60, SCREEN_WIDTH - 60), 70
            self.hazard_bottles.append(HazardBottle(bx, by))
            self.particles.add_floating_text(
                "WARNING: HAZARD BOTTLE INCOMING!",
                SCREEN_WIDTH // 2, 80, (255, 30, 60), self.font_medium
            )

        surviving_bottles = []
        for bottle in self.hazard_bottles:
            reached_floor = not bottle.update(dt)
            if reached_floor:
                # Bottle reached the floor safely! (Allowed: no life deduction)
                self.particles.spawn_paddle_sparks(bottle.x, SCREEN_HEIGHT - 4, count=6)
                continue

            # 1. Check collision with active balls (Shatters bottle, +500 pts)
            bottle_shattered = False
            for ball in self.balls:
                dist = math.hypot(ball.x - bottle.x, ball.y - bottle.y)
                if dist <= ball.RADIUS + bottle.RADIUS + 3.0:
                    bottle_shattered = True
                    bottle.alive = False
                    self.score[0] += 500
                    self.audio.play('bottle_shatter')
                    self.particles.spawn_brick_burst(bottle.x, bottle.y, (180, 0, 220), count=18)
                    self.particles.add_floating_text(
                        "+500 BOTTLE SHATTERED!",
                        bottle.x, bottle.y, COLOR_NEON_GREEN, self.font_medium
                    )
                    ball.vy = -abs(ball.vy)
                    ball._normalize_speed()
                    break

            if bottle_shattered:
                continue

            # 2. Check collision with paddle (Lethal hazard: must NOT hit paddle!)
            if bottle.rect.colliderect(self.paddle.rect):
                bottle.alive = False
                if getattr(self.paddle, 'fire_shield_timer', 0.0) > 0.0:
                    self.audio.play('bottle_shatter')
                    self.particles.spawn_brick_burst(bottle.x, bottle.y, (0, 220, 255), count=24)
                    self.particles.add_floating_text(
                        "ARMOR BLOCKED!",
                        self.paddle.rect.centerx, self.paddle.y - 25, (0, 220, 255), self.font_large
                    )
                    continue

                self.lives -= 1
                self.audio.play('lose_life')
                self.particles.spawn_brick_burst(bottle.x, bottle.y, (255, 30, 60), count=22)
                self.particles.add_floating_text(
                    "BOTTLE HIT PADDLE! -1 LIFE",
                    self.paddle.rect.centerx, self.paddle.y - 25, (255, 30, 60), self.font_large
                )
                if self.lives <= 0:
                    self.state = GameState.GAME_OVER
                    self.state_timer = 1.0
                    self.audio.play('game_over')
                    self.is_new_high_score = self.high_score_mgr.update(self.score[0], self.current_level)
                    return
                continue

            if bottle.alive:
                surviving_bottles.append(bottle)

        self.hazard_bottles = surviving_bottles

    def check_matrix_shuffle(self, dt: float):
        """
        Matrix shuffle intervals:
        - Levels 8–15: Every 3 mins (180s), 10% chance
        - Levels 16–19: Every 2 mins (120s), 10% chance
        - Level 20: Every 1 min (60s), 10% chance
        """
        if self.state != GameState.PLAYING:
            return

        interval = 0.0
        if 8 <= self.current_level <= 15:
            interval = 180.0
        elif 16 <= self.current_level <= 19:
            interval = 120.0
        elif self.current_level == 20:
            interval = 60.0
        else:
            return

        self.shuffle_timer += dt
        if self.shuffle_timer >= interval:
            self.shuffle_timer = 0.0
            if random.random() < 0.10:
                self.perform_matrix_shuffle()

    def perform_matrix_shuffle(self):
        """Shuffles alive brick positions strictly within upper matrix bounds (Y <= 360), leaving permanent scenery fixed."""
        alive_bricks = [b for b in self.bricks if b.is_alive and not getattr(b, 'is_scenery', False)]
        if len(alive_bricks) < 2:
            return

        positions = [(b.x, b.y) for b in alive_bricks]
        random.shuffle(positions)

        for b, (nx, ny) in zip(alive_bricks, positions):
            b.x = float(nx)
            b.y = min(360.0, float(ny))  # Guarantee safety distance from paddle (Y=550)
            b.rect.x = int(b.x)
            b.rect.y = int(b.y)
            if b.btype == BrickType.MOVING:
                b.move_min_x = max(20.0, b.x - 120.0)
                b.move_max_x = min(SCREEN_WIDTH - 20.0, b.x + b.width + 120.0)

        self.audio.play('hit_iron')
        for b in alive_bricks:
            self.particles.spawn_brick_burst(b.rect.centerx, b.rect.centery, COLOR_NEON_MAGENTA, count=3)
        self.particles.add_floating_text(
            "*** MATRIX SHUFFLE ACTIVATED! ***",
            SCREEN_WIDTH // 2, 230, COLOR_NEON_MAGENTA, self.font_large
        )

    def update_rainbow_mechanic(self, dt: float):
        """
        Level 20 Rainbow Regenerator:
        When remaining destructibles < 50%, every 30s picks 1 brick to become flashing rainbow.
        If destroyed within 30s: +500 pts.
        If not destroyed in 30s: spawns 1 new brick with energy beam.
        30s cooldown before next selection.
        """
        if self.current_level != 20 or self.state != GameState.PLAYING:
            return

        if self.rainbow_beam:
            self.rainbow_beam[2] -= dt
            if self.rainbow_beam[2] <= 0:
                self.rainbow_beam = None

        destruct_alive = [b for b in self.bricks if b.is_alive and not b.is_unbreakable]
        if self.level_initial_destructible <= 0:
            return
        if len(destruct_alive) >= self.level_initial_destructible * 0.5:
            return

        if self.rainbow_state == "WAIT_CHOOSE":
            self.rainbow_timer += dt
            if self.rainbow_timer >= 30.0:
                self.rainbow_timer = 0.0
                candidates = [b for b in destruct_alive if not getattr(b, 'is_rainbow', False)]
                if candidates:
                    self.rainbow_brick = random.choice(candidates)
                    self.rainbow_brick.is_rainbow = True
                    self.rainbow_state = "COUNTDOWN"
                    self.particles.add_floating_text(
                        "RAINBOW TARGET DETECTED! (30s)",
                        self.rainbow_brick.rect.centerx,
                        self.rainbow_brick.rect.top - 15,
                        COLOR_NEON_YELLOW,
                        self.font_medium
                    )

        elif self.rainbow_state == "COUNTDOWN":
            self.rainbow_timer += dt
            if self.rainbow_brick is None or not self.rainbow_brick.is_alive:
                self.score[0] += 500
                self.audio.play('stage_clear')
                self.particles.add_floating_text(
                    "+500 RAINBOW CRACKED!",
                    SCREEN_WIDTH // 2, 200, COLOR_NEON_YELLOW, self.font_large
                )
                self.rainbow_brick = None
                self.rainbow_state = "COOLDOWN"
                self.rainbow_timer = 0.0
            elif self.rainbow_timer >= 30.0:
                # 30s expired: spawn 1 new brick in open slot with energy beam!
                new_pos = self._find_open_brick_slot()
                if new_pos:
                    nx, ny = new_pos
                    new_b = Brick(nx, ny, LevelBuilder.BW, LevelBuilder.BH, BrickType.STANDARD, 1, COLOR_NEON_CYAN)
                    self.bricks.append(new_b)
                    if self.rainbow_brick:
                        self.rainbow_beam = [
                            (self.rainbow_brick.rect.centerx, self.rainbow_brick.rect.centery),
                            (nx + LevelBuilder.BW // 2, ny + LevelBuilder.BH // 2),
                            0.8
                        ]
                    self.particles.spawn_brick_burst(nx + LevelBuilder.BW // 2, ny + LevelBuilder.BH // 2, COLOR_NEON_MAGENTA, count=16)
                    self.particles.add_floating_text("RAINBOW REGEN: +1 BRICK!", nx, ny - 12, COLOR_NEON_MAGENTA, self.font_medium)
                    self.audio.play('powerup_spawn')

                if self.rainbow_brick:
                    self.rainbow_brick.is_rainbow = False
                self.rainbow_brick = None
                self.rainbow_state = "COOLDOWN"
                self.rainbow_timer = 0.0

        elif self.rainbow_state == "COOLDOWN":
            self.rainbow_timer += dt
            if self.rainbow_timer >= 30.0:
                self.rainbow_timer = 0.0
                self.rainbow_state = "WAIT_CHOOSE"

    def _find_open_brick_slot(self) -> tuple:
        """Finds an unoccupied slot in the upper playfield matrix for level 20 regeneration."""
        occupied_rects = [b.rect for b in self.bricks if b.is_alive]
        lines_count = 6
        cols = 13
        total_w = cols * LevelBuilder.BW + (cols - 1) * LevelBuilder.PAD_X
        start_x = (SCREEN_WIDTH - total_w) // 2
        offset_y = 60

        candidate_slots = []
        for r in range(lines_count):
            for c in range(cols):
                bx = start_x + c * (LevelBuilder.BW + LevelBuilder.PAD_X)
                by = offset_y + r * (LevelBuilder.BH + LevelBuilder.PAD_Y)
                test_rect = pygame.Rect(bx, by, LevelBuilder.BW, LevelBuilder.BH)
                if not any(test_rect.colliderect(occ) for occ in occupied_rects):
                    candidate_slots.append((bx, by))

        if candidate_slots:
            return random.choice(candidate_slots)
        return (random.randint(60, SCREEN_WIDTH - LevelBuilder.BW - 60), random.randint(60, 220))

    def perform_paddle_swing(self, direction: int):
        """
        direction == -1: Left click (left side swings up, reflects ball right)
        direction == 1: Right click (right side swings up, reflects ball left)
        """
        self.paddle.swing_dir = direction
        self.paddle.swing_timer = self.paddle.swing_duration
        self.audio.play('hit_paddle')

        # Active bat strike: If any ball is in reach of the swing, hit it immediately!
        for ball in self.balls:
            if not ball.alive or ball.attached:
                continue
            if (self.paddle.x - 14 <= ball.x <= self.paddle.x + self.paddle.width + 14 and
                self.paddle.y - 34 <= ball.y <= self.paddle.y + self.paddle.HEIGHT + 10):
                rel_offset = (ball.x - (self.paddle.x + self.paddle.width / 2.0)) / (self.paddle.width / 2.0)
                rel_offset = max(-0.85, min(0.85, rel_offset))
                max_angle = math.radians(62.0)
                bounce_angle = rel_offset * max_angle

                # Directional Batting:
                # Left Click (direction == -1): Left side tilts up, GUARANTEED bounce to the RIGHT (> 0)
                # Right Click (direction == 1): Right side tilts up, GUARANTEED bounce to the LEFT (< 0)
                if direction == -1:
                    deg = 46.0 - rel_offset * 14.0
                    deg = min(66.0, max(28.0, deg))
                    bounce_angle = math.radians(deg)
                    txt = "RIGHT SMASH! >>"
                else:
                    deg = 46.0 + rel_offset * 14.0
                    deg = min(66.0, max(28.0, deg))
                    bounce_angle = -math.radians(deg)
                    txt = "<< LEFT SMASH!"
                ball.target_speed = ball.base_speed * 1.35
                ball.is_smashed = True
                ball.y = self.paddle.y - ball.RADIUS - 2
                ball.vx = ball.target_speed * math.sin(bounce_angle)
                ball.vy = -abs(ball.target_speed * math.cos(bounce_angle))
                self.particles.add_floating_text(txt, ball.x, ball.y - 15, COLOR_NEON_YELLOW, self.font_medium)
                self.particles.spawn_paddle_sparks(ball.x, ball.y, count=18)

    def detonate_bomb_at(self, target_x: int, target_y: int):
        """Detonates a tactical bomb blasting a 3x3 brick area (approx 180x66 px)."""
        if self.bomb_charges <= 0:
            return

        box_w = LevelBuilder.BW * 3 + LevelBuilder.PAD_X * 2  # 180 px
        box_h = LevelBuilder.BH * 3 + LevelBuilder.PAD_Y * 2  # 66 px
        blast_rect = pygame.Rect(target_x - box_w // 2, target_y - box_h // 2, box_w, box_h)

        destroyed_count = 0
        for b in self.bricks:
            if b.is_alive and not b.is_unbreakable and blast_rect.colliderect(b.rect):
                b.hp = 0
                destroyed_count += 1
                points = 100 * (1 if b.btype == BrickType.STANDARD else 2)
                self.score[0] += points
                self.particles.spawn_brick_burst(b.rect.centerx, b.rect.centery, COLOR_NEON_YELLOW, count=16)

        self.audio.play('bomb_blast')
        self.particles.spawn_paddle_sparks(target_x, target_y, count=30)
        self.particles.add_floating_text(
            f"3x3 BLAST! ({destroyed_count} CRUSHED)",
            target_x, target_y - 20, (255, 50, 50), self.font_large
        )

        self.bomb_charges -= 1
        self.check_level_completion()

    # ==========================================================================
    # RENDER LOOP & HUD
    # ==========================================================================
    def draw_background_grid(self):
        self.screen.fill(COLOR_BG_DARK)
        # Synthwave Grid lines
        for y in range(int(self.grid_scroll) + HUD_HEIGHT, SCREEN_HEIGHT, 30):
            pygame.draw.line(self.screen, COLOR_BG_GRID, (0, y), (SCREEN_WIDTH, y), 1)
        for x in range(0, SCREEN_WIDTH, 40):
            pygame.draw.line(self.screen, COLOR_BG_GRID, (x, HUD_HEIGHT), (x, SCREEN_HEIGHT), 1)

    def draw_hud(self):
        # Top HUD Bar Container
        hud_rect = pygame.Rect(0, 0, SCREEN_WIDTH, HUD_HEIGHT)
        pygame.draw.rect(self.screen, COLOR_HUD_BG, hud_rect)
        pygame.draw.line(self.screen, COLOR_HUD_LINE, (0, HUD_HEIGHT), (SCREEN_WIDTH, HUD_HEIGHT), 2)

        # Score & High Score & Level & Speed
        score_str = f"SCORE: {self.score[0]:06d}"
        high_str = f"HIGH: {max(self.high_score_mgr.high_score, self.score[0]):06d}"
        lvl_str = f"LVL: {self.current_level:02d}/{self.TOTAL_LEVELS}"
        spd_str = f"SPD: {self.speed_multiplier:.1f}x"

        s_surf = self.font_medium.render(score_str, True, COLOR_NEON_YELLOW)
        h_surf = self.font_medium.render(high_str, True, COLOR_NEON_CYAN)
        l_surf = self.font_medium.render(lvl_str, True, COLOR_NEON_MAGENTA)
        sp_surf = self.font_medium.render(spd_str, True, COLOR_NEON_GREEN if self.speed_multiplier >= 1.0 else COLOR_WHITE)

        self.screen.blit(s_surf, (12, 12))
        self.screen.blit(h_surf, (175, 12))
        self.screen.blit(l_surf, (330, 12))
        self.screen.blit(sp_surf, (430, 12))

        # Powerup Badges (Bomb, Gun, Shield)
        badge_x = 496
        if self.bomb_charges > 0:
            bomb_str = f"BOMB x{self.bomb_charges}"
            b_surf = self.font_small.render(bomb_str, True, (255, 60, 60))
            pygame.draw.rect(self.screen, (60, 15, 20), (badge_x, 12, 68, 20), border_radius=4)
            pygame.draw.rect(self.screen, (255, 50, 50), (badge_x, 12, 68, 20), 1, border_radius=4)
            self.screen.blit(b_surf, (badge_x + 5, 16))
            badge_x -= 74

        if getattr(self.paddle, 'gun_timer', 0.0) > 0.0 and getattr(self.paddle, 'gun_ammo', 0) > 0:
            gun_str = f"GUN x{self.paddle.gun_ammo} ({self.paddle.gun_timer:.1f}s)"
            g_surf = self.font_small.render(gun_str, True, (255, 140, 60))
            gw = g_surf.get_width() + 10
            gx = badge_x - gw + 68
            pygame.draw.rect(self.screen, (50, 20, 10), (gx, 12, gw, 20), border_radius=4)
            pygame.draw.rect(self.screen, (255, 100, 50), (gx, 12, gw, 20), 1, border_radius=4)
            self.screen.blit(g_surf, (gx + 5, 16))
            badge_x = gx - 6

        if getattr(self.paddle, 'fire_shield_timer', 0.0) > 0.0:
            sh_str = f"SHIELD ({self.paddle.fire_shield_timer:.1f}s)"
            sh_surf = self.font_small.render(sh_str, True, (0, 230, 255))
            sw = sh_surf.get_width() + 10
            sx = badge_x - sw + 68
            pygame.draw.rect(self.screen, (10, 25, 45), (sx, 12, sw, 20), border_radius=4)
            pygame.draw.rect(self.screen, (0, 200, 255), (sx, 12, sw, 20), 1, border_radius=4)
            self.screen.blit(sh_surf, (sx + 5, 16))

        # Lives Icons (Supports unlimited lives)
        lx = 574
        lbl_lives = self.font_small.render("LIVES:", True, COLOR_WHITE)
        self.screen.blit(lbl_lives, (lx, 16))
        lx += 48
        if self.lives <= 5:
            for i in range(self.lives):
                mini_pad = pygame.Rect(lx + i * 16, 16, 13, 8)
                pygame.draw.rect(self.screen, COLOR_NEON_GREEN, mini_pad, border_radius=2)
        else:
            mini_pad = pygame.Rect(lx, 16, 13, 8)
            pygame.draw.rect(self.screen, COLOR_NEON_GREEN, mini_pad, border_radius=2)
            cnt_txt = self.font_medium.render(f"x{self.lives}", True, COLOR_NEON_GREEN)
            self.screen.blit(cnt_txt, (lx + 18, 12))

        # Extended / Giga Paddle Duration Gauge (HUD bar)
        if self.paddle.is_extended and self.paddle.extended_timer > 0.0:
            gauge_w = 60
            gauge_h = 8
            gx = SCREEN_WIDTH - gauge_w - 12
            gy = 18
            ratio = self.paddle.extended_timer / EXTENDED_PADDLE_DUR
            fill_w = max(0, int(gauge_w * ratio))
            gauge_col = COLOR_WHITE if self.paddle.is_giga else COLOR_NEON_CYAN
            lbl_title = "GIGA" if self.paddle.is_giga else "WIDE"
            pygame.draw.rect(self.screen, COLOR_GRAY, (gx, gy, gauge_w, gauge_h), 1, border_radius=2)
            pygame.draw.rect(self.screen, gauge_col, (gx, gy, fill_w, gauge_h), border_radius=2)
            timer_txt = self.font_small.render(f"{lbl_title} {self.paddle.extended_timer:04.1f}s", True, gauge_col)
            self.screen.blit(timer_txt, (gx - 74, 14))

    def _draw_bomb_reticle(self):
        """Renders 3x3 tactical targeting crosshair when bomb charge is armed."""
        if self.bomb_charges <= 0 or self.state != GameState.PLAYING:
            return
        mx, my = pygame.mouse.get_pos()
        if my < HUD_HEIGHT + 10 or my > self.paddle.y + 10:
            return

        box_w = LevelBuilder.BW * 3 + LevelBuilder.PAD_X * 2
        box_h = LevelBuilder.BH * 3 + LevelBuilder.PAD_Y * 2
        rx = mx - box_w // 2
        ry = my - box_h // 2

        # Translucent red overlay
        ret_surf = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        pulse = (math.sin(time.time() * 10.0) + 1.0) / 2.0
        alpha = int(40 + 35 * pulse)
        ret_surf.fill((255, 30, 60, alpha))
        self.screen.blit(ret_surf, (rx, ry))

        # 3x3 Grid outlines
        border_col = (255, int(50 + 100 * pulse), 50)
        pygame.draw.rect(self.screen, border_col, (rx, ry, box_w, box_h), 2, border_radius=4)

        # Inner division lines for 3x3
        c1_x = rx + LevelBuilder.BW + LevelBuilder.PAD_X // 2
        c2_x = rx + (LevelBuilder.BW + LevelBuilder.PAD_X) * 2 - LevelBuilder.PAD_X // 2
        r1_y = ry + LevelBuilder.BH + LevelBuilder.PAD_Y // 2
        r2_y = ry + (LevelBuilder.BH + LevelBuilder.PAD_Y) * 2 - LevelBuilder.PAD_Y // 2
        pygame.draw.line(self.screen, (255, 120, 120), (c1_x, ry), (c1_x, ry + box_h), 1)
        pygame.draw.line(self.screen, (255, 120, 120), (c2_x, ry), (c2_x, ry + box_h), 1)
        pygame.draw.line(self.screen, (255, 120, 120), (rx, r1_y), (rx + box_w, r1_y), 1)
        pygame.draw.line(self.screen, (255, 120, 120), (rx, r2_y), (rx + box_w, r2_y), 1)

        # Crosshair center tick
        pygame.draw.circle(self.screen, COLOR_WHITE, (mx, my), 3)

        # Reticle banner text
        txt = self.font_small.render(f"3x3 TACTICAL BOMB ({self.bomb_charges}) - CLICK TO BLAST", True, (255, 90, 90))
        t_y = ry - 14 if ry - 14 > HUD_HEIGHT else ry + box_h + 4
        self.screen.blit(txt, txt.get_rect(center=(mx, t_y)))

    def _draw_rainbow_beam(self):
        """Renders radiant rainbow energy beam during brick regeneration in level 20."""
        if not self.rainbow_beam:
            return
        p1, p2, _ = self.rainbow_beam
        t = time.time() * 12.0
        r = int((math.sin(t) + 1.0) * 127.5)
        g = int((math.sin(t + 2.094) + 1.0) * 127.5)
        b = int((math.sin(t + 4.188) + 1.0) * 127.5)
        pygame.draw.line(self.screen, (r // 2, g // 2, b // 2), p1, p2, 6)
        pygame.draw.line(self.screen, (r, g, b), p1, p2, 3)
        pygame.draw.line(self.screen, COLOR_WHITE, p1, p2, 1)

    def draw(self):
        self.draw_background_grid()

        # Bricks
        for brick in self.bricks:
            brick.draw(self.screen)

        # Rainbow Beam Effect
        self._draw_rainbow_beam()

        # Hazard Bottles (Levels 19 & 20)
        for bottle in self.hazard_bottles:
            bottle.draw(self.screen, self.font_small)

        # Power-ups
        for p in self.powerups:
            p.draw(self.screen, self.font_small)
        for b in getattr(self, 'bullets', []):
            b.draw(self.screen)

        # Paddle
        if self.state in (GameState.READY, GameState.PLAYING, GameState.STAGE_CLEAR):
            self.paddle.draw(self.screen)

        # Balls
        for ball in self.balls:
            ball.draw(self.screen)

        # 3x3 Bomb Reticle Crosshair
        self._draw_bomb_reticle()

        # Particles & Floating Text
        self.particles.draw(self.screen)

        # Top HUD
        self.draw_hud()

        # Touch Controls (Faint on-screen corner buttons for mobile)
        self._draw_touch_controls()

        # State Specific Overlays
        if self.state == GameState.START:
            self._draw_start_screen()
        elif self.state == GameState.READY:
            self._draw_ready_prompt()
        elif self.state == GameState.STAGE_CLEAR:
            self._draw_stage_clear_banner()
        elif self.state == GameState.GAME_OVER:
            self._draw_game_over_screen()
        elif self.state == GameState.VICTORY:
            self._draw_victory_screen()
        elif self.state == GameState.PAUSED:
            self._draw_pause_overlay()

        pygame.display.flip()

    # ==========================================================================
    # OVERLAYS & SCREENS
    # ==========================================================================
    def _draw_start_screen(self):
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((5, 5, 15, 210))
        self.screen.blit(overlay, (0, 0))

        title = self.font_title.render("CYBER BREAKOUT", True, COLOR_NEON_CYAN)
        t_rect = title.get_rect(center=(SCREEN_WIDTH // 2, 170))
        self.screen.blit(title, t_rect)

        sub = self.font_medium.render("20-STAGE NEON ARCADIA", True, COLOR_NEON_MAGENTA)
        s_rect = sub.get_rect(center=(SCREEN_WIDTH // 2, 225))
        self.screen.blit(sub, s_rect)

        # Controls instructions
        c1 = self.font_small.render("[MOUSE] Move Paddle  |  [LEFT CLICK / SPACE] Launch Ball", True, COLOR_WHITE)
        c2 = self.font_small.render("[A / D / ARROWS] Move  |  [P] Pause  |  [+ / -] Speed  |  [N / B] Skip Stages", True, COLOR_WHITE)
        c3 = self.font_small.render("[LEFT CLICK] Detonate 3x3 Tactical Bomb (when armed)", True, (255, 120, 120))
        self.screen.blit(c1, c1.get_rect(center=(SCREEN_WIDTH // 2, 295)))
        self.screen.blit(c2, c2.get_rect(center=(SCREEN_WIDTH // 2, 320)))
        self.screen.blit(c3, c3.get_rect(center=(SCREEN_WIDTH // 2, 345)))

        # Powerups info
        p1 = self.font_small.render("POWER-UPS: [x2, x10, x100] MULTI-BALL | [PIERCE] | [WIDE/GIGA] PADDLE", True, COLOR_NEON_YELLOW)
        p2 = self.font_small.render("[+LIFE] UNLIMITED EXTRA LIVES | [BOMB] 3x3 TACTICAL DEMOLITION", True, COLOR_NEON_CYAN)
        self.screen.blit(p1, p1.get_rect(center=(SCREEN_WIDTH // 2, 385)))
        self.screen.blit(p2, p2.get_rect(center=(SCREEN_WIDTH // 2, 410)))

        # Start prompt with pulsing glow
        pulse = (math.sin(time.time() * 5.0) + 1.0) / 2.0
        prompt_color = (
            int(COLOR_NEON_GREEN[0] * pulse + 100 * (1 - pulse)),
            int(COLOR_NEON_GREEN[1] * pulse + 100 * (1 - pulse)),
            int(COLOR_NEON_GREEN[2] * pulse + 100 * (1 - pulse))
        )
        prompt = self.font_large.render("PRESS SPACE OR CLICK TO START", True, prompt_color)
        self.screen.blit(prompt, prompt.get_rect(center=(SCREEN_WIDTH // 2, 460)))

    def _draw_ready_prompt(self):
        pulse = (math.sin(time.time() * 6.0) + 1.0) / 2.0
        col = (
            int(COLOR_NEON_YELLOW[0] * pulse + 120 * (1 - pulse)),
            int(COLOR_NEON_YELLOW[1] * pulse + 120 * (1 - pulse)),
            int(COLOR_NEON_YELLOW[2] * pulse + 120 * (1 - pulse))
        )
        prompt = self.font_medium.render("CLICK OR PRESS SPACE TO LAUNCH", True, col)
        self.screen.blit(prompt, prompt.get_rect(center=(SCREEN_WIDTH // 2, 490)))

    def _draw_stage_clear_banner(self):
        overlay = pygame.Surface((SCREEN_WIDTH, 90), pygame.SRCALPHA)
        overlay.fill((10, 15, 30, 220))
        self.screen.blit(overlay, (0, SCREEN_HEIGHT // 2 - 45))
        pygame.draw.line(self.screen, COLOR_NEON_CYAN, (0, SCREEN_HEIGHT // 2 - 45), (SCREEN_WIDTH, SCREEN_HEIGHT // 2 - 45), 2)
        pygame.draw.line(self.screen, COLOR_NEON_CYAN, (0, SCREEN_HEIGHT // 2 + 45), (SCREEN_WIDTH, SCREEN_HEIGHT // 2 + 45), 2)

        txt = self.font_large.render(f"STAGE {self.current_level} INITIALIZED", True, COLOR_NEON_YELLOW)
        self.screen.blit(txt, txt.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)))

    def _draw_game_over_screen(self):
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((15, 5, 10, 225))
        self.screen.blit(overlay, (0, 0))

        go_txt = self.font_title.render("GAME OVER", True, (255, 40, 40))
        self.screen.blit(go_txt, go_txt.get_rect(center=(SCREEN_WIDTH // 2, 190)))

        score_txt = self.font_large.render(f"FINAL SCORE: {self.score[0]:,}", True, COLOR_WHITE)
        self.screen.blit(score_txt, score_txt.get_rect(center=(SCREEN_WIDTH // 2, 260)))

        if self.is_new_high_score:
            rec_txt = self.font_medium.render("*** NEW HIGH SCORE RECORD! ***", True, COLOR_NEON_YELLOW)
            self.screen.blit(rec_txt, rec_txt.get_rect(center=(SCREEN_WIDTH // 2, 310)))
        else:
            high_txt = self.font_medium.render(f"HIGH SCORE: {self.high_score_mgr.high_score:,}", True, COLOR_GRAY)
            self.screen.blit(high_txt, high_txt.get_rect(center=(SCREEN_WIDTH // 2, 310)))

        retry_txt = self.font_medium.render("PRESS SPACE OR CLICK TO PLAY AGAIN", True, COLOR_NEON_CYAN)
        self.screen.blit(retry_txt, retry_txt.get_rect(center=(SCREEN_WIDTH // 2, 410)))

    def _draw_victory_screen(self):
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((5, 20, 15, 230))
        self.screen.blit(overlay, (0, 0))

        vic_txt = self.font_title.render("CYBER CHAMPION!", True, COLOR_NEON_GREEN)
        self.screen.blit(vic_txt, vic_txt.get_rect(center=(SCREEN_WIDTH // 2, 180)))

        sub_txt = self.font_large.render("ALL 20 LEVELS CONQUERED!", True, COLOR_NEON_YELLOW)
        self.screen.blit(sub_txt, sub_txt.get_rect(center=(SCREEN_WIDTH // 2, 240)))

        score_txt = self.font_large.render(f"FINAL SCORE: {self.score[0]:,}", True, COLOR_WHITE)
        self.screen.blit(score_txt, score_txt.get_rect(center=(SCREEN_WIDTH // 2, 300)))

        retry_txt = self.font_medium.render("PRESS SPACE TO RETURN TO CYBERSPACE", True, COLOR_NEON_CYAN)
        self.screen.blit(retry_txt, retry_txt.get_rect(center=(SCREEN_WIDTH // 2, 420)))

    def _draw_pause_overlay(self):
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))
        txt = self.font_title.render("PAUSED", True, COLOR_WHITE)
        self.screen.blit(txt, txt.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)))
        sub = self.font_medium.render("PRESS P TO RESUME", True, COLOR_NEON_CYAN)
        self.screen.blit(sub, sub.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 50)))

    def _draw_touch_controls(self):
        """
        Renders faint, translucent cyber on-screen touch buttons in the top-left
        and top-right corners for mobile play.
        - Normal: Left Tilt / Swing (deflects Right) and Right Tilt / Swing (deflects Left)
        - Gun Power-Up Active: Transforms both buttons into Blaster FIRE triggers with ammo gauge.
        """
        if self.state not in (GameState.READY, GameState.PLAYING):
            return

        gun_active = getattr(self.paddle, 'gun_timer', 0.0) > 0.0 and getattr(self.paddle, 'gun_ammo', 0) > 0
        ammo = getattr(self.paddle, 'gun_ammo', 0)

        # Subtle pulsing glow
        t = time.time()
        pulse = (math.sin(t * 5.0) + 1.0) / 2.0

        for is_right, rect in ((False, self.btn_left_rect), (True, self.btn_right_rect)):
            btn_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)

            # 1. Background (Faint translucent cyber glass)
            if gun_active:
                bg_alpha = int(45 + 25 * pulse)
                btn_surf.fill((255, 60, 20, bg_alpha))
                border_color = (255, int(120 + 100 * pulse), 40, 160)
            else:
                swing_active = getattr(self.paddle, 'swing_timer', 0.0) > 0.0 and (
                    (self.paddle.swing_dir == 1 if is_right else self.paddle.swing_dir == -1)
                )
                if swing_active:
                    btn_surf.fill((0, 255, 242, 85))
                    border_color = (255, 255, 255, 200)
                else:
                    # Faint translucent cyber glass
                    btn_surf.fill((10, 25, 45, 45))
                    border_color = (0, 255, 242, 75)

            # 2. Cyberpunk frame with rounded corners & corner accent ticks
            pygame.draw.rect(btn_surf, border_color, (0, 0, rect.width, rect.height), 1, border_radius=6)

            c_len = 8
            accent_col = (255, 140, 40) if gun_active else COLOR_NEON_CYAN
            pygame.draw.line(btn_surf, accent_col, (0, 0), (c_len, 0), 2)
            pygame.draw.line(btn_surf, accent_col, (0, 0), (0, c_len), 2)
            pygame.draw.line(btn_surf, accent_col, (rect.width - 1, rect.height - 1), (rect.width - 1 - c_len, rect.height - 1), 2)
            pygame.draw.line(btn_surf, accent_col, (rect.width - 1, rect.height - 1), (rect.width - 1, rect.height - 1 - c_len), 2)

            self.screen.blit(btn_surf, (rect.x, rect.y))

            # 3. Text and Icons rendered crisp
            cx = rect.centerx
            cy = rect.centery

            if gun_active:
                # Blaster Fire Button
                lbl_color = (255, int(150 + 80 * pulse), 60)
                fire_txt = self.font_medium.render("FIRE", True, lbl_color)
                self.screen.blit(fire_txt, fire_txt.get_rect(center=(cx, cy - 9)))

                ammo_txt = self.font_small.render(f"x{ammo}", True, COLOR_NEON_YELLOW)
                self.screen.blit(ammo_txt, ammo_txt.get_rect(center=(cx, cy + 13)))
            else:
                lbl_color = COLOR_WHITE if swing_active else (180, 240, 255)
                if not is_right:
                    t_lbl = self.font_medium.render("SWING", True, lbl_color)
                    self.screen.blit(t_lbl, t_lbl.get_rect(center=(cx, cy - 9)))
                    sub_lbl = self.font_small.render("TILT L", True, COLOR_NEON_CYAN)
                    self.screen.blit(sub_lbl, sub_lbl.get_rect(center=(cx, cy + 13)))
                else:
                    t_lbl = self.font_medium.render("SWING", True, lbl_color)
                    self.screen.blit(t_lbl, t_lbl.get_rect(center=(cx, cy - 9)))
                    sub_lbl = self.font_small.render("TILT R", True, COLOR_NEON_MAGENTA)
                    self.screen.blit(sub_lbl, sub_lbl.get_rect(center=(cx, cy + 13)))

    # ==========================================================================
    # EVENT LOOP & EXECUTION
    # ==========================================================================
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.state == GameState.PLAYING:
                        self.state = GameState.PAUSED
                    elif self.state == GameState.PAUSED:
                        self.state = GameState.PLAYING
                    elif self.state in (GameState.START, GameState.GAME_OVER, GameState.VICTORY):
                        self.running = False

                elif event.key == pygame.K_p:
                    if self.state == GameState.PLAYING:
                        self.state = GameState.PAUSED
                    elif self.state == GameState.PAUSED:
                        self.state = GameState.PLAYING

                elif event.key == pygame.K_SPACE:
                    if self.state == GameState.START:
                        self.start_new_game()
                    elif self.state == GameState.READY:
                        self.launch_ball()
                    elif self.state in (GameState.GAME_OVER, GameState.VICTORY):
                        self.start_new_game()

                elif event.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                    self.adjust_speed(1)

                elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    self.adjust_speed(-1)

                elif event.key == pygame.K_n:
                    # Skip to next level (Dev Key)
                    if self.state in (GameState.PLAYING, GameState.READY, GameState.STAGE_CLEAR):
                        target = min(self.TOTAL_LEVELS, self.current_level + 1)
                        self.load_level(target)
                        self.particles.add_floating_text(
                            f"STAGE ADVANCE -> LEVEL {target}",
                            SCREEN_WIDTH // 2, 260, COLOR_NEON_YELLOW, self.font_large
                        )

                elif event.key == pygame.K_b:
                    # Return to previous level (Dev Key)
                    if self.state in (GameState.PLAYING, GameState.READY, GameState.STAGE_CLEAR):
                        target = max(1, self.current_level - 1)
                        self.load_level(target)
                        self.particles.add_floating_text(
                            f"STAGE PREV -> LEVEL {target}",
                            SCREEN_WIDTH // 2, 260, COLOR_NEON_YELLOW, self.font_large
                        )

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button in (1, 3):
                if self.state == GameState.START:
                    self.start_new_game()
                elif self.state == GameState.READY:
                    self.launch_ball()
                elif self.state == GameState.PLAYING:
                    mx, my = event.pos

                    # Check tactical bomb first
                    if self.bomb_charges > 0 and event.button == 1:
                        if HUD_HEIGHT < my < self.paddle.y - 20:
                            if not self.btn_left_rect.collidepoint(mx, my) and not self.btn_right_rect.collidepoint(mx, my):
                                self.detonate_bomb_at(mx, my)
                                continue

                    # Check touch buttons in top corners:
                    now = time.time()
                    if self.btn_left_rect.collidepoint(mx, my):
                        if now - self._last_corner_action_time > 0.10:
                            self._last_corner_action_time = now
                            if getattr(self.paddle, 'gun_timer', 0.0) > 0.0 and getattr(self.paddle, 'gun_ammo', 0) > 0:
                                self.fire_gun()
                            else:
                                self.perform_paddle_swing(-1)
                        continue

                    if self.btn_right_rect.collidepoint(mx, my):
                        if now - self._last_corner_action_time > 0.10:
                            self._last_corner_action_time = now
                            if getattr(self.paddle, 'gun_timer', 0.0) > 0.0 and getattr(self.paddle, 'gun_ammo', 0) > 0:
                                self.fire_gun()
                            else:
                                self.perform_paddle_swing(1)
                        continue

                    # Gun firing takes priority on Left Click (button 1)
                    if getattr(self.paddle, 'gun_timer', 0.0) > 0.0 and getattr(self.paddle, 'gun_ammo', 0) > 0:
                        if event.button == 1:
                            self.fire_gun()
                            continue

                    # Paddle swing / tilt: Left Click = Left Up (-1), Right Click = Right Up (1)
                    if event.button == 1:
                        self.perform_paddle_swing(-1)
                    elif event.button == 3:
                        self.perform_paddle_swing(1)

                elif self.state in (GameState.GAME_OVER, GameState.VICTORY):
                    self.start_new_game()

            elif event.type == pygame.FINGERDOWN:
                fx = int(event.x * SCREEN_WIDTH)
                fy = int(event.y * SCREEN_HEIGHT)
                if self.state == GameState.START:
                    self.start_new_game()
                elif self.state == GameState.READY:
                    self.launch_ball()
                elif self.state == GameState.PLAYING:
                    now = time.time()
                    if self.btn_left_rect.collidepoint(fx, fy):
                        if now - self._last_corner_action_time > 0.10:
                            self._last_corner_action_time = now
                            if getattr(self.paddle, 'gun_timer', 0.0) > 0.0 and getattr(self.paddle, 'gun_ammo', 0) > 0:
                                self.fire_gun()
                            else:
                                self.perform_paddle_swing(-1)
                    elif self.btn_right_rect.collidepoint(fx, fy):
                        if now - self._last_corner_action_time > 0.10:
                            self._last_corner_action_time = now
                            if getattr(self.paddle, 'gun_timer', 0.0) > 0.0 and getattr(self.paddle, 'gun_ammo', 0) > 0:
                                self.fire_gun()
                            else:
                                self.perform_paddle_swing(1)
                    else:
                        # Touch and drag paddle directly
                        if fy > HUD_HEIGHT + 10:
                            self.paddle.x = fx - (self.paddle.width / 2.0)
                            self.paddle.x = max(0.0, min(SCREEN_WIDTH - self.paddle.width, self.paddle.x))
                            self.paddle.rect.x = int(self.paddle.x)
                elif self.state in (GameState.GAME_OVER, GameState.VICTORY):
                    self.start_new_game()

            elif event.type == pygame.FINGERMOTION:
                fx = int(event.x * SCREEN_WIDTH)
                fy = int(event.y * SCREEN_HEIGHT)
                if self.state in (GameState.READY, GameState.PLAYING):
                    if not self.btn_left_rect.collidepoint(fx, fy) and not self.btn_right_rect.collidepoint(fx, fy):
                        self.paddle.x = fx - (self.paddle.width / 2.0)
                        self.paddle.x = max(0.0, min(SCREEN_WIDTH - self.paddle.width, self.paddle.x))
                        self.paddle.rect.x = int(self.paddle.x)

    def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            dt = min(dt, 0.05)  # Delta clamp to protect against lag spikes
            self.handle_events()
            if self.state != GameState.PAUSED:
                self.update(dt)
            self.draw()

        pygame.quit()
        sys.exit(0)


# ==============================================================================
# 11. ENTRY POINT
# ==============================================================================
if __name__ == "__main__":
    game = BreakoutGame()
    game.run()
