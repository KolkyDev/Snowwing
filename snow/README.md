# Desktop Snow

Desktop snowfall for Windows, with a local granular snow simulation and a transparent Qt overlay.

## Run

Python 3.10 or newer is required.

```powershell
python -m pip install -r requirements.txt
python snow.py
```

Use `start.bat` to start and `stop.bat` to stop. The tray menu provides Pause, Light/Steady/Heavy snowfall, Accumulate, Snow on windows, Clear snow, and Quit. Only one instance can run. There is no automatic restart or startup registration.

## Behavior

Snow collects on visible window tops and above the taskbar. It settles, compacts, and slumps; the cursor sweeps it into airborne material. Moving a window sheds clumps, while closing or minimizing it releases its bank. Falling clumps can land on lower surfaces and burst into powder. Application interiors remain unobstructed.

`physics.py` tracks mass, packing density, and lateral velocity in 4-pixel columns with a fixed 60 Hz step. `simulation.py` handles collisions, cursor interaction, support changes, and airborne material. `rendering.py` draws cached contours and sprites using Qt, updating changed regions. Display updates target 30 FPS; bank contours refresh at up to 15 FPS.

This is an independent 2D implementation. No third-party snow application source is included. Material leaving the desktop is discarded; closing the app resets the simulation. Rectangular window bounds are used; irregular transparent windows and rounded corners may leave small gaps. Monitor layout changes require restarting.

## Verification

```powershell
python -m unittest test_physics test_simulation test_rendering -v
python benchmark.py
```

The rendering tests and benchmark use an offscreen backend and do not show the overlay. Benchmark timings exclude native desktop composition and window enumeration. The new Qt integration still needs an interactive desktop check.

## Privacy

Runs locally, without telemetry, network calls, or file logging. Review Git author settings and commit history before publishing.
