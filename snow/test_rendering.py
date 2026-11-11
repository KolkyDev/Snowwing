"""Offscreen rendering checks. No desktop window is shown."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import unittest
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage,QPainter,QRegion
from PySide6.QtWidgets import QApplication
from rendering import SnowLayer,qt_sprite,flake


class RenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        sprite=qt_sprite(flake(2,(240,245,255),180))
        self.layer=SnowLayer(320,220,[sprite]*4)

    def tearDown(self): self.layer.close()

    def image(self):
        image=QImage(320,220,QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter=QPainter(image)
        self.layer.paint_scene(painter,QRegion(self.layer.rect()))
        painter.end()
        return image

    def test_window_interiors_remain_transparent(self):
        self.layer.set_scene([(20,100,300,1,[12]*71)],[(100,110,0,1)],[(20,100,300,200)])
        image=self.image()
        self.assertGreater(image.pixelColor(100,95).alpha(),0)
        self.assertEqual(image.pixelColor(100,110).alpha(),0)
        self.assertEqual(image.pixelColor(5,5).alpha(),0)

    def test_overlapping_flakes_blend_instead_of_erasing(self):
        self.layer.set_scene([],[(100,50,0,1)],[])
        single=self.image().pixelColor(100,50).alpha()
        self.layer.set_scene([],[(100,50,0,1),(100,50,0,1)],[])
        self.assertGreater(self.image().pixelColor(100,50).alpha(),single)

    def test_removed_occluder_exposes_snow(self):
        self.layer.set_scene([],[(100,50,0,1)],[(50,20,150,90)])
        self.assertEqual(self.image().pixelColor(100,50).alpha(),0)
        self.layer.set_scene([],[(100,50,0,1)],[])
        self.assertGreater(self.image().pixelColor(100,50).alpha(),0)

    def test_empty_bank_does_not_draw_white_baseline(self):
        self.layer.set_scene([(20,100,300,1,[0]*71)],[],[])
        self.assertEqual(self.image().pixelColor(100,100).alpha(),0)


if __name__=='__main__': unittest.main()
