import socket
import time
from threading import Thread
import os
import json

import platform
import shutil

from PyQt5.QtWidgets import QFileIconProvider
from PyQt5.QtCore import QFileInfo
from my_public.public import Tools, FileIO, Recv_Len, Protocol_Len, MyLog, RecvStream, Protocol, WriteFile, SendFile, Stop_Send, Start_Send
from config import Config_Impl


Log = MyLog("log.txt")
FILE_IP = (Config_Impl.File_Ip, Config_Impl.File_Port)
DATA_IP = (Config_Impl.Data_Ip, Config_Impl.Data_Port)


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
            self.Conn.sendall(DataManage.get_files(data))
        # 获取服务器磁盘列表
        elif pro_code == Protocol.GetServerDrive:
            self.Conn.sendall(DataManage.get_drive())
        # 删除文件或目录
        elif pro_code == Protocol.OsRemoveItem:
            self.Conn.sendall(DataManage.remove_item(data))
        # 创建文件夹
        elif pro_code == Protocol.OsMkDir:
            self.Conn.sendall(DataManage.mk_dir(data))
        # 更改文件或目录名字
        elif pro_code == Protocol.OsReName:
            self.Conn.sendall(DataManage.rename(data))
        # 终止发送
        elif pro_code == Protocol.Cancel_Download:
            Stop_Send()
            Log.info("已更新全局状态为停止发送")
        # 取消上传
        elif pro_code == Protocol.Cancel_Upload:
            File_Socket.Write_File.Stop_Write()


class DataManage:
    @staticmethod
    def get_files(data):
        _root, _path, _select_item, is_last_node = data["data"]["root"], data["data"]["path"], data["data"]["item"], data["data"]["is_dir_name"]
        if _path and is_last_node:
            _path = os.path.dirname(_path)
        path = os.path.join(_root, _path, _select_item)
        if path[-1] == "/":
            path = path[:-1]
        b_data = json.dumps(FileIO.get_files(path)).encode()
        b_data_len = len(b_data)

        next_path = _path
        if _select_item:
            next_path = os.path.join(_path, _select_item)

        protocol = dict(code=Protocol.ResponseServerFiles, next_node=path, next_path=next_path)
        # if b_data_len > Recv_Len - Protocol_Len:
        protocol.update(data_len=b_data_len)
        return Tools.encode(protocol=protocol, data=b_data)

    @staticmethod
    def get_drive():
        protocol = dict(code=Protocol.ResponseServerDrive)
        data = Tools.get_drive()
        return Tools.encode(protocol=protocol, data=json.dumps(data).encode())

    @staticmethod
    def remove_item(data):
        asb_path = os.path.join(data["data"]["root"], data["data"]["path"], data["data"]["item_name"])
        is_success, msg = FileIO.del_every(None, asb_path)
        protocol = dict(code=Protocol.OsRemoveItem, success=is_success, message=msg)
        b_data = b""
        if protocol["success"]:
            b_data = json.dumps(FileIO.get_files(os.path.dirname(asb_path))).encode()
        return Tools.encode(protocol=protocol, data=b_data)

    @staticmethod
    def mk_dir(data):
        path = os.path.join(data["data"]["root"], data["data"]["path"])
        abs_path = os.path.join(path, data["data"]["item_name"])
        result, msg = FileIO.mk_dir(None, abs_path)
        protocol = dict(code=Protocol.OsMkDir, success=result, message=msg)
        data = b""
        if result:
            data = json.dumps(FileIO.get_files(os.path.dirname(abs_path))).encode()
        return Tools.encode(protocol, data)

    @staticmethod
    def rename(data):
        path = os.path.join(data["data"]["old_data"]["root"], data["data"]["old_data"]["path"])
        old_item = os.path.join(path, data["data"]["old_data"]["item_name"])
        new_item = os.path.join(path, data["data"]["new_data"]["item_name"])
        result, msg = FileIO.rename(None, old_item, new_item)
        protocol = dict(code=Protocol.OsReName, success=result, message=msg)
        data = b""
        if result:
            data = json.dumps(FileIO.get_files(path)).encode()
        return Tools.encode(protocol, data)


class FileSocket:
    def __init__(self, connect, address):
        self.Recv_Size = Recv_Len
        self.Conn = connect                     # 客户端会话
        self.Addr = address                     # 客户端地址
        # self.File_Manage = FileManage(self.Conn)
        self.Write_File = WriteFile(None, None, None)
        self.Send_File = SendFile(self.Conn, False, None, None, None)
        RecvStream(self.Conn, self.on_message, self.Recv_Size)

    def on_message(self, data):
        """监听客户端"""
        if not data:
            print("")
        pro_code = data['code']
        if pro_code == Protocol.UpLoad_File:
            result, msg = self.Write_File.write(data)
            if not result:
                self.Conn.sendall(Tools.encode(dict(code=Protocol.OsError, msg=msg)))
        elif pro_code == Protocol.Request_DownLoad_File:
            Log.info("客户端下载文件 %s" % data["file_name"])
            Start_Send()
            result, msg = self.Send_File.send(data)
            if not result:
                Log.info(msg)
                self.Conn.sendall(Tools.encode(dict(code=Protocol.Stop_Send_Success, msg=msg)))
        else:
            Log.waring("其他协议 %s" % data)


class SocketStorage:
    Socket = dict()


Socket_Storage = SocketStorage()


def data_socket():
    f_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    f_socket.bind(DATA_IP)
    f_socket.listen()
    print("数据传送服务已启动，等待连接。。。")
    while True:
        conn, addr = f_socket.accept()
        print("与 %s 建立数据传送服务" % addr[0])
        uuid = str(time.time()).encode()
        s = DataSocket(conn, addr)
        # SocketStorage.Socket.update({uuid: s})


if __name__ == '__main__':
    f_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    f_socket.bind(FILE_IP)
    f_socket.listen()
    print("文件传送服务已启动，等待连接。。。")
    Thread(target=data_socket).start()
    try:
        while True:
            conn, addr = f_socket.accept()
            print("与 %s 建立文件传送服务" % addr[0])
            uuid = str(time.time()).encode()
            conn.sendall(uuid)
            File_Socket = FileSocket(conn, addr)
            SocketStorage.Socket.update({uuid: File_Socket})
    except Exception as e:
        print(e)
