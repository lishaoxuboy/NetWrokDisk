from PyQt5.QtCore import QProcess, QTimer
from functools import partial
import time

def started():
    print("1111")

def dataReady(*args):
    print(args)

def finished(*args):
    print(args)

import os
os.chdir(r"C:\Program Files\NetWorkDisk")
command = "main.exe"
Q = QProcess()
# mpvplayer.setProcessChannelMode(QProcess.MergedChannels)
# mpvplayer.started.connect(started)
# mpvplayer.readyReadStandardOutput.connect(partial(dataReady, mpvplayer))
# mpvplayer.finished.connect(finished)
# QTimer.singleShot(1000, partial(mpvplayer.start, command))
Q.start(command)
while True:
    pass

