import os
import json
import time
import queue
import threading

from PyQt5.Qt import QApplication

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
                print(f"文件流 {file_stream['write_path']} 写入磁盘成功")
            else:
                # print(f"写入流 {len(file_stream)}")
                self.write_data(file_stream)
        # print("File对象释放了")

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


class Handler:
    """
    可发送文件
    可发送对象
    """

    def __init__(self,
                base_socket,
                 file_io,
                 protocol_len,
                 file_once_recv,
                 once_recv,
                 padding_char=b"*",
                 on_error=None):
        self.file_io = file_io              # 当接受到文件时候
        self.once_recv = once_recv
        self.base_socket = base_socket
        self.padding_char = padding_char
        self.protocol_len = protocol_len
        self.file_group_len = file_once_recv
        self.on_error = on_error
        self.file_fp = None
        self.allow_send = False
        self.recv_allow_send_response = False
        self.local_reload = None

        self.show_progress = None   # 信号槽
        self.hide_progress = None
        self.set_status = None

        self.response_data = queue.Queue()
    # 运行参数的初始化

    # 接受信息（继承RecvStream类）
    def on_msg(self, b_data):
        try:
            protocol = self.decode_protocol(b_data)
        except Exception as e:
            print("解析协议出错", e, b_data, len(b_data))
            return
        try:
            code = protocol["code"]
            next_size = protocol.get("size")
            msg = protocol["msg"]
        except Exception as e:
            print("解析协议错误", e)
            return

        if code == 100:    # 收到了文件流
            print(f"收到文件流 {protocol['write_path']}")
            all_size = next_size
            last_d = b''                        # 接收到上一组的数据
            last_second_recv_bytes = int()      # 上一秒接收到的字节数，用于计算下载进度条
            last_second = int(time.time())      # 用来控制间隔一秒更新一次下载进度的变量
            start_time = int(time.time())       # 下载数据开始的时间
            once_recv = self.once_recv          # 规定了一次最多接收多少数据
            receive_size = 0                    # 一共接收了多少数据
            detail_size = tools.bytes_to_speed(all_size)   # 需要下载的数据大小以人性化方式展示

            # 首次接收到文件，需要实例化一个文件类
            if not self.file_fp:
                try:
                    self.file_fp = self.file_io(write_path=protocol["write_path"])
                except Exception as e:
                    print("初始化文件对象错误：", str(e))
                    return
            # 当需要接收的数据大于单次最大接收量时，需要进入while循环，直到接收完毕
            if all_size > once_recv:
                while receive_size !=  all_size:
                    receive_data = self.base_socket.recv_once(once_recv)
                    last_d = receive_data
                    last_second_recv_bytes += len(receive_data)
                    receive_size += len(receive_data)

                    # 为了不让IO耽误时间，这里使用工厂模式处理文件的写入
                    self.file_fp.stream_queue.put(receive_data)

                    # 当剩余的数据小于一组的大小，需要更改下一次接收字节的数量，否则会打乱数据
                    if (all_size - receive_size) < once_recv:
                        once_recv = all_size - receive_size

                    # 每秒钟更新下载进度条
                    if int(time.time()) != last_second and self.set_status:
                        progress = tools.Dict(
                            operation="传送中",
                            name=os.path.basename(protocol["write_path"]),
                            progress=int(receive_size / all_size * 100),
                            speed=tools.bytes_to_speed(last_second_recv_bytes),
                            detail=tools.bytes_to_speed(receive_size) + "/" + detail_size,
                            elapsed_time=tools.second_to_time(int(time.time()) - start_time),
                            remaining_time=tools.second_to_time((all_size - receive_size) / last_second_recv_bytes))
                        self.set_status.emit(tools.Dict(progress))
                        last_second = int(time.time())
                        last_second_recv_bytes = int()

            else:
                receive_data = self.base_socket.recv_once(all_size)
                last_d = receive_data
                self.file_fp.stream_queue.put(receive_data)
            # 发送一个字典对象，表示写入结束
            self.file_fp.stream_queue.put(protocol)
            self.file_fp = None
            print(f"文件写入缓存成功 {os.path.basename(protocol['write_path'])} \n"
                  f"文件一共{all_size} 接收了 {receive_size}  最后一组数据长度 {len(last_d)} \n {last_d}")

        elif code == 101:   # 客户端需要下载文件
            receive_data = self.base_socket.recv_agroup(next_size)
            data = tools.decode_dict(receive_data)
            file_list = data["file_list"]
            write_to = data["write_path"]
            print("客户下载文件", file_list)
            self.send_files(file_list, write_to)

        elif code == 200: # 创建新目录
            # 只有服务器才会使用此方法
            receive_data = self.base_socket.recv_agroup(next_size)
            data = tools.decode_dict(receive_data)
            # if data.get("dir_path") == "C:/test/Keil/C51/Examples/ST uPSD/upsd3300/DK3300-ELCD/I2C/I2C_Master":
            #     print("11111")
            dir_path = data["dir_path"]
            succ, msg = tools.mkdir(dir_path)
            if not succ:
                # return self.send_data(201, '创建新目录成功')
                return self.error(msg)

        elif code == 202:   # 更改名字
            # 只有服务器才会使用此方法
            receive_data = self.base_socket.recv_agroup(next_size)
            data = tools.decode_dict(receive_data)
            succ, msg = tools.rename(data["old"], data["new"])
            if succ:
                return self.send_data(203, '重命名成功')
            return self.error(msg)

        elif code == 204:   #删除服务器目录或者文件
            # 只有服务器才会使用此方法
            receive_data = self.base_socket.recv_agroup(next_size)
            data = tools.decode_dict(receive_data)
            succ, msg = tools.remove(data["abs_path"])
            if succ:
                return self.send_data(205, '删除成功')
            return self.error(msg)

        elif code == 206:   # 客户端获取服务器目录
            receive_data = self.base_socket.recv_agroup(next_size)
            data = tools.decode_dict(receive_data)
            list_dir = tools.listdir(data["dir_path"])
            self.send_data(207, data=dict(list_dir=list_dir))

        elif code == 207: # 服务器返回目录
            receive_data = self.base_socket.recv_agroup(next_size)
            data = tools.decode_dict(receive_data)
            self.response_data.put(data)

        elif code == 208:  # 客户端获取服务器磁盘
            disk_list = tools.get_disk()
            self.send_data(207, data=dict(disk_list=disk_list))

        elif code == 209:
            receive_data = self.base_socket.recv_agroup(next_size)
            data = tools.decode_dict(receive_data)
            self.response_data.put(data["disk_list"])
            disk_list = data["disk_list"]
            print("收到服务器磁盘列表", disk_list)

        elif code == 210:
            if self.local_reload:
                print("刷新本地文件")
                self.local_reload()

        elif code == 500:   # 收到异常
            receive_data = self.base_socket.recv_agroup(next_size)
            data = tools.decode_dict(receive_data)
            if self.on_error:
                self.on_error(data)
            print(f"收到异常： {data}")

        elif code == 501:   # 收到通知
            print(f"收到消息： {protocol['msg']}")

        elif code == 600:
            if self.show_progress:
                self.show_progress.emit()

        elif code == 601:
            if self.hide_progress:
                self.hide_progress.emit()

        elif code == 602:
            receive_data = self.base_socket.recv_agroup(next_size)
            data = tools.decode_dict(receive_data)
            if self.set_status:
                self.set_status.emit(tools.Dict(data))

    def send_summary(self):
        pass

    # 发送文件
    def send_files(self, file_list, write_to, set_progress=None):
        for file_path in file_list:
            file_name = os.path.basename(file_path)
            size, unit, bytes_size = tools.file_size(file_path)
            with open(file_path, 'rb') as fp:
                protocol = dict(code=100, msg='', size=os.path.getsize(file_path), write_path=os.path.join(write_to, file_name))
                self.before_send(protocol)
                b_data = fp.read(self.file_group_len)
                last_s = int(time.time())
                last_s_send_group = int()
                send_group = int()
                start_time = int(time.time())
                while b_data:
                    if self.base_socket.send_all(b_data):
                        send_group += 1
                        last_s_send_group += 1
                        b_data = fp.read(self.file_group_len)
                        # 如果设置了回调函数，每秒钟调用并且传递回调函数
                        if int(time.time()) != last_s and set_progress:  # 说明过去了一秒
                            QApplication.processEvents()
                            d = tools.Dict(
                                operation="传送中",
                                name=file_name,
                                progress=int(send_group * self.file_group_len / bytes_size* 100),
                                speed=tools.bytes_to_speed(last_s_send_group * self.file_group_len),
                                detail=tools.bytes_to_speed(send_group * self.file_group_len) + "/" + str(size) + unit,
                                elapsed_time=tools.second_to_time(int(time.time()) - start_time),
                                remaining_time=tools.second_to_time((bytes_size - send_group * self.file_group_len) / (last_s_send_group * self.file_group_len))
                            )
                            last_s_send_group = int()
                            last_s = int(time.time())
                            set_progress.emit(d)

                    else:
                        print("scoket异常 文件发送停止。")
                        return False
            print("文件发送完毕", file_name)
        return True

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
        res = self.response_data.get()
        return res["list_dir"]
    
    def get_disk_list(self):
        self.send_data(208, '获取磁盘列表')
        return self.response_data.get()
    
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
