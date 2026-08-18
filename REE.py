# -*- coding: utf-8 -*-
"""
稀土元素（REE）标准化图解工具
- 支持多种标准化方案（C1球粒陨石、Taylor、Haskin、Nakamura、MORB、UCC）
- 自动计算δEu、δCe、(La/Yb)N等参数
- 交互式样式编辑，配置自动保存
"""

import sys
import json
import os
import math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.patches import Polygon
from matplotlib.lines import Line2D
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QLabel, QComboBox, QSpinBox,
    QCheckBox, QLineEdit, QStatusBar, QMessageBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QDialog, QGroupBox, QGridLayout
)
from PySide6.QtCore import Qt

# ================== 常量定义 ==================
CONFIG_FILE = "ree_config.json"

ELEMENTS = ['La', 'Ce', 'Pr', 'Nd', 'Sm', 'Eu', 'Gd', 'Tb', 'Dy', 'Ho', 'Er', 'Tm', 'Yb', 'Lu']

# 标准化标准（来自 REE.py）
STANDARDS = {
    'C1 Chondrite Sun and McDonough,1989': {
        'La': 0.237, 'Ce': 0.612, 'Pr': 0.095, 'Nd': 0.467, 'Sm': 0.153,
        'Eu': 0.058, 'Gd': 0.2055, 'Tb': 0.0374, 'Dy': 0.254, 'Ho': 0.0566,
        'Er': 0.1655, 'Tm': 0.0255, 'Yb': 0.17, 'Lu': 0.0254
    },
    'Chondrite Taylor and McLennan,1985': {
        'La': 0.367, 'Ce': 0.957, 'Pr': 0.137, 'Nd': 0.711, 'Sm': 0.231,
        'Eu': 0.087, 'Gd': 0.306, 'Tb': 0.058, 'Dy': 0.381, 'Ho': 0.0851,
        'Er': 0.249, 'Tm': 0.0356, 'Yb': 0.248, 'Lu': 0.0381
    },
    'Chondrite Haskin et al.,1966': {
        'La': 0.32, 'Ce': 0.787, 'Pr': 0.112, 'Nd': 0.58, 'Sm': 0.185,
        'Eu': 0.071, 'Gd': 0.256, 'Tb': 0.05, 'Dy': 0.343, 'Ho': 0.07,
        'Er': 0.225, 'Tm': 0.03, 'Yb': 0.186, 'Lu': 0.034
    },
    'Chondrite Nakamura,1977': {
        'La': 0.33, 'Ce': 0.865, 'Pr': 0.112, 'Nd': 0.63, 'Sm': 0.203,
        'Eu': 0.077, 'Gd': 0.276, 'Tb': 0.047, 'Dy': 0.343, 'Ho': 0.07,
        'Er': 0.225, 'Tm': 0.03, 'Yb': 0.22, 'Lu': 0.034
    },
    'MORB Sun and McDonough,1989': {
        'La': 2.5, 'Ce': 7.5, 'Pr': 1.32, 'Nd': 7.3, 'Sm': 2.63,
        'Eu': 1.02, 'Gd': 3.68, 'Tb': 0.67, 'Dy': 4.55, 'Ho': 1.052,
        'Er': 2.97, 'Tm': 0.46, 'Yb': 3.05, 'Lu': 0.46
    },
    'UCC_Rudnick & Gao2003': {
        'La': 31, 'Ce': 63, 'Pr': 7.1, 'Nd': 27, 'Sm': 4.7,
        'Eu': 1, 'Gd': 4, 'Tb': 0.7, 'Dy': 3.9, 'Ho': 0.83,
        'Er': 2.3, 'Tm': 0.3, 'Yb': 1.96, 'Lu': 0.31
    }
}

STANDARD_NAMES = list(STANDARDS.keys())

# 颜色与标记映射（与 tas2 一致）
COLOR_MAP = {
    '红色': 'red', '蓝色': 'blue', '绿色': 'green', '紫色': 'purple',
    '橙色': 'orange', '棕色': 'brown', '粉色': 'pink', '灰色': 'gray',
    '青色': 'cyan', '深红': 'darkred', '深绿': 'darkgreen', '黑色': 'black'
}
MARKER_MAP = {
    '圆': 'o', '方': 's', '三角': '^', '菱形': 'D', '倒三角': 'v',
    '五角星': '*', '叉': 'x', '左三角': '<', '右三角': '>',
    '加号': '+', '竖线': '|', '横线': '_'
}

# ================== 配置管理 ==================
class ConfigManager:
    def __init__(self, filename=CONFIG_FILE):
        self.filename = filename
        self.default_config = {
            "dpi": 300,
            "standard": STANDARD_NAMES[0],
            "col_label": "",
            "show_labels": False,
            "sample_styles": {},
            "main_title": {"text": "稀土元素标准化图解", "font": "SimHei", "size": 16, "x_offset": 0, "y_offset": 0.02},
            "xlabel": {"text": "元素", "font": "SimHei", "size": 12, "x_offset": 0, "y_offset": 0},
            "ylabel": {"text": "样品/标准 (log10)", "font": "SimHei", "size": 12, "x_offset": 0, "y_offset": 0},
            "legend": {"font": "SimHei", "size": 10, "color": "black", "x_offset": 0, "y_offset": 0, "markersize": 10},
        }
        # 为每个元素添加可编辑的显示名称（默认即元素符号）
        for elem in ELEMENTS:
            self.default_config[elem] = {"text": elem, "font": "SimHei", "size": 10, "x_offset": 0, "y_offset": 0}
        self.config = self.load()

    def load(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 补全缺失项
                    for key, val in self.default_config.items():
                        if key not in data:
                            data[key] = val.copy()
                        elif isinstance(val, dict):
                            for subkey, subval in val.items():
                                if subkey not in data[key]:
                                    data[key][subkey] = subval
                    if "sample_styles" not in data:
                        data["sample_styles"] = {}
                    return data
            except Exception:
                return self.default_config.copy()
        else:
            return self.default_config.copy()

    def save(self):
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print("保存配置失败:", e)

    def reset(self):
        self.config = self.default_config.copy()
        self.save()

    def get_element(self, key):
        return self.config.get(key, {})

    def set_element(self, key, prop, value):
        if key not in self.config:
            self.config[key] = {}
        self.config[key][prop] = value
        self.save()

    def get_sample_style(self, category):
        styles = self.config.get("sample_styles", {})
        default = {"marker": "o", "color": "red", "size": 60, "zorder": 10}
        style = styles.get(category, default.copy())
        if "zorder" not in style:
            style["zorder"] = 10
        return style

    def set_sample_style(self, category, style_dict):
        styles = self.config.get("sample_styles", {})
        styles[category] = style_dict
        self.config["sample_styles"] = styles
        self.save()

    def has_sample_style(self, category):
        return category in self.config.get("sample_styles", {})

# ================== 计算结果表格对话框 ==================
class ResultTableDialog(QDialog):
    def __init__(self, data_frame, parent=None):
        super().__init__(parent)
        self.setWindowTitle("REE 计算结果")
        self.setModal(True)
        self.resize(1000, 600)
        layout = QVBoxLayout(self)
        table = QTableWidget()
        table.setAlternatingRowColors(True)
        table.setSortingEnabled(False)
        layout.addWidget(table)

        if data_frame is not None and not data_frame.empty:
            table.setRowCount(data_frame.shape[0])
            table.setColumnCount(data_frame.shape[1])
            table.setHorizontalHeaderLabels(data_frame.columns.tolist())
            for i, (_, row) in enumerate(data_frame.iterrows()):
                for j, val in enumerate(row):
                    item = QTableWidgetItem(str(val))
                    item.setTextAlignment(Qt.AlignCenter)
                    table.setItem(i, j, item)
            table.resizeColumnsToContents()
            table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        else:
            table.setRowCount(0)
            table.setColumnCount(1)
            table.setHorizontalHeaderLabels(["无数据"])

        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

# ================== 主窗口 ==================
class REEWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("稀土元素（REE）标准化图解")
        self.setGeometry(50, 50, 1200, 850)

        self.config = ConfigManager()
        self.current_df = None
        self.file_path = None
        self.sample_categories = []
        self.result_df = None  # 存储计算结果用于显示

        # 字体映射
        self.font_map = {
            "黑体": "SimHei", "宋体": "SimSun", "楷体": "KaiTi",
            "仿宋": "FangSong", "微软雅黑": "Microsoft YaHei",
            "Arial": "Arial", "Times New Roman": "Times New Roman"
        }
        self.font_display_to_family = self.font_map
        self.font_family_to_display = {v: k for k, v in self.font_map.items()}

        self.current_edit_type = "none"
        self.current_element_key = None
        self.current_sample_category = None

        # 主容器
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(4)
        main_layout.setContentsMargins(6, 6, 6, 6)

        # ---------- 第一行：文件操作、标准选择、DPI、刷新、保存、复位 ----------
        row1 = QHBoxLayout()
        row1.setSpacing(4)

        self.btn_open = QPushButton("打开文件")
        self.btn_open.setFixedWidth(90)
        self.btn_open.clicked.connect(self.open_file)
        row1.addWidget(self.btn_open)

        self.label_status = QLabel("请选择数据文件")
        row1.addWidget(self.label_status, 1)

        row1.addWidget(QLabel("标准化:"))
        self.cb_standard = QComboBox()
        self.cb_standard.addItems(STANDARD_NAMES)
        self.cb_standard.setCurrentText(self.config.config.get("standard", STANDARD_NAMES[0]))
        self.cb_standard.currentTextChanged.connect(self.on_standard_changed)
        self.cb_standard.setFixedWidth(200)
        row1.addWidget(self.cb_standard)

        row1.addWidget(QLabel("DPI:"))
        self.spin_dpi = QSpinBox()
        self.spin_dpi.setRange(72, 1200)
        self.spin_dpi.setValue(self.config.config.get("dpi", 300))
        self.spin_dpi.valueChanged.connect(lambda v: self.config.set_element("dpi", None, v) if False else None)
        # 直接用config保存
        self.spin_dpi.valueChanged.connect(self.on_dpi_changed)
        self.spin_dpi.setFixedWidth(70)
        row1.addWidget(self.spin_dpi)

        self.btn_refresh = QPushButton("刷新")
        self.btn_refresh.setFixedWidth(60)
        self.btn_refresh.clicked.connect(self.redraw)
        row1.addWidget(self.btn_refresh)

        self.btn_save_img = QPushButton("保存图片")
        self.btn_save_img.setFixedWidth(80)
        self.btn_save_img.clicked.connect(self.save_image)
        row1.addWidget(self.btn_save_img)

        self.btn_reset = QPushButton("复位")
        self.btn_reset.setFixedWidth(60)
        self.btn_reset.clicked.connect(self.reset_all)
        row1.addWidget(self.btn_reset)

        main_layout.addLayout(row1)

        # ---------- 第二行：标签列、显示标签、应用列、计算结果按钮 ----------
        row2 = QHBoxLayout()
        row2.setSpacing(4)
        row2.addWidget(QLabel("标签列:"))
        self.cb_label = QComboBox()
        self.cb_label.setMinimumWidth(120)
        row2.addWidget(self.cb_label)

        self.cb_show_labels = QCheckBox("显示标签")
        self.cb_show_labels.setChecked(self.config.config.get("show_labels", False))
        self.cb_show_labels.stateChanged.connect(self.on_show_labels_toggle)
        row2.addWidget(self.cb_show_labels)

        self.btn_apply = QPushButton("应用列")
        self.btn_apply.setFixedWidth(70)
        self.btn_apply.clicked.connect(self.apply_column_selection)
        row2.addWidget(self.btn_apply)

        self.btn_result = QPushButton("显示计算结果")
        self.btn_result.setFixedWidth(100)
        self.btn_result.clicked.connect(self.show_result_table)
        row2.addWidget(self.btn_result)

        row2.addStretch(1)
        main_layout.addLayout(row2)

        # ---------- 第三行：编辑对象（元素/标题/轴）和编辑投影点（类别） ----------
        row3 = QHBoxLayout()
        row3.setSpacing(4)

        row3.addWidget(QLabel("编辑对象:"))
        self.cb_element = QComboBox()
        self.cb_element.setMinimumWidth(150)
        self.cb_element.currentIndexChanged.connect(self.on_element_changed)
        row3.addWidget(self.cb_element)

        row3.addWidget(QLabel("编辑投影点:"))
        self.cb_sample = QComboBox()
        self.cb_sample.setMinimumWidth(150)
        self.cb_sample.currentIndexChanged.connect(self.on_sample_changed)
        row3.addWidget(self.cb_sample)

        row3.addStretch(1)
        main_layout.addLayout(row3)

        # ---------- 第四行：属性控件 ----------
        row4 = QHBoxLayout()
        row4.setSpacing(4)

        self.edit_text = QLineEdit()
        self.edit_text.setPlaceholderText("文本...")
        self.edit_text.setMinimumWidth(120)
        self.edit_text.textChanged.connect(self.on_text_changed)
        self.edit_text.setVisible(False)
        row4.addWidget(self.edit_text)

        row4.addWidget(QLabel("字体:"))
        self.cb_font = QComboBox()
        for display_name in self.font_map.keys():
            self.cb_font.addItem(display_name)
        self.cb_font.currentTextChanged.connect(self.on_font_changed)
        self.cb_font.setFixedWidth(90)
        self.cb_font.setVisible(False)
        row4.addWidget(self.cb_font)

        row4.addWidget(QLabel("大小:"))
        self.spin_size = QSpinBox()
        self.spin_size.setRange(6, 30)
        self.spin_size.valueChanged.connect(self.on_size_changed)
        self.spin_size.setFixedWidth(60)
        self.spin_size.setVisible(False)
        row4.addWidget(self.spin_size)

        row4.addWidget(QLabel("X偏移:"))
        self.spin_x = QSpinBox()
        self.spin_x.setRange(-100, 100)
        self.spin_x.valueChanged.connect(self.on_x_changed)
        self.spin_x.setFixedWidth(60)
        self.spin_x.setVisible(False)
        row4.addWidget(self.spin_x)

        row4.addWidget(QLabel("Y偏移:"))
        self.spin_y = QSpinBox()
        self.spin_y.setRange(-100, 100)
        self.spin_y.valueChanged.connect(self.on_y_changed)
        self.spin_y.setFixedWidth(60)
        self.spin_y.setVisible(False)
        row4.addWidget(self.spin_y)

        self.cb_color = QComboBox()
        self.cb_color.addItems(COLOR_MAP.keys())
        self.cb_color.currentIndexChanged.connect(self.on_color_changed)
        self.cb_color.setFixedWidth(70)
        self.cb_color.setVisible(False)
        row4.addWidget(QLabel("颜色:"))
        row4.addWidget(self.cb_color)

        self.label_marker = QLabel("标记:")
        self.cb_marker = QComboBox()
        self.cb_marker.addItems(MARKER_MAP.keys())
        self.cb_marker.currentIndexChanged.connect(self.on_marker_changed)
        self.cb_marker.setFixedWidth(70)
        self.label_marker.setVisible(False)
        self.cb_marker.setVisible(False)
        row4.addWidget(self.label_marker)
        row4.addWidget(self.cb_marker)

        self.label_size = QLabel("点大小:")
        self.spin_point_size = QSpinBox()
        self.spin_point_size.setRange(5, 200)
        self.spin_point_size.setValue(60)
        self.spin_point_size.valueChanged.connect(self.on_point_size_changed)
        self.spin_point_size.setFixedWidth(60)
        self.label_size.setVisible(False)
        self.spin_point_size.setVisible(False)
        row4.addWidget(self.label_size)
        row4.addWidget(self.spin_point_size)

        self.label_zorder = QLabel("Z值:")
        self.spin_zorder = QSpinBox()
        self.spin_zorder.setRange(1, 100)
        self.spin_zorder.setValue(10)
        self.spin_zorder.valueChanged.connect(self.on_zorder_changed)
        self.spin_zorder.setFixedWidth(60)
        self.label_zorder.setVisible(False)
        self.spin_zorder.setVisible(False)
        row4.addWidget(self.label_zorder)
        row4.addWidget(self.spin_zorder)

        row4.addStretch(1)
        main_layout.addLayout(row4)

        # ---------- 绘图区域 ----------
        self.figure = Figure(figsize=(10, 7))
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setParent(central)
        main_layout.addWidget(self.canvas)

        # 状态栏
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("就绪")

        # 初始化下拉列表
        self.populate_element_list()
        self.populate_sample_list()
        self.set_edit_state("none")
        self.redraw()

    # ========== 下拉列表填充 ==========
    def populate_element_list(self):
        self.cb_element.clear()
        self.cb_element.addItem("无", None)
        # 主标题、轴标签、图例
        for key in ["main_title", "xlabel", "ylabel", "legend"]:
            display = self.config.get_element(key).get("text", key) if key != "legend" else "图例"
            self.cb_element.addItem(display, key)
        # 各个元素
        for elem in ELEMENTS:
            display = self.config.get_element(elem).get("text", elem)
            self.cb_element.addItem(f"元素:{display}", elem)

    def populate_sample_list(self):
        self.cb_sample.clear()
        self.cb_sample.addItem("无", None)
        for cat in self.sample_categories:
            self.cb_sample.addItem(cat, cat)

    def set_edit_state(self, state, key=None, category=None):
        self.current_edit_type = state
        if state == "element":
            self.current_element_key = key
            self.current_sample_category = None
            idx = self.cb_sample.findData(None)
            if idx >= 0:
                self.cb_sample.blockSignals(True)
                self.cb_sample.setCurrentIndex(idx)
                self.cb_sample.blockSignals(False)
        elif state == "sample":
            self.current_sample_category = category
            self.current_element_key = None
            idx = self.cb_element.findData(None)
            if idx >= 0:
                self.cb_element.blockSignals(True)
                self.cb_element.setCurrentIndex(idx)
                self.cb_element.blockSignals(False)
        else:
            self.current_element_key = None
            self.current_sample_category = None
        self.update_controls()

    def update_controls(self):
        # 全部隐藏
        for w in [self.edit_text, self.cb_font, self.spin_size, self.spin_x, self.spin_y,
                  self.cb_color, self.label_marker, self.cb_marker,
                  self.label_size, self.spin_point_size, self.label_zorder, self.spin_zorder]:
            w.setVisible(False)

        if self.current_edit_type == "none":
            return

        if self.current_edit_type == "element":
            key = self.current_element_key
            if key is None:
                return
            elem = self.config.get_element(key)
            # 显示字体、大小、偏移（所有都支持）
            self.cb_font.setVisible(True)
            self.spin_size.setVisible(True)
            self.spin_x.setVisible(True)
            self.spin_y.setVisible(True)
            # 根据类型显示额外控件
            if key == "legend":
                self.cb_color.setVisible(True)
                self.cb_color.setCurrentText(self.get_color_name(elem.get("color", "black")))
                self.label_size.setVisible(True)
                self.spin_point_size.setVisible(True)
                self.spin_point_size.setValue(elem.get("markersize", 10))
                self.label_size.setText("图例符号大小:")
                self.edit_text.setVisible(False)  # 图例无文本编辑
            elif key in ["main_title", "xlabel", "ylabel"]:
                self.edit_text.setVisible(True)
                self.edit_text.setText(elem.get("text", ""))
                # 颜色、标记、点大小不显示
            else:  # 元素分区
                self.edit_text.setVisible(True)
                self.edit_text.setText(elem.get("text", key))
                # 颜色、标记等不显示
            # 设置当前值
            self.cb_font.setCurrentText(self.font_family_to_display.get(elem.get("font", "SimHei"), "黑体"))
            self.spin_size.setValue(elem.get("size", 10))
            self.spin_x.setValue(int(elem.get("x_offset", 0) * 100))
            self.spin_y.setValue(int(elem.get("y_offset", 0) * 100))
            return

        elif self.current_edit_type == "sample":
            category = self.current_sample_category
            if category is None:
                return
            style = self.config.get_sample_style(category)
            self.label_marker.setVisible(True)
            self.cb_marker.setVisible(True)
            self.cb_marker.setCurrentText(self.get_marker_name(style.get("marker", "o")))
            self.cb_color.setVisible(True)
            self.cb_color.setCurrentText(self.get_color_name(style.get("color", "red")))
            self.label_size.setVisible(True)
            self.spin_point_size.setVisible(True)
            self.spin_point_size.setValue(style.get("size", 60))
            self.label_size.setText("点大小:")
            self.label_zorder.setVisible(True)
            self.spin_zorder.setVisible(True)
            self.spin_zorder.setValue(style.get("zorder", 10))
            # 不显示字体、偏移等
            return

    # ========== 下拉事件 ==========
    def on_element_changed(self, index):
        key = self.cb_element.currentData()
        if key is None:
            self.set_edit_state("none")
            return
        # 如果之前是 sample，取消选择
        if self.current_edit_type == "sample":
            idx = self.cb_sample.findData(None)
            if idx >= 0:
                self.cb_sample.blockSignals(True)
                self.cb_sample.setCurrentIndex(idx)
                self.cb_sample.blockSignals(False)
        self.set_edit_state("element", key=key)

    def on_sample_changed(self, index):
        category = self.cb_sample.currentData()
        if category is None:
            self.set_edit_state("none")
            return
        if self.current_edit_type == "element":
            idx = self.cb_element.findData(None)
            if idx >= 0:
                self.cb_element.blockSignals(True)
                self.cb_element.setCurrentIndex(idx)
                self.cb_element.blockSignals(False)
        self.set_edit_state("sample", category=category)

    # ========== 属性控件事件 ==========
    def on_text_changed(self, text):
        if self.current_edit_type == "element" and self.current_element_key is not None:
            key = self.current_element_key
            if key in ["main_title", "xlabel", "ylabel"] or key in ELEMENTS:
                self.config.set_element(key, "text", text)
                self.redraw()

    def on_font_changed(self, display_name):
        if self.current_edit_type == "element" and self.current_element_key is not None:
            key = self.current_element_key
            family = self.font_display_to_family.get(display_name, "SimHei")
            self.config.set_element(key, "font", family)
            self.redraw()

    def on_size_changed(self, val):
        if self.current_edit_type == "element" and self.current_element_key is not None:
            key = self.current_element_key
            self.config.set_element(key, "size", val)
            self.redraw()

    def on_x_changed(self, val):
        if self.current_edit_type == "element" and self.current_element_key is not None:
            key = self.current_element_key
            offset = val / 100.0
            self.config.set_element(key, "x_offset", offset)
            self.redraw()

    def on_y_changed(self, val):
        if self.current_edit_type == "element" and self.current_element_key is not None:
            key = self.current_element_key
            offset = val / 100.0
            self.config.set_element(key, "y_offset", offset)
            self.redraw()

    def on_color_changed(self, idx):
        if self.current_edit_type == "element" and self.current_element_key == "legend":
            color_code = COLOR_MAP.get(self.cb_color.currentText(), "black")
            self.config.set_element("legend", "color", color_code)
            self.redraw()
        elif self.current_edit_type == "sample" and self.current_sample_category:
            category = self.current_sample_category
            color_code = COLOR_MAP.get(self.cb_color.currentText(), "red")
            style = self.config.get_sample_style(category)
            style["color"] = color_code
            self.config.set_sample_style(category, style)
            self.redraw()

    def on_marker_changed(self, idx):
        if self.current_edit_type == "sample" and self.current_sample_category:
            category = self.current_sample_category
            marker_symbol = MARKER_MAP.get(self.cb_marker.currentText(), "o")
            style = self.config.get_sample_style(category)
            style["marker"] = marker_symbol
            self.config.set_sample_style(category, style)
            self.redraw()

    def on_point_size_changed(self, val):
        if self.current_edit_type == "element" and self.current_element_key == "legend":
            self.config.set_element("legend", "markersize", val)
            self.redraw()
        elif self.current_edit_type == "sample" and self.current_sample_category:
            category = self.current_sample_category
            style = self.config.get_sample_style(category)
            style["size"] = val
            self.config.set_sample_style(category, style)
            self.redraw()

    def on_zorder_changed(self, val):
        if self.current_edit_type == "sample" and self.current_sample_category:
            category = self.current_sample_category
            style = self.config.get_sample_style(category)
            style["zorder"] = val
            self.config.set_sample_style(category, style)
            self.redraw()

    # ========== 其他事件 ==========
    def on_standard_changed(self, text):
        self.config.config["standard"] = text
        self.config.save()
        self.redraw()

    def on_show_labels_toggle(self, state):
        self.config.config["show_labels"] = (state == Qt.Checked)
        self.config.save()
        self.redraw()

    def on_dpi_changed(self, val):
        self.config.config["dpi"] = val
        self.config.save()

    def apply_column_selection(self):
        label_col = self.cb_label.currentText()
        self.config.config["col_label"] = label_col
        self.config.save()
        self.update_sample_categories()
        self.populate_sample_list()
        self.redraw()

    def update_sample_categories(self):
        self.sample_categories = []
        if self.current_df is not None:
            label_col = self.cb_label.currentText()
            if label_col and label_col in self.current_df.columns:
                cats = [str(v) for v in self.current_df[label_col].unique() if pd.notna(v)]
                self.sample_categories = cats
                # 为新类别分配默认样式
                marker_list = list(MARKER_MAP.values())
                color_list = list(COLOR_MAP.values())
                for idx, cat in enumerate(cats):
                    if not self.config.has_sample_style(cat):
                        style = {
                            "marker": marker_list[idx % len(marker_list)],
                            "color": color_list[idx % len(color_list)],
                            "size": 60,
                            "zorder": 10
                        }
                        self.config.set_sample_style(cat, style)

    # ========== 辅助 ==========
    def get_marker_name(self, marker_symbol):
        for name, sym in MARKER_MAP.items():
            if sym == marker_symbol:
                return name
        return "圆"

    def get_color_name(self, color_code):
        for name, code in COLOR_MAP.items():
            if code == color_code:
                return name
        return "红色"

    # ================== 文件操作 ==================
    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择 Excel 数据文件", "",
            "Excel Files (*.xlsx *.xls)"
        )
        if not file_path:
            return
        self.file_path = file_path
        try:
            df = pd.read_excel(file_path)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"读取文件失败: {e}")
            return
        # 检查是否包含所有必需的元素列
        missing = [elem for elem in ELEMENTS if elem not in df.columns]
        if missing:
            QMessageBox.warning(self, "列缺失",
                f"数据文件中缺少以下元素列: {', '.join(missing)}\n"
                "请确保列名与元素符号完全一致（如 La, Ce, ...）。")
            return
        self.current_df = df
        # 更新标签列下拉
        cols = list(df.columns)
        self.cb_label.clear()
        self.cb_label.addItems(cols)
        # 尝试自动选择标签列
        saved_label = self.config.config.get("col_label", "")
        if saved_label in cols:
            self.cb_label.setCurrentText(saved_label)
        else:
            # 尝试匹配 'label' 或 'sample'
            for c in cols:
                if 'label' in c.lower() or 'sample' in c.lower() or 'id' in c.lower():
                    self.cb_label.setCurrentText(c)
                    break
        self.label_status.setText(f"已加载: {file_path} (共 {len(df)} 行)")
        self.update_sample_categories()
        self.populate_element_list()
        self.populate_sample_list()
        self.apply_column_selection()

    # ================== 绘图核心 ==================
    def redraw(self):
        self.figure.clear()
        ax = self.figure.add_subplot(111)

        # 获取标准
        standard_name = self.cb_standard.currentText()
        standard = STANDARDS.get(standard_name, STANDARDS[STANDARD_NAMES[0]])

        # 绘制背景网格（可选）
        ax.grid(True, linestyle='--', alpha=0.3)

        # 绘制元素分区标签（在横轴下方显示元素名称，可编辑）
        # 由于元素名称是固定的，我们直接使用配置中的显示文本
        elem_labels = []
        for elem in ELEMENTS:
            elem_cfg = self.config.get_element(elem)
            elem_labels.append(elem_cfg.get("text", elem))
        # 横轴位置为 0..13
        ax.set_xticks(range(len(ELEMENTS)))
        ax.set_xticklabels(elem_labels, rotation=45, ha='right',
                          fontsize=self.config.get_element("xlabel").get("size", 12),
                          fontfamily=self.config.get_element("xlabel").get("font", "SimHei"))

        # 设置轴标签
        xlabel_cfg = self.config.get_element("xlabel")
        ylabel_cfg = self.config.get_element("ylabel")
        ax.set_xlabel(xlabel_cfg.get("text", "元素"), fontsize=xlabel_cfg.get("size", 12),
                     fontfamily=xlabel_cfg.get("font", "SimHei"))
        ax.set_ylabel(ylabel_cfg.get("text", "样品/标准 (log10)"), fontsize=ylabel_cfg.get("size", 12),
                     fontfamily=ylabel_cfg.get("font", "SimHei"))

        # 设置主标题
        title_cfg = self.config.get_element("main_title")
        ax.set_title(title_cfg.get("text", "稀土元素标准化图解"),
                    fontsize=title_cfg.get("size", 16),
                    fontfamily=title_cfg.get("font", "SimHei"),
                    y=1.0 + title_cfg.get("y_offset", 0.02))

        # 如果有数据，绘制样品
        if self.current_df is not None and not self.current_df.empty:
            label_col = self.cb_label.currentText()
            if label_col and label_col in self.current_df.columns:
                categories = [str(v) for v in self.current_df[label_col]]
            else:
                categories = [None] * len(self.current_df)

            # 准备图例句柄
            legend_handles = []
            legend_labels = []
            legend_cfg = self.config.get_element("legend")
            leg_markersize = legend_cfg.get("markersize", 10)

            # 为每个类别绘制
            for cat in self.sample_categories:
                style = self.config.get_sample_style(cat)
                marker = style.get("marker", "o")
                color = style.get("color", "red")
                size = style.get("size", 60)
                zorder = style.get("zorder", 10)

                # 筛选属于该类别的样品
                mask = [c == cat for c in categories]
                if not any(mask):
                    continue
                df_cat = self.current_df[mask]
                # 对每个样品绘制一条线和一个散点
                for idx_row, row in df_cat.iterrows():
                    # 计算归一化值并取 log10
                    norm_vals = []
                    valid = True
                    for elem in ELEMENTS:
                        val = row[elem]
                        std_val = standard.get(elem, 1.0)
                        if pd.isna(val) or pd.isna(std_val) or std_val == 0:
                            valid = False
                            break
                        norm = val / std_val
                        if norm <= 0:
                            valid = False
                            break
                        norm_vals.append(math.log10(norm))
                    if not valid:
                        continue
                    # 绘制线条
                    x = list(range(len(ELEMENTS)))
                    ax.plot(x, norm_vals, color=color, linewidth=1.0, alpha=0.7, zorder=zorder)
                    # 绘制散点
                    ax.scatter(x, norm_vals, marker=marker, color=color, s=size,
                               edgecolors='black', linewidth=0.5, zorder=zorder)

                # 添加图例句柄（每个类别只添加一次）
                handle = Line2D([0], [0], marker=marker, color=color,
                                markerfacecolor=color, markersize=leg_markersize,
                                linestyle='None')
                legend_handles.append(handle)
                legend_labels.append(cat)

            # 显示图例
            if legend_handles:
                leg_x_offset = legend_cfg.get("x_offset", 0)
                leg_y_offset = legend_cfg.get("y_offset", 0)
                bbox_x = 0.98 + leg_x_offset
                bbox_y = 0.98 + leg_y_offset
                leg = ax.legend(legend_handles, legend_labels,
                                bbox_to_anchor=(bbox_x, bbox_y),
                                loc='upper right',
                                fontsize=legend_cfg.get("size", 10),
                                prop={'family': legend_cfg.get("font", "SimHei")},
                                labelcolor=legend_cfg.get("color", "black"))
                leg.set_title(None)

            # 显示标签（如果启用）
            if self.config.config.get("show_labels", False) and label_col:
                for i, (_, row) in enumerate(self.current_df.iterrows()):
                    # 计算归一化值以获取最后一个点的位置（用于标注）
                    norm_vals = []
                    valid = True
                    for elem in ELEMENTS:
                        val = row[elem]
                        std_val = standard.get(elem, 1.0)
                        if pd.isna(val) or pd.isna(std_val) or std_val == 0:
                            valid = False
                            break
                        norm = val / std_val
                        if norm <= 0:
                            valid = False
                            break
                        norm_vals.append(math.log10(norm))
                    if not valid:
                        continue
                    # 在最后一个点附近标注
                    x = len(ELEMENTS) - 1
                    y = norm_vals[-1]
                    label_text = str(row[label_col])
                    ax.annotate(label_text, xy=(x, y), xytext=(5, 0),
                                textcoords='offset points', ha='left', va='center',
                                fontsize=8, bbox=dict(boxstyle='round,pad=0.2',
                                                      facecolor='white', alpha=0.6))

        # 设置轴范围
        ax.set_xlim(-0.5, len(ELEMENTS) - 0.5)
        # 纵轴自动调整，但留边距
        ax.set_ylim(auto=True)
        # 如果所有数据点都为零或负数，显示空图
        if ax.get_ylim()[0] == ax.get_ylim()[1]:
            ax.set_ylim(-2, 2)

        self.canvas.draw()
        self.canvas.flush_events()
        self.statusBar.showMessage("图形已刷新", 1000)

        # 更新计算结果（以备查看）
        self.update_result_data(standard)

    # ================== 计算结果 ==================
    def update_result_data(self, standard):
        if self.current_df is None or self.current_df.empty:
            self.result_df = None
            return
        label_col = self.cb_label.currentText()
        if label_col not in self.current_df.columns:
            self.result_df = None
            return

        rows = []
        for idx, row in self.current_df.iterrows():
            label = row[label_col]
            # 获取各元素值
            vals = {elem: row[elem] for elem in ELEMENTS}
            # 标准化值
            norm = {elem: vals[elem] / standard.get(elem, 1.0) for elem in ELEMENTS}
            # 计算参数
            try:
                eu_algebra = 2 * norm['Eu'] / (norm['Sm'] + norm['Gd'])
                eu_geometric = norm['Eu'] / np.sqrt(norm['Sm'] * norm['Gd'])
                ce_la_pr = 2 * norm['Ce'] / (norm['La'] + norm['Pr'])
                ce_la_nd = 3 * norm['Ce'] / (2 * norm['La'] + norm['Nd'])
                la_sm = norm['La'] / norm['Sm']
                la_yb = norm['La'] / norm['Yb']
                gd_yb = norm['Gd'] / norm['Yb']
                lree = sum(norm[e] for e in ['La','Ce','Pr','Nd'])
                mree = sum(norm[e] for e in ['Sm','Eu','Gd','Tb','Dy','Ho'])
                hree = sum(norm[e] for e in ['Er','Tm','Yb','Lu'])
                l_h = lree / hree if hree != 0 else np.nan
            except Exception:
                eu_algebra = eu_geometric = ce_la_pr = ce_la_nd = la_sm = la_yb = gd_yb = np.nan
                lree = mree = hree = l_h = np.nan

            rows.append({
                'Label': label,
                'Eu/Eu*(algebra)': eu_algebra,
                'Eu/Eu*(geometric)': eu_geometric,
                'Ce/Ce*(LaPr)': ce_la_pr,
                'Ce/Ce*(LaNd)': ce_la_nd,
                '(La/Sm)N': la_sm,
                '(La/Yb)N': la_yb,
                '(Gd/Yb)N': gd_yb,
                'LREE_sum': lree,
                'MREE_sum': mree,
                'HREE_sum': hree,
                'LREE/HREE': l_h
            })
        self.result_df = pd.DataFrame(rows)

    def show_result_table(self):
        if self.result_df is None or self.result_df.empty:
            QMessageBox.information(self, "提示", "无计算结果，请先加载数据并应用列。")
            return
        dialog = ResultTableDialog(self.result_df, self)
        dialog.exec()

    # ================== 保存图片 ==================
    def save_image(self):
        if self.figure is None:
            QMessageBox.warning(self, "提示", "没有可保存的图片")
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存图片", "",
            "PNG (*.png);;JPG (*.jpg);;SVG (*.svg);;PDF (*.pdf)"
        )
        if not file_path:
            return
        dpi = self.spin_dpi.value()
        self.figure.savefig(file_path, dpi=dpi, bbox_inches='tight')
        QMessageBox.information(self, "成功", f"图片已保存至 {file_path} (DPI={dpi})")

    # ================== 复位 ==================
    def reset_all(self):
        reply = QMessageBox.question(self, "确认复位", "将恢复所有设置到默认状态，确定继续？",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        self.config.reset()
        self.cb_standard.setCurrentText(self.config.config.get("standard", STANDARD_NAMES[0]))
        self.spin_dpi.setValue(self.config.config.get("dpi", 300))
        self.cb_show_labels.setChecked(self.config.config.get("show_labels", False))
        self.cb_label.clear()
        self.current_df = None
        self.file_path = None
        self.sample_categories = []
        self.result_df = None
        self.populate_element_list()
        self.populate_sample_list()
        self.set_edit_state("none")
        self.label_status.setText("已复位，请重新加载数据")
        self.redraw()
        QMessageBox.information(self, "复位完成", "所有设置已恢复到默认状态。")

# ================== 启动 ==================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
    plt.rcParams['axes.unicode_minus'] = False
    window = REEWindow()
    window.show()
    sys.exit(app.exec())