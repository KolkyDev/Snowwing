"""Offscreen frame-cost benchmark; does not open a desktop overlay."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import random
import time
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage,QPainter,QRegion
from PySide6.QtWidgets import QApplication
from rendering import SnowLayer,qt_sprite,flake
from simulation import SnowWorld


def main():
    app=QApplication.instance() or QApplication([])
    width,height=5120,1600
    world=SnowWorld(width,height,seed=4)
    roofs=[(0,1560,width,'floor')]+[(150+i*600,250+(i%3)*250,650+i*600,i) for i in range(7)]
    blocks=[(a,b,c,b+260) for a,b,c,k in roofs if k!='floor']
    world.set_geometry(roofs,blocks)
    sprites=[qt_sprite(flake(r,(230,240,255),190)) for r in (.85,1.15,1.65,2.1)]
    layer=SnowLayer(width,height,sprites)
    image=QImage(width,height,QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    rng=random.Random(3)
    positions=[(rng.uniform(0,width),rng.uniform(0,height),i%4,1) for i in range(280)]
    count=120
    start=time.perf_counter()
    for frame in range(count):
        world.step(1/60)
        banks=[(a,b,c,k,world.banks[k].heights) for a,b,c,k in roofs]
        flakes=[(x,(y+frame*2)%height,index,scale) for x,y,index,scale in positions]
        layer.set_scene(banks,flakes,blocks)
        painter=QPainter(image)
        layer.paint_scene(painter,QRegion(layer.rect()))
        painter.end()
    elapsed=time.perf_counter()-start
    print(f'{width}x{height}, 8 banks, 280 flakes: {elapsed/count*1000:.2f} ms/frame')
    print('Offscreen measurement; excludes native desktop composition and window enumeration.')
    layer.close()


if __name__=='__main__': main()
