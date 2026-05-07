# -*- coding: utf-8 -*-
"""Windowed launcher with a splash screen and startup error dialog."""

import os
import threading
import traceback

from javax.swing import (
    BorderFactory, ImageIcon, JLabel, JOptionPane, JScrollPane, JTextArea,
    JWindow, SwingUtilities, Timer
)
from java.awt import Color, Dimension
from java.lang import System


SPLASH_FILE = 'splash.png'
SPLASH_MIN_MILLIS = 1200


def show_startup_error(message):
    area = JTextArea(message)
    area.setEditable(False)
    area.setLineWrap(False)
    scroll = JScrollPane(area)
    scroll.setPreferredSize(Dimension(900, 420))
    JOptionPane.showMessageDialog(
        None,
        scroll,
        "HL7 Transform startup error",
        JOptionPane.ERROR_MESSAGE
    )


def splash_path():
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        base_dir = System.getProperty('user.dir')
    return os.path.join(base_dir, SPLASH_FILE)


def create_splash():
    path = splash_path()
    if not os.path.exists(path):
        return None

    window = JWindow()
    label = JLabel(ImageIcon(path))
    label.setBorder(BorderFactory.createLineBorder(Color(42, 166, 151), 1))
    window.getContentPane().add(label)
    window.pack()
    window.setLocationRelativeTo(None)
    window.setAlwaysOnTop(True)
    return window


def close_splash(splash):
    if splash is not None:
        splash.setVisible(False)
        splash.dispose()


def start_gui_after_splash(splash, started_at):
    def show_frame():
        try:
            from hl7_transform_gui import HL7TransformGUI
            frame = HL7TransformGUI()
            frame.setVisible(True)
            close_splash(splash)
        except Exception:
            close_splash(splash)
            show_startup_error(traceback.format_exc())

    elapsed = System.currentTimeMillis() - started_at
    delay = max(0, SPLASH_MIN_MILLIS - elapsed)
    if delay:
        timer = Timer(delay, lambda event: show_frame())
        timer.setRepeats(False)
        timer.start()
    else:
        show_frame()


def load_gui_in_background(splash, started_at):
    try:
        import hl7_transform_gui
        SwingUtilities.invokeLater(lambda: start_gui_after_splash(splash, started_at))
    except Exception:
        error = traceback.format_exc()
        def show_error():
            close_splash(splash)
            show_startup_error(error)
        SwingUtilities.invokeLater(show_error)


def start_launcher():
    try:
        splash = create_splash()
        started_at = System.currentTimeMillis()
        if splash is not None:
            splash.setVisible(True)

        worker = threading.Thread(target=lambda: load_gui_in_background(splash, started_at))
        worker.setDaemon(True)
        worker.start()
    except Exception:
        show_startup_error(traceback.format_exc())


if __name__ == '__main__':
    SwingUtilities.invokeLater(start_launcher)
