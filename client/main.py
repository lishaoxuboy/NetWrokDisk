import sys
import os
from PyQt5.Qt import QApplication

from PyQt5.QtWidgets import (QWidget, QTableWidgetItem, QAbstractItemView, QFileIconProvider, QMenu, QMessageBox)
from PyQt5.QtCore import Qt, QFileInfo, pyqtSignal

from my_public.public import Tools, FileIO, Protocol, Stop_Send
from my_public import public
from file_socket import FileSocket, Log, DataSocket
from upload import Ui_Form
from progress import Ui_transfer
from create_dir import Ui_widget
import platform


class ProgressWindow(Ui_transfer, QWidget):
    def __init__(self):
        super(Ui_transfer, self).__init__()
        self.setupUi(self)
        self.local = True

    def update_status(self, file_name, send_detail, progress=0):
        self.file_name.setText(file_name)
        self.progress.setValue(int(progress or 1))
        self.speed_3.setText(send_detail)

    def update_speed(self, speed, elapsed_time, remaining_time):
        self.speed.setText(speed)
        self.elapsed_time.setText(elapsed_time)
        self.remaining_time.setText(remaining_time)

    def show_progress(self, data):
        self.local = data["is_local"]
        self.show()

    def hide_progress(self, *args):
        self.hide()
        QApplication.processEvents()
        Log.info("进度条界面已关闭")
        self.progress.setValue(0)
        for func in args:
            func()

    def closeEvent(self, event) -> None:
        reply = QMessageBox.question(self, "文件传送", "是否取消传送？", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            # 取消上传
            if self.local:
                Stop_Send()
                main_window.Data_Socket.Conn.sendall(Tools.encode(dict(code=Protocol.Cancel_Upload)))
                Log.info("通知本地取消上传文件")
            # 取消下载
            else:
                main_window.Data_Socket.Conn.sendall(Tools.encode(dict(code=Protocol.Cancel_Download)))
                main_window.File_Socket.Write_File.Stop_Write()
                Log.info("通知服务取消发送文件")
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
                old_abs_path = os.path.join(self.root, self.path, self.select_item)
                new_abs_path = os.path.join(self.root, self.path,  self.dir_name.text())
                if FileIO.rename(self, old_abs_path, new_abs_path)[0]:
                    self.hide_()
                    main_window.reload_local_files()
            else:
                print("其他")
        else:
            data = dict(root=self.root, path=self.path)
            # 新建文件夹
            if self.operation == self.NEW_DIR:
                data.update(dict(item_name=self.dir_name.text()))
                main_window.remote_mk_dir_signal.emit(data)
            # 重命名
            elif self.operation == self.RENAME:
                template_data = dict(root=self.root, path=self.path)
                data = dict(old_data=dict(item_name=self.select_item), new_data=dict(item_name=self.dir_name.text()))
                data["old_data"].update(template_data)
                main_window.remote_rename_signal.emit(data)
            else:
                print("其他2")

    def show_(self, is_local, data, operation=1):
        self.root = data["root"]
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

    def closeEvent(self, event):
        1 / 0

    def __init__(self):
        super().__init__()
        self.remote_root = "/"
        self.remote_path = str()
        self.remote_root = "/"
        self.remote_path = str()
        self.setupUi(self)
        self.Progress = ProgressWindow()                                                                # 进度条对象
        self.Data_Socket = DataSocket()                                                                 # 数据对象

        self.Create_Dir = CreateDir()                                                               # 创建目录对象
        self._init_local_drive()                                                                        # 初始化本地盘符
        self._init_server_drive()
        self.show_signal.connect(self.Progress.show_progress)                                           # 显示上传界面信号
        self.hide_signal.connect(lambda: self.Progress.hide_progress(self.reload_local_files, self.reload_server_files))  # 关闭上传界面信号
        self.update_signal.connect(self.update_status)                                                  # 更新上传进度信号
        self.remote_mk_dir_signal.connect(self.mk_server_dir)
        self.remote_rename_signal.connect(self.rename_server_item)
        self.q_message_box_signal.connect(self.show_message_box)
        self.File_Socket = FileSocket(self.q_message_box_signal, self.show_signal, self.update_signal, self.hide_signal)
                                                               # 初始化本地盘符
        self._init_file_table()                                                                         # 初始化文件表格数据

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

        self.local_root = device["root"]
        self.local_path = device["path"]
        self.LocalComboBox.currentIndexChanged.connect(lambda x: self.chang_drive(0))

    def _init_file_table(self):
        # 设置本地表格右键功能
        local_button_func = {"上传": self.File_Socket.upload_file,
                             "刷新": self.reload_local_files,
                             "删除": FileIO.del_every,
                             "新建文件夹": self.Create_Dir.show_,
                             "重命名": self.Create_Dir.show_,
                             }
        local_table = (self.LocalFiles, self.LocalLastDir, self.local_root, local_button_func)
        self._add_table_attr(local_table)
        # 设置远程表格右键功能
        remote_button_func = {"下载": self.File_Socket.download_file,
                              "刷新": self.reload_server_files,
                              "删除": self.remove_server_item,
                              "新建文件夹": self.Create_Dir.show_,
                              "重命名": self.Create_Dir.show_,
                              }
        remote_table = (self.RemoteFiles, self.RemoteLastDir, os.path.join(self.remote_root, self.remote_path), remote_button_func)
        self._add_table_attr(remote_table)

        # 加载本地根目录文件
        self.display_files(self.LocalFiles, FileIO.get_files(os.path.join(self.local_root, self.local_path), sord_type=4))
        # 加载远程根目录文件
        self.display_files(self.RemoteFiles, self.get_server_files(self.remote_root, self.remote_path, "")["data"])

    def _add_table_attr(self, data):
        item_table, last_button, root_dir, button_func = data
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
            node = self.local_root
            path = self.local_path
        else:
            local = False
            node = self.remote_root
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
        abs_path = os.path.join(os.path.join(node, path), select_name)
        func = callback_map.get(select, None)
        # 这些操作需要具体到对象， 必须检查是否选择某一项
        if row_num is None and select in ["上传", "下载", "重命名", "删除"]:
            QMessageBox.warning(self, "操作", "请选择要编辑的文件")
            return

        if local:
            Log.debug("选中文件的绝对路径为%s" % abs_path)
            data = dict(item_name=select_name,
                        file_name=select_name,
                        write_root=self.remote_root,
                        write_path=self.remote_path,
                        root=node,
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
                    root=self.remote_root,
                    path=self.remote_path,
                    item_name=select_name,  # item是编辑某一项的时候使用
                    file_name=select_name,  # file_name 是下载的时候使用
                )
            if select == "下载":
                data["write_path"] = self.local_path
                data["write_root"] = self.local_root
                func(data)
            elif select == "新建文件夹":
                func(False, data, 1)
            elif select == "重命名":
                func(False, data, 2)
            else:
                func(data)

    def get_local_cur_list(self):
        cur_abs_path = os.path.join(self.local_root, self.local_path)
        return FileIO.get_files(cur_abs_path)

    def get_local_cur_path(self, join_path=""):
        res = os.path.join(self.local_root, self.local_path)
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

    def chang_drive(self, obj):
        if obj == 0:
            t_obj = self.LocalFiles
            t_com = self.LocalComboBox
        else:
            t_obj = self.RemoteFiles
            t_com = self.RemoteComboBox

        drive = t_com.currentText()[:3]
        if "Local" in t_obj.objectName():
            self.local_root = drive
            self.local_path = ""
            self.display_files(t_obj, FileIO.get_files(t_com.currentText()))
            # self.File_Socket.FileIO.update_path(is_local=True, root=drive)
            # self.File_Socket.FileIO.update_path(is_local=True, path="")
            Log.debug("本地盘符已切换 %s" % drive)
        else:
            self.remote_root = drive
            self.remote_path = ""

            self.display_files(t_obj, MainWindow.get_server_files(t_com.currentText()))
            # self.File_Socket.FileIO.update_path(is_local=False, root=drive)
            # self.File_Socket.FileIO.update_path(is_local=False, path="")
            Log.debug("远程盘符已切换 %s" % drive)

    def _to_next_node(self, evt, f_widget):
        drive = self.get_drive(f_widget)
        path = self.get_path(f_widget)
        file_type = f_widget.item(f_widget.currentRow(), 2).text()
        click_name = f_widget.item(f_widget.currentRow(), 0).text()
        if path:
            next_path = os.path.join(path, click_name)
        else:
            next_path = click_name
        if len(next_path):
            if next_path[0] == "/":
                next_path = next_path[1:]
        next_node = os.path.join(drive, next_path)
        if file_type == "File Folder" or file_type == "Folder":
            if "Local" in f_widget.objectName():
                self.local_path = next_path
                self.display_files(f_widget, FileIO.get_files(next_node))
                # self.File_Socket.FileIO.update_path(is_local=True, path=self.local_path)
                self.LocalComboBox.setItemText(self.LocalComboBox.currentIndex(), os.path.join(self.local_root, self.local_path))
                Log.debug("访问本地下一级 %s" % next_node)
            else:
                data = self.get_server_files(drive, path, click_name)
                self.display_files(f_widget, data["data"])
                # self.File_Socket.FileIO.update_path(is_local=False, path=next_path)
                self.remote_path = data["next_path"]
                self.RemoteComboBox.setItemText(self.RemoteComboBox.currentIndex(), data["next_node"])
                Log.debug("访问服务器下一级 %s" % next_path)

        else:
            if "Local" in f_widget.objectName():
                Log.info("打开%s" % next_node)
                os.system("start " + next_node)
            else:
                QMessageBox.warning(self.RemoteFiles, '提示', '不能打开远程文件')

    def _go_back(self, f_widget):
        drive = self.get_drive(f_widget)
        path = self.get_path(f_widget)
        dir_name = os.path.dirname(path)
        if dir_name in ["/", "\\"]:
            dir_name = str()
        if len(dir_name) > 0:
            if dir_name[0] == "/":
                dir_name = dir_name[1:]

        if "Local" in f_widget.objectName():
            last_node = os.path.join(drive, dir_name)
            last_path = last_node.replace(drive, "")
            if last_path in ["/", "\\"]:
                last_path = str()
            self.display_files(f_widget, FileIO.get_files(last_node))
            self.local_path = last_path
            # self.File_Socket.FileIO.update_path(is_local=True, path=self.local_path)
            self.LocalComboBox.setItemText(self.LocalComboBox.currentIndex(), last_node)
            Log.debug("访问本地上一级 %s" % last_node)
        else:
            res = self.get_server_files(drive, path, "", True)
            self.display_files(f_widget, res["data"])
            self.remote_path = res["next_path"]
            self.RemoteComboBox.setItemText(self.RemoteComboBox.currentIndex(), res["next_node"])
            Log.debug("访问服务器上一级 %s" % res["next_node"])

    def get_drive(self, q_obj):
        return self.local_root if "Local" in q_obj.objectName() else self.remote_root

    def get_path(self, q_obj):
        return self.local_path if "Local" in q_obj.objectName() else self.remote_path

    # ================================下面是操作服务器方法===============================#
    def get_server_files(self, root, path=str(), select_item=str(), last_node=False):
        """同步 获取服务器目录"""
        data = self.Data_Socket.get_server_files(root, path, select_item, last_node)
        Log.debug("接收服务端文件")
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
            item0.setIcon(provider.icon(QFileInfo(public.FILE_TYPE_ICO.get(file_type, "ico/txt.txt"))))
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
        self.RemoteComboBox.currentIndexChanged.connect(lambda x: self.chang_drive(1))
        self.remote_path = server_drive["data"]["path"]
        self.remote_root = server_drive["data"]["root"]

    def reload_server_files(self, *args, **kwargs):
        self.display_files(self.RemoteFiles, self.get_server_files(self.remote_root, self.remote_path)["data"])

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
