"""Desktop snowfall for Windows."""
import ctypes as C
from ctypes import wintypes as W
import math
import random
import sys
import time
from rendering import Surface
from simulation import SnowWorld

if sys.platform != 'win32':
    raise SystemExit('Desktop Snow requires Windows.')

user32=C.WinDLL('user32',use_last_error=True)
try:
    C.windll.shcore.SetProcessDpiAwareness(2)
except (AttributeError,OSError):
    user32.SetProcessDPIAware()
ENUMPROC=C.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
user32.EnumWindows.argtypes=[ENUMPROC,W.LPARAM]
user32.GetWindowRect.argtypes=[W.HWND,C.POINTER(W.RECT)]
user32.IsWindowVisible.argtypes=[W.HWND]
user32.IsIconic.argtypes=[W.HWND]
user32.GetCursorPos.argtypes=[C.POINTER(W.POINT)]


class Snow:
    def __init__(self):
        self.x=user32.GetSystemMetrics(76)
        self.y=user32.GetSystemMetrics(77)
        self.width=user32.GetSystemMetrics(78)
        self.height=user32.GetSystemMetrics(79)
        self.surface=Surface(self.x,self.y,self.width,self.height)
        self.hwnd=self.surface.hwnd
        self.world=SnowWorld(self.width,self.height)
        self.flakes=[]
        self.paused=False
        self.running=True
        self.accumulate=True
        self.on_windows=True
        self.intensity=1.0
        self.last=time.perf_counter()
        self.scan_at=0
        self.snow_time=0
        self.surface.install_controls(self)
        self.reset_flakes()

    def reset_flakes(self):
        count=int(min(280,max(70,self.width/18))*self.intensity)
        while len(self.flakes)<count:
            kind=random.randrange(4)
            self.flakes.append([random.uniform(0,self.width),random.uniform(-100,self.height),
                random.uniform(65,145)*(0.8+kind*.12),(.85,1.15,1.65,2.1)[kind],
                random.uniform(0,math.tau),kind])
        del self.flakes[count:]

    def clear(self):
        for bank in self.world.banks.values(): bank.drain()
        self.world.particles.clear()

    def scan_windows(self):
        windows=[]
        @ENUMPROC
        def visit(hwnd,_):
            if hwnd==self.hwnd or not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
                return True
            name=C.create_unicode_buffer(256)
            user32.GetClassNameW(W.HWND(hwnd),name,256)
            if name.value in ('Progman','WorkerW','tooltips_class32'):
                return True
            rect=W.RECT()
            if not user32.GetWindowRect(hwnd,C.byref(rect)): return True
            try:
                cloaked=W.DWORD()
                C.windll.dwmapi.DwmGetWindowAttribute(W.HWND(hwnd),14,C.byref(cloaked),C.sizeof(cloaked))
                if cloaked.value: return True
                visual=W.RECT()
                if C.windll.dwmapi.DwmGetWindowAttribute(W.HWND(hwnd),9,C.byref(visual),C.sizeof(visual))==0:
                    rect=visual
            except (AttributeError,OSError):
                pass
            left,top=rect.left-self.x,rect.top-self.y
            right,bottom=rect.right-self.x,rect.bottom-self.y
            if right-left>20 and bottom-top>20:
                windows.append((int(hwnd),left,top,right,bottom,name.value))
            return True
        user32.EnumWindows(visit,0)
        roofs=[]
        if self.on_windows:
            for hwnd,left,top,right,bottom,name in windows:
                if 3<top<self.height and right>0 and left<self.width and name not in ('Shell_TrayWnd','Shell_SecondaryTrayWnd'):
                    roofs.append((left,top,right,hwnd))
        MONITORPROC=C.WINFUNCTYPE(W.BOOL,W.HANDLE,W.HDC,C.POINTER(W.RECT),W.LPARAM)
        class MonitorInfo(C.Structure):
            _fields_=[('size',W.DWORD),('monitor',W.RECT),('work',W.RECT),('flags',W.DWORD)]
        @MONITORPROC
        def monitor(handle,dc,rect,data):
            info=MonitorInfo(); info.size=C.sizeof(info)
            if user32.GetMonitorInfoW(W.HANDLE(handle),C.byref(info)):
                r=info.work
                roofs.append((r.left-self.x,r.bottom-self.y,r.right-self.x,('floor',int(handle))))
            return True
        user32.EnumDisplayMonitors(None,None,monitor,0)
        self.world.set_geometry(roofs,[(a,b,c,d) for _,a,b,c,d,_ in windows])

    def tick(self):
        now=time.perf_counter()
        dt=min(.1,now-self.last)
        self.last=now
        if now>=self.scan_at:
            self.scan_windows()
            self.scan_at=now+.075
        if not self.paused:
            point=W.POINT()
            cursor=(point.x-self.x,point.y-self.y) if user32.GetCursorPos(C.byref(point)) else None
            self.world.step(dt,cursor)
            self.snow_time+=dt
        draw=[]
        for f in self.flakes:
            x,y,speed,radius,phase,index=f
            if not self.paused:
                nx=(x+(math.sin(self.snow_time*.7+phase)*14+5)*dt)%self.width
                ny=y+speed*dt
                hit=self.world.collision(nx,y,ny,radius) if self.accumulate else None
                if hit:
                    _,key,local=hit
                    self.world.deposit(key,local,math.pi*radius*radius*.27)
                if hit or ny>self.height+10:
                    nx,ny=random.uniform(0,self.width),random.uniform(-70,-5)
                f[0],f[1]=nx,ny
            if not self.world.hidden(f[0],f[1],radius+2):
                draw.append((f[0],f[1],index,1.0))
        for p in self.world.particles:
            scale=min(2.4,max(.7,math.sqrt(p.mass)/2))
            if not self.world.hidden(p.x,p.y,scale*3):
                draw.append((p.x,p.y,1,scale))
        banks=[(left,top,right,key,self.world.banks[key].heights)
               for key,(left,top,right) in self.world.roofs.items()]
        self.surface.present(banks,draw,self.world.blockers)

    def run(self):
        try:
            while self.running and not getattr(self,'stop_requested',lambda:False)():
                started=time.perf_counter()
                self.surface.pump()
                self.tick()
                time.sleep(max(0,1/30-(time.perf_counter()-started)))
        except KeyboardInterrupt:
            pass
        finally:
            self.surface.close()


def main():
    kernel = C.WinDLL('kernel32', use_last_error=True)
    kernel.CreateMutexW.argtypes = [C.c_void_p, W.BOOL, W.LPCWSTR]
    kernel.CreateMutexW.restype = W.HANDLE
    kernel.CreateEventW.argtypes = [C.c_void_p, W.BOOL, W.BOOL, W.LPCWSTR]
    kernel.CreateEventW.restype = W.HANDLE
    kernel.OpenEventW.argtypes = [W.DWORD, W.BOOL, W.LPCWSTR]
    kernel.OpenEventW.restype = W.HANDLE
    kernel.SetEvent.argtypes = [W.HANDLE]
    kernel.WaitForSingleObject.argtypes = [W.HANDLE, W.DWORD]
    kernel.CloseHandle.argtypes = [W.HANDLE]
    event_name = 'Local\\DesktopSnow.Stop'
    if '--stop' in sys.argv:
        event = kernel.OpenEventW(2, False, event_name)
        if event:
            kernel.SetEvent(event)
            kernel.CloseHandle(event)
            print('Snow stop requested.')
        else:
            print('Snow is not running.')
        return
    mutex = kernel.CreateMutexW(None, False, 'Local\\DesktopSnow.Instance')
    error = C.get_last_error()
    if not mutex:
        raise C.WinError(error)
    if error == 183:
        kernel.CloseHandle(mutex)
        print('Snow is already running. Use stop.bat to stop it.')
        return
    event = kernel.CreateEventW(None, True, False, event_name)
    if not event:
        kernel.CloseHandle(mutex)
        raise C.WinError(C.get_last_error())
    try:
        app = Snow()
        app.stop_requested = lambda: kernel.WaitForSingleObject(event, 0) == 0
        app.run()
    finally:
        kernel.CloseHandle(event)
        kernel.CloseHandle(mutex)


if __name__ == '__main__':
    main()
