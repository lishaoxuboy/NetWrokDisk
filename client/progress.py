# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'progress.ui'
#
# Created by: PyQt5 UI code generator 5.11.3
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_transfer(object):
    def setupUi(self, transfer):
        transfer.setObjectName("transfer")
        transfer.resize(539, 130)
        transfer.setMinimumSize(QtCore.QSize(500, 120))
        transfer.setMaximumSize(QtCore.QSize(999999, 999999))
        self.gridLayout = QtWidgets.QGridLayout(transfer)
        self.gridLayout.setObjectName("gridLayout")
        self.operation = QtWidgets.QLabel(transfer)
        self.operation.setMaximumSize(QtCore.QSize(16777215, 16777215))
        self.operation.setObjectName("operation")
        self.gridLayout.addWidget(self.operation, 0, 0, 1, 1)
        self.name = QtWidgets.QLabel(transfer)
        self.name.setMaximumSize(QtCore.QSize(16777215, 16777215))
        self.name.setText("")
        self.name.setObjectName("name")
        self.gridLayout.addWidget(self.name, 0, 1, 1, 5)
        self.progress = QtWidgets.QProgressBar(transfer)
        self.progress.setMinimumSize(QtCore.QSize(0, 31))
        self.progress.setProperty("value", 24)
        self.progress.setObjectName("progress")
        self.gridLayout.addWidget(self.progress, 1, 0, 1, 6)
        self.lable_1 = QtWidgets.QLabel(transfer)
        self.lable_1.setMaximumSize(QtCore.QSize(50, 16777215))
        font = QtGui.QFont()
        font.setBold(True)
        font.setWeight(75)
        self.lable_1.setFont(font)
        self.lable_1.setObjectName("lable_1")
        self.gridLayout.addWidget(self.lable_1, 3, 0, 1, 1)
        self.elapsed_time = QtWidgets.QLabel(transfer)
        self.elapsed_time.setMaximumSize(QtCore.QSize(16777215, 16777215))
        self.elapsed_time.setObjectName("elapsed_time")
        self.gridLayout.addWidget(self.elapsed_time, 3, 1, 1, 1)
        self.remaining_time = QtWidgets.QLabel(transfer)
        self.remaining_time.setMaximumSize(QtCore.QSize(16777215, 16777215))
        self.remaining_time.setObjectName("remaining_time")
        self.gridLayout.addWidget(self.remaining_time, 3, 3, 1, 1)
        self.lable_3 = QtWidgets.QLabel(transfer)
        self.lable_3.setMaximumSize(QtCore.QSize(40, 16777215))
        font = QtGui.QFont()
        font.setBold(True)
        font.setWeight(75)
        self.lable_3.setFont(font)
        self.lable_3.setObjectName("lable_3")
        self.gridLayout.addWidget(self.lable_3, 3, 4, 1, 1)
        self.speed = QtWidgets.QLabel(transfer)
        self.speed.setMaximumSize(QtCore.QSize(16777215, 16777215))
        self.speed.setObjectName("speed")
        self.gridLayout.addWidget(self.speed, 3, 5, 1, 1)
        self.lable_2 = QtWidgets.QLabel(transfer)
        self.lable_2.setMaximumSize(QtCore.QSize(55, 16777215))
        font = QtGui.QFont()
        font.setBold(True)
        font.setWeight(75)
        self.lable_2.setFont(font)
        self.lable_2.setObjectName("lable_2")
        self.gridLayout.addWidget(self.lable_2, 3, 2, 1, 1)
        self.detail = QtWidgets.QLabel(transfer)
        self.detail.setMinimumSize(QtCore.QSize(150, 0))
        self.detail.setMaximumSize(QtCore.QSize(200, 16777215))
        self.detail.setObjectName("detail")
        self.gridLayout.addWidget(self.detail, 2, 5, 1, 1)

        self.retranslateUi(transfer)
        QtCore.QMetaObject.connectSlotsByName(transfer)

    def retranslateUi(self, transfer):
        _translate = QtCore.QCoreApplication.translate
        transfer.setWindowTitle(_translate("transfer", "Form"))
        self.operation.setText(_translate("transfer", "发送文件"))
        self.lable_1.setText(_translate("transfer", "已用时:"))
        self.elapsed_time.setText(_translate("transfer", "00:00:00"))
        self.remaining_time.setText(_translate("transfer", "00:00:00"))
        self.lable_3.setText(_translate("transfer", "速度:"))
        self.speed.setText(_translate("transfer", "0MB/s"))
        self.lable_2.setText(_translate("transfer", "预计用时:"))
        self.detail.setText(_translate("transfer", "0MB/0MB"))

