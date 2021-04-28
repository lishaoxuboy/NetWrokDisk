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
    def __init__(self, conn, address, protocol_len, enable_ping=False, retry_interval=1, ping_interval=3):

        self.conn = conn
        self.conn_online = True
        self.retry_interval = retry_interval
        self.ping_interval = ping_interval
        self.address = address
        self.enable_ping = enable_ping
        self.protocol_len = protocol_len
        self.on_msg = None
        if enable_ping:
            threading.Thread(target=self.check_conn).start()
            threading.Thread(target=self.ping).start()

    def set_onmsg(self, f):
        self.on_msg = f

    def recv_data_for_every(self):
        """
        改通道具备传输字节流功能，并保障能保证数据的完整性
        """
        def innter(self_):
            print("等待回调函数...")
            while True:
                if self.on_msg:
                    print("套接字监听已启动...")
                    break
            while self.conn:
                try:
                    if not self.protocol_len:
                        raise ("必须指定接收数据的长度",)
                    received_data = self.conn.recv(self.protocol_len)
                    # print("innter  1111", received_data)
                    data_len = len(received_data)
                except ConnectionResetError:
                    print(f"error 与 {self.address} 断开连接")
                    self.conn.close()
                    return
                if data_len == 0:
                    print(f"与 {self.address} 断开连接")
                    self.conn.close()
                    return
                if self.protocol_len:
                    while data_len < self.protocol_len:
                        received_data += self.conn.recv(self.protocol_len - data_len)
                        data_len = len(received_data)
                self.on_msg(received_data)

        threading.Thread(target=innter, args=(self,)).start()

    def recv_once(self, size):
        recv_size = int()
        recv_data = b''
        while size != recv_size:
            recv_data += self.conn.recv(size - recv_size)
            recv_size = len(recv_data)
        return recv_data

    def recv_agroup(self, size):
        receive_size = 0
        receive_data = b''
        while not size == receive_size:  # 根据协议内说明的文件大小，循环接收，直到接收完毕
            try:
                receive_data += self.conn.recv(size - receive_size)
                # print("recv_agroup", receive_data)
            except ValueError as e:
                print(e)
            receive_size = len(receive_data)
        return receive_data

    def get_conn(self):
        while True:
            try:
                self.conn = None
                self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.conn.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.conn.connect(self.address)
                self.conn_online = True
                print(f"Socket连接成功")
                if self.enable_ping:
                    threading.Thread(target=self.ping).start()
                    threading.Thread(target=self.recv_data_for_every).start()
                    print("Ping已启动")
                return self.conn
            except Exception as e:
                print(f"连接socket失败 {str(e)}")
                time.sleep(self.retry_interval)

    def send_all(self, data):
        while True:
            if self.conn_online:
                try:
                    self.conn.sendall(data)
                    return True
                except Exception as e:
                    print(f"sendall error {str(e)}")
                    time.sleep(1)

    def ping(self):
        """
        控制  self.conn_online 的状态
        """
        while True:
            if self.conn_online:
                ping_data = tools.jsondumps(dict(code=0, msg='', data=None))
                if len(ping_data) < self.protocol_len:
                    ping_data = tools.padding_data(ping_data, self.protocol_len - len(ping_data))
                try:
                    self.conn.sendall(ping_data)
                except Exception as e:
                    print("检查到断线" ,e)
                    self.conn.close()
                    self.conn_online = False
                    return True
                time.sleep(self.ping_interval)

    def check_conn(self):
        """
        根据  self.conn_online 的状态判断是否重连
        """
        while True:
            time.sleep(0.1)
            if self.conn_online:    # 等待连接
                while True: # 等待断线
                    if not self.conn_online:
                        print("准备重连")
                        self.get_conn()
                        break
                    time.sleep(0.1)