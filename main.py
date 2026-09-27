#!/usr/bin/env python3
"""
================================================================================
CYBERPUNK BREAKOUT (CASSE-BRIQUE)
Android / Desktop Application Entry Point
================================================================================
"""
import sys
import os

# Suppress Pygame welcome message
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'

# Import game engine
from breakout_game import BreakoutGame

def main():
    game = BreakoutGame()
    game.run()

if __name__ == '__main__':
    main()
