# -*- coding: utf-8 -*-
"""
K₂O-SiO₂ 图解工具 (基于 GeoPyTool 实现)
- 三分类：高钾、中钾、低钾
- 背景填充开关
- 标签列显示
- 数据加载、样式编辑、图例、导出图片
- 所有设置持久化
"""

import sys
import json
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from matplotlib.lines import Line2D
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QPushButton, QFileDialog, QLabel, QHBoxLayout,
                               QComboBox, QSpinBox, QMessageBox, QCheckBox,
                               QLineEdit, QTableWidget, QTableWidgetItem,
                               QHeaderView, QDialog, QDialogButtonBox)
from PySide6.QtCore import Qt

# ================== 全局配置 ==================
CONFIG_FILE = "k2o_config.json"

# ================== 分类定义 ==================
CLASS_POLYGONS = {
    'High K': np.array([
        [45, 100], [45, 0.945], [48, 1.2], [68, 2.9], [85, 4.345], [85, 100]
    ]),
    'Medium K': np.array([
        [45, 0.945], [48, 1.2], [68, 2.9], [85, 4.345],
        [85, 1.965], [68, 1.2], [48, 0.3], [45, 0.165]
    ]),
    'Low K': np.array([
        [45, 0.165], [48, 0.3], [68, 1.2], [85, 1.965],
        [85, 0], [45, 0]
    ])
}

CLASS_NAMES_DEFAULT = {
    'High K': '高钾',
    'Medium K': '中钾',
    'Low K': '低钾'
}

CLASS_STYLES_DEFAULT = {
    'High K': {'marker': 'o', 'color': 'red', 'size': 60},
    'Medium K': {'marker': 's', 'color': 'blue', 'size': 60},
    'Low K': {'marker': '^', 'color': 'green', 'size': 60}
}

# ================== 配置管理 ==================
class ConfigManager:
    def __init__(self, filename=CONFIG_FILE):
        self.filename = filename
        self.default_config = {
            "dpi": 300,
            "show_legend": True,
            "show_subtitle": True,
            "show_background": True,
            "show_labels": False,
            "col_sio2": "",
            "col_k2o": "",
            "col_label": "",
            "main_title": "K₂O-SiO₂ 分类图解",
            "sub_title": "高钾/中钾/低钾",
            "xlabel": "SiO2 (wt%)",
            "ylabel": "K2O (wt%)",
            "legend_font": "SimHei",
            "legend_size": 10,
            "legend_color": "black",
            "legend_x_offset": 0,
            "legend_y_offset": 0,
            "legend_markersize": 10,
            "main_font": "SimHei",
            "main_size": 16,
            "main_x_offset": 0,
            "main_y_offset": 0.02,
            "sub_font": "SimHei",
            "sub_size": 11,
            "sub_x_offset": 0,
            "sub_y_offset": -0.03,
            "class_names": CLASS_NAMES_DEFAULT.copy(),
            "class_styles": CLASS_STYLES_DEFAULT.copy()
        }
        self.config = self.load()

    def load(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return self.default_config.copy()
        else:
            return self.default_config.copy()

    def save(self):
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)

    def reset(self):
        self.config = self.default_config.copy()
        self.save()

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self.save()

    def get_class_name(self, class_key):
        return self.config.get("class_names", {}).get(class_key, class_key)

    def set_class_name(self, class_key, name):
        self.config.setdefault("class_names", {})[class_key] = name
        self.save()

    def get_class_style(self, class_key):
        styles = self.config.get("class_styles", {})
        return styles.get(class_key, CLASS_STYLES_DEFAULT.get(class_key, {}))

    def set_class_style(self, class_key, style_dict):
        styles = self.config.get("class_styles", {})
        styles[class_key] = style_dict
        self.config["class_styles"] = styles
        self.save()

# ================== 分类结果表格 ==================
class ResultTableDialog(QDialog):
    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("分类结果")
        self.resize(600, 400)
        layout = QVBoxLayout(self)
        self.table = QTableWidget()
        self.table.setColumnCount(len(data.columns))
        self.table.setHorizontalHeaderLabels(data.columns)
        self.table.setRowCount(len(data))
        for i, row in data.iterrows():
            for j, val in enumerate(row):
                self.table.setItem(i, j, QTableWidgetItem(str(val)))
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok)
        btn_box.accepted.connect(self.accept)
        layout.addWidget(btn_box)

# ================== 主窗口 ==================
class K2OSiO2Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("K₂O-SiO₂ 图解工具")
        self.setGeometry(30, 30, 1100, 820)

        self.config = ConfigManager()
        self.current_df = None
        self.file_path = None
        self.class_keys = list(CLASS_POLYGONS.keys())
        self.last_result = pd.DataFrame()

        # 字体映射
        self.font_map = {
            "黑体": "SimHei", "宋体": "SimSun", "楷体": "KaiTi",
            "仿宋": "FangSong", "微软雅黑": "Microsoft YaHei",
            "Arial": "Arial", "Times New Roman": "Times New Roman"
        }
        self.font_display_to_family = self.font_map
        self.font_family_to_display = {v: k for k, v in self.font_map.items()}

        self.color_map = {
            '红色': 'red', '蓝色': 'blue', '绿色': 'green', '紫色': 'purple',
            '橙色': 'orange', '棕色': 'brown', '粉色': 'pink', '灰色': 'gray',
            '青色': 'cyan', '深红': 'darkred', '深绿': 'darkgreen', '黑色': 'black'
        }
        self.marker_map = {
            '圆': 'o', '方': 's', '三角': '^', '菱形': 'D', '倒三角': 'v',
            '五角星': '*', '叉': 'x', '左三角': '<', '右三角': '>',
            '加号': '+', '竖线': '|', '横线': '_'
        }
        self.marker_names = list(self.marker_map.keys())
        self.color_names = list(self.color_map.keys())

        self.base_keys = ["main_title", "sub_title", "xlabel", "ylabel", "legend"]

        # 界面构建
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # ===== 第一行 =====
        hbox1 = QHBoxLayout()
        self.btn_open = QPushButton("打开 Excel 文件")
        self.btn_open.setMaximumWidth(120)
        self.btn_open.clicked.connect(self.open_file)
        hbox1.addWidget(self.btn_open)

        self.label_status = QLabel("请选择数据文件")
        hbox1.addWidget(self.label_status)

        hbox1.addWidget(QLabel("DPI:"))
        self.spin_dpi = QSpinBox()
        self.spin_dpi.setRange(72, 1200)
        self.spin_dpi.setValue(self.config.get("dpi", 300))
        self.spin_dpi.valueChanged.connect(lambda v: self.config.set("dpi", v))
        hbox1.addWidget(self.spin_dpi)

        self.btn_save = QPushButton("保存图片")
        self.btn_save.setMaximumWidth(100)
        self.btn_save.clicked.connect(self.save_image)
        hbox1.addWidget(self.btn_save)

        self.btn_reset = QPushButton("复位设置")
        self.btn_reset.setMaximumWidth(100)
        self.btn_reset.clicked.connect(self.reset_all)
        hbox1.addWidget(self.btn_reset)

        self.btn_result = QPushButton("显示分类结果")
        self.btn_result.setMaximumWidth(120)
        self.btn_result.clicked.connect(self.show_result)
        hbox1.addWidget(self.btn_result)

        main_layout.addLayout(hbox1)

        # ===== 第二行：列选择 =====
        hbox2 = QHBoxLayout()
        hbox2.addWidget(QLabel("SiO₂:"))
        self.cb_sio2 = QComboBox()
        self.cb_sio2.setMinimumWidth(80)
        hbox2.addWidget(self.cb_sio2)
        hbox2.addWidget(QLabel("K₂O:"))
        self.cb_k2o = QComboBox()
        self.cb_k2o.setMinimumWidth(80)
        hbox2.addWidget(self.cb_k2o)
        hbox2.addWidget(QLabel("标签列:"))
        self.cb_label = QComboBox()
        self.cb_label.setMinimumWidth(80)
        hbox2.addWidget(self.cb_label)
        self.cb_show_labels = QCheckBox("显示标签")
        self.cb_show_labels.setChecked(self.config.get("show_labels", False))
        self.cb_show_labels.stateChanged.connect(lambda s: self.config.set("show_labels", s == Qt.Checked) or self.redraw())
        hbox2.addWidget(self.cb_show_labels)
        self.btn_apply_cols = QPushButton("应用列选择")
        self.btn_apply_cols.setMaximumWidth(100)
        self.btn_apply_cols.clicked.connect(self.apply_column_selection)
        hbox2.addWidget(self.btn_apply_cols)
        main_layout.addLayout(hbox2)

        # ===== 第三行：编辑对象与属性 =====
        hbox3 = QHBoxLayout()
        hbox3.addWidget(QLabel("编辑对象:"))
        self.cb_element = QComboBox()
        self.cb_element.currentIndexChanged.connect(self.on_element_selected)
        hbox3.addWidget(self.cb_element)

        self.edit_text = QLineEdit()
        self.edit_text.setPlaceholderText("输入标题文本...")
        self.edit_text.setMinimumWidth(150)
        self.edit_text.textChanged.connect(self.on_text_changed)
        hbox3.addWidget(self.edit_text)

        hbox3.addWidget(QLabel("字体:"))
        self.cb_font = QComboBox()
        for name in self.font_map.keys():
            self.cb_font.addItem(name)
        self.cb_font.currentTextChanged.connect(self.on_font_changed)
        hbox3.addWidget(self.cb_font)

        hbox3.addWidget(QLabel("大小:"))
        self.spin_size = QSpinBox()
        self.spin_size.setRange(6, 30)
        self.spin_size.valueChanged.connect(self.on_size_changed)
        hbox3.addWidget(self.spin_size)

        hbox3.addWidget(QLabel("X偏移:"))
        self.spin_x = QSpinBox()
        self.spin_x.setRange(-100, 100)
        self.spin_x.valueChanged.connect(self.on_x_changed)
        hbox3.addWidget(self.spin_x)

        hbox3.addWidget(QLabel("Y偏移:"))
        self.spin_y = QSpinBox()
        self.spin_y.setRange(-100, 100)
        self.spin_y.valueChanged.connect(self.on_y_changed)
        hbox3.addWidget(self.spin_y)

        self.cb_color = QComboBox()
        self.cb_color.addItems(self.color_names)
        self.cb_color.currentIndexChanged.connect(self.on_color_changed)
        hbox3.addWidget(self.cb_color)

        self.cb_marker = QComboBox()
        self.cb_marker.addItems(self.marker_names)
        self.cb_marker.currentIndexChanged.connect(self.on_marker_changed)
        hbox3.addWidget(self.cb_marker)

        self.spin_point_size = QSpinBox()
        self.spin_point_size.setRange(5, 200)
        self.spin_point_size.setValue(60)
        self.spin_point_size.valueChanged.connect(self.on_point_size_changed)

        self.label_style = QLabel("样式:")

        self.cb_show_sub = QCheckBox("显示副标题")
        self.cb_show_sub.setChecked(self.config.get("show_subtitle", True))
        self.cb_show_sub.stateChanged.connect(lambda s: self.config.set("show_subtitle", s == Qt.Checked) or self.redraw())

        self.cb_show_legend = QCheckBox("显示图例")
        self.cb_show_legend.setChecked(self.config.get("show_legend", True))
        self.cb_show_legend.stateChanged.connect(lambda s: self.config.set("show_legend", s == Qt.Checked) or self.redraw())

        self.cb_show_bg = QCheckBox("显示背景色")
        self.cb_show_bg.setChecked(self.config.get("show_background", True))
        self.cb_show_bg.stateChanged.connect(lambda s: self.config.set("show_background", s == Qt.Checked) or self.redraw())

        # 默认隐藏
        self.edit_text.setVisible(False)
        self.cb_font.setVisible(False)
        self.spin_size.setVisible(False)
        self.spin_x.setVisible(False)
        self.spin_y.setVisible(False)
        self.cb_color.setVisible(False)
        self.cb_marker.setVisible(False)
        self.spin_point_size.setVisible(False)
        self.label_style.setVisible(False)
        self.cb_show_sub.setVisible(False)
        self.cb_show_legend.setVisible(False)
        self.cb_show_bg.setVisible(False)

        hbox3.addWidget(self.label_style)
        hbox3.addWidget(self.cb_marker)
        hbox3.addWidget(self.spin_point_size)
        hbox3.addWidget(self.cb_show_sub)
        hbox3.addWidget(self.cb_show_legend)
        hbox3.addWidget(self.cb_show_bg)

        main_layout.addLayout(hbox3)

        # ===== 绘图区域 =====
        self.figure = Figure(figsize=(10, 7))
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setParent(central)
        main_layout.addWidget(self.canvas)

        # 初始化
        self.populate_element_list()
        self.on_element_selected(0)
        self.redraw()

    # ================== 元素下拉列表管理 ==================
    def populate_element_list(self):
        self.cb_element.clear()
        for key in self.base_keys:
            display = {"main_title": "主标题", "sub_title": "副标题",
                       "xlabel": "X轴标签", "ylabel": "Y轴标签", "legend": "图例"}[key]
            self.cb_element.addItem(display, key)
        for cls in self.class_keys:
            name = self.config.get_class_name(cls)
            self.cb_element.addItem(f"分类:{name}", f"class_{cls}")

    def get_current_key(self):
        return self.cb_element.currentData()

    def on_element_selected(self, index):
        key = self.get_current_key()
        if key is None:
            return
        # 隐藏所有动态控件
        self.edit_text.setVisible(False)
        self.cb_font.setVisible(False)
        self.spin_size.setVisible(False)
        self.spin_x.setVisible(False)
        self.spin_y.setVisible(False)
        self.cb_color.setVisible(False)
        self.cb_marker.setVisible(False)
        self.spin_point_size.setVisible(False)
        self.label_style.setVisible(False)
        self.cb_show_sub.setVisible(False)
        self.cb_show_legend.setVisible(False)
        self.cb_show_bg.setVisible(False)

        if key in self.base_keys:
            if key == "legend":
                self.cb_font.setVisible(True)
                self.spin_size.setVisible(True)
                self.spin_x.setVisible(True)
                self.spin_y.setVisible(True)
                self.cb_color.setVisible(True)
                self.cb_show_legend.setVisible(True)
                self.label_style.setVisible(True)
                self.label_style.setText("图例符号大小:")
                self.spin_point_size.setVisible(True)
                # 加载设置
                font_display = self.font_family_to_display.get(self.config.get("legend_font", "SimHei"), "黑体")
                idx = self.cb_font.findText(font_display)
                if idx >= 0:
                    self.cb_font.setCurrentIndex(idx)
                self.spin_size.setValue(self.config.get("legend_size", 10))
                self.spin_x.setValue(int(self.config.get("legend_x_offset", 0) * 100))
                self.spin_y.setValue(int(self.config.get("legend_y_offset", 0) * 100))
                color_name = self.get_color_name(self.config.get("legend_color", "black"))
                idx = self.cb_color.findText(color_name)
                if idx >= 0:
                    self.cb_color.setCurrentIndex(idx)
                self.spin_point_size.setValue(self.config.get("legend_markersize", 10))
                self.cb_show_legend.setChecked(self.config.get("show_legend", True))
                self.edit_text.setVisible(False)
                self.cb_marker.setVisible(False)
                self.cb_show_sub.setVisible(False)
                self.cb_show_bg.setVisible(False)
                return
            elif key in ["main_title", "sub_title", "xlabel", "ylabel"]:
                self.edit_text.setVisible(True)
                self.edit_text.setEnabled(True)
                if key == "main_title":
                    text = self.config.get("main_title", "")
                elif key == "sub_title":
                    text = self.config.get("sub_title", "")
                elif key == "xlabel":
                    text = self.config.get("xlabel", "")
                elif key == "ylabel":
                    text = self.config.get("ylabel", "")
                self.edit_text.setText(text)
                self.cb_font.setVisible(True)
                self.spin_size.setVisible(True)
                self.spin_x.setVisible(True)
                self.spin_y.setVisible(True)
                if key == "main_title":
                    font = self.config.get("main_font", "SimHei")
                    size = self.config.get("main_size", 16)
                    xoff = self.config.get("main_x_offset", 0)
                    yoff = self.config.get("main_y_offset", 0.02)
                elif key == "sub_title":
                    font = self.config.get("sub_font", "SimHei")
                    size = self.config.get("sub_size", 11)
                    xoff = self.config.get("sub_x_offset", 0)
                    yoff = self.config.get("sub_y_offset", -0.03)
                else:
                    font = "SimHei"
                    size = 12
                    xoff = 0
                    yoff = 0
                font_display = self.font_family_to_display.get(font, "黑体")
                idx = self.cb_font.findText(font_display)
                if idx >= 0:
                    self.cb_font.setCurrentIndex(idx)
                self.spin_size.setValue(size)
                self.spin_x.setValue(int(xoff * 100))
                self.spin_y.setValue(int(yoff * 100))
                if key == "sub_title":
                    self.cb_show_sub.setVisible(True)
                    self.cb_show_sub.setChecked(self.config.get("show_subtitle", True))
                self.cb_color.setVisible(False)
                self.cb_marker.setVisible(False)
                self.spin_point_size.setVisible(False)
                self.label_style.setVisible(False)
                self.cb_show_legend.setVisible(False)
                self.cb_show_bg.setVisible(False)
                return
        elif key.startswith("class_"):
            cls = key[6:]
            self.label_style.setVisible(True)
            self.label_style.setText("样式:")
            self.cb_marker.setVisible(True)
            self.spin_point_size.setVisible(True)
            self.cb_color.setVisible(True)
            # 显示背景色开关（通用）
            self.cb_show_bg.setVisible(True)
            self.cb_show_bg.setChecked(self.config.get("show_background", True))
            style = self.config.get_class_style(cls)
            marker_name = self.get_marker_name(style.get("marker", "o"))
            idx = self.cb_marker.findText(marker_name)
            if idx >= 0:
                self.cb_marker.setCurrentIndex(idx)
            color_name = self.get_color_name(style.get("color", "red"))
            idx = self.cb_color.findText(color_name)
            if idx >= 0:
                self.cb_color.setCurrentIndex(idx)
            self.spin_point_size.setValue(style.get("size", 60))
            self.edit_text.setVisible(False)
            self.cb_font.setVisible(False)
            self.spin_size.setVisible(False)
            self.spin_x.setVisible(False)
            self.spin_y.setVisible(False)
            self.cb_show_sub.setVisible(False)
            self.cb_show_legend.setVisible(False)
            return

    # ================== 辅助映射 ==================
    def get_marker_name(self, marker_symbol):
        for name, sym in self.marker_map.items():
            if sym == marker_symbol:
                return name
        return "圆"

    def get_color_name(self, color_code):
        for name, code in self.color_map.items():
            if code == color_code:
                return name
        return "红色"

    # ================== 控件事件 ==================
    def on_text_changed(self, text):
        key = self.get_current_key()
        if key in ["main_title", "sub_title", "xlabel", "ylabel"]:
            self.config.set(key, text)
            self.redraw()

    def on_font_changed(self, display_name):
        key = self.get_current_key()
        family = self.font_display_to_family.get(display_name, "SimHei")
        if key == "legend":
            self.config.set("legend_font", family)
            self.redraw()
        elif key in ["main_title", "sub_title"]:
            if key == "main_title":
                self.config.set("main_font", family)
            else:
                self.config.set("sub_font", family)
            self.redraw()

    def on_size_changed(self, val):
        key = self.get_current_key()
        if key == "legend":
            self.config.set("legend_size", val)
            self.redraw()
        elif key in ["main_title", "sub_title"]:
            if key == "main_title":
                self.config.set("main_size", val)
            else:
                self.config.set("sub_size", val)
            self.redraw()

    def on_x_changed(self, val):
        key = self.get_current_key()
        if key == "legend":
            self.config.set("legend_x_offset", val / 100.0)
            self.redraw()
        elif key in ["main_title", "sub_title"]:
            if key == "main_title":
                self.config.set("main_x_offset", val / 100.0)
            else:
                self.config.set("sub_x_offset", val / 100.0)
            self.redraw()

    def on_y_changed(self, val):
        key = self.get_current_key()
        if key == "legend":
            self.config.set("legend_y_offset", val / 100.0)
            self.redraw()
        elif key in ["main_title", "sub_title"]:
            if key == "main_title":
                self.config.set("main_y_offset", val / 100.0)
            else:
                self.config.set("sub_y_offset", val / 100.0)
            self.redraw()

    def on_color_changed(self, idx):
        key = self.get_current_key()
        if key == "legend":
            color_code = self.color_map.get(self.cb_color.currentText(), "black")
            self.config.set("legend_color", color_code)
            self.redraw()
        elif key and key.startswith("class_"):
            cls = key[6:]
            color_code = self.color_map.get(self.cb_color.currentText(), "red")
            style = self.config.get_class_style(cls)
            style["color"] = color_code
            self.config.set_class_style(cls, style)
            self.redraw()

    def on_marker_changed(self, idx):
        key = self.get_current_key()
        if key and key.startswith("class_"):
            cls = key[6:]
            marker_symbol = self.marker_map.get(self.cb_marker.currentText(), "o")
            style = self.config.get_class_style(cls)
            style["marker"] = marker_symbol
            self.config.set_class_style(cls, style)
            self.redraw()

    def on_point_size_changed(self, val):
        key = self.get_current_key()
        if key == "legend":
            self.config.set("legend_markersize", val)
            self.redraw()
        elif key and key.startswith("class_"):
            cls = key[6:]
            style = self.config.get_class_style(cls)
            style["size"] = val
            self.config.set_class_style(cls, style)
            self.redraw()

    # ================== 数据加载 ==================
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
        self.current_df = df
        cols = list(df.columns)
        for cb in [self.cb_sio2, self.cb_k2o, self.cb_label]:
            cb.clear()
            cb.addItems(cols)
        for c in cols:
            c_low = c.lower()
            if 'sio2' in c_low or 'sio' in c_low:
                self.cb_sio2.setCurrentText(c)
            if 'k2o' in c_low:
                self.cb_k2o.setCurrentText(c)
            if 'label' in c_low or 'sample' in c_low or 'id' in c_low:
                self.cb_label.setCurrentText(c)
        # 加载保存的列
        for key, cb in [("col_sio2", self.cb_sio2), ("col_k2o", self.cb_k2o), ("col_label", self.cb_label)]:
            saved = self.config.get(key)
            if saved and saved in cols:
                cb.setCurrentText(saved)
        self.label_status.setText(f"已加载: {file_path} (共 {len(df)} 行)")
        self.apply_column_selection()

    def apply_column_selection(self):
        self.config.set("col_sio2", self.cb_sio2.currentText())
        self.config.set("col_k2o", self.cb_k2o.currentText())
        self.config.set("col_label", self.cb_label.currentText())
        self.redraw()

    # ================== 绘图核心 ==================
    def redraw(self):
        self.figure.clear()
        ax = self.figure.add_subplot(111)

        # 绘制分类区域（背景色）
        show_bg = self.config.get("show_background", True)
        for cls, verts in CLASS_POLYGONS.items():
            style = self.config.get_class_style(cls)
            color = style.get("color", "gray")
            if show_bg:
                polygon = Polygon(verts, closed=True, edgecolor='none',
                                 facecolor=color, alpha=0.2)
            else:
                polygon = Polygon(verts, closed=True, edgecolor='none',
                                 facecolor='none', alpha=0)
            ax.add_patch(polygon)

        # 绘制两条分界线（黑色虚线）
        pts_high = [[45, 0.945], [48, 1.2], [68, 2.9], [85, 4.345]]
        x_high, y_high = zip(*pts_high)
        ax.plot(x_high, y_high, 'k--', linewidth=1.5, alpha=0.7)
        pts_low = [[45, 0.165], [48, 0.3], [68, 1.2], [85, 1.965]]
        x_low, y_low = zip(*pts_low)
        ax.plot(x_low, y_low, 'k--', linewidth=1.5, alpha=0.7)

        # 添加分类标签（右侧）
        labels = ['High K', 'Medium K', 'Low K']
        positions = [(80, 5), (80, 3), (80, 1)]
        for lbl, pos in zip(labels, positions):
            ax.annotate(lbl, pos, xycoords='data', fontsize=9, color='gray', alpha=0.8,
                        ha='center', va='center')

        # 轴标签
        ax.set_xlabel(self.config.get("xlabel", "SiO2 (wt%)"), fontsize=12)
        ax.set_ylabel(self.config.get("ylabel", "K2O (wt%)"), fontsize=12)
        ax.set_xlim(40, 90)
        ax.set_ylim(0, 7)
        ax.grid(True, linestyle='--', alpha=0.3)

        # ---- 样品点 ----
        result_data = []
        if self.current_df is not None and not self.current_df.empty:
            sio2_col = self.cb_sio2.currentText()
            k2o_col = self.cb_k2o.currentText()
            label_col = self.cb_label.currentText()
            if sio2_col and k2o_col:
                try:
                    df = self.current_df
                    x_vals = df[sio2_col]
                    y_vals = df[k2o_col]
                    classifications = []
                    for i, (x, y) in enumerate(zip(x_vals, y_vals)):
                        found = False
                        for cls, verts in CLASS_POLYGONS.items():
                            if self.point_in_polygon(x, y, verts):
                                classifications.append(cls)
                                found = True
                                break
                        if not found:
                            classifications.append("未分类")
                    for cls in self.class_keys:
                        mask = [c == cls for c in classifications]
                        if any(mask):
                            style = self.config.get_class_style(cls)
                            marker = style.get("marker", "o")
                            color = style.get("color", "red")
                            size = style.get("size", 60)
                            ax.scatter(x_vals[mask], y_vals[mask],
                                       marker=marker, color=color, s=size,
                                       edgecolors='black', linewidth=0.5,
                                       label=self.config.get_class_name(cls), zorder=5)
                    # 显示标签
                    if self.cb_show_labels.isChecked() and label_col and label_col in df.columns:
                        for i, (x, y) in enumerate(zip(x_vals, y_vals)):
                            ax.text(x, y, str(df.iloc[i][label_col]), fontsize=8,
                                    ha='center', va='bottom', color='black',
                                    bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.6))
                    # 记录结果
                    for i, (x, y) in enumerate(zip(x_vals, y_vals)):
                        result_data.append({
                            "SiO2": x,
                            "K2O": y,
                            "分类": classifications[i]
                        })
                    # 图例
                    if self.config.get("show_legend", True):
                        legend_elem = {}
                        legend_elem["font"] = self.config.get("legend_font", "SimHei")
                        legend_elem["size"] = self.config.get("legend_size", 10)
                        legend_elem["color"] = self.config.get("legend_color", "black")
                        legend_elem["x_offset"] = self.config.get("legend_x_offset", 0)
                        legend_elem["y_offset"] = self.config.get("legend_y_offset", 0)
                        legend_elem["markersize"] = self.config.get("legend_markersize", 10)
                        handles = []
                        labels = []
                        for cls in self.class_keys:
                            style = self.config.get_class_style(cls)
                            marker = style.get("marker", "o")
                            color = style.get("color", "red")
                            handle = Line2D([0], [0], marker=marker, color=color,
                                            markerfacecolor=color,
                                            markersize=legend_elem["markersize"],
                                            linestyle='None')
                            handles.append(handle)
                            labels.append(self.config.get_class_name(cls))
                        bbox_x = 0.98 + legend_elem["x_offset"]
                        bbox_y = 0.98 + legend_elem["y_offset"]
                        leg = ax.legend(handles, labels,
                                        bbox_to_anchor=(bbox_x, bbox_y),
                                        loc='upper right',
                                        fontsize=legend_elem["size"],
                                        prop={'family': legend_elem["font"], 'size': legend_elem["size"]},
                                        labelcolor=legend_elem["color"])
                        leg.set_title(None)
                except Exception as e:
                    print("绘图失败:", e)
            else:
                ax.text(0.5, 0.95, "请选择正确的列", transform=ax.transAxes,
                        ha='center', va='top', fontsize=12,
                        bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.8))

        # ---- 标题 ----
        main_title = self.config.get("main_title", "K₂O-SiO₂ 分类图解")
        sub_title = self.config.get("sub_title", "高钾/中钾/低钾")
        main_font = self.config.get("main_font", "SimHei")
        main_size = self.config.get("main_size", 16)
        main_x_off = self.config.get("main_x_offset", 0)
        main_y_off = self.config.get("main_y_offset", 0.02)
        ax.text(0.5 + main_x_off, 0.98 + main_y_off, main_title,
                transform=ax.transAxes, ha='center', va='bottom',
                fontsize=main_size, fontfamily=main_font, fontweight='bold')
        if self.config.get("show_subtitle", True):
            sub_font = self.config.get("sub_font", "SimHei")
            sub_size = self.config.get("sub_size", 11)
            sub_x_off = self.config.get("sub_x_offset", 0)
            sub_y_off = self.config.get("sub_y_offset", -0.03)
            ax.text(0.5 + sub_x_off, 0.93 + sub_y_off, sub_title,
                    transform=ax.transAxes, ha='center', va='bottom',
                    fontsize=sub_size, fontfamily=sub_font, style='italic', color='gray')

        self.canvas.draw()
        self.last_result = pd.DataFrame(result_data)

    # ================== 工具函数 ==================
    def point_in_polygon(self, x, y, verts):
        n = len(verts)
        inside = False
        for i in range(n):
            x1, y1 = verts[i]
            x2, y2 = verts[(i+1) % n]
            if ((y1 > y) != (y2 > y)) and (x < (x2 - x1) * (y - y1) / (y2 - y1) + x1):
                inside = not inside
        return inside

    # ================== 显示结果 ==================
    def show_result(self):
        if self.last_result.empty:
            QMessageBox.warning(self, "提示", "请先加载数据并应用列选择。")
            return
        dialog = ResultTableDialog(self.last_result, self)
        dialog.exec()

    # ================== 复位 ==================
    def reset_all(self):
        reply = QMessageBox.question(self, "确认复位", "将恢复所有设置到默认状态，确定继续？",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        self.config.reset()
        self.spin_dpi.setValue(self.config.get("dpi", 300))
        self.cb_show_sub.setChecked(self.config.get("show_subtitle", True))
        self.cb_show_legend.setChecked(self.config.get("show_legend", True))
        self.cb_show_bg.setChecked(self.config.get("show_background", True))
        self.cb_show_labels.setChecked(self.config.get("show_labels", False))
        self.cb_sio2.clear()
        self.cb_k2o.clear()
        self.cb_label.clear()
        self.current_df = None
        self.file_path = None
        self.label_status.setText("已复位，请重新加载数据")
        self.populate_element_list()
        self.on_element_selected(0)
        self.redraw()
        QMessageBox.information(self, "复位完成", "所有设置已恢复到默认状态。")

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

# ================== 启动 ==================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
    plt.rcParams['axes.unicode_minus'] = False
    window = K2OSiO2Window()
    window.show()
    sys.exit(app.exec())