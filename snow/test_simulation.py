"""Behavior checks without opening a desktop overlay."""
import unittest
from simulation import SnowWorld,Particle


class WorldTests(unittest.TestCase):
    def scene(self):
        world=SnowWorld(640,480,seed=3)
        world.set_geometry([(80,150,560,1),(0,450,640,'floor')],[(80,150,560,300)])
        return world

    def test_closed_or_minimized_window_drops_its_mass(self):
        world=self.scene(); mass=world.total_mass
        bank_mass=world.banks[1].total_mass
        world.set_geometry([(0,450,640,'floor')],[])
        self.assertNotIn(1,world.banks)
        self.assertAlmostEqual(sum(p.mass for p in world.particles),bank_mass)
        self.assertAlmostEqual(world.total_mass,mass)
        for _ in range(150): world.step(1/60)
        self.assertAlmostEqual(world.total_mass,mass,places=6)
        world.set_geometry([(80,150,560,1),(0,450,640,'floor')],[(80,150,560,300)])
        self.assertEqual(world.banks[1].total_mass,0)

    def test_cursor_sweeps_surface_without_deleting_snow(self):
        world=self.scene(); bank=world.banks[1]
        bank.deposit(180,140,spread=20)
        mass=world.total_mass; before=bank.total_mass
        y=150-bank.height_at(180)-2
        world.brush((235,y),1/60)
        world.brush((285,y),1/60)
        self.assertLess(bank.total_mass,before)
        self.assertTrue(world.particles)
        self.assertAlmostEqual(world.total_mass,mass)

    def test_fast_window_motion_sheds_clumps(self):
        world=self.scene(); mass=world.total_mass
        world.step(.1)
        world.set_geometry([(180,140,660,1),(0,450,640,'floor')],[(180,140,660,300)])
        self.assertTrue(any(p.can_break for p in world.particles))
        self.assertAlmostEqual(world.total_mass,mass)

    def test_clump_breakup_conserves_mass(self):
        world=SnowWorld(400,400,seed=2)
        world.set_geometry([(0,350,400,'floor')],[])
        world.banks['floor'].drain()
        world.particles=[Particle(200,345,0,200,12,can_break=True)]
        world.step(.05)
        self.assertAlmostEqual(world.total_mass,12)
        self.assertGreater(world.banks['floor'].total_mass,0)
        self.assertEqual(len([p for p in world.particles if p.source=='floor']),2)

    def test_hidden_roof_does_not_catch_snow(self):
        world=self.scene()
        world.blockers.insert(0,(0,0,640,180))
        self.assertIsNone(world.collision(250,50,155))

    def test_merging_particles_keeps_mass(self):
        world=SnowWorld(640,480)
        world.particles=[Particle(100+i%3,100,1,2,.2,source=1) for i in range(700)]
        mass=world.total_mass
        world._limit_particles()
        self.assertLess(len(world.particles),700)
        self.assertAlmostEqual(world.total_mass,mass)


if __name__=='__main__': unittest.main()
