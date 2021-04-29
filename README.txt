# Pupil Imsoft

Pupil Imsoft is a command line Python program designed to control the
goniometric high-speed imaging experiments where

* rotary encoder values are read over serial (pySerial)
* NI-DAQmx is used for general input/output (nidaqmx)
* the camera is controlled over MicroManager (MMCorePy)

It was developed for the need of imaging 200 distinct
rotations (eye locations) per specimen fast, requiring
only the space bar to be pressed between the rotations.

For general imaging, it may be more convinient
to use MicroManager or similar.


## Required hardware and current limitations

* Any MicroManager supported imaging device
* Any National Instruments input/output board (NI specificity can be lifted in
  future by using PyVISA or similar)
* Any serial device reporting rotation values in format "pos1,pos2\n"

There are currently some limitations however (to be fixed soon)

* **Limitation 1**. Imsoft yet lacks dialogs to select and configure
  devices in a user-friendly manner.
  Currently, the same can be achieved by modifications in
  `camera_server.Camera.__init__`, `core.Dynamic.analog_output`
  and `arduino_serial.ArduinoReader`.

* **Limitation 2**. At least previously, MicroManager used to ship only Python 2 bindings
  and because of this, the *camera_server.py*
  has to be ran with Python 2 and rest of the software with
  Python 3.

* **Limitation 3**. It only works on Windows. This is because of using
  nidaqmx and msvcrt modules.


## How to install

### Rotary encoders

We connected two 1024-step rotary encoders to two perpendicular
rotation stages (goniometers), and used Arduino for readout.

If using similar setup to us, you can flash 
*arduino.angle_sensors/angle_sensors.ino* and use Serial Monitor
in the Arduino IDE to confirm that the readout work.

Alternatively, any serial device reporting rotations in format "pos1,pos2\n"
where pos1 and pos2 are rotation steps of the two encoders will do.


### Main software

First make sure that you have
* a working MicroManager installation (camera works)
* National Insturments cards configured with names *Dev1* and *Dev2* for input
  and output, respectively
* Python 3 and Python 2

```
pip install pupil-imsoft
```

## How to use

```
python -m pupilimsoft.tui
```

