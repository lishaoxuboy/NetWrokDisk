import threading
import time
import socket
import tools
"""
实现一个可靠的socket通道，并且它具有一下功能
    改通道具备自己维护通道可用性
    改通道具备传输字节流功能，并保障能保证数据的完整性
    改通道具备接受字节流功能，并保障能保证数据的完整性
"""


class BaseSocket:
    """
    接受一个socket会话，接收到一组完整的包后调用回掉函数
    """
    def __init__(self, conn, address, callback=None, protocol_len=1024, enable_ping=False, retry_interval=1, ping_interval=3):

        self.conn = conn
        self.conn_online = True
        self.retry_interval = retry_interval
        self.ping_interval = ping_interval
        self.address = address
        self.enable_ping = enable_ping
        self.protocol_len = protocol_len
        self.on_msg = callback
        if enable_ping:
            threading.Thread(target=self.check_conn).start()

    def set_onmsg(self, f):
        self.on_msg = f

    def recv_data_for_every(self):
        """
        改通道具备传输字节流功能，并保障能保证数据的完整性
        """
        def innter(_self):
            print("等待回调函数...")
            while True:
                if _self.on_msg:
                    print("套接字监听已启动...")
                    break
            while _self.conn:
                try:
                    received_data = _self.conn.recv(_self.protocol_len)
                    data_len = len(received_data)
                except ConnectionResetError:
                    print(f"error 与 {_self.address} 断开连接")
                    _self.conn.close()
                    return
                if not data_len:
                    print(f"与 {_self.address} 断开连接")
                    _self.conn.close()
                    return
                while data_len != _self.protocol_len:
                    received_data += _self.conn.recv(_self.protocol_len - data_len)
                    data_len = len(received_data)
                _self.on_msg(received_data)

        threading.Thread(target=innter, args=(self,)).start()

    def recv_once(self, size):
        return self.conn.recv(size)

    def recv_agroup(self, size):
        receive_size = 0
        receive_data = b''
        while not size == receive_size:  # 根据协议内说明的文件大小，循环接收，直到接收完毕
            receive_data += self.conn.recv(size - receive_size)
            receive_size = len(receive_data)
        return receive_data

    def get_conn(self):
        while True:
            try:
                self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.conn.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.conn.connect(self.address)
                self.conn_online = True
                print(f"Socket连接成功")
                if self.enable_ping:
                    threading.Thread(target=self.ping).start()
                    print("Ping已启动")
                return self.conn
            except Exception as e:
                print(f"连接socket失败 {str(e)}")
                time.sleep(self.retry_interval)

    def send_all(self, data):
        try:
            self.conn.sendall(data)
            return True
        except Exception as e:
            print(f"sendall error {str(e)}")
            return False

    def ping(self):
        while True:
            ping_data = tools.jsondumps(dict(code=0, msg='', data=None))
            if len(ping_data) < self.protocol_len:
                ping_data = tools.padding_data(ping_data, self.protocol_len - len(ping_data))
            success = self.send_all(ping_data)
            if not success:
                self.conn_online = False
                return True
            time.sleep(self.ping_interval)

    def check_conn(self):
        """
        断线重连
        """
        while True:
            while self.conn_online:
                while True:
                    if not self.conn_online:
                        print("检查到断线，准备重连")
                        self.get_conn()
