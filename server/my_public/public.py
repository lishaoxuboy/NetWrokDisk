"""实现一些公共用法"""
import json
import time
import os
import queue
from PyQt5.QtWidgets import QFileIconProvider, QMessageBox
from PyQt5.QtCore import QFileInfo
import threading
import datetime
import psutil
import shutil
import platform
import getpass
from config import Config_Impl

Protocol_Len = Config_Impl.Protocol_Len
One_Group_Len = Config_Impl.Data_Len
Send_Len = One_Group_Len - Protocol_Len
Recv_Len = One_Group_Len
STOP_SEND = False
UPDATE_INTERVAL = False

FILE_TYPE_ICO = dict()
FILE_TYPE_ICO["File Folder"] = "static/ico/Folder"
FILE_TYPE_ICO["Folder"] = "static/ico/Folder"
FILE_TYPE_ICO["jpg File"] = "static/ico/jpg.png"
FILE_TYPE_ICO["png File"] = "static/ico/png.png"
FILE_TYPE_ICO["sys File"] = "static/ico/img.png"
FILE_TYPE_ICO["text File"] = "static/ico/txt.txt"
FILE_TYPE_ICO["File"] = "static/ico/txt.txt"
FILE_TYPE_ICO["zip File"] = "static/ico/zip.zip"
FILE_TYPE_ICO["7z File"] = "static/ico/7z.7z"
FILE_TYPE_ICO["rar File"] = "static/ico/rar.rar"
FILE_TYPE_ICO["gz File"] = "static/ico/gz.gz"


def Stop_Send():
    global STOP_SEND
    STOP_SEND = True
    return True


def Start_Send():
    global STOP_SEND
    STOP_SEND = False
    return True


class MyLog:
    _instance_lock = threading.Lock()

    def __init__(self, log_file_path="log.txt"):
        self.Log_List = queue.Queue()
        self.Log_Fp = open(log_file_path, "a+")
        threading.Thread(target=self.write_log).start()
        self.Log_List.put(dict(level="DEBUG", log="日志模块已启动"))

    def __new__(cls, *args, **kwargs):
        if not hasattr(MyLog, "_instance"):
            with MyLog._instance_lock:
                if not hasattr(MyLog, "_instance"):
                    MyLog._instance = object.__new__(cls)
        return MyLog._instance

    def info(self, log):
        self.Log_List.put(dict(level="INFO", log=log))

    def waring(self, log):
        self.Log_List.put(dict(level="WARING", log=log))

    def error(self, log):
        self.Log_List.put(dict(level="ERROR", log=log))

    def debug(self, log):
        self.Log_List.put(dict(level="DEBUG", log=log))

    def write_log(self):
        while True:
            log_item = self.Log_List.get()
            log = "%s - %s - %s" % (time.strftime("%Y:%m:%d %H-%M-%S"), log_item["level"], log_item["log"])
            print(log)
            # self.Log_Fp.write(log)


Log = MyLog()


class Protocol:
    Local = 0
    Server = 1
    SuccessCode = 0
    UpLoad_File = 1001
    Request_DownLoad_File = 1002
    Response_DwonnLoad_File = 1003
    Cancel_Download = 1004
    Stop_Send_Success = 1005
    Cancel_Upload = 1006

    GetServerDrive = 2001
    ResponseServerDrive = 2002
    GetServerFiles = 2003
    ResponseServerFiles = 2004

    OsError = 3000
    OsRemoveItem = 3002
    OsMkDir = 3004
    OsReName = 3005
    WriteEndFlag = b'~*~*'
    GetSysInfo = 4001


class Tools:

    @staticmethod
    def format_show_second(s, join=True):

        return str(datetime.timedelta(seconds=s if s > 1 else 1)).rsplit(".", maxsplit=1)[0]

    @staticmethod
    def padding_data(b_data, all_length):
        """将数据填充到指定长度"""
        has_length = all_length - len(b_data)
        for i in range(has_length):
            b_data += b'$'
        return b_data

    @staticmethod
    def b_size(b_len, lens=2):
        """
        auth: wangshengke@kedacom.com ；科达柯大侠
        递归实现，精确为最大单位值 + 小数点后三位
        """

        def _size(_integer, _remainder, _level):
            if _integer >= 1024:
                _remainder = int(int(_integer % 1024) / 100)
                if _remainder < 1:
                    _remainder = 1
                _integer //= 1024
                _level += 1
                return _size(_integer, _remainder, _level)
            else:
                return int(_integer), _remainder, _level

        units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
        integer, remainder, level = _size(b_len, 0, 0)
        if level + 1 > len(units):
            level = -1
        try:
            r = '{}.{} {}'.format(integer, remainder, units[level])
            # r = '{}{}'.format(round(integer, 1), units[level])
            return r
        except Exception:
            return 0

    @staticmethod
    def decode(b_data, json_decode=True) -> bytes or dict:
        if not b_data:
            return None
        n_data = ''
        for i in b_data:
            i = chr(i)
            if i != '$':
                n_data += i
        try:
            if not json_decode:
                return n_data
            else:
                data = json.loads(n_data)
            return data
        except Exception as e:
            print(b_data)
            return None

    @staticmethod
    def encode(protocol, data=b""):
        if isinstance(data, dict):
            data = json.dumps(data).encode()
        protocol_data = Tools.padding_data(json.dumps(protocol).encode(), Protocol_Len)
        data = protocol_data + data
        return data

    @staticmethod
    def is_last_group(data):
        if data[-4:] == Protocol.WriteEndFlag:
            return True, data[:-4]
        else:
            return False, data

    @staticmethod
    def get_drive():
        sys_name = platform.system()
        _drive = []
        _root = str()
        _path = str()
        if sys_name == "Windows":
            for i in psutil.disk_partitions():
                _drive.append(i.device)
            _root = _drive[0] if _drive else "C:\\"
        else:
            username = getpass.getuser()
            _drive.append(os.path.join("/", "Users", username))
            _root = "/Users"
            _path = os.path.join(username)
        return dict(root=_root, path=_path, device=_drive)

    @staticmethod
    def before_to_next(in_path, windows=True, check_exists=True):
        try:
            t_root = str()
            t_path = str()
            if windows:
                if check_exists:
                    if not os.path.exists(in_path):
                        return None, None
                base_root = in_path.split(":")
                if not len(base_root) > 1:
                    return None, None
                t_root = base_root[0] + ":"
                base_path = in_path.replace(t_root, "")
                t_path = str()
                if base_path:
                    t_path = base_path[1:]
            else:
                if check_exists:
                    if not os.path.exists(in_path):
                        return None, None
                base_root = in_path.split("/")
                t_root = os.path.join("/", base_root[1])
                if "Users" not in t_root:
                    return None, None
                replace_str = t_root
                if len(base_root) > 2:
                    replace_str += "/"
                t_path = in_path.replace(replace_str, "")
            return t_root, t_path
        except Exception:
            return None, None


class FileIO:

    @staticmethod
    def rename(q_widget, old_name, new_name):
        if os.path.exists(new_name):
            if q_widget:
                QMessageBox.warning(q_widget, "重命名", "%s已存在" % os.path.basename(new_name))
            return False, "%s已存在" % os.path.basename(new_name)
        else:
            try:
                os.renames(old_name, new_name)
                return True, ""
            except Exception as e:
                if q_widget:
                    QMessageBox.warning(q_widget, "重命名", "命名失败 %s" % e.args[1])
                try:
                    e_msg = e.args[1]
                except Exception:
                    e_msg = ""
                return False, "命名失败 %s" % e_msg

    @staticmethod
    def mk_dir(q_widget, new_dir):
        if os.path.exists(new_dir):
            if q_widget:
                QMessageBox.warning(q_widget, "新建文件夹", "%s已存在" % new_dir)
            return False, "%s已存在" % new_dir
        try:
            os.mkdir(new_dir)
            return True, ""
        except Exception as e:
            if q_widget:
                QMessageBox.warning(q_widget, "新建文件夹", "%s创建失败" % e.args[1])
            return False, "创建失败 %s" % e.args[1]

    @staticmethod
    def del_every(q_widget, abs_path):
        # 删除文件
        if not os.path.isdir(abs_path):
            if not q_widget:
                res = QMessageBox.Yes
            else:
                res = QMessageBox.question(q_widget, "删除文件", "确认删除？", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if res == QMessageBox.Yes:
                try:
                    os.remove(abs_path)
                    return True, ""
                except Exception as e:
                    if q_widget:
                        QMessageBox.warning(q_widget, "删除文件", "删除失败%s" % e.args[1])
                    return False, "删除失败%s" % e.args[1]
            return False, "取消删除"
        # 删除目录
        else:
            if q_widget:
                res = QMessageBox.question(q_widget, "删除目录", "确认删除？", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            else:
                res = QMessageBox.Yes

            if res == QMessageBox.Yes:
                try:
                    shutil.rmtree(path=abs_path)
                    return True, ""
                except Exception as e:
                    if q_widget:
                        QMessageBox.warning(q_widget, "删除目录", "删除失败%s" % e.args[1])
                    return False, "删除失败%s" % e.args[1]
            return False, "取消删除"

    @staticmethod
    def _listdir(path):
        try:
            return os.listdir(path)
        except PermissionError as e:
            return list()

    @staticmethod
    def get_files(path, sord_type=4, reverse=False):
        provider = QFileIconProvider()
        try:
            list_dir = os.listdir(path)
        except Exception:
            return []
        list_dir.sort()
        file_list = list()
        for file in list_dir:
            item_file = dict()
            if file.startswith("."):
                continue
            if file == "pagefile.sys":
                continue
            abs_file_path = os.path.join(path, file)
            mtime = os.path.getmtime(abs_file_path)
            item_file["name"] = file
            item_file["type"] = provider.type(QFileInfo(abs_file_path))
            item_file["last_time"] = time.strftime('%Y-%m-%d %H-%M-%S', time.localtime(int(mtime)))
            raw_size = os.path.getsize(abs_file_path)
            item_file["raw_size"] = raw_size
            size = raw_size / 1024
            if item_file["type"] in ["File Folder", "Folder"]:
                item_file["size"] = ""
                item_file["raw_size"] = 0
            else:
                size, unit = FileIO.byte_to_size(size)
                item_file["size"] = str(size) + " " + unit

            file_list.append(item_file)
        Sort_Dict = {1: "type", 2: "name", 3: "last_time", 4: "raw_size"}
        file_list = sorted(file_list, key=lambda x: x[Sort_Dict[sord_type]], reverse=reverse)
        return file_list

    @staticmethod
    def get_drive():
        return psutil.disk_partitions()

    @staticmethod
    def byte_to_size(size):
        if size >= 1024:
            size /= 1024
            unit = " MB"
            if size >= 1024:
                size /= 1024
                unit = "GB"
        else:
            unit = " KB"
        return round(size, 2), unit


class RecvStream:
    def __init__(self, conn, on_msg, limit=Recv_Len):
        self.Conn = conn
        self.on_msg = on_msg
        self.Only_Read_Recv_Size = limit
        self.Recv_Size = limit
        self.stream_buffer = b""
        self.data_buffer = b""
        self.data_queue = queue.Queue()
        self.File_Transfer_Protocol_List = [Protocol.UpLoad_File, Protocol.Response_DwonnLoad_File]
        threading.Thread(target=self.recv_data).start()

    def recv_data(self):
        """
        保证接收到的数据都是预期接收到的
            解决服务器端发送10字节， 客户端分N次接收的问题，所以约定发送的大小，除了到文件结尾，否则会一直接收到约定大小。
        :return:
        """
        while True:
            try:
                b_data = self.Conn.recv(self.Recv_Size)
                b_data_len = len(b_data)
            except ConnectionResetError:
                print("Socket断开了")
                break
            if not b_data_len:
                # print("空消息")
                time.sleep(0.01)
                continue
            # 不能先解析协议，协议有可能会被分割发送
            if b_data_len == self.Recv_Size:
                protocol = Tools.decode(b_data[:Protocol_Len])
                if protocol["code"] in self.File_Transfer_Protocol_List:
                    if protocol["last_group"]:
                        stream = b_data[Protocol_Len:][:protocol["last_group_size"]]
                    else:
                        stream = b_data[Protocol_Len:]
                    protocol.update(dict(stream=stream))
                    self.on_msg(protocol)
                else:
                    try:
                        dict_data = Tools.decode(b_data[Protocol_Len:])
                        protocol.update(dict(data=dict_data))
                        self.on_msg(protocol)
                    except json.decoder.JSONDecodeError:
                        need_recv_len = protocol["data_len"]
                        receive_len = len(b_data[Protocol_Len:])
                        receive_b_data = b_data[Protocol_Len:]
                        # 循环接受剩余数据
                        while need_recv_len - receive_len != 0:
                            b_data = self.Conn.recv(need_recv_len - receive_len)
                            receive_len += len(b_data)
                            receive_b_data += b_data
                        dict_data = json.loads(receive_b_data)
                        protocol.update(data=dict_data)
                        self.on_msg(protocol)
            else:
                # 先判断协议部分是否接收完毕
                while b_data_len < Protocol_Len:
                    b_data += self.Conn.recv(Protocol_Len - b_data_len)
                    b_data_len = len(b_data)

                protocol = Tools.decode(b_data[:Protocol_Len])
                if not protocol:
                    print("协议解析错误")
                    continue

                # 文件传送
                if protocol["code"] in self.File_Transfer_Protocol_List:
                    while Recv_Len != b_data_len:
                        b_data += self.Conn.recv(Recv_Len - b_data_len)
                        b_data_len = len(b_data)
                    if protocol["last_group"]:
                        file_stream = b_data[Protocol_Len:][:protocol["last_group_size"]]
                    else:
                        file_stream = b_data[Protocol_Len:]
                    protocol.update(stream=file_stream)
                    self.on_msg(protocol)
                # 数据传送
                else:
                    """
                    2、接收到了数据字节，但是数据字节不足额定长度
                    """
                    try:
                        if b_data[Protocol_Len:]:
                            data = json.loads(b_data[Protocol_Len:])
                        else:
                            data = dict()
                        protocol.update(data=data)
                        self.on_msg(protocol)
                    except Exception:
                        # 没接收到完整的数据
                        need_recv_len = protocol["data_len"]
                        receive_len = len(b_data[Protocol_Len:])
                        receive_b_data = b_data[Protocol_Len:]
                        # 循环接受剩余数据
                        while need_recv_len - receive_len != 0:
                            b_data = self.Conn.recv(need_recv_len - receive_len)
                            receive_len += len(b_data)
                            receive_b_data += b_data
                        dict_data = json.loads(receive_b_data)
                        protocol.update(data=dict_data)
                        self.on_msg(protocol)


class WriteFile:
    def __init__(self, *args):
        # 首次写入文件信号函数，每次写入文件调用信号函数，写入结束调用信号函数
        self.brfore_first_write, self.every_write, self.after_end = args
        self.File_Fp = None
        self.Keep_Write_File = True
        # self.IO_Error = False
        # self.IO_Error_Msg = str()
        self.update_widget = False

    def Stop_Write(self):
        if self.File_Fp:
            self.File_Fp.close()
            Log.info(f"停止写入文件 已释放")
        self.File_Fp = None
        self.Keep_Write_File = False

    def write(self, data):
        if not self.Keep_Write_File:
            return False, "停止写入"
        # if self.IO_Error:
        #     # if data["last_group"]:
        #     self.IO_Error = False
        #     self.IO_Error_Msg = str()
        #     self.File_Fp and self.File_Fp.close()
        #     self.File_Fp = None
        #     return True, ""
        try:
            # 文件流
            stream = data["stream"]
            # 最后一组数据
            if data["last_group"]:
                # 发送的时候如果不足一组数据大小，会填充数据，解析的时候会方便些
                stream = stream[:data["last_group_size"]]
            # 已打开直接写入
            if self.File_Fp:
                self.File_Fp.write(stream)
                # 每次写入回调
                if self.every_write:
                    # 如果传递更新进度条的信号函数，则调用
                    progress_data = dict(
                        file_name=data.get("file_name"),
                        progress=data.get("progress"),
                        speed=data.get("speed"),
                        elapsed_time=data.get("elapsed_time"),
                        remaining_time=data.get("remaining_time"),
                        send_detail=data.get("send_detail", ""),
                    )
                    if self.every_write and UPDATE_INTERVAL:
                        if int(time.time()) % 2 == 0 and not self.update_widget:
                            self.update_widget = True
                            self.every_write.emit(progress_data)
                        if int(time.time()) % 2 == 1 and self.update_widget:
                            self.update_widget = False
                            self.every_write.emit(progress_data)
                    else:
                        self.every_write.emit(progress_data)

                if data["last_group"]:
                    # 写入结束回调
                    self.after_end and self.after_end.emit()
                    Log.info("文件写入完毕 %s" % data["file_name"])
                    self.File_Fp.close()
                    self.File_Fp = None
                    Log.info("文件已释放.")
                return True, ""
            # 文件首次写入
            else:
                abs_path = os.path.join(data["write_root"], data["write_path"], data["file_name"])
                if os.path.exists(abs_path):
                    try:
                        os.remove(abs_path)
                    except Exception as e:
                        # 需要通知不在发送
                        self.IO_Error = True
                        return False, e.args[1]
                self.File_Fp = open(abs_path, "ba")
                self.File_Fp.write(stream)
                # 首次写入回调
                self.brfore_first_write and self.brfore_first_write.emit(dict(is_local=data["is_local"]))
                Log.info("接收推送文件 %s" % abs_path)
                if data["last_group"]:
                    # 写入结束回调
                    self.after_end and self.after_end.emit()
                    Log.info("文件写入完毕 %s" % data["file_name"])
                    self.File_Fp.close()
                    self.File_Fp = None
                    Log.info("文件已释放.")
                return True, ""
        except Exception as e:
            # self.IO_Error = True
            try:
                e_msg = e.args[1]
            except Exception:
                e_msg = ""
            # self.IO_Error_Msg = e_msg
            return False, e_msg


class SendFile:
    def __init__(self, Conn, update_widget=False, *args):
        # 发送通道，开始发送文件信号函数，每次发送文件调用信号函数，发送结束调用信号函数
        self.brfore_begin_send, self.every_send, self.after_end = args
        self.Conn = Conn
        self.update_widget = update_widget

    def send(self, data):
        try:
            # 开始发送回调函数
            self.brfore_begin_send and self.brfore_begin_send.emit(dict(is_local=data["is_local"]))
            abs_path = os.path.join(data["root"], data["path"], data["file_name"])
            file_name = data["file_name"]
            abs_path = os.path.join(data["root"], data["path"], file_name)
            file_size = os.path.getsize(abs_path)
            send_size = int()
            file_size_detail = Tools.b_size(file_size)
            Log.info("即将发送 %s 大小 %s" % (abs_path, file_size_detail))
            with open(abs_path, 'rb') as FP:
                Log.info("文件已打开")
                # 读取固定长度
                b_data = FP.read(Send_Len)
                # 在消息头中加入协议
                protocol = dict(code=Protocol.UpLoad_File,
                                file_name=file_name,
                                write_path=data["write_path"],
                                write_root=data["write_root"],
                                last_group=False
                                )
                start_time = time.time()
                if len(b_data) < Send_Len or os.path.getsize(abs_path) == Send_Len:
                    Log.info("文件将一次性发送完毕")
                    protocol["last_group"] = True
                    protocol["last_group_size"] = len(b_data)
                    b_data = Tools.padding_data(b_data, Send_Len)
                    self.Conn.send(Tools.encode(protocol, b_data))
                    self.after_end and self.after_end.emit()
                    return True, ""
                send_b_data = Tools.encode(protocol, b_data)
                update_widget = False
                while len(send_b_data) > Protocol_Len:
                    if STOP_SEND:
                        Start_Send()
                        self.after_end and self.after_end.emit()
                        return False, "已停止发送 %s" % file_name
                    send_len = self.Conn.send(send_b_data)
                    send_size += send_len
                    # 再次读取
                    b_data = FP.read(Send_Len)
                    # 读取到了文件结尾
                    if len(b_data) < Send_Len:
                        protocol["last_group"] = True
                        Log.info("文件已发送至结尾")
                        protocol["last_group_size"] = len(b_data)
                        b_data = Tools.padding_data(b_data, Send_Len)
                        print("发送的长度 %s" % len(b_data))
                        self.Conn.send(Tools.encode(protocol, b_data))
                        Log.info("%s 上传完毕， 耗时 %d" % (file_name, int(time.time()) - start_time))
                        self.after_end and self.after_end.emit()
                        return True, ""
                    else:
                        protocol["last_group"] = False

                    using_time = time.time() - start_time
                    if using_time < 1:
                        using_time = 1
                    one_s = int(send_size / using_time)
                    p_data = dict(
                        file_name=file_name,
                        progress=round(send_size / file_size * 100, 2),
                        speed=Tools.b_size(one_s),
                        elapsed_time=Tools.format_show_second(time.time() - start_time),
                        remaining_time=Tools.format_show_second((file_size - send_size) / one_s),
                        update_widget=self.update_widget,
                        send_detail=Tools.b_size(send_size) + "/" + file_size_detail
                    )
                    # time.sleep(0.001)
                    if self.every_send:
                        # self.every_send.emit(p_data)
                        if UPDATE_INTERVAL:
                            if int(time.time()) % 2 == 0 and not update_widget:
                                update_widget = True
                                self.every_send.emit(p_data)
                            if int(time.time()) % 2 == 1 and update_widget:
                                update_widget = False
                                self.every_send.emit(p_data)
                        else:
                            self.every_send.emit(p_data)
                    else:
                        protocol.update(p_data)
                    send_b_data = Tools.encode(protocol, b_data)
        except Exception as e:
            return False, e.args[1]