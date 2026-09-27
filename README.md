# 🕹️ Cyberpunk Breakout (Casse-Brique)

A feature-complete, modern retro Cyberpunk Breakout arcade engine developed in Python & Pygame, fully ready for both **Desktop (PC/Mac/Linux)** and **Mobile (Android APK)** with automated cloud building via GitHub Actions.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)
![Pygame-CE](https://img.shields.io/badge/Engine-Pygame--CE%202.5%2B-green)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20Android-orange)
![Build](https://img.shields.io/badge/Android%20Build-GitHub%20Actions-brightgreen?logo=githubactions)

---

## 🌟 Key Features

- **20 Handcrafted Escalating Levels**: Progressing from basic warmup neon grids to moving conveyors, orbital wings, iron sentinels, and the ultimate Citadel Nexus.
- **360° Omnidirectional 100-Ball Supernova (`x100`)**: Spawns up to 100 balls radiating radially outward across all 360 degrees from existing active balls.
- **Giga Full-Screen Paddle (`GIGA`)**: Expands the paddle across the full 800px display width with real-time countdown timer.
- **Tactical 3x3 Bomb Blast (`BOMB`)**: Tactical targeting reticle detonating a 9-brick blast radius with deep procedural audio shockwave.
- **Permanent Industrial Scenery Barriers**: Unmistakable hazard-caution barriers (`/// /// ///`) that deflect balls, scale progressively from Level 3 to 20 (up to 26 barriers in Level 20), and form anti-supernova blast shields.
- **Level 20 Rainbow Regenerator & Matrix Shuffling**: Dynamic playfield mechanics keeping gameplay fast and unpredictable.
- **Lethal Falling Hazard Bottles**: Biohazard bottles drop periodically—dodge them with your paddle or shatter them with your ball for +500 pts!
- **100% Procedural Sound Synthesizer**: No external audio files required. All sfx (laser chimes, iron thuds, victory fanfares, explosions) are synthesized in real-time math waveforms.
- **Cross-Platform Responsive Controls**:
  - **PC**: Dual Mouse Follower + Smooth Keyboard (`A`/`D` or Arrow Keys).
  - **Android**: Single-finger drag touch steering + tap to launch.

---

## 🚀 How to Play on PC (Desktop)

### Requirements
- Python 3.10+
- `pygame-ce` (or `pygame`)

### Quick Start
```bash
pip install pygame-ce
python main.py
```

### Controls (PC)
| Key / Input | Action |
| :--- | :--- |
| **Mouse Move** | Steer paddle smoothly |
| **Left Click** | Launch attached ball / Detonate Tactical 3x3 Bomb |
| **A / D** or **Left / Right Arrow** | Steer paddle via keyboard |
| **Spacebar** | Launch ball / Start game / Play again |
| **P** | Pause / Resume |
| **+ / -** | Adjust game speed multiplier (0.5x to 4.0x) |
| **N / B** | Developer stage skip (Next / Previous level) |

---

## 📱 How to Get the Android APK (Automated via GitHub)

This repository includes `.github/workflows/build_apk.yml`. Whenever you push code to this repository:
1. GitHub Actions automatically spins up an Ubuntu runner.
2. Uses **Buildozer** to compile a standalone Android `.apk` package.
3. Once completed (green checkmark in the **Actions** tab), download `CyberBreakout-APK` from the **Artifacts** section and install it directly on your Android device!

---

## 📁 Repository Structure

```text
├── main.py                     # Android / Desktop entry point
├── breakout_game.py            # Complete self-contained Cyberpunk Breakout engine
├── buildozer.spec              # Android packaging & build configuration
├── .gitignore                  # Python & build artifact exclusions
├── .github/
│   └── workflows/
│       └── build_apk.yml       # Automated GitHub Actions APK builder
└── README.md                   # Project documentation
```

---

## 📄 License
MIT License. Free to learn, modify, and build upon.
