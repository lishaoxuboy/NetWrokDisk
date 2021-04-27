import sys

from PyQt5.Qt import QApplication

import tools
from module import MainWindow, InputWindow, ProgressWindow
from file_socket import run
import time

if __name__ == '__main__':
    # 创建应用
    import sys
    if len(sys.argv) > 1:
        IP = sys.argv[1]
    else:
        IP = "www.lsxboy.top"
        # IP = "127.0.0.1"
    print("IP", IP)
    app = QApplication(sys.argv)
    session = run((IP, 1122), file_group_len=2048, once_recv=2048, enable_ping=False, protocol_len=1024)
    input_window = InputWindow()
    progress = ProgressWindow()
    main_window = MainWindow(tools, session, tools.Dict(input_window=input_window, progress_window=progress))
    session.local_reload = main_window.local_reload_table
    session.show_progress = main_window.show_progress  # 信号槽
    session.hide_progress = main_window.hide_progress
    session.set_status = main_window.set_progress
    progress.on_close = main_window.on_progress_window_close
    main_window.show()
    # 运行应用，并监听事件
    sys.exit(app.exec_())
