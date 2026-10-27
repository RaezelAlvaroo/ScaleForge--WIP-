import sys, time
from pathlib import Path
import cv2
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence, QImage, QPixmap
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QLabel,QPushButton,QFileDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QComboBox,QSlider,QCheckBox,QGroupBox,QSplitter,QMessageBox,QStatusBar)

PRESETS={"Balanced":("1.5x",35),"Performance":("1.0x",10),"Crisp UI":("2.0x",55),"Pixel Art":("2.0x",0)}
def sharpen(img, amount):
    if not amount: return img
    blur=cv2.GaussianBlur(img,(0,0),1.2)
    return cv2.addWeighted(img,1+amount/100,blur,-amount/100,0)
def pixmap(img):
    rgb=cv2.cvtColor(img,cv2.COLOR_BGR2RGB); h,w,ch=rgb.shape
    return QPixmap.fromImage(QImage(rgb.data,w,h,ch*w,QImage.Format.Format_RGB888).copy())

class ScaleForge(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("ScaleForge"); self.resize(1100,720)
        self.original=None; self.second=None; self.render_fps=0
        root=QWidget(); self.setCentralWidget(root); layout=QVBoxLayout(root)
        header=QHBoxLayout(); title=QLabel("ScaleForge"); title.setStyleSheet("font-size:24px;font-weight:bold")
        header.addWidget(title); header.addWidget(QLabel("Image scaling • sharpening • frame blend prototype")); header.addStretch()
        self.fps=QLabel("Preview FPS: --"); header.addWidget(self.fps); layout.addLayout(header)
        split=QSplitter(Qt.Orientation.Horizontal); layout.addWidget(split,1)
        self.preview=QLabel("Ctrl+O — open an image"); self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter); self.preview.setMinimumSize(400,300); self.preview.setStyleSheet("background:#111827;color:#ddd")
        split.addWidget(self.preview)
        side=QWidget(); side.setMinimumWidth(290); sl=QVBoxLayout(side)
        fg=QGroupBox("Image"); fl=QVBoxLayout(fg)
        b=QPushButton("Open image… (Ctrl+O)"); b.clicked.connect(self.open_image); fl.addWidget(b)
        b=QPushButton("Load second frame…"); b.clicked.connect(self.open_second); fl.addWidget(b); sl.addWidget(fg)
        sg=QGroupBox("Scaling & sharpening"); form=QFormLayout(sg)
        self.scale=QComboBox(); self.scale.addItems(["0.5x","0.75x","1.0x","1.25x","1.5x","2.0x","3.0x","4.0x"]); self.scale.setCurrentText("1.5x"); self.scale.currentTextChanged.connect(self.render); form.addRow("Scale factor",self.scale)
        self.sharp=QSlider(Qt.Orientation.Horizontal); self.sharp.setRange(0,100); self.sharp.setValue(35); self.sharp.valueChanged.connect(self.render); form.addRow("Sharpen",self.sharp); sl.addWidget(sg)
        pg=QGroupBox("Gaming presets"); pl=QVBoxLayout(pg); self.preset=QComboBox(); self.preset.addItems(PRESETS); self.preset.currentTextChanged.connect(self.apply_preset); pl.addWidget(self.preset); sl.addWidget(pg)
        bg=QGroupBox("Frame blend prototype"); bl=QVBoxLayout(bg); bl.addWidget(QLabel("Blend two still images; not real-time motion interpolation."))
        self.blend=QSlider(Qt.Orientation.Horizontal); self.blend.setRange(0,100); self.blend.setValue(50); self.blend.valueChanged.connect(self.render); bl.addWidget(self.blend)
        b=QPushButton("Export processed image…"); b.clicked.connect(self.export_image); bl.addWidget(b); sl.addWidget(bg)
        self.fit=QCheckBox("Fit preview to window"); self.fit.setChecked(True); self.fit.stateChanged.connect(self.render); sl.addWidget(self.fit); sl.addStretch(); split.addWidget(side); split.setSizes([760,340])
        self.setStatusBar(QStatusBar()); self.setStyleSheet("QMainWindow,QWidget{background:#1f2937;color:#f9fafb} QGroupBox{border:1px solid #566;border-radius:7px;margin-top:9px;padding:8px} QPushButton,QComboBox{background:#374151;border:1px solid #6b7280;border-radius:5px;padding:7px}")
        self.add_hotkey("Ctrl+O",self.open_image); self.add_hotkey("F11",self.fullscreen); self.add_hotkey("Ctrl+R",self.reset)
        self.timer=QTimer(self); self.timer.timeout.connect(self.update_fps); self.timer.start(500)
    def add_hotkey(self,key,fn):
        a=QAction(self); a.setShortcut(QKeySequence(key)); a.triggered.connect(fn); self.addAction(a)
    def open_image(self):
        p,_=QFileDialog.getOpenFileName(self,"Open image","","Images (*.png *.jpg *.jpeg *.bmp *.webp *.tif)")
        if p:
            im=cv2.imread(p)
            if im is None: QMessageBox.warning(self,"Error","Cannot decode image."); return
            self.original=im; self.statusBar().showMessage(f"Loaded {Path(p).name} • {im.shape[1]}×{im.shape[0]}"); self.render()
    def open_second(self):
        p,_=QFileDialog.getOpenFileName(self,"Load second image","","Images (*.png *.jpg *.jpeg *.bmp *.webp)")
        if p:
            self.second=cv2.imread(p)
            if self.second is None: QMessageBox.warning(self,"Error","Cannot decode image."); return
            self.render()
    def apply_preset(self,name):
        if name in PRESETS: self.scale.setCurrentText(PRESETS[name][0]); self.sharp.setValue(PRESETS[name][1])
    def processed(self):
        im=self.original.copy()
        if self.second is not None:
            other=cv2.resize(self.second,(im.shape[1],im.shape[0]),interpolation=cv2.INTER_LINEAR)
            a=self.blend.value()/100; im=cv2.addWeighted(im,1-a,other,a,0)
        im=sharpen(im,self.sharp.value()); factor=float(self.scale.currentText()[:-1])
        if factor!=1:
            interp=cv2.INTER_NEAREST if self.preset.currentText()=="Pixel Art" else (cv2.INTER_LANCZOS4 if factor>1 else cv2.INTER_AREA)
            h,w=im.shape[:2]; im=cv2.resize(im,(max(1,int(w*factor)),max(1,int(h*factor))),interpolation=interp)
        return im
    def render(self,*_):
        if self.original is None: return
        t=time.perf_counter(); im=self.processed(); pm=pixmap(im)
        if self.fit.isChecked(): pm=pm.scaled(self.preview.size(),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)
        self.preview.setPixmap(pm); self.render_fps=1/max(time.perf_counter()-t,0.0001); self.fps.setText(f"Preview FPS: {self.render_fps:.1f}")
        self.statusBar().showMessage(f"Output {im.shape[1]}×{im.shape[0]} • preview render {1000/self.render_fps:.1f} ms")
    def update_fps(self):
        if self.original is not None: self.fps.setText(f"Preview FPS: {self.render_fps:.1f}")
    def export_image(self):
        if self.original is None: QMessageBox.information(self,"No image","Open an image first."); return
        p,_=QFileDialog.getSaveFileName(self,"Export image","scaleforge-output.png","PNG (*.png);;JPEG (*.jpg)")
        if p and not cv2.imwrite(p,self.processed()): QMessageBox.warning(self,"Export failed","Could not save file.")
    def reset(self):
        self.scale.setCurrentText("1.5x"); self.sharp.setValue(35); self.blend.setValue(50); self.preset.setCurrentText("Balanced"); self.render()
    def fullscreen(self): self.showNormal() if self.isFullScreen() else self.showFullScreen()
    def resizeEvent(self,event):
        super().resizeEvent(event); self.render()

if __name__=="__main__":
    app=QApplication(sys.argv); app.setApplicationName("ScaleForge"); w=ScaleForge(); w.show(); sys.exit(app.exec())
