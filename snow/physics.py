"""Conservative 2D cross-section of a cohesive granular snow bank."""
import math
import random


class SnowBank:
    def __init__(self, width, spacing=4.0, seed=None, initial_depth=5.0):
        self.width = max(1.0, float(width))
        self.count = max(2, math.ceil(self.width / spacing))
        self.dx = self.width / self.count
        self.mass = [0.0] * self.count
        self.packing = [0.30] * self.count
        self.velocity = [0.0] * self.count
        self.revision = 0
        self.clock = 0.0
        if initial_depth:
            rng = random.Random(seed)
            events = max(12, self.count // 2)
            for _ in range(events):
                self.deposit(rng.uniform(0, self.width),
                             self.width * initial_depth * .30 / events,
                             rng.uniform(9, 28))

    @property
    def heights(self):
        return [self.height_at(i*self.width/self.count) for i in range(self.count+1)]

    @property
    def total_mass(self):
        return sum(self.mass)

    def height_at(self, x):
        t = max(0.0, min(self.count - 1.0, x / self.dx - .5))
        i = min(self.count - 2, int(t))
        u = t - i
        return ((1-u) * self.mass[i] / self.packing[i]
                + u * self.mass[i+1] / self.packing[i+1]) / self.dx

    def deposit(self, x, amount, spread=4.0):
        if amount <= 0:
            return
        lo = max(0, int((x - spread * 3) / self.dx))
        hi = min(self.count, math.ceil((x + spread * 3) / self.dx) + 1)
        weights = [(i, math.exp(-.5 * (((i+.5)*self.dx-x) / max(1,spread))**2))
                   for i in range(lo,hi)]
        normalizer = sum(w for _,w in weights)
        if not normalizer:
            return
        for i, w in weights:
            added = amount * w / normalizer
            previous = self.mass[i]
            # Fresh loose powder lowers the bulk density of compacted snow.
            self.packing[i] = (previous + added) / (previous/self.packing[i] + added/.27)
            self.mass[i] += added
        self.revision += 1

    def impulse(self, x, radius, speed):
        """Local horizontal impulse, in pixels/second, for future interactions."""
        for i in range(self.count):
            distance = ((i+.5)*self.dx-x) / max(1,radius)
            self.velocity[i] += speed * math.exp(-.5*distance*distance)

    def step(self, dt):
        """Returns loose material (local x, mass, lateral velocity) leaving edges."""
        self.clock += max(0,min(dt,.25))
        released = []
        changed = False
        while self.clock >= 1/60:
            self.clock -= 1/60
            h = [m/(self.dx*p) for m,p in zip(self.mass,self.packing)]
            delta = [0.0]*self.count
            for i in range(self.count-1):
                difference = h[i]-h[i+1]
                # Cohesion and angle of repose allow stable irregular mounds.
                excess = max(0,abs(difference)-(1.1+self.dx*.48))
                slope_flux = math.copysign(excess*self.dx*.27*.12,difference)
                drift = (self.velocity[i]+self.velocity[i+1])*.5
                source = i if drift >= 0 else i+1
                transport = drift/self.dx/60*self.mass[source]
                flux = slope_flux+transport
                donor = i if flux >= 0 else i+1
                flux = math.copysign(min(abs(flux),self.mass[donor]*.22),flux)
                delta[i] -= flux; delta[i+1] += flux
            for i in range(self.count):
                self.mass[i] += delta[i]
                target = .43 + min(.10,h[i]*.002)
                compacted = min(target,self.packing[i]+(target-self.packing[i])/60*.10)
                if abs(delta[i]) > 1e-7 or (self.mass[i] > 0 and abs(compacted-self.packing[i]) > 1e-7):
                    changed = True
                self.packing[i] = compacted
                self.velocity[i] *= math.exp(-5/60)
            for i, direction in ((0,-1),(self.count-1,1)):
                height = self.mass[i]/(self.dx*self.packing[i])
                # Unsupported lips shed grains instead of silently deleting volume.
                if height > 3.5:
                    amount = min(self.mass[i]*.08,(height-3.5)*self.dx*.27*.08)
                    self.mass[i] -= amount
                    released.append((0 if i == 0 else self.width,amount,
                                     direction*(7+abs(self.velocity[i]))))
                    changed = True
        if changed:
            self.revision += 1
        return released

    def scoop(self, x, radius, fraction):
        """Remove material under a brush; return exact mass and local position."""
        removed=[]
        for i in range(max(0,int((x-radius)/self.dx)),
                       min(self.count,math.ceil((x+radius)/self.dx))):
            center=(i+.5)*self.dx
            weight=max(0,1-((center-x)/max(1,radius))**2)
            amount=self.mass[i]*min(1,max(0,fraction)*weight)
            if amount > 1e-8:
                self.mass[i]-=amount
                removed.append((center,amount))
        if removed:
            self.revision+=1
        return removed

    def drain(self, fraction=1.0, chunk_width=16):
        """Detach grouped clumps without discarding their material."""
        chunks=[]
        group=max(1,round(chunk_width/self.dx))
        fraction=max(0,min(1,fraction))
        for start in range(0,self.count,group):
            mass=weighted_x=0.0
            for i in range(start,min(self.count,start+group)):
                amount=self.mass[i]*fraction
                self.mass[i]-=amount
                mass+=amount
                weighted_x+=(i+.5)*self.dx*amount
            if mass > 1e-8:
                chunks.append((weighted_x/mass,mass))
        if chunks:
            self.revision+=1
        return chunks

    def resize(self, width):
        """Redistribute material by overlap; resizing never creates or loses mass."""
        width=max(1.0,float(width))
        count=max(2,math.ceil(width/4))
        masses=[0.0]*count; volumes=[0.0]*count
        for i, mass in enumerate(self.mass):
            a=i/self.count*count; b=(i+1)/self.count*count
            for j in range(int(a),min(count,math.ceil(b))):
                fraction=max(0,min(b,j+1)-max(a,j))/(b-a)
                masses[j] += mass*fraction
                volumes[j] += mass*fraction/self.packing[i]
        self.width=width; self.count=count; self.dx=width/count
        self.mass=masses
        self.packing=[m/v if v else .30 for m,v in zip(masses,volumes)]
        self.velocity=[0.0]*count
        self.revision += 1
