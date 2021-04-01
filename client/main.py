import sys
import os
import time

from PyQt5.Qt import QApplication
from PyQt5.QtWidgets import (QWidget, QTableWidgetItem, QAbstractItemView, QFileIconProvider, QMenu, QMessageBox)
from PyQt5.QtCore import Qt, QFileInfo, pyqtSignal
import platform
from threading import Thread

from my_public.public import Tools, FileIO, Protocol, FILE_TYPE_ICO
from config import Config_Impl
from file_socket import FileSocket, Log, DataSocket
from upload import Ui_Form
from progress import Ui_transfer
from create_dir import Ui_widget


class ProgressWindow(Ui_transfer, QWidget):
    def __init__(self):
        super(Ui_transfer, self).__init__()
        self.setupUi(self)
        self.local = True
        self.setWindowModality(Qt.ApplicationModal)

    def update_status(self, file_name, send_detail, progress=0):
        self.file_name.setText(file_name)
        self.progress.setValue(int(progress or 1))
        self.speed_3.setText(send_detail)

    def update_speed(self, speed, elapsed_time, remaining_time):
        self.speed.setText(speed)
        self.elapsed_time.setText(elapsed_time)
        self.remaining_time.setText(remaining_time)

    def show_progress(self, data):
        Log.info("进度条界面已打开")
        self.local = data["is_local"]
        self.show()

    def hide_progress(self, *args):
        self.progress.setValue(0)
        for func in args:
            func()
        Log.info("进度条界面已关闭")
        self.hide()

    def delay_close(self, delay_time=1):
        time.sleep(delay_time)
        main_window.File_Socket.Write_File.Stop_Write()
        main_window.hide_signal.emit()

    def closeEvent(self, event) -> None:
        reply = QMessageBox.question(self, "文件传送", "是否取消传送？", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            # 取消上传
            if self.local:
                # 本地停止发送
                main_window.File_Socket.Send_File.stop_send()
                # 通知服务器取消上传
                main_window.Data_Socket.Conn.sendall(Tools.encode(dict(code=Protocol.Cancel_Upload)))
                # 关闭上传界面
                self.hide_progress()
                Log.info("通知本地取消上传文件")
            # 取消下载
            else:
                # 本地先停止写入
                # main_window.File_Socket.Write_File.Stop_Write()
                # 通知服务器取消发送
                main_window.Data_Socket.Conn.sendall(Tools.encode(dict(code=Protocol.Cancel_Download)))
                Log.info("客户端发出取消下载申请")
                res = main_window.Data_Socket.Recv_Data_Queue.get()
                Log.info("客户端发出取消下载申请结果 %s" % res)
                main_window.File_Socket.Write_File.stop_write()
                Log.info("客户端本地关闭文件")
                self.hide_progress()

        else:
            event.ignore()


class CreateDir(Ui_widget, QWidget):
    def __init__(self):
        super(Ui_widget, self).__init__()
        self.setupUi(self)
        self.local = True
        self.select_item_path = str()
        self.operation = None
        self.NEW_DIR = 1
        self.RENAME = 2
        self.buttonBox.accepted.connect(self.to_exec)
        self.buttonBox.rejected.connect(self.hide_)
        self.setWindowModality(Qt.ApplicationModal)

    def to_exec(self):
        if not self.dir_name.text():
            QMessageBox.warning(self, "更改", "内容不能为空")
            return
        if self.local:
            # 新建文件夹
            if self.operation == self.NEW_DIR:
                new_dir = os.path.join(main_window.get_local_cur_path(), self.dir_name.text())
                if FileIO.mk_dir(self, new_dir)[0]:
                    self.hide_()
                    main_window.reload_local_files()
            # 重命名
            elif self.operation == self.RENAME:
                old_abs_path = os.path.join(self.path, self.select_item)
                new_abs_path = os.path.join(self.path,  self.dir_name.text())
                if FileIO.rename(self, old_abs_path, new_abs_path)[0]:
                    self.hide_()
                    main_window.reload_local_files()
            else:
                print("其他")
        else:
            data = dict(path=self.path)
            # 新建文件夹
            if self.operation == self.NEW_DIR:
                data.update(dict(item_name=self.dir_name.text()))
                main_window.remote_mk_dir_signal.emit(data)
            # 重命名
            elif self.operation == self.RENAME:
                template_data = dict(path=self.path)
                data = dict(old_data=dict(item_name=self.select_item), new_data=dict(item_name=self.dir_name.text()))
                data["old_data"].update(template_data)
                main_window.remote_rename_signal.emit(data)
            else:
                print("其他2")

    def show_(self, is_local, data, operation=1):
        self.path = data["path"]
        self.select_item = data["item_name"]
        self.local = is_local
        self.operation = operation
        # 如果为重命名， 默认将原来名字填充编辑框
        if operation == self.RENAME:
            self.dir_name.setText(os.path.basename(data["item_name"]))
            self.setWindowTitle("重命名")
        else:
            self.setWindowTitle("新建文件夹")
        self.show()

    def hide_(self):
        self.hide()
        self.dir_name.setText("")


class MainWindow(Ui_Form, QWidget):
    show_signal = pyqtSignal(dict)
    hide_signal = pyqtSignal()
    update_signal = pyqtSignal(dict)
    mk_remote_dir_signal = pyqtSignal(dict)
    remote_mk_dir_signal = pyqtSignal(dict)
    remote_rename_signal = pyqtSignal(dict)
    q_message_box_signal = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.remote_path = str()
        self.setupUi(self)

        # 实例化组件
        self.Create_Dir = CreateDir()                                                   # 创建目录对象
        self.Progress = ProgressWindow()                                                # 进度条对象
        self.Data_Socket = DataSocket()                                                 # 数据对象
        self.File_Socket = FileSocket(self.q_message_box_signal,                        # 文件传输对象
                                      self.show_signal,
                                      self.update_signal,
                                      self.hide_signal,
                                      self.Data_Socket)

        # 初始化组件
        self._init_local_drive()                                                         # 初始化本地盘符
        self._init_server_drive()
        self._init_file_table()
        self._get_sys_info()
        self._get_server_info()

        # 绑定信号槽
        self.show_signal.connect(self.Progress.show_progress)                           # 显示上传界面信号
        self.hide_signal.connect(
            lambda: self.Progress.hide_progress(self.reload_local_files,
                                                self.reload_server_files))              # 关闭上传界面信号
        self.update_signal.connect(self.update_status)                                  # 更新上传进度信号
        self.remote_mk_dir_signal.connect(self.mk_server_dir)
        self.remote_rename_signal.connect(self.rename_server_item)
        self.q_message_box_signal.connect(self.show_message_box)

    def _get_sys_info(self):
        self.Local_Window_Sys = False
        if "Windows" in platform.platform():
            self.Local_Window_Sys = True

    def _get_server_info(self):
        self.Data_Socket.Conn.sendall(Tools.encode(dict(code=Protocol.GetSysInfo)))
        res = self.Data_Socket.Recv_Data_Queue.get()
        if res["data"].get("windows"):
            self.Remote_Window_Sys = True
        else:
            self.Remote_Window_Sys = False

    def closeEvent(self, event):
        event.accept()
        os._exit(0)

    # def keyPressEvent(self, event):
    #     key = event.key()
        # if Qt.Key_A <= key <= Qt.Key_Z:
        #     if event.modifiers() & Qt.ShiftModifier:  # Shift 键被按下
        #         self.statusBar().showMessage('"Shift+%s" pressed' % chr(key), 500)
        #     elif event.modifiers() & Qt.ControlModifier:  # Ctrl 键被按下
        #         self.statusBar().showMessage('"Control+%s" pressed' % chr(key), 500)
        #     elif event.modifiers() & Qt.AltModifier:  # Alt 键被按下
        #         self.statusBar().showMessage('"Alt+%s" pressed' % chr(key), 500)
        #     else:
        #         self.statusBar().showMessage('"%s" pressed' % chr(key), 500)
        #
        # elif key == Qt.Key_Home:
        #     self.statusBar().showMessage('"Home" pressed', 500)
        # elif key == Qt.Key_End:
        #     self.statusBar().showMessage('"End" pressed', 500)
        # elif key == Qt.Key_PageUp:
        #     self.statusBar().showMessage('"PageUp" pressed', 500)
        # elif key == Qt.Key_PageDown:
        #     self.statusBar().showMessage('"PageDown" pressed', 500)
        # else:  # 其它未设定的情况
        #     QWidget.keyPressEvent(self, event)  # 留给基类处理

    def show_message_box(self, data):
        QMessageBox.warning(self, data["title"], data["msg"])

    def update_status(self, data):
        self.Progress.update_status(data["file_name"], data["send_detail"],  data["progress"])
        self.Progress.update_speed(data["speed"], data["elapsed_time"], data["remaining_time"])
        if data.get("update_widget"):
            QApplication.processEvents()

    def _init_local_drive(self):
        """初始化本地盘符"""
        device = Tools.get_drive()
        for i in device["device"]:
            self.LocalComboBox.addItem(i)
        self.local_path = device["device"][0]
        self.LocalComboBox.currentIndexChanged.connect(lambda x: self._chang_drive(Protocol.Local))
        # self.LocalComboBox.activated.connect(self._local_combobox_activated)

    # def _local_combobox_activated(self):
    #     _root, _path = Tools.before_to_next(self.LocalComboBox.currentText(), windows=False)
    #     if _root:
    #         self.local_root = _root
    #         self.local_path = _path
    #         self.reload_local_files()
    #     else:
    #         Log.info("无效路径%s" % self.LocalComboBox.currentText())

    def _init_file_table(self):
        # 设置本地表格右键功能
        local_button_func = {"上传": self.File_Socket.upload_file,
                             "刷新": self.reload_local_files,
                             "删除": FileIO.del_every,
                             "新建文件夹": self.Create_Dir.show_,
                             "重命名": self.Create_Dir.show_,
                             }
        local_table = (self.LocalFiles, self.LocalLastDir, local_button_func)
        self._add_table_attr(local_table)
        # 设置远程表格右键功能
        remote_button_func = {"下载": self.File_Socket.download_file,
                              "刷新": self.reload_server_files,
                              "删除": self.remove_server_item,
                              "新建文件夹": self.Create_Dir.show_,
                              "重命名": self.Create_Dir.show_,
                              }
        remote_table = (self.RemoteFiles, self.RemoteLastDir, remote_button_func)
        self._add_table_attr(remote_table)

        # 加载本地根目录文件
        self.display_files(self.LocalFiles, FileIO.get_files(self.local_path,  sord_type=Config_Impl.Sort_Type))
        # 加载远程根目录文件
        self.display_files(self.RemoteFiles, self.get_server_files(self.remote_path)["data"])

    def _add_table_attr(self, data):
        item_table, last_button, button_func = data
        self.set_table_attr(item_table)
        # 绑定右击事件
        on_right_click = lambda x: self.set_right_key_menu(x, table_ojb=item_table, callback_map=button_func)
        item_table.customContextMenuRequested.connect(on_right_click)
        # 绑定双击事件
        item_table.doubleClicked.connect(lambda x: self._to_next_node(x, item_table))
        # 绑定返回上一级按钮事件
        last_func = lambda x: self._go_back(item_table)
        last_button.clicked.connect(last_func)

    @staticmethod
    def set_table_attr(table_obj):
        """设置文件表格属性"""
        # 设置布局后，不在生效
        # if "Local" in table_obj.objectName():
        # table_obj.setGeometry(0, 80, 500, 500)
        # else:
        # table_obj.setGeometry(550, 80, 500, 500)
        # 设置表头不可见，可能是左侧的一列
        table_obj.verticalHeader().setVisible(False)
        # SelectionBehavior属性用于控制选择行为操作的数据单位，是指选择时选中数据是按行、按列还是按项来选择，这里选择行
        table_obj.setSelectionBehavior(QAbstractItemView.SelectRows)
        # 在树型部件QTreeWidget中，有三种方法触发进行项数据的编辑：editTriggers触发编辑、editItem触发编辑和openPersistentEditor打开持久编辑器。
        table_obj.setEditTriggers(QAbstractItemView.NoEditTriggers)
        # 应该是设置点击的时候选中多少列
        table_obj.setColumnCount(4)
        # 允许表格右键
        table_obj.setContextMenuPolicy(Qt.CustomContextMenu)
        headers = ['文件名字', '文件大小', '文件类型', '修改时间']
        for index, item_name in enumerate(headers):
            item = QTableWidgetItem()
            item.setText(item_name)
            table_obj.setHorizontalHeaderItem(index, item)
        table_obj.setRowCount(0)

    def set_right_key_menu(self, pos, table_ojb, callback_map):
        """设置右键菜单"""
        try:
            row_num = table_ojb.selectionModel().selection().indexes()[0].row()
        except IndexError:
            Log.waring("选中了空文件")
            row_num = None
            # return

        menu = QMenu()
        menu_map = dict()
        for option, func in callback_map.items():
            item_menu = menu.addAction(option)
            menu_map[item_menu] = func
        action = menu.exec_(table_ojb.mapToGlobal(pos))
        if "Local" in table_ojb.objectName():
            local = True
            path = self.local_path
        else:
            local = False
            path = self.remote_path
        if not action:
            Log.info("未选择任何选项")
            return
        else:
            select = action.text()
        if row_num is None:
            select_name = ""
        else:
            select_name = table_ojb.item(row_num, 0).text()
        abs_path = os.path.join(path, select_name)
        func = callback_map.get(select, lambda : QMessageBox.warning(self.table_ojb, "警告", "未找到指定函数"))
        # 这些操作需要具体到对象， 必须检查是否选择某一项
        if row_num is None and select in ["上传", "下载", "重命名", "删除"]:
            QMessageBox.warning(self, "操作", "请选择要编辑的文件")
            return

        if local:
            Log.debug("选中文件的绝对路径为%s" % abs_path)
            data = dict(item_name=select_name,
                        file_name=select_name,
                        write_path=self.remote_path,
                        path=path)
            if select == "上传":
                func(data)
            elif select == "删除":
                func(self, abs_path)
                self.reload_local_files()
            elif select == "新建文件夹":
                func(True, data, 1)
            elif select == "重命名":
                func(True, data, 2)
                self.reload_local_files()
            else:
                func(abs_path)
        # 操作服务端
        else:

            data = dict(
                    path=self.remote_path,
                    item_name=select_name,  # item是编辑某一项的时候使用
                    file_name=select_name,  # file_name 是下载的时候使用
                )
            if select == "下载":
                data["write_path"] = self.local_path
                func(data)
            elif select == "新建文件夹":
                func(False, data, 1)
            elif select == "重命名":
                func(False, data, 2)
            else:
                func(data)

    def get_local_cur_list(self):
        return FileIO.get_files(self.local_path)

    def get_local_cur_path(self, join_path=""):
        res = self.local_path
        if join_path:
            res = os.path.join(res, join_path)
        return res

    def reload_local_files(self, *args, **kwargs):
        return self.display_files(self.LocalFiles, self.get_local_cur_list())

    def ready_reload_files(self, data):
        is_local = data["is_local"]
        if is_local:
            self.reload_local_files()
        else:
           self.reload_server_files()

    def _chang_drive(self, _from):
        if _from == Protocol.Local:
            self._change_dir(self.LocalFiles, self.LocalComboBox.currentText())
        else:
            self._change_dir(self.RemoteFiles, self.RemoteComboBox.currentText())

    def _to_next_node(self, evt, f_widget):
        file_type = f_widget.item(f_widget.currentRow(), 2).text()
        click_name = f_widget.item(f_widget.currentRow(), 0).text()
        next_path = os.path.join(self.get_path(f_widget), click_name).replace("\\", "/")
        if file_type == "File Folder" or file_type == "Folder":
            self._change_dir(f_widget, next_path)
        else:
            if "Local" in f_widget.objectName():
                Log.info("打开%s" % next_path)
                os.system(next_path)
            else:
                QMessageBox.warning(self.RemoteFiles, '提示', '不能打开远程文件')

    def _change_dir(self, f_widget, path):
        print("***********************", path)
        if "Local" in f_widget.objectName():
            data = FileIO.get_files(path)
            self.display_files(f_widget, data)
            self.local_path = path
            Log.debug("访问本地下一级 %s" % path)
            self.LocalComboBox.setItemText(self.LocalComboBox.currentIndex(), path)
        else:
            data = self.get_server_files(path)
            self.display_files(f_widget, data["data"])
            self.remote_path = path
            self.RemoteComboBox.setItemText(self.RemoteComboBox.currentIndex(), path)
            Log.debug("访问服务器下一级 %s" % path)

    def _go_back(self, f_widget):
        cur_path = self.get_path(f_widget)
        last_path = os.path.dirname(cur_path)
        if "/" not in last_path:
            last_path += "/"
        self._change_dir(f_widget, last_path)

    def get_path(self, q_obj):
        return self.local_path if "Local" in q_obj.objectName() else self.remote_path

    # ================================下面是操作服务器方法===============================#
    def get_server_files(self, path=str(), select_item=str()):
        """同步 获取服务器目录"""
        data = self.Data_Socket.get_server_files(path, select_item)
        return data

    def get_server_cur_path(self):
        return os.path.join(self.remote_root, self.remote_path)

    @staticmethod
    def display_files(f_widget, list_dir):

        if f_widget.rowCount() > 0:
            for row in range(f_widget.rowCount()):
                f_widget.removeRow(0)

        for index, file_obj in enumerate(list_dir):
            provider = QFileIconProvider()
            f_widget.insertRow(index)

            # =============文件图标
            item0 = QTableWidgetItem()
            item0.setText(file_obj["name"])
            file_type = file_obj['type']
            item0.setIcon(provider.icon(QFileInfo(FILE_TYPE_ICO.get(file_type, "ico/txt.txt"))))
            # f_t_widget.setRowHeight(index, 20)
            f_widget.setItem(index, 0, item0)

            # =============文件大小
            item3 = QTableWidgetItem()
            # item3.setFont(self.fileInfoWidget.global_row_font)
            item3.setText(file_obj["size"])
            f_widget.setItem(index, 1, item3)

            # =============文件类型
            item2 = QTableWidgetItem()
            # item2.setFont(self.fileInfoWidget.global_row_font)
            # fileType = provider.type(QFileInfo(abs_file_path))
            item2.setText(file_type)
            f_widget.setItem(index, 2, item2)

            # ============最后修改时间
            item1 = QTableWidgetItem()
            # item1.setFont(self.fileInfoWidget.global_row_font)
            # mtime = os.path.getmtime(abs_file_path)
            item1.setText(file_obj['last_time'])
            f_widget.setItem(index, 3, item1)
        return True

    def _init_server_drive(self):
        """初始化服务器盘符"""
        server_drive = self.Data_Socket.get_server_drive()
        for i in server_drive["data"]["device"]:
            self.RemoteComboBox.addItem(i)
        self.RemoteComboBox.currentIndexChanged.connect(lambda x: self._chang_drive(Protocol.Server))
        self.remote_path = server_drive["data"]["device"][0]

    def reload_server_files(self, *args, **kwargs):
        self.display_files(self.RemoteFiles, self.get_server_files(self.remote_path)["data"])

    def remove_server_item(self, data, *args, **kwargs):
        res = QMessageBox.question(self, "删除", "确认删除？", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if res == QMessageBox.Yes:
            del_res = self.Data_Socket.del_server_item(data)
            if not del_res["success"]:
                QMessageBox.warning(self, "删除", del_res["message"])
            else:
                self.display_files(self.RemoteFiles, del_res["data"])

    def mk_server_dir(self, data, *args, **kwargs):
        protocol = dict(code=Protocol.OsMkDir)
        self.Data_Socket.Conn.sendall(Tools.encode(protocol, data))
        res = self.Data_Socket.Recv_Data_Queue.get()
        if res["success"]:
            self.display_files(self.RemoteFiles, res["data"])
            self.Create_Dir.hide_()
        else:
            QMessageBox.warning(self, "创建文件夹", res["message"])

    def rename_server_item(self, data):
        protocol = dict(code=Protocol.OsReName)
        self.Data_Socket.Conn.sendall(Tools.encode(protocol, data))
        res = self.Data_Socket.Recv_Data_Queue.get()
        if res["success"]:
            self.Create_Dir.hide_()
            self.display_files(self.RemoteFiles, res['data'])
        else:
            QMessageBox.warning(self, "重命名", res["message"])


if __name__ == '__main__':
    # 创建应用
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    # 运行应用，并监听事件
    sys.exit(app.exec_())
