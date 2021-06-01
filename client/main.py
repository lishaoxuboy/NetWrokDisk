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
    # 服务器的IP Port
    ip = sys.argv[1] if len(sys.argv) > 1 else "www.lsxboy.com"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 1123

    # 协议的长度（不用于文件流的传送）
    p_len = 1024

    # 下载的时候一次接受多少字节
    once_recv_btyes = 10240

    # 发送文件的时候一次读多少字节
    once_recv_file_bytes = 10240

    # 创建socket核心
    Session = create_socket((ip, port), protocol_len=p_len)

    # 控制类（根据协议实作出响应）
    remote_handler = Handler(Session, FileIO, p_len, once_recv_file_bytes, once_recv_btyes)

    # 注册session的响应类
    Session.on_msg = remote_handler.on_msg

    # 启动session监听
    Session.recv_data_for_every()

    # 实例主窗口的子组件（交互输入框、进度展示界面）
    input_window = InputWindow()
    progress = ProgressWindow()

    # 实例化主窗口（文件窗口的主窗口）
    main_window = MainWindow(local_handler, remote_handler, local_handler.Dict(input_window=input_window, progress_window=progress))

    # 注册控制类的回调函数
    remote_handler.local_reload = main_window.local_reload_table
    remote_handler.show_progress = main_window.show_progress  # 信号槽
    remote_handler.hide_progress = main_window.hide_progress
    remote_handler.set_status = main_window.set_progress

    # 注册进度条关闭的时间
    progress.on_close = main_window.on_progress_window_close

    # 显示主窗口
    main_window.show()
    # 运行应用，并监听事件
    sys.exit(app.exec_())
