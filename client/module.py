from PyQt5.QtWidgets import (QWidget, QTableWidgetItem, QAbstractItemView, QFileIconProvider, QMenu, QMessageBox)
from PyQt5.QtCore import Qt, QFileInfo, pyqtSignal
from PyQt5.Qt import QApplication

from main_window import Ui_Form
from sub_windoow import Ui_widget
from progress import Ui_transfer
from tools import Dict, ICO, os
import tools


class Base:
    @classmethod
    def fmt_pack(cls, widget=None, **kwargs):
        """
        格式话函数之前传递参数的格式
        """
        if kwargs is None:
            data = Dict()
        else:
            data = Dict(kwargs)
        return Dict(widget=widget, data=data)

    @staticmethod
    def question(package):
        res = QMessageBox.question(package.widget, "删除", "确认删除？", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if res == QMessageBox.Yes:
            return True
        return False


class ProgressWindow(Ui_transfer, QWidget):
    def __init__(self):
        super(Ui_transfer, self).__init__()
        self.setupUi(self)
        self.setWindowModality(Qt.ApplicationModal)

    def set_status(self, data):
        self.operation.setText(data.operation)
        self.name.setText(data.name)
        # 进度
        self.progress.setValue(int(data.progress) or 1)
        # 详情
        self.detail.setText(data.detail)
        # 传输速度
        self.speed.setText(data.speed)
        # 已用时间
        self.elapsed_time.setText(data.elapsed_time)
        # 预计还需时间
        self.remaining_time.setText(data.remaining_time)

    def show_window(self):
        self.show()

    def hide_window(self):
        self.hide()

    def closeEvent(self, event) -> None:
        reply = QMessageBox.question(self, "文件传送", "是否取消传送？", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            if self.on_close:
                self.on_close()
        else:
            event.ignore()


class InputWindow(Base, Ui_widget, QWidget):
    def __init__(self, accept=None):
        super(Ui_widget, self).__init__()
        self.setupUi(self)
        self.accept = accept
        self.package = None
        self.buttonBox.accepted.connect(self.ok)
        self.buttonBox.rejected.connect(self.hide_window)
        self.setWindowModality(Qt.ApplicationModal)

    def register(self, package):
        self.package = package

    def ok(self):
        self.package.data.text = self.dir_name.text()
        self.package.data.ok(self.package)

    def show_window(self):
        self.show()

    def set_title(self, package):
        self.setWindowTitle(package.data.title)

    def set_text(self, package):
        self.dir_name.setText(package.data.text)

    def hide_window(self):
        self.hide()
        self.package = None
        self.accept = None
        self.set_text(self.fmt_pack(text=str()))


class MainWindow(Base, Ui_Form, QWidget):
    set_progress = pyqtSignal(Dict)
    show_progress = pyqtSignal()
    hide_progress = pyqtSignal()

    def __init__(self, local_c, remote_c, module_c):
        super().__init__()
        self.table_headers = ['文件名字', '文件大小', '文件类型', '修改时间']
        self.setupUi(self)  # 继承主界面

        self.local_table_func = tools  # 包含了一些可以操作本地文件io的函数
        self.remote_table_func = remote_c  # 包含了可以与远程服务器的一些操作
        self.modules = module_c  # 操作辅助组件的类
        self.remote_table_func.on_error = self.on_error
        self.set_progress.connect(self.modules.progress_window.set_status)
        self.show_progress.connect(self.modules.progress_window.show_window)
        self.hide_progress.connect(self.modules.progress_window.hide_window)
        self.init_local_table()  # 初始化本地文件表格
        self.init_remote_table()  # 初始化本地文件表格

    def get_local_selected(self):
        selected_list = list()
        select_rows = self.LocalFiles.selectionModel().selectedRows()
        if len(select_rows):
            for i in select_rows:
                select_name = self.LocalFiles.item(i.row(), 0).text()
                base_path = self.get_comboBox_first_item(self.fmt_pack(self.LocalComboBox))
                selected_list.append((base_path, select_name))
        return selected_list

    def get_remote_selected(self):
        selected_list = list()
        select_rows = self.RemoteFiles.selectionModel().selectedRows()
        if len(select_rows):
            for i in select_rows:
                select_name = self.RemoteFiles.item(i.row(), 0).text()
                base_path = self.get_comboBox_first_item(self.fmt_pack(self.RemoteComboBox))
                selected_list.append((base_path, select_name))
        return selected_list

    def selecte_send(self):
        select_rows = self.get_local_selected()
        if len(select_rows):
            for path, name in select_rows:
                self.local_upload(self.fmt_pack(local_path=path, name=name))

        else:
            selected_list = list()
            select_rows = self.get_remote_selected()
            if len(select_rows):
                for path, name in select_rows:
                    selected_list.append(os.path.join(path, name))
            if selected_list:
                self.remote_downloads(selected_list)

    def select_del(self):
        select_rows = self.get_local_selected()
        if select_rows:
            removes_list = list()
            for path, name in select_rows:
                removes_list.append(os.path.join(path, name))
            self.remove_dirs(self.fmt_pack(removes_list=removes_list))
        else:
            select_rows = self.get_remote_selected()

    def remove_dirs(self, package):
        del_count = len(package.data.removes_list)
        package.data.title = "考虑清楚了吗？"
        package.data.text = f"批量删除 {del_count}个对象，删除后不可撤回！"
        if self.aer_you_sure(package):
            self.show_progress.emit()
            for i in package.data.removes_list:
                if self.set_progress:
                    progress_data = tools.Dict(
                        operation="批量删除",
                        name=os.path.basename(i),
                        progress=100,
                        speed="---",
                        detail="",
                        elapsed_time="00:00:00",
                        remaining_time="00:00:00"
                    )
                    self.set_progress.emit(progress_data)
                QApplication.processEvents()
                self.local_table_func.remove(i)
            self.hide_progress.emit()
            self.local_reload_table()


    def keyPressEvent(self, evt):
        # control + s
        if evt.key() == Qt.Key_S and evt.modifiers() == Qt.ControlModifier:
            self.selecte_send()
        if evt.modifiers() == Qt.ControlModifier and evt.key() == Qt.Key_R:
            self.local_reload_table()
            self.remote_reload()
        if evt.modifiers() == Qt.ControlModifier and evt.key() == Qt.Key_D:
            self.select_del()
        # print(evt.key())
        # if evt.key() == Qt.Key_Control:

        # if evt.modifiers() == Qt.ControlModifier:
        #     print("you want del ?")
        # if evt.modifiers() == Qt.AltModifier:
        #     print("you want send ?")
        # if evt.modifiers() == Qt.ShiftModifier:
        #     print("you press shift")

    def init_local_table(self):
        # 设置盘符列表
        self.set_disk(self.fmt_pack(widget=self.LocalComboBox, disk_list=self.local_table_func.get_disk()))

        # 绑定磁盘切换回调函数
        self.bind_comboBox_change_event(self.fmt_pack(self.LocalComboBox, callbak=self.on_local_change_disk))

        # 添加表头
        self.add_table_header(self.fmt_pack(self.LocalFiles, headers=self.table_headers))

        # 获取根目录文件，并添加到文件表格中
        list_dir = lambda: self.local_table_func.listdir(
            self.get_comboBox_first_item(self.fmt_pack(self.LocalComboBox)))
        self.add_item_on_file_table(self.fmt_pack(self.LocalFiles, listdir=list_dir()))

        # 添加表格双击事件(下一级)
        self.bind_doubleClicked(self.fmt_pack(self.LocalFiles,
                                              get_listdir=list_dir,
                                              curpath=self.get_local_path,
                                              comboBox=self.LocalComboBox
                                              ))
        # （上一级）
        self.LocalLastDir.clicked.connect(lambda: self.go_back(self.fmt_pack(self.LocalComboBox,
                                                                             listdir=list_dir,
                                                                             file_widget=self.LocalFiles
                                                                             )))

        # 设置右键菜单
        button_func = Dict(上传=self.local_upload,
                           刷新=self.local_reload_table,
                           删除=self.local_remove_and_reload,
                           新建文件夹=self.local_ready_mkdir,
                           重命名=self.local_ready_rename)
        get_local_path = lambda: self.get_comboBox_first_item(self.fmt_pack(self.LocalComboBox))
        get_remote_path = lambda: self.get_comboBox_first_item(self.fmt_pack(self.RemoteComboBox))
        data = self.fmt_pack(self.LocalFiles, menu=button_func, get_local_path=get_local_path,
                             get_remote_path=get_remote_path)
        # 将菜单绑定到指定对象上
        self.table_add_right_key_menu(data)

    def init_remote_table(self):
        # 设置盘符列表
        self.set_disk(
            self.fmt_pack(widget=self.RemoteComboBox, disk_list=self.remote_table_func.get_disk_list()['disk_list']))

        # 绑定磁盘切换回调函数
        self.bind_comboBox_change_event(self.fmt_pack(self.RemoteComboBox, callbak=self.on_remote_change_disk))

        # 添加表头
        self.add_table_header(self.fmt_pack(self.RemoteFiles, headers=self.table_headers))

        # 获取根目录文件，并添加到文件表格中
        list_dir = lambda: self.remote_table_func.get_dir_list(
            self.get_comboBox_first_item(self.fmt_pack(self.RemoteComboBox)))
        self.add_item_on_file_table(self.fmt_pack(self.RemoteFiles, listdir=list_dir()))

        # 添加表格双击事件(下一级)
        self.bind_doubleClicked(self.fmt_pack(self.RemoteFiles,
                                              get_listdir=list_dir,
                                              curpath=self.get_remote_path,
                                              comboBox=self.RemoteComboBox
                                              ))
        # (上一级)
        self.RemoteLastDir.clicked.connect(lambda: self.go_back(self.fmt_pack(self.RemoteComboBox,
                                                                              listdir=list_dir,
                                                                              file_widget=self.RemoteFiles
                                                                              )))
        # 设置右键菜单
        button_func = Dict(下载=self.remote_download,
                           刷新=self.remote_reload,
                           删除=self.remote_remove,
                           新建文件夹=self.remote_mkdir,
                           重命名=self.remote_rename)
        get_local_path = lambda: self.get_comboBox_first_item(self.fmt_pack(self.LocalComboBox))
        get_remote_path = lambda: self.get_comboBox_first_item(self.fmt_pack(self.RemoteComboBox))
        data = self.fmt_pack(self.RemoteFiles, menu=button_func, get_local_path=get_local_path,
                             get_remote_path=get_remote_path)
        # 将菜单绑定到指定对象上
        self.table_add_right_key_menu(data)

    def bind_doubleClicked(self, package):
        package.widget.doubleClicked.connect(lambda x: self._to_next_node(x, package))

    @classmethod
    def bind_comboBox_change_event(cls, package):
        """
        绑定下拉框更改事件
        """
        package.widget.currentIndexChanged.connect(package.data.callbak)

    def on_error(self, data):
        print("modele_on_error: ", data)

    def on_local_change_disk(self):
        """
        本地切换了盘符
        """
        next_dir_list = self.local_table_func.listdir(Dict(path=self.LocalComboBox.currentText()))
        print("本地切换盘符", self.LocalComboBox.currentText())
        if next_dir_list:
            self.clear_table_files(self.fmt_pack(self.LocalFiles))
            self.add_item_on_file_table(self.fmt_pack(self.LocalFiles, listdir=next_dir_list))

    def on_remote_change_disk(self):
        """
        本地切换了盘符
        """
        print("远程切换盘符", self.RemoteComboBox.currentText())
        next_dir_list = self.remote_table_func.get_dir_list(self.RemoteComboBox.currentText())
        if next_dir_list:
            self.clear_table_files(self.fmt_pack(self.RemoteFiles))
            self.add_item_on_file_table(self.fmt_pack(self.RemoteFiles, listdir=next_dir_list))
            # self.remote_reload(self.fmt_pack())

    def on_progress_window_close(self):
        print("on_progress_window_close")

    def local_upload(self, package):
        # abs_path = os.path.join(package.data.local_path, package.data.name)
        for flag, item in tools.list_dir_all(package.data.local_path, package.data.name):
            self.show_progress.emit()
            if flag == 0:  # 需要创建目录
                write_to = self.get_comboBox_first_item(self.fmt_pack(self.RemoteComboBox))
                self.set_progress.emit(Dict(
                    operation="创建目录",
                    name=item,
                    progress=100,
                    detail="创建完毕",
                    speed="---",
                    elapsed_time="00:00:00",
                    remaining_time="00:00:00"
                ))
                QApplication.processEvents()
                self.remote_table_func.os_mkdir(os.path.join(write_to, item))
                print(f"创建目录:{item}")
            else:  # 发送文件
                abs_path = os.path.join(package.data.local_path, item)
                base_write_to = self.get_comboBox_first_item(self.fmt_pack(self.RemoteComboBox))
                write_to = os.path.dirname(os.path.join(base_write_to, item))
                try:
                    self.remote_table_func.send_files([abs_path], write_to, self.set_progress)
                except Exception as e:
                    print("1111")

        self.hide_progress.emit()
        self.remote_reload(package)

    def local_ready_mkdir(self, package):
        """
        本地创建文件
        """
        package.data.local = True
        package.data.mkdir = True
        package.data.path = package.data.local_path
        package.data.ok = self.input_ok
        self.modules.input_window.register(package)
        self.modules.input_window.show_window()
        self.modules.input_window.set_title(self.fmt_pack(title="创建目录"))

    def local_ready_rename(self, package):
        """
        重命名本地文件
        """
        package.data.local = True
        package.data.rename = True
        package.data.path = package.data.local_path
        package.data.ok = self.input_ok
        self.modules.input_window.register(package)
        self.modules.input_window.show_window()
        self.modules.input_window.set_title(self.fmt_pack(title="重命名"))
        self.modules.input_window.set_text(self.fmt_pack(text=package.data.name))

    def local_ready_del(self, package):
        """
        删除本地指定项
        """
        abs_path = os.path.join(package.data.local_path, package.data.name)
        self.local_table_func.remove(abs_path)

    def local_reload_table(self, package=None):
        """重新加载本地文件列表"""
        package = self.fmt_pack(self.LocalFiles)
        self.clear_table_files(package)
        package.data.listdir = self.local_table_func.listdir(
            self.get_comboBox_first_item(self.fmt_pack(self.LocalComboBox)))
        self.add_item_on_file_table(package)

    def local_remove_and_reload(self, package):
        """
        删除目录或文件 并且重新加载列表
        """
        package.data.title = "考虑清楚了吗？"
        package.data.text = "删除后不可撤回！"
        if self.aer_you_sure(package):
            self.local_ready_del(package)
            self.local_reload_table(package)

    def remote_download(self, package):
        # for flag, item in tools.list_dir_all(package.data.remote_path, package.data.name):
        #     if flag == 0:   # 需要创建目录
        #         write_to = self.get_comboBox_first_item(self.fmt_pack(self.RemoteComboBox))
        #         self.remote_table_func.os_mkdir(os.path.join(write_to, item))
        #     else:   # 发送文件
        #         abs_path = os.path.join(package.data.local_path, item)
        #         base_write_to = self.get_comboBox_first_item(self.fmt_pack(self.RemoteComboBox))
        #         write_to = os.path.dirname(os.path.join(base_write_to, item))
        #         self.remote_table_func.send_files([abs_path], write_to)
        # tools.list_dir_all()
        self.remote_table_func.down_load_files([os.path.join(package.data.remote_path, package.data.name)],
                                               package.data.local_path)

    def remote_downloads(self, files):
        local_path = self.get_comboBox_first_item(self.fmt_pack(self.LocalComboBox))
        self.remote_table_func.down_load_files(files, local_path)

    def remote_reload(self, package=None):
        # 获取根目录文件，并添加到文件表格中
        list_dir = self.remote_table_func.get_dir_list(self.get_comboBox_first_item(self.fmt_pack(self.RemoteComboBox)))
        self.clear_table_files(self.fmt_pack(self.RemoteFiles))
        self.add_item_on_file_table(self.fmt_pack(self.RemoteFiles, listdir=list_dir))

    def remote_mkdir(self, package):
        package.data.remote = True
        package.data.mkdir = True
        package.data.path = package.data.remote_path
        package.data.ok = self.input_ok
        self.modules.input_window.register(package)
        self.modules.input_window.show_window()
        self.modules.input_window.set_title(self.fmt_pack(title="创建目录"))

    def remote_remove(self, package):
        if self.aer_you_sure(self.fmt_pack(self, title="考虑清楚了吗？", text="删除不可撤回!")):
            self.remote_table_func.os_remove(os.path.join(package.data.remote_path, package.data.name))
            self.remote_reload(package)

    def remote_rename(self, package):
        package.data.remote = True
        package.data.rename = True
        package.data.path = package.data.remote_path
        package.data.ok = self.input_ok
        self.modules.input_window.register(package)
        self.modules.input_window.show_window()
        self.modules.input_window.set_title(self.fmt_pack(title="重命名"))
        self.modules.input_window.set_text(self.fmt_pack(text=package.data.name))

    def get_local_path(self):
        return self.LocalComboBox.currentText()

    def get_remote_path(self):
        return self.RemoteComboBox.currentText()

    # ==========================远程与本地的文件表格公用方法=======================================+#

    def _to_next_node(self, evt, package):
        f_widget = package.widget
        file_type = f_widget.item(f_widget.currentRow(), 2).text()
        click_name = f_widget.item(f_widget.currentRow(), 0).text()
        cur_path = package.data.curpath()
        next_path = os.path.join(cur_path, click_name)
        if file_type == "File Folder" or file_type == "Folder":
            next_path = os.path.join(cur_path, click_name + "/")
            self.set_comboBox_text(self.fmt_pack(package.data.comboBox, text=next_path))
            package.data.listdir = package.data.get_listdir()
            self.clear_table_files(package)
            self.add_item_on_file_table(package)
        else:
            if "Local" in f_widget.objectName():
                print("打开%s" % next_path)
                os.system(next_path)
            else:
                QMessageBox.warning(self.RemoteFiles, '提示', '不能打开远程文件')

    def go_back(self, package):
        cur_path = self.get_comboBox_first_item(package)[:-1]  # dirname函数以反斜线来区分目录，需要把最后一个反斜线去掉
        last_path = os.path.dirname(cur_path) + "/"  # 在加上去
        self.set_comboBox_text(self.fmt_pack(package.widget, text=last_path))
        package.data.listdir = package.data.listdir()
        package.widget = package.data.file_widget
        self.clear_table_files(package)
        self.add_item_on_file_table(package)

    @staticmethod
    def set_comboBox_text(package):
        package.widget.setCurrentText(package.data.text)

    def msg_box(self, package):
        QMessageBox.warning(self, package.title, package.text)

    @staticmethod
    def aer_you_sure(package):
        if QMessageBox.question(package.widget, package.data.title, package.data.text) == QMessageBox.Yes:
            return True
        return False

    def input_ok(self, package):
        """
        当创建完目录或者更改了目录或者文件名字后会跳转这里，进行动作分发
        """
        if package.data.local:
            abs_path = os.path.join(package.data.local_path, package.data.text)
            if package.data.mkdir:
                status, msg = self.local_table_func.mkdir(abs_path)
                if status is not True:
                    print(msg)
                else:
                    self.modules.input_window.hide_window()
                    self.local_reload_table(self.fmt_pack())
            else:
                old_path = os.path.join(package.data.local_path, package.data.name)
                status, msg = self.local_table_func.rename(old_path, abs_path)
                if status is not True:
                    print(msg)
                else:
                    self.modules.input_window.hide_window()
                    self.local_reload_table(self.fmt_pack())
        else:
            abs_path = os.path.join(package.data.remote_path, package.data.text)
            if package.data.mkdir:
                self.remote_table_func.os_mkdir(abs_path)
                self.modules.input_window.hide_window()
            else:
                old_path = os.path.join(package.data.remote_path, package.data.name)
                self.remote_table_func.os_rename(old_path, abs_path)
                self.modules.input_window.hide_window()
                self.local_reload_table(self.fmt_pack())
            self.remote_reload(package)

    @classmethod
    def add_table_header(cls, package):
        """设置文件表头"""
        # 设置表头不可见，可能是左侧的一列
        package.widget.verticalHeader().setVisible(False)
        # SelectionBehavior属性用于控制选择行为操作的数据单位，是指选择时选中数据是按行、按列还是按项来选择，这里选择行
        package.widget.setSelectionBehavior(QAbstractItemView.SelectRows)
        # 在树型部件QTreeWidget中，有三种方法触发进行项数据的编辑：editTriggers触发编辑、editItem触发编辑和openPersistentEditor打开持久编辑器。
        package.widget.setEditTriggers(QAbstractItemView.NoEditTriggers)
        # 应该是设置点击的时候选中多少列
        package.widget.setColumnCount(4)
        # 允许表格右键
        package.widget.setContextMenuPolicy(Qt.CustomContextMenu)
        for index, item_name in enumerate(package.data.headers):
            item = QTableWidgetItem()
            item.setText(item_name)
            package.widget.setHorizontalHeaderItem(index, item)
        package.widget.setRowCount(0)

    @classmethod
    def add_item_on_file_table(cls, package):
        """
        像指定表格对象添加指定的特定格式数据数据
        """

        for index, file_obj in enumerate(package.data.listdir):
            file_obj = Dict(file_obj)
            # 插入空行
            package.widget.insertRow(index)

            # =============文件图标
            item0 = QTableWidgetItem()
            item0.setText(file_obj.name)
            provider = QFileIconProvider()
            item0.setIcon(provider.icon(QFileInfo(ICO.FILE_TYPE_ICO.get(file_obj.type, "ico/txt.txt"))))
            # f_t_widget.setRowHeight(index, 20)
            package.widget.setItem(index, 0, item0)

            # =============文件大小
            item3 = QTableWidgetItem()
            # item3.setFont(self.fileInfoWidget.global_row_font)
            item3.setText(file_obj.size)
            package.widget.setItem(index, 1, item3)

            # =============文件类型
            item2 = QTableWidgetItem()
            # item2.setFont(self.fileInfoWidget.global_row_font)
            # fileType = provider.type(QFileInfo(abs_file_path))
            item2.setText(file_obj.type)
            package.widget.setItem(index, 2, item2)

            # ============最后修改时间
            item1 = QTableWidgetItem()
            # item1.setFont(self.fileInfoWidget.global_row_font)
            # mtime = os.path.getmtime(abs_file_path)
            item1.setText(file_obj.last_time)
            package.widget.setItem(index, 3, item1)
        return True

    def table_add_right_key_menu(self, package):
        """
        绑定表右键功能
        pos右键时组件传递进去
        """
        package.widget.customContextMenuRequested.connect(lambda pos: self.on_right_click(pos, package))

    @classmethod
    def on_right_click(cls, pos, package):
        row_num = -1
        select_name = str()
        try:
            row_num = package.widget.selectionModel().selection().indexes()[0].row()
            select_name = package.widget.item(row_num, 0).text()
        except IndexError:
            pass

        menu = QMenu()
        for value, func in package.data.menu.items():
            menu.addAction(value)
            # item_menu = menu.addAction(value)
            # menu_map[item_menu] = func

        # 显示菜单，并返回一个被选择项或者空
        action = menu.exec_(package.widget.mapToGlobal(pos))
        if not action:
            print("未选择任何选项")
            return

        # 选中的操作
        select_action = action.text()
        # 没有选择文件时候不能使用这些功能
        if row_num == -1 and select_action in ["上传", "下载", "重命名", "删除"]:
            QMessageBox.warning(package.widget, "操作", "请选择要编辑的文件")
            return

        # 获取操作对应的函数
        button_func = package.data.menu[select_action]
        standard_data = cls.fmt_pack(name=select_name,
                                     local_path=package.data.get_local_path(),
                                     remote_path=package.data.get_remote_path())
        button_func(standard_data)

    @classmethod
    def set_disk(cls, package):
        for i in package.data.disk_list:
            package.widget.addItem(i)

    @classmethod
    def clear_table_files(cls, package):
        if package.widget.rowCount() > 0:
            for row in range(package.widget.rowCount()):
                package.widget.removeRow(0)

    @classmethod
    def get_comboBox_first_item(cls, package):
        return package.widget.currentText()

    # def _get_sys_info(self):
    #     self.Local_Window_Sys = False
    #     if "Windows" in platform.platform():
    #         self.Local_Window_Sys = True
    #
    # def _get_server_info(self):
    #     self.Data_Socket.Conn.sendall(Tools.encode(dict(code=Protocol.GetSysInfo)))
    #     res = self.Data_Socket.Recv_Data_Queue.get()
    #     if res["data"].get("windows"):
    #         self.Remote_Window_Sys = True
    #     else:
    #         self.Remote_Window_Sys = False
    #
    # def closeEvent(self, event):
    #     event.accept()
    #     os._exit(0)
    #
    # # def keyPressEvent(self, event):
    # #     key = event.key()
    #     # if Qt.Key_A <= key <= Qt.Key_Z:
    #     #     if event.modifiers() & Qt.ShiftModifier:  # Shift 键被按下
    #     #         self.statusBar().showMessage('"Shift+%s" pressed' % chr(key), 500)
    #     #     elif event.modifiers() & Qt.ControlModifier:  # Ctrl 键被按下
    #     #         self.statusBar().showMessage('"Control+%s" pressed' % chr(key), 500)
    #     #     elif event.modifiers() & Qt.AltModifier:  # Alt 键被按下
    #     #         self.statusBar().showMessage('"Alt+%s" pressed' % chr(key), 500)
    #     #     else:
    #     #         self.statusBar().showMessage('"%s" pressed' % chr(key), 500)
    #     #
    #     # elif key == Qt.Key_Home:
    #     #     self.statusBar().showMessage('"Home" pressed', 500)
    #     # elif key == Qt.Key_End:
    #     #     self.statusBar().showMessage('"End" pressed', 500)
    #     # elif key == Qt.Key_PageUp:
    #     #     self.statusBar().showMessage('"PageUp" pressed', 500)
    #     # elif key == Qt.Key_PageDown:
    #     #     self.statusBar().showMessage('"PageDown" pressed', 500)
    #     # else:  # 其它未设定的情况
    #     #     QWidget.keyPressEvent(self, event)  # 留给基类处理
    #
    # def show_message_box(self, data):
    #     QMessageBox.warning(self, data["title"], data["msg"])
    #
    # def update_status(self, data):
    #     self.Progress.update_status(data["file_name"], data["send_detail"],  data["progress"])
    #     self.Progress.update_speed(data["speed"], data["elapsed_time"], data["remaining_time"])
    #     if data.get("update_widget"):
    #         QApplication.processEvents()
    #
    # def _init_local_table_disk(self):
    #     """初始化本地盘符"""
    #     device = Tools.get_drive()
    #     for i in device["device"]:
    #         self.LocalComboBox.addItem(i)
    #     self.local_path = device["device"][0]
    #     self.LocalComboBox.currentIndexChanged.connect(lambda x: self._chang_drive(Protocol.Local))
    #     # self.LocalComboBox.activated.connect(self._local_combobox_activated)
    #
    # # def _local_combobox_activated(self):
    # #     _root, _path = Tools.before_to_next(self.LocalComboBox.currentText(), windows=False)
    # #     if _root:
    # #         self.local_root = _root
    # #         self.local_path = _path
    # #         self.reload_local_files()
    # #     else:
    # #         print("无效路径%s" % self.LocalComboBox.currentText())
    #
    # def before_upload(self, data):
    #     """
    #     在上传文件之前查看是否选择了目录，如果是目录的话将递归创建目录与文件
    #     """
    #     create_root = False
    #     abs_path = os.path.join(data["path"], data["file_name"])
    #     if os.path.isdir(abs_path):    # 发送的是目录
    #         for home, dirs, files in os.walk(abs_path):
    #             remote_root = home
    #             remote_root = remote_root.replace(data["path"], self.remote_path)
    #             # # 先创建第一个目录
    #             if not create_root:
    #                 protocol = dict(code=Protocol.OsMkDir)
    #                 self.Data_Socket.Conn.sendall(Tools.encode(protocol, dict(item_name=os.path.join(os.path.basename(home)), path=self.remote_path)))
    #                 res = self.Data_Socket.Recv_Data_Queue.get()
    #                 print(f"创建 根目录 结果 {res['success']}")
    #                 create_root = True
    #             # 获得所有文件夹
    #             for dirname in dirs:
    #                 protocol = dict(code=Protocol.OsMkDir)
    #                 self.Data_Socket.Conn.sendall(Tools.encode(protocol, dict(item_name=dirname, path=remote_root)))
    #                 res = self.Data_Socket.Recv_Data_Queue.get()
    #                 print(f"创建 {home, dirname} 结果 {res['success']}")
    #                 time.sleep(0.1)
    #
    #             # 获得所有文件
    #             for filename in files:
    #                 time.sleep(0.1)
    #                 os.path.join(home, filename)
    #                 self.File_Socket.upload_file(dict(file_name=filename, path=home, write_path=remote_root, no_close=True))
    #                 time.sleep(0.1)
    #         self.File_Socket.Send_File.after_end.emit()
    #     else:
    #         self.File_Socket.upload_file(data)
    #
    # # def before_download(self):
    # #     """
    # #     在下载文件之前查看是否选择了目录，如果是目录的话将递归创建目录与文件
    # #     """
    #
    # def _init_file_table(self):
    #     # 设置本地表格右键功能
    #     local_button_func = {"上传": self.before_upload,
    #                          "刷新": self.reload_local_files,
    #                          "删除": FileIO.del_every,
    #                          "新建文件夹": self.Create_Dir.show_,
    #                          "重命名": self.Create_Dir.show_,
    #                          }
    #     local_table = (self.LocalFiles, self.LocalLastDir, local_button_func)
    #     self._add_table_attr(local_table)
    #     # 设置远程表格右键功能
    #     remote_button_func = {"下载": self.File_Socket.download_file,
    #                           "刷新": self.reload_server_files,
    #                           "删除": self.remove_server_item,
    #                           "新建文件夹": self.Create_Dir.show_,
    #                           "重命名": self.Create_Dir.show_,
    #                           }
    #     remote_table = (self.RemoteFiles, self.RemoteLastDir, remote_button_func)
    #     self._add_table_attr(remote_table)
    #
    #     # 加载本地根目录文件
    #     self.display_files(self.LocalFiles, FileIO.get_files(self.local_path,  sord_type=Config_Impl.Sort_Type))
    #     # 加载远程根目录文件
    #     self.display_files(self.RemoteFiles, self.get_server_files(self.remote_path)["data"])
    #
    # def _add_table_attr(self, data):
    #     item_table, last_button, button_func = data
    #     self.set_table_attr(item_table)
    #     # 绑定右击事件
    #     on_right_click = lambda x: self.set_right_key_menu(x, table_ojb=item_table, callback_map=button_func)
    #     item_table.customContextMenuRequested.connect(on_right_click)
    #     # 绑定双击事件
    #     item_table.doubleClicked.connect(lambda x: self._to_next_node(x, item_table))
    #     # 绑定返回上一级按钮事件
    #     last_func = lambda x: self._go_back(item_table)
    #     last_button.clicked.connect(last_func)
    #
    #
    #
    # def set_right_key_menu(self, pos, table_ojb, callback_map):
    #     """设置右键菜单"""
    #     try:
    #         row_num = table_ojb.selectionModel().selection().indexes()[0].row()
    #     except IndexError:
    #         Log.waring("选中了空文件")
    #         row_num = None
    #         # return
    #
    #     menu = QMenu()
    #     menu_map = dict()
    #     for option, func in callback_map.items():
    #         item_menu = menu.addAction(option)
    #         menu_map[item_menu] = func
    #     action = menu.exec_(table_ojb.mapToGlobal(pos))
    #     if "Local" in table_ojb.objectName():
    #         local = True
    #         path = self.local_path
    #     else:
    #         local = False
    #         path = self.remote_path
    #     if not action:
    #         print("未选择任何选项")
    #         return
    #     else:
    #         select = action.text()
    #     if row_num is None:
    #         select_name = ""
    #     else:
    #         select_name = table_ojb.item(row_num, 0).text()
    #     abs_path = os.path.join(path, select_name)
    #     func = callback_map.get(select, lambda : QMessageBox.warning(self.table_ojb, "警告", "未找到指定函数"))
    #     # 这些操作需要具体到对象， 必须检查是否选择某一项
    #     if row_num is None and select in ["上传", "下载", "重命名", "删除"]:
    #         QMessageBox.warning(self, "操作", "请选择要编辑的文件")
    #         return
    #
    #     if local:
    #         Log.debug("选中文件的绝对路径为%s" % abs_path)
    #         data = dict(item_name=select_name,
    #                     file_name=select_name,
    #                     write_path=self.remote_path,
    #                     path=path)
    #         if select == "上传":
    #             func(data)
    #         elif select == "删除":
    #             func(self, abs_path)
    #             self.reload_local_files()
    #         elif select == "新建文件夹":
    #             func(True, data, 1)
    #         elif select == "重命名":
    #             func(True, data, 2)
    #             self.reload_local_files()
    #         else:
    #             func(abs_path)
    #     # 操作服务端
    #     else:
    #
    #         data = dict(
    #                 path=self.remote_path,
    #                 item_name=select_name,  # item是编辑某一项的时候使用
    #                 file_name=select_name,  # file_name 是下载的时候使用
    #             )
    #         if select == "下载":
    #             data["write_path"] = self.local_path
    #             func(data)
    #         elif select == "新建文件夹":
    #             func(False, data, 1)
    #         elif select == "重命名":
    #             func(False, data, 2)
    #         else:
    #             func(data)
    #
    # def get_local_cur_list(self):
    #     return FileIO.get_files(self.local_path)
    #
    # def get_local_cur_path(self, join_path=""):
    #     res = self.local_path
    #     if join_path:
    #         res = os.path.join(res, join_path)
    #     return res
    #
    # def reload_local_files(self, *args, **kwargs):
    #     return self.display_files(self.LocalFiles, self.get_local_cur_list())
    #
    # def ready_reload_files(self, data):
    #     is_local = data["is_local"]
    #     if is_local:
    #         self.reload_local_files()
    #     else:
    #        self.reload_server_files()
    #
    # def _chang_drive(self, _from):
    #     if _from == Protocol.Local:
    #         self._change_dir(self.LocalFiles, self.LocalComboBox.currentText())
    #     else:
    #         self._change_dir(self.RemoteFiles, self.RemoteComboBox.currentText())
    #
    # def _to_next_node(self, evt, f_widget):
    #     file_type = f_widget.item(f_widget.currentRow(), 2).text()
    #     click_name = f_widget.item(f_widget.currentRow(), 0).text()
    #     next_path = os.path.join(self.get_path(f_widget), click_name).replace("\\", "/")
    #     if file_type == "File Folder" or file_type == "Folder":
    #         self._change_dir(f_widget, next_path)
    #     else:
    #         if "Local" in f_widget.objectName():
    #             print("打开%s" % next_path)
    #             os.system(next_path)
    #         else:
    #             QMessageBox.warning(self.RemoteFiles, '提示', '不能打开远程文件')
    #
    # def _change_dir(self, f_widget, path):
    #     print("***********************", path)
    #     if "Local" in f_widget.objectName():
    #         data = FileIO.get_files(path)
    #         self.display_files(f_widget, data)
    #         self.local_path = path
    #         Log.debug("访问本地下一级 %s" % path)
    #         self.LocalComboBox.setItemText(self.LocalComboBox.currentIndex(), path)
    #     else:
    #         data = self.get_server_files(path)
    #         self.display_files(f_widget, data["data"])
    #         self.remote_path = path
    #         self.RemoteComboBox.setItemText(self.RemoteComboBox.currentIndex(), path)
    #         Log.debug("访问服务器下一级 %s" % path)
    #
    # def _go_back(self, f_widget):
    #     cur_path = self.get_path(f_widget)
    #     last_path = os.path.dirname(cur_path)
    #     if "/" not in last_path:
    #         last_path += "/"
    #     self._change_dir(f_widget, last_path)
    #
    # def get_path(self, q_obj):
    #     return self.local_path if "Local" in q_obj.objectName() else self.remote_path
    #
    # # ================================下面是操作服务器方法===============================#
    # def get_server_files(self, path=str(), select_item=str()):
    #     """同步 获取服务器目录"""
    #     data = self.Data_Socket.get_server_files(path, select_item)
    #     return data
    #
    # def get_server_cur_path(self):
    #     return os.path.join(self.remote_root, self.remote_path)
    #
    #
    # def _init_remote_table_disk(self):
    #     """初始化服务器盘符"""
    #     server_drive = self.Data_Socket.get_server_drive()
    #     for i in server_drive["data"]["device"]:
    #         self.RemoteComboBox.addItem(i)
    #     self.RemoteComboBox.currentIndexChanged.connect(lambda x: self._chang_drive(Protocol.Server))
    #     self.remote_path = server_drive["data"]["device"][0]
    #
    # def reload_server_files(self, *args, **kwargs):
    #     self.display_files(self.RemoteFiles, self.get_server_files(self.remote_path)["data"])
    #
    # def remove_server_item(self, data, *args, **kwargs):
    #     res = QMessageBox.question(self, "删除", "确认删除？", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
    #     if res == QMessageBox.Yes:
    #         del_res = self.Data_Socket.del_server_item(data)
    #         if not del_res["success"]:
    #             QMessageBox.warning(self, "删除", del_res["message"])
    #         else:
    #             self.display_files(self.RemoteFiles, del_res["data"])
    #
    # def mk_server_dir(self, data, *args, **kwargs):
    #     protocol = dict(code=Protocol.OsMkDir)
    #     self.Data_Socket.Conn.sendall(Tools.encode(protocol, data))
    #     res = self.Data_Socket.Recv_Data_Queue.get()
    #     if res["success"]:
    #         self.display_files(self.RemoteFiles, res["data"])
    #         self.Create_Dir.hide_()
    #     else:
    #         QMessageBox.warning(self, "创建文件夹", res["message"])
    #
    # def rename_server_item(self, data):
    #     protocol = dict(code=Protocol.OsReName)
    #     self.Data_Socket.Conn.sendall(Tools.encode(protocol, data))
    #     res = self.Data_Socket.Recv_Data_Queue.get()
    #     if res["success"]:
    #         self.Create_Dir.hide_()
    #         self.display_files(self.RemoteFiles, res['data'])
    #     else:
    #         QMessageBox.warning(self, "重命名", res["message"])
