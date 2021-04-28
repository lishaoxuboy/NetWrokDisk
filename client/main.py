import sys

from PyQt5.Qt import QApplication

import tools as local_handler
from module import MainWindow, InputWindow, ProgressWindow
from file_socket import Handler, FileIO
from base_socket import BaseSocket
import sys
import socket


def create_socket(addr, protocol_len):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.connect(addr)
    print(f"与 {addr} 连接成功")
    return BaseSocket(s, addr, protocol_len)

    
    
if __name__ == '__main__':
    app = QApplication(sys.argv)
    # 启动变量
    ip = sys.argv[1] if len(sys.argv) > 1 else "www.lsxboy.top"
    port = 1122
    p_len = 1024
    once_recv_btyes = 2048
    once_recv_file_bytes = 10240
    # 创建socket核心
    Session = create_socket((ip, port), protocol_len=p_len)
    # 控制类（根据协议实作出响应）
    remote_handler = Handler(Session, FileIO, p_len, once_recv_file_bytes, once_recv_btyes)
    Session.on_msg = remote_handler.on_msg
    # 线程
    Session.recv_data_for_every()
    # 实例化子组件
    input_window = InputWindow()
    progress = ProgressWindow()
    # 实例化主窗口
    main_window = MainWindow(local_handler, remote_handler, local_handler.Dict(input_window=input_window, progress_window=progress))
    # 注册服务端功能
    remote_handler.local_reload = main_window.local_reload_table
    remote_handler.show_progress = main_window.show_progress  # 信号槽
    remote_handler.hide_progress = main_window.hide_progress
    remote_handler.set_status = main_window.set_progress
    progress.on_close = main_window.on_progress_window_close
    main_window.show()
    # 运行应用，并监听事件
    sys.exit(app.exec_())
