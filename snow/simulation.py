"""Desktop snow dynamics, independent of Windows and the display backend."""
from dataclasses import dataclass
import math
import random
from physics import SnowBank


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    mass: float
    source: object = None
    grace: float = 0.0
    can_break: bool = False


class SnowWorld:
    def __init__(self, width, height, seed=None):
        self.width=width
        self.height=height
        self.rng=random.Random(seed)
        self.banks={}
        self.roofs={}
        self.blockers=[]
        self.particles=[]
        self.time=0.0
        self.last_cursor=None
        self.last_geometry_time=None
        self.seen=set()
        self.escaped_mass=0.0
        self.initialized=False

    def hidden(self,x,y,padding=0):
        return any(a-padding <= x <= c+padding and b-padding <= y <= d+padding
                   for a,b,c,d in self.blockers)

    def set_geometry(self, roofs, blockers):
        """Roofs are (left, top, right, key); blockers exclude desktop wallpaper."""
        current={key:(left,top,right) for left,top,right,key in roofs}
        elapsed=max(.016,self.time-(self.last_geometry_time or 0))
        for key,(left,top,right) in self.roofs.items():
            if key not in current:
                bank=self.banks.pop(key)
                for local,mass in bank.drain():
                    self.particles.append(Particle(left+local,top-bank.height_at(local)-2,
                        self.rng.uniform(-9,9),15,mass,key,self.time+.08,True))
        for key,(left,top,right) in current.items():
            bank=self.banks.get(key)
            if bank is None:
                initial=2.5 if not self.initialized else 0
                self.banks[key]=bank=SnowBank(right-left,seed=len(self.seen),initial_depth=initial)
                self.seen.add(key)
            elif abs(bank.width-(right-left)) > .5:
                bank.resize(right-left)
            previous=self.roofs.get(key)
            if previous:
                dx=left-previous[0]; dy=top-previous[1]
                if dx or dy:
                    speed=math.hypot(dx,dy)/elapsed
                    bank.impulse(bank.width/2,bank.width,max(-220,min(220,-dx/elapsed*.22)))
                    fraction=min(.65,max(0,speed-100)/1400)
                    if fraction:
                        for local,mass in bank.drain(fraction,chunk_width=24):
                            # Loose material keeps its old world position as support moves away.
                            x=previous[0]+local/(right-left)*(previous[2]-previous[0])
                            self.particles.append(Particle(x,previous[1]-4,
                                -dx/elapsed*.10,self.rng.uniform(-30,10),mass,
                                key,self.time+.15,True))
        self.roofs=current
        self.blockers=list(blockers)
        self.last_geometry_time=self.time
        self.initialized=True
        self._limit_particles()

    def collision(self,x,old_y,new_y,radius=0,ignore=None):
        if new_y < old_y:
            return None
        hits=[]
        for key,(left,top,right) in self.roofs.items():
            if key == ignore or not left <= x < right:
                continue
            surface=top-self.banks[key].height_at(x-left)
            if old_y+radius <= surface <= new_y+radius and not self.hidden(x,surface-.3):
                hits.append((surface,key,x-left))
        return min(hits,key=lambda h:h[0]) if hits else None

    def deposit(self,key,x,mass):
        self.banks[key].deposit(x,mass)

    def brush(self,cursor,dt):
        if cursor is None:
            self.last_cursor=None
            return
        if self.last_cursor is None:
            self.last_cursor=cursor
            return
        px,py=self.last_cursor
        x,y=cursor
        self.last_cursor=cursor
        distance=math.hypot(x-px,y-py)
        if distance < .8 or self.hidden(x,y):
            return
        speed=min(1400,distance/max(.001,dt))
        steps=max(1,min(24,math.ceil(distance/8)))
        for j in range(1,steps+1):
            cx=px+(x-px)*j/steps; cy=py+(y-py)*j/steps
            if self.hidden(cx,cy):
                continue
            for key,(left,top,right) in self.roofs.items():
                if not left-16 <= cx <= right+16:
                    continue
                bank=self.banks[key]
                surface=top-bank.height_at(max(0,min(bank.width,cx-left)))
                if not surface-14 <= cy <= top+2:
                    continue
                removed=bank.scoop(cx-left,16,min(.9,.3+speed/1800)/steps)
                # Group tiny grains into a few parcels rather than one object per cell.
                for start in range(0,len(removed),3):
                    group=removed[start:start+3]
                    mass=sum(m for _,m in group)
                    local=sum(xx*m for xx,m in group)/mass
                    side=-1 if left+local < cx else 1
                    vx=(x-px)/max(.001,dt)*.22+side*self.rng.uniform(18,50)
                    self.particles.append(Particle(left+local,surface-2,vx,
                        -self.rng.uniform(35,105),mass,key,self.time+.12,False))

    def _limit_particles(self):
        if len(self.particles) <= 600:
            return
        # Merge nearby parcels; preserve mass and momentum under heavy interaction.
        merged={}
        for p in self.particles:
            cell=(int(p.x//20),int(p.y//20),p.source,p.can_break)
            other=merged.get(cell)
            if other is None:
                merged[cell]=p
            else:
                total=other.mass+p.mass
                for name in ('x','y','vx','vy'):
                    setattr(other,name,(getattr(other,name)*other.mass+getattr(p,name)*p.mass)/total)
                other.mass=total
                other.grace=max(other.grace,p.grace)
        self.particles=list(merged.values())

    def step(self,dt,cursor=None):
        dt=max(0,min(.1,dt))
        self.time+=dt
        self.brush(cursor,dt)
        for key,(left,top,right) in self.roofs.items():
            emissions=self.banks[key].step(dt)
            edges={}
            for local,mass,vx in emissions:
                edge=-1 if local == 0 else 1
                if edge not in edges: edges[edge]=[local,0,vx]
                edges[edge][1]+=mass
            for edge,(local,mass,vx) in edges.items():
                self.particles.append(Particle(left+local+edge*2,top-2,vx,14,
                                               mass,key,self.time+.08,False))
        remaining=[]
        for p in self.particles:
            radius=min(5,max(.6,math.sqrt(p.mass/math.pi)))
            nx=p.x+p.vx*dt
            ny=p.y+p.vy*dt+.5*300*dt*dt
            ignore=p.source if self.time < p.grace else None
            hit=self.collision(nx,p.y,ny,radius,ignore)
            if hit:
                surface,key,local=hit
                if p.can_break and p.mass > 1.5 and p.vy > 65:
                    self.deposit(key,local,p.mass*.65)
                    for side in (-1,1):
                        remaining.append(Particle(nx,surface-radius-2,
                            side*self.rng.uniform(20,55),-self.rng.uniform(30,70),
                            p.mass*.175,key,self.time+.14,False))
                else:
                    self.deposit(key,local,p.mass)
            elif -100 < nx < self.width+100 and ny < self.height+40:
                p.x=nx; p.y=ny; p.vx*=math.exp(-dt*.5); p.vy+=300*dt
                remaining.append(p)
            else:
                self.escaped_mass+=p.mass
        self.particles=remaining
        self._limit_particles()

    @property
    def total_mass(self):
        return sum(b.total_mass for b in self.banks.values())+sum(p.mass for p in self.particles)+self.escaped_mass
