"""Headless checks for material conservation and snow-bank dynamics."""
import unittest
from physics import SnowBank


class SnowPhysicsTests(unittest.TestCase):
    def test_deposition_conserves_added_mass_at_edge(self):
        bank=SnowBank(160,initial_depth=0)
        bank.deposit(0,12)
        self.assertAlmostEqual(bank.total_mass,12)
        self.assertGreater(bank.height_at(0),bank.height_at(30))

    def test_steep_heap_slumps_without_losing_material(self):
        bank=SnowBank(200,initial_depth=0)
        bank.deposit(100,160,spread=1)
        peak=max(bank.heights)
        released=0
        for _ in range(240):
            released += sum(m for _,m,_ in bank.step(1/60))
        self.assertLess(max(bank.heights),peak*.7)
        self.assertGreater(bank.height_at(85),0)
        self.assertAlmostEqual(bank.total_mass+released,160,places=7)
        self.assertGreaterEqual(min(bank.mass),0)

    def test_settling_changes_density_without_melting(self):
        bank=SnowBank(400,initial_depth=0)
        bank.deposit(200,80,spread=35)
        before=bank.height_at(200)
        mass=bank.total_mass
        for _ in range(180): bank.step(1/60)
        self.assertLess(bank.height_at(200),before)
        self.assertAlmostEqual(bank.total_mass,mass,places=7)

    def test_resize_conserves_mass_and_bulk_volume(self):
        bank=SnowBank(310,seed=4)
        mass=bank.total_mass
        volume=sum(m/p for m,p in zip(bank.mass,bank.packing))
        for width in (70,903,177,310):
            bank.resize(width)
            self.assertAlmostEqual(bank.total_mass,mass,places=7)
            self.assertAlmostEqual(sum(m/p for m,p in zip(bank.mass,bank.packing)),volume,places=7)

    def test_edge_sheds_material_and_impulse_moves_heap(self):
        bank=SnowBank(180,initial_depth=0)
        bank.deposit(0,70,spread=3)
        shed=[]
        for _ in range(20): shed.extend(bank.step(1/60))
        self.assertTrue(shed)
        self.assertAlmostEqual(bank.total_mass+sum(m for _,m,_ in shed),70)
        bank=SnowBank(300,initial_depth=0)
        bank.deposit(150,80,spread=20)
        center=lambda:sum((i+.5)*bank.dx*m for i,m in enumerate(bank.mass))/bank.total_mass
        before=center()
        bank.impulse(150,80,100)
        for _ in range(60): bank.step(1/60)
        self.assertGreater(center(),before+5)

    def test_fixed_timestep_is_independent_of_display_rate(self):
        a=SnowBank(300,seed=3); b=SnowBank(300,seed=3)
        for _ in range(60): a.step(1/60)
        for _ in range(10): b.step(.1)
        for x,y in zip(a.mass,b.mass): self.assertAlmostEqual(x,y,places=7)


if __name__=='__main__': unittest.main()
