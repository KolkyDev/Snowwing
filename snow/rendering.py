"""Procedural, antialiased snow textures and a per-pixel-alpha Win32 surface."""
import os
os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "0")
import math
import time
from PIL import Image, ImageDraw, ImageFilter


def flake(radius, shade, opacity):
    scale = 4
    size = max(8, math.ceil(radius * 2 + 6))
    image = Image.new('RGBA', (size * scale, size * scale))
    draw = ImageDraw.Draw(image)
    c = size * scale / 2
    r = radius * scale
    draw.ellipse((c-r, c-r, c+r, c+r), fill=(*shade, opacity))
    image = image.filter(ImageFilter.GaussianBlur(.32 * scale))
    return image.resize((size, size), Image.Resampling.LANCZOS)


def snowcap(width, heights, seed):
    """Lit snow with stable fine grain, rounded drifts and translucent edges."""
    scale = 3
    height = max(4, math.ceil(max(heights))+4)
    width = max(2, int(width))
    # Smooth interpolation prevents the sample grid from appearing in the edge.
    outline = []
    n = len(heights)
    for x in range(width + 1):
        t = x / width * (n - 1)
        i = min(n - 2, int(t))
        u = t-i
        depth = heights[i]*(1-u) + heights[i+1]*u
        depth = max(0, depth)
        outline.append((x*scale, (height-depth)*scale))
    mask = Image.new('L', ((width+1)*scale, (height+2)*scale))
    ImageDraw.Draw(mask).polygon(outline + [(width*scale,(height+1)*scale),
                                         (0,(height+1)*scale)], fill=255)
    mask = mask.resize((width+1,height+2), Image.Resampling.LANCZOS)
    texture = Image.new('RGBA', mask.size)
    pixels = texture.load()
    for x in range(width+1):
        edge = outline[x][1]/scale
        depth = max(1,height-edge)
        for y in range(max(0,int(edge)-2),height+2):
            t = max(0,min(1,(y-edge)/depth))
            grain_hash = ((x*73856093) ^ (y*19349663) ^ int(seed)) & 0xffffffff
            grain_hash = ((grain_hash ^ (grain_hash >> 13))*1274126177) & 0xffffffff
            grain = (grain_hash % 101)/100*5.6-2.8
            slope = (outline[min(width,x+1)][1]-outline[max(0,x-1)][1])/(2*scale)
            lighting = max(-9,min(5,-slope*7))*(1-t*.5)
            # Bright soft crest, cool compacted snow along the underside.
            pixels[x,y] = tuple(max(0,min(255,int(c+grain+lighting)))
                                for c in (247-44*t*t,251-29*t*t,255-12*t*t))+(255,)
    if max(heights) < .02:
        mask.paste(0,(0,0,*mask.size))
    texture.putalpha(mask)
    return texture


def premultiplied_bgra(image):
    r, g, b, a = image.split()
    return Image.merge('RGBA', (b, g, r, a)).convert('RGBa')


from PySide6.QtCore import Qt, QRect, QRectF, QPointF
from PySide6.QtGui import (QActionGroup, QIcon, QPixmap, QBrush, QColor, QImage, QLinearGradient,
                          QPainter, QPainterPath, QPen, QRegion)
from PySide6.QtWidgets import QApplication, QWidget, QSystemTrayIcon, QMenu


def qt_sprite(image):
    return QImage(image.tobytes(), image.width, image.height,
                  image.width*4,QImage.Format.Format_RGBA8888).convertToFormat(
                      QImage.Format.Format_ARGB32_Premultiplied)


class SnowLayer(QWidget):
    def __init__(self,width,height,sprites):
        super().__init__(None,Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool |
                         Qt.WindowType.WindowStaysOnTopHint |
                         Qt.WindowType.WindowTransparentForInput |
                         Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle('Desktop Snow')
        self.resize(width,height)
        self.sprites=sprites
        self.caps={}
        self.flakes=[]
        self.visible_region=QRegion(self.rect())
        self.blockers=[]
        self.grain=QImage(64,32,QImage.Format.Format_ARGB32_Premultiplied)
        self.grain.fill(Qt.GlobalColor.transparent)
        import random
        rng=random.Random(73)
        painter=QPainter(self.grain)
        for _ in range(170):
            painter.setPen(QColor(255,255,255,rng.randrange(8,28)))
            painter.drawPoint(rng.randrange(64),rng.randrange(32))
        painter.end()

    def set_scene(self,banks,flakes,blockers):
        regions=[]
        current={}
        for left,top,right,key,heights in banks:
            if not heights or max(heights)<.06:
                continue
            signature=(left,top,right,tuple(round(h*4) for h in heights))
            cached=self.caps.get(key)
            if cached and (cached[0]==signature or (cached[0][:3]==signature[:3] and time.perf_counter()<cached[6])):
                current[key]=cached
                continue
            crest=QPainterPath()
            crest.moveTo(left,top-heights[0])
            for i,h in enumerate(heights[1:],1):
                crest.lineTo(left+(right-left)*i/(len(heights)-1),top-h)
            path=QPainterPath(crest)
            path.lineTo(right,top); path.lineTo(left,top); path.closeSubpath()
            bounds=path.boundingRect().adjusted(-2,-2,2,2).toAlignedRect()
            gradient=QLinearGradient(0,top-max(heights),0,top)
            gradient.setColorAt(0,QColor(251,253,255))
            gradient.setColorAt(.40,QColor(234,244,253))
            gradient.setColorAt(1,QColor(177,201,226))
            brush=QBrush(gradient)
            image=QImage(bounds.width(),bounds.height(),QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(Qt.GlobalColor.transparent)
            cap_painter=QPainter(image)
            cap_painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            cap_painter.translate(-bounds.left(),-bounds.top())
            cap_painter.fillPath(path,brush)
            cap_painter.save()
            cap_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceAtop)
            cap_painter.fillRect(bounds,QBrush(self.grain))
            cap_painter.restore()
            cap_painter.setPen(QPen(QColor(255,255,255,185),.75))
            cap_painter.drawPath(crest)
            cap_painter.end()
            current[key]=(signature,path,crest,bounds,brush,image,time.perf_counter()+1/15)
            regions.append(QRegion(bounds))
            if cached: regions.append(QRegion(cached[3]))
        for key,cached in self.caps.items():
            if key not in current: regions.append(QRegion(cached[3]))
        for x,y,index,scale in self.flakes+flakes:
            image=self.sprites[index]
            w=image.width()*scale; h=image.height()*scale
            regions.append(QRegion(QRectF(x-w/2-1,y-h/2-1,w+2,h+2).toAlignedRect()))
        if blockers != self.blockers:
            self.visible_region=QRegion(self.rect())
            for a,b,c,d in blockers:
                self.visible_region=self.visible_region.subtracted(QRegion(QRect(a,b,max(0,c-a+1),max(0,d-b+1))))
            # Erase old occlusion and expose newly visible background.
            regions=[QRegion(self.rect())]
            self.blockers=list(blockers)
        self.caps=current
        self.flakes=flakes
        # A balanced union avoids repeatedly copying an ever-growing region.
        while len(regions)>1:
            regions=[regions[i].united(regions[i+1]) if i+1<len(regions) else regions[i]
                     for i in range(0,len(regions),2)]
        if regions and not regions[0].isEmpty(): self.update(regions[0])

    def paintEvent(self,event):
        painter=QPainter(self)
        self.paint_scene(painter,event.region())
        painter.end()

    def paint_scene(self,painter,dirty):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setClipRegion(dirty.intersected(self.visible_region))
        for cached in self.caps.values():
            bounds=cached[3]
            if dirty.intersects(bounds):
                painter.drawImage(bounds.topLeft(),cached[5])
        for x,y,index,scale in self.flakes:
            image=self.sprites[index]
            w=image.width()*scale; h=image.height()*scale
            rect=QRectF(x-w/2,y-h/2,w,h)
            if dirty.intersects(rect.toAlignedRect()):
                painter.drawImage(rect,image)


class Surface:
    def __init__(self,x,y,width,height):
        self.app=QApplication.instance() or QApplication([])
        self.app.setQuitOnLastWindowClosed(False)
        sprites=[qt_sprite(flake(r,color,opacity)) for r,color,opacity in [
            (.85,(193,210,234),125),(1.15,(222,234,249),175),
            (1.65,(244,249,255),220),(2.1,(232,242,255),170)]]
        self.layer=SnowLayer(width,height,sprites)
        self.layer.move(x,y)
        self.hwnd=int(self.layer.winId())
        self.layer.show()

    def install_controls(self,owner):
        icon=QPixmap.fromImage(self.layer.sprites[2].scaled(32,32,Qt.AspectRatioMode.KeepAspectRatio,
                                                       Qt.TransformationMode.SmoothTransformation))
        self.tray=QSystemTrayIcon(QIcon(icon),self.layer)
        self.tray.setToolTip('Desktop Snow')
        self.menu=QMenu()
        pause=self.menu.addAction('Pause'); pause.setCheckable(True)
        pause.toggled.connect(lambda checked:setattr(owner,'paused',checked))
        intensity=self.menu.addMenu('Snowfall')
        group=QActionGroup(intensity); group.setExclusive(True)
        for label,value in [('Light',.5),('Steady',1.0),('Heavy',1.7)]:
            action=intensity.addAction(label); action.setCheckable(True)
            action.setChecked(value==1.0); group.addAction(action)
            def choose(checked,v=value):
                if checked:
                    owner.intensity=v; owner.reset_flakes()
            action.toggled.connect(choose)
        accumulate=self.menu.addAction('Accumulate'); accumulate.setCheckable(True); accumulate.setChecked(True)
        accumulate.toggled.connect(lambda checked:setattr(owner,'accumulate',checked))
        windows=self.menu.addAction('Snow on windows'); windows.setCheckable(True); windows.setChecked(True)
        windows.toggled.connect(lambda checked:setattr(owner,'on_windows',checked))
        self.menu.addAction('Clear snow').triggered.connect(owner.clear)
        self.menu.addSeparator()
        self.menu.addAction('Quit').triggered.connect(lambda:setattr(owner,'running',False))
        self.tray.setContextMenu(self.menu)
        self.tray.show()

    def present(self,banks,flakes,blockers):
        self.layer.set_scene(banks,flakes,blockers)

    def pump(self):
        self.app.processEvents()

    def close(self):
        if hasattr(self,'tray'): self.tray.hide()
        self.layer.close()
        self.app.processEvents()
