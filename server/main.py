import socket
import time
from threading import Thread
import os
import json

import platform
import shutil

from PyQt5.QtWidgets import QFileIconProvider
from PyQt5.QtCore import QFileInfo
from my_public.public import Tools, FileIO, Recv_Len, Protocol_Len, MyLog, RecvStream, Protocol, WriteFile, SendFile
from config import Config_Impl


Log = MyLog("log.txt")
FILE_IP = (Config_Impl.File_Ip, Config_Impl.File_Port)
DATA_IP = (Config_Impl.Data_Ip, Config_Impl.Data_Port)
Data_Socket = None
File_Socket = None


class DataSocket:
    def __init__(self, connect, address):
        self.Recv_Size = Recv_Len
        self.Conn = connect                     # 客户端会话
        self.Addr = address                     # 客户端地址
        RecvStream(self.Conn, self.on_message, self.Recv_Size)

    def on_message(self, data):
        """监听客户端"""
        pro_code = data['code']
        # 获取服务指定目录内容
        if pro_code == Protocol.GetServerFiles:
            Log.info("客户端获取指定目录信息 %s" % data)
            self.Conn.sendall(DataManage.get_files(data))
        # 获取服务器磁盘列表
        elif pro_code == Protocol.GetServerDrive:
            Log.info("客户端获取磁盘信息 %s" % data)
            self.Conn.sendall(DataManage.get_drive())
        # 删除文件或目录
        elif pro_code == Protocol.OsRemoveItem:
            Log.info("客户端删除文件或目录 %s" % data)
            self.Conn.sendall(DataManage.remove_item(data))
        # 创建文件夹
        elif pro_code == Protocol.OsMkDir:
            Log.info("客户端创建文件夹 %s" % data)
            self.Conn.sendall(DataManage.mk_dir(data))
        # 更改文件或目录名字
        elif pro_code == Protocol.OsReName:
            Log.info("客户端更改文件或目录名字 %s" % data)
            self.Conn.sendall(DataManage.rename(data))
        # 终止下载
        elif pro_code == Protocol.Cancel_Download:
            Log.info("客户端终止下载 %s" % data)
            File_Socket.Send_File.stop_send()
        # 取消上传
        elif pro_code == Protocol.Cancel_Upload:
            Log.info("客户端上传文件取消 %s" % data)
            File_Socket.Write_File.stop_write()
        # 获取系统信息
        elif pro_code == Protocol.GetSysInfo:
            Log.info("客户端获取系统信息 %s" % data)
            self.Conn.sendall(DataManage.get_sys_info())
        # 客户端写入错误
        elif pro_code == Protocol.Write_Error_Cancel_Download:
            Log.info("客户端申请停止写入 %s" % data)
            File_Socket.Send_File.stop_send()
            # self.Conn.sendall(Tools.encode(dict(code=Protocol.Write_Error_Cancel_Download_Response)))


class DataManage:
    @staticmethod
    def get_files(data):
        _path, _select_item = data["data"]["path"], data["data"]["item"],
        _path = os.path.dirname(os.path.join(_path, _select_item))
        b_data = json.dumps(FileIO.get_files(_path)).encode()
        b_data_len = len(b_data)
        protocol = dict(code=Protocol.ResponseServerFiles, path=_path, data_len=b_data_len)
        Log.info("%s下信息获取成功" % _path)
        return Tools.encode(protocol=protocol, data=b_data)

    @staticmethod
    def get_drive():
        protocol = dict(code=Protocol.ResponseServerDrive)
        data = Tools.get_drive()
        Log.info("磁盘信息获取成功")
        return Tools.encode(protocol=protocol, data=json.dumps(data).encode())

    @staticmethod
    def remove_item(data):
        asb_path = os.path.join(data["data"]["path"], data["data"]["item_name"])
        is_success, msg = FileIO.del_every(None, asb_path)
        protocol = dict(code=Protocol.OsRemoveItem, success=is_success, message=msg)
        b_data = b""
        if is_success:
            Log.info("客户端删除文件或目录")
            b_data = json.dumps(FileIO.get_files(os.path.dirname(asb_path))).encode()
        protocol.update(dict(data_len=len(b_data)))
        return Tools.encode(protocol=protocol, data=b_data)

    @staticmethod
    def mk_dir(data):
        path = data["data"]["path"]
        abs_path = os.path.join(path, data["data"]["item_name"])
        result, msg = FileIO.mk_dir(None, abs_path)
        protocol = dict(code=Protocol.OsMkDir, success=result, message=msg)
        data = b""
        if result:
            Log.info("%s 客户端创建文件夹成功" % path)
            data = json.dumps(FileIO.get_files(os.path.dirname(abs_path))).encode()
        protocol.update(dict(data_len=len(data)))
        return Tools.encode(protocol, data)

    @staticmethod
    def rename(data):
        path = data["data"]["old_data"]["path"]
        old_item = os.path.join(path, data["data"]["old_data"]["item_name"])
        new_item = os.path.join(path, data["data"]["new_data"]["item_name"])
        result, msg = FileIO.rename(None, old_item, new_item)
        protocol = dict(code=Protocol.OsReName, success=result, message=msg)
        data = b""
        if result:
            Log.info("%s to %s 客户端重命名" % (old_item, new_item))
            data = json.dumps(FileIO.get_files(path)).encode()
        protocol.update(dict(data_len=len(data)))
        return Tools.encode(protocol, data)

    @staticmethod
    def get_sys_info():
        is_windows = "Windows" in platform.platform()
        Log.info("客户端获取系统信息成功")
        return Tools.encode(dict(code=Protocol.GetSysInfo), json.dumps(dict(windows=is_windows)).encode())


class FileSocket:
    def __init__(self, connect, address):
        self.Recv_Size = Recv_Len
        self.Conn = connect                     # 客户端会话
        self.Addr = address                     # 客户端地址
        # self.File_Manage = FileManage(self.Conn)
        self.Write_File = WriteFile(None, None, None)
        self.Send_File = SendFile(self.Conn, False, None, None, None)
        self.Os_Error = False
        RecvStream(self.Conn, self.on_message, self.Recv_Size)

    def on_message(self, data):
        """监听客户端"""
        pro_code = data['code']
        # 写入文件
        if pro_code == Protocol.UpLoad_File:
            if self.Os_Error:
                return
            self.Write_File.reset_write()
            # 第一组
            if data.get("first_group"):
                Log.info("客户端上传文件开始 %s" % data["file_name"])
            # 最后一组
            if data.get("last_group"):
                Log.info("客户端上传文件完毕 %s" % data["file_name"])

            res_code, msg = self.Write_File.write(data)

            # 写入每一组数据成功
            if res_code == 1:
                pass
                # Log.info("客户端上传文件当前组写入完毕 %s" % data["file_name"])
            # 取消上传
            elif res_code == -1:
                # 取消上传客户端会直接停止发送，所以这里应该捕捉不到
                # Log.info("客户端上传文件取消 %s" % data["file_name"])
                pass
            elif res_code == -2:
                Log.info("写入异常，准备申请取消上传 %s" % msg)
                self.Os_Error = True
                self.Conn.sendall(Tools.encode(dict(code=Protocol.Write_Error_Cancel_Upload)))
            else:
                Log.info("未知错误")
        # 发送文件
        elif pro_code == Protocol.Request_DownLoad_File:
            self.Send_File.reset_send()
            Log.info("客户端下载文件开始 %s" % data["file_name"])
            result, msg = self.Send_File.send(data)
            if result == 1:
                Log.info("客户端下载文件结束 %s" % data["file_name"])
            if result == -1:
                Data_Socket.Conn.sendall(Tools.encode(dict(code=Protocol.Cancel_Download_Success, msg="已取消本次操作")))
                Log.info("客户端取消下载文件 %s" % data["file_name"])

        elif pro_code == Protocol.Write_Error_Cancel_Upload_Response:
            Log.info("写入异常，申请取消上传结果 %s" % data)
            self.Os_Error = False

        else:
            Log.waring("其他协议 %s" % data)


class SocketStorage:
    Socket = dict()


Socket_Storage = SocketStorage()


def data_socket():
    global Data_Socket
    f_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    f_socket.bind(DATA_IP)
    f_socket.listen()
    Log.info("数据传送服务已启动，等待连接。。。")
    while True:
        conn, addr = f_socket.accept()
        Log.info("与 %s 建立数据传送服务" % addr[0])
        uuid = str(time.time()).encode()
        Data_Socket = DataSocket(conn, addr)
        # SocketStorage.Socket.update({uuid: s})


if __name__ == '__main__':
    f_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    f_socket.bind(FILE_IP)
    f_socket.listen()
    Log.info("文件传送服务已启动，等待连接。。。")
    Thread(target=data_socket).start()
    try:
        while True:
            conn, addr = f_socket.accept()
            Log.info("与 %s 建立文件传送服务" % addr[0])
            uuid = str(time.time()).encode()
            conn.sendall(uuid)
            File_Socket = FileSocket(conn, addr)
            SocketStorage.Socket.update({uuid: File_Socket})
    except Exception as e:
        print(e)
