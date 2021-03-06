# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'progress.ui'
#
# Created by: PyQt5 UI code generator 5.15.2
#
# WARNING: Any manual changes made to this file will be lost when pyuic5 is
# run again.  Do not edit this file unless you know what you are doing.


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_transfer(object):
    def setupUi(self, transfer):
        transfer.setObjectName("transfer")
        transfer.resize(500, 120)
        transfer.setMinimumSize(QtCore.QSize(500, 120))
        transfer.setMaximumSize(QtCore.QSize(999999, 999999))
        self.gridLayout = QtWidgets.QGridLayout(transfer)
        self.gridLayout.setObjectName("gridLayout")
        self.progress = QtWidgets.QProgressBar(transfer)
        self.progress.setMinimumSize(QtCore.QSize(0, 31))
        self.progress.setProperty("value", 24)
        self.progress.setObjectName("progress")
        self.gridLayout.addWidget(self.progress, 2, 0, 1, 7)
        self.elapsed_time_2 = QtWidgets.QLabel(transfer)
        self.elapsed_time_2.setObjectName("elapsed_time_2")
        self.gridLayout.addWidget(self.elapsed_time_2, 3, 0, 1, 1)
        self.elapsed_time = QtWidgets.QLabel(transfer)
        self.elapsed_time.setText("")
        self.elapsed_time.setObjectName("elapsed_time")
        self.gridLayout.addWidget(self.elapsed_time, 3, 1, 1, 1)
        self.remaining_time_2 = QtWidgets.QLabel(transfer)
        self.remaining_time_2.setObjectName("remaining_time_2")
        self.gridLayout.addWidget(self.remaining_time_2, 3, 2, 1, 1)
        self.remaining_time = QtWidgets.QLabel(transfer)
        self.remaining_time.setText("")
        self.remaining_time.setObjectName("remaining_time")
        self.gridLayout.addWidget(self.remaining_time, 3, 3, 1, 1)
        self.speed_2 = QtWidgets.QLabel(transfer)
        self.speed_2.setObjectName("speed_2")
        self.gridLayout.addWidget(self.speed_2, 3, 4, 1, 1)
        self.speed = QtWidgets.QLabel(transfer)
        self.speed.setText("")
        self.speed.setObjectName("speed")
        self.gridLayout.addWidget(self.speed, 3, 5, 1, 1)
        self.speed_3 = QtWidgets.QLabel(transfer)
        self.speed_3.setText("")
        self.speed_3.setObjectName("speed_3")
        self.gridLayout.addWidget(self.speed_3, 3, 6, 1, 1)
        self.file_name_2 = QtWidgets.QLabel(transfer)
        self.file_name_2.setMaximumSize(QtCore.QSize(16777215, 16777215))
        self.file_name_2.setObjectName("file_name_2")
        self.gridLayout.addWidget(self.file_name_2, 0, 0, 2, 1)
        self.file_name = QtWidgets.QLabel(transfer)
        self.file_name.setMaximumSize(QtCore.QSize(16777215, 16777215))
        self.file_name.setText("")
        self.file_name.setObjectName("file_name")
        self.gridLayout.addWidget(self.file_name, 0, 1, 2, 6)

        self.retranslateUi(transfer)
        QtCore.QMetaObject.connectSlotsByName(transfer)

    def retranslateUi(self, transfer):
        _translate = QtCore.QCoreApplication.translate
        transfer.setWindowTitle(_translate("transfer", "Form"))
        self.elapsed_time_2.setText(_translate("transfer", "已用时:"))
        self.remaining_time_2.setText(_translate("transfer", "预计用时:"))
        self.speed_2.setText(_translate("transfer", "平均速度:"))
        self.file_name_2.setText(_translate("transfer", "文件名字:"))
