# Goniometric imaging software

GonioImsoft is a command line Python program designed to control the
goniometric high-speed imaging experiments where

* rotary encoder values are read over serial (pySerial)
* NI-DAQmx is used for general input/output (nidaqmx)
* the camera is controlled over MicroManager (pymmcore)

It was developed for the need of imaging 200 distinct
rotations (eye locations) per specimen fast, requiring
only the space bar to be pressed between the rotations.

For general imaging, without these specific needs,
it is easier to use MicroManager directly.

Following block diagram illustrates the used software architecture

´´´
GonioImsoft Core
  |
  |__ nidaqmx - Control NI boards (trigger, stimuli)
  |
  |__ pyserial - Read Arduino (rotation data)
  |
  |__ Camera Client
        |_Camera Server
	    |
	    |__ pymmcore - camera control using MicroManager
	    |__ tifffile - writes images/stacks
´´´

Thanks to the camera server/client model,
the camera(s) can be ran on another computer(s)
allowing parallel data acquisition.



## Required hardware and current limitations

* MicroManager supported camera device
* National Instruments input/output board (NI specificity can be
  lifted in future by using PyVISA or similar)
* Serial device reporting rotation values in format "pos1,pos2\n"

Windows and Linux tested.


## How to install

### Rotary encoders

Rotary encoders, mechanically attached to rotation stages,
monitor the rotation of the imaged specimen/sample.
Their state is digitally read out using an Arduino microcontroller.

In our system, we used two 1024-step rotary encoders attached on
two perpendicular rotation stages.
If your system is identical, you can flash 
`arduino/angle_sensors/angle_sensors.ino` and use the Serial Monitor
in the Arduino IDE to confirm it works.

If your system differs, you may have to modify the `ino` file.
However, any serial device reporting rotations in format "pos1,pos2\n"
will do. Here, pos1 and pos2 are rotation steps (integers)
of the two encoders.


### Main software (using pip)

First please make sure that you have
* MicroManager installation with a working camera
* National Insturments cards configured with
names *Dev1* and *Dev2* for input and output, respectively
* Python 3.6 or newer

Then, use pip to install

```
pip install gonio-imsoft
```

## How to use

You can launch the main program using

```
python -m gonioimsoft.tui
```


