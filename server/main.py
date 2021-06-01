import os
import json
import time
import queue
import threading
import traceback

from base_socket import BaseSocket

import tools


class FileIO:
    def __init__(self, read_path=None, write_path=None, read_len=None, cover_write=True):
        self.stream_queue = queue.Queue()
        self.read_len = read_len
        if read_path:
            if not os.path.exists(read_path):
                raise (f"文件 {read_path} 不存在",)
            self.abs_path = read_path
            mode = "rb"
        else:
            if not os.path.exists(os.path.dirname(write_path)):
                raise Exception(f"文件夹 {write_path} 不存在")
            if os.path.exists(write_path):
                if cover_write:
                    succ, msg = tools.remove(write_path)
                    if not succ:
                        raise Exception(msg)
                else:
                    raise Exception(f"文件  {write_path} 已存在")
            self.abs_path = write_path
            mode = "wb"
        self.FP = open(self.abs_path, mode)
        if write_path:
            threading.Thread(target=self.clear_stream).start()

    def clear_stream(self):
        while not self.FP.closed:
            file_stream = self.stream_queue.get()
            if isinstance(file_stream, dict):
                self.close_file()
            else:
                self.write_data(file_stream)

    def write_data(self, data):
        self.FP.write(data)
        return True

    def read_data(self):
        one_group = self.FP.read(self.read_len)
        while one_group:
            yield one_group
            one_group = self.FP.read(self.read_len)

    def close_file(self):
        self.FP.close()


class Main:
    """
    可发送文件
    可发送对象
    """

    # 运行参数的初始化
    def __init__(self, base_socket, file_io, padding_char=b"*", protocol_len=1024, file_group_len=5120, once_recv=1024):
        self.protocol_len = protocol_len
        self.file_io = file_io
        self.file_group_len = file_group_len
        self.padding_char = padding_char
        self.base_socket = base_socket
        self.once_recv = once_recv
        self.file_fp = None
        self.allow_send = False
        self.recv_allow_send_response = False

    # 接受信息（继承RecvStream类）
    def on_msg(self, b_data):
        try:
            protocol = self.decode_protocol(b_data)
        except Exception:
            raise Exception(f"数据解析出错了 {b_data}")

        code = protocol["code"]
        size = protocol.get("size")
        msg = protocol["msg"]
        if code == 0:
            print("收到客户端的Ping....")
            return

        elif code == 100:  # 收到了文件流
            if not self.file_fp:  # 首次接收到文件，需要穿件文件写入类
                try:
                    self.file_fp = self.file_io(write_path=protocol["write_path"])
                except Exception as e:
                    print("初始化文件对象错误：", str(e))
                    # self.send_data(200, str(e), dict(allow_send=False))
                    return

            receive_size = 0
            once_recv = self.once_recv
            last_d = b""
            if size > once_recv:  # 文件大于一个接收包
                try:
                    while not size == receive_size:  # 根据协议内说明的文件大小，循环接收，直到接收完毕
                        receive_data = self.base_socket.conn.recv(once_recv)
                        last_d = receive_data
                        if receive_data:
                            receive_size += len(receive_data)
                            self.file_fp.stream_queue.put(receive_data)  # 为了不让IO耽误时间，这里使用工厂模式处理文件的写入
                            if (size - receive_size) < once_recv:  # 剩余的数据小于一组的大小了
                                once_recv = size - receive_size  # 接收剩余大小
                        else:
                            print("在接受文件流的过程中发生错误，导致接收到空字节,停止接收")
                            self.file_fp.stream_queue.put(protocol)
                            self.file_fp = None
                            return False
                except Exception as e:
                    traceback.print_exc()
                    print("在接收字节流中发生错误", e)
                    time.sleep(3)

            else:
                receive_data = self.base_socket.recv_once(size)
                last_d = receive_data
                self.file_fp.stream_queue.put(receive_data)  # 为了不让IO耽误时间，这里使用工厂模式处理文件的写入
            self.file_fp.stream_queue.put(protocol)
            self.file_fp = None
            print(f"文件写入缓存成功 {os.path.basename(protocol['write_path'])}")

        elif code == 101:  # 客户端需要下载文件
            receive_data = self.base_socket.recv_agroup(size)
            data = tools.decode_dict(receive_data)
            file_list = data["file_list"]
            write_to = data["write_path"]
            print("客户下载文件", file_list)
            self.sendfile_or_mkdir(file_list, write_to)

        elif code == 200:  # 创建新目录
            # 只有服务器才会使用此方法
            receive_data = self.base_socket.recv_agroup(size)
            data = tools.decode_dict(receive_data)
            dir_path = data["dir_path"]
            succ, msg = tools.mkdir(dir_path)
            if succ:
                return self.send_data(201, '')
            return self.error(msg)

        elif code == 202:  # 更改名字
            # 只有服务器才会使用此方法
            receive_data = self.base_socket.recv_agroup(size)
            data = tools.decode_dict(receive_data)
            succ, msg = tools.rename(data["old"], data["new"])
            if succ:
                return self.send_data(203, '')
            return self.error(msg)

        elif code == 204:  # 删除服务器目录或者文件
            # 只有服务器才会使用此方法
            receive_data = self.base_socket.recv_agroup(size)
            data = tools.decode_dict(receive_data)
            succ, msg = tools.remove(data["abs_path"])
            if succ:
                return self.send_data(205, '')
            return self.error(msg)

        elif code == 206:  # 客户端获取服务器目录
            receive_data = self.base_socket.recv_agroup(size)
            data = tools.decode_dict(receive_data)
            list_dir = tools.listdir(data["dir_path"])
            self.send_data(207, data=dict(list_dir=list_dir))

        elif code == 207:  # 服务器返回目录
            receive_data = self.base_socket.recv_agroup(size)
            data = tools.decode_dict(receive_data)
            print("收到服务器目录内容", data)

        elif code == 208:  # 客户端获取服务器磁盘
            disk_list = tools.get_disk()
            self.send_data(207, data=dict(disk_list=disk_list))

        elif code == 209:
            receive_data = self.base_socket.recv_agroup(size)
            data = tools.decode_dict(receive_data)
            disk_list = data["disk_list"]
            print("收到服务器磁盘列表", disk_list)

        elif code == 500:  # 收到异常
            receive_data = self.base_socket.recv_agroup(size)
            data = tools.decode_dict(receive_data)
            print(f"收到异常： {data}")

        elif code == 501:  # 收到通知
            print(f"收到消息： {protocol['msg']}")

    def sendfile_or_mkdir(self, file_list, write_to):
        # 打开传送窗口
        self.send_data(600, '')
        for item in file_list:
            cur_path = os.path.dirname(item)
            for flag, path in tools.list_dir_all(cur_path, os.path.basename(item)):
                path = path.replace("\\", "/")
                if flag == 0:  # 创建目录
                    progress_data = tools.Dict(
                        operation="创建目录",
                        name=os.path.basename(path),
                        progress=100,
                        speed="---",
                        detail="创建完毕",
                        elapsed_time="00:00:00",
                        remaining_time="00:00:00"
                    )
                    # 更新状态
                    print("创建目录", path)
                    abs_path = os.path.join(write_to, path)
                    self.os_mkdir(abs_path)
                    self.send_data(602, '', progress_data)
                    # time.sleep(0.1)
                else:
                    file_path = os.path.join(cur_path, path).replace("\\", "/")
                    client_write_to = os.path.dirname(os.path.join(write_to, path)) + "/"
                    # progress_data = tools.Dict(
                    #     operation="下载中...",
                    #     name=os.path.basename(file_path),
                    #     progress=100,
                    #     speed="---",
                    #     detail="下载暂不提供进度",
                    #     elapsed_time="00:00:00",
                    #     remaining_time="00:00:00"
                    # )
                    # self.send_data(602, '', progress_data)
                    self.send_files([file_path], client_write_to)
                    # time.sleep(0.1)
        # 关闭传送窗口
        self.send_data(601, '')
        self.client_reload()

    # 发送文件
    def send_files(self, file_list, write_to):
        for file_path in file_list:
            file_name = os.path.basename(file_path)
            size, unit, bytes_size = tools.file_size(file_path)
            # 用来辅助计算发送进度
            # last_s = int(time.time())
            # last_s_send_group = int()
            # send_group = 1
            # start_time = int(time.time())
            # update_status = False
            with open(file_path, 'rb') as fp:
                protocol = dict(code=100, msg='', size=bytes_size, write_path=os.path.join(write_to, file_name))
                self.before_send(protocol)
                print(f"通知客户端接收文件 {file_path} 每组 {self.file_group_len} ")
                b_data = fp.read(self.file_group_len)
                if len(b_data) < self.file_group_len:
                    self.base_socket.send_all(b_data)
                    return
                while b_data:
                    self.base_socket.send_all(b_data)
                    b_data = fp.read(self.file_group_len)
                    continue
                    # 服务端不提供进度，客户端自己计算
                    # last_s_send_group += 1
                    # # 如果设置了回调函数，每秒钟调用并且传递回调函数
                    # if int(time.time()) != last_s and not update_status:  # 说明过去了一秒
                    #     progress_data = tools.Dict(
                    #         operation="下载中",
                    #         name=file_name,
                    #         progress=int((send_group * self.file_group_len / bytes_size) * 100),
                    #         speed=tools.bytes_to_speed(last_s_send_group * self.file_group_len),
                    #         detail=tools.bytes_to_speed(send_group * self.file_group_len) + "/" + str(
                    #             size) + unit,
                    #         elapsed_time=tools.second_to_time(int(time.time()) - start_time),
                    #         remaining_time=tools.second_to_time(
                    #             (bytes_size - send_group * self.file_group_len) / (
                    #                     last_s_send_group * self.file_group_len))
                    #     )
                    #     last_s_send_group = int()
                    #     last_s = int(time.time())
                    #     base_data = tools.jsondumps(progress_data)
                    #     base_data_len = len(base_data)
                    #     b_data = tools.padding_data(base_data, self.file_group_len - base_data_len)
                    #     update_status = True
                    #     # print("progress data", bytes_progress_data)
                    # else:
                    #     send_group += 1
                    #     update_status = False
                    #     b_data = fp.read(self.file_group_len)

    # 下载文件
    def down_load_files(self, file_list, write_path):
        new_file_list = file_list.copy()
        for i in file_list:
            name = os.path.basename(i)
            if os.path.exists(os.path.join(write_path, name)):
                print(f"{os.path.join(write_path, name)} 已存在，跳过...")
                new_file_list.remove(i)
        self.send_data(101, '下载文件', dict(file_list=new_file_list, write_path=write_path))

    # 发送普通对象数据
    def send_data(self, code, msg='', data=None):
        b_data = tools.encode_dict(data)
        size = len(b_data) if data else int()
        protocol = dict(code=code, msg=msg, size=size)
        self.before_send(protocol)
        if data:
            self.base_socket.send_all(b_data)
        return

    def os_mkdir(self, dir_path):
        self.send_data(200, '创建目录', data=dict(dir_path=dir_path))

    def os_remove(self, abs_path):
        self.send_data(204, '删除目录', data=dict(abs_path=abs_path))

    def os_rename(self, old, new):
        self.send_data(202, '重命名', data=dict(old=old, new=new))

    def get_dir_list(self, dir_path):
        self.send_data(206, '获取目录', data=dict(dir_path=dir_path))

    def get_disk_list(self):
        self.send_data(208, '获取磁盘列表')

    def client_reload(self):
        self.send_data(210, '通知客户端刷新列表')

    # 在发送数据前通知对方相关信息，做好接受准备
    def before_send(self, protocol):
        self.base_socket.send_all(self.padding(tools.encode_dict(protocol)))

    # 数据解析
    def decode_protocol(self, b_data):
        return json.loads(b_data.decode().replace(self.padding_char.decode(), ''))

    # 数据对齐
    def padding(self, bytes_data):
        bytes_data += self.padding_char * (self.protocol_len - len(bytes_data))
        return bytes_data

    # 服务发生异常，通知客户端
    def error(self, msg):
        self.send_data(500, msg, dict(msg=msg))


import socket
import sys

once_r = int(sys.argv[1]) if len(sys.argv) > 1 else 10240
port = int(sys.argv[2]) if len(sys.argv) > 2 else 1123
protocol_len = 1024
print("once_r", once_r)
while True:
    session = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    session.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    session.bind(("0.0.0.0", port))
    session.listen(5)
    print("server start on 0.0.0.0:%s..." % port)
    c, addr = session.accept()
    print(f"来自 {addr} 的连接")
    socket_base = BaseSocket(c, addr, protocol_len=protocol_len)
    # 线程
    socket_base.recv_data_for_every()
    # 实例化主程序
    main = Main(socket_base, FileIO, file_group_len=once_r, once_recv=once_r, protocol_len=protocol_len)
    print("主程序完成序列化")
    # 绑定socket收到消息后的回调函数
    socket_base.set_onmsg(main.on_msg)
