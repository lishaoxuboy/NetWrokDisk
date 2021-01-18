import socket
import time
import queue
import sys

from my_public.public import Tools, Protocol, Recv_Len,  MyLog, RecvStream, SendFile, WriteFile
from config import Config_Impl


# 初始化日志、服务端端口
Log = MyLog("log.txt")
FILE_IP = (Config_Impl.File_Ip, Config_Impl.File_Port)
DATA_IP = (Config_Impl.Data_Ip, Config_Impl.Data_Port)


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
                self.Conn.connect(DATA_IP)
                print(f"数据服务连接成功")
                break
            except Exception as e:
                print("数据通道连接失败。。%s" % e)
                time.sleep(1)

    def on_message(self, data):
        """监听服务端发送的消息"""
        self.Recv_Data_Queue.put(data)

    def get_server_files(self, *args):
        data = Tools.encode(dict(code=Protocol.GetServerFiles), dict(path=args[0], item=args[1]))
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
        self._connect()                                                 # 连接文件传送通道
        self.msg_signal = signal                                        # 发送消息
        self.Send_File = SendFile(self.Conn, True, *args)               # 初始化文件发送接收类
        self.Write_File = WriteFile(*args)                              # 初始化文件发送接收类
        self.Data_Socket = args[-1]
        self.Os_Error = False
        self.Error_List = list()
        RecvStream(self.Conn, self.on_message)                          # 专门管理数据接受，并且回调给处理函数

    def _connect(self):
        """与服务器建立socket"""
        self.Conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        while True:
            try:
                self.Conn.connect(FILE_IP)
                Log.info(f"文件服务连接成功，等待接收uuid....")
                uuid = self.Conn.recv(Recv_Len)
                Log.info("文件服务uuid: %s" % uuid)
                self.Uuid = uuid
                break
            except Exception as e:
                Log.info("连接失败。。%s" % e)
                time.sleep(1)

    def on_message(self, data):
        try:
            # 写入文件

            if data['code'] == Protocol.UpLoad_File:
                file_uuid = data["uuid"]
                # 发生异常后，停止写入
                if self.Os_Error or file_uuid in self.Error_List:
                    return
                if data.get("first_group"):
                    self.Send_File.before_begin_send.emit(dict(is_local=False))
                if data.get("last_group"):
                    self.Send_File.after_end.emit()
                self.Write_File.reset_write()
                res_code, msg = self.Write_File.write(data)
                # 写入成功
                if res_code == 1:
                    pass
                    # self.Send_File.after_end and self.Send_File.after_end.emit()
                # 写入被取消(一般接收不到，因为取消下载，服务端立马停止发送)
                elif res_code == -1:
                    Log.info("写入被取消")
                # 写入过程发生异常错误
                elif res_code == -2:
                    self.Os_Error = True
                    self.Error_List.append(file_uuid)
                    self.Write_File.after_end.emit()
                    self.Data_Socket.Conn.sendall(Tools.encode(dict(code=Protocol.Write_Error_Cancel_Download)))
                    # res = self.Data_Socket.Recv_Data_Queue.get()
                    # if res["code"] == Protocol.Write_Error_Cancel_Download_Response:
                    self.msg_signal.emit(dict(title="警告", msg="下载失败"))
                    self.Os_Error = False
                else:
                    Log.info("写入未知错误")
            # 服务端写入错误，申请取消上传
            elif data["code"] == Protocol.Write_Error_Cancel_Upload:
                self.Send_File.stop_send()
                self.Conn.sendall(Tools.encode(dict(code=Protocol.Write_Error_Cancel_Upload_Response)))
                Log.info("停止向服务端上传文件")
                self.msg_signal.emit(dict(title="警告", msg="上传失败"))
            # elif data["code"] == Protocol.Response_Os_Error:
            #    self.msg_signal.emit(dict(title="OS错误", msg=data["msg"]))
            #    self.Write_File.Stop_Write()
            #    self.Os_Error = False
            # 服务端出现错误，停止接收，客户端需要停止发送文件呢
            # elif data["code"] == Protocol.Stop_Send:
            #     Log.info("停止发送")
            #     # self.Os_Error = False
            #     self.Send_File.after_end.emit()
            # else:
            #     Log.info("未知协议 %d" % data["code"])
        except Exception as e:
            Log.error("FileSocket.on_message 错误%s" % e)

    def upload_file(self, data):
        # 清除发送控制标志
        self.Send_File.reset_send()
        # 打开发送窗口
        self.Send_File.before_begin_send.emit(dict(is_local=True))
        res_code, msg = self.Send_File.send(data)
        # 发送成功
        if res_code == 1:
            self.Send_File.after_end.emit()
            # self.Send_File.after_end and self.Send_File.after_end.emit()
        # 发送被取消
        elif res_code == -1:
            self.Send_File.after_end.emit()
            # self.Conn.sendall(Tools.encode(dict(code=Protocol.Cancel_Upload, msg=msg)))
            # self.Send_File.after_end.emit()
        # 发送过程出现异常错误
        else:
            Log.info(msg)
            self.msg_signal.emit(dict(title="IO错误", msg=msg))

    def download_file(self, protocol):
        self.Write_File.reset_write()
        protocol.update(code=Protocol.Request_DownLoad_File)
        data = Tools.encode(protocol)
        self.Conn.sendall(data)
