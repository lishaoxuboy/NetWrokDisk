import socket
import time
import queue
import sys


from my_public.public import Tools, Protocol, Recv_Len,  MyLog, RecvStream, SendFile, WriteFile, Start_Send, Stop_Send


Log = MyLog("log.txt")
# ip = "www.lsxboy.top"
# ip = "127.0.0.1"
ip = "192.168.1.61"
args = [ip, 8081, 8082]
Log.info(sys.argv)
for index, value in enumerate(sys.argv):
    if index > 0:
        args[index - 1] = value

print(args[0], args[1], args[2])
file_service_ip = (args[0], args[1])
data_service_ip = (args[0], args[2])


class DataSocket:
    def __init__(self):
        self.Uuid = str()                                           # 服务器分配的UUID
        self.Conn = None                                            # 保存连接
        self._connect()                                             # 建立连接
        self.Recv_Size = Recv_Len                                   # 单次接收数据长度
        self.Recv_Data_Queue = queue.Queue()                        # 保存服务器相应的数据， 相关的函数会自动取获取该数据
        RecvStream(self.Conn, self.on_message, self.Recv_Size)      # 管理字节流的类，收到消息解析后，调用回调函数

    def _connect(self):
        """与服务器建立socket"""
        self.Conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        while True:
            try:
                self.Conn.connect(data_service_ip)
                print(f"数据服务连接成功")
                break
            except Exception as e:
                print("数据通道连接失败。。%s" % e)
                time.sleep(1)

    def on_message(self, data):
        """监听服务端发送的消息"""
        Log.info("接收到协议 %d" % data["code"])
        self.Recv_Data_Queue.put(data)

    def get_server_files(self, *args):
        _root, _path, select_item, is_dir_name = args
        protocol = dict(code=Protocol.GetServerFiles)
        data = dict(root=_root, path=_path, item=select_item, is_dir_name=is_dir_name)
        data = Tools.encode(protocol, data)
        self.Conn.sendall(data)
        return self.Recv_Data_Queue.get()

    def get_server_drive(self):
        protocol = dict(code=Protocol.GetServerDrive)
        data = Tools.encode(protocol)
        self.Conn.sendall(data)
        return self.Recv_Data_Queue.get()

    def del_server_item(self, data):
        data = Tools.encode(dict(code=Protocol.OsRemoveItem), data)
        self.Conn.sendall(data)
        return self.Recv_Data_Queue.get()

    def request(self, protocol):
        data = Tools.encode(protocol)
        self.Conn.sendall(data)
        return self.Recv_Data_Queue.get()


class FileSocket:
    """
    主要接收文件相关的通信，并且处理一些简单的功能
    """
    def __init__(self, signal, *args):
        self.Uuid = str()                                               # 服务器分配的UUID
        self.Conn = None                                                # 保存文件通信的SOCKET对象
        self.Progress = None                                            # 进度条对象
        self.Recv_Size = Recv_Len                                       # 每次接收包大小
        self._connect()                                                 # 连接文件传送通道
        self.msg_signal = signal
        # # 发送通道，开始发送文件信号函数，每次发送文件调用信号函数，发送结束调用信号函数
        # self.Conn, self.before_begin_send, self.every_send, self.after_end = args
        self.Send_File = SendFile(self.Conn, True, *args)                                   # 初始化文件发送接收类
        self.Write_File = WriteFile(*args)                                   # 初始化文件发送接收类
        RecvStream(self.Conn, self.on_message, self.Recv_Size)          # 专门管理数据接受，并且回调给处理函数

    def _connect(self):
        """与服务器建立socket"""
        self.Conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        while True:
            try:
                self.Conn.connect(file_service_ip)
                Log.info(f"文件服务连接成功，等待接收uuid....")
                uuid = self.Conn.recv(self.Recv_Size)
                Log.info("文件服务uuid: %s" % uuid)
                self.Uuid = uuid
                break
            except Exception as e:
                Log.info("连接失败。。%s" % e)
                time.sleep(1)

    def on_message(self, data):
        try:
            """监听服务端发送的消息"""
            # 客户端接收服务端传动的文件，也就是客户端的下载操作
            if data['code'] == Protocol.UpLoad_File:
                data.update(dict(is_local=False))
                result, msg = self.Write_File.write(data)
                if not result:
                    Log.waring(msg)
                    self.msg_signal.emit(dict(title="OS错误", msg=msg))
            elif data["code"] == Protocol.OsError:
               self.msg_signal.emit(dict(title="OS错误", msg=data["msg"]))
               Stop_Send()
               Log.info("服务端发送文件错误， 已更新全局状态为暂停发送")
            # elif data["code"] == Protocol.Cancel_Upload:
            #     Stop_Send()
            #     Log.waring("服务器取消接受文件，已更新全局状态为暂停发送")
            elif data["code"] == Protocol.Stop_Send_Success:
                Log.info("服务端停止接收")
            else:
                Log.info("未知协议 %d" % data["code"])
        except Exception as e:
            Log.error("FileSocket.on_message 错误%s" % e)

    def upload_file(self, data):
        Start_Send()
        data.update(is_local=True)
        result, msg = self.Send_File.send(data)
        if not result:
            Log.info(msg)
            self.msg_signal.emit(dict(title="IO错误", msg=msg))

    def download_file(self, protocol):
        protocol.update(code=Protocol.Request_DownLoad_File)
        data = Tools.encode(protocol)
        self.Conn.sendall(data)
